"""
Production Deployment Readiness Validation System

This module provides comprehensive validation to ensure deployments are production-ready.
It validates code quality, tests, infrastructure, dependencies, and provides automated
rollback capabilities.

Usage:
    python -m tests.deployment.deployment_readiness --validate-all
    python -m tests.deployment.deployment_readiness --rollback-check
    python -m tests.deployment.deployment_readiness --production-simulation
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of validation checks"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CRITICAL = "critical"  # Critical failure that blocks deployment
    WARNING = "warning"  # Warning that allows deployment with conditions


@dataclass
class ValidationResult:
    """Result of a validation check"""

    name: str
    status: ValidationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    error: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class DeploymentReadinessReport:
    """Comprehensive deployment readiness report"""

    timestamp: datetime
    overall_status: ValidationStatus
    validations: List[ValidationResult]
    total_duration: float

    # Categorized results
    critical_failures: List[ValidationResult] = field(default_factory=list)
    failures: List[ValidationResult] = field(default_factory=list)
    warnings: List[ValidationResult] = field(default_factory=list)
    passed: List[ValidationResult] = field(default_factory=list)

    # Summary stats
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    warning_tests: int = 0

    def __post_init__(self):
        """Calculate summary statistics"""
        for result in self.validations:
            if result.status == ValidationStatus.CRITICAL:
                self.critical_failures.append(result)
            elif result.status == ValidationStatus.FAILED:
                self.failures.append(result)
            elif result.status == ValidationStatus.WARNING:
                self.warnings.append(result)
            elif result.status == ValidationStatus.PASSED:
                self.passed.append(result)

        self.total_tests = len(self.validations)
        self.passed_tests = len(self.passed)
        self.failed_tests = len(self.failures) + len(self.critical_failures)
        self.warning_tests = len(self.warnings)


class DeploymentReadinessValidator:
    """Main deployment readiness validation system"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.aws_profile = "campaign_prod_v7"
        self.aws_region = "eu-west-1"
        self.production_servers = {
            "prod1": {
                "hostname": "ketchup-prod1.campaign.adobe.com",
                "ip": "10.30.0.68",
                "public_ip": "54.217.126.90",
            },
            "prod2": {
                "hostname": "ketchup-prod2.campaign.adobe.com",
                "ip": "10.30.165.228",
                "public_ip": "54.220.15.1",
            },
        }
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
        self.feature_flags = {
            "KETCHUP_STATUS_UPDATER_FEATURE": "true",
            "KETCHUP_NLP_FEATURE": "true",
            "KETCHUP_JIRA_REPORTER_FEATURE": "true",
            "KETCHUP_TRUST_ENDORSEMENT_FEATURE": "true",
            "KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE": "true",
            "KETCHUP_JIRA_RAG_ENABLED": "true",
            "KETCHUP_JIRA_UNIFIED_ENABLED": "true",
        }

    async def validate_all(self) -> DeploymentReadinessReport:
        """Run comprehensive deployment readiness validation"""
        logger.info("Starting comprehensive deployment readiness validation...")
        start_time = time.time()

        validations = []

        # Core validation phases - run in order due to dependencies
        validations.extend(await self._validate_code_quality())
        validations.extend(await self._validate_tests())
        validations.extend(await self._validate_dependencies())
        validations.extend(await self._validate_infrastructure())
        validations.extend(await self._validate_aws_services())
        validations.extend(await self._validate_production_environment())
        validations.extend(await self._validate_feature_flags())

        total_duration = time.time() - start_time

        # Determine overall status
        critical_failures = [v for v in validations if v.status == ValidationStatus.CRITICAL]
        failures = [v for v in validations if v.status == ValidationStatus.FAILED]

        if critical_failures:
            overall_status = ValidationStatus.CRITICAL
        elif failures:
            overall_status = ValidationStatus.FAILED
        elif any(v.status == ValidationStatus.WARNING for v in validations):
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.PASSED

        report = DeploymentReadinessReport(
            timestamp=datetime.now(),
            overall_status=overall_status,
            validations=validations,
            total_duration=total_duration,
        )

        return report

    async def _validate_code_quality(self) -> List[ValidationResult]:
        """Validate code quality requirements"""
        logger.info("Validating code quality...")
        results = []

        # Black formatting
        result = await self._run_validation(
            "Code Formatting (Black)",
            self._check_black_formatting,
            critical=True,
            remediation="Run: make pylint from tests/setup directory to fix formatting",
        )
        results.append(result)

        # Ruff linting
        result = await self._run_validation(
            "Ruff Linting", self._check_ruff_linting, critical=False
        )
        results.append(result)

        # isort imports
        result = await self._run_validation(
            "Import Sorting (isort)", self._check_isort, critical=False
        )
        results.append(result)

        # Pylint analysis
        result = await self._run_validation("Pylint Analysis", self._check_pylint, critical=False)
        results.append(result)

        return results

    async def _validate_tests(self) -> List[ValidationResult]:
        """Validate test requirements"""
        logger.info("Validating test requirements...")
        results = []

        # Unit tests must pass
        result = await self._run_validation(
            "Unit Tests",
            self._check_unit_tests,
            critical=True,
            remediation="Fix failing unit tests before deployment. Current: 112 failures",
        )
        results.append(result)

        # Test environment setup
        result = await self._run_validation(
            "Test Environment Setup", self._check_test_environment, critical=True
        )
        results.append(result)

        # DI container initialization
        result = await self._run_validation(
            "DI Container Initialization",
            self._check_di_container,
            critical=True,
            remediation="Fix DI container initialization issues in production configuration",
        )
        results.append(result)

        return results

    async def _validate_dependencies(self) -> List[ValidationResult]:
        """Validate dependency requirements"""
        logger.info("Validating dependencies...")
        results = []

        # Python environment
        result = await self._run_validation(
            "Python Environment", self._check_python_environment, critical=True
        )
        results.append(result)

        # Package dependencies
        result = await self._run_validation(
            "Package Dependencies", self._check_package_dependencies, critical=True
        )
        results.append(result)

        # Docker environment
        result = await self._run_validation(
            "Docker Environment", self._check_docker_environment, critical=True
        )
        results.append(result)

        return results

    async def _validate_infrastructure(self) -> List[ValidationResult]:
        """Validate infrastructure requirements"""
        logger.info("Validating infrastructure...")
        results = []

        # SSH connectivity
        result = await self._run_validation(
            "SSH Connectivity",
            self._check_ssh_connectivity,
            critical=True,
            remediation="Ensure SSH keys are properly configured for production servers",
        )
        results.append(result)

        # Production server health
        result = await self._run_validation(
            "Production Server Health", self._check_server_health, critical=True
        )
        results.append(result)

        # Docker services status
        result = await self._run_validation(
            "Docker Services Status", self._check_docker_services, critical=False
        )
        results.append(result)

        return results

    async def _validate_aws_services(self) -> List[ValidationResult]:
        """Validate AWS service requirements"""
        logger.info("Validating AWS services...")
        results = []

        # AWS credentials
        result = await self._run_validation(
            "AWS Credentials",
            self._check_aws_credentials,
            critical=True,
            remediation=f"Ensure AWS profile '{self.aws_profile}' is properly configured",
        )
        results.append(result)

        # DynamoDB access
        result = await self._run_validation(
            "DynamoDB Access", self._check_dynamodb_access, critical=True
        )
        results.append(result)

        # Secrets Manager access
        result = await self._run_validation(
            "Secrets Manager Access", self._check_secrets_manager, critical=True
        )
        results.append(result)

        # ECR access
        result = await self._run_validation("ECR Access", self._check_ecr_access, critical=True)
        results.append(result)

        # SQS access
        result = await self._run_validation("SQS Access", self._check_sqs_access, critical=False)
        results.append(result)

        return results

    async def _validate_production_environment(self) -> List[ValidationResult]:
        """Validate production environment simulation"""
        logger.info("Validating production environment simulation...")
        results = []

        # Production environment variables
        result = await self._run_validation(
            "Production Environment Variables",
            self._check_production_env_vars,
            critical=True,
        )
        results.append(result)

        # Service startup simulation
        result = await self._run_validation(
            "Service Startup Simulation", self._check_service_startup, critical=True
        )
        results.append(result)

        # Health check endpoints
        result = await self._run_validation(
            "Health Check Endpoints", self._check_health_endpoints, critical=True
        )
        results.append(result)

        return results

    async def _validate_feature_flags(self) -> List[ValidationResult]:
        """Validate feature flag configuration"""
        logger.info("Validating feature flags...")
        results = []

        # Feature flag consistency
        result = await self._run_validation(
            "Feature Flag Consistency", self._check_feature_flags, critical=False
        )
        results.append(result)

        return results

    async def _run_validation(
        self,
        name: str,
        check_func,
        critical: bool = False,
        remediation: Optional[str] = None,
    ) -> ValidationResult:
        """Run a single validation check with error handling"""
        start_time = time.time()

        try:
            logger.info(f"Running validation: {name}")
            success, message, details = await check_func()
            duration = time.time() - start_time

            if success:
                status = ValidationStatus.PASSED
            elif critical:
                status = ValidationStatus.CRITICAL
            else:
                status = ValidationStatus.FAILED

            return ValidationResult(
                name=name,
                status=status,
                message=message,
                details=details,
                duration=duration,
                remediation=remediation,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Validation failed with exception: {name}: {e}")

            return ValidationResult(
                name=name,
                status=(ValidationStatus.CRITICAL if critical else ValidationStatus.FAILED),
                message=f"Validation failed with exception: {str(e)}",
                details={},
                duration=duration,
                error=str(e),
                remediation=remediation,
            )

    # Validation check implementations
    async def _check_black_formatting(self) -> Tuple[bool, str, Dict]:
        """Check if code is properly formatted with Black"""
        try:
            result = subprocess.run(
                ["black", "--check", "packages", "tests"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return (
                    True,
                    "Code is properly formatted",
                    {"files_checked": "packages, tests"},
                )
            else:
                return (
                    False,
                    "Code formatting issues found",
                    {"stdout": result.stdout, "stderr": result.stderr},
                )
        except FileNotFoundError:
            return False, "Black is not installed", {"error": "black command not found"}

    async def _check_ruff_linting(self) -> Tuple[bool, str, Dict]:
        """Check Ruff linting results"""
        try:
            result = subprocess.run(
                ["ruff", "check", "packages", "tests"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return (
                    True,
                    "No linting issues found",
                    {"files_checked": "packages, tests"},
                )
            else:
                return (
                    False,
                    "Linting issues found",
                    {"stdout": result.stdout, "stderr": result.stderr},
                )
        except FileNotFoundError:
            return False, "Ruff is not installed", {"error": "ruff command not found"}

    async def _check_isort(self) -> Tuple[bool, str, Dict]:
        """Check isort import sorting"""
        try:
            result = subprocess.run(
                ["isort", "--check", "packages", "tests"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return (
                    True,
                    "Imports are properly sorted",
                    {"files_checked": "packages, tests"},
                )
            else:
                return (
                    False,
                    "Import sorting issues found",
                    {"stdout": result.stdout, "stderr": result.stderr},
                )
        except FileNotFoundError:
            return False, "isort is not installed", {"error": "isort command not found"}

    async def _check_pylint(self) -> Tuple[bool, str, Dict]:
        """Check pylint analysis"""
        try:
            result = subprocess.run(
                ["pylint", "packages", "tests"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            # Pylint returns 0 for perfect score, but we'll be more lenient
            # Consider it a warning if score is above 8.0
            score = self._extract_pylint_score(result.stdout)

            if score is None:
                return (
                    False,
                    "Could not extract pylint score",
                    {"stdout": result.stdout, "stderr": result.stderr},
                )
            elif score >= 8.0:
                return True, f"Pylint score: {score}/10", {"score": score}
            else:
                return (
                    False,
                    f"Low pylint score: {score}/10",
                    {
                        "score": score,
                        "stdout": result.stdout[:1000],  # Truncate for readability
                    },
                )
        except FileNotFoundError:
            return (
                False,
                "Pylint is not installed",
                {"error": "pylint command not found"},
            )

    def _extract_pylint_score(self, output: str) -> Optional[float]:
        """Extract score from pylint output"""
        import re

        match = re.search(r"Your code has been rated at ([\d.]+)/10", output)
        if match:
            return float(match.group(1))
        return None

    async def _check_unit_tests(self) -> Tuple[bool, str, Dict]:
        """Check unit test status"""
        try:
            # Change to tests/setup directory and run make test-unit
            result = subprocess.run(
                ["make", "test-unit"],
                cwd=self.project_root / "tests" / "setup",
                capture_output=True,
                text=True,
            )

            # Extract test results from output
            test_stats = self._extract_test_stats(result.stdout)

            if result.returncode == 0:
                return True, f"All unit tests passed: {test_stats}", test_stats
            else:
                return (
                    False,
                    f"Unit tests failed: {test_stats}",
                    {
                        **test_stats,
                        "stderr": result.stderr[-1000:],  # Last 1000 chars of error
                    },
                )
        except Exception as e:
            return False, f"Failed to run unit tests: {str(e)}", {"error": str(e)}

    def _extract_test_stats(self, output: str) -> Dict[str, Any]:
        """Extract test statistics from pytest output"""
        import re

        stats = {}

        # Look for the final test summary line
        # Example: "112 failed, 1709 passed, 3 skipped, 46 warnings in 25.53s"
        match = re.search(r"(\d+) failed, (\d+) passed", output)
        if match:
            stats["failed"] = int(match.group(1))
            stats["passed"] = int(match.group(2))

        match = re.search(r"(\d+) skipped", output)
        if match:
            stats["skipped"] = int(match.group(1))

        match = re.search(r"(\d+) warnings", output)
        if match:
            stats["warnings"] = int(match.group(1))

        match = re.search(r"in ([\d.]+)s", output)
        if match:
            stats["duration"] = float(match.group(1))

        return stats

    async def _check_test_environment(self) -> Tuple[bool, str, Dict]:
        """Check test environment setup"""
        test_setup_dir = self.project_root / "tests" / "setup"

        checks = {}

        # Check virtual environment exists
        venv_path = test_setup_dir / ".venv"
        checks["venv_exists"] = venv_path.exists()

        # Check requirements.txt exists
        req_path = test_setup_dir / "requirements.txt"
        checks["requirements_exists"] = req_path.exists()

        # Check Makefile exists
        makefile_path = test_setup_dir / "Makefile"
        checks["makefile_exists"] = makefile_path.exists()

        all_checks_passed = all(checks.values())

        if all_checks_passed:
            return True, "Test environment properly configured", checks
        else:
            return False, "Test environment configuration issues", checks

    async def _check_di_container(self) -> Tuple[bool, str, Dict]:
        """Check DI container initialization"""
        try:
            # Try importing and initializing the DI container
            sys.path.insert(0, str(self.project_root))

            from packages.core.di_container import cleanup_container, get_container

            # Set up minimal environment variables for testing
            test_env = {
                "AWS_REGION": "eu-west-1",
                "DYNAMODB_TABLE_NAME": "ketchup_channel_information",
                "AWS_SECRET_NAME": "Ketchup_Token_Secrets",
                "LOG_LEVEL": "WARNING",
                "PYTHONPATH": str(self.project_root),
            }

            for key, value in test_env.items():
                os.environ.setdefault(key, value)

            container = await get_container()

            # Check if basic services are available
            services_available = {}

            try:
                services_available["dynamodb"] = container.get("dynamodb_client") is not None
            except Exception:
                services_available["dynamodb"] = False

            try:
                services_available["secrets"] = container.get("secrets_client") is not None
            except Exception:
                services_available["secrets"] = False

            await cleanup_container()

            if all(services_available.values()):
                return True, "DI container initializes successfully", services_available
            else:
                return False, "DI container missing services", services_available

        except Exception as e:
            return (
                False,
                f"DI container initialization failed: {str(e)}",
                {"error": str(e)},
            )

    async def _check_python_environment(self) -> Tuple[bool, str, Dict]:
        """Check Python environment"""
        info = {
            "version": sys.version,
            "executable": sys.executable,
            "path": sys.path[:3],  # First few paths
        }

        # Check Python version (should be 3.12+)
        version_info = sys.version_info
        if version_info.major == 3 and version_info.minor >= 12:
            return (
                True,
                f"Python {version_info.major}.{version_info.minor}.{version_info.micro}",
                info,
            )
        else:
            return (
                False,
                f"Python version too old: {version_info.major}.{version_info.minor}.{version_info.micro}",
                info,
            )

    async def _check_package_dependencies(self) -> Tuple[bool, str, Dict]:
        """Check package dependencies"""
        try:
            # Try importing critical packages
            critical_packages = [
                "fastapi",
                "boto3",
                "aiohttp",
                "langchain",
                "openai",
                "pytest",
                "black",
                "ruff",
            ]

            imported = {}
            for package in critical_packages:
                try:
                    __import__(package)
                    imported[package] = True
                except ImportError:
                    imported[package] = False

            missing = [pkg for pkg, success in imported.items() if not success]

            if not missing:
                return True, "All critical packages available", imported
            else:
                return False, f"Missing packages: {missing}", imported

        except Exception as e:
            return (
                False,
                f"Package dependency check failed: {str(e)}",
                {"error": str(e)},
            )

    async def _check_docker_environment(self) -> Tuple[bool, str, Dict]:
        """Check Docker environment"""
        try:
            # Check if Docker is available
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)

            if result.returncode == 0:
                return (
                    True,
                    f"Docker available: {result.stdout.strip()}",
                    {"version": result.stdout.strip()},
                )
            else:
                return False, "Docker not available", {"error": result.stderr}

        except FileNotFoundError:
            return False, "Docker not installed", {"error": "docker command not found"}

    async def _check_ssh_connectivity(self) -> Tuple[bool, str, Dict]:
        """Check SSH connectivity to production servers"""
        connectivity = {}

        for server_name, server_info in self.production_servers.items():
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
                    text=True,
                    timeout=10,
                )

                connectivity[server_name] = {
                    "hostname": server_info["hostname"],
                    "accessible": result.returncode == 0,
                    "error": result.stderr if result.returncode != 0 else None,
                }
            except subprocess.TimeoutExpired:
                connectivity[server_name] = {
                    "hostname": server_info["hostname"],
                    "accessible": False,
                    "error": "Connection timeout",
                }
            except Exception as e:
                connectivity[server_name] = {
                    "hostname": server_info["hostname"],
                    "accessible": False,
                    "error": str(e),
                }

        accessible_servers = [name for name, info in connectivity.items() if info["accessible"]]

        if len(accessible_servers) == len(self.production_servers):
            return True, "All production servers accessible", connectivity
        elif accessible_servers:
            return (
                False,
                f"Only {len(accessible_servers)}/{len(self.production_servers)} servers accessible",
                connectivity,
            )
        else:
            return False, "No production servers accessible", connectivity

    async def _check_server_health(self) -> Tuple[bool, str, Dict]:
        """Check production server health"""
        health = {}

        for server_name, server_info in self.production_servers.items():
            try:
                # Check basic system stats
                result = subprocess.run(
                    ["ssh", server_info["hostname"], "uptime && df -h / && free -m"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                if result.returncode == 0:
                    health[server_name] = {
                        "accessible": True,
                        "stats": result.stdout,
                        "error": None,
                    }
                else:
                    health[server_name] = {
                        "accessible": False,
                        "stats": None,
                        "error": result.stderr,
                    }
            except Exception as e:
                health[server_name] = {
                    "accessible": False,
                    "stats": None,
                    "error": str(e),
                }

        healthy_servers = [name for name, info in health.items() if info["accessible"]]

        if len(healthy_servers) == len(self.production_servers):
            return True, "All production servers healthy", health
        else:
            return (
                False,
                f"Server health issues: {len(healthy_servers)}/{len(self.production_servers)} healthy",
                health,
            )

    async def _check_docker_services(self) -> Tuple[bool, str, Dict]:
        """Check Docker services status on production servers"""
        services_status = {}

        for server_name, server_info in self.production_servers.items():
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        server_info["hostname"],
                        "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep ketchup",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                services_status[server_name] = {
                    "accessible": result.returncode == 0,
                    "services": result.stdout if result.returncode == 0 else None,
                    "error": result.stderr if result.returncode != 0 else None,
                }
            except Exception as e:
                services_status[server_name] = {
                    "accessible": False,
                    "services": None,
                    "error": str(e),
                }

        return True, "Docker services status retrieved", services_status

    async def _check_aws_credentials(self) -> Tuple[bool, str, Dict]:
        """Check AWS credentials"""
        try:
            session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
            sts = session.client("sts")

            identity = sts.get_caller_identity()

            return (
                True,
                f"AWS credentials valid for {identity.get('Arn', 'unknown')}",
                {
                    "profile": self.aws_profile,
                    "region": self.aws_region,
                    "account": identity.get("Account"),
                    "user_id": identity.get("UserId"),
                },
            )

        except NoCredentialsError:
            return (
                False,
                f"No AWS credentials found for profile {self.aws_profile}",
                {"profile": self.aws_profile},
            )
        except ClientError as e:
            return False, f"AWS credential error: {str(e)}", {"error": str(e)}
        except Exception as e:
            return False, f"AWS credential check failed: {str(e)}", {"error": str(e)}

    async def _check_dynamodb_access(self) -> Tuple[bool, str, Dict]:
        """Check DynamoDB access"""
        try:
            session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
            dynamodb = session.client("dynamodb")

            table_name = "ketchup_channel_information"

            response = dynamodb.describe_table(TableName=table_name)
            table_status = response["Table"]["TableStatus"]

            return (
                True,
                f"DynamoDB table {table_name} accessible, status: {table_status}",
                {
                    "table_name": table_name,
                    "status": table_status,
                    "item_count": response["Table"].get("ItemCount", "unknown"),
                },
            )

        except ClientError as e:
            return False, f"DynamoDB access error: {str(e)}", {"error": str(e)}
        except Exception as e:
            return False, f"DynamoDB check failed: {str(e)}", {"error": str(e)}

    async def _check_secrets_manager(self) -> Tuple[bool, str, Dict]:
        """Check Secrets Manager access"""
        try:
            session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
            secrets = session.client("secretsmanager")

            secret_name = "Ketchup_Token_Secrets"

            response = secrets.describe_secret(SecretId=secret_name)

            return (
                True,
                f"Secrets Manager secret {secret_name} accessible",
                {
                    "secret_name": secret_name,
                    "arn": response.get("ARN"),
                    "last_changed": str(response.get("LastChangedDate")),
                },
            )

        except ClientError as e:
            return False, f"Secrets Manager access error: {str(e)}", {"error": str(e)}
        except Exception as e:
            return False, f"Secrets Manager check failed: {str(e)}", {"error": str(e)}

    async def _check_ecr_access(self) -> Tuple[bool, str, Dict]:
        """Check ECR access"""
        try:
            session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
            ecr = session.client("ecr")

            repositories = ecr.describe_repositories()["repositories"]
            ketchup_repos = [
                repo["repositoryName"]
                for repo in repositories
                if repo["repositoryName"].startswith("ketchup")
                or repo["repositoryName"] == "mcp-jira"
            ]

            return (
                True,
                f"ECR accessible, {len(ketchup_repos)} Ketchup repositories found",
                {
                    "total_repositories": len(repositories),
                    "ketchup_repositories": ketchup_repos,
                },
            )

        except ClientError as e:
            return False, f"ECR access error: {str(e)}", {"error": str(e)}
        except Exception as e:
            return False, f"ECR check failed: {str(e)}", {"error": str(e)}

    async def _check_sqs_access(self) -> Tuple[bool, str, Dict]:
        """Check SQS access"""
        try:
            session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
            sqs = session.client("sqs")

            queues = sqs.list_queues(QueueNamePrefix="ketchup")

            if "QueueUrls" in queues and queues["QueueUrls"]:
                return (
                    True,
                    f"SQS accessible, found {len(queues['QueueUrls'])} ketchup queues",
                    {"queues": queues["QueueUrls"]},
                )
            else:
                return False, "No ketchup SQS queues found", {"queues": []}

        except ClientError as e:
            return False, f"SQS access error: {str(e)}", {"error": str(e)}
        except Exception as e:
            return False, f"SQS check failed: {str(e)}", {"error": str(e)}

    async def _check_production_env_vars(self) -> Tuple[bool, str, Dict]:
        """Check production environment variables"""
        required_vars = {
            "AWS_REGION": "eu-west-1",
            "DYNAMODB_TABLE_NAME": "ketchup_channel_information",
            "AWS_SECRET_NAME": "Ketchup_Token_Secrets",
            "LOG_LEVEL": "WARNING",
            "PYTHONPATH": str(self.project_root),
        }

        current_vars = {}
        missing_vars = []

        for var, expected in required_vars.items():
            current = os.environ.get(var)
            current_vars[var] = current

            if not current:
                missing_vars.append(var)

        if not missing_vars:
            return True, "All required environment variables present", current_vars
        else:
            return (
                False,
                f"Missing environment variables: {missing_vars}",
                {"missing": missing_vars, "current": current_vars},
            )

    async def _check_service_startup(self) -> Tuple[bool, str, Dict]:
        """Check service startup simulation"""
        # This would simulate starting services in a test environment
        # For now, just check if docker-compose files are valid

        compose_file = self.project_root / "infrastructure" / "docker-compose.yml"

        if not compose_file.exists():
            return False, "docker-compose.yml not found", {"file": str(compose_file)}

        # Validate docker-compose syntax
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(compose_file), "config"],
                capture_output=True,
                text=True,
                cwd=self.project_root / "infrastructure",
            )

            if result.returncode == 0:
                return (
                    True,
                    "docker-compose configuration valid",
                    {"file": str(compose_file)},
                )
            else:
                return (
                    False,
                    f"docker-compose validation failed: {result.stderr}",
                    {"file": str(compose_file), "error": result.stderr},
                )
        except FileNotFoundError:
            return (
                False,
                "docker-compose not available",
                {"error": "docker-compose command not found"},
            )

    async def _check_health_endpoints(self) -> Tuple[bool, str, Dict]:
        """Check health check endpoints"""
        # This would check if health endpoints respond correctly
        # For now, just verify the load balancer configuration exists

        alb_dns = "ketchup-alb-1659122421.eu-west-1.elb.amazonaws.com"
        health_check_path = "/health"

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(f"http://{alb_dns}{health_check_path}") as response,
            ):
                status = response.status
                text = await response.text()

                if status == 200:
                    return (
                        True,
                        f"Health endpoint responding: {status}",
                        {
                            "url": f"http://{alb_dns}{health_check_path}",
                            "status": status,
                            "response": text[:200],  # First 200 chars
                        },
                    )
                else:
                    return (
                        False,
                        f"Health endpoint error: {status}",
                        {
                            "url": f"http://{alb_dns}{health_check_path}",
                            "status": status,
                            "response": text[:200],
                        },
                    )
        except Exception as e:
            return (
                False,
                f"Health endpoint check failed: {str(e)}",
                {"url": f"http://{alb_dns}{health_check_path}", "error": str(e)},
            )

    async def _check_feature_flags(self) -> Tuple[bool, str, Dict]:
        """Check feature flag consistency"""
        # This would validate feature flags are consistent across environments
        flags_status = {}

        for flag, expected_value in self.feature_flags.items():
            current_value = os.environ.get(flag)
            flags_status[flag] = {
                "expected": expected_value,
                "current": current_value,
                "matches": current_value == expected_value,
            }

        mismatched = [flag for flag, info in flags_status.items() if not info["matches"]]

        if not mismatched:
            return True, "All feature flags properly configured", flags_status
        else:
            return False, f"Feature flag mismatches: {mismatched}", flags_status

    def generate_report(self, report: DeploymentReadinessReport) -> str:
        """Generate human-readable deployment readiness report"""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("DEPLOYMENT READINESS ASSESSMENT")
        lines.append("=" * 80)
        lines.append(f"Timestamp: {report.timestamp.isoformat()}")
        lines.append(f"Duration: {report.total_duration:.2f}s")
        lines.append("")

        # Overall Status
        status_color = {
            ValidationStatus.PASSED: "✅ READY",
            ValidationStatus.WARNING: "⚠️  READY WITH CONDITIONS",
            ValidationStatus.FAILED: "❌ NOT READY",
            ValidationStatus.CRITICAL: "🚨 CRITICAL ISSUES - NOT READY",
        }

        lines.append(
            f"Overall Status: {status_color.get(report.overall_status, report.overall_status.value)}"
        )
        lines.append("")

        # Summary Statistics
        lines.append("Test Coverage")
        lines.append(f"- Total Validations: {report.total_tests}")
        lines.append(f"- Passed: ✅ {report.passed_tests}")
        lines.append(f"- Failed: ❌ {report.failed_tests}")
        lines.append(f"- Warnings: ⚠️  {report.warning_tests}")
        lines.append("")

        # Critical Issues
        if report.critical_failures:
            lines.append("🚨 CRITICAL ISSUES")
            for result in report.critical_failures:
                lines.append(f"- {result.name}: {result.message}")
                if result.remediation:
                    lines.append(f"  Remediation: {result.remediation}")
            lines.append("")

        # Failures
        if report.failures:
            lines.append("❌ FAILURES")
            for result in report.failures:
                lines.append(f"- {result.name}: {result.message}")
                if result.remediation:
                    lines.append(f"  Remediation: {result.remediation}")
            lines.append("")

        # Warnings
        if report.warnings:
            lines.append("⚠️  WARNINGS")
            for result in report.warnings:
                lines.append(f"- {result.name}: {result.message}")
                if result.remediation:
                    lines.append(f"  Remediation: {result.remediation}")
            lines.append("")

        # Detailed Results
        lines.append("DETAILED RESULTS")
        lines.append("-" * 40)

        for result in report.validations:
            status_icon = {
                ValidationStatus.PASSED: "✅",
                ValidationStatus.FAILED: "❌",
                ValidationStatus.CRITICAL: "🚨",
                ValidationStatus.WARNING: "⚠️",
            }

            lines.append(f"{status_icon.get(result.status, '?')} {result.name}")
            lines.append(f"   Status: {result.status.value}")
            lines.append(f"   Message: {result.message}")
            lines.append(f"   Duration: {result.duration:.2f}s")

            if result.error:
                lines.append(f"   Error: {result.error}")

            if result.details:
                lines.append("   Details:")
                for key, value in result.details.items():
                    if isinstance(value, dict) or isinstance(value, list):
                        lines.append(f"     {key}: {json.dumps(value, indent=6)}")
                    else:
                        lines.append(f"     {key}: {value}")

            lines.append("")

        # Deployment Decision
        lines.append("DEPLOYMENT DECISION")
        lines.append("-" * 40)

        if report.overall_status == ValidationStatus.PASSED:
            lines.append("✅ READY FOR DEPLOYMENT")
            lines.append("All validation checks passed. Deployment can proceed safely.")
        elif report.overall_status == ValidationStatus.WARNING:
            lines.append("⚠️  READY WITH CONDITIONS")
            lines.append("Some warnings detected. Review warnings and proceed with caution.")
            lines.append("Consider addressing warnings in next release cycle.")
        elif report.overall_status == ValidationStatus.FAILED:
            lines.append("❌ NOT READY FOR DEPLOYMENT")
            lines.append(
                "Critical validation failures detected. Address all failures before deployment."
            )
        else:  # CRITICAL
            lines.append("🚨 CRITICAL ISSUES - DEPLOYMENT BLOCKED")
            lines.append("Critical infrastructure or code quality issues prevent deployment.")
            lines.append("Address all critical issues immediately.")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def save_report(self, report: DeploymentReadinessReport, filename: Optional[str] = None):
        """Save deployment readiness report to file"""
        if not filename:
            timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"deployment_readiness_{timestamp}.txt"

        report_text = self.generate_report(report)

        reports_dir = self.project_root / "tests" / "deployment" / "reports"
        reports_dir.mkdir(exist_ok=True)

        report_path = reports_dir / filename

        with open(report_path, "w") as f:
            f.write(report_text)

        logger.info(f"Deployment readiness report saved to: {report_path}")
        return report_path


class RollbackManager:
    """Manages rollback operations and validation"""

    def __init__(self, validator: DeploymentReadinessValidator):
        self.validator = validator
        self.project_root = validator.project_root
        self.production_servers = validator.production_servers

    async def validate_rollback_readiness(self, target_version: str) -> DeploymentReadinessReport:
        """Validate that rollback to target version is safe"""
        logger.info(f"Validating rollback readiness to version {target_version}")

        start_time = time.time()
        validations = []

        # Check version exists in ECR
        result = await self.validator._run_validation(
            f"Target Version Available ({target_version})",
            lambda: self._check_version_exists(target_version),
            critical=True,
            remediation=f"Ensure version {target_version} exists in ECR",
        )
        validations.append(result)

        # Check production servers are accessible
        result = await self.validator._run_validation(
            "Production Server Accessibility",
            self.validator._check_ssh_connectivity,
            critical=True,
        )
        validations.append(result)

        # Check current service status
        result = await self.validator._run_validation(
            "Current Service Status",
            self.validator._check_docker_services,
            critical=False,
        )
        validations.append(result)

        total_duration = time.time() - start_time

        # Determine overall status
        critical_failures = [v for v in validations if v.status == ValidationStatus.CRITICAL]

        if critical_failures:
            overall_status = ValidationStatus.CRITICAL
        else:
            overall_status = ValidationStatus.PASSED

        return DeploymentReadinessReport(
            timestamp=datetime.now(),
            overall_status=overall_status,
            validations=validations,
            total_duration=total_duration,
        )

    async def _check_version_exists(self, version: str) -> Tuple[bool, str, Dict]:
        """Check if target version exists in ECR"""
        try:
            session = boto3.Session(
                profile_name=self.validator.aws_profile,
                region_name=self.validator.aws_region,
            )
            ecr = session.client("ecr")

            version_status = {}

            for service in self.validator.services:
                try:
                    response = ecr.describe_images(
                        repositoryName=service, imageIds=[{"imageTag": version}]
                    )

                    if response["imageDetails"]:
                        version_status[service] = True
                    else:
                        version_status[service] = False

                except ClientError as e:
                    if e.response["Error"]["Code"] == "ImageNotFoundException":
                        version_status[service] = False
                    else:
                        raise

            available_services = [svc for svc, available in version_status.items() if available]

            if len(available_services) == len(self.validator.services):
                return (
                    True,
                    f"Version {version} available for all services",
                    version_status,
                )
            else:
                missing_services = [
                    svc for svc, available in version_status.items() if not available
                ]
                return (
                    False,
                    f"Version {version} missing for services: {missing_services}",
                    version_status,
                )

        except Exception as e:
            return (
                False,
                f"Failed to check version availability: {str(e)}",
                {"error": str(e)},
            )

    async def execute_rollback(self, target_version: str, force: bool = False) -> bool:
        """Execute rollback to target version"""
        logger.info(f"Executing rollback to version {target_version}")

        # Validate rollback readiness first unless forced
        if not force:
            readiness_report = await self.validate_rollback_readiness(target_version)

            if readiness_report.overall_status != ValidationStatus.PASSED:
                logger.error(
                    f"Rollback readiness validation failed: {readiness_report.overall_status}"
                )
                return False

        try:
            # Execute rollback using the existing deployment script
            result = subprocess.run(
                ["./deploy-ketchup.sh", "--rollback", target_version, "--force"],
                cwd=self.project_root / "infrastructure",
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info(f"Rollback to {target_version} completed successfully")
                return True
            else:
                logger.error(f"Rollback failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Rollback execution failed: {str(e)}")
            return False


async def main():
    """Main entry point for deployment readiness validation"""
    import argparse

    parser = argparse.ArgumentParser(description="Deployment Readiness Validation System")
    parser.add_argument("--validate-all", action="store_true", help="Run comprehensive validation")
    parser.add_argument(
        "--rollback-check",
        metavar="VERSION",
        help="Check rollback readiness for version",
    )
    parser.add_argument("--rollback", metavar="VERSION", help="Execute rollback to version")
    parser.add_argument(
        "--production-simulation",
        action="store_true",
        help="Run production environment simulation",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force operations without confirmation"
    )
    parser.add_argument("--report-file", help="Save report to specific file")

    args = parser.parse_args()

    # Initialize validator
    validator = DeploymentReadinessValidator()

    if args.validate_all or (
        not any([args.rollback_check, args.rollback, args.production_simulation])
    ):
        # Run comprehensive validation
        report = await validator.validate_all()

        # Display report
        print(validator.generate_report(report))

        # Save report
        validator.save_report(report, args.report_file)

        # Exit with appropriate code
        if report.overall_status in [
            ValidationStatus.CRITICAL,
            ValidationStatus.FAILED,
        ]:
            sys.exit(1)
        elif report.overall_status == ValidationStatus.WARNING:
            sys.exit(2)  # Warning exit code
        else:
            sys.exit(0)

    elif args.rollback_check:
        # Check rollback readiness
        rollback_manager = RollbackManager(validator)
        report = await rollback_manager.validate_rollback_readiness(args.rollback_check)

        print(validator.generate_report(report))

        if report.overall_status != ValidationStatus.PASSED:
            sys.exit(1)

    elif args.rollback:
        # Execute rollback
        rollback_manager = RollbackManager(validator)
        success = await rollback_manager.execute_rollback(args.rollback, args.force)

        if not success:
            sys.exit(1)

    elif args.production_simulation:
        # Run production environment simulation
        logger.info("Production simulation not yet implemented")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
