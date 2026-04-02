"""Tests for SkillRegistry manifest parsing and loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.agent.skills.base import SkillManifest, SkillRegistry

pytestmark = pytest.mark.unit


class TestParseManifest:
    """Test _parse_manifest with various manifest formats."""

    def _write_manifest(self, tmp_path: Path, content: str) -> Path:
        """Helper to write a manifest file and return its path."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        manifest = skill_dir / "manifest.md"
        manifest.write_text(content)
        return manifest

    def test_parses_valid_manifest(self, tmp_path: Path) -> None:
        content = """---
name: test_skill
description: A test skill
activation_keywords:
  - test
feature_flag: TEST_FLAG
requires: []
executor_path: some.module.Executor
---

Test prompt content.

```json
[{"type": "function", "function": {"name": "test_tool", "description": "A test tool", "parameters": {"type": "object", "properties": {}, "required": []}}}]
```
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert result.name == "test_skill"
        assert result.description == "A test skill"
        assert result.feature_flag == "TEST_FLAG"
        assert result.executor_path == "some.module.Executor"
        assert len(result.tools) == 1
        assert result.tools[0]["function"]["name"] == "test_tool"
        assert "Test prompt content." in result.prompt

    def test_parses_activation_keywords(self, tmp_path: Path) -> None:
        content = """---
name: kw_skill
description: Keyword test
activation_keywords:
  - incident
  - rca
feature_flag: KW_FLAG
requires: []
executor_path: some.module.Executor
---

Prompt text.
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert result.activation_keywords == ["incident", "rca"]

    def test_parses_requires_list(self, tmp_path: Path) -> None:
        content = """---
name: req_skill
description: Requires test
feature_flag: REQ_FLAG
requires:
  - KETCHUP_AGENT_ENABLED
executor_path: some.module.Executor
---

Prompt text.
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert result.requires == ["KETCHUP_AGENT_ENABLED"]

    def test_manifest_without_tools(self, tmp_path: Path) -> None:
        content = """---
name: no_tools
description: No tools skill
feature_flag: NO_TOOLS_FLAG
executor_path: some.module.Executor
---

Just a prompt with no JSON block.
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert result.tools == []
        assert "Just a prompt" in result.prompt

    def test_prompt_excludes_json_block(self, tmp_path: Path) -> None:
        content = """---
name: prompt_test
description: Prompt extraction test
feature_flag: PROMPT_FLAG
executor_path: some.module.Executor
---

This is the prompt section.

```json
[{"type": "function", "function": {"name": "a_tool", "description": "desc", "parameters": {"type": "object", "properties": {}, "required": []}}}]
```
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert "This is the prompt section." in result.prompt
        assert "```json" not in result.prompt

    def test_invalid_manifest_missing_delimiters(self, tmp_path: Path) -> None:
        content = "No frontmatter here"
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)

        with pytest.raises(ValueError, match="missing --- delimiters"):
            registry._parse_manifest(manifest_path)

    def test_returns_skill_manifest_instance(self, tmp_path: Path) -> None:
        content = """---
name: type_test
description: Type check
feature_flag: TYPE_FLAG
executor_path: some.module.Executor
---

Prompt.
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert isinstance(result, SkillManifest)

    def test_defaults_for_optional_fields(self, tmp_path: Path) -> None:
        content = """---
name: defaults_test
description: Defaults
feature_flag: DEFAULTS_FLAG
executor_path: some.module.Executor
---

Prompt.
"""
        manifest_path = self._write_manifest(tmp_path, content)
        registry = SkillRegistry(skills_dir=tmp_path)
        result = registry._parse_manifest(manifest_path)

        assert result.activation_keywords == []
        assert result.requires == []
        assert result.tools == []


class TestLoadEnabledSkills:
    """Test load_enabled_skills with env var gating."""

    def _create_skill_dir(self, tmp_path: Path, name: str, flag: str) -> None:
        skill_dir = tmp_path / name
        skill_dir.mkdir()
        manifest = skill_dir / "manifest.md"
        manifest.write_text(
            f"""---
name: {name}
description: Skill {name}
feature_flag: {flag}
executor_path: some.module.Executor
---

Prompt for {name}.
"""
        )

    def test_returns_empty_when_no_skills_enabled(self, tmp_path: Path) -> None:
        self._create_skill_dir(tmp_path, "skill_a", "SKILL_A_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKILL_A_FLAG", None)
            result = registry.load_enabled_skills()

        assert result == []

    def test_returns_enabled_skills(self, tmp_path: Path) -> None:
        self._create_skill_dir(tmp_path, "skill_a", "SKILL_A_FLAG")
        self._create_skill_dir(tmp_path, "skill_b", "SKILL_B_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"SKILL_A_FLAG": "true", "SKILL_B_FLAG": "false"}):
            result = registry.load_enabled_skills()

        assert len(result) == 1
        assert result[0].name == "skill_a"

    def test_returns_all_when_all_enabled(self, tmp_path: Path) -> None:
        self._create_skill_dir(tmp_path, "skill_a", "SKILL_A_FLAG")
        self._create_skill_dir(tmp_path, "skill_b", "SKILL_B_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"SKILL_A_FLAG": "true", "SKILL_B_FLAG": "true"}):
            result = registry.load_enabled_skills()

        assert len(result) == 2

    def test_returns_empty_for_nonexistent_dir(self) -> None:
        registry = SkillRegistry(skills_dir=Path("/nonexistent/path"))
        assert registry.load_enabled_skills() == []

    def test_skips_non_directory_entries(self, tmp_path: Path) -> None:
        (tmp_path / "not_a_dir.txt").write_text("just a file")
        self._create_skill_dir(tmp_path, "real_skill", "REAL_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"REAL_FLAG": "true"}):
            result = registry.load_enabled_skills()

        assert len(result) == 1
        assert result[0].name == "real_skill"

    def test_flag_value_false_string_disables_skill(self, tmp_path: Path) -> None:
        self._create_skill_dir(tmp_path, "skill_x", "SKILL_X_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"SKILL_X_FLAG": "false"}):
            result = registry.load_enabled_skills()

        assert result == []

    def test_flag_case_insensitive_true(self, tmp_path: Path) -> None:
        # The implementation lowercases the flag value before comparison
        self._create_skill_dir(tmp_path, "skill_y", "SKILL_Y_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"SKILL_Y_FLAG": "True"}):
            result = registry.load_enabled_skills()

        assert len(result) == 1
        assert result[0].name == "skill_y"

    def test_skips_directory_without_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "no_manifest").mkdir()
        self._create_skill_dir(tmp_path, "has_manifest", "HAS_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"HAS_FLAG": "true"}):
            result = registry.load_enabled_skills()

        assert len(result) == 1
        assert result[0].name == "has_manifest"

    def test_results_sorted_alphabetically(self, tmp_path: Path) -> None:
        self._create_skill_dir(tmp_path, "zebra_skill", "ZEBRA_FLAG")
        self._create_skill_dir(tmp_path, "alpha_skill", "ALPHA_FLAG")
        registry = SkillRegistry(skills_dir=tmp_path)

        with patch.dict(os.environ, {"ZEBRA_FLAG": "true", "ALPHA_FLAG": "true"}):
            result = registry.load_enabled_skills()

        assert result[0].name == "alpha_skill"
        assert result[1].name == "zebra_skill"
