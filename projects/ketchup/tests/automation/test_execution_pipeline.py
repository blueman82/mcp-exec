#!/usr/bin/env python3
"""
Automated Test Execution Pipeline for TypedDI Service Registration

Comprehensive pipeline that automatically runs after each service registration
to validate TypedDI integrity. Provides automated triggers, CI integration,
and batch processing capabilities for continuous validation.

Features:
- Automated test execution after service registrations
- CI/CD pipeline integration with configurable triggers
- Batch test processing with parallel execution
- Comprehensive result collection and analysis
- Integration with existing test frameworks
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import unittest
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.getcwd())

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services

# Import our test modules
try:
    from tests.integration.cross_service_validation_templates import (
        CrossServiceValidationTestSuite
    )
    from tests.performance.regression_test_framework import (
        PerformanceRegressionTestSuite
    )
except ImportError:
    logger = setup_logger(__name__)
    logger.warning("Test modules not found - some functionality may be limited")

logger = setup_logger(__name__)


@dataclass
class TestExecutionResult:
    """Container for test execution results."""
    __test__ = False  # Tell pytest this is not a test class
    test_name: str
    status: str  # "passed", "failed", "error"
    execution_time: float
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class PipelineExecutionReport:
    """Container for complete pipeline execution report."""
    timestamp: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    execution_time: float
    test_results: List[TestExecutionResult]
    zero_errors_achieved: bool


class TestExecutionPipeline:
    """Automated test execution pipeline for TypedDI validation."""
    __test__ = False  # Tell pytest this is not a test class

    def __init__(self):
        self.registry = None
        self.test_suites = []
        self.results_dir = "tests/automation/results"
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Set up the testing environment."""
        os.makedirs(self.results_dir, exist_ok=True)

        # Initialize registry
        import packages.core.typed_di.service_registrations as svc_reg
        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None

        self.registry = TypedServiceRegistry()
        register_all_services(self.registry)

    def register_test_suite(self, test_suite_class: type, name: str) -> None:
        """Register a test suite for execution."""
        self.test_suites.append({
            "class": test_suite_class,
            "name": name,
            "enabled": True
        })

    def execute_test_suite(self, test_suite_info: Dict[str, Any]) -> TestExecutionResult:
        """Execute a single test suite."""
        start_time = time.time()
        test_name = test_suite_info["name"]

        try:
            # Create test suite instance
            suite = unittest.TestSuite()
            test_class = test_suite_info["class"]

            # Add all test methods from the class
            for method_name in dir(test_class):
                if method_name.startswith("test_"):
                    suite.addTest(test_class(method_name))

            # Run tests with custom result collector
            TestResultCollector()
            runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'),
                                           resultclass=TestResultCollector)
            test_result = runner.run(suite)

            execution_time = time.time() - start_time

            if test_result.wasSuccessful():
                return TestExecutionResult(
                    test_name=test_name,
                    status="passed",
                    execution_time=execution_time,
                    details={"tests_run": test_result.testsRun}
                )
            else:
                error_messages = []
                for failure in test_result.failures:
                    error_messages.append(f"FAIL: {failure[0]} - {failure[1]}")
                for error in test_result.errors:
                    error_messages.append(f"ERROR: {error[0]} - {error[1]}")

                return TestExecutionResult(
                    test_name=test_name,
                    status="failed",
                    execution_time=execution_time,
                    error_message="; ".join(error_messages),
                    details={
                        "tests_run": test_result.testsRun,
                        "failures": len(test_result.failures),
                        "errors": len(test_result.errors)
                    }
                )

        except Exception as e:
            execution_time = time.time() - start_time
            return TestExecutionResult(
                test_name=test_name,
                status="error",
                execution_time=execution_time,
                error_message=str(e)
            )

    def execute_all_tests(self, parallel: bool = True) -> PipelineExecutionReport:
        """Execute all registered test suites."""
        start_time = time.time()
        test_results = []

        logger.info(f"Starting test execution pipeline with {len(self.test_suites)} test suites")

        if parallel and len(self.test_suites) > 1:
            # Execute tests in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_test = {
                    executor.submit(self.execute_test_suite, test_suite): test_suite
                    for test_suite in self.test_suites if test_suite["enabled"]
                }

                for future in concurrent.futures.as_completed(future_to_test):
                    result = future.result()
                    test_results.append(result)
                    logger.info(f"Completed test: {result.test_name} - {result.status}")
        else:
            # Execute tests sequentially
            for test_suite in self.test_suites:
                if test_suite["enabled"]:
                    result = self.execute_test_suite(test_suite)
                    test_results.append(result)
                    logger.info(f"Completed test: {result.test_name} - {result.status}")

        execution_time = time.time() - start_time

        # Analyze results
        passed_tests = sum(1 for r in test_results if r.status == "passed")
        failed_tests = sum(1 for r in test_results if r.status == "failed")
        error_tests = sum(1 for r in test_results if r.status == "error")

        zero_errors_achieved = failed_tests == 0 and error_tests == 0

        report = PipelineExecutionReport(
            timestamp=time.time(),
            total_tests=len(test_results),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests,
            execution_time=execution_time,
            test_results=test_results,
            zero_errors_achieved=zero_errors_achieved
        )

        self._save_execution_report(report)
        return report

    def _save_execution_report(self, report: PipelineExecutionReport) -> None:
        """Save execution report to file."""
        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(report.timestamp))
        report_file = os.path.join(self.results_dir, f"execution_report_{timestamp_str}.json")

        report_data = asdict(report)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Execution report saved to {report_file}")

    def run_after_service_registration(self) -> PipelineExecutionReport:
        """Run the pipeline after service registration changes."""
        logger.info("Triggered automated test execution after service registration")

        # Re-initialize registry to pick up new registrations
        self._setup_environment()

        # Execute all tests
        report = self.execute_all_tests(parallel=True)

        if report.zero_errors_achieved:
            logger.info("✅ All tests passed - zero errors/warnings achieved")
        else:
            logger.error(f"❌ Test failures detected: {report.failed_tests} failed, {report.error_tests} errors")

        return report


