"""Performance monitoring and regression detection for TypedDI.

This module provides real-time monitoring and regression detection
for TypedDI service resolution performance.
"""

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PerformanceBaseline:
    """Performance baseline for regression detection."""

    timestamp: str
    service_count: int
    avg_resolution_ms: float
    p95_resolution_ms: float
    p99_resolution_ms: float
    max_resolution_ms: float
    memory_mb: float
    startup_ms: float
    thresholds: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize default thresholds if not provided."""
        if not self.thresholds:
            self.thresholds = {
                "resolution_regression_pct": 10.0,  # 10% regression
                "memory_regression_pct": 20.0,  # 20% memory increase
                "startup_regression_pct": 15.0,  # 15% startup increase
                "p99_multiplier": 2.0,  # P99 shouldn't exceed 2x avg
            }


@dataclass
class PerformanceMetric:
    """Single performance measurement."""

    service_name: str
    resolution_time_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    memory_delta_kb: float = 0.0
    cache_hit: bool = False


class PerformanceMonitor:
    """Monitor and detect TypedDI performance regressions."""

    def __init__(self, baseline_path: Optional[Path] = None) -> None:
        """Initialize performance monitor.

        Args:
            baseline_path: Path to baseline metrics file
        """
        self.metrics: List[PerformanceMetric] = []
        self.baseline: Optional[PerformanceBaseline] = None
        self.baseline_path = baseline_path or Path("analysis/performance_baseline.json")
        self.regressions_detected: List[Dict[str, Any]] = []

        self.load_baseline()

    def load_baseline(self) -> None:
        """Load performance baseline from file."""
        if self.baseline_path.exists():
            with open(self.baseline_path, "r") as f:
                data = json.load(f)
                self.baseline = PerformanceBaseline(**data)

    def save_baseline(self, baseline: PerformanceBaseline) -> None:
        """Save performance baseline to file.

        Args:
            baseline: Baseline to save
        """
        self.baseline_path.parent.mkdir(exist_ok=True)
        with open(self.baseline_path, "w") as f:
            json.dump(asdict(baseline), f, indent=2)
        self.baseline = baseline

    def record_metric(self, metric: PerformanceMetric) -> None:
        """Record a performance metric.

        Args:
            metric: Performance metric to record
        """
        self.metrics.append(metric)

        # Check for regression if we have enough data
        if len(self.metrics) >= 10:
            self.check_regression()

    def check_regression(self) -> List[Dict[str, Any]]:
        """Check for performance regressions.

        Returns:
            List of detected regressions
        """
        if not self.baseline or not self.metrics:
            return []

        recent_metrics = self.metrics[-100:]  # Last 100 measurements

        # Calculate current performance
        resolution_times = [m.resolution_time_ms for m in recent_metrics]
        current_avg = statistics.mean(resolution_times)
        statistics.quantiles(resolution_times, n=100)[94]
        current_p99 = statistics.quantiles(resolution_times, n=100)[98]

        regressions = []

        # Check average resolution regression
        avg_regression_pct = (
            (current_avg - self.baseline.avg_resolution_ms) / self.baseline.avg_resolution_ms * 100
        )

        if avg_regression_pct > self.baseline.thresholds["resolution_regression_pct"]:
            regressions.append(
                {
                    "type": "resolution_time",
                    "severity": "HIGH" if avg_regression_pct > 25 else "MEDIUM",
                    "baseline": self.baseline.avg_resolution_ms,
                    "current": current_avg,
                    "regression_pct": avg_regression_pct,
                    "message": f"Resolution time regressed by {avg_regression_pct:.1f}%",
                }
            )

        # Check P99 regression
        if current_p99 > self.baseline.p99_resolution_ms * 1.5:
            regressions.append(
                {
                    "type": "p99_latency",
                    "severity": "HIGH",
                    "baseline": self.baseline.p99_resolution_ms,
                    "current": current_p99,
                    "message": f"P99 latency degraded: {current_p99:.2f}ms",
                }
            )

        self.regressions_detected = regressions
        return regressions

    def generate_monitoring_report(self) -> Dict[str, Any]:
        """Generate comprehensive monitoring report.

        Returns:
            Monitoring report with current metrics and health status
        """
        if not self.metrics:
            return {"status": "NO_DATA", "message": "No metrics collected"}

        recent = self.metrics[-100:]
        resolution_times = [m.resolution_time_ms for m in recent]

        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics_collected": len(self.metrics),
            "current_performance": {
                "avg_resolution_ms": statistics.mean(resolution_times),
                "median_resolution_ms": statistics.median(resolution_times),
                "p95_resolution_ms": (
                    statistics.quantiles(resolution_times, n=100)[94]
                    if len(resolution_times) > 1
                    else resolution_times[0]
                ),
                "p99_resolution_ms": (
                    statistics.quantiles(resolution_times, n=100)[98]
                    if len(resolution_times) > 1
                    else resolution_times[0]
                ),
                "max_resolution_ms": max(resolution_times),
                "min_resolution_ms": min(resolution_times),
            },
            "health_status": self._calculate_health_status(resolution_times),
            "regressions_detected": len(self.regressions_detected),
            "regression_details": self.regressions_detected,
        }

        if self.baseline:
            report["baseline_comparison"] = {
                "baseline_service_count": self.baseline.service_count,
                "baseline_avg_ms": self.baseline.avg_resolution_ms,
                "performance_delta_pct": (
                    (
                        report["current_performance"]["avg_resolution_ms"]
                        - self.baseline.avg_resolution_ms
                    )
                    / self.baseline.avg_resolution_ms
                    * 100
                ),
            }

        return report

    def _calculate_health_status(self, resolution_times: List[float]) -> str:
        """Calculate overall health status.

        Args:
            resolution_times: Recent resolution times

        Returns:
            Health status (HEALTHY, WARNING, CRITICAL)
        """
        avg_time = statistics.mean(resolution_times)

        if avg_time < 0.5:
            return "HEALTHY"
        elif avg_time < 1.0:
            return "WARNING"
        else:
            return "CRITICAL"

    def create_baseline_from_current(self, service_count: int) -> PerformanceBaseline:
        """Create baseline from current metrics.

        Args:
            service_count: Number of services

        Returns:
            New performance baseline
        """
        if not self.metrics:
            raise ValueError("No metrics available to create baseline")

        resolution_times = [m.resolution_time_ms for m in self.metrics]
        memory_deltas = [m.memory_delta_kb for m in self.metrics]

        baseline = PerformanceBaseline(
            timestamp=datetime.now().isoformat(),
            service_count=service_count,
            avg_resolution_ms=statistics.mean(resolution_times),
            p95_resolution_ms=statistics.quantiles(resolution_times, n=100)[94],
            p99_resolution_ms=statistics.quantiles(resolution_times, n=100)[98],
            max_resolution_ms=max(resolution_times),
            memory_mb=sum(memory_deltas) / 1024,
            startup_ms=sum(resolution_times[:service_count]),
        )

        self.save_baseline(baseline)
        return baseline


class RegressionDetector:
    """Detect performance regressions in service additions."""

    def __init__(self) -> None:
        """Initialize regression detector."""
        self.service_benchmarks: Dict[str, List[float]] = {}
        self.batch_performance: List[Tuple[int, float]] = []

    def benchmark_service_batch(self, services: List[str], container: Any) -> Dict[str, Any]:
        """Benchmark a batch of services.

        Args:
            services: List of service names
            container: TypedDI container

        Returns:
            Batch benchmark results
        """
        batch_start = time.perf_counter()
        results = {}

        for service in services:
            times = []
            for _ in range(10):  # 10 iterations per service
                start = time.perf_counter()
                try:
                    container.resolve(service)
                except Exception:
                    pass
                times.append((time.perf_counter() - start) * 1000)

            avg_time = statistics.mean(times)
            results[service] = avg_time

            # Track for regression detection
            if service not in self.service_benchmarks:
                self.service_benchmarks[service] = []
            self.service_benchmarks[service].append(avg_time)

        batch_time = (time.perf_counter() - batch_start) * 1000
        self.batch_performance.append((len(services), batch_time))

        return {
            "batch_size": len(services),
            "total_time_ms": batch_time,
            "avg_per_service_ms": batch_time / len(services),
            "service_results": results,
            "regression_detected": self._detect_batch_regression(),
        }

    def _detect_batch_regression(self) -> bool:
        """Detect if latest batch shows regression.

        Returns:
            True if regression detected
        """
        if len(self.batch_performance) < 2:
            return False

        # Compare latest batch to previous
        prev_size, prev_time = self.batch_performance[-2]
        curr_size, curr_time = self.batch_performance[-1]

        # Normalize by batch size
        prev_avg = prev_time / prev_size
        curr_avg = curr_time / curr_size

        # Regression if >20% slower per service
        return curr_avg > prev_avg * 1.2
