#!/usr/bin/env python3
"""
Quality Validation Framework - Rollback Safety Validator.

This module provides comprehensive rollback safety validation for TypedDI
service registrations, ensuring safe rollback procedures and state recovery.

Author: GUARDIAN-004
Created: 2025-09-22
"""

import os
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from .code_quality_validator import CodeQualityViolation


class RollbackSafetyValidator:
    """Validates rollback safety for service deployments."""

    def __init__(self):
        """Initialize the rollback safety validator."""
        self.git_backup_branch_prefix = "backup/guardian-"
        self.critical_files = [
            "packages/core/typed_di/service_registrations.py",
            "packages/core/di_container.py",
            "infrastructure/docker-compose.yml",
        ]
        self.database_backup_required = ["ketchup_channel_information"]
        self.violations: List[CodeQualityViolation] = []

    def _check_git_repository(self) -> Optional[CodeQualityViolation]:
        """Check if we're in a valid git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )
            if result.returncode != 0:
                return CodeQualityViolation(
                    violation_type="git_backup",
                    file_path="git",
                    line_number=0,
                    message="Not in a git repository - cannot create backup",
                )
        except Exception as e:
            return CodeQualityViolation(
                violation_type="git_backup",
                file_path="git",
                line_number=0,
                message=f"Git repository check failed: {str(e)}",
            )
        return None

    def _check_uncommitted_changes(self) -> Optional[CodeQualityViolation]:
        """Check for uncommitted changes in the repository."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )
            if result.stdout.strip():
                return CodeQualityViolation(
                    violation_type="git_backup",
                    file_path="git",
                    line_number=0,
                    message="Uncommitted changes detected - backup may be incomplete",
                    severity="warning",
                )
        except Exception as e:
            return CodeQualityViolation(
                violation_type="git_backup",
                file_path="git",
                line_number=0,
                message=f"Uncommitted changes check failed: {str(e)}",
            )
        return None

    def _test_backup_branch_creation(self) -> Optional[CodeQualityViolation]:
        """Test backup branch creation and cleanup."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_branch = f"{self.git_backup_branch_prefix}{timestamp}"

            result = subprocess.run(
                ["git", "checkout", "-b", backup_branch],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )
            if result.returncode != 0:
                return CodeQualityViolation(
                    violation_type="git_backup",
                    file_path="git",
                    line_number=0,
                    message=f"Failed to create backup branch: {result.stderr}",
                )
            else:
                # Return to original branch
                subprocess.run(
                    ["git", "checkout", "-"],
                    capture_output=True,
                    text=True,
                    cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
                )
        except Exception as e:
            return CodeQualityViolation(
                violation_type="git_backup",
                file_path="git",
                line_number=0,
                message=f"Backup branch test failed: {str(e)}",
            )
        return None

    def validate_git_backup_branch(self) -> List[CodeQualityViolation]:
        """Validate git backup branch creation and safety."""
        violations = []

        # Check git repository
        git_violation = self._check_git_repository()
        if git_violation:
            violations.append(git_violation)
            return violations

        # Check uncommitted changes
        changes_violation = self._check_uncommitted_changes()
        if changes_violation:
            violations.append(changes_violation)

        # Test backup branch creation
        branch_violation = self._test_backup_branch_creation()
        if branch_violation:
            violations.append(branch_violation)

        return violations

    def validate_critical_file_preservation(self) -> List[CodeQualityViolation]:
        """Validate that critical files can be safely preserved and restored."""
        violations = []

        for file_path in self.critical_files:
            full_path = os.path.join(
                "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup", file_path
            )

            if not os.path.exists(full_path):
                violations.append(
                    CodeQualityViolation(
                        violation_type="file_preservation",
                        file_path=file_path,
                        line_number=0,
                        message="Critical file does not exist",
                    )
                )
                continue

            try:
                # Check if file is readable
                with open(full_path, "r") as f:
                    content = f.read()

                # Check file size (large files may indicate issues)
                file_size = os.path.getsize(full_path)
                if file_size > 10 * 1024 * 1024:  # 10MB
                    violations.append(
                        CodeQualityViolation(
                            violation_type="file_preservation",
                            file_path=file_path,
                            line_number=0,
                            message=f"Large file ({file_size} bytes) may cause rollback delays",
                            severity="warning",
                        )
                    )

                # Check for sensitive content that shouldn't be in backups
                sensitive_patterns = ["password", "secret", "key", "token"]
                for pattern in sensitive_patterns:
                    if pattern.lower() in content.lower():
                        violations.append(
                            CodeQualityViolation(
                                violation_type="file_preservation",
                                file_path=file_path,
                                line_number=0,
                                message=f"File contains potential sensitive data: {pattern}",
                                severity="warning",
                            )
                        )

            except Exception as e:
                violations.append(
                    CodeQualityViolation(
                        violation_type="file_preservation",
                        file_path=file_path,
                        line_number=0,
                        message=f"Failed to validate file preservation: {str(e)}",
                    )
                )

        return violations

    def validate_rollback_impact_assessment(self) -> List[CodeQualityViolation]:
        """Assess the impact of potential rollbacks on system state."""
        violations = []

        # Check for database migration files
        migration_paths = ["migrations/", "db/migrations/", "packages/db/migrations/"]

        migration_files_found = []
        for migration_path in migration_paths:
            full_path = os.path.join(
                "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup", migration_path
            )
            if os.path.exists(full_path):
                for root, dirs, files in os.walk(full_path):
                    migration_files_found.extend([f for f in files if f.endswith((".sql", ".py"))])

        if migration_files_found:
            violations.append(
                CodeQualityViolation(
                    violation_type="rollback_impact",
                    file_path="migrations",
                    line_number=0,
                    message=f"Found {len(migration_files_found)} migration files - rollback may require database rollback",
                    severity="warning",
                )
            )

        # Check for configuration changes
        config_files = ["infrastructure/docker-compose.yml", ".env", "packages/core/config/"]

        for config_file in config_files:
            full_path = os.path.join(
                "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup", config_file
            )
            if os.path.exists(full_path):
                try:
                    # Check git diff for this file
                    result = subprocess.run(
                        ["git", "diff", "HEAD~1", config_file],
                        capture_output=True,
                        text=True,
                        cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
                    )
                    if result.stdout.strip():
                        violations.append(
                            CodeQualityViolation(
                                violation_type="rollback_impact",
                                file_path=config_file,
                                line_number=0,
                                message="Configuration changes detected - rollback may require manual config restoration",
                                severity="warning",
                            )
                        )
                except Exception:
                    pass  # Git diff may fail for various reasons

        return violations

    def simulate_rollback_procedure(self) -> List[CodeQualityViolation]:
        """Simulate rollback procedure to validate safety."""
        violations = []

        try:
            # Create a temporary test branch for simulation
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            test_branch = f"rollback-test-{timestamp}"

            result = subprocess.run(
                ["git", "checkout", "-b", test_branch],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )

            if result.returncode != 0:
                violations.append(
                    CodeQualityViolation(
                        violation_type="rollback_simulation",
                        file_path="git",
                        line_number=0,
                        message=f"Failed to create rollback test branch: {result.stderr}",
                    )
                )
                return violations

            # Test rollback to previous commit
            result = subprocess.run(
                ["git", "reset", "--hard", "HEAD~1"],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )

            if result.returncode != 0:
                violations.append(
                    CodeQualityViolation(
                        violation_type="rollback_simulation",
                        file_path="git",
                        line_number=0,
                        message=f"Rollback simulation failed: {result.stderr}",
                    )
                )

            # Test file integrity after rollback
            for file_path in self.critical_files:
                full_path = os.path.join(
                    "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup", file_path
                )
                if not os.path.exists(full_path):
                    violations.append(
                        CodeQualityViolation(
                            violation_type="rollback_simulation",
                            file_path=file_path,
                            line_number=0,
                            message="Critical file missing after rollback simulation",
                        )
                    )

            # Clean up test branch
            subprocess.run(
                ["git", "checkout", "-"],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )
            subprocess.run(
                ["git", "branch", "-D", test_branch],
                capture_output=True,
                text=True,
                cwd="/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup",
            )

        except Exception as e:
            violations.append(
                CodeQualityViolation(
                    violation_type="rollback_simulation",
                    file_path="simulation",
                    line_number=0,
                    message=f"Rollback simulation error: {str(e)}",
                )
            )

        return violations

    def validate_rollback_safety(self) -> Dict[str, List[CodeQualityViolation]]:
        """Run comprehensive rollback safety validation."""
        all_violations = {}

        # Validate git backup capability
        git_violations = self.validate_git_backup_branch()
        if git_violations:
            all_violations["git_backup"] = git_violations

        # Validate critical file preservation
        file_violations = self.validate_critical_file_preservation()
        if file_violations:
            all_violations["file_preservation"] = file_violations

        # Assess rollback impact
        impact_violations = self.validate_rollback_impact_assessment()
        if impact_violations:
            all_violations["rollback_impact"] = impact_violations

        # Simulate rollback procedure
        simulation_violations = self.simulate_rollback_procedure()
        if simulation_violations:
            all_violations["rollback_simulation"] = simulation_violations

        return all_violations

    def generate_rollback_safety_report(
        self, violations: Dict[str, List[CodeQualityViolation]]
    ) -> str:
        """Generate comprehensive rollback safety report."""
        if not violations:
            return (
                "✅ ALL ROLLBACK SAFETY CHECKS PASSED\n🔄 Rollback procedures are safe to execute!"
            )

        report = ["🔄 ROLLBACK SAFETY VALIDATION REPORT"]
        report.append("=" * 45)

        total_violations = sum(len(v) for v in violations.values())
        error_count = sum(
            1 for v_list in violations.values() for v in v_list if v.severity == "error"
        )
        warning_count = total_violations - error_count

        report.append(f"🚨 Total Issues: {total_violations}")
        report.append(f"❌ Errors: {error_count}")
        report.append(f"⚠️  Warnings: {warning_count}")
        report.append("")

        if error_count > 0:
            report.append("🛑 ROLLBACK UNSAFE - Critical errors found")
        else:
            report.append("⚠️  ROLLBACK CAUTION - Warnings found")

        report.append("")

        for category, violation_list in violations.items():
            report.append(f"🔍 {category.upper().replace('_', ' ')}")
            report.append("-" * 30)

            for violation in violation_list:
                severity_icon = "🚨" if violation.severity == "error" else "⚠️"
                report.append(f"  {severity_icon} {violation.message}")
            report.append("")

        # Add recommendations
        report.append("💡 ROLLBACK SAFETY RECOMMENDATIONS:")
        if error_count > 0:
            report.append("1. Fix critical errors before attempting rollback")
            report.append("2. Create comprehensive backup before deployment")
            report.append("3. Test rollback procedure in staging environment")
        else:
            report.append("1. Address warnings for optimal rollback safety")
            report.append("2. Monitor system state during rollback")
            report.append("3. Have manual recovery procedures ready")

        return "\n".join(report)
