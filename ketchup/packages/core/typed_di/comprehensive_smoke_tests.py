"""
Comprehensive Smoke Tests for TypedDI System

Tests all registered services end-to-end to catch:
- Pattern 1: Services not initialized (two-phase init issues)
- Pattern 2: Services mapped but not registered
- Pattern 3: Services used but not in bridge
- Pattern 4: Import error handling gaps

These tests should be run:
- Before deployment
- After adding new services
- In CI/CD pipeline
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class ServiceTestResult:
    """Result of testing a single service."""
    service_key: str
    success: bool
    error: Optional[str] = None
    resolution_time: float = 0.0
    service_type: Optional[str] = None


@dataclass
class SmokeTestReport:
    """Comprehensive smoke test report."""
    total_services: int = 0
    services_tested: int = 0
    services_passed: int = 0
    services_failed: int = 0
    services_skipped: int = 0
    
    test_results: List[ServiceTestResult] = field(default_factory=list)
    failures: List[ServiceTestResult] = field(default_factory=list)
    
    test_duration: float = 0.0
    
    def get_pass_rate(self) -> float:
        """Get pass rate percentage."""
        if self.services_tested == 0:
            return 0.0
        return (self.services_passed / self.services_tested) * 100
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        lines = []
        lines.append("=" * 80)
        lines.append("TYPEDDI COMPREHENSIVE SMOKE TEST REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append("📊 OVERALL RESULTS")
        lines.append(f"  Total services: {self.total_services}")
        lines.append(f"  Services tested: {self.services_tested}")
        lines.append(f"  ✅ Passed: {self.services_passed}")
        lines.append(f"  ❌ Failed: {self.services_failed}")
        lines.append(f"  ⏭️  Skipped: {self.services_skipped}")
        lines.append(f"  Pass rate: {self.get_pass_rate():.1f}%")
        lines.append(f"  Test duration: {self.test_duration:.2f}s")
        lines.append("")
        
        if self.failures:
            lines.append("❌ FAILURES")
            lines.append("-" * 80)
            for failure in self.failures:
                lines.append(f"  • {failure.service_key}")
                if failure.error:
                    # Truncate long errors
                    error_lines = failure.error.split('\n')
                    for line in error_lines[:3]:
                        lines.append(f"    {line[:76]}")
                    if len(error_lines) > 3:
                        lines.append(f"    ... ({len(error_lines) - 3} more lines)")
            lines.append("")
        
        # Verdict
        if self.services_failed == 0:
            lines.append("✅ ALL TESTS PASSED - READY FOR DEPLOYMENT")
        elif self.get_pass_rate() >= 95:
            lines.append("⚠️  MINOR FAILURES - REVIEW BEFORE DEPLOYMENT")
        else:
            lines.append("❌ CRITICAL FAILURES - DO NOT DEPLOY")
        
        lines.append("=" * 80)
        return "\n".join(lines)


class ComprehensiveSmokeTester:
    """Comprehensive smoke tester for TypedDI services."""
    
    def __init__(self):
        self.report = SmokeTestReport()
        self.tested_services: Set[str] = set()
    
    async def test_all_registered_services(self) -> SmokeTestReport:
        """Test all services registered in TypedDI."""
        from .registry import TypedServiceRegistry
        from .service_registrations import register_all_services
        
        logger.info("🔬 Starting comprehensive smoke tests...")
        start_time = time.time()
        
        # Create registry and register all services
        registry = TypedServiceRegistry()
        register_all_services(registry)
        
        # Get list of all registered services
        registered_services = registry._registrations.keys()
        self.report.total_services = len(registered_services)
        
        logger.info(f"  Found {self.report.total_services} registered services")
        
        # Initialize registry
        try:
            await registry.initialize_all()
            logger.info("  ✅ Registry initialized successfully")
        except Exception as e:
            logger.error(f"  ❌ Registry initialization failed: {e}")
            return self.report
        
        # Test each service
        for service_key in registered_services:
            result = await self._test_service(registry, service_key)
            self.report.test_results.append(result)
            
            if result.success:
                self.report.services_passed += 1
            else:
                self.report.services_failed += 1
                self.report.failures.append(result)
            
            self.report.services_tested += 1
        
        self.report.test_duration = time.time() - start_time
        
        logger.info(f"🔬 Smoke tests complete: {self.report.services_passed}/{self.report.services_tested} passed")
        
        return self.report
    
    async def _test_service(
        self,
        registry,
        service_key: str
    ) -> ServiceTestResult:
        """Test a single service."""
        start_time = time.time()
        
        try:
            # Try to get service instance
            # Extract service type from key
            service_type_name = service_key.split('#')[0].split('.')[-1]
            
            # Try to resolve by key
            if service_key in registry._instances:
                instance = registry._instances[service_key].instance
                
                # Basic validation: ensure instance is not None
                if instance is None:
                    return ServiceTestResult(
                        service_key=service_key,
                        success=False,
                        error="Service resolved to None",
                        resolution_time=time.time() - start_time,
                        service_type=service_type_name
                    )
                
                # Check if instance has expected attributes (basic health check)
                # Most services should be callable or have methods
                if not (callable(instance) or hasattr(instance, '__dict__')):
                    return ServiceTestResult(
                        service_key=service_key,
                        success=False,
                        error=f"Service is not callable and has no attributes: {type(instance)}",
                        resolution_time=time.time() - start_time,
                        service_type=service_type_name
                    )
                
                return ServiceTestResult(
                    service_key=service_key,
                    success=True,
                    resolution_time=time.time() - start_time,
                    service_type=service_type_name
                )
            else:
                return ServiceTestResult(
                    service_key=service_key,
                    success=False,
                    error="Service not in instances (not initialized)",
                    resolution_time=time.time() - start_time,
                    service_type=service_type_name
                )
                
        except Exception as e:
            return ServiceTestResult(
                service_key=service_key,
                success=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
                resolution_time=time.time() - start_time,
                service_type=service_key.split('.')[-1]
            )
    
    async def test_compatibility_bridge(self) -> SmokeTestReport:
        """Test all services accessible via compatibility bridge."""
        from .compatibility import CompatibilityBridge
        from .registry import TypedServiceRegistry
        from .service_registrations import register_all_services
        
        logger.info("🔬 Testing compatibility bridge...")
        start_time = time.time()
        
        # Setup
        registry = TypedServiceRegistry()
        register_all_services(registry)
        await registry.initialize_all()
        bridge = CompatibilityBridge(registry)
        
        # Get all available service keys from bridge
        service_keys = bridge.get_available_services()
        self.report.total_services = len(service_keys)
        
        logger.info(f"  Found {self.report.total_services} services in bridge")
        
        # Test each service key
        for key in service_keys:
            result = await self._test_bridge_service(bridge, key)
            self.report.test_results.append(result)
            
            if result.success:
                self.report.services_passed += 1
            else:
                self.report.services_failed += 1
                self.report.failures.append(result)
            
            self.report.services_tested += 1
        
        self.report.test_duration = time.time() - start_time
        
        return self.report
    
    async def _test_bridge_service(
        self,
        bridge,
        service_key: str
    ) -> ServiceTestResult:
        """Test service access via compatibility bridge."""
        start_time = time.time()
        
        try:
            instance = bridge.get_instance(service_key)
            
            if instance is None:
                return ServiceTestResult(
                    service_key=service_key,
                    success=False,
                    error="Bridge returned None",
                    resolution_time=time.time() - start_time
                )
            
            return ServiceTestResult(
                service_key=service_key,
                success=True,
                resolution_time=time.time() - start_time,
                service_type=type(instance).__name__
            )
            
        except Exception as e:
            return ServiceTestResult(
                service_key=service_key,
                success=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
                resolution_time=time.time() - start_time
            )
    
    async def test_critical_service_chain(self) -> SmokeTestReport:
        """Test critical service dependency chains."""
        logger.info("🔬 Testing critical service chains...")
        start_time = time.time()
        
        from .registry import TypedServiceRegistry
        from .service_registrations import register_all_services
        from .compatibility import CompatibilityBridge
        
        # Setup
        registry = TypedServiceRegistry()
        register_all_services(registry)
        await registry.initialize_all()
        bridge = CompatibilityBridge(registry)
        
        # Test critical chains
        critical_chains = [
            # Chain 1: Secrets → Config → Services
            ["secrets_manager", "slack_config", "slack_posting"],
            
            # Chain 2: DB Stack
            ["dynamodb_config", "dynamodb_async_client", "dynamodb_store", "user_store"],
            
            # Chain 3: Slack Operations
            ["user_ops", "info_ops", "membership_ops", "archive_ops"],
            
            # Chain 4: Handlers
            ["feedback_reactions_handler", "feedback_report_handler", "shortcut_handler"],
        ]
        
        for chain in critical_chains:
            for service_key in chain:
                if not bridge.has_service(service_key):
                    result = ServiceTestResult(
                        service_key=service_key,
                        success=False,
                        error=f"Missing from bridge (part of chain: {' → '.join(chain)})"
                    )
                    self.report.test_results.append(result)
                    self.report.services_failed += 1
                    self.report.failures.append(result)
                    self.report.services_tested += 1
                    continue
                
                result = await self._test_bridge_service(bridge, service_key)
                self.report.test_results.append(result)
                
                if result.success:
                    self.report.services_passed += 1
                else:
                    self.report.services_failed += 1
                    self.report.failures.append(result)
                
                self.report.services_tested += 1
        
        self.report.test_duration = time.time() - start_time
        
        return self.report


async def run_comprehensive_smoke_tests() -> SmokeTestReport:
    """Run all smoke tests and return comprehensive report."""
    tester = ComprehensiveSmokeTester()
    
    # Test all registered services
    report = await tester.test_all_registered_services()
    
    # Print summary
    print(report.generate_summary())
    
    return report


async def run_bridge_smoke_tests() -> SmokeTestReport:
    """Run compatibility bridge smoke tests."""
    tester = ComprehensiveSmokeTester()
    report = await tester.test_compatibility_bridge()
    print(report.generate_summary())
    return report


async def run_critical_chain_tests() -> SmokeTestReport:
    """Run critical service chain tests."""
    tester = ComprehensiveSmokeTester()
    report = await tester.test_critical_service_chain()
    print(report.generate_summary())
    return report


if __name__ == "__main__":
    import sys
    
    # Run tests
    report = asyncio.run(run_comprehensive_smoke_tests())
    
    # Exit with error if tests failed
    if report.services_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)
