"""
Metadata service module for channel metadata extraction and storage.

This module contains the business logic for extracting and storing
channel metadata using AI-powered analysis.
"""

from ketchup_unified_scheduler.services.metadata.channel_processor import ChannelProcessor
from ketchup_unified_scheduler.services.metadata.extractor import MetadataExtractor
from ketchup_unified_scheduler.services.metadata.processor import (
    create_channel_metadata_updater,
    process_channels,
)
from ketchup_unified_scheduler.services.metadata.storage import MetadataStorage
from ketchup_unified_scheduler.services.metadata.updater import ChannelMetadataUpdater

__all__ = [
    "ChannelMetadataUpdater",
    "MetadataExtractor",
    "MetadataStorage",
    "ChannelProcessor",
    "create_channel_metadata_updater",
    "process_channels",
]
