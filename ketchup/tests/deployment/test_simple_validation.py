#!/usr/bin/env python3
"""
Simple test script to verify deployment validation system works with mocking
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

@pytest.mark.asyncio
async def test_basic_validation():
    """Test basic deployment validation with mocking"""
    print("Testing basic deployment validation...")

    with patch('boto3.Session') as mock_boto_session, \
         patch('subprocess.run') as mock_subprocess, \
         patch('aiohttp.ClientSession') as mock_session:

        # Mock AWS services
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {
            'Account': '123456789012',
            'UserId': 'test-user',
            'Arn': 'arn:aws:iam::123456789012:user/test'
        }

        mock_dynamodb_client = MagicMock()
        mock_dynamodb_client.describe_table.return_value = {
            'Table': {'TableStatus': 'ACTIVE', 'ItemCount': 100}
        }

        def mock_client(service_name):
            if service_name == 'sts':
                return mock_sts_client
            elif service_name == 'dynamodb':
                return mock_dynamodb_client
            return MagicMock()

        mock_boto_session.return_value.client = mock_client

        # Mock subprocess calls
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "All checks passed"
        mock_subprocess.return_value.stderr = ""

        # Mock HTTP session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "OK"
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Import and test the validator
        from tests.deployment.deployment_readiness import DeploymentReadinessValidator, ValidationStatus

        validator = DeploymentReadinessValidator()

        # Test AWS validation
        aws_results = await validator._validate_aws_services()

        passed_count = sum(1 for result in aws_results if result.status == ValidationStatus.PASSED)
        total_count = len(aws_results)

        print(f"AWS validation results: {passed_count}/{total_count} passed")

        for result in aws_results:
            status_icon = "✅" if result.status == ValidationStatus.PASSED else "❌"
            print(f"{status_icon} {result.name}: {result.message}")

        # Test code quality validation
        code_results = await validator._validate_code_quality()

        passed_code = sum(1 for result in code_results if result.status == ValidationStatus.PASSED)
        total_code = len(code_results)

        print(f"Code quality validation results: {passed_code}/{total_code} passed")

        return passed_count > 0 and passed_code > 0

async def main():
    """Main test function"""
    print("=" * 60)
    print("DEPLOYMENT VALIDATION SYSTEM TEST")
    print("=" * 60)

    try:
        success = await test_basic_validation()

        if success:
            print("✅ Basic validation test PASSED")
            return 0
        else:
            print("❌ Basic validation test FAILED")
            return 1

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)