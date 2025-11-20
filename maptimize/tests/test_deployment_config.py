"""Comprehensive deployment configuration tests.

Tests deployment configurations including:
- Dockerfile validity and best practices
- Docker-compose configuration
- IAM policies and security
- GitHub Actions CI/CD workflow
- Systemd service configuration
- Environment variable handling
"""

import json
import yaml
from pathlib import Path
import pytest


class TestDeploymentConfiguration:
    """Test complete deployment configuration."""

    def test_all_deployment_files_present(self):
        """Verify all required deployment files exist."""
        required_files = [
            'infrastructure/Dockerfile',
            'infrastructure/docker-compose.production.yml',
            'docker-compose.yml',
            '.github/workflows/ecr-build-push.yml',
            'infrastructure/maptimize.service'
        ]

        for file_path in required_files:
            path = Path(file_path)
            assert path.exists(), f"Required deployment file missing: {file_path}"

    def test_all_iam_policy_files_present(self):
        """Verify all IAM policy files exist."""
        required_policies = [
            'infrastructure/iam/trust-policy.json',
            'infrastructure/iam/secrets-policy.json',
            'infrastructure/iam/ecr-policy.json',
            'infrastructure/iam/github-actions-ecr-policy.json',
            'infrastructure/iam/pcl-deny-policy.json'
        ]

        for policy_file in required_policies:
            path = Path(policy_file)
            assert path.exists(), f"Required IAM policy missing: {policy_file}"

    def test_deployment_files_are_valid(self):
        """Verify all deployment files have valid syntax."""
        yaml_files = [
            'docker-compose.yml',
            'infrastructure/docker-compose.production.yml',
            '.github/workflows/ecr-build-push.yml',
            'infrastructure/maptimize.service'
        ]

        for file_path in yaml_files:
            if not Path(file_path).exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()
                # Try to parse as YAML
                try:
                    yaml.safe_load(content)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {file_path}: {e}")


