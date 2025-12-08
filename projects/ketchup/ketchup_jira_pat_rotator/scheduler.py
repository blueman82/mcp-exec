#!/usr/bin/env python3
"""PAT rotation scheduler - runs daily rotation check via BaseScheduler."""

import asyncio
from typing import Optional

from packages.core.schedulers import BaseScheduler
from packages.core.typed_di.registry import TypedServiceRegistry


class PatRotationScheduler(BaseScheduler):
    """Scheduler for daily PAT rotation checks (24-hour interval)."""

    def __init__(self, container: Optional[TypedServiceRegistry] = None):
        """
        Initialize PAT rotation scheduler.

        Args:
            container: TypedDI container for dependency resolution.
                      If None, rotator will fall back to direct instantiation.
        """
        super().__init__(
            health_file_prefix="pat_rotator",
            interval_minutes=1440,
            base_path="/tmp",
        )
        self._container = container

    async def run_task(self) -> None:
        """Run PAT rotation check."""
        from ketchup_jira_pat_rotator.rotator import PATRotator

        rotator = PATRotator(container=self._container)
        result = await rotator.rotate()
        self.logger.info(
            f"PAT rotation result: {result.get('status')} - {result.get('action', result.get('newPatId', 'N/A'))}"
        )


async def async_main():
    await PatRotationScheduler().start()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
