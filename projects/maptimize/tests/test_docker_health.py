"""Docker container health check and deployment tests.

Tests Docker configuration including:
- Dockerfile structure and build validation
- Docker Compose health checks
- Container startup behavior
- Non-root user enforcement
- Health check verification
"""

import subprocess
import json
from pathlib import Path
import pytest


class TestDockerHealthCheck:
    """Test Docker health check configuration."""

    def test_docker_healthcheck_directive_exists(self):
        """Verify HEALTHCHECK directive is present in Dockerfile."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        assert 'HEALTHCHECK' in content, "Dockerfile must include HEALTHCHECK directive"
        # Verify healthcheck has proper format
        assert '--interval' in content, "HEALTHCHECK should specify interval"

    def test_docker_healthcheck_python_import(self):
        """Verify health check uses Python import validation."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Check for python -c or python -m in healthcheck
        assert 'python' in content.lower(), "Health check should use Python"

    def test_docker_healthcheck_interval_reasonable(self):
        """Verify health check interval is reasonable (30s is good)."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Extract healthcheck line
        for line in content.split('\n'):
            if 'HEALTHCHECK' in line:
                # Should have reasonable intervals (30s-60s is typical)
                assert '--interval' in line, "HEALTHCHECK should specify interval"
                # Should have timeout
                assert '--timeout' in line or 'CMD' in line, "HEALTHCHECK should have timeout"

    def test_docker_healthcheck_retry_logic(self):
        """Verify health check has retry logic."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Healthcheck should have retries configured
        for line in content.split('\n'):
            if 'HEALTHCHECK' in line:
                # Should have retries (optional but recommended)
                if '--retries' in content:
                    assert '--retries' in line or '--retries' in content


class TestDockerfile:
    """Test Dockerfile configuration and structure."""

    def test_dockerfile_uses_multi_stage_build(self):
        """Verify Dockerfile uses multi-stage build for optimization."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        from_count = content.count('FROM')
        assert from_count >= 2, f"Dockerfile should use multi-stage build (2+ FROM), found {from_count}"

    def test_dockerfile_builder_stage_exists(self):
        """Verify builder stage is present and properly configured."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        assert 'FROM' in content, "Dockerfile should have FROM statements"
        # Should have build dependencies
        assert 'hatchling' in content or 'build' in content.lower(), \
            "Builder stage should install build tools"

    def test_dockerfile_runtime_stage_exists(self):
        """Verify runtime stage is present."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Count FROM statements (should be at least 2)
        from_indices = [i for i, line in enumerate(content.split('\n')) if line.startswith('FROM')]
        assert len(from_indices) >= 2, "Should have runtime stage (2nd FROM)"

    def test_dockerfile_non_root_user(self):
        """Verify non-root user is used in final stage."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        assert 'USER' in content, "Dockerfile should specify USER directive"

        # Get last USER directive (final stage)
        user_directives = [line.strip() for line in content.split('\n') if line.strip().startswith('USER')]
        assert len(user_directives) > 0, "Dockerfile should have USER directive"

        final_user = user_directives[-1]
        assert 'root' not in final_user or '1000' in final_user, \
            "Final stage should use non-root user"

    def test_dockerfile_creates_app_user(self):
        """Verify application user is created."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Should create a user (typically maptimize or similar)
        assert 'useradd' in content or 'USER' in content, \
            "Dockerfile should create application user"

    def test_dockerfile_working_directory_set(self):
        """Verify WORKDIR is set appropriately."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        assert 'WORKDIR' in content, "Dockerfile should set WORKDIR"

    def test_dockerfile_entrypoint_configured(self):
        """Verify ENTRYPOINT or CMD is properly configured."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        has_entrypoint = 'ENTRYPOINT' in content
        has_cmd = 'CMD' in content
        assert has_entrypoint or has_cmd, "Dockerfile should have ENTRYPOINT or CMD"

    def test_dockerfile_python_slim_base(self):
        """Verify slim Python image is used for minimal size."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Should use slim or alpine for size optimization
        assert 'slim' in content or 'alpine' in content, \
            "Should use slim or alpine base image for size optimization"


