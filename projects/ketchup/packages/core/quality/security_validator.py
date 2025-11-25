#!/usr/bin/env python3
"""
Quality Validation Framework - Security Validator.

This module provides comprehensive security validation for TypedDI service
registrations, focusing on injection prevention and secure coding patterns.

Author: GUARDIAN-003
Created: 2025-09-22
"""

import re
from pathlib import Path
from typing import Dict, List

from .code_quality_validator import CodeQualityViolation


class SecurityValidator:
    """Validates security patterns and prevents injection vulnerabilities."""

    def __init__(self):
        """Initialize the security validator."""
        self.dangerous_patterns = {
            'eval': r'\beval\s*\(',
            'exec': r'\bexec\s*\(',
            'subprocess_shell': r'subprocess\.[^(]*\([^)]*shell\s*=\s*True',
            'os_system': r'\bos\.system\s*\(',
            'pickle_load': r'\bpickle\.loads?\s*\(',
            'yaml_unsafe_load': r'\byaml\.load\s*\(',
            'sql_string_format': r'\.format\s*\([^)]*\)\s*(?=.*(?:SELECT|INSERT|UPDATE|DELETE))',
            'hardcoded_secrets': r'(?i)(password|secret|key|token)\s*=\s*["\'][^"\']+["\']'
        }
        self.injection_patterns = {
            'sql_injection': r'["\'][^"\']*\+[^"\']*["\'].*(?:SELECT|INSERT|UPDATE|DELETE)',
            'command_injection': r'["\'][^"\']*\+[^"\']*["\'].*(?:system|subprocess)',
            'ldap_injection': r'["\'][^"\']*\+[^"\']*["\'].*(?:ldap|LDAP)',
            'xpath_injection': r'["\'][^"\']*\+[^"\']*["\'].*(?:xpath|XPath)'
        }
        self.violations: List[CodeQualityViolation] = []

    def _check_dangerous_functions(self, content: str, file_path: str) -> List[CodeQualityViolation]:
        """Check for dangerous function usage."""
        violations = []
        lines = content.split('\n')

        for line_no, line in enumerate(lines, 1):
            for danger_type, pattern in self.dangerous_patterns.items():
                if re.search(pattern, line):
                    violations.append(CodeQualityViolation(
                        violation_type="security_risk",
                        file_path=file_path,
                        line_number=line_no,
                        message=f"Dangerous pattern detected: {danger_type} - {line.strip()}",
                        severity="error"
                    ))

        return violations

    def _check_injection_vulnerabilities(self, content: str, file_path: str) -> List[CodeQualityViolation]:
        """Check for potential injection vulnerabilities."""
        violations = []
        lines = content.split('\n')

        for line_no, line in enumerate(lines, 1):
            for injection_type, pattern in self.injection_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(CodeQualityViolation(
                        violation_type="injection_risk",
                        file_path=file_path,
                        line_number=line_no,
                        message=f"Potential {injection_type} vulnerability: {line.strip()}",
                        severity="error"
                    ))

        return violations

    def _check_service_registration_security(self, content: str, file_path: str) -> List[CodeQualityViolation]:
        """Check TypedDI service registration security patterns."""
        violations = []

        # Check for unsafe factory patterns
        unsafe_factory_patterns = [
            r'factory\s*=\s*lambda.*eval',
            r'factory\s*=\s*lambda.*exec',
            r'register_factory\([^)]*eval',
            r'register_factory\([^)]*exec'
        ]

        lines = content.split('\n')
        for line_no, line in enumerate(lines, 1):
            for pattern in unsafe_factory_patterns:
                if re.search(pattern, line):
                    violations.append(CodeQualityViolation(
                        violation_type="unsafe_factory",
                        file_path=file_path,
                        line_number=line_no,
                        message=f"Unsafe factory pattern in service registration: {line.strip()}",
                        severity="error"
                    ))

        # Check for dynamic imports in service definitions
        dynamic_import_pattern = r'__import__\s*\('
        for line_no, line in enumerate(lines, 1):
            if re.search(dynamic_import_pattern, line):
                violations.append(CodeQualityViolation(
                    violation_type="dynamic_import_risk",
                    file_path=file_path,
                    line_number=line_no,
                    message=f"Dynamic import detected - security risk: {line.strip()}",
                    severity="warning"
                ))

        return violations

    def _check_secret_exposure(self, content: str, file_path: str) -> List[CodeQualityViolation]:
        """Check for potential secret exposure."""
        violations = []
        lines = content.split('\n')

        # Patterns for potential secrets
        secret_patterns = [
            r'(?i)(password|secret|key|token|api_key)\s*=\s*["\'][^"\']{8,}["\']',
            r'(?i)(aws_access_key|aws_secret)\s*=\s*["\'][^"\']+["\']',
            r'(?i)(bearer\s+[a-zA-Z0-9_-]{20,})',
            r'(?i)(basic\s+[a-zA-Z0-9+/=]{20,})'
        ]

        for line_no, line in enumerate(lines, 1):
            # Skip comments and obvious examples
            if line.strip().startswith('#') or 'example' in line.lower() or 'dummy' in line.lower():
                continue

            for pattern in secret_patterns:
                if re.search(pattern, line):
                    violations.append(CodeQualityViolation(
                        violation_type="secret_exposure",
                        file_path=file_path,
                        line_number=line_no,
                        message=f"Potential secret exposure detected: {line.strip()[:50]}...",
                        severity="error"
                    ))

        return violations

    def _check_unsafe_deserialization(self, content: str, file_path: str) -> List[CodeQualityViolation]:
        """Check for unsafe deserialization patterns."""
        violations = []
        lines = content.split('\n')

        unsafe_patterns = [
            r'\bpickle\.loads?\s*\(',
            r'\bcPickle\.loads?\s*\(',
            r'\bdill\.loads?\s*\(',
            r'\byaml\.load\s*\(',
            r'\beval\s*\(',
            r'\bexec\s*\('
        ]

        for line_no, line in enumerate(lines, 1):
            for pattern in unsafe_patterns:
                if re.search(pattern, line):
                    violations.append(CodeQualityViolation(
                        violation_type="unsafe_deserialization",
                        file_path=file_path,
                        line_number=line_no,
                        message=f"Unsafe deserialization pattern: {line.strip()}",
                        severity="error"
                    ))

        return violations

    def validate_file_security(self, file_path: str) -> List[CodeQualityViolation]:
        """Validate security for a single file."""
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            violations.extend(self._check_dangerous_functions(content, file_path))
            violations.extend(self._check_injection_vulnerabilities(content, file_path))
            violations.extend(self._check_service_registration_security(content, file_path))
            violations.extend(self._check_secret_exposure(content, file_path))
            violations.extend(self._check_unsafe_deserialization(content, file_path))

        except Exception as e:
            violations.append(CodeQualityViolation(
                violation_type="security_scan_error",
                file_path=file_path,
                line_number=0,
                message=f"Failed to scan file for security issues: {str(e)}"
            ))

        return violations

    def scan_directory_for_security_violations(self, directory_path: str,
                                             file_patterns: List[str] = None) -> Dict[str, List[CodeQualityViolation]]:
        """Scan directory for security violations."""
        if file_patterns is None:
            file_patterns = ['*.py']

        results = {}
        directory = Path(directory_path)

        for pattern in file_patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file():
                    violations = self.validate_file_security(str(file_path))
                    if violations:
                        results[str(file_path)] = violations

        return results

    def generate_security_report(self, violations: Dict[str, List[CodeQualityViolation]]) -> str:
        """Generate comprehensive security violation report."""
        if not violations:
            return "✅ All files pass security validation - no vulnerabilities detected\n"

        report = ["🛡️ SECURITY VALIDATION REPORT"]
        report.append("=" * 40)

        total_violations = sum(len(v) for v in violations.values())
        error_count = sum(1 for v_list in violations.values()
                         for v in v_list if v.severity == "error")
        warning_count = total_violations - error_count

        report.append(f"Total security issues: {total_violations}")
        report.append(f"  🚨 Critical: {error_count}")
        report.append(f"  ⚠️  Warnings: {warning_count}")
        report.append(f"Files affected: {len(violations)}")
        report.append("")

        # Group by violation type
        violation_types = {}
        for file_violations in violations.values():
            for violation in file_violations:
                if violation.violation_type not in violation_types:
                    violation_types[violation.violation_type] = 0
                violation_types[violation.violation_type] += 1

        report.append("Security Issues by Type:")
        for vtype, count in sorted(violation_types.items()):
            report.append(f"  • {vtype}: {count}")
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