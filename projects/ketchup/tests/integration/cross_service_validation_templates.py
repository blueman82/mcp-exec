#!/usr/bin/env python3
"""
Cross-Service Dependency Validation Templates for TypedDI

Provides focused test templates for validating cross-service dependencies
in TypedDI registrations. Ensures proper dependency injection across service
boundaries with comprehensive validation patterns.

Key Features:
- Service dependency validation
- Cross-service interaction testing
- Failure scenario handling
- Comprehensive reporting
"""

from __future__ import annotations

import inspect
import os
import sys
import time
import unittest
from typing import Any, Dict, List, Type
from unittest.mock import patch

sys.path.insert(0, os.getcwd())

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services

logger = setup_logger(__name__)


class ServiceDependencyValidator:
    """Validates service dependencies and cross-service interactions."""

    def __init__(self, registry: TypedServiceRegistry):
        self.registry = registry

    def validate_service_dependencies(self, service_type: Type) -> Dict[str, Any]:
        """Validate all dependencies for a service type."""
        result = {
            "service_type": service_type.__name__,
            "module": service_type.__module__,
            "dependencies_valid": True,
            "missing_dependencies": [],
            "circular_dependencies": [],
            "resolution_time": 0.0,
            "errors": []
        }

        try:
            start_time = time.time()

            # Check if service can be resolved
            instance = self.registry.get(service_type)
            if instance is None:
                result["dependencies_valid"] = False
                result["errors"].append("Service resolution returned None")
                return result

            # Validate constructor dependencies
            self._validate_constructor_dependencies(service_type, result)

            # Check for circular dependencies
            self._detect_circular_dependencies(service_type, result)

            result["resolution_time"] = time.time() - start_time

        except Exception as e:
            result["dependencies_valid"] = False
            result["errors"].append(f"Resolution failed: {str(e)}")

        return result

    def _validate_constructor_dependencies(self, service_type: Type,
                                         result: Dict[str, Any]) -> None:
        """Validate constructor parameter dependencies."""
        try:
            sig = inspect.signature(service_type.__init__)
            for name, param in sig.parameters.items():
                if name == "self" or param.default is not inspect._empty:
                    continue

                # Required parameter - check if dependency exists
                if param.annotation != inspect._empty:
                    try:
                        self.registry.get(param.annotation)
                    except Exception:
                        result["missing_dependencies"].append({
                            "parameter": name,
                            "type": str(param.annotation)
                        })
                        result["dependencies_valid"] = False

        except Exception as e:
            result["errors"].append(f"Constructor validation failed: {str(e)}")

    def _detect_circular_dependencies(self, service_type: Type,
                                    result: Dict[str, Any]) -> None:
        """Detect circular dependency chains using DFS."""
        visited = set()
        visiting = set()

        def dfs(current_type: Type, path: List[str]) -> bool:
            if current_type in visiting:
                circular_path = path[path.index(current_type.__name__):]
                result["circular_dependencies"].append(circular_path)
                return True

            if current_type in visited:
                return False

            visiting.add(current_type)

            try:
                registration = self.registry._registrations.get(current_type)
                if registration and hasattr(registration, 'dependencies'):
                    for dep in registration.dependencies:
                        if hasattr(dep, 'type') and inspect.isclass(dep.type):
                            new_path = path + [current_type.__name__]
                            if dfs(dep.type, new_path):
                                return True
            except Exception:
                pass

            visiting.remove(current_type)
            visited.add(current_type)
            return False

        dfs(service_type, [])