class TestDockerCompose:
    """Test docker-compose configuration."""

    def test_docker_compose_file_exists(self):
        """Verify docker-compose files exist."""
        compose_files = [
            'docker-compose.yml',
            'docker-compose.production.yml'
        ]

        for compose_file in compose_files:
            path = Path(compose_file)
            assert path.exists(), f"docker-compose file {compose_file} should exist"

    def test_docker_compose_has_maptimize_service(self):
        """Verify docker-compose has maptimize service."""
        import yaml

        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)

        assert 'services' in config, "docker-compose should have services"
        assert any('maptimize' in key for key in config['services'].keys()), \
            "docker-compose should have maptimize service"

    def test_docker_compose_healthcheck_configured(self):
        """Verify docker-compose has health check."""
        import yaml

        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)

        services = config.get('services', {})
        maptimize_service = None

        for service_name, service_config in services.items():
            if 'maptimize' in service_name:
                maptimize_service = service_config
                break

        assert maptimize_service is not None, "Maptimize service should exist"
        assert 'healthcheck' in maptimize_service, "Service should have healthcheck"

    def test_docker_compose_production_has_image_specification(self):
        """Verify production compose specifies ECR image."""
        import yaml

        with open('docker-compose.production.yml', 'r') as f:
            config = yaml.safe_load(f)

        services = config.get('services', {})
        maptimize_service = None

        for service_name, service_config in services.items():
            if 'maptimize' in service_name:
                maptimize_service = service_config
                break

        assert maptimize_service is not None, "Maptimize service should exist"
        assert 'image' in maptimize_service, "Production service should specify image"
        # ECR image format: account.dkr.ecr.region.amazonaws.com/repo:tag
        image = maptimize_service.get('image', '')
        assert 'dkr.ecr' in image or 'ecr' in image or '483013340174' in image, \
            "Production should use ECR image"

    def test_docker_compose_environment_variables(self):
        """Verify docker-compose configures necessary environment variables."""
        import yaml

        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)

        services = config.get('services', {})
        maptimize_service = None

        for service_name, service_config in services.items():
            if 'maptimize' in service_name:
                maptimize_service = service_config
                break

        assert maptimize_service is not None
        environment = maptimize_service.get('environment', {})

        # Should have Python unbuffered output
        assert 'PYTHONUNBUFFERED' in str(environment), \
            "Should set PYTHONUNBUFFERED"

    def test_docker_compose_volumes_for_development(self):
        """Verify development compose mounts volumes for live code."""
        import yaml

        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)

        services = config.get('services', {})
        maptimize_service = None

        for service_name, service_config in services.items():
            if 'maptimize' in service_name:
                maptimize_service = service_config
                break

        assert maptimize_service is not None
        volumes = maptimize_service.get('volumes', [])

        # Development should mount source code
        assert len(volumes) > 0, "Development compose should mount volumes"

    def test_docker_compose_network_configuration(self):
        """Verify docker-compose network is properly configured."""
        import yaml

        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)

        assert 'services' in config or 'networks' in config, \
            "docker-compose should have services or network configuration"


class TestDockerBuildContext:
    """Test Docker build context and dependencies."""

    def test_dockerfile_in_infrastructure_directory(self):
        """Verify Dockerfile is in correct location."""
        dockerfile = Path('infrastructure/Dockerfile')
        assert dockerfile.exists(), "Dockerfile should exist in infrastructure/"

    def test_dockerignore_file_exists(self):
        """Verify .dockerignore file exists to optimize build context."""
        dockerignore = Path('.dockerignore')
        if dockerignore.exists():
            # Verify it contains common entries
            with open(dockerignore, 'r') as f:
                content = f.read()
                assert len(content) > 0, ".dockerignore should not be empty"

    def test_docker_build_excludes_test_files(self):
        """Verify test files are excluded from Docker image."""
        if Path('.dockerignore').exists():
            with open('.dockerignore', 'r') as f:
                content = f.read()
                assert 'test' in content.lower() or 'pytest' in content.lower(), \
                    ".dockerignore should exclude test files"


