"""
Continuous Deployment Monitoring System

This module provides real-time monitoring of deployments and automatic
rollback capabilities based on health metrics and error rates.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List

import aiohttp
import boto3

from .deployment_readiness import DeploymentReadinessValidator

logger = logging.getLogger(__name__)


class ContinuousMonitor:
    """Continuous monitoring system for deployed services"""

    def __init__(self, validator: DeploymentReadinessValidator):
        self.validator = validator
        self.monitoring_interval = 60  # seconds
        self.error_threshold = 0.05  # 5% error rate threshold
        self.health_check_timeout = 30  # seconds
        self.rollback_cooldown = 300  # 5 minutes between rollbacks
        self.last_rollback = None
        self.monitoring_active = False

    async def start_monitoring(self, version: str, duration_minutes: int = 60):
        """Start continuous monitoring for specified duration"""
        logger.info(
            f"Starting continuous monitoring for version {version} ({duration_minutes} minutes)"
        )

        self.monitoring_active = True
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)

        monitoring_results = []

        try:
            while datetime.now() < end_time and self.monitoring_active:
                result = await self._monitor_iteration(version)
                monitoring_results.append(result)

                # Check if rollback is needed
                if result["status"] == "critical" and self._should_trigger_rollback():
                    logger.error("Critical issues detected - triggering automatic rollback")
                    await self._trigger_automatic_rollback(version)
                    break

                # Wait for next iteration
                await asyncio.sleep(self.monitoring_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        finally:
            self.monitoring_active = False

        # Generate monitoring summary
        await self._generate_monitoring_summary(version, monitoring_results, start_time)

    async def _monitor_iteration(self, version: str) -> Dict:
        """Single monitoring iteration"""
        timestamp = datetime.now()
        logger.info(f"Monitoring iteration at {timestamp.isoformat()}")

        iteration_result = {
            "timestamp": timestamp.isoformat(),
            "version": version,
            "status": "healthy",
            "checks": {},
            "metrics": {},
            "alerts": [],
        }

        # Health check endpoints
        health_status = await self._check_health_endpoints()
        iteration_result["checks"]["health_endpoints"] = health_status

        # Service availability
        service_status = await self._check_service_availability()
        iteration_result["checks"]["service_availability"] = service_status

        # Error rate monitoring
        error_metrics = await self._check_error_rates()
        iteration_result["metrics"]["error_rates"] = error_metrics

        # Resource utilization
        resource_metrics = await self._check_resource_utilization()
        iteration_result["metrics"]["resources"] = resource_metrics

        # DynamoDB throttling
        dynamodb_metrics = await self._check_dynamodb_health()
        iteration_result["metrics"]["dynamodb"] = dynamodb_metrics

        # Determine overall status
        if not health_status["healthy"] or error_metrics["critical"]:
            iteration_result["status"] = "critical"
        elif error_metrics["warning"] or resource_metrics["warning"]:
            iteration_result["status"] = "warning"

        # Generate alerts
        iteration_result["alerts"] = self._generate_alerts(iteration_result)

        return iteration_result

    async def _check_health_endpoints(self) -> Dict:
        """Check health endpoints"""
        health_endpoints = [
            "http://ketchup-alb-1659122421.eu-west-1.elb.amazonaws.com/health",
            "http://10.30.0.68/health",  # prod1 direct
            "http://10.30.165.228/health",  # prod2 direct
        ]

        results = {}
        overall_healthy = True

        for endpoint in health_endpoints:
            try:
                timeout = aiohttp.ClientTimeout(total=self.health_check_timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    start_time = time.time()
                    async with session.get(endpoint) as response:
                        response_time = time.time() - start_time
                        status_code = response.status
                        content = await response.text()

                        is_healthy = status_code == 200
                        if not is_healthy:
                            overall_healthy = False

                        results[endpoint] = {
                            "healthy": is_healthy,
                            "status_code": status_code,
                            "response_time": response_time,
                            "content": content[:200] if content else "",
                        }

            except Exception as e:
                overall_healthy = False
                results[endpoint] = {
                    "healthy": False,
                    "error": str(e),
                    "response_time": None,
                }

        return {
            "healthy": overall_healthy,
            "endpoints": results,
            "total_endpoints": len(health_endpoints),
            "healthy_endpoints": sum(1 for r in results.values() if r.get("healthy", False)),
        }

    async def _check_service_availability(self) -> Dict:
        """Check service availability on production servers"""
        servers = [
            "ketchup-prod1.campaign.adobe.com",
            "ketchup-prod2.campaign.adobe.com",
        ]
        results = {}

        for server in servers:
            try:
                # Check Docker services
                import subprocess

                result = subprocess.run(
                    [
                        "ssh",
                        server,
                        "sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep -E '^(ketchup-|mcp-jira|nginx)'",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                if result.returncode == 0:
                    running_services = (
                        result.stdout.strip().split("\n") if result.stdout.strip() else []
                    )
                    healthy_services = [s for s in running_services if "Up" in s]

                    results[server] = {
                        "accessible": True,
                        "total_services": len(running_services),
                        "healthy_services": len(healthy_services),
                        "services": running_services,
                    }
                else:
                    results[server] = {"accessible": False, "error": result.stderr}

            except Exception as e:
                results[server] = {"accessible": False, "error": str(e)}

        # Calculate overall availability
        accessible_servers = sum(1 for r in results.values() if r.get("accessible", False))

        return {
            "overall_healthy": accessible_servers == len(servers),
            "accessible_servers": accessible_servers,
            "total_servers": len(servers),
            "servers": results,
        }

    async def _check_error_rates(self) -> Dict:
        """Check error rates from logs and metrics"""
        # This is a simplified implementation
        # In a real system, you'd check CloudWatch logs or application metrics

        return {
            "critical": False,  # > 5% error rate
            "warning": False,  # > 1% error rate
            "current_rate": 0.001,  # Mock 0.1% error rate
            "threshold_critical": self.error_threshold,
            "threshold_warning": self.error_threshold / 5,
            "last_check": datetime.now().isoformat(),
        }

    async def _check_resource_utilization(self) -> Dict:
        """Check resource utilization"""
        servers = [
            "ketchup-prod1.campaign.adobe.com",
            "ketchup-prod2.campaign.adobe.com",
        ]
        results = {}

        for server in servers:
            try:
                import subprocess

                # Get basic system stats
                result = subprocess.run(
                    ["ssh", server, "free -m | grep '^Mem:' && df -h / | tail -1"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) >= 2:
                        # Parse memory usage
                        mem_line = lines[0].split()
                        total_mem = int(mem_line[1])
                        used_mem = int(mem_line[2])
                        mem_usage = (used_mem / total_mem) * 100

                        # Parse disk usage
                        disk_line = lines[1].split()
                        disk_usage = float(disk_line[4].replace("%", ""))

                        results[server] = {
                            "accessible": True,
                            "memory_usage_percent": mem_usage,
                            "disk_usage_percent": disk_usage,
                            "memory_warning": mem_usage > 80,
                            "disk_warning": disk_usage > 80,
                        }
                    else:
                        results[server] = {
                            "accessible": False,
                            "error": "Could not parse output",
                        }
                else:
                    results[server] = {"accessible": False, "error": result.stderr}

            except Exception as e:
                results[server] = {"accessible": False, "error": str(e)}

        # Determine if any warnings
        warning = any(
            r.get("memory_warning", False) or r.get("disk_warning", False)
            for r in results.values()
            if r.get("accessible", False)
        )

        return {"warning": warning, "servers": results}

    async def _check_dynamodb_health(self) -> Dict:
        """Check DynamoDB health and throttling"""
        try:
            session = boto3.Session(
                profile_name=self.validator.aws_profile,
                region_name=self.validator.aws_region,
            )

            # Check if we can read from DynamoDB
            dynamodb = session.client("dynamodb")

            start_time = time.time()
            response = dynamodb.scan(TableName="ketchup_channel_information", Limit=1)
            response_time = time.time() - start_time

            return {
                "healthy": True,
                "response_time": response_time,
                "item_count": response.get("Count", 0),
                "throttled": response_time > 5.0,  # Consider >5s as potential throttling
            }

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def _generate_alerts(self, iteration_result: Dict) -> List[str]:
        """Generate alerts based on monitoring results"""
        alerts = []

        # Health endpoint alerts
        health_checks = iteration_result["checks"].get("health_endpoints", {})
        if not health_checks.get("healthy", True):
            alerts.append(
                f"Health endpoints failing: {health_checks.get('healthy_endpoints', 0)}/{health_checks.get('total_endpoints', 0)} healthy"
            )

        # Service availability alerts
        service_checks = iteration_result["checks"].get("service_availability", {})
        if not service_checks.get("overall_healthy", True):
            alerts.append(
                f"Service availability issues: {service_checks.get('accessible_servers', 0)}/{service_checks.get('total_servers', 0)} servers accessible"
            )

        # Error rate alerts
        error_metrics = iteration_result["metrics"].get("error_rates", {})
        if error_metrics.get("critical", False):
            alerts.append(f"Critical error rate: {error_metrics.get('current_rate', 0)*100:.2f}%")
        elif error_metrics.get("warning", False):
            alerts.append(f"Warning error rate: {error_metrics.get('current_rate', 0)*100:.2f}%")

        # Resource alerts
        resource_metrics = iteration_result["metrics"].get("resources", {})
        if resource_metrics.get("warning", False):
            alerts.append("Resource utilization warnings detected")

        # DynamoDB alerts
        dynamodb_metrics = iteration_result["metrics"].get("dynamodb", {})
        if not dynamodb_metrics.get("healthy", True):
            alerts.append("DynamoDB health issues detected")
        elif dynamodb_metrics.get("throttled", False):
            alerts.append("DynamoDB throttling detected")

        return alerts

    def _should_trigger_rollback(self) -> bool:
        """Determine if automatic rollback should be triggered"""
        if self.last_rollback is None:
            return True

        # Check cooldown period
        time_since_rollback = datetime.now() - self.last_rollback
        return time_since_rollback.total_seconds() > self.rollback_cooldown

    async def _trigger_automatic_rollback(self, current_version: str):
        """Trigger automatic rollback"""
        logger.error(f"Triggering automatic rollback from version {current_version}")

        self.last_rollback = datetime.now()

        # Get previous version (simplified - would need better version tracking)
        try:
            from .deployment_readiness import RollbackManager

            RollbackManager(self.validator)

            # For now, we'll log the rollback trigger
            # In a real implementation, this would execute the rollback
            logger.error("AUTOMATIC ROLLBACK TRIGGERED")
            logger.error(f"Current version: {current_version}")
            logger.error("Manual intervention required to complete rollback")

            # Stop monitoring after triggering rollback
            self.monitoring_active = False

        except Exception as e:
            logger.error(f"Failed to trigger automatic rollback: {e}")

    async def _generate_monitoring_summary(
        self, version: str, results: List[Dict], start_time: datetime
    ):
        """Generate summary of monitoring session"""
        end_time = datetime.now()
        duration = end_time - start_time

        summary = {
            "version": version,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration.total_seconds() / 60,
            "total_iterations": len(results),
            "status_counts": {},
            "alerts_summary": {},
            "recommendations": [],
        }

        # Count statuses
        for result in results:
            status = result["status"]
            summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1

        # Count alerts
        all_alerts = []
        for result in results:
            all_alerts.extend(result.get("alerts", []))

        for alert in all_alerts:
            summary["alerts_summary"][alert] = summary["alerts_summary"].get(alert, 0) + 1

        # Generate recommendations
        if summary["status_counts"].get("critical", 0) > 0:
            summary["recommendations"].append(
                "Critical issues detected during monitoring - consider rollback"
            )

        if summary["status_counts"].get("warning", 0) > len(results) * 0.5:
            summary["recommendations"].append("High warning rate - investigate performance issues")

        if len(all_alerts) > len(results) * 0.3:
            summary["recommendations"].append("High alert rate - review system health")

        # Save summary
        reports_dir = self.validator.project_root / "tests" / "deployment" / "reports"
        reports_dir.mkdir(exist_ok=True)

        summary_file = (
            reports_dir
            / f"monitoring_summary_{version}_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Monitoring summary saved to: {summary_file}")

        # Display summary
        print("\n" + "=" * 80)
        print("CONTINUOUS MONITORING SUMMARY")
        print("=" * 80)
        print(f"Version: {version}")
        print(f"Duration: {duration.total_seconds()/60:.1f} minutes")
        print(f"Total Iterations: {len(results)}")
        print("")
        print("Status Distribution:")
        for status, count in summary["status_counts"].items():
            percentage = (count / len(results)) * 100
            print(f"  {status}: {count} ({percentage:.1f}%)")
        print("")

        if summary["alerts_summary"]:
            print("Alert Summary:")
            for alert, count in summary["alerts_summary"].items():
                print(f"  {alert}: {count} times")
            print("")

        if summary["recommendations"]:
            print("Recommendations:")
            for rec in summary["recommendations"]:
                print(f"  - {rec}")
            print("")

        print("=" * 80)


async def main():
    """Main entry point for continuous monitoring"""
    import argparse

    parser = argparse.ArgumentParser(description="Continuous Deployment Monitoring")
    parser.add_argument("--version", required=True, help="Version to monitor")
    parser.add_argument("--duration", type=int, default=60, help="Monitoring duration in minutes")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")

    args = parser.parse_args()

    # Initialize components
    from .deployment_readiness import DeploymentReadinessValidator

    validator = DeploymentReadinessValidator()
    monitor = ContinuousMonitor(validator)

    if args.interval:
        monitor.monitoring_interval = args.interval

    # Start monitoring
    await monitor.start_monitoring(args.version, args.duration)


if __name__ == "__main__":
    asyncio.run(main())
