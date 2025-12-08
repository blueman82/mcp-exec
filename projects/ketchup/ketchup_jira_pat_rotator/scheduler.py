#!/usr/bin/env python3
"""PAT rotation scheduler - runs daily rotation check via BaseScheduler."""

import asyncio

from packages.core.schedulers import BaseScheduler


class PatRotationScheduler(BaseScheduler):
    """Scheduler for daily PAT rotation checks (24-hour interval)."""

    def __init__(self):
        super().__init__(
            health_file_prefix="pat_rotator",
            interval_minutes=1440,
            base_path="/tmp",
        )

    async def run_task(self) -> None:
        """Run PAT rotation check."""
        from ketchup_jira_pat_rotator.rotator import PATRotator

        rotator = PATRotator()
        result = await rotator.rotate()
        self.logger.info(f"PAT rotation result: {result.get('status')} - {result.get('action', result.get('newPatId', 'N/A'))}")


async def async_main():
    await PatRotationScheduler().start()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
