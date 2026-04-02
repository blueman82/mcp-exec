"""Tests that verify the RCA Historian manifest content matches source of truth."""

from pathlib import Path

import pytest

from packages.agent.rca.tools import RCA_TOOLS
from packages.agent.skills.base import SkillManifest, SkillRegistry

pytestmark = pytest.mark.unit

SKILLS_DIR = Path(__file__).resolve().parents[4] / "packages" / "agent" / "skills"


class TestRCAHistorianManifest:
    """Verify manifest.md content matches source files."""

    @pytest.fixture
    def manifest(self) -> SkillManifest:
        registry = SkillRegistry(skills_dir=SKILLS_DIR)
        manifest_path = SKILLS_DIR / "rca_historian" / "manifest.md"
        return registry._parse_manifest(manifest_path)

    def test_manifest_file_exists(self) -> None:
        manifest_path = SKILLS_DIR / "rca_historian" / "manifest.md"
        assert manifest_path.exists(), f"manifest.md not found at {manifest_path}"

    def test_has_four_tools(self, manifest) -> None:
        assert len(manifest.tools) == 4

    def test_tool_names_match_rca_tools(self, manifest) -> None:
        manifest_names = [t["function"]["name"] for t in manifest.tools]
        rca_names = [t["function"]["name"] for t in RCA_TOOLS]
        assert manifest_names == rca_names

    def test_tool_definitions_match_rca_tools(self, manifest) -> None:
        """Verify complete tool definitions match, not just names."""
        assert manifest.tools == RCA_TOOLS

    def test_prompt_contains_rca_historian_tags(self, manifest) -> None:
        assert "<rca_historian>" in manifest.prompt
        assert "</rca_historian>" in manifest.prompt

    def test_prompt_contains_tool_usage_guidelines(self, manifest) -> None:
        assert "<tool_usage_guidelines>" in manifest.prompt
        assert "search_similar_incidents" in manifest.prompt

    def test_feature_flag_is_correct(self, manifest) -> None:
        assert manifest.feature_flag == "KETCHUP_RCA_HISTORIAN_ENABLED"

    def test_executor_path_is_correct(self, manifest) -> None:
        assert (
            manifest.executor_path
            == "packages.agent.skills.rca_historian.executor.RCAHistorianExecutor"
        )

    def test_requires_agent_enabled(self, manifest) -> None:
        assert "KETCHUP_AGENT_ENABLED" in manifest.requires

    def test_name_is_rca_historian(self, manifest) -> None:
        assert manifest.name == "rca_historian"

    def test_has_non_empty_description(self, manifest) -> None:
        assert manifest.description

    def test_has_activation_keywords(self, manifest) -> None:
        assert manifest.activation_keywords
        assert "rca" in manifest.activation_keywords

    def test_prompt_is_non_empty(self, manifest) -> None:
        assert manifest.prompt

    def test_all_rca_tool_names_present_in_prompt(self, manifest) -> None:
        """Every RCA tool name should appear in the prompt guidelines."""
        for tool in RCA_TOOLS:
            tool_name = tool["function"]["name"]
            assert (
                tool_name in manifest.prompt
            ), f"Tool '{tool_name}' not referenced in manifest prompt"
