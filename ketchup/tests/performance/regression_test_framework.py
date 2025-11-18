#!/usr/bin/env python3
"""
Performance Regression Test Framework for TypedDI Resolution

Framework for monitoring and detecting performance regressions in TypedDI
service resolution with baseline comparison and automated detection.

Features:
- Performance baseline establishment and comparison
- Automated regression detection with configurable thresholds
- Service resolution timing and memory analysis
- Batch performance testing for scalability
"""

from __future__ import annotations

import gc
import json
import os
import psutil
import statistics
import sys
import time
import tracemalloc
import unittest
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Type

# Add ketchup root to path for imports
ketchup_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ketchup_root)

from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations import register_all_services

logger = setup_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance measurement data."""
    service_name: str
    resolution_time_ms: float
    memory_peak_mb: float
    memory_current_mb: float
    cpu_percent: float
    iterations: int
    timestamp: float
    baseline_deviation: Optional[float] = None
    regression_detected: bool = False


@dataclass
class PerformanceBaseline:
    """Container for performance baseline data."""
    service_name: str
    avg_resolution_time_ms: float
    max_resolution_time_ms: float
    avg_memory_peak_mb: float
    max_memory_peak_mb: float
    samples: int
    created_timestamp: float


class PerformanceMonitor:
    """Performance monitoring for TypedDI service resolution."""

    def __init__(self):
        self.baseline_file = "tests/performance/baselines.json"
        self.process = psutil.Process()
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self._load_baselines()

    def _load_baselines(self) -> None:
        """Load existing performance baselines from file."""
        if os.path.exists(self.baseline_file):
            try:
                with open(self.baseline_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.baselines = {
                    name: PerformanceBaseline(**baseline_data)
                    for name, baseline_data in data.items()
                }
                logger.info(f"Loaded {len(self.baselines)} performance baselines")
            except Exception as e:
                logger.warning(f"Failed to load baselines: {e}")

    def save_baselines(self) -> None:
        """Save current baselines to file."""
        os.makedirs(os.path.dirname(self.baseline_file), exist_ok=True)
        baseline_data = {
            name: asdict(baseline) for name, baseline in self.baselines.items()
        }
        with open(self.baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, indent=2)
        logger.info(f"Saved {len(self.baselines)} performance baselines")

    def measure_service_resolution(self, registry: TypedServiceRegistry,
                                 service_type: Type, iterations: int = 100) -> PerformanceMetrics:
        """Measure performance of service resolution with detailed metrics."""
        service_name = service_type.__name__
        resolution_times = []
        memory_peaks = []

        # Warm up
        for _ in range(5):
            try:
                registry.get(service_type)
            except Exception:
                pass

        gc.collect()
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        start_cpu_time = self.process.cpu_percent()

        # Performance measurement loop
        for i in range(iterations):
            tracemalloc.start()
            start_time = time.perf_counter()

            try:
                instance = registry.get(service_type)
                if instance is None:
                    continue

                end_time = time.perf_counter()
                resolution_time = (end_time - start_time) * 1000
                resolution_times.append(resolution_time)

                current, peak = tracemalloc.get_traced_memory()
                memory_peaks.append(peak / 1024 / 1024)

            except Exception as e:
                logger.debug(f"Resolution failed for {service_name}: {e}")
            finally:
                tracemalloc.stop()

        current_memory = self.process.memory_info().rss / 1024 / 1024
        cpu_percent = self.process.cpu_percent() - start_cpu_time

        if not resolution_times:
            return PerformanceMetrics(
                service_name=service_name, resolution_time_ms=0.0, memory_peak_mb=0.0,
                memory_current_mb=current_memory - initial_memory, cpu_percent=cpu_percent,
                iterations=0, timestamp=time.time()
            )

        avg_resolution_time = statistics.mean(resolution_times)
        avg_memory_peak = statistics.mean(memory_peaks)

        metrics = PerformanceMetrics(
            service_name=service_name, resolution_time_ms=avg_resolution_time,
            memory_peak_mb=avg_memory_peak, memory_current_mb=current_memory - initial_memory,
            cpu_percent=cpu_percent, iterations=len(resolution_times), timestamp=time.time()
        )

        self._analyze_regression(metrics)
        return metrics

    def _analyze_regression(self, metrics: PerformanceMetrics) -> None:
        """Analyze metrics against baseline to detect regression."""
        baseline = self.baselines.get(metrics.service_name)
        if not baseline:
            return

        # Calculate deviation percentage
        time_deviation = (
            (metrics.resolution_time_ms - baseline.avg_resolution_time_ms)
            / baseline.avg_resolution_time_ms * 100
        )
        memory_deviation = (
            (metrics.memory_peak_mb - baseline.avg_memory_peak_mb)
            / baseline.avg_memory_peak_mb * 100
        )

        metrics.baseline_deviation = max(time_deviation, memory_deviation)

        # Detect regression (> 20% performance degradation)
        if time_deviation > 20 or memory_deviation > 25:
            metrics.regression_detected = True
            logger.warning(
                f"Performance regression detected for {metrics.service_name}: "
                f"time +{time_deviation:.1f}%, memory +{memory_deviation:.1f}%"
            )

    def establish_baseline(self, registry: TypedServiceRegistry,
                         service_type: Type, iterations: int = 200) -> None:
        """Establish performance baseline for a service."""
        service_name = service_type.__name__
        logger.info(f"Establishing baseline for {service_name}")

        resolution_times = []
        memory_peaks = []

        for _ in range(iterations):
            tracemalloc.start()
            start_time = time.perf_counter()

            try:
                instance = registry.get(service_type)
                if instance is not None:
                    end_time = time.perf_counter()
                    resolution_time = (end_time - start_time) * 1000
                    resolution_times.append(resolution_time)

                    current, peak = tracemalloc.get_traced_memory()
                    memory_peaks.append(peak / 1024 / 1024)

            except Exception:
                pass
            finally:
                tracemalloc.stop()

        if resolution_times:
            baseline = PerformanceBaseline(
                service_name=service_name,
                avg_resolution_time_ms=statistics.mean(resolution_times),
                max_resolution_time_ms=max(resolution_times),
                avg_memory_peak_mb=statistics.mean(memory_peaks),
                max_memory_peak_mb=max(memory_peaks),
                samples=len(resolution_times),
                created_timestamp=time.time()
            )

            self.baselines[service_name] = baseline
            logger.info(f"Baseline established for {service_name}: "
                       f"{baseline.avg_resolution_time_ms:.2f}ms avg")


class PerformanceRegressionTestSuite(unittest.TestCase):
    """Comprehensive performance regression test suite."""

    @classmethod
    def setUpClass(cls):
        """Set up performance testing environment."""
        import packages.core.typed_di.service_registrations as svc_reg
        if hasattr(svc_reg, "_registration_manager"):
            svc_reg._registration_manager = None

        cls.registry = TypedServiceRegistry()
        register_all_services(cls.registry)
        cls.monitor = PerformanceMonitor()

    def test_service_resolution_performance(self):
        """Test resolution performance for all services against baselines."""
        errors = []
        regression_count = 0
        total_services = 0

        for service_type, _ in self.registry._registrations.items():
            if not hasattr(service_type, "__name__"):
                continue

            total_services += 1
            metrics = self.monitor.measure_service_resolution(
                self.registry, service_type, iterations=50
            )

            if metrics.regression_detected:
                regression_count += 1
                errors.append(
                    f"{metrics.service_name}: performance regression detected "
                    f"(+{metrics.baseline_deviation:.1f}% degradation)"
                )

            # Log performance data
            logger.info(
                f"{metrics.service_name}: {metrics.resolution_time_ms:.2f}ms, "
                f"{metrics.memory_peak_mb:.2f}MB peak memory"
            )

        logger.info(f"Performance test completed: {regression_count}/{total_services} regressions")

        if errors:
            self.fail("Performance regressions detected:\n" + "\n".join(errors))

    def test_batch_resolution_scalability(self):
        """Test scalability with batch service resolution."""
        errors = []
        batch_sizes = [10, 50, 100]

        # Test with a representative service
        test_services = []
        for service_type, _ in self.registry._registrations.items():
            if hasattr(service_type, "__name__") and len(test_services) < 3:
                test_services.append(service_type)

        for service_type in test_services:
            service_name = service_type.__name__
            previous_time = None

            for batch_size in batch_sizes:
                metrics = self.monitor.measure_service_resolution(
                    self.registry, service_type, iterations=batch_size
                )

                if previous_time and metrics.resolution_time_ms > previous_time * 2:
                    errors.append(
                        f"{service_name}: scalability issue - "
                        f"resolution time doubled at batch size {batch_size}"
                    )

                previous_time = metrics.resolution_time_ms

        if errors:
            self.fail("Scalability issues detected:\n" + "\n".join(errors))

    def test_memory_usage_efficiency(self):
        """Test memory efficiency during service resolution."""
        errors = []
        memory_threshold_mb = 50  # 50MB threshold per service

        services_tested = 0
        for service_type, _ in self.registry._registrations.items():
            if not hasattr(service_type, "__name__") or services_tested >= 10:
                continue

            metrics = self.monitor.measure_service_resolution(
                self.registry, service_type, iterations=100
            )

            if metrics.memory_peak_mb > memory_threshold_mb:
                errors.append(
                    f"{metrics.service_name}: excessive memory usage "
                    f"({metrics.memory_peak_mb:.1f}MB > {memory_threshold_mb}MB threshold)"
                )

            services_tested += 1

        if errors:
            self.fail("Memory efficiency issues:\n" + "\n".join(errors))


def establish_performance_baselines(registry: TypedServiceRegistry) -> Dict[str, PerformanceBaseline]:
    """Establish performance baselines for all services."""
    monitor = PerformanceMonitor()
    baselines_created = {}

    logger.info("Establishing performance baselines for all services...")

    for service_type, _ in registry._registrations.items():
        if not hasattr(service_type, "__name__"):
            continue

        try:
            monitor.establish_baseline(registry, service_type, iterations=100)
            baseline = monitor.baselines.get(service_type.__name__)
            if baseline:
                baselines_created[service_type.__name__] = baseline

        except Exception as e:
            logger.warning(f"Failed to establish baseline for {service_type.__name__}: {e}")

    monitor.save_baselines()
    logger.info(f"Established {len(baselines_created)} performance baselines")

    return baselines_created


def generate_performance_report(registry: TypedServiceRegistry) -> Dict[str, Any]:
    """Generate performance analysis report."""
    monitor = PerformanceMonitor()
    report = {
        "timestamp": time.time(),
        "total_services": len(registry._registrations),
        "performance_metrics": [],
        "regressions_detected": 0,
        "summary": {"avg_resolution_time_ms": 0.0, "services_with_regressions": []}
    }

    resolution_times = []
    services_tested = 0
    for service_type, _ in registry._registrations.items():
        if not hasattr(service_type, "__name__") or services_tested >= 10:
            continue

        try:
            metrics = monitor.measure_service_resolution(registry, service_type, iterations=25)
            report["performance_metrics"].append(asdict(metrics))

            if metrics.regression_detected:
                report["regressions_detected"] += 1
                report["summary"]["services_with_regressions"].append(metrics.service_name)

            if metrics.resolution_time_ms > 0:
                resolution_times.append(metrics.resolution_time_ms)

            services_tested += 1

        except Exception as e:
            logger.warning(f"Performance measurement failed for {service_type.__name__}: {e}")

    if resolution_times:
        report["summary"]["avg_resolution_time_ms"] = statistics.mean(resolution_times)

    return report


if __name__ == "__main__":
    unittest.main(verbosity=2)