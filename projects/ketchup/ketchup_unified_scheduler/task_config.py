"""
TaskConfig dataclass for unified scheduler task configuration.

Supports both interval-based scheduling (every N minutes) and time-based
scheduling (daily at HH:MM UTC).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional


@dataclass
class TaskConfig:
    """
    Configuration for a scheduled task.

    Supports two scheduling modes:
    1. Interval-based: Set interval_minutes for recurring tasks (e.g., every 15 minutes)
    2. Time-based: Set schedule_time for daily tasks at specific time (e.g., "01:30" UTC)

    Attributes:
        name: Unique identifier for the task (e.g., "metadata_updater")
        handler: Async callable that executes the task. Must be an async function.
        interval_minutes: Minutes between runs for interval-based scheduling.
                         Mutually exclusive with schedule_time.
        schedule_time: Time of day to run (HH:MM format, UTC) for time-based scheduling.
                      Mutually exclusive with interval_minutes.
        feature_flag: Environment variable name to check for enabling/disabling.
                     If set, task only runs when os.getenv(feature_flag) == 'true'.
        enabled: Static enable/disable flag. Defaults to True.
                Combined with feature_flag check at runtime.

    Example:
        # Interval-based task running every 15 minutes
        TaskConfig(
            name="metadata_updater",
            handler=update_metadata,
            interval_minutes=15,
            feature_flag="KETCHUP_METADATA_UPDATER_FEATURE"
        )

        # Time-based task running daily at 1:30 AM UTC
        TaskConfig(
            name="maintenance_fetcher",
            handler=fetch_maintenance,
            schedule_time="01:30",
            feature_flag="KETCHUP_MAINTENANCE_FETCHER_FEATURE"
        )
    """

    name: str
    handler: Callable[[], Coroutine[Any, Any, None]]
    interval_minutes: Optional[int] = None
    schedule_time: Optional[str] = None
    feature_flag: Optional[str] = None
    enabled: bool = field(default=True)

    def __post_init__(self):
        """Validate task configuration after initialization."""
        # Validate scheduling mode
        if self.interval_minutes is None and self.schedule_time is None:
            raise ValueError(
                f"Task '{self.name}' must specify either interval_minutes or schedule_time"
            )

        if self.interval_minutes is not None and self.schedule_time is not None:
            raise ValueError(
                f"Task '{self.name}' cannot have both interval_minutes and schedule_time"
            )

        # Validate interval
        if self.interval_minutes is not None and self.interval_minutes <= 0:
            raise ValueError(f"Task '{self.name}' interval_minutes must be positive")

        # Validate schedule_time format (HH:MM)
        if self.schedule_time is not None:
            try:
                parts = self.schedule_time.split(":")
                if len(parts) != 2:
                    raise ValueError("Invalid format")
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time values")
            except (ValueError, AttributeError):
                raise ValueError(
                    f"Task '{self.name}' schedule_time must be in HH:MM format (e.g., '01:30')"
                )

    @property
    def is_interval_based(self) -> bool:
        """Check if this task uses interval-based scheduling."""
        return self.interval_minutes is not None

    @property
    def is_time_based(self) -> bool:
        """Check if this task uses time-based scheduling."""
        return self.schedule_time is not None
