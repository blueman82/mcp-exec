"""
cso_metrics.py

Data models for CSO channel metrics.
"""

from dataclasses import dataclass


@dataclass
class CSOChannelCounts:
    """
    Counts of CSO channels by product type.

    Attributes:
        total: Total number of channels
        campaign: Number of Adobe Campaign channels
        ajo: Number of Adobe Journey Optimizer channels
    """

    total: int
    campaign: int
    ajo: int


@dataclass
class CSOMetrics:
    """
    Complete CSO metrics with active and archived breakdown.

    Attributes:
        currently_active: Channels with archived=false
        archived: Channels with archived=true that had activity in reporting period
    """

    currently_active: CSOChannelCounts
    archived: CSOChannelCounts
