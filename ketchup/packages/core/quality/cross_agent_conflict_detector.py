#!/usr/bin/env python3
"""
Quality Validation Framework - Cross-Agent Conflict Detector.

This module provides cross-agent conflict detection for coordinated work
on TypedDI service registrations, preventing resource conflicts and deadlocks.

Author: GUARDIAN-004
Created: 2025-09-22
"""

import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from .code_quality_validator import CodeQualityViolation


class WorkSession:
    """Represents an active work session by an agent."""

    def __init__(self, agent_id: str, session_id: str, files: List[str],
                 start_time: datetime, priority: int = 5):
        """Initialize a work session."""
        self.agent_id = agent_id
        self.session_id = session_id
        self.files = set(files)
        self.start_time = start_time
        self.last_activity = start_time
        self.priority = priority
        self.locked_resources: Set[str] = set()

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if the work session has expired."""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)


class CrossAgentConflictDetector:
    """Detects and prevents conflicts between multiple agents."""

    def __init__(self, lock_file_path: str = None):
        """Initialize the conflict detector."""
        if lock_file_path is None:
            lock_file_path = "/tmp/ketchup_agent_locks.json"
        self.lock_file_path = lock_file_path
        self.active_sessions: Dict[str, WorkSession] = {}
        self.file_locks: Dict[str, str] = {}  # file_path -> session_id
        self.resource_locks: Dict[str, str] = {}  # resource_name -> session_id
        self._lock = threading.Lock()

    def _load_locks_from_file(self) -> Dict:
        """Load existing locks from file system."""
        if not os.path.exists(self.lock_file_path):
            return {"sessions": {}, "file_locks": {}, "resource_locks": {}}

        try:
            with open(self.lock_file_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {"sessions": {}, "file_locks": {}, "resource_locks": {}}

    def _save_locks_to_file(self):
        """Save current locks to file system."""
        try:
            lock_data = {
                "sessions": {
                    session_id: {
                        "agent_id": session.agent_id,
                        "files": list(session.files),
                        "start_time": session.start_time.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                        "priority": session.priority,
                        "locked_resources": list(session.locked_resources)
                    }
                    for session_id, session in self.active_sessions.items()
                },
                "file_locks": self.file_locks,
                "resource_locks": self.resource_locks
            }

            os.makedirs(os.path.dirname(self.lock_file_path), exist_ok=True)
            with open(self.lock_file_path, 'w') as f:
                json.dump(lock_data, f, indent=2)
        except Exception:
            pass  # Fail silently for lock file issues

    def _cleanup_expired_sessions(self):
        """Remove expired work sessions."""
        expired_sessions = [
            session_id for session_id, session in self.active_sessions.items()
            if session.is_expired()
        ]

        for session_id in expired_sessions:
            self._release_session(session_id)

    def register_work_session(self, agent_id: str, session_id: str,
                            files: List[str], priority: int = 5) -> List[CodeQualityViolation]:
        """Register a new work session and check for conflicts."""
        violations = []

        with self._lock:
            self._cleanup_expired_sessions()

            # Check for file conflicts
            conflicting_files = []
            for file_path in files:
                if file_path in self.file_locks:
                    existing_session = self.file_locks[file_path]
                    if existing_session != session_id:
                        conflicting_files.append((file_path, existing_session))

            if conflicting_files:
                for file_path, existing_session in conflicting_files:
                    existing_agent = self.active_sessions.get(existing_session, {})
                    agent_name = getattr(existing_agent, 'agent_id', 'unknown')
                    violations.append(CodeQualityViolation(
                        violation_type="file_conflict",
                        file_path=file_path,
                        line_number=0,
                        message=f"File locked by {agent_name} (session: {existing_session})"
                    ))

            # If no conflicts, register the session
            if not violations:
                session = WorkSession(agent_id, session_id, files, datetime.now(), priority)
                self.active_sessions[session_id] = session

                # Lock files
                for file_path in files:
                    self.file_locks[file_path] = session_id

                self._save_locks_to_file()

        return violations

    def acquire_resource_lock(self, session_id: str, resource_name: str) -> Optional[CodeQualityViolation]:
        """Acquire a lock on a specific resource."""
        with self._lock:
            if resource_name in self.resource_locks:
                existing_session = self.resource_locks[resource_name]
                if existing_session != session_id:
                    existing_agent = self.active_sessions.get(existing_session, {})
                    agent_name = getattr(existing_agent, 'agent_id', 'unknown')
                    return CodeQualityViolation(
                        violation_type="resource_conflict",
                        file_path=resource_name,
                        line_number=0,
                        message=f"Resource locked by {agent_name} (session: {existing_session})"
                    )

            # Acquire the lock
            self.resource_locks[resource_name] = session_id
            if session_id in self.active_sessions:
                self.active_sessions[session_id].locked_resources.add(resource_name)
                self.active_sessions[session_id].update_activity()

            self._save_locks_to_file()
            return None

    def release_resource_lock(self, session_id: str, resource_name: str):
        """Release a lock on a specific resource."""
        with self._lock:
            if resource_name in self.resource_locks and self.resource_locks[resource_name] == session_id:
                del self.resource_locks[resource_name]

            if session_id in self.active_sessions:
                self.active_sessions[session_id].locked_resources.discard(resource_name)
                self.active_sessions[session_id].update_activity()

            self._save_locks_to_file()

    def _release_session(self, session_id: str):
        """Release all locks for a session."""
        if session_id not in self.active_sessions:
            return

        self.active_sessions[session_id]

        # Release file locks
        files_to_release = [
            file_path for file_path, locked_session in self.file_locks.items()
            if locked_session == session_id
        ]
        for file_path in files_to_release:
            del self.file_locks[file_path]

        # Release resource locks
        resources_to_release = [
            resource for resource, locked_session in self.resource_locks.items()
            if locked_session == session_id
        ]
        for resource in resources_to_release:
            del self.resource_locks[resource]

        # Remove session
        del self.active_sessions[session_id]

    def release_work_session(self, session_id: str):
        """Release a work session and all its locks."""
        with self._lock:
            self._release_session(session_id)
            self._save_locks_to_file()

    def detect_deadlocks(self) -> List[CodeQualityViolation]:
        """Detect potential deadlock scenarios."""
        violations = []

        with self._lock:
            # Simple deadlock detection: check for circular dependencies
            waiting_sessions = {}

            for session_id, session in self.active_sessions.items():
                waiting_for = []

                # Check what files this session might be waiting for
                for file_path in session.files:
                    if file_path in self.file_locks and self.file_locks[file_path] != session_id:
                        blocking_session = self.file_locks[file_path]
                        waiting_for.append(blocking_session)

                if waiting_for:
                    waiting_sessions[session_id] = waiting_for

            # Check for circular dependencies
            for session_id, waiting_for in waiting_sessions.items():
                for blocking_session in waiting_for:
                    if blocking_session in waiting_sessions:
                        if session_id in waiting_sessions[blocking_session]:
                            violations.append(CodeQualityViolation(
                                violation_type="deadlock",
                                file_path="system",
                                line_number=0,
                                message=f"Potential deadlock between sessions {session_id} and {blocking_session}"
                            ))

        return violations

    def get_conflict_status(self) -> Dict:
        """Get current conflict status and active sessions."""
        with self._lock:
            self._cleanup_expired_sessions()

            return {
                "active_sessions": len(self.active_sessions),
                "locked_files": len(self.file_locks),
                "locked_resources": len(self.resource_locks),
                "sessions": {
                    session_id: {
                        "agent_id": session.agent_id,
                        "files": list(session.files),
                        "priority": session.priority,
                        "duration_minutes": (datetime.now() - session.start_time).total_seconds() / 60,
                        "locked_resources": list(session.locked_resources)
                    }
                    for session_id, session in self.active_sessions.items()
                }
            }

    def generate_conflict_report(self, violations: List[CodeQualityViolation]) -> str:
        """Generate comprehensive conflict detection report."""
        if not violations:
            status = self.get_conflict_status()
            active_count = status["active_sessions"]
            return f"✅ NO CONFLICTS DETECTED\n🤝 {active_count} active agent session(s) coordinating safely"

        report = ["🚨 CROSS-AGENT CONFLICT DETECTION REPORT"]
        report.append("=" * 45)

        # Categorize violations
        file_conflicts = [v for v in violations if v.violation_type == "file_conflict"]
        resource_conflicts = [v for v in violations if v.violation_type == "resource_conflict"]
        deadlocks = [v for v in violations if v.violation_type == "deadlock"]

        report.append(f"🔒 File Conflicts: {len(file_conflicts)}")
        report.append(f"⚠️  Resource Conflicts: {len(resource_conflicts)}")
        report.append(f"💀 Deadlocks: {len(deadlocks)}")
        report.append("")

        if file_conflicts:
            report.append("📁 FILE CONFLICTS:")
            for violation in file_conflicts:
                report.append(f"  🔒 {violation.file_path}: {violation.message}")
            report.append("")

        if resource_conflicts:
            report.append("🔧 RESOURCE CONFLICTS:")
            for violation in resource_conflicts:
                report.append(f"  ⚠️  {violation.file_path}: {violation.message}")
            report.append("")

        if deadlocks:
            report.append("💀 DEADLOCK DETECTION:")
            for violation in deadlocks:
                report.append(f"  💀 {violation.message}")
            report.append("")

        # Add current status
        status = self.get_conflict_status()
        report.append("📊 CURRENT STATUS:")
        report.append(f"  Active Sessions: {status['active_sessions']}")
        report.append(f"  Locked Files: {status['locked_files']}")
        report.append(f"  Locked Resources: {status['locked_resources']}")

        return "\n".join(report)