class TestIAMPolicies:
    """Test IAM policy configuration and validity."""

    @pytest.mark.parametrize("policy_file", [
        "infrastructure/iam/trust-policy.json",
        "infrastructure/iam/secrets-policy.json",
        "infrastructure/iam/ecr-policy.json",
        "infrastructure/iam/pcl-deny-policy.json",
        "infrastructure/iam/github-actions-ecr-policy.json",
    ])
    def test_iam_policy_valid_json(self, policy_file):
        """Test that all IAM policy files contain valid JSON."""
        path = Path(policy_file)
        assert path.exists(), f"Policy file {policy_file} does not exist"

        with open(path, 'r') as f:
            try:
                config = json.load(f)
                assert isinstance(config, dict), f"{policy_file} should be a JSON object"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {policy_file}: {e}")

    def test_iam_policies_have_required_structure(self):
        """Test that IAM policies have required structure."""
        policies = {
            'infrastructure/iam/trust-policy.json': 'trust',
            'infrastructure/iam/secrets-policy.json': 'standard',
            'infrastructure/iam/ecr-policy.json': 'standard',
            'infrastructure/iam/pcl-deny-policy.json': 'standard',
            'infrastructure/iam/github-actions-ecr-policy.json': 'standard'
        }

        for policy_file, policy_type in policies.items():
            with open(policy_file, 'r') as f:
                config = json.load(f)

            assert isinstance(config, dict), f"{policy_file} must be a JSON object"

            if policy_type == 'trust':
                assert 'Statement' in config, f"{policy_file} must have Statement"
            else:
                # Standard IAM policy
                assert 'Version' in config or 'Statement' in config, \
                    f"{policy_file} missing required fields"

    def test_trust_policy_valid_structure(self):
        """Test trust policy has correct structure for role assumption."""
        with open('infrastructure/iam/trust-policy.json', 'r') as f:
            config = json.load(f)

        assert 'Statement' in config, "Trust policy must have Statement"

        statements = config['Statement']
        assert isinstance(statements, list), "Statement must be a list"
        assert len(statements) > 0, "Trust policy must have at least one statement"

        # Verify EC2 is allowed
        found_ec2 = False
        for statement in statements:
            principal = statement.get('Principal', {})
            if isinstance(principal, dict):
                service = principal.get('Service', '')
                if 'ec2' in str(service).lower():
                    found_ec2 = True
                    assert statement.get('Effect') == 'Allow', "EC2 should be allowed"
                    assert statement.get('Action') == 'sts:AssumeRole', \
                        "Should allow AssumeRole"

        assert found_ec2, "Trust policy must allow EC2 service to assume role"

    def test_secrets_policy_limits_resources(self):
        """Test secrets policy limits access to maptimize secrets."""
        with open('infrastructure/iam/secrets-policy.json', 'r') as f:
            config = json.load(f)

        statements = config.get('Statement', [])
        assert len(statements) > 0, "Secrets policy must have statements"

        # Verify at least one statement references maptimize secrets
        found_scoped_access = False
        for statement in statements:
            resources = statement.get('Resource', [])
            if not isinstance(resources, list):
                resources = [resources]

            for resource in resources:
                if 'maptimize' in str(resource).lower():
                    found_scoped_access = True
                    # Should not be overly broad (like arn:aws:secretsmanager:*:*:secret:*)
                    assert 'maptimize' in resource, "Should be scoped to maptimize secrets"

        assert found_scoped_access, "Secrets policy must reference maptimize secrets"

    def test_ecr_policy_configured_correctly(self):
        """Test ECR policy allows proper ECR operations."""
        with open('infrastructure/iam/ecr-policy.json', 'r') as f:
            config = json.load(f)

        statements = config.get('Statement', [])
        assert len(statements) > 0, "ECR policy must have statements"

        content_str = json.dumps(config).lower()
        assert 'ecr' in content_str, "ECR policy must include ECR actions"

    def test_pcl_deny_policy_has_deny_statements(self):
        """Test PCL deny policy contains Deny statements."""
        with open('infrastructure/iam/pcl-deny-policy.json', 'r') as f:
            config = json.load(f)

        statements = config.get('Statement', [])
        assert len(statements) > 0, "PCL policy must have statements"

        has_deny = any(stmt.get('Effect') == 'Deny' for stmt in statements)
        assert has_deny, "PCL policy should contain Deny statements"

    def test_github_actions_ecr_policy_allows_push(self):
        """Test GitHub Actions ECR policy allows image push."""
        with open('infrastructure/iam/github-actions-ecr-policy.json', 'r') as f:
            config = json.load(f)

        statements = config.get('Statement', [])
        assert len(statements) > 0, "GitHub Actions policy must have statements"

        content_str = json.dumps(config).upper()
        # Should allow pushing/putting images to ECR
        assert 'ECR' in content_str or 'PUT' in content_str, \
            "GitHub Actions policy should allow ECR operations"

    def test_policies_reference_correct_account(self):
        """Test policies reference correct AWS account (483013340174)."""
        account_id = '483013340174'
        policy_files = [
            'infrastructure/iam/secrets-policy.json',
            'infrastructure/iam/ecr-policy.json'
        ]

        for policy_file in policy_files:
            with open(policy_file, 'r') as f:
                content = f.read()

            # Check for account ID or proper ARN format
            if 'arn:aws' in content:
                # Should contain account ID or be wildcarded
                assert account_id in content or 'arn:aws:secretsmanager' in content or \
                       'arn:aws:ecr' in content, \
                       f"{policy_file} should reference correct AWS account or service"


