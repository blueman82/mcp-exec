#!/usr/bin/env python3
"""
Quality Validation Framework - Import Order Validator.

This module provides comprehensive import order validation following Python
standards: stdlib → third-party → local. Includes automated sorting capabilities.

Author: GUARDIAN-003
Created: 2025-09-22
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .code_quality_validator import CodeQualityViolation


class ImportOrderValidator:
    """Validates and automatically sorts import statements according to PEP8."""

    def __init__(self):
        """Initialize the import order validator."""
        self.stdlib_modules = self._get_stdlib_modules()
        self.violations: List[CodeQualityViolation] = []

    def _get_stdlib_modules(self) -> Set[str]:
        """Get standard library module names."""
        # Common standard library modules
        return {
            'abc', 'argparse', 'ast', 'asyncio', 'base64', 'calendar',
            'collections', 'contextlib', 'copy', 'datetime', 'decimal',
            'enum', 'functools', 'hashlib', 'http', 'io', 'itertools',
            'json', 'logging', 'math', 'os', 'pathlib', 'queue', 're',
            'socket', 'subprocess', 'sys', 'tempfile', 'threading',
            'time', 'typing', 'urllib', 'uuid', 'warnings'
        }

    def _categorize_import(self, import_name: str) -> str:
        """Categorize import as stdlib, third-party, or local."""
        # Remove any submodule parts for categorization
        base_module = import_name.split('.')[0]

        if base_module in self.stdlib_modules:
            return 'stdlib'
        elif import_name.startswith('.') or import_name.startswith('packages.'):
            return 'local'
        else:
            return 'third_party'

    def _extract_imports(self, file_path: str) -> List[Tuple[int, str, str, str]]:
        """Extract import statements with line numbers and categories."""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        category = self._categorize_import(alias.name)
                        import_text = f"import {alias.name}"
                        if alias.asname:
                            import_text += f" as {alias.asname}"
                        imports.append((node.lineno, import_text, category, alias.name))

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    level = "." * node.level
                    full_module = level + module
                    category = self._categorize_import(full_module)

                    names = []
                    for alias in node.names:
                        if alias.asname:
                            names.append(f"{alias.name} as {alias.asname}")
                        else:
                            names.append(alias.name)

                    import_text = f"from {full_module} import {', '.join(names)}"
                    imports.append((node.lineno, import_text, category, full_module))

        except Exception:
            # Log error but continue
            pass

        return imports

    def _check_import_order(self, imports: List[Tuple[int, str, str, str]],
                           file_path: str) -> List[CodeQualityViolation]:
        """Check if imports are in correct order."""
        violations = []

        if not imports:
            return violations

        expected_order = ['stdlib', 'third_party', 'local']
        current_section = 0

        for line_no, import_text, category, module_name in imports:
            expected_section = expected_order.index(category)

            if expected_section < current_section:
                violations.append(CodeQualityViolation(
                    violation_type="import_order",
                    file_path=file_path,
                    line_number=line_no,
                    message=f"Import '{module_name}' ({category}) should come before "
                           f"current section ({expected_order[current_section]})",
                    severity="warning"
                ))

            current_section = max(current_section, expected_section)

        return violations

    def _generate_sorted_imports(self, imports: List[Tuple[int, str, str, str]]) -> str:
        """Generate correctly sorted import block."""
        if not imports:
            return ""

        # Group imports by category
        stdlib_imports = []
        third_party_imports = []
        local_imports = []

        for _, import_text, category, _ in imports:
            if category == 'stdlib':
                stdlib_imports.append(import_text)
            elif category == 'third_party':
                third_party_imports.append(import_text)
            elif category == 'local':
                local_imports.append(import_text)

        # Sort each group
        stdlib_imports.sort()
        third_party_imports.sort()
        local_imports.sort()

        # Combine with proper spacing
        sorted_imports = []

        if stdlib_imports:
            sorted_imports.extend(stdlib_imports)

        if third_party_imports:
            if sorted_imports:
                sorted_imports.append("")  # Blank line separator
            sorted_imports.extend(third_party_imports)

        if local_imports:
            if sorted_imports:
                sorted_imports.append("")  # Blank line separator
            sorted_imports.extend(local_imports)

        return "\n".join(sorted_imports)

    def validate_import_order(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate import order in a file."""
        imports = self._extract_imports(file_path)
        return self._check_import_order(imports, file_path)

    def auto_sort_imports(self, file_path: str) -> Optional[str]:
        """Generate auto-sorted import section for a file."""
        imports = self._extract_imports(file_path)
        if imports:
            return self._generate_sorted_imports(imports)
        return None

    def scan_directory_for_import_violations(self, directory_path: str,
                                           file_patterns: List[str] = None) -> Dict[str, List[CodeQualityViolation]]:
        """Scan directory for import order violations."""
        if file_patterns is None:
            file_patterns = ['*.py']

        results = {}
        directory = Path(directory_path)

        for pattern in file_patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file():
                    violations = self.validate_import_order(str(file_path))
                    if violations:
                        results[str(file_path)] = violations

        return results

    def generate_import_order_report(self, violations: Dict[str, List[CodeQualityViolation]]) -> str:
        """Generate comprehensive import order violation report."""
        if not violations:
            return "✅ All files pass import order validation (stdlib → third-party → local)\n"

        report = ["📦 IMPORT ORDER VALIDATION REPORT"]
        report.append("=" * 45)

        total_violations = sum(len(v) for v in violations.values())
        report.append(f"Total violations: {total_violations}")
        report.append(f"Files affected: {len(violations)}")
        report.append("")
        report.append("Expected order: stdlib → third-party → local")
        report.append("")

        for file_path, file_violations in violations.items():
            relative_path = file_path.replace(
                '/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/', ''
            )
            report.append(f"🔍 {relative_path}")

            for violation in file_violations:
                severity_icon = "🚨" if violation.severity == "error" else "⚠️"
                report.append(f"  {severity_icon} Line {violation.line_number}: {violation.message}")
            report.append("")

        return "\n".join(report)