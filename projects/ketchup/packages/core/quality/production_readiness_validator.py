#!/usr/bin/env python3
"""
Quality Validation Framework - Production Readiness Validator.

This module provides comprehensive production readiness validation for TypedDI
service registrations, ensuring deployment safety and operational reliability.

Author: GUARDIAN-004
Created: 2025-09-22
"""

import json
import os
from typing import Dict, List

from .code_quality_validator import CodeQualityViolation


class ProductionReadinessValidator:
    """Validates production readiness for service deployments."""

    def __init__(self):
        """Initialize the production readiness validator."""
        self.aws_region = "eu-west-1"
        self.required_aws_resources = {
            "dynamodb": ["ketchup_channel_information"],
            "secrets": ["Ketchup_Token_Secrets"],
            "sqs": ["ketchup-events-queue"],
            "elb": ["ketchup-alb"],
            "ec2": ["ketchup-prod1", "ketchup-prod2"],
        }
        self.performance_thresholds = {
            "latency_ms": 50,
            "cpu_percent": 1,
            "memory_mb": 512,
            "disk_usage_percent": 80,
        }
        self.violations: List[CodeQualityViolation] = []

    def validate_aws_environment(self) -> List[CodeQualityViolation]:
        """Validate AWS environment configuration and resources."""
        violations = []

        # Check AWS profile configuration
        aws_profile = os.environ.get("AWS_PROFILE")
        if aws_profile != "campaign_prod_v7":
            violations.append(
                CodeQualityViolation(
                    violation_type="aws_config",
                    file_path="environment",
                    line_number=0,
                    message=f"AWS_PROFILE should be 'campaign_prod_v7', got '{aws_profile}'",
                )
            )

        # Check AWS region configuration
        aws_region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))
        if aws_region != self.aws_region:
            violations.append(
                CodeQualityViolation(
                    violation_type="aws_config",
                    file_path="environment",
                    line_number=0,
                    message=f"AWS_REGION should be '{self.aws_region}', got '{aws_region}'",
                )
            )

        return violations

    def validate_docker_configuration(self, compose_file_path: str) -> List[CodeQualityViolation]:
        """Validate Docker Compose configuration for production readiness."""
        violations = []

        if not os.path.exists(compose_file_path):
            violations.append(
                CodeQualityViolation(
                    violation_type="docker_config",
                    file_path=compose_file_path,
                    line_number=0,
                    message="Docker Compose file not found",
                )
            )
            return violations

        try:
            with open(compose_file_path, "r") as f:
                content = f.read()

            # Check for required environment variables
            required_env_vars = [
                "AWS_REGION",
                "DYNAMODB_TABLE_NAME",
                "AWS_SECRET_NAME",
                "LOG_LEVEL",
                "PYTHONPATH",
            ]

            for env_var in required_env_vars:
                if env_var not in content:
                    violations.append(
                        CodeQualityViolation(
                            violation_type="docker_config",
                            file_path=compose_file_path,
                            line_number=0,
                            message=f"Missing required environment variable: {env_var}",
                        )
                    )

            # Check for resource limits
            if "mem_limit" not in content:
                violations.append(
                    CodeQualityViolation(
                        violation_type="docker_config",
                        file_path=compose_file_path,
                        line_number=0,
                        message="Missing memory limits in Docker Compose",
                        severity="warning",
                    )
                )

        except Exception as e:
            violations.append(
                CodeQualityViolation(
                    violation_type="docker_config",
                    file_path=compose_file_path,
                    line_number=0,
                    message=f"Failed to parse Docker Compose file: {str(e)}",
                )
            )

        return violations

    def validate_service_dependencies(self, service_file_path: str) -> List[CodeQualityViolation]:
        """Validate service dependency configurations."""
        violations = []

        if not os.path.exists(service_file_path):
            violations.append(
                CodeQualityViolation(
                    violation_type="dependency_config",
                    file_path=service_file_path,
                    line_number=0,
                    message="Service configuration file not found",
                )
            )
            return violations

        try:
            with open(service_file_path, "r") as f:
                content = f.read()

            # Check for proper error handling in service initialization
            if "try:" not in content or "except" not in content:
                violations.append(
                    CodeQualityViolation(
                        violation_type="dependency_config",
                        file_path=service_file_path,
                        line_number=0,
                        message="Service lacks proper error handling for initialization",
                        severity="warning",
                    )
                )

            # Check for health check endpoints
            health_patterns = ["health", "ping", "status", "ready"]
            has_health_check = any(pattern in content.lower() for pattern in health_patterns)
            if not has_health_check:
                violations.append(
                    CodeQualityViolation(
                        violation_type="dependency_config",
                        file_path=service_file_path,
                        line_number=0,
                        message="Service lacks health check endpoint",
                        severity="warning",
                    )
                )

        except Exception as e:
            violations.append(
                CodeQualityViolation(
                    violation_type="dependency_config",
                    file_path=service_file_path,
                    line_number=0,
                    message=f"Failed to analyze service file: {str(e)}",
                )
            )

        return violations

    def validate_performance_requirements(
        self, test_results_path: str = None
    ) -> List[CodeQualityViolation]:
        """Validate performance requirements and benchmarks."""
        violations = []

        # If test results are provided, validate against thresholds
        if test_results_path and os.path.exists(test_results_path):
            try:
                with open(test_results_path, "r") as f:
                    results = json.load(f)

                # Check latency requirements
                if "latency_ms" in results:
                    latency = results["latency_ms"]
                    if latency > self.performance_thresholds["latency_ms"]:
                        violations.append(
                            CodeQualityViolation(
                                violation_type="performance",
                                file_path=test_results_path,
                                line_number=0,
                                message=f"Latency {latency}ms exceeds threshold {self.performance_thresholds['latency_ms']}ms",
                            )
                        )

                # Check CPU usage
                if "cpu_percent" in results:
                    cpu_usage = results["cpu_percent"]
                    if cpu_usage > self.performance_thresholds["cpu_percent"]:
                        violations.append(
                            CodeQualityViolation(
                                violation_type="performance",
                                file_path=test_results_path,
                                line_number=0,
                                message=f"CPU usage {cpu_usage}% exceeds threshold {self.performance_thresholds['cpu_percent']}%",
                            )
                        )

            except Exception as e:
                violations.append(
                    CodeQualityViolation(
                        violation_type="performance",
                        file_path=test_results_path,
                        line_number=0,
                        message=f"Failed to parse performance results: {str(e)}",
                    )
                )
        else:
            violations.append(
                CodeQualityViolation(
                    violation_type="performance",
                    file_path="performance_tests",
                    line_number=0,
                    message="No performance test results found",
                    severity="warning",
                )
            )

        return violations

    def validate_deployment_checklist(
        self, deployment_dir: str
    ) -> Dict[str, List[CodeQualityViolation]]:
        """Run comprehensive deployment checklist validation."""
        all_violations = {}

        # Validate AWS environment
        aws_violations = self.validate_aws_environment()
        if aws_violations:
            all_violations["aws_environment"] = aws_violations

        # Validate Docker configuration
        compose_path = os.path.join(deployment_dir, "docker-compose.yml")
        docker_violations = self.validate_docker_configuration(compose_path)
        if docker_violations:
            all_violations["docker_configuration"] = docker_violations

        # Validate service dependencies
        service_files = [
            "packages/core/typed_di/service_registrations.py",
            "packages/core/di_container.py",
        ]

        for service_file in service_files:
            full_path = os.path.join(
                "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup", service_file
            )
            violations = self.validate_service_dependencies(full_path)
            if violations:
                all_violations[f"service_dependencies_{service_file}"] = violations

        # Validate performance requirements
        perf_violations = self.validate_performance_requirements()
        if perf_violations:
            all_violations["performance_requirements"] = perf_violations

        return all_violations

    def generate_readiness_report(self, violations: Dict[str, List[CodeQualityViolation]]) -> str:
        """Generate comprehensive production readiness report."""
        if not violations:
            return "✅ ALL PRODUCTION READINESS CHECKS PASSED\n🚀 Ready for deployment!"

        report = ["🏭 PRODUCTION READINESS VALIDATION REPORT"]
        report.append("=" * 50)

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
            report.append("🛑 DEPLOYMENT BLOCKED - Critical errors found")
        else:
            report.append("⚠️  DEPLOYMENT CAUTION - Warnings found")

        report.append("")

        for category, violation_list in violations.items():
            report.append(f"📋 {category.upper().replace('_', ' ')}")
            report.append("-" * 30)

            for violation in violation_list:
                severity_icon = "🚨" if violation.severity == "error" else "⚠️"
                report.append(f"  {severity_icon} {violation.message}")
            report.append("")

        # Add next steps
        report.append("📝 NEXT STEPS:")
        if error_count > 0:
            report.append("1. Fix all critical errors before deployment")
            report.append("2. Re-run validation after fixes")
            report.append("3. Address warnings for optimal production readiness")
        else:
            report.append("1. Review and address warnings")
            report.append("2. Proceed with cautious deployment")
            report.append("3. Monitor closely during initial rollout")

        return "\n".join(report)
