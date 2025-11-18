#!/usr/bin/env python3
"""
Quality Validation Framework - Code Quality Validator.

This module provides comprehensive code quality validation for TypedDI service
registrations during the 271-service completion initiative.

Author: GUARDIAN-001
Created: 2025-09-22
"""

import ast
from pathlib import Path
from typing import Dict, List


class CodeQualityViolation:
    """Represents a code quality violation."""

    def __init__(self, violation_type: str, file_path: str, line_number: int,
                 message: str, severity: str = "error"):
        """Initialize a code quality violation."""
        self.violation_type = violation_type
        self.file_path = file_path
        self.line_number = line_number
        self.message = message
        self.severity = severity


class CodeQualityValidator:
    """Validates code quality for new service registrations."""

    def __init__(self):
        """Initialize the code quality validator."""
        self.max_function_lines = 50
        self.max_module_lines = 400
        self.violations: List[CodeQualityViolation] = []

    def validate_function_size(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate function sizes are ≤50 lines."""
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_lines = node.end_lineno - node.lineno + 1
                    if func_lines > self.max_function_lines:
                        violation = CodeQualityViolation(
                            violation_type="function_size",
                            file_path=file_path,
                            line_number=node.lineno,
                            message=f"Function '{node.name}' has {func_lines} lines (max: {self.max_function_lines})"
                        )
                        violations.append(violation)
        except Exception as e:
            violation = CodeQualityViolation(
                violation_type="parse_error",
                file_path=file_path,
                line_number=0,
                message=f"Failed to parse file: {str(e)}"
            )
            violations.append(violation)

        return violations

    def validate_module_size(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate module size is ≤400 lines."""
        violations = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                total_lines = len(lines)

            if total_lines > self.max_module_lines:
                violation = CodeQualityViolation(
                    violation_type="module_size",
                    file_path=file_path,
                    line_number=total_lines,
                    message=f"Module has {total_lines} lines (max: {self.max_module_lines})"
                )
                violations.append(violation)
        except Exception as e:
            violation = CodeQualityViolation(
                violation_type="file_error",
                file_path=file_path,
                line_number=0,
                message=f"Failed to read file: {str(e)}"
            )
            violations.append(violation)

        return violations

    def scan_directory_for_violations(self, directory_path: str,
                                    file_patterns: List[str] = None) -> Dict[str, List[CodeQualityViolation]]:
        """Scan directory for file size violations with comprehensive reporting."""
        if file_patterns is None:
            file_patterns = ['*.py']

        results = {}
        directory = Path(directory_path)

        for pattern in file_patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file():
                    file_violations = []
                    file_violations.extend(self.validate_module_size(str(file_path)))
                    file_violations.extend(self.validate_function_size(str(file_path)))

                    if file_violations:
                        results[str(file_path)] = file_violations

        return results

    def generate_violation_report(self, violations: Dict[str, List[CodeQualityViolation]]) -> str:
        """Generate comprehensive violation report."""
        if not violations:
            return "✅ All files pass size validation requirements\n"

        report = ["📊 FILE SIZE VALIDATION REPORT"]
        report.append("=" * 40)

        total_violations = sum(len(v) for v in violations.values())
        report.append(f"Total violations: {total_violations}")
        report.append(f"Files affected: {len(violations)}")
        report.append("")

        for file_path, file_violations in violations.items():
            relative_path = file_path.replace('/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/', '')
            report.append(f"🔍 {relative_path}")

            for violation in file_violations:
                severity_icon = "🚨" if violation.severity == "error" else "⚠️"
                report.append(f"  {severity_icon} Line {violation.line_number}: {violation.message}")
            report.append("")

        return "\n".join(report)