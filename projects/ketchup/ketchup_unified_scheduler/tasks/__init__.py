"""
Tasks module for the unified scheduler.

Contains individual task implementations that can be registered with the TaskRegistry.
"""

from ketchup_unified_scheduler.tasks.jira_report_task import (
    get_jira_report_task_config,
    jira_report_task,
)
from ketchup_unified_scheduler.tasks.maintenance_fetch_task import (
    get_maintenance_fetch_task_config,
    maintenance_fetch_task,
)
from ketchup_unified_scheduler.tasks.metadata_update_task import (
    get_metadata_update_task_config,
    metadata_update_task,
)
from ketchup_unified_scheduler.tasks.pat_rotation_task import (
    get_pat_rotation_task_config,
    pat_rotation_task,
)
from ketchup_unified_scheduler.tasks.status_update_task import (
    get_status_update_task_config,
    status_update_task,
)

__all__ = [
    # Maintenance fetch task
    "maintenance_fetch_task",
    "get_maintenance_fetch_task_config",
    # PAT rotation task
    "pat_rotation_task",
    "get_pat_rotation_task_config",
    # Metadata update task
    "metadata_update_task",
    "get_metadata_update_task_config",
    # Status update task
    "status_update_task",
    "get_status_update_task_config",
    # JIRA report task
    "jira_report_task",
    "get_jira_report_task_config",
]
