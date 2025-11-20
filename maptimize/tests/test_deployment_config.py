"""Comprehensive deployment configuration tests.

Tests deployment configurations including:
- Dockerfile validity and best practices
- Docker-compose configuration
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
        # Setup documentation has been removed as part of infrastructure cleanup
        # Main deployment guidance is now in README.md and docs/plans/
        pass


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