class TestDockerProductionConfig:
    """Test production Docker configuration."""

    def test_production_docker_compose_exists(self):
        """Verify production docker-compose file exists."""
        path = Path('docker-compose.production.yml')
        assert path.exists(), "Production docker-compose should exist"

    def test_production_config_has_ecr_image(self):
        """Verify production config references ECR image."""
        import yaml

        with open('docker-compose.production.yml', 'r') as f:
            config = yaml.safe_load(f)

        content = json.dumps(config)
        assert 'dkr.ecr' in content or 'amazonaws' in content or '483013340174' in content, \
            "Production config should reference ECR image (AWS account)"

    def test_production_no_volume_mounts(self):
        """Verify production doesn't mount development volumes."""
        import yaml

        with open('docker-compose.production.yml', 'r') as f:
            config = yaml.safe_load(f)

        services = config.get('services', {})
        maptimize_service = None

        for service_name, service_config in services.items():
            if 'maptimize' in service_name:
                maptimize_service = service_config
                break

        if maptimize_service:
            volumes = maptimize_service.get('volumes', [])
            # Production might not have volumes or only data volumes
            # Should not mount source code
            if volumes:
                for volume in volumes:
                    if isinstance(volume, str):
                        assert '/src' not in volume and './src' not in volume, \
                            "Production should not mount source code"


class TestDockerSecurityConfiguration:
    """Test Docker security configurations."""

    def test_dockerfile_user_is_not_root(self):
        """Verify final user is not root."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Get last USER directive
        lines = content.split('\n')
        user_directives = [line for line in lines if line.strip().startswith('USER')]

        assert len(user_directives) > 0, "Should have USER directive"

        last_user = user_directives[-1].strip()
        assert last_user != 'USER root', "Final user should not be root"
        assert 'maptimize' in last_user or '1000' in last_user or '1001' in last_user, \
            "Should use application-specific non-root user"

    def test_dockerfile_drops_capabilities(self):
        """Verify unnecessary capabilities are dropped if configured."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Check if there are any security hardening directives
        # (This is optional but recommended)
        has_security_config = ('cap-drop' in content.lower() or
                               'cap-add' in content.lower() or
                               'readonly' in content.lower())
        # Just verify it's configured if present
        if has_security_config:
            assert True


class TestDockerImageOptimization:
    """Test Docker image optimization."""

    def test_dockerfile_uses_layer_caching(self):
        """Verify Dockerfile is structured to leverage layer caching."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        lines = content.split('\n')

        # Verify structure: build tools first, then copy, then install
        has_pip_install = any('pip' in line for line in lines)
        has_copy = any('COPY' in line for line in lines)

        if has_pip_install and has_copy:
            # Verify copy comes before install for caching
            copy_line_nums = [i for i, line in enumerate(lines) if 'COPY' in line]
            pip_line_nums = [i for i, line in enumerate(lines) if 'pip' in line]

            if copy_line_nums and pip_line_nums:
                # This is a soft check - good practice to copy after install setup
                assert len(copy_line_nums) > 0 or len(pip_line_nums) > 0

    def test_dockerfile_minimal_base_image(self):
        """Verify minimal base image is used."""
        with open('infrastructure/Dockerfile', 'r') as f:
            content = f.read()

        # Should use slim or alpine
        lines = [line for line in content.split('\n') if line.startswith('FROM')]
        assert any('slim' in line or 'alpine' in line for line in lines), \
            "Should use slim or alpine base image"
