#!/usr/bin/env python3
"""
Quality Validation Framework - Docstring Validator.

This module provides comprehensive Google-style docstring validation for TypedDI
service registrations during the 271-service completion initiative.

Author: GUARDIAN-003
Created: 2025-09-22
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional

from .code_quality_validator import CodeQualityViolation


class DocstringValidator:
    """Validates Google-style docstring compliance for all functions and classes."""

    def __init__(self):
        """Initialize the docstring validator."""
        self.google_sections = {
            'Args:', 'Arguments:', 'Parameters:', 'Param:', 'Params:',
            'Returns:', 'Return:', 'Yields:', 'Yield:',
            'Raises:', 'Raise:', 'Except:', 'Exceptions:',
            'Note:', 'Notes:', 'Example:', 'Examples:'
        }
        self.violations: List[CodeQualityViolation] = []

    def _check_missing_docstring(self, docstring: str, node_name: str,
                                file_path: str, line_number: int) -> Optional[CodeQualityViolation]:
        """Check if docstring is missing."""
        if not docstring:
            return CodeQualityViolation(
                violation_type="missing_docstring",
                file_path=file_path,
                line_number=line_number,
                message=f"Missing docstring for {node_name}",
                severity="error"
            )
        return None

    def _check_summary_line(self, lines: List[str], node_name: str,
                           file_path: str, line_number: int) -> List[CodeQualityViolation]:
        """Check summary line format."""
        violations = []

        if not lines[0].strip():
            violations.append(CodeQualityViolation(
                violation_type="docstring_format",
                file_path=file_path,
                line_number=line_number,
                message=f"Docstring for {node_name} must start with summary line",
                severity="error"
            ))

        if lines[0].strip() and not lines[0].strip().endswith('.'):
            violations.append(CodeQualityViolation(
                violation_type="docstring_format",
                file_path=file_path,
                line_number=line_number,
                message=f"Summary line for {node_name} must end with period",
                severity="warning"
            ))

        return violations

    def _check_section_formatting(self, lines: List[str], node_name: str,
                                 file_path: str, line_number: int) -> List[CodeQualityViolation]:
        """Check Google section formatting."""
        violations = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(stripped.startswith(section) for section in self.google_sections):
                if line != stripped:
                    violations.append(CodeQualityViolation(
                        violation_type="docstring_format",
                        file_path=file_path,
                        line_number=line_number + i,
                        message=f"Section headers in {node_name} must not be indented",
                        severity="warning"
                    ))

        return violations

    def _check_docstring_format(self, docstring: str, node_name: str,
                               file_path: str, line_number: int) -> List[CodeQualityViolation]:
        """Check if docstring follows Google format."""
        missing_check = self._check_missing_docstring(docstring, node_name, file_path, line_number)
        if missing_check:
            return [missing_check]

        lines = docstring.strip().split('\n')
        violations = []
        violations.extend(self._check_summary_line(lines, node_name, file_path, line_number))
        violations.extend(self._check_section_formatting(lines, node_name, file_path, line_number))

        return violations

    def validate_function_docstrings(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate function docstrings follow Google format."""
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    docstring = ast.get_docstring(node)
                    violations.extend(self._check_docstring_format(
                        docstring or "", f"function '{node.name}'",
                        file_path, node.lineno
                    ))

                    # Special check for functions with parameters
                    if node.args.args and not docstring:
                        violations.append(CodeQualityViolation(
                            violation_type="missing_param_docs",
                            file_path=file_path,
                            line_number=node.lineno,
                            message=f"Function '{node.name}' has parameters but no Args: section",
                            severity="error"
                        ))

        except Exception as e:
            violations.append(CodeQualityViolation(
                violation_type="parse_error",
                file_path=file_path,
                line_number=0,
                message=f"Failed to parse file for docstring validation: {str(e)}"
            ))

        return violations

    def validate_class_docstrings(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate class docstrings follow Google format."""
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node)
                    violations.extend(self._check_docstring_format(
                        docstring or "", f"class '{node.name}'",
                        file_path, node.lineno
                    ))

        except Exception as e:
            violations.append(CodeQualityViolation(
                violation_type="parse_error",
                file_path=file_path,
                line_number=0,
                message=f"Failed to parse file for class docstring validation: {str(e)}"
            ))

        return violations

    def validate_module_docstring(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate module-level docstring exists and follows format."""
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                tree = ast.parse(content)

            module_docstring = ast.get_docstring(tree)
            if not module_docstring:
                violations.append(CodeQualityViolation(
                    violation_type="missing_module_docstring",
                    file_path=file_path,
                    line_number=1,
                    message="Missing module-level docstring",
                    severity="error"
                ))
            else:
                violations.extend(self._check_docstring_format(
                    module_docstring, "module", file_path, 1
                ))

        except Exception as e:
            violations.append(CodeQualityViolation(
                violation_type="parse_error",
                file_path=file_path,
                line_number=0,
                message=f"Failed to parse module for docstring validation: {str(e)}"
            ))

        return violations

    def scan_directory_for_docstring_violations(self, directory_path: str,
                                              file_patterns: List[str] = None) -> Dict[str, List[CodeQualityViolation]]:
        """Scan directory for docstring violations."""
        if file_patterns is None:
            file_patterns = ['*.py']

        results = {}
        directory = Path(directory_path)

        for pattern in file_patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file():
                    file_violations = []
                    file_violations.extend(self.validate_module_docstring(str(file_path)))
                    file_violations.extend(self.validate_class_docstrings(str(file_path)))
                    file_violations.extend(self.validate_function_docstrings(str(file_path)))

                    if file_violations:
                        results[str(file_path)] = file_violations

        return results

    def generate_docstring_report(self, violations: Dict[str, List[CodeQualityViolation]]) -> str:
        """Generate comprehensive docstring violation report."""
        if not violations:
            return "✅ All files pass Google-style docstring validation\n"

        report = ["📖 GOOGLE-STYLE DOCSTRING VALIDATION REPORT"]
        report.append("=" * 50)

        total_violations = sum(len(v) for v in violations.values())
        error_count = sum(1 for v_list in violations.values()
                         for v in v_list if v.severity == "error")
        warning_count = total_violations - error_count

        report.append(f"Total violations: {total_violations}")
        report.append(f"  🚨 Errors: {error_count}")
        report.append(f"  ⚠️  Warnings: {warning_count}")
        report.append(f"Files affected: {len(violations)}")
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