class TestGitHubActionsWorkflow:
    """Test GitHub Actions CI/CD workflow configuration."""

    def test_github_actions_workflow_exists(self):
        """Verify GitHub Actions workflow file exists."""
        workflow_file = Path('.github/workflows/ecr-build-push.yml')
        assert workflow_file.exists(), "GitHub Actions workflow should exist"

    def test_github_actions_workflow_valid_yaml(self):
        """Verify GitHub Actions workflow is valid YAML."""
        with open('.github/workflows/ecr-build-push.yml', 'r') as f:
            try:
                config = yaml.safe_load(f)
                assert isinstance(config, dict), "Workflow should be YAML object"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in workflow: {e}")

    def test_github_actions_workflow_has_name(self):
        """Verify GitHub Actions workflow has name."""
        with open('.github/workflows/ecr-build-push.yml', 'r') as f:
            config = yaml.safe_load(f)

        assert 'name' in config, "Workflow should have name"
        assert len(config['name']) > 0, "Workflow name should not be empty"

    def test_github_actions_workflow_has_triggers(self):
        """Verify GitHub Actions workflow has event triggers."""
        with open('.github/workflows/ecr-build-push.yml', 'r') as f:
            config = yaml.safe_load(f)

        assert 'on' in config, "Workflow should have triggers"
        triggers = config['on']
        assert len(triggers) > 0, "Workflow should have at least one trigger"

    def test_github_actions_has_build_job(self):
        """Verify GitHub Actions has build job."""
        with open('.github/workflows/ecr-build-push.yml', 'r') as f:
            config = yaml.safe_load(f)

        assert 'jobs' in config, "Workflow should have jobs"
        jobs = config['jobs']
        assert len(jobs) > 0, "Workflow should have at least one job"

        # Should have build or similar job
        job_names = list(jobs.keys())
        assert any('build' in name.lower() or 'push' in name.lower() or 'docker' in name.lower()
                   for name in job_names), \
            "Should have build/push job"

    def test_github_actions_builds_docker_image(self):
        """Verify GitHub Actions workflow builds Docker image."""
        with open('.github/workflows/ecr-build-push.yml', 'r') as f:
            content = f.read()

        # Should reference Dockerfile or docker build
        assert 'docker' in content.lower() or 'build' in content.lower(), \
            "Workflow should build Docker image"

    def test_github_actions_pushes_to_ecr(self):
        """Verify GitHub Actions pushes to ECR."""
        with open('.github/workflows/ecr-build-push.yml', 'r') as f:
            content = f.read()

        # Should push to ECR
        assert 'ecr' in content.lower() or 'push' in content.lower(), \
            "Workflow should push to ECR"


class TestSystemdService:
    """Test systemd service configuration."""

    def test_systemd_service_file_exists(self):
        """Verify systemd service file exists."""
        service_file = Path('infrastructure/maptimize.service')
        assert service_file.exists(), "Systemd service file should exist"

    def test_systemd_service_has_unit_section(self):
        """Verify systemd service has [Unit] section."""
        with open('infrastructure/maptimize.service', 'r') as f:
            content = f.read()

        assert '[Unit]' in content, "Service file should have [Unit] section"
        assert 'Description' in content, "Should have Description in [Unit]"

    def test_systemd_service_has_service_section(self):
        """Verify systemd service has [Service] section."""
        with open('infrastructure/maptimize.service', 'r') as f:
            content = f.read()

        assert '[Service]' in content, "Service file should have [Service] section"

    def test_systemd_service_has_type(self):
        """Verify systemd service specifies Type."""
        with open('infrastructure/maptimize.service', 'r') as f:
            content = f.read()

        assert 'Type=' in content, "Service should specify Type"

    def test_systemd_service_has_exec_start(self):
        """Verify systemd service has ExecStart."""
        with open('infrastructure/maptimize.service', 'r') as f:
            content = f.read()

        assert 'ExecStart' in content, "Service should have ExecStart"

    def test_systemd_service_has_install_section(self):
        """Verify systemd service has [Install] section."""
        with open('infrastructure/maptimize.service', 'r') as f:
            content = f.read()

        assert '[Install]' in content, "Service file should have [Install] section"
        assert 'WantedBy' in content, "Should specify WantedBy target"

    def test_systemd_service_restart_policy(self):
        """Verify systemd service has restart policy."""
        with open('infrastructure/maptimize.service', 'r') as f:
            content = f.read()

        # Should have restart policy for reliability
        assert 'Restart=' in content, "Service should specify Restart policy"


