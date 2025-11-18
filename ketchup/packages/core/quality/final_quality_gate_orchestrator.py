#!/usr/bin/env python3
"""
Quality Validation Framework - Final Quality Gate Orchestrator.

This module orchestrates all quality validators into a unified pipeline for
comprehensive TypedDI service registration validation and deployment readiness.

Author: GUARDIAN-004
Created: 2025-09-22
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict, List

from .code_quality_validator import CodeQualityValidator, CodeQualityViolation
from .completion_percentage_tracker import CompletionPercentageTracker
from .cross_agent_conflict_detector import CrossAgentConflictDetector
from .docstring_validator import DocstringValidator
from .import_order_validator import ImportOrderValidator
from .production_readiness_validator import ProductionReadinessValidator
from .rollback_safety_validator import RollbackSafetyValidator
from .security_validator import SecurityValidator


class QualityGateResult:
    """Represents the result of a quality gate check."""

    def __init__(self, gate_name: str, passed: bool, violations: List[CodeQualityViolation],
                 execution_time_ms: float, severity_counts: Dict[str, int]):
        """Initialize a quality gate result."""
        self.gate_name = gate_name
        self.passed = passed
        self.violations = violations
        self.execution_time_ms = execution_time_ms
        self.severity_counts = severity_counts
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "gate_name": self.gate_name,
            "passed": self.passed,
            "violation_count": len(self.violations),
            "execution_time_ms": self.execution_time_ms,
            "severity_counts": self.severity_counts,
            "timestamp": self.timestamp.isoformat()
        }


class FinalQualityGateOrchestrator:
    """Orchestrates all quality validators in a unified pipeline."""

    def __init__(self, base_path: str = None, session_id: str = None):
        """Initialize the quality gate orchestrator."""
        if base_path is None:
            base_path = "/Users/harrison/Documents/Github/camp-ops-tools-emea/ketchup"
        self.base_path = base_path
        self.session_id = session_id or f"guardian-{int(time.time())}"

        # Initialize all validators
        self.code_quality_validator = CodeQualityValidator()
        self.security_validator = SecurityValidator()
        self.docstring_validator = DocstringValidator()
        self.import_order_validator = ImportOrderValidator()
        self.production_readiness_validator = ProductionReadinessValidator()
        self.rollback_safety_validator = RollbackSafetyValidator()
        self.completion_tracker = CompletionPercentageTracker()
        self.conflict_detector = CrossAgentConflictDetector()

        # Quality gate configuration
        self.quality_gates = {
            "code_quality": {"validator": self.code_quality_validator, "critical": True},
            "security": {"validator": self.security_validator, "critical": True},
            "docstrings": {"validator": self.docstring_validator, "critical": False},
            "import_order": {"validator": self.import_order_validator, "critical": False},
            "production_readiness": {"validator": self.production_readiness_validator, "critical": True},
            "rollback_safety": {"validator": self.rollback_safety_validator, "critical": True},
            "completion_tracking": {"validator": self.completion_tracker, "critical": False},
            "conflict_detection": {"validator": self.conflict_detector, "critical": False}
        }

        self.results: Dict[str, QualityGateResult] = {}

    def _count_violation_severities(self, violations: List[CodeQualityViolation]) -> Dict[str, int]:
        """Count violations by severity."""
        counts = {"error": 0, "warning": 0}
        for violation in violations:
            severity = getattr(violation, 'severity', 'error')
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    async def _run_code_quality_gate(self) -> QualityGateResult:
        """Run code quality validation gate."""
        start_time = time.time()
        violations = {}

        # Scan packages directory for violations
        violations = self.code_quality_validator.scan_directory_for_violations(
            os.path.join(self.base_path, "packages"),
            ['*.py']
        )

        # Flatten violations from all files
        all_violations = []
        for file_violations in violations.values():
            all_violations.extend(file_violations)

        execution_time = (time.time() - start_time) * 1000
        severity_counts = self._count_violation_severities(all_violations)
        passed = severity_counts.get("error", 0) == 0

        return QualityGateResult(
            "code_quality", passed, all_violations, execution_time, severity_counts
        )

    async def _run_security_gate(self) -> QualityGateResult:
        """Run security validation gate."""
        start_time = time.time()

        violations = self.security_validator.validate_directory_security(
            os.path.join(self.base_path, "packages")
        )

        # Flatten violations from all files
        all_violations = []
        for file_violations in violations.values():
            all_violations.extend(file_violations)

        execution_time = (time.time() - start_time) * 1000
        severity_counts = self._count_violation_severities(all_violations)
        passed = severity_counts.get("error", 0) == 0

        return QualityGateResult(
            "security", passed, all_violations, execution_time, severity_counts
        )

    async def _run_production_readiness_gate(self) -> QualityGateResult:
        """Run production readiness validation gate."""
        start_time = time.time()

        violations = self.production_readiness_validator.validate_deployment_checklist(
            os.path.join(self.base_path, "infrastructure")
        )

        # Flatten violations from all categories
        all_violations = []
        for category_violations in violations.values():
            all_violations.extend(category_violations)

        execution_time = (time.time() - start_time) * 1000
        severity_counts = self._count_violation_severities(all_violations)
        passed = severity_counts.get("error", 0) == 0

        return QualityGateResult(
            "production_readiness", passed, all_violations, execution_time, severity_counts
        )

    async def _run_rollback_safety_gate(self) -> QualityGateResult:
        """Run rollback safety validation gate."""
        start_time = time.time()

        violations = self.rollback_safety_validator.validate_rollback_safety()

        # Flatten violations from all categories
        all_violations = []
        for category_violations in violations.values():
            all_violations.extend(category_violations)

        execution_time = (time.time() - start_time) * 1000
        severity_counts = self._count_violation_severities(all_violations)
        passed = severity_counts.get("error", 0) == 0

        return QualityGateResult(
            "rollback_safety", passed, all_violations, execution_time, severity_counts
        )

    async def _run_completion_tracking_gate(self) -> QualityGateResult:
        """Run completion tracking validation gate."""
        start_time = time.time()

        violations = self.completion_tracker.scan_for_service_registrations(self.base_path)

        execution_time = (time.time() - start_time) * 1000
        severity_counts = self._count_violation_severities(violations)
        passed = True  # Tracking gate is informational, always passes

        return QualityGateResult(
            "completion_tracking", passed, violations, execution_time, severity_counts
        )

    async def _run_conflict_detection_gate(self) -> QualityGateResult:
        """Run conflict detection validation gate."""
        start_time = time.time()

        # Register current session
        critical_files = [
            "packages/core/typed_di/service_registrations.py",
            "packages/core/di_container.py"
        ]

        violations = self.conflict_detector.register_work_session(
            "GUARDIAN-004", self.session_id, critical_files, priority=1
        )

        # Check for deadlocks
        deadlock_violations = self.conflict_detector.detect_deadlocks()
        violations.extend(deadlock_violations)

        execution_time = (time.time() - start_time) * 1000
        severity_counts = self._count_violation_severities(violations)
        passed = severity_counts.get("error", 0) == 0

        return QualityGateResult(
            "conflict_detection", passed, violations, execution_time, severity_counts
        )

    async def run_all_quality_gates(self) -> Dict[str, QualityGateResult]:
        """Run all quality gates in parallel where possible."""
        # Define gate execution order and dependencies
        independent_gates = [
            self._run_code_quality_gate(),
            self._run_security_gate(),
            self._run_completion_tracking_gate(),
            self._run_conflict_detection_gate()
        ]

        dependent_gates = [
            self._run_production_readiness_gate(),
            self._run_rollback_safety_gate()
        ]

        # Run independent gates in parallel
        independent_results = await asyncio.gather(*independent_gates, return_exceptions=True)

        # Process independent results
        gate_names = ["code_quality", "security", "completion_tracking", "conflict_detection"]
        for i, result in enumerate(independent_results):
            if isinstance(result, Exception):
                # Create error result for failed gate
                self.results[gate_names[i]] = QualityGateResult(
                    gate_names[i], False, [CodeQualityViolation(
                        "execution_error", "orchestrator", 0, f"Gate execution failed: {str(result)}"
                    )], 0, {"error": 1}
                )
            else:
                self.results[gate_names[i]] = result

        # Run dependent gates sequentially
        for gate_coro in dependent_gates:
            try:
                result = await gate_coro
                self.results[result.gate_name] = result
            except Exception as e:
                gate_name = "unknown_dependent_gate"
                self.results[gate_name] = QualityGateResult(
                    gate_name, False, [CodeQualityViolation(
                        "execution_error", "orchestrator", 0, f"Dependent gate failed: {str(e)}"
                    )], 0, {"error": 1}
                )

        return self.results

    def cleanup_session(self):
        """Clean up the orchestrator session."""
        try:
            self.conflict_detector.release_work_session(self.session_id)
        except Exception:
            pass  # Fail silently for cleanup issues

    def generate_final_quality_report(self) -> str:
        """Generate comprehensive final quality report."""
        if not self.results:
            return "❌ NO QUALITY GATES EXECUTED\n⚠️  Run quality gates first"

        report = ["🏆 FINAL QUALITY GATE ORCHESTRATION REPORT"]
        report.append("=" * 50)
        report.append("")

        # Overall summary
        total_gates = len(self.results)
        passed_gates = sum(1 for result in self.results.values() if result.passed)
        critical_gates = ["code_quality", "security", "production_readiness", "rollback_safety"]
        critical_passed = sum(1 for gate_name in critical_gates
                            if gate_name in self.results and self.results[gate_name].passed)

        report.append(f"📊 OVERALL RESULTS: {passed_gates}/{total_gates} gates passed")
        report.append(f"🔒 CRITICAL GATES: {critical_passed}/{len(critical_gates)} passed")

        # Determine overall status
        all_critical_passed = critical_passed == len(critical_gates)
        if all_critical_passed and passed_gates == total_gates:
            status = "✅ DEPLOYMENT APPROVED - All quality gates passed"
        elif all_critical_passed:
            status = "⚠️  DEPLOYMENT CAUTION - Critical gates passed, warnings present"
        else:
            status = "🛑 DEPLOYMENT BLOCKED - Critical quality gates failed"

        report.append(f"\n🚦 STATUS: {status}")
        report.append("")

        # Individual gate results
        report.append("📋 GATE RESULTS:")
        for gate_name, result in self.results.items():
            is_critical = gate_name in critical_gates
            critical_marker = " (CRITICAL)" if is_critical else ""
            status_icon = "✅" if result.passed else "❌"

            report.append(f"  {status_icon} {gate_name.upper()}{critical_marker}")
            report.append(f"     Violations: {len(result.violations)} (Errors: {result.severity_counts.get('error', 0)}, Warnings: {result.severity_counts.get('warning', 0)})")
            report.append(f"     Execution Time: {result.execution_time_ms:.1f}ms")

        report.append("")

        # Completion tracking summary
        if "completion_tracking" in self.results:
            percentages = self.completion_tracker.calculate_completion_percentage()
            report.append("📈 COMPLETION PROGRESS:")
            report.append(f"  Overall: {percentages['overall']:.1f}%")
            report.append(f"  Target Discovery: {percentages['target_percentage']:.1f}% ({percentages['total_found']}/{percentages['target_total']} services)")

        # Performance summary
        total_execution_time = sum(result.execution_time_ms for result in self.results.values())
        report.append("")
        report.append(f"⚡ TOTAL EXECUTION TIME: {total_execution_time:.1f}ms")

        return "\n".join(report)