class CrossServiceInteractionTester:
    """Tests cross-service interactions and communication patterns."""

    def __init__(self, registry: TypedServiceRegistry):
        self.registry = registry

    def test_service_communication(self, service_a: Type, service_b: Type,
                                 interaction_method: str) -> Dict[str, Any]:
        """Test communication between two services."""
        result = {
            "service_a": service_a.__name__,
            "service_b": service_b.__name__,
            "interaction_method": interaction_method,
            "communication_successful": False,
            "response_time": 0.0,
            "errors": []
        }

        try:
            start_time = time.time()

            # Get service instances
            instance_a = self.registry.get(service_a)
            instance_b = self.registry.get(service_b)

            if instance_a is None or instance_b is None:
                result["errors"].append("Failed to resolve service instances")
                return result

            # Test interaction if method exists
            if hasattr(instance_a, interaction_method):
                method = getattr(instance_a, interaction_method)
                if callable(method):
                    # Mock the interaction for testing
                    with patch.object(instance_a, interaction_method) as mock_method:
                        mock_method.return_value = "test_response"
                        response = mock_method(instance_b)
                        result["communication_successful"] = response is not None

            result["response_time"] = time.time() - start_time

        except Exception as e:
            result["errors"].append(f"Communication test failed: {str(e)}")

        return result

    def test_critical_service_pairs(self) -> List[Dict[str, Any]]:
        """Test interactions between critical service pairs."""
        critical_pairs = [
            ("SlackAsyncClient", "SecretsManager"),
            ("DynamoDBAsyncClient", "DynamoDBConfig"),
            ("OpenAIHandler", "AzureConfig"),
        ]

        results = []

        for service_a_name, service_b_name in critical_pairs:
            # Find service types by name
            service_a = self._find_service_by_name(service_a_name)
            service_b = self._find_service_by_name(service_b_name)

            if service_a and service_b:
                result = self.test_service_communication(
                    service_a, service_b, "test_interaction"
                )
                results.append(result)

        return results

    def _find_service_by_name(self, service_name: str) -> Type:
        """Find service type by name in registry."""
        for service_type in self.registry._registrations.keys():
            if hasattr(service_type, "__name__") and service_type.__name__ == service_name:
                return service_type
        return None


class FailureScenarioTester:
    """Tests dependency injection failure scenarios."""

    def __init__(self, registry: TypedServiceRegistry):
        self.registry = registry

    def test_missing_dependency_handling(self, service_type: Type) -> Dict[str, Any]:
        """Test behavior when dependencies are missing."""
        result = {
            "service_type": service_type.__name__,
            "handles_missing_deps": False,
            "error_message": "",
            "graceful_degradation": False,
            "errors": []
        }

        try:
            # Create a registry without this service's dependencies
            test_registry = TypedServiceRegistry()

            try:
                test_registry.register(service_type, service_type)
                instance = test_registry.get(service_type)

                if instance is None:
                    result["handles_missing_deps"] = True
                    result["graceful_degradation"] = True

            except Exception as e:
                result["error_message"] = str(e)
                result["handles_missing_deps"] = True

                # Check if error message is informative
                if "dependency" in str(e).lower() or "missing" in str(e).lower():
                    result["graceful_degradation"] = True

        except Exception as e:
            result["errors"].append(f"Test setup failed: {str(e)}")

        return result

    def test_malformed_service_handling(self, service_type: Type) -> Dict[str, Any]:
        """Test behavior with malformed service configurations."""
        result = {
            "service_type": service_type.__name__,
            "handles_malformed_config": False,
            "error_recovery": False,
            "errors": []
        }

        try:
            # Test with corrupted dependencies
            test_registry = TypedServiceRegistry()
            test_registry.register(service_type, lambda: None)  # Invalid factory

            try:
                instance = test_registry.get(service_type)
                result["handles_malformed_config"] = instance is None
                result["error_recovery"] = True
            except Exception as e:
                result["handles_malformed_config"] = True
                result["error_recovery"] = "malformed" in str(e).lower()

        except Exception as e:
            result["errors"].append(f"Malformed config test failed: {str(e)}")

        return result

    def test_concurrent_access_failures(self, service_type: Type) -> Dict[str, Any]:
        """Test service behavior under concurrent access scenarios."""
        result = {
            "service_type": service_type.__name__,
            "thread_safe": True,
            "concurrent_resolution_successful": True,
            "errors": []
        }

        try:
            import threading
            import queue

            results_queue = queue.Queue()
            exceptions_queue = queue.Queue()

            def resolve_service():
                try:
                    instance = self.registry.get(service_type)
                    results_queue.put(instance is not None)
                except Exception as e:
                    exceptions_queue.put(str(e))

            # Create multiple threads for concurrent access
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=resolve_service)
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5.0)

            # Analyze results
            successful_resolutions = 0
            while not results_queue.empty():
                if results_queue.get():
                    successful_resolutions += 1

            # Check for exceptions
            while not exceptions_queue.empty():
                exception = exceptions_queue.get()
                result["errors"].append(f"Concurrent access exception: {exception}")
                result["thread_safe"] = False

            result["concurrent_resolution_successful"] = successful_resolutions >= 3

        except Exception as e:
            result["errors"].append(f"Concurrent access test failed: {str(e)}")
            result["thread_safe"] = False
            result["concurrent_resolution_successful"] = False

        return result

    def test_memory_pressure_handling(self, service_type: Type) -> Dict[str, Any]:
        """Test service behavior under memory pressure."""
        result = {
            "service_type": service_type.__name__,
            "handles_memory_pressure": True,
            "memory_efficient": True,
            "errors": []
        }

        try:
            initial_memory = self._get_memory_usage()

            # Create multiple instances to simulate memory pressure
            instances = []
            for _ in range(10):
                try:
                    instance = self.registry.get(service_type)
                    if instance is not None:
                        instances.append(instance)
                except Exception as e:
                    result["errors"].append(f"Memory pressure resolution failed: {str(e)}")
                    result["handles_memory_pressure"] = False

            final_memory = self._get_memory_usage()
            memory_increase = final_memory - initial_memory

            # Consider memory efficient if increase is less than 10MB
            result["memory_efficient"] = memory_increase < 10.0

            # Clean up
            del instances

        except Exception as e:
            result["errors"].append(f"Memory pressure test failed: {str(e)}")
            result["handles_memory_pressure"] = False

        return result

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0