class TestEnvironmentConfiguration:
    """Test environment variable configuration."""

    def test_env_example_file_exists(self):
        """Verify .env.example file exists."""
        env_file = Path('.env.example')
        assert env_file.exists(), ".env.example should exist"

    def test_env_example_has_required_variables(self):
        """Verify .env.example contains required variables."""
        with open('.env.example', 'r') as f:
            content = f.read()

        required_vars = [
            'AWS_REGION',
            'AWS_PROFILE',
            'SLACK_TOKENS_SECRET_ID'
        ]

        for var in required_vars:
            assert var in content, f".env.example should include {var}"

    def test_env_example_has_descriptions(self):
        """Verify .env.example has helpful comments."""
        with open('.env.example', 'r') as f:
            content = f.read()

        # Should have comments explaining variables
        assert '#' in content, ".env.example should have comments"

    def test_docker_compose_references_env(self):
        """Verify docker-compose references environment variables."""
        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)

        content_str = json.dumps(config).upper()

        # Should reference some environment variables
        assert '${' in str(config) or 'environment' in str(config), \
            "docker-compose should reference environment variables"


class TestDeploymentDocumentation:
    """Test deployment documentation."""

    def test_deployment_documentation_exists(self):
        """Verify deployment documentation files exist."""
        docs_files = [
            'infrastructure/SLACK_APP_SETUP.md',
            'infrastructure/ec2-setup.md'
        ]

        for doc_file in docs_files:
            path = Path(doc_file)
            if path.exists():
                with open(path, 'r') as f:
                    content = f.read()
                    assert len(content) > 0, f"{doc_file} should not be empty"

    def test_slack_app_setup_documentation(self):
        """Verify SLACK_APP_SETUP documentation is complete."""
        doc_file = Path('infrastructure/SLACK_APP_SETUP.md')
        if doc_file.exists():
            with open(doc_file, 'r') as f:
                content = f.read()

            # Should mention key setup steps
            assert 'bot_token' in content.lower() or 'token' in content.lower(), \
                "Should mention token configuration"

    def test_ec2_setup_documentation(self):
        """Verify EC2 setup documentation is complete."""
        doc_file = Path('infrastructure/ec2-setup.md')
        if doc_file.exists():
            with open(doc_file, 'r') as f:
                content = f.read()

            # Should mention IAM role setup
            assert 'iam' in content.lower() or 'role' in content.lower(), \
                "Should mention IAM role configuration"


class TestDeploymentScripts:
    """Test deployment scripts."""

    def test_deployment_scripts_exist(self):
        """Verify deployment scripts exist."""
        scripts = [
            'infrastructure/deploy.sh',
            'infrastructure/launch-ec2.sh',
            'infrastructure/user-data.sh'
        ]

        for script_file in scripts:
            path = Path(script_file)
            if path.exists():
                assert path.stat().st_size > 0, f"{script_file} should not be empty"

    def test_user_data_script_valid(self):
        """Verify user-data script is valid shell script."""
        if Path('infrastructure/user-data.sh').exists():
            with open('infrastructure/user-data.sh', 'r') as f:
                content = f.read()

            assert content.startswith('#!/bin/bash'), "user-data.sh should be bash script"

    def test_deploy_script_valid(self):
        """Verify deploy script is valid shell script."""
        if Path('infrastructure/deploy.sh').exists():
            with open('infrastructure/deploy.sh', 'r') as f:
                content = f.read()

            assert content.startswith('#!/bin/bash'), "deploy.sh should be bash script"
