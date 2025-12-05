#!/usr/bin/env python3
"""
Test Result Aggregator for TypedDI Validation

Aggregates test results and validates zero errors/warnings requirement
across all TypedDI tests with comprehensive analysis and reporting.

Features:
- Zero-error validation across all test components
- Result aggregation and failure analysis
- Actionable reporting for issue resolution
- CI/CD integration for automated validation
"""

from __future__ import annotations

import json
import os
import sys
import time
import unittest
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.getcwd())

try:
    from tests.integration.cross_service_validation_templates import generate_validation_report
except ImportError:
    generate_validation_report = None

try:
    from tests.performance.regression_test_framework import generate_performance_report
except ImportError:
    generate_performance_report = None

try:
    from tests.automation.test_execution_pipeline import TestExecutionPipeline
except ImportError:
    TestExecutionPipeline = None

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services

logger = setup_logger(__name__)
if not generate_performance_report:
    logger.warning(
        "Performance test framework not available "
        "(missing psutil dependency) - limited functionality"
    )
if not generate_validation_report:
    logger.warning("Cross-service validation not available - limited functionality")
if not TestExecutionPipeline:
    logger.warning("Test execution pipeline not available - limited functionality")


@dataclass
class ValidationSummary:
    """Summary of validation results across all components."""

    timestamp: float
    total_services_tested: int
    services_with_issues: int
    dependency_validation_passed: bool
    performance_validation_passed: bool
    cross_service_validation_passed: bool
    zero_errors_achieved: bool
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]


@dataclass
class AggregatedTestResults:
    """Aggregated results from all test components."""

    validation_summary: ValidationSummary
    dependency_results: Optional[Dict[str, Any]] = None
    performance_results: Optional[Dict[str, Any]] = None
    cross_service_results: Optional[Dict[str, Any]] = None
    execution_pipeline_results: Optional[Dict[str, Any]] = None


