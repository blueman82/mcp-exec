"""Application configuration using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    """Jira API settings."""

    model_config = SettingsConfigDict(env_prefix="JIRA_")

    base_url: str = "https://jira.corp.adobe.com"
    api_token: str = ""
    username: str = ""
    projects: list[str] = Field(
        default=["CPGNCX", "AMSE", "CPGNREQ", "CPGNPROV", "CAMP", "NEO", "PLATIR", "CPGNTT"]
    )
    org_groups: list[str] = Field(
        default=["ORG-VALLET-ALL", "ORG-BRONSHTE-ALL", "ORG-OMEARA-ALL", "ORG-ADCAIN-ALL"]
    )


class SlackSettings(BaseSettings):
    """Slack API settings."""

    model_config = SettingsConfigDict(env_prefix="SLACK_")

    bot_token: str = ""
    app_token: str = ""
    signing_secret: str = ""


class LLMSettings(BaseSettings):
    """LLM scoring settings."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    model: str = "gpt-4"
    api_key: str = ""
    threshold: float = 3.0


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

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jira: JiraSettings = Field(default_factory=JiraSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    gates: GateSettings = Field(default_factory=GateSettings)


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
