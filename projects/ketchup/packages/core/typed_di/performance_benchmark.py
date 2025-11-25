"""Performance benchmarking framework for TypedDI service resolution.

This module provides comprehensive performance metrics for:
- Service resolution time analysis
- Memory footprint tracking
- Startup performance measurement
- Scalability projections
"""

import gc
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class BenchmarkResult:
    """Container for benchmark results and metrics."""

    service_count: int
    resolution_times: List[float] = field(default_factory=list)
    memory_before_mb: float = 0.0
    memory_after_mb: float = 0.0
    memory_delta_mb: float = 0.0
    total_time_ms: float = 0.0
    avg_resolution_time_ms: float = 0.0
    median_resolution_time_ms: float = 0.0
    p95_resolution_time_ms: float = 0.0
    p99_resolution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def calculate_statistics(self) -> None:
        """Calculate statistical metrics from resolution times."""
        if self.resolution_times:
            times_ms = [t * 1000 for t in self.resolution_times]
            self.avg_resolution_time_ms = statistics.mean(times_ms)
            self.median_resolution_time_ms = statistics.median(times_ms)
            if len(times_ms) > 1:
                self.p95_resolution_time_ms = statistics.quantiles(
                    times_ms, n=100
                )[94]
                self.p99_resolution_time_ms = statistics.quantiles(
                    times_ms, n=100
                )[98]
            else:
                self.p95_resolution_time_ms = times_ms[0]
                self.p99_resolution_time_ms = times_ms[0]


