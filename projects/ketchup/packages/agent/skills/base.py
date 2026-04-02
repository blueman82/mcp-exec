"""Skill library data model and registry."""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


@runtime_checkable
class BaseSkillExecutor(Protocol):
    """Protocol for skill executors that handle tool calls."""

    async def setup(self, resolver: Any) -> None: ...
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str: ...


@dataclass
class SkillManifest:
    """Parsed skill manifest containing metadata, prompt, and tool definitions."""

    name: str
    description: str
    activation_keywords: list[str]
    feature_flag: str
    requires: list[str]
    executor_path: str
    prompt: str  # markdown body (system prompt fragment)
    tools: list[dict[str, Any]] = field(default_factory=list)  # OpenAI tool definitions


class SkillRegistry:
    """Discovers and loads skill manifests from the skills directory."""

    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir

    def load_enabled_skills(self) -> list[SkillManifest]:
        """Scan skills directory and return manifests for enabled skills."""
        if not self._skills_dir.is_dir():
            logger.warning("Skills directory not found: %s", self._skills_dir)
            return []

        enabled: list[SkillManifest] = []
        for child in sorted(self._skills_dir.iterdir()):
            manifest_path = child / "manifest.md"
            if child.is_dir() and manifest_path.exists():
                try:
                    manifest = self._parse_manifest(manifest_path)
                    flag_value = os.environ.get(manifest.feature_flag, "false").lower()
                    if flag_value == "true":
                        logger.info(
                            "Skill enabled: %s (flag=%s)", manifest.name, manifest.feature_flag
                        )
                        enabled.append(manifest)
                    else:
                        logger.debug(
                            "Skill disabled: %s (flag=%s=%s)",
                            manifest.name,
                            manifest.feature_flag,
                            flag_value,
                        )
                except Exception:
                    logger.exception("Failed to parse manifest: %s", manifest_path)
        return enabled

    def _parse_manifest(self, path: Path) -> SkillManifest:
        """Parse a manifest.md file into a SkillManifest."""
        content = path.read_text()

        # Split YAML frontmatter from markdown body
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid manifest format (missing --- delimiters): {path}")

        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()

        # Extract first ```json ... ``` code block as tools
        if json_match := re.search(r"```json\s*\n(.*?)\n```", body, re.DOTALL):
            tools = json.loads(json_match.group(1))
            prompt = body[: json_match.start()].strip()
        else:
            tools = []
            prompt = body

        return SkillManifest(
            name=frontmatter["name"],
            description=frontmatter["description"],
            activation_keywords=frontmatter.get("activation_keywords", []),
            feature_flag=frontmatter["feature_flag"],
            requires=frontmatter.get("requires", []),
            executor_path=frontmatter["executor_path"],
            prompt=prompt,
            tools=tools,
        )
