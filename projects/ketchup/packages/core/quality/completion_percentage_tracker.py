#!/usr/bin/env python3
"""
Quality Validation Framework - Completion Percentage Tracker.

This module provides real-time progress tracking for the 271-service TypedDI
completion initiative, with milestone tracking and progress analytics.

Author: GUARDIAN-004
Created: 2025-09-22
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .code_quality_validator import CodeQualityViolation


class ServiceRegistrationEntry:
    """Represents a single service registration entry."""

    def __init__(
        self,
        service_name: str,
        file_path: str,
        line_number: int,
        registration_type: str,
        status: str = "pending",
    ):
        """Initialize a service registration entry."""
        self.service_name = service_name
        self.file_path = file_path
        self.line_number = line_number
        self.registration_type = registration_type
        self.status = status  # pending, migrated, validated, completed
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "service_name": self.service_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "registration_type": self.registration_type,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
        }


class Milestone:
    """Represents a completion milestone."""

    def __init__(self, name: str, target_percentage: float, target_date: datetime = None):
        """Initialize a milestone."""
        self.name = name
        self.target_percentage = target_percentage
        self.target_date = target_date
        self.achieved = False
        self.achieved_date: Optional[datetime] = None

    def check_achievement(self, current_percentage: float) -> bool:
        """Check if milestone has been achieved."""
        if not self.achieved and current_percentage >= self.target_percentage:
            self.achieved = True
            self.achieved_date = datetime.now()
            return True
        return False


class CompletionPercentageTracker:
    """Tracks completion percentage for 271-service goal."""

    def __init__(self, progress_file_path: str = None):
        """Initialize the completion tracker."""
        if progress_file_path is None:
            progress_file_path = "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup/typed_di_progress.json"
        self.progress_file_path = progress_file_path
        self.target_service_count = 271
        self.services: Dict[str, ServiceRegistrationEntry] = {}
        self.milestones = self._initialize_milestones()
        self._load_progress()

    def _initialize_milestones(self) -> List[Milestone]:
        """Initialize completion milestones."""
        return [
            Milestone("Initial Migration", 25.0),
            Milestone("Quarter Complete", 25.0),
            Milestone("Half Complete", 50.0),
            Milestone("Three Quarters", 75.0),
            Milestone("Near Complete", 90.0),
            Milestone("Full Complete", 100.0),
        ]

    def _load_progress(self):
        """Load progress from file if it exists."""
        if os.path.exists(self.progress_file_path):
            try:
                with open(self.progress_file_path, "r") as f:
                    data = json.load(f)

                # Load services
                for service_data in data.get("services", []):
                    service = ServiceRegistrationEntry(
                        service_data["service_name"],
                        service_data["file_path"],
                        service_data["line_number"],
                        service_data["registration_type"],
                        service_data["status"],
                    )
                    service.timestamp = datetime.fromisoformat(service_data["timestamp"])
                    self.services[service.service_name] = service

                # Load milestones
                for i, milestone_data in enumerate(data.get("milestones", [])):
                    if i < len(self.milestones):
                        self.milestones[i].achieved = milestone_data.get("achieved", False)
                        if milestone_data.get("achieved_date"):
                            self.milestones[i].achieved_date = datetime.fromisoformat(
                                milestone_data["achieved_date"]
                            )

            except Exception:
                pass  # Start fresh if file is corrupted

    def _save_progress(self):
        """Save current progress to file."""
        try:
            data = {
                "target_service_count": self.target_service_count,
                "last_updated": datetime.now().isoformat(),
                "services": [service.to_dict() for service in self.services.values()],
                "milestones": [
                    {
                        "name": milestone.name,
                        "target_percentage": milestone.target_percentage,
                        "achieved": milestone.achieved,
                        "achieved_date": (
                            milestone.achieved_date.isoformat() if milestone.achieved_date else None
                        ),
                    }
                    for milestone in self.milestones
                ],
            }

            os.makedirs(os.path.dirname(self.progress_file_path), exist_ok=True)
            with open(self.progress_file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Fail silently for save issues

    def scan_for_service_registrations(self, base_path: str) -> List[CodeQualityViolation]:
        """Scan codebase for service registrations and update tracking."""
        violations = []
        found_services = {}

        # Search patterns for different registration types
        patterns = {
            "typed_di_register": r"@register\s*\(\s*([^)]+)\s*\)",
            "container_register": r"container\.register\s*\(\s*([^)]+)\s*\)",
            "di_container": r"DI\.register\s*\(\s*([^)]+)\s*\)",
            "service_decorator": r"@service\s*\(\s*([^)]+)\s*\)",
        }

        # Scan TypedDI related files
        search_paths = [
            "packages/core/typed_di/",
            "packages/core/di_container.py",
            "packages/*/",
        ]

        for search_path in search_paths:
            full_path = os.path.join(base_path, search_path)
            if os.path.exists(full_path):
                self._scan_directory(full_path, patterns, found_services)

        # Update services tracking
        for service_name, (file_path, line_number, reg_type) in found_services.items():
            if service_name not in self.services:
                # New service found
                self.services[service_name] = ServiceRegistrationEntry(
                    service_name, file_path, line_number, reg_type, "pending"
                )
            else:
                # Update existing service
                self.services[service_name].file_path = file_path
                self.services[service_name].line_number = line_number
                self.services[service_name].registration_type = reg_type

        # Check for removed services
        current_service_names = set(found_services.keys())
        tracked_service_names = set(self.services.keys())
        removed_services = tracked_service_names - current_service_names

        for service_name in removed_services:
            del self.services[service_name]

        self._save_progress()
        return violations

    def _scan_directory(
        self,
        directory_path: str,
        patterns: Dict[str, str],
        found_services: Dict[str, Tuple[str, int, str]],
    ):
        """Scan a directory for service registrations."""
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    self._scan_file(file_path, patterns, found_services)

    def _scan_file(
        self,
        file_path: str,
        patterns: Dict[str, str],
        found_services: Dict[str, Tuple[str, int, str]],
    ):
        """Scan a single file for service registrations."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line_no, line in enumerate(lines, 1):
                for reg_type, pattern in patterns.items():
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        # Extract service name from the registration
                        service_name = self._extract_service_name(match.group(1))
                        if service_name:
                            found_services[service_name] = (file_path, line_no, reg_type)

        except Exception:
            pass  # Skip files that can't be read

    def _extract_service_name(self, registration_content: str) -> Optional[str]:
        """Extract service name from registration content."""
        # Simple extraction - look for class names or string literals
        # This can be enhanced based on actual registration patterns
        clean_content = registration_content.strip().strip("\"'")

        # Look for class references
        class_match = re.search(r"\b([A-Z][a-zA-Z0-9_]*)\b", clean_content)
        if class_match:
            return class_match.group(1)

        # Look for string literals
        string_match = re.search(r'["\']([^"\']+)["\']', clean_content)
        if string_match:
            return string_match.group(1)

        return None

    def update_service_status(
        self, service_name: str, status: str
    ) -> Optional[CodeQualityViolation]:
        """Update the status of a specific service."""
        if service_name not in self.services:
            return CodeQualityViolation(
                violation_type="tracking_error",
                file_path="tracker",
                line_number=0,
                message=f"Service '{service_name}' not found in tracking",
            )

        valid_statuses = ["pending", "migrated", "validated", "completed"]
        if status not in valid_statuses:
            return CodeQualityViolation(
                violation_type="tracking_error",
                file_path="tracker",
                line_number=0,
                message=f"Invalid status '{status}'. Valid: {', '.join(valid_statuses)}",
            )

        self.services[service_name].status = status
        self.services[service_name].timestamp = datetime.now()
        self._save_progress()
        return None

    def calculate_completion_percentage(self) -> Dict[str, float]:
        """Calculate completion percentages by status."""
        total_services = len(self.services)
        if total_services == 0:
            return {
                "overall": 0.0,
                "migrated": 0.0,
                "validated": 0.0,
                "completed": 0.0,
                "target_percentage": 0.0,
            }

        status_counts = {}
        for service in self.services.values():
            status_counts[service.status] = status_counts.get(service.status, 0) + 1

        migrated = status_counts.get("migrated", 0)
        validated = status_counts.get("validated", 0)
        completed = status_counts.get("completed", 0)

        # Overall completion is services that are at least migrated
        overall_complete = migrated + validated + completed

        return {
            "overall": (overall_complete / total_services) * 100,
            "migrated": (migrated / total_services) * 100,
            "validated": (validated / total_services) * 100,
            "completed": (completed / total_services) * 100,
            "target_percentage": (total_services / self.target_service_count) * 100,
            "total_found": total_services,
            "target_total": self.target_service_count,
        }

    def check_milestones(self) -> List[str]:
        """Check and update milestone achievements."""
        percentages = self.calculate_completion_percentage()
        current_percentage = percentages["overall"]

        achieved_milestones = []
        for milestone in self.milestones:
            if milestone.check_achievement(current_percentage):
                achieved_milestones.append(milestone.name)

        if achieved_milestones:
            self._save_progress()

        return achieved_milestones

    def generate_progress_report(self) -> str:
        """Generate comprehensive progress report."""
        percentages = self.calculate_completion_percentage()
        achieved_milestones = self.check_milestones()

        report = ["📊 TYPED DI COMPLETION PROGRESS REPORT"]
        report.append("=" * 45)
        report.append("")

        # Overall progress
        overall = percentages["overall"]
        target = percentages["target_percentage"]
        report.append(f"🎯 OVERALL PROGRESS: {overall:.1f}%")
        report.append(
            f"📈 Target Discovery: {target:.1f}% ({percentages['total_found']}/{percentages['target_total']} services)"
        )
        report.append("")

        # Status breakdown
        report.append("📋 STATUS BREAKDOWN:")
        report.append(f"  🔄 Migrated: {percentages['migrated']:.1f}%")
        report.append(f"  ✅ Validated: {percentages['validated']:.1f}%")
        report.append(f"  🏆 Completed: {percentages['completed']:.1f}%")
        report.append("")

        # Milestones
        report.append("🏁 MILESTONES:")
        for milestone in self.milestones:
            status = "✅" if milestone.achieved else "⏳"
            achieved_text = (
                f" (achieved {milestone.achieved_date.strftime('%Y-%m-%d')})"
                if milestone.achieved
                else ""
            )
            report.append(
                f"  {status} {milestone.name}: {milestone.target_percentage}%{achieved_text}"
            )

        if achieved_milestones:
            report.append("")
            report.append("🎉 NEWLY ACHIEVED MILESTONES:")
            for milestone_name in achieved_milestones:
                report.append(f"  🎊 {milestone_name}")

        # Progress velocity
        if len(self.services) > 0:
            recent_services = [
                s
                for s in self.services.values()
                if s.timestamp > datetime.now() - timedelta(days=7)
            ]
            if recent_services:
                report.append("")
                report.append(f"⚡ WEEKLY VELOCITY: {len(recent_services)} services updated")

        return "\n".join(report)