class TestResultCollector(unittest.TestResult):
    """Custom test result collector for detailed reporting."""
    __test__ = False  # Tell pytest this is not a test class

    def __init__(self):
        super().__init__()
        self.test_details = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.test_details.append({
            "test": str(test),
            "status": "success"
        })

    def addError(self, test, err):
        super().addError(test, err)
        self.test_details.append({
            "test": str(test),
            "status": "error",
            "error": str(err[1])
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.test_details.append({
            "test": str(test),
            "status": "failure",
            "error": str(err[1])
        })


class CIIntegrationManager:
    """Manages CI/CD pipeline integration."""

    @staticmethod
    def generate_ci_config() -> Dict[str, Any]:
        """Generate CI configuration for automated test execution."""
        return {
            "name": "TypedDI Validation Pipeline",
            "on": {
                "push": {"branches": ["main", "develop"]},
                "pull_request": {"branches": ["main"]}
            },
            "jobs": {
                "typeddi-validation": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v3"},
                        {"name": "Set up Python", "uses": "actions/setup-python@v4",
                         "with": {"python-version": "3.12"}},
                        {"name": "Install dependencies", "run": "pip install -r requirements.txt"},
                        {"name": "Run TypedDI validation",
                         "run": "python -m tests.automation.test_execution_pipeline"},
                        {"name": "Upload test results", "uses": "actions/upload-artifact@v3",
                         "with": {"name": "test-results", "path": "tests/automation/results/"}}
                    ]
                }
            }
        }

    @staticmethod
    def check_git_hooks() -> bool:
        """Check if git hooks are properly configured."""
        hooks_dir = ".git/hooks"
        pre_commit_hook = os.path.join(hooks_dir, "pre-commit")

        if os.path.exists(pre_commit_hook):
            with open(pre_commit_hook, 'r') as f:
                content = f.read()
                return "test_execution_pipeline" in content
        return False

    @staticmethod
    def install_git_hooks() -> None:
        """Install git hooks for automated test execution."""
        hooks_dir = ".git/hooks"
        pre_commit_hook = os.path.join(hooks_dir, "pre-commit")

        hook_content = """#!/bin/bash
# TypedDI Validation Pre-commit Hook
echo "Running TypedDI validation tests..."
python -m tests.automation.test_execution_pipeline
if [ $? -ne 0 ]; then
    echo "❌ TypedDI validation failed - commit blocked"
    exit 1
fi
echo "✅ TypedDI validation passed"
"""

        with open(pre_commit_hook, 'w') as f:
            f.write(hook_content)

        os.chmod(pre_commit_hook, 0o755)
        logger.info("Git pre-commit hook installed successfully")


def main():
    """Main execution function for the pipeline."""
    pipeline = TestExecutionPipeline()

    # Register available test suites
    try:
        pipeline.register_test_suite(CrossServiceValidationTestSuite, "cross_service_validation")
        pipeline.register_test_suite(PerformanceRegressionTestSuite, "performance_regression")
    except NameError:
        logger.warning("Some test suites not available - limited functionality")

    # Execute pipeline
    report = pipeline.execute_all_tests()

    # Print summary
    print(f"\n{'='*60}")
    print("TypedDI Validation Pipeline Results")
    print(f"{'='*60}")
    print(f"Total Tests: {report.total_tests}")
    print(f"Passed: {report.passed_tests}")
    print(f"Failed: {report.failed_tests}")
    print(f"Errors: {report.error_tests}")
    print(f"Execution Time: {report.execution_time:.2f}s")
    print(f"Zero Errors Achieved: {'✅ YES' if report.zero_errors_achieved else '❌ NO'}")
    print(f"{'='*60}")

    # Exit with appropriate code
    sys.exit(0 if report.zero_errors_achieved else 1)


if __name__ == "__main__":
    main()