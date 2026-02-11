"""Application configuration using pydantic-settings."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LOG_FILE = Path("/var/log/bravo.log")


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "bravo"
    user: str = "bravo"
    password: str = ""
    min_pool_size: int = 5
    max_pool_size: int = 20

    @property
    def dsn(self) -> str:
        """Return PostgreSQL DSN."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class JiraSettings(BaseSettings):
    """Jira MCP client settings."""

    model_config = SettingsConfigDict(env_prefix="JIRA_")

    mcp_url: str = "http://mcp-jira:8081"
    projects: list[str] = Field(
        default=[
            "CPGNCX",
            "AMSE",
            "CPGNREQ",
            "CPGNPROV",
            "CAMP",
            "NEO",
            "PLATIR",
            "CPGNTT",
        ]
    )
    org_groups: list[str] = Field(
        default=[
            "ORG-VALLET-ALL",
            "ORG-BRONSHTE-ALL",
            "ORG-OMEARA-ALL",
            "ORG-ADCAIN-ALL",
        ]
    )
    max_concurrent_requests: int = 10
    request_timeout: float = 30.0
    max_retries: int = 3
    email_domain: str = "adobe.com"


class SlackSettings(BaseSettings):
    """Slack API settings."""

    model_config = SettingsConfigDict(env_prefix="SLACK_")

    bot_token: str = ""
    app_token: str = ""
    signing_secret: str = ""


class LLMSettings(BaseSettings):
    """LLM scoring settings."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    model: str = ""
    api_key: str = ""
    endpoint: str = ""
    api_version: str = ""
    threshold: float = 3.0
    reasoning_effort: str = "low"


class GateSettings(BaseSettings):
    """Heuristic gate settings."""

    model_config = SettingsConfigDict(env_prefix="GATE_")

    g1_enabled: bool = True
    g2_stale_hours: int = 4
    g3_response_hours: int = 24
    g4_resolution_hours: int = 24


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="BRAVO_",
        env_nested_delimiter="__",
    )

    debug: bool = False
    log_level: str = "INFO"
    poll_interval_minutes: int = 60
    nudge_cooldown_hours: int = 24

    aws_secrets_enabled: bool = False
    aws_region: str = "eu-west-1"
    aws_cache_ttl: int = 3600
    aws_profile: str = ""

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jira: JiraSettings = Field(default_factory=JiraSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    gates: GateSettings = Field(default_factory=GateSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings singleton.

    Returns the same Settings instance across calls, allowing
    runtime mutations to persist until process restart.
    """
    return Settings()


async def load_settings() -> Settings:
    """Load settings, optionally hydrating from AWS Secrets Manager.

    When aws_secrets_enabled=True, fetches secrets from AWS and fills in
    any settings not already set via env vars. Env vars always take
    precedence over AWS values.

    Returns:
        Hydrated Settings instance.
    """
    settings = get_settings()
    if not settings.aws_secrets_enabled:
        return settings

    from bravo.services.secrets import SecretsManager

    async with SecretsManager(
        region=settings.aws_region,
        cache_ttl=settings.aws_cache_ttl,
        profile=settings.aws_profile or None,
    ) as sm:
        slack_secrets = await sm.get_slack_secrets()
        llm_secrets = await sm.get_llm_secrets()
        db_secrets = await sm.get_database_secrets()

    settings.slack.bot_token = settings.slack.bot_token or slack_secrets["bot_token"]
    settings.slack.app_token = settings.slack.app_token or slack_secrets["app_token"]
    settings.slack.signing_secret = settings.slack.signing_secret or slack_secrets.get("signing_secret", "")

    settings.llm.api_key = settings.llm.api_key or llm_secrets["api_key"]
    settings.llm.endpoint = settings.llm.endpoint or llm_secrets["endpoint"]
    settings.llm.api_version = settings.llm.api_version or llm_secrets.get("api_version", "")
    settings.llm.model = settings.llm.model or llm_secrets.get("model", "")

    settings.database.password = settings.database.password or db_secrets["password"]
    if "user" in db_secrets and "DB_USER" not in os.environ:
        settings.database.user = db_secrets["user"]
    if "host" in db_secrets and "DB_HOST" not in os.environ:
        settings.database.host = db_secrets["host"]

    return settings