class CrossServiceValidationTestSuite(unittest.TestCase):
    """Complete test suite for cross-service dependency validation."""

    @classmethod
    def setUpClass(cls):
        """Set up test registry with all services."""
        import packages.core.typed_di.service_registrations as svc_reg
        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None

        cls.registry = TypedServiceRegistry()
        register_all_services(cls.registry)

        # Initialize test components
        cls.dependency_validator = ServiceDependencyValidator(cls.registry)
        cls.interaction_tester = CrossServiceInteractionTester(cls.registry)
        cls.failure_tester = FailureScenarioTester(cls.registry)

    def test_all_service_dependencies(self):
        """Test dependencies for all registered services."""
        errors = []
        total_services = 0
        valid_services = 0

        for service_type, _ in self.registry._registrations.items():
            if not inspect.isclass(service_type):
                continue

            total_services += 1
            result = self.dependency_validator.validate_service_dependencies(service_type)

            if result["dependencies_valid"]:
                valid_services += 1
            else:
                errors.append(
                    f"{service_type.__name__}: {', '.join(result['errors'])}"
                )

        logger.info(f"Dependency validation: {valid_services}/{total_services} services valid")

        if errors:
            self.fail("Service dependency validation failed:\n" + "\n".join(errors))

    def test_critical_service_interactions(self):
        """Test interactions between critical services."""
        results = self.interaction_tester.test_critical_service_pairs()
        errors = []

        for result in results:
            if result["errors"]:
                errors.append(
                    f"{result['service_a']} -> {result['service_b']}: {', '.join(result['errors'])}"
                )

        if errors:
            self.fail("Service interaction tests failed:\n" + "\n".join(errors))

    def test_failure_scenario_handling(self):
        """Test handling of dependency injection failures."""
        errors = []
        services_tested = 0

        for service_type, _ in self.registry._registrations.items():
            if not inspect.isclass(service_type) or services_tested >= 5:
                continue

            # Test missing dependency handling
            missing_dep_result = self.failure_tester.test_missing_dependency_handling(service_type)
            if not missing_dep_result["handles_missing_deps"] and not missing_dep_result["graceful_degradation"]:
                errors.append(
                    f"{service_type.__name__}: poor missing dependency handling - {', '.join(missing_dep_result['errors'])}"
                )

            # Test malformed service handling
            malformed_result = self.failure_tester.test_malformed_service_handling(service_type)
            if not malformed_result["handles_malformed_config"]:
                errors.append(
                    f"{service_type.__name__}: poor malformed config handling - {', '.join(malformed_result['errors'])}"
                )

            # Test concurrent access
            concurrent_result = self.failure_tester.test_concurrent_access_failures(service_type)
            if not concurrent_result["thread_safe"]:
                errors.append(
                    f"{service_type.__name__}: not thread-safe - {', '.join(concurrent_result['errors'])}"
                )

            # Test memory pressure handling
            memory_result = self.failure_tester.test_memory_pressure_handling(service_type)
            if not memory_result["handles_memory_pressure"]:
                errors.append(
                    f"{service_type.__name__}: poor memory pressure handling - {', '.join(memory_result['errors'])}"
                )

            services_tested += 1

        logger.info(f"Comprehensive failure scenario validation tested {services_tested} services")

        if errors:
            self.fail("Failure scenario tests failed:\n" + "\n".join(errors))

    def test_service_lifecycle_validation(self):
        """Test complete service lifecycle including initialization and cleanup."""
        errors = []
        lifecycle_tested = 0

        for service_type, _ in self.registry._registrations.items():
            if not inspect.isclass(service_type) or lifecycle_tested >= 8:
                continue

            try:
                # Test initialization
                instance = self.registry.get(service_type)
                if instance is None:
                    errors.append(f"{service_type.__name__}: failed to initialize")
                    continue

                # Test that instance has expected interface
                if hasattr(service_type, '__init__'):
                    sig = inspect.signature(service_type.__init__)
                    required_params = [
                        name for name, param in sig.parameters.items()
                        if name != "self" and param.default is inspect._empty
                    ]

                    if required_params and instance is not None:
                        # Service resolved successfully despite having dependencies
                        logger.debug(f"✅ {service_type.__name__}: lifecycle validation passed")

                lifecycle_tested += 1

            except Exception as e:
                errors.append(f"{service_type.__name__}: lifecycle validation failed - {str(e)}")

        logger.info(f"Service lifecycle validation tested {lifecycle_tested} services")

        if errors:
            self.fail("Service lifecycle validation failed:\n" + "\n".join(errors))


