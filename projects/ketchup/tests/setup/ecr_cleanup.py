#!/usr/bin/env python3
"""
ECR Image Cleanup Script
========================

CRITICAL: This script deletes ECR images older than v2.360.16
PRESERVES: v2.360.16 and any newer versions

Usage:
    python ecr_cleanup.py --dry-run    # Test mode - no deletions
    python ecr_cleanup.py              # Actual cleanup
"""

import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError


@dataclass
class ImageInfo:
    """Container for ECR image information"""

    repository_name: str
    image_digest: str
    image_tags: List[str]
    image_pushed_at: datetime
    image_size_in_bytes: int


@dataclass
class CleanupMetrics:
    """Metrics for cleanup operation"""

    total_repositories: int = 0
    total_images_scanned: int = 0
    images_to_delete: int = 0
    images_preserved: int = 0
    images_deleted: int = 0
    deletion_failures: int = 0
    bytes_to_delete: int = 0
    bytes_deleted: int = 0
    repositories_with_deletions: List[str] = None

    def __post_init__(self):
        if self.repositories_with_deletions is None:
            self.repositories_with_deletions = []


class VersionComparator:
    """Aggressive version comparison for ECR image cleanup"""

    # Target version: v2.360.16
    TARGET_MAJOR = 2
    TARGET_MINOR = 360
    TARGET_PATCH = 16

    # Services that are currently deployed and should be preserved at v2.360.16+
    PROTECTED_SERVICES = {
        "ketchup-app",
        "ketchup-metadata-updater",
        "mcp-jira",
        "ketchup-status-updater",
        "ketchup-jira-reporter",
        "ketchup-access-monitor",
    }

    @staticmethod
    def parse_version(tag: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse version string into tuple of (major, minor, patch)
        Handles various formats aggressively but safely
        """
        # Standard vX.Y.Z pattern
        patterns = [
            r"^v(\d+)\.(\d+)\.(\d+)$",  # v2.360.16
            r"^(\d+)\.(\d+)\.(\d+)$",  # 2.360.16 (without v)
        ]

        for pattern in patterns:
            match = re.match(pattern, tag)
            if match:
                try:
                    major = int(match.group(1))
                    minor = int(match.group(2))
                    patch = int(match.group(3))
                    return (major, minor, patch)
                except ValueError:
                    continue

        return None

    @classmethod
    def should_preserve_image(cls, repository_name: str, tag: str) -> bool:
        """
        Determine if image should be preserved

        PRESERVE ONLY if:
        - Repository is in PROTECTED_SERVICES AND tag is exactly v2.360.16

        DELETE everything else including:
        - All non-protected services (entire repositories)
        - All versions != v2.360.16 in protected services
        - All non-standard tags (latest, date-based, etc.)
        """
        # If repository is not in protected services, delete everything
        if repository_name not in cls.PROTECTED_SERVICES:
            return False

        # For protected services, only preserve exactly v2.360.16
        version = cls.parse_version(tag)
        if version is None:
            # Non-standard format - delete it
            return False

        major, minor, patch = version
        target = (cls.TARGET_MAJOR, cls.TARGET_MINOR, cls.TARGET_PATCH)

        # Only preserve if version is exactly the target
        return version == target


class ECRCleanup:
    """ECR image cleanup orchestrator"""

    def __init__(self, region: str = "eu-west-1", dry_run: bool = True):
        self.region = region
        self.dry_run = dry_run
        self.ecr_client = boto3.client("ecr", region_name=region)
        self.metrics = CleanupMetrics()

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Configure comprehensive logging"""
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'ecr_cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            ],
        )
        self.logger = logging.getLogger(__name__)

        mode = "DRY RUN" if self.dry_run else "LIVE DELETION"
        self.logger.warning(f"ECR Cleanup started in {mode} mode")
        self.logger.warning(
            f"Target: Delete images older than v{VersionComparator.TARGET_MAJOR}.{VersionComparator.TARGET_MINOR}.{VersionComparator.TARGET_PATCH}"
        )

    def get_repositories(self) -> List[str]:
        """Get all ECR repository names"""
        try:
            response = self.ecr_client.describe_repositories()
            repos = [repo["repositoryName"] for repo in response["repositories"]]
            self.metrics.total_repositories = len(repos)
            self.logger.info(f"Found {len(repos)} ECR repositories")
            return repos
        except ClientError as e:
            self.logger.error(f"Failed to list repositories: {e}")
            raise

    def get_repository_images(self, repository_name: str) -> List[ImageInfo]:
        """Get all images from a repository"""
        images = []
        paginator = self.ecr_client.get_paginator("describe_images")

        try:
            for page in paginator.paginate(repositoryName=repository_name):
                for image_detail in page["imageDetails"]:
                    # Handle images without tags (should be rare)
                    tags = image_detail.get("imageTags", [])
                    if not tags:
                        tags = ["<untagged>"]

                    image_info = ImageInfo(
                        repository_name=repository_name,
                        image_digest=image_detail["imageDigest"],
                        image_tags=tags,
                        image_pushed_at=image_detail["imagePushedAt"],
                        image_size_in_bytes=image_detail["imageSizeInBytes"],
                    )
                    images.append(image_info)

            self.logger.info(f"Repository {repository_name}: {len(images)} images")
            return images

        except ClientError as e:
            self.logger.error(f"Failed to get images for {repository_name}: {e}")
            return []

    def analyze_image_for_deletion(self, image: ImageInfo) -> bool:
        """
        Determine if image should be deleted

        AGGRESSIVE CLEANUP LOGIC:
        - DELETE if repository is not in protected services
        - DELETE if ANY tag is < v2.360.16
        - DELETE all non-standard tags (latest, date-based, etc.)
        - PRESERVE only if ALL tags are >= v2.360.16 in protected services
        """
        # Check if ANY tag should be preserved
        should_preserve = False

        for tag in image.image_tags:
            if VersionComparator.should_preserve_image(image.repository_name, tag):
                should_preserve = True
                self.logger.info(
                    f"Preserving {image.repository_name}:{tag} - meets preservation criteria"
                )
                break
            else:
                self.logger.debug(f"Tag {image.repository_name}:{tag} - marked for deletion")

        if should_preserve:
            # Check if image has mixed tags (some good, some bad) and log warnings
            for tag in image.image_tags:
                if not VersionComparator.should_preserve_image(image.repository_name, tag):
                    self.logger.warning(
                        f"Image {image.repository_name} has mixed tags - preserving due to good tag but noting bad tag: {tag}"
                    )

            return False  # Preserve the image

        # No preservable tags found - delete the image
        self.logger.info(
            f"Marking for deletion {image.repository_name}:{image.image_tags} - no preservation criteria met"
        )
        return True

    def delete_image(self, image: ImageInfo) -> bool:
        """Delete a single image"""
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would delete {image.repository_name}:{image.image_tags}")
            return True

        try:
            self.ecr_client.batch_delete_image(
                repositoryName=image.repository_name,
                imageIds=[{"imageDigest": image.image_digest}],
            )
            self.logger.info(f"DELETED: {image.repository_name}:{image.image_tags}")
            return True

        except ClientError as e:
            self.logger.error(f"Failed to delete {image.repository_name}:{image.image_tags}: {e}")
            return False

    def cleanup_repository(self, repository_name: str):
        """Clean up a single repository"""
        self.logger.info(f"Processing repository: {repository_name}")

        images = self.get_repository_images(repository_name)
        if not images:
            return

        self.metrics.total_images_scanned += len(images)

        images_to_delete = []
        for image in images:
            if self.analyze_image_for_deletion(image):
                images_to_delete.append(image)
                self.metrics.images_to_delete += 1
                self.metrics.bytes_to_delete += image.image_size_in_bytes
            else:
                self.metrics.images_preserved += 1

        if images_to_delete:
            self.metrics.repositories_with_deletions.append(repository_name)
            self.logger.warning(
                f"Repository {repository_name}: {len(images_to_delete)} images marked for deletion"
            )

            for image in images_to_delete:
                if self.delete_image(image):
                    self.metrics.images_deleted += 1
                    self.metrics.bytes_deleted += image.image_size_in_bytes
                else:
                    self.metrics.deletion_failures += 1
        else:
            self.logger.info(f"Repository {repository_name}: No images to delete")

    def run_cleanup(self):
        """Execute the complete cleanup process"""
        start_time = time.time()

        try:
            repositories = self.get_repositories()

            for repo in repositories:
                self.cleanup_repository(repo)
                # Small delay to avoid rate limiting
                time.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            raise

        finally:
            duration = time.time() - start_time
            self.log_final_metrics(duration)

    def log_final_metrics(self, duration: float):
        """Log comprehensive cleanup metrics"""
        self.logger.warning("=" * 60)
        self.logger.warning("ECR CLEANUP COMPLETED")
        self.logger.warning("=" * 60)

        mode = "DRY RUN" if self.dry_run else "LIVE DELETION"
        self.logger.warning(f"Mode: {mode}")
        self.logger.warning(f"Duration: {duration:.2f} seconds")
        self.logger.warning(f"Repositories processed: {self.metrics.total_repositories}")
        self.logger.warning(f"Total images scanned: {self.metrics.total_images_scanned}")
        self.logger.warning(f"Images preserved: {self.metrics.images_preserved}")
        self.logger.warning(f"Images marked for deletion: {self.metrics.images_to_delete}")

        if not self.dry_run:
            self.logger.warning(f"Images successfully deleted: {self.metrics.images_deleted}")
            self.logger.warning(f"Deletion failures: {self.metrics.deletion_failures}")
            self.logger.warning(f"Bytes deleted: {self.metrics.bytes_deleted:,}")
        else:
            self.logger.warning(f"Bytes that would be deleted: {self.metrics.bytes_to_delete:,}")

        self.logger.warning(
            f"Repositories with deletions: {len(self.metrics.repositories_with_deletions)}"
        )
        for repo in self.metrics.repositories_with_deletions:
            self.logger.warning(f"  - {repo}")

        # Save metrics to JSON file
        metrics_file = f'ecr_cleanup_metrics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(metrics_file, "w") as f:
            json.dump(
                {
                    "mode": mode,
                    "duration_seconds": duration,
                    "total_repositories": self.metrics.total_repositories,
                    "total_images_scanned": self.metrics.total_images_scanned,
                    "images_preserved": self.metrics.images_preserved,
                    "images_to_delete": self.metrics.images_to_delete,
                    "images_deleted": self.metrics.images_deleted,
                    "deletion_failures": self.metrics.deletion_failures,
                    "bytes_to_delete": self.metrics.bytes_to_delete,
                    "bytes_deleted": self.metrics.bytes_deleted,
                    "repositories_with_deletions": self.metrics.repositories_with_deletions,
                    "timestamp": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        self.logger.warning(f"Metrics saved to: {metrics_file}")


def main():
    """Main entry point"""
    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    if not dry_run:
        print("\n" + "=" * 60)
        print("WARNING: LIVE DELETION MODE")
        print("This will permanently delete ECR images!")
        print("Target: Delete images older than v2.360.16")
        print("=" * 60)

        confirmation = input("\nType 'DELETE_OLD_IMAGES' to confirm: ")
        if confirmation != "DELETE_OLD_IMAGES":
            print("Operation cancelled.")
            return

    # Run cleanup
    cleanup = ECRCleanup(dry_run=dry_run)
    cleanup.run_cleanup()


if __name__ == "__main__":
    main()
