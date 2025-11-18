#!/usr/bin/env python3
"""
Automated Test Generation Framework for TypedDI Service Registrations

Provides templating and generation tools for creating comprehensive test suites
for TypedDI service registration validation and smoke checking.

Key Features:
- Template-based test generation for new service registrations
- Parameterized test generators for service resolution validation
- Automated smoke check generation with service list input
- Performance regression test framework generation
- Test discovery for services added to mapping files
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from tests.setup.test_templates import (
    SERVICE_RESOLUTION_TEMPLATE,
    SMOKE_CHECK_TEMPLATE,
    PARAMETERIZED_TEST_TEMPLATE,
    DYNAMIC_SMOKE_CHECK_TEMPLATE
)


class TestTemplateGenerator:
    """Generates test templates for TypedDI service registrations."""

    def __init__(self, project_root: str):
        """Initialize generator with project root path."""
        self.project_root = Path(project_root)
        self.templates_dir = self.project_root / "tests" / "setup" / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def generate_service_resolution_test(
        self, service_name: str, service_type: str, dependencies: List[str]
    ) -> str:
        """Generate test template for service resolution validation."""
        return SERVICE_RESOLUTION_TEMPLATE.format(
            service_name=service_name,
            service_type=service_type,
            dependencies=dependencies
        )

    def generate_smoke_check_template(
        self, service_list: List[Dict[str, str]]
    ) -> str:
        """Generate smoke check template for service list."""
        service_names = [svc["name"] for svc in service_list]
        return SMOKE_CHECK_TEMPLATE.format(
            service_list=service_list,
            service_names=service_names,
            service_count=len(service_list)
        )

    def create_test_file(self, filename: str, content: str) -> Path:
        """Create test file with generated content."""
        test_file = self.templates_dir / filename
        with open(test_file, 'w') as f:
            f.write(content)
        return test_file


class ParameterizedTestGenerator:
    """Generates parameterized tests for service resolution validation."""

    def __init__(self, project_root: str):
        """Initialize with project root."""
        self.project_root = Path(project_root)

    def generate_parameterized_resolution_tests(
        self, services: List[Dict[str, str]]
    ) -> str:
        """Generate parameterized tests for multiple services."""
        service_params = []
        for svc in services:
            service_params.append(
                f'("{svc["name"]}", {svc["type"]}, {svc.get("dependencies", [])})'
            )

        param_string = ",\n        ".join(service_params)
        return PARAMETERIZED_TEST_TEMPLATE.format(
            param_string=param_string,
            service_count=len(services)
        )


class AutomatedSmokeCheckGenerator:
    """Generates automated smoke checks from service lists."""

    def __init__(self, project_root: str):
        """Initialize with project root."""
        self.project_root = Path(project_root)

    def generate_from_service_list(
        self, service_list_file: str
    ) -> Tuple[str, List[Dict]]:
        """Generate smoke check from service list file."""
        service_list_path = self.project_root / service_list_file

        if not service_list_path.exists():
            raise FileNotFoundError(f"Service list file not found: {service_list_file}")

        with open(service_list_path, 'r') as f:
            services = json.load(f)

        if isinstance(services, dict) and "services" in services:
            services = services["services"]

        template = self._create_dynamic_smoke_check(services)
        return template, services

    def _create_dynamic_smoke_check(self, services: List[Dict]) -> str:
        """Create dynamic smoke check for service list."""
        service_count = len(services)
        service_names = [svc.get("name", "Unknown") for svc in services]

        return DYNAMIC_SMOKE_CHECK_TEMPLATE.format(
            service_count=service_count,
            services=services,
            service_names=service_names
        )


class TestDiscoveryEngine:
    """Discovers and generates tests for services in mapping files."""

    def __init__(self, project_root: str):
        """Initialize discovery engine."""
        self.project_root = Path(project_root)
        self.mapping_file = self.project_root / "analysis" / "client_map_to_protocol_mapping.json"

    def discover_unmapped_services(self) -> List[str]:
        """Discover services that need test generation."""
        if not self.mapping_file.exists():
            return []

        with open(self.mapping_file, 'r') as f:
            mapping = json.load(f)

        unmapped = []
        for client_key, protocol_info in mapping.items():
            if isinstance(protocol_info, dict):
                test_file = f"test_{client_key.lower()}_resolution.py"
                test_path = self.project_root / "tests" / "unit" / "typed_di" / test_file
                if not test_path.exists():
                    unmapped.append(client_key)

        return unmapped

    def generate_missing_tests(self) -> List[str]:
        """Generate tests for unmapped services."""
        unmapped = self.discover_unmapped_services()
        template_gen = TestTemplateGenerator(str(self.project_root))
        generated_files = []

        for service_key in unmapped:
            test_content = template_gen.generate_service_resolution_test(
                service_name=service_key,
                service_type=f"{service_key}Protocol",
                dependencies=[]
            )

            test_file = f"test_{service_key.lower()}_resolution.py"
            output_path = template_gen.create_test_file(test_file, test_content)
            generated_files.append(str(output_path))

        return generated_files


class TestCoverageValidator:
    """Validates test coverage for registered services."""

    def __init__(self, project_root: str):
        """Initialize coverage validator."""
        self.project_root = Path(project_root)

    def validate_service_coverage(self) -> Dict[str, bool]:
        """Validate test coverage for all registered services."""
        try:
            from packages.core.typed_di.service_registrations import get_all_registrations
            registrations = get_all_registrations()
        except ImportError:
            return {}

        coverage_report = {}
        test_dir = self.project_root / "tests" / "unit" / "typed_di"

        for reg in registrations:
            service_type = reg.get("service_type")
            if service_type:
                service_name = getattr(service_type, '__name__', str(service_type))
                test_file = f"test_{service_name.lower()}_resolution.py"
                test_path = test_dir / test_file
                coverage_report[service_name] = test_path.exists()

        return coverage_report

    def get_coverage_percentage(self) -> float:
        """Get overall test coverage percentage."""
        coverage = self.validate_service_coverage()
        if not coverage:
            return 0.0

        covered = sum(1 for is_covered in coverage.values() if is_covered)
        total = len(coverage)
        return (covered / total) * 100.0


def main():
    """Example usage of automated test generation."""
    project_root = "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup"

    # Initialize generators
    TestTemplateGenerator(project_root)
    discovery = TestDiscoveryEngine(project_root)
    coverage = TestCoverageValidator(project_root)

    # Example: Generate missing tests
    missing_tests = discovery.generate_missing_tests()
    print(f"Generated {len(missing_tests)} missing test files")

    # Example: Check coverage
    coverage_pct = coverage.get_coverage_percentage()
    print(f"Current test coverage: {coverage_pct:.1f}%")


if __name__ == "__main__":
    main()