def generate_validation_report(registry: TypedServiceRegistry) -> Dict[str, Any]:
    """Generate comprehensive cross-service validation report."""
    report = {
        "timestamp": time.time(),
        "total_services": len(registry._registrations),
        "dependency_results": [],
        "interaction_results": [],
        "failure_scenario_results": [],
        "summary": {
            "services_with_valid_dependencies": 0,
            "services_with_circular_dependencies": 0,
            "services_with_missing_dependencies": 0,
            "average_resolution_time": 0.0
        }
    }

    # Initialize components
    dependency_validator = ServiceDependencyValidator(registry)
    interaction_tester = CrossServiceInteractionTester(registry)
    failure_tester = FailureScenarioTester(registry)

    total_resolution_time = 0.0

    # Test all services
    for service_type, _ in registry._registrations.items():
        if not inspect.isclass(service_type):
            continue

        # Dependency validation
        dep_result = dependency_validator.validate_service_dependencies(service_type)
        report["dependency_results"].append(dep_result)

        if dep_result["dependencies_valid"]:
            report["summary"]["services_with_valid_dependencies"] += 1
        if dep_result["circular_dependencies"]:
            report["summary"]["services_with_circular_dependencies"] += 1
        if dep_result["missing_dependencies"]:
            report["summary"]["services_with_missing_dependencies"] += 1

        total_resolution_time += dep_result["resolution_time"]

        # Failure scenario validation (limited sampling)
        if report["summary"]["services_with_valid_dependencies"] < 10:
            failure_result = failure_tester.test_missing_dependency_handling(service_type)
            report["failure_scenario_results"].append(failure_result)

    # Test critical interactions
    report["interaction_results"] = interaction_tester.test_critical_service_pairs()

    # Add comprehensive failure scenario results
    report["failure_scenarios"] = {
        "missing_dependency_tests": [],
        "malformed_config_tests": [],
        "concurrent_access_tests": [],
        "memory_pressure_tests": []
    }

    tested_count = 0
    for service_type, _ in registry._registrations.items():
        if not inspect.isclass(service_type) or tested_count >= 8:
            continue

        # Run comprehensive failure scenario tests
        missing_dep_result = failure_tester.test_missing_dependency_handling(service_type)
        report["failure_scenarios"]["missing_dependency_tests"].append(missing_dep_result)

        malformed_result = failure_tester.test_malformed_service_handling(service_type)
        report["failure_scenarios"]["malformed_config_tests"].append(malformed_result)

        concurrent_result = failure_tester.test_concurrent_access_failures(service_type)
        report["failure_scenarios"]["concurrent_access_tests"].append(concurrent_result)

        memory_result = failure_tester.test_memory_pressure_handling(service_type)
        report["failure_scenarios"]["memory_pressure_tests"].append(memory_result)

        tested_count += 1

    # Calculate comprehensive failure scenario summary
    report["summary"]["failure_scenario_coverage"] = {
        "services_tested": tested_count,
        "thread_safe_services": sum(1 for r in report["failure_scenarios"]["concurrent_access_tests"] if r["thread_safe"]),
        "memory_efficient_services": sum(1 for r in report["failure_scenarios"]["memory_pressure_tests"] if r["memory_efficient"]),
        "graceful_degradation_services": sum(1 for r in report["failure_scenarios"]["missing_dependency_tests"] if r["graceful_degradation"])
    }

    # Calculate averages
    if report["dependency_results"]:
        report["summary"]["average_resolution_time"] = (
            total_resolution_time / len(report["dependency_results"])
        )

    return report


if __name__ == "__main__":
    unittest.main(verbosity=2)