class TypedDIBenchmark:
    """Benchmark TypedDI service resolution performance."""

    def __init__(self, warmup_iterations: int = 3) -> None:
        """Initialize benchmarking system.

        Args:
            warmup_iterations: Number of warmup iterations before measurement
        """
        self.warmup_iterations = warmup_iterations
        self.results: List[BenchmarkResult] = []

    def benchmark_service_resolution(
        self,
        container: Any,
        service_names: List[str],
        iterations: int = 100
    ) -> BenchmarkResult:
        """Benchmark service resolution for given services.

        Args:
            container: TypedDI container instance
            service_names: List of service names to resolve
            iterations: Number of resolution iterations per service

        Returns:
            BenchmarkResult with performance metrics
        """
        result = BenchmarkResult(service_count=len(service_names))

        # Force garbage collection
        gc.collect()

        # Measure memory before
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # Warmup iterations
        for _ in range(self.warmup_iterations):
            for service_name in service_names:
                try:
                    container.resolve(service_name)
                except Exception:
                    pass

        # Actual benchmark
        start_time = time.perf_counter()

        for service_name in service_names:
            service_times = []
            for _ in range(iterations):
                iter_start = time.perf_counter()
                try:
                    container.resolve(service_name)
                except Exception:
                    pass
                iter_time = time.perf_counter() - iter_start
                service_times.append(iter_time)

            avg_time = statistics.mean(service_times)
            result.resolution_times.append(avg_time)

        end_time = time.perf_counter()
        result.total_time_ms = (end_time - start_time) * 1000

        # Measure memory after
        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Calculate memory stats
        stats = snapshot_after.compare_to(snapshot_before, 'lineno')
        memory_delta_bytes = sum(stat.size_diff for stat in stats)
        result.memory_delta_mb = memory_delta_bytes / (1024 * 1024)

        # Calculate statistics
        result.calculate_statistics()
        self.results.append(result)

        return result

    def project_scalability(
        self,
        current_result: BenchmarkResult,
        target_service_count: int
    ) -> Dict[str, Any]:
        """Project performance for target service count.

        Args:
            current_result: Current benchmark result
            target_service_count: Target number of services

        Returns:
            Dict with projected performance metrics
        """
        scale_factor = target_service_count / current_result.service_count

        # Linear projection (conservative estimate)
        linear_projection = {
            "service_count": target_service_count,
            "avg_resolution_time_ms": (
                current_result.avg_resolution_time_ms
            ),
            "total_resolution_time_ms": (
                current_result.avg_resolution_time_ms * target_service_count
            ),
            "memory_footprint_mb": (
                current_result.memory_delta_mb * scale_factor
            ),
            "startup_time_ms": (
                current_result.total_time_ms * scale_factor
            )
        }

        # O(log n) projection (optimistic for hash-based lookups)
        import math
        log_scale = math.log(target_service_count) / math.log(
            current_result.service_count
        )

        log_projection = {
            "service_count": target_service_count,
            "avg_resolution_time_ms": (
                current_result.avg_resolution_time_ms * log_scale
            ),
            "total_resolution_time_ms": (
                current_result.avg_resolution_time_ms * log_scale *
                target_service_count
            ),
            "memory_footprint_mb": (
                current_result.memory_delta_mb * scale_factor
            ),
            "startup_time_ms": (
                current_result.total_time_ms * log_scale
            )
        }

        return {
            "linear_projection": linear_projection,
            "logarithmic_projection": log_projection,
            "scale_factor": scale_factor,
            "current_baseline": {
                "service_count": current_result.service_count,
                "avg_resolution_time_ms": current_result.avg_resolution_time_ms,
                "memory_footprint_mb": current_result.memory_delta_mb
            }
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report.

        Returns:
            Dict with performance analysis and recommendations
        """
        if not self.results:
            return {"error": "No benchmark results available"}

        latest = self.results[-1]

        report = {
            "summary": {
                "timestamp": latest.timestamp,
                "services_tested": latest.service_count,
                "avg_resolution_ms": round(latest.avg_resolution_time_ms, 4),
                "p95_resolution_ms": round(latest.p95_resolution_time_ms, 4),
                "p99_resolution_ms": round(latest.p99_resolution_time_ms, 4),
                "memory_impact_mb": round(latest.memory_delta_mb, 2),
                "total_benchmark_ms": round(latest.total_time_ms, 2)
            },
            "performance_grade": self._calculate_grade(latest),
            "bottlenecks": self._identify_bottlenecks(latest),
            "recommendations": self._generate_recommendations(latest)
        }

        return report

    def _calculate_grade(self, result: BenchmarkResult) -> str:
        """Calculate performance grade based on metrics.

        Args:
            result: Benchmark result to grade

        Returns:
            Performance grade (A-F)
        """
        if result.avg_resolution_time_ms < 0.1:
            return "A"
        elif result.avg_resolution_time_ms < 0.5:
            return "B"
        elif result.avg_resolution_time_ms < 1.0:
            return "C"
        elif result.avg_resolution_time_ms < 5.0:
            return "D"
        else:
            return "F"

    def _identify_bottlenecks(
        self,
        result: BenchmarkResult
    ) -> List[str]:
        """Identify performance bottlenecks.

        Args:
            result: Benchmark result to analyze

        Returns:
            List of identified bottlenecks
        """
        bottlenecks = []

        if result.avg_resolution_time_ms > 1.0:
            bottlenecks.append("High average resolution time")

        if result.p99_resolution_time_ms > result.avg_resolution_time_ms * 10:
            bottlenecks.append("High variance in resolution times")

        if result.memory_delta_mb > 100:
            bottlenecks.append("Excessive memory consumption")

        return bottlenecks

    def _generate_recommendations(
        self,
        result: BenchmarkResult
    ) -> List[str]:
        """Generate optimization recommendations.

        Args:
            result: Benchmark result to analyze

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        if result.avg_resolution_time_ms > 0.5:
            recommendations.append(
                "Implement service caching for frequently resolved services"
            )

        if result.memory_delta_mb > 50:
            recommendations.append(
                "Consider lazy initialization for heavy services"
            )

        if result.p99_resolution_time_ms > result.p95_resolution_time_ms * 2:
            recommendations.append(
                "Investigate outlier services causing resolution delays"
            )

        return recommendations