class TestResultAggregator:
    """Aggregates and validates test results for zero-error requirement."""

    __test__ = False  # Tell pytest this is not a test class

    def __init__(self):
        self.registry = None
        self.results_dir = "tests/automation/aggregated_results"
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Set up the aggregation environment."""
        os.makedirs(self.results_dir, exist_ok=True)

        # Initialize registry
        import packages.core.typed_di.service_registrations as svc_reg

        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None

        self.registry = TypedServiceRegistry()
        register_all_services(self.registry)

    def collect_all_test_results(self) -> AggregatedTestResults:
        """Collect results from all test components."""
        logger.info("Collecting test results from all components...")

        validation_summary = ValidationSummary(
            timestamp=time.time(),
            total_services_tested=len(self.registry._registrations),
            services_with_issues=0,
            dependency_validation_passed=True,
            performance_validation_passed=True,
            cross_service_validation_passed=True,
            zero_errors_achieved=True,
            critical_issues=[],
            warnings=[],
            recommendations=[],
        )

        results = AggregatedTestResults(validation_summary=validation_summary)

        # Collect dependency validation results
        try:
            results.dependency_results = self._collect_dependency_results()
            validation_summary.dependency_validation_passed = self._validate_dependency_results(
                results.dependency_results, validation_summary
            )
        except Exception as e:
            logger.error(f"Failed to collect dependency results: {e}")
            validation_summary.dependency_validation_passed = False
            validation_summary.critical_issues.append(f"Dependency validation failed: {str(e)}")

        # Collect performance results
        try:
            results.performance_results = self._collect_performance_results()
            validation_summary.performance_validation_passed = self._validate_performance_results(
                results.performance_results, validation_summary
            )
        except Exception as e:
            logger.error(f"Failed to collect performance results: {e}")
            validation_summary.performance_validation_passed = False
            validation_summary.critical_issues.append(f"Performance validation failed: {str(e)}")

        # Collect cross-service validation results
        try:
            results.cross_service_results = self._collect_cross_service_results()
            validation_summary.cross_service_validation_passed = (
                self._validate_cross_service_results(
                    results.cross_service_results, validation_summary
                )
            )
        except Exception as e:
            logger.error(f"Failed to collect cross-service results: {e}")
            validation_summary.cross_service_validation_passed = False
            validation_summary.critical_issues.append(f"Cross-service validation failed: {str(e)}")

        # Final zero-error validation
        validation_summary.zero_errors_achieved = (
            validation_summary.dependency_validation_passed
            and validation_summary.performance_validation_passed
            and validation_summary.cross_service_validation_passed
            and len(validation_summary.critical_issues) == 0
        )

        self._generate_recommendations(validation_summary)
        return results

    def _collect_dependency_results(self) -> Dict[str, Any]:
        """Collect dependency validation results."""
        logger.info("Collecting dependency validation results...")

        # Run dependency coverage tests
        from tests.unit.core.typed_di.test_dependency_coverage import TestDependencyCoverage

        test_suite = unittest.TestSuite()
        test_suite.addTest(
            TestDependencyCoverage("test_required_constructor_types_are_declared_as_dependencies")
        )

        result = unittest.TestResult()
        test_suite.run(result)

        return {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "success": result.wasSuccessful(),
            "failure_details": [str(failure[1]) for failure in result.failures],
            "error_details": [str(error[1]) for error in result.errors],
        }

    def _collect_performance_results(self) -> Dict[str, Any]:
        """Collect performance validation results."""
        logger.info("Collecting performance validation results...")
        if generate_performance_report:
            return generate_performance_report(self.registry)
        return {"error": "Performance framework unavailable", "success": False}

    def _collect_cross_service_results(self) -> Dict[str, Any]:
        """Collect cross-service validation results."""
        logger.info("Collecting cross-service validation results...")
        return generate_validation_report(self.registry)

    def _validate_dependency_results(
        self, results: Dict[str, Any], summary: ValidationSummary
    ) -> bool:
        """Validate dependency test results for zero-error requirement."""
        if not results["success"]:
            summary.critical_issues.extend(
                [
                    f"Dependency validation failure: {detail}"
                    for detail in results["failure_details"]
                ]
            )
            summary.critical_issues.extend(
                [f"Dependency validation error: {detail}" for detail in results["error_details"]]
            )
            return False

        summary.recommendations.append(
            "Dependency validation: All services have valid dependencies"
        )
        return True

    def _validate_performance_results(
        self, results: Dict[str, Any], summary: ValidationSummary
    ) -> bool:
        """Validate performance test results for regressions."""
        regressions = results.get("regressions_detected", 0)

        if regressions > 0:
            regression_services = results.get("summary", {}).get("services_with_regressions", [])
            summary.critical_issues.append(
                f"Performance regressions detected in {regressions} services: {', '.join(regression_services)}"
            )
            return False

        # Check for excessive resolution times
        avg_time = results.get("summary", {}).get("avg_resolution_time_ms", 0)
        if avg_time > 10.0:  # 10ms threshold
            summary.warnings.append(
                f"Average resolution time ({avg_time:.1f}ms) exceeds recommended threshold (10ms)"
            )

        summary.recommendations.append(
            "Performance validation: No significant regressions detected"
        )
        return True

    def _validate_cross_service_results(
        self, results: Dict[str, Any], summary: ValidationSummary
    ) -> bool:
        """Validate cross-service test results."""
        valid_services = results.get("summary", {}).get("services_with_valid_dependencies", 0)
        circular_deps = results.get("summary", {}).get("services_with_circular_dependencies", 0)
        missing_deps = results.get("summary", {}).get("services_with_missing_dependencies", 0)

        has_issues = False

        if circular_deps > 0:
            summary.critical_issues.append(
                f"Circular dependencies detected in {circular_deps} services"
            )
            has_issues = True

        if missing_deps > 0:
            summary.critical_issues.append(
                f"Missing dependencies detected in {missing_deps} services"
            )
            has_issues = True

        if not has_issues:
            summary.recommendations.append(
                f"Cross-service validation: {valid_services} services validated successfully"
            )

        summary.services_with_issues = circular_deps + missing_deps
        return not has_issues

    def _generate_recommendations(self, summary: ValidationSummary) -> None:
        """Generate actionable recommendations based on validation results."""
        if summary.zero_errors_achieved:
            summary.recommendations.append("🎉 All validations passed - TypedDI system is healthy!")
            summary.recommendations.append(
                "Consider establishing performance baselines for regression detection"
            )
        else:
            summary.recommendations.append(
                "❌ Critical issues detected - immediate action required"
            )
            if not summary.dependency_validation_passed:
                summary.recommendations.append("Priority 1: Fix dependency validation issues")
                summary.recommendations.append(
                    "- Review service registrations and constructor dependencies"
                )
            if not summary.performance_validation_passed:
                summary.recommendations.append("Priority 2: Address performance regressions")
                summary.recommendations.append(
                    "- Review recent changes affecting service resolution"
                )
            if not summary.cross_service_validation_passed:
                summary.recommendations.append("Priority 3: Fix cross-service dependency issues")
                summary.recommendations.append(
                    "- Review service interactions and eliminate circular dependencies"
                )

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        logger.info("Generating comprehensive validation report...")

        results = self.collect_all_test_results()

        report = {
            "report_metadata": {
                "generated_at": time.time(),
                "generator": "TypedDI Test Result Aggregator",
                "version": "1.0",
            },
            "validation_summary": asdict(results.validation_summary),
            "detailed_results": {
                "dependency_validation": results.dependency_results,
                "performance_validation": results.performance_results,
                "cross_service_validation": results.cross_service_results,
            },
            "compliance_status": {
                "zero_errors_achieved": results.validation_summary.zero_errors_achieved,
                "compliance_score": self._calculate_compliance_score(results.validation_summary),
                "next_actions": results.validation_summary.recommendations[
                    :3
                ],  # Top 3 recommendations
            },
        }

        self._save_comprehensive_report(report)
        return report

    def _calculate_compliance_score(self, summary: ValidationSummary) -> float:
        """Calculate compliance score as percentage."""
        total_validations = 3  # dependency, performance, cross-service
        passed_validations = sum(
            [
                summary.dependency_validation_passed,
                summary.performance_validation_passed,
                summary.cross_service_validation_passed,
            ]
        )

        base_score = (passed_validations / total_validations) * 100

        # Deduct points for critical issues
        deduction = min(len(summary.critical_issues) * 10, 30)  # Max 30% deduction

        return max(base_score - deduction, 0.0)

    def _save_comprehensive_report(self, report: Dict[str, Any]) -> None:
        """Save comprehensive report to file."""
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.results_dir, f"comprehensive_report_{timestamp_str}.json")

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Comprehensive report saved to {report_file}")

        # Also save latest report
        latest_file = os.path.join(self.results_dir, "latest_report.json")
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    def validate_zero_errors_requirement(self) -> Tuple[bool, List[str]]:
        """Validate the zero errors/warnings requirement."""
        logger.info("Validating zero errors/warnings requirement...")

        results = self.collect_all_test_results()
        summary = results.validation_summary

        validation_passed = summary.zero_errors_achieved
        issues = summary.critical_issues.copy()

        if summary.warnings:
            issues.extend([f"WARNING: {warning}" for warning in summary.warnings])

        return validation_passed, issues


class ComplianceValidator(unittest.TestCase):
    """Unit tests for compliance validation."""

    def setUp(self):
        self.aggregator = TestResultAggregator()

    def test_zero_errors_requirement_compliance(self):
        """Test that zero errors requirement is met."""
        validation_passed, issues = self.aggregator.validate_zero_errors_requirement()

        if not validation_passed:
            self.fail("Zero errors requirement not met. Issues:\n" + "\n".join(issues))

        logger.info("✅ Zero errors requirement validated successfully")

    def test_comprehensive_validation_health_check(self):
        """Test overall system health through comprehensive validation."""
        report = self.aggregator.generate_comprehensive_report()

        compliance_score = report["compliance_status"]["compliance_score"]
        zero_errors = report["compliance_status"]["zero_errors_achieved"]

        self.assertTrue(zero_errors, "Zero errors requirement not achieved")
        self.assertGreaterEqual(
            compliance_score, 95.0, f"Compliance score too low: {compliance_score}%"
        )

        logger.info(f"✅ System health validated - Compliance score: {compliance_score}%")


def main():
    """Main function for standalone execution."""
    aggregator = TestResultAggregator()
    print("TypedDI Test Result Aggregator")
    print("=" * 50)

    report = aggregator.generate_comprehensive_report()
    summary = report["validation_summary"]

    print(f"Validation Status: {'✅ PASSED' if summary['zero_errors_achieved'] else '❌ FAILED'}")
    print(f"Services Tested: {summary['total_services_tested']}")
    print(f"Services with Issues: {summary['services_with_issues']}")
    print(f"Compliance Score: {report['compliance_status']['compliance_score']:.1f}%")

    if summary["critical_issues"]:
        print(f"\nCritical Issues ({len(summary['critical_issues'])}):")
        for issue in summary["critical_issues"]:
            print(f"  ❌ {issue}")

    if summary["warnings"]:
        print(f"\nWarnings ({len(summary['warnings'])}):")
        for warning in summary["warnings"]:
            print(f"  ⚠️  {warning}")

    print("\nRecommendations:")
    for rec in summary["recommendations"][:5]:
        print(f"  💡 {rec}")

    print("=" * 50)
    sys.exit(0 if summary["zero_errors_achieved"] else 1)


if __name__ == "__main__":
    main()
