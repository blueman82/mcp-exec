"""Test suite for campaign_prod schema validation.

This module validates that the campaign_prod_schema.json file follows the expected
structure for the Adobe Campaign index documentation. Tests ensure all required
keys exist and field definitions are properly formatted.
"""

import json
from pathlib import Path

import pytest


class TestCampaignProdSchema:
    """Test that campaign_prod schema JSON follows expected structure."""

    @pytest.fixture
    def schema_path(self):
        """Path to the schema JSON file.

        Returns:
            Path object pointing to campaign_prod_schema.json
        """
        # Use path relative to this test file to work from any directory
        test_dir = Path(__file__).parent
        project_root = test_dir.parent.parent
        return project_root / "docs" / "schema" / "campaign_prod_schema.json"

    @pytest.fixture
    def schema_data(self, schema_path):
        """Load and parse the schema JSON.

        Args:
            schema_path: Path fixture to schema file

        Returns:
            Parsed JSON dictionary

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema file has invalid JSON
        """
        with open(schema_path) as f:
            return json.load(f)

    def test_schema_has_required_top_level_keys(self, schema_data):
        """Schema must have index_name, display_name, field_categories, query_patterns.

        Verifies that all required top-level keys are present in the schema
        to ensure the RAG system can properly parse the documentation.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        required_keys = [
            "index_name",
            "display_name",
            "description",
            "sourcetypes",
            "field_categories",
            "query_patterns",
        ]
        for key in required_keys:
            assert key in schema_data, f"Missing required key: {key}"

    def test_field_categories_is_list(self, schema_data):
        """field_categories must be a list of category objects.

        Ensures field_categories is a non-empty list so the indexer
        can iterate over categories.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        assert isinstance(schema_data["field_categories"], list)
        assert len(schema_data["field_categories"]) > 0

    def test_field_has_required_attributes(self, schema_data):
        """Each field must have name, type, description, examples, common_in.

        Validates that every field definition contains all required attributes
        for embedding generation and semantic search.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        for category in schema_data["field_categories"]:
            for field in category.get("fields", []):
                assert "name" in field, "Field missing 'name' attribute"
                assert "type" in field, f"Field {field.get('name')} missing 'type'"
                assert "description" in field, f"Field {field.get('name')} missing 'description'"
                assert "examples" in field, f"Field {field.get('name')} missing 'examples'"
                assert isinstance(
                    field["examples"], list
                ), f"Field {field.get('name')} examples must be a list"
                assert "common_in" in field, f"Field {field.get('name')} missing 'common_in'"
                assert isinstance(
                    field["common_in"], list
                ), f"Field {field.get('name')} common_in must be a list"

    def test_query_patterns_structure(self, schema_data):
        """Query patterns must have required fields.

        Verifies that each query pattern contains pattern_name, use_case,
        and spl_template for agent reference.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        assert "query_patterns" in schema_data
        assert isinstance(schema_data["query_patterns"], list)

        for pattern in schema_data["query_patterns"]:
            assert "pattern_name" in pattern, "Query pattern missing 'pattern_name'"
            assert "use_case" in pattern, "Query pattern missing 'use_case'"
            assert "spl_template" in pattern, "Query pattern missing 'spl_template'"

    def test_use_cases_structure(self, schema_data):
        """Common use cases must reference fields and patterns if present.

        Ensures use cases link questions to relevant fields and query patterns
        for RAG retrieval. This section is optional in the schema.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        # common_use_cases is optional - pass if not present
        if "common_use_cases" not in schema_data:
            return  # Optional section, test passes

        assert isinstance(schema_data["common_use_cases"], list)

        for use_case in schema_data["common_use_cases"]:
            assert "question" in use_case, "Use case missing 'question'"
            assert "fields_involved" in use_case, "Use case missing 'fields_involved'"
            assert isinstance(use_case["fields_involved"], list), "fields_involved must be a list"

    def test_sourcetypes_structure(self, schema_data):
        """Sourcetypes must have name and description.

        Validates that each sourcetype is properly documented for the agent
        to understand log types.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        assert "sourcetypes" in schema_data
        assert isinstance(schema_data["sourcetypes"], list)
        assert len(schema_data["sourcetypes"]) > 0

        for sourcetype in schema_data["sourcetypes"]:
            assert "name" in sourcetype, "Sourcetype missing 'name'"
            assert "description" in sourcetype, "Sourcetype missing 'description'"

    def test_field_common_in_references_valid_sourcetypes(self, schema_data):
        """Fields' common_in must reference valid sourcetypes.

        Ensures that every sourcetype referenced in field common_in
        exists in the sourcetypes list. The special value "all" is allowed.

        Args:
            schema_data: Parsed schema JSON dictionary
        """
        valid_sourcetypes = {st["name"] for st in schema_data["sourcetypes"]}
        # Add "all" as a special valid value indicating the field appears in all sourcetypes
        valid_sourcetypes.add("all")

        for category in schema_data["field_categories"]:
            for field in category.get("fields", []):
                common_in = field.get("common_in", [])
                for sourcetype in common_in:
                    assert (
                        sourcetype in valid_sourcetypes
                    ), f"Field {field['name']} references invalid sourcetype: {sourcetype}"
