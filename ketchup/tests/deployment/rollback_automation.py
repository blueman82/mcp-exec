"""
Automated Rollback System

This module provides automated rollback capabilities with validation,
monitoring, and safety checks to ensure reliable service restoration.
"""

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class RollbackReason(Enum):
    """Reasons for triggering rollback"""

    MANUAL = "manual"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    ERROR_RATE_THRESHOLD = "error_rate_threshold"
    DEPLOYMENT_FAILURE = "deployment_failure"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    TIMEOUT = "timeout"


class RollbackStatus(Enum):
    """Rollback execution status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomatedRollbackSystem:
    """Automated rollback system with safety checks and monitoring"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.aws_profile = "campaign_prod_v7"
        self.aws_region = "eu-west-1"

        # Production servers
        self.production_servers = {
            "prod1": {
                "hostname": "ketchup-prod1.campaign.adobe.com",
                "ip": "10.30.0.68",
                "services": [
                    "ketchup-app",
                    "ketchup-metadata-updater",
                    "mcp-jira",
                    "nginx",
                    "ketchup-access-monitor",
                    "ketchup-elasticsearch",
                    "ketchup-elasticsearch-monitor",
                ],
            },
            "prod2": {
                "hostname": "ketchup-prod2.campaign.adobe.com",
                "ip": "10.30.165.228",
                "services": [
                    "ketchup-app",
                    "ketchup-metadata-updater",
                    "mcp-jira",
                    "nginx",
                    "ketchup-access-monitor",
                    "ketchup-elasticsearch",
                    "ketchup-elasticsearch-monitor",
                    "ketchup-status-updater",
                    "ketchup-jira-reporter",
                ],
            },
        }

        # Services in ECR
        self.services = [
            "ketchup-app",
            "ketchup-metadata-updater",
            "mcp-jira",
            "ketchup-status-updater",
            "ketchup-jira-reporter",
            "ketchup-access-monitor",
            "ketchup-elasticsearch-monitor",
            "ketchup-jira-indexer",
            "ketchup-elasticsearch",
        ]

        # Rollback safety settings
        self.max_rollback_attempts = 3
        self.rollback_timeout = 600  # 10 minutes
        self.health_check_timeout = 300  # 5 minutes
        self.service_stabilization_time = 60  # 1 minute

        # Version tracking
        self.version_history = []
        self.current_versions = {}

    async def initialize_version_tracking(self):
        """Initialize version tracking from current deployments"""
        logger.info("Initializing version tracking")

        for server_name, server_info in self.production_servers.items():
            try:
                current_version = await self._get_current_version(
                    server_info["hostname"]
                )
                self.current_versions[server_name] = current_version
                logger.info(f"{server_name} current version: {current_version}")
            except Exception as e:
                logger.error(f"Failed to get current version for {server_name}: {e}")
                self.current_versions[server_name] = "unknown"

    async def execute_rollback(
        self,
        target_version: str,
        reason: RollbackReason = RollbackReason.MANUAL,
        force: bool = False,
        servers: Optional[List[str]] = None,
    ) -> Dict:
        """Execute automated rollback with comprehensive validation"""

        rollback_id = f"rollback-{int(time.time())}"
        logger.info(f"Starting rollback {rollback_id} to version {target_version}")

        rollback_record = {
            "rollback_id": rollback_id,
            "target_version": target_version,
            "reason": reason.value,
            "start_time": datetime.now().isoformat(),
            "servers": servers or list(self.production_servers.keys()),
            "force": force,
            "status": RollbackStatus.PENDING.value,
            "steps": [],
            "current_versions_before": self.current_versions.copy(),
            "validation_results": {},
            "errors": [],
        }

        try:
            # Step 1: Pre-rollback validation
            rollback_record["status"] = RollbackStatus.IN_PROGRESS.value

            if not force:
                validation_result = await self._validate_rollback_safety(
                    target_version, servers
                )
                rollback_record["validation_results"] = validation_result

                if not validation_result["safe_to_rollback"]:
                    rollback_record["status"] = RollbackStatus.FAILED.value
                    rollback_record["errors"].append("Pre-rollback validation failed")
                    return rollback_record

            # Step 2: Create backup of current state
            backup_result = await self._create_state_backup(rollback_id)
            rollback_record["steps"].append(
                {
                    "step": "backup_creation",
                    "status": "completed" if backup_result["success"] else "failed",
                    "details": backup_result,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            if not backup_result["success"] and not force:
                rollback_record["status"] = RollbackStatus.FAILED.value
                rollback_record["errors"].append("Failed to create state backup")
                return rollback_record

            # Step 3: Execute rollback on each server
            rollback_servers = servers or list(self.production_servers.keys())

            for server_name in rollback_servers:
                server_result = await self._rollback_server(
                    server_name, target_version, rollback_id
                )

                rollback_record["steps"].append(
                    {
                        "step": f"rollback_{server_name}",
                        "status": "completed" if server_result["success"] else "failed",
                        "details": server_result,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                if not server_result["success"]:
                    rollback_record["errors"].append(
                        f"Rollback failed on {server_name}: {server_result.get('error', 'Unknown error')}"
                    )

                    if not force:
                        # Attempt to restore other servers if possible
                        await self._attempt_partial_recovery(
                            rollback_record, rollback_servers
                        )
                        rollback_record["status"] = RollbackStatus.FAILED.value
                        return rollback_record

            # Step 4: Post-rollback validation
            validation_result = await self._validate_rollback_success(
                target_version, rollback_servers
            )
            rollback_record["steps"].append(
                {
                    "step": "post_rollback_validation",
                    "status": "completed" if validation_result["success"] else "failed",
                    "details": validation_result,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            if validation_result["success"]:
                rollback_record["status"] = RollbackStatus.COMPLETED.value

                # Update version tracking
                for server_name in rollback_servers:
                    self.current_versions[server_name] = target_version
            else:
                rollback_record["status"] = RollbackStatus.FAILED.value
                rollback_record["errors"].append("Post-rollback validation failed")

            rollback_record["end_time"] = datetime.now().isoformat()

            # Save rollback record
            await self._save_rollback_record(rollback_record)

            return rollback_record

        except Exception as e:
            logger.error(f"Rollback execution failed with exception: {e}")
            rollback_record["status"] = RollbackStatus.FAILED.value
            rollback_record["errors"].append(f"Exception during rollback: {str(e)}")
            rollback_record["end_time"] = datetime.now().isoformat()

            await self._save_rollback_record(rollback_record)
            return rollback_record

    async def _validate_rollback_safety(
        self, target_version: str, servers: Optional[List[str]]
    ) -> Dict:
        """Validate that rollback is safe to execute"""
        logger.info(f"Validating rollback safety for version {target_version}")

        validation_result = {
            "safe_to_rollback": False,
            "version_available": False,
            "servers_accessible": False,
            "services_stable": False,
            "checks": {},
            "warnings": [],
            "errors": [],
        }

        try:
            # Check 1: Target version exists in ECR
            version_check = await self._check_version_availability(target_version)
            validation_result["checks"]["version_availability"] = version_check
            validation_result["version_available"] = version_check["available"]

            if not version_check["available"]:
                validation_result["errors"].append(
                    f"Version {target_version} not available in ECR"
                )

            # Check 2: Production servers are accessible
            server_check = await self._check_server_accessibility(servers)
            validation_result["checks"]["server_accessibility"] = server_check
            validation_result["servers_accessible"] = server_check["all_accessible"]

            if not server_check["all_accessible"]:
                validation_result["errors"].append(
                    "Not all production servers are accessible"
                )

            # Check 3: Current services are stable
            stability_check = await self._check_service_stability(servers)
            validation_result["checks"]["service_stability"] = stability_check
            validation_result["services_stable"] = stability_check["stable"]

            if not stability_check["stable"]:
                validation_result["warnings"].append(
                    "Some services are currently unstable"
                )

            # Check 4: No recent rollbacks (safety cooldown)
            cooldown_check = await self._check_rollback_cooldown()
            validation_result["checks"]["rollback_cooldown"] = cooldown_check

            if not cooldown_check["safe"]:
                validation_result["warnings"].append(
                    f"Recent rollback detected, cooldown: {cooldown_check['remaining_minutes']} minutes"
                )

            # Determine overall safety
            validation_result["safe_to_rollback"] = (
                validation_result["version_available"]
                and validation_result["servers_accessible"]
                and len(validation_result["errors"]) == 0
            )

            return validation_result

        except Exception as e:
            validation_result["errors"].append(
                f"Validation failed with exception: {str(e)}"
            )
            return validation_result

    async def _check_version_availability(self, version: str) -> Dict:
        """Check if target version is available in ECR"""
        try:
            session = boto3.Session(
                profile_name=self.aws_profile, region_name=self.aws_region
            )
            ecr = session.client("ecr")

            availability = {}

            for service in self.services:
                try:
                    response = ecr.describe_images(
                        repositoryName=service, imageIds=[{"imageTag": version}]
                    )
                    availability[service] = bool(response["imageDetails"])
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ImageNotFoundException":
                        availability[service] = False
                    else:
                        raise

            available_services = [
                svc for svc, available in availability.items() if available
            ]

            return {
                "available": len(available_services) == len(self.services),
                "services": availability,
                "available_count": len(available_services),
                "total_count": len(self.services),
            }

        except Exception as e:
            return {"available": False, "error": str(e)}

    async def _check_server_accessibility(self, servers: Optional[List[str]]) -> Dict:
        """Check if production servers are accessible"""
        servers_to_check = servers or list(self.production_servers.keys())
        accessibility = {}

        for server_name in servers_to_check:
            server_info = self.production_servers[server_name]

            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-q",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "ConnectTimeout=5",
                        server_info["hostname"],
                        "exit",
                    ],
                    capture_output=True,
                    timeout=10,
                )

                accessibility[server_name] = {
                    "accessible": result.returncode == 0,
                    "hostname": server_info["hostname"],
                }

                if result.returncode != 0:
                    accessibility[server_name]["error"] = (
                        result.stderr.decode() if result.stderr else "Connection failed"
                    )

            except subprocess.TimeoutExpired:
                accessibility[server_name] = {
                    "accessible": False,
                    "hostname": server_info["hostname"],
                    "error": "Connection timeout",
                }
            except Exception as e:
                accessibility[server_name] = {
                    "accessible": False,
                    "hostname": server_info["hostname"],
                    "error": str(e),
                }

        accessible_count = sum(
            1 for info in accessibility.values() if info["accessible"]
        )

        return {
            "all_accessible": accessible_count == len(servers_to_check),
            "accessible_count": accessible_count,
            "total_count": len(servers_to_check),
            "servers": accessibility,
        }

    async def _check_service_stability(self, servers: Optional[List[str]]) -> Dict:
        """Check if current services are stable"""
        servers_to_check = servers or list(self.production_servers.keys())
        stability = {}

        for server_name in servers_to_check:
            server_info = self.production_servers[server_name]

            try:
                # Check Docker service status
                result = subprocess.run(
                    [
                        "ssh",
                        server_info["hostname"],
                        "sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep -E '^(ketchup-|mcp-jira|nginx)'",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                if result.returncode == 0:
                    services = (
                        result.stdout.strip().split("\n")
                        if result.stdout.strip()
                        else []
                    )
                    unstable_services = [
                        s for s in services if "Restarting" in s or "Exit" in s
                    ]

                    stability[server_name] = {
                        "stable": len(unstable_services) == 0,
                        "total_services": len(services),
                        "unstable_services": len(unstable_services),
                        "services": services,
                    }
                else:
                    stability[server_name] = {
                        "stable": False,
                        "error": "Failed to get service status",
                    }

            except Exception as e:
                stability[server_name] = {"stable": False, "error": str(e)}

        stable_servers = sum(
            1 for info in stability.values() if info.get("stable", False)
        )

        return {
            "stable": stable_servers == len(servers_to_check),
            "stable_servers": stable_servers,
            "total_servers": len(servers_to_check),
            "servers": stability,
        }

    async def _check_rollback_cooldown(self) -> Dict:
        """Check if enough time has passed since last rollback"""
        cooldown_period = 30  # 30 minutes

        try:
            # Check for recent rollback records
            rollback_logs_dir = (
                self.project_root / "tests" / "deployment" / "rollback_logs"
            )

            if not rollback_logs_dir.exists():
                return {"safe": True, "no_previous_rollbacks": True}

            # Find most recent rollback
            rollback_files = list(rollback_logs_dir.glob("rollback_*.json"))

            if not rollback_files:
                return {"safe": True, "no_previous_rollbacks": True}

            # Get most recent file
            most_recent = max(rollback_files, key=lambda f: f.stat().st_mtime)

            with open(most_recent) as f:
                last_rollback = json.load(f)

            if "end_time" in last_rollback:
                end_time = datetime.fromisoformat(last_rollback["end_time"])
                time_since = datetime.now() - end_time
                minutes_since = time_since.total_seconds() / 60

                if minutes_since < cooldown_period:
                    return {
                        "safe": False,
                        "last_rollback_time": last_rollback["end_time"],
                        "minutes_since": minutes_since,
                        "cooldown_period": cooldown_period,
                        "remaining_minutes": cooldown_period - minutes_since,
                    }

            return {"safe": True, "cooldown_satisfied": True}

        except Exception as e:
            # If we can't determine cooldown status, err on the side of caution
            return {"safe": False, "error": str(e)}

    async def _create_state_backup(self, rollback_id: str) -> Dict:
        """Create backup of current deployment state"""
        logger.info(f"Creating state backup for rollback {rollback_id}")

        try:
            backup_data = {
                "rollback_id": rollback_id,
                "backup_time": datetime.now().isoformat(),
                "current_versions": self.current_versions.copy(),
                "server_states": {},
            }

            # Capture current state of each server
            for server_name, server_info in self.production_servers.items():
                try:
                    # Get Docker compose file content
                    result = subprocess.run(
                        [
                            "ssh",
                            server_info["hostname"],
                            "cat /opt/ketchup/docker-compose.yml",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode == 0:
                        backup_data["server_states"][server_name] = {
                            "docker_compose": result.stdout,
                            "services": await self._get_server_service_list(
                                server_info["hostname"]
                            ),
                        }
                    else:
                        backup_data["server_states"][server_name] = {
                            "error": "Failed to backup docker-compose.yml"
                        }

                except Exception as e:
                    backup_data["server_states"][server_name] = {"error": str(e)}

            # Save backup
            backup_dir = self.project_root / "tests" / "deployment" / "backups"
            backup_dir.mkdir(exist_ok=True)

            backup_file = backup_dir / f"backup_{rollback_id}.json"

            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2)

            return {
                "success": True,
                "backup_file": str(backup_file),
                "backup_data": backup_data,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _rollback_server(
        self, server_name: str, target_version: str, rollback_id: str
    ) -> Dict:
        """Execute rollback on a specific server"""
        logger.info(f"Rolling back {server_name} to version {target_version}")

        server_info = self.production_servers[server_name]

        try:
            # Use the existing deployment script to perform rollback
            result = subprocess.run(
                [
                    "./deploy-ketchup.sh",
                    "--rollback",
                    target_version,
                    f"--{server_name}-only",
                    "--force",
                ],
                cwd=self.project_root / "infrastructure",
                capture_output=True,
                text=True,
                timeout=self.rollback_timeout,
            )

            if result.returncode == 0:
                # Wait for services to stabilize
                await asyncio.sleep(self.service_stabilization_time)

                # Verify rollback success
                verification = await self._verify_server_rollback(
                    server_info["hostname"], target_version
                )

                return {
                    "success": verification["success"],
                    "server": server_name,
                    "target_version": target_version,
                    "verification": verification,
                    "deployment_output": result.stdout,
                }
            else:
                return {
                    "success": False,
                    "server": server_name,
                    "error": f"Deployment script failed: {result.stderr}",
                    "return_code": result.returncode,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "server": server_name,
                "error": f"Rollback timed out after {self.rollback_timeout} seconds",
            }
        except Exception as e:
            return {"success": False, "server": server_name, "error": str(e)}

    async def _verify_server_rollback(
        self, hostname: str, expected_version: str
    ) -> Dict:
        """Verify that rollback was successful on a server"""
        try:
            # Check running container versions
            result = subprocess.run(
                [
                    "ssh",
                    hostname,
                    "sudo docker ps --format 'table {{.Names}}\t{{.Image}}' | grep -E '(ketchup-|mcp-jira)'",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[1:]  # Skip header
                version_matches = 0
                total_services = 0

                for line in lines:
                    if line.strip():
                        total_services += 1
                        if expected_version in line:
                            version_matches += 1

                success = version_matches == total_services and total_services > 0

                return {
                    "success": success,
                    "version_matches": version_matches,
                    "total_services": total_services,
                    "services": lines,
                }
            else:
                return {"success": False, "error": "Failed to check container versions"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _validate_rollback_success(
        self, target_version: str, servers: List[str]
    ) -> Dict:
        """Validate that rollback was successful across all servers"""
        logger.info("Validating rollback success")

        validation_result = {
            "success": False,
            "servers": {},
            "health_checks": {},
            "overall_health": False,
        }

        # Check each server
        for server_name in servers:
            server_info = self.production_servers[server_name]

            # Verify version
            version_check = await self._verify_server_rollback(
                server_info["hostname"], target_version
            )
            validation_result["servers"][server_name] = version_check

            # Check health endpoints
            health_check = await self._check_server_health(server_info["hostname"])
            validation_result["health_checks"][server_name] = health_check

        # Determine overall success
        all_versions_correct = all(
            result.get("success", False)
            for result in validation_result["servers"].values()
        )

        all_healthy = all(
            result.get("healthy", False)
            for result in validation_result["health_checks"].values()
        )

        validation_result["success"] = all_versions_correct
        validation_result["overall_health"] = all_healthy

        return validation_result

    async def _check_server_health(self, hostname: str) -> Dict:
        """Check health of services on a server"""
        try:
            # Simple health check - verify services are running
            result = subprocess.run(
                [
                    "ssh",
                    hostname,
                    "curl -s -o /dev/null -w '%{http_code}' http://localhost/health || echo '000'",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                status_code = result.stdout.strip()
                healthy = status_code == "200"

                return {
                    "healthy": healthy,
                    "status_code": status_code,
                    "hostname": hostname,
                }
            else:
                return {
                    "healthy": False,
                    "error": "Failed to check health endpoint",
                    "hostname": hostname,
                }

        except Exception as e:
            return {"healthy": False, "error": str(e), "hostname": hostname}

    async def _attempt_partial_recovery(
        self, rollback_record: Dict, servers: List[str]
    ):
        """Attempt to recover from partial rollback failure"""
        logger.warning("Attempting partial recovery from rollback failure")

        # This would implement logic to restore servers that were successfully rolled back
        # For now, we'll just log the attempt

        rollback_record["steps"].append(
            {
                "step": "partial_recovery_attempt",
                "status": "attempted",
                "details": {"servers": servers},
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def _save_rollback_record(self, rollback_record: Dict):
        """Save rollback record for audit and troubleshooting"""
        try:
            rollback_logs_dir = (
                self.project_root / "tests" / "deployment" / "rollback_logs"
            )
            rollback_logs_dir.mkdir(exist_ok=True)

            log_file = rollback_logs_dir / f"{rollback_record['rollback_id']}.json"

            with open(log_file, "w") as f:
                json.dump(rollback_record, f, indent=2)

            logger.info(f"Rollback record saved: {log_file}")

        except Exception as e:
            logger.error(f"Failed to save rollback record: {e}")

    async def _get_current_version(self, hostname: str) -> str:
        """Get current version from running containers"""
        try:
            result = subprocess.run(
                [
                    "ssh",
                    hostname,
                    "sudo docker ps --format '{{.Image}}' | grep ketchup-app | head -1 | grep -o 'v[0-9.]*' || echo 'unknown'",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                return result.stdout.strip() or "unknown"
            else:
                return "unknown"

        except Exception:
            return "unknown"

    async def _get_server_service_list(self, hostname: str) -> List[str]:
        """Get list of running services on a server"""
        try:
            result = subprocess.run(
                ["ssh", hostname, "sudo docker ps --format '{{.Names}}'"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                return (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
            else:
                return []

        except Exception:
            return []

    def generate_rollback_report(self, rollback_record: Dict) -> str:
        """Generate human-readable rollback report"""
        lines = []

        lines.append("=" * 80)
        lines.append("AUTOMATED ROLLBACK REPORT")
        lines.append("=" * 80)
        lines.append(f"Rollback ID: {rollback_record['rollback_id']}")
        lines.append(f"Target Version: {rollback_record['target_version']}")
        lines.append(f"Reason: {rollback_record['reason']}")
        lines.append(f"Status: {rollback_record['status']}")
        lines.append(f"Start Time: {rollback_record['start_time']}")
        if "end_time" in rollback_record:
            lines.append(f"End Time: {rollback_record['end_time']}")
        lines.append("")

        # Servers affected
        lines.append("Servers Affected:")
        for server in rollback_record["servers"]:
            lines.append(f"  - {server}")
        lines.append("")

        # Execution steps
        lines.append("Execution Steps:")
        for step in rollback_record["steps"]:
            status_icon = "✅" if step["status"] == "completed" else "❌"
            lines.append(f"  {status_icon} {step['step']}: {step['status']}")

            if "details" in step and isinstance(step["details"], dict):
                for key, value in step["details"].items():
                    if isinstance(value, (str, int, float)):
                        lines.append(f"     {key}: {value}")
        lines.append("")

        # Errors
        if rollback_record.get("errors"):
            lines.append("Errors:")
            for error in rollback_record["errors"]:
                lines.append(f"  ❌ {error}")
            lines.append("")

        # Overall result
        if rollback_record["status"] == RollbackStatus.COMPLETED.value:
            lines.append("✅ ROLLBACK SUCCESSFUL")
            lines.append("All services have been restored to the target version.")
        elif rollback_record["status"] == RollbackStatus.FAILED.value:
            lines.append("❌ ROLLBACK FAILED")
            lines.append("Manual intervention may be required.")
        else:
            lines.append(f"⚠️  ROLLBACK STATUS: {rollback_record['status'].upper()}")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)


async def main():
    """Main entry point for rollback automation"""
    import argparse

    parser = argparse.ArgumentParser(description="Automated Rollback System")
    parser.add_argument("--version", required=True, help="Target version for rollback")
    parser.add_argument("--reason", default="manual", help="Reason for rollback")
    parser.add_argument("--servers", nargs="+", help="Specific servers to rollback")
    parser.add_argument(
        "--force", action="store_true", help="Force rollback without validation"
    )

    args = parser.parse_args()

    # Initialize rollback system
    rollback_system = AutomatedRollbackSystem()
    await rollback_system.initialize_version_tracking()

    # Parse reason
    try:
        reason = RollbackReason(args.reason)
    except ValueError:
        reason = RollbackReason.MANUAL

    # Execute rollback
    result = await rollback_system.execute_rollback(
        target_version=args.version,
        reason=reason,
        force=args.force,
        servers=args.servers,
    )

    # Display report
    report = rollback_system.generate_rollback_report(result)
    print(report)

    # Exit with appropriate code
    if result["status"] == RollbackStatus.COMPLETED.value:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    import sys

    asyncio.run(main())
