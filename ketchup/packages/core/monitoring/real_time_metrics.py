"""
Real-Time Production Metrics

Data structures for real-time production monitoring.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class RealTimeMetrics:
    """Real-time production metrics snapshot."""

    timestamp: str
    service_resolution_avg_ms: float
    service_resolution_p99_ms: float
    active_services: int
    memory_usage_mb: float
    cpu_utilization_percent: float
    error_rate: float
    success_rate: float
    health_status: str
    predictive_alerts: List[str]
    optimization_recommendations: List[str]