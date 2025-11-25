import yaml
from pathlib import Path


def test_ecr_workflow_exists():
    """Verify ECR workflow file exists."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "ecr-build-push.yml"
    assert workflow_path.exists(), "ECR workflow file not found"


def test_ecr_workflow_valid_yaml():
    """Verify workflow YAML is valid."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "ecr-build-push.yml"
    with open(workflow_path, 'r') as f:
        config = yaml.safe_load(f)
    assert config is not None, "Workflow YAML is empty or invalid"
    assert isinstance(config, dict), "Workflow YAML must be a dictionary"


def test_ecr_workflow_has_build_job():
    """Verify workflow has build-and-push job."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "ecr-build-push.yml"
    with open(workflow_path, 'r') as f:
        config = yaml.safe_load(f)
    assert 'jobs' in config, "Workflow missing 'jobs' section"
    assert 'build-and-push' in config['jobs'], "Workflow missing 'build-and-push' job"


def test_ecr_workflow_has_required_steps():
    """Verify workflow has all required steps."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "ecr-build-push.yml"
    with open(workflow_path, 'r') as f:
        config = yaml.safe_load(f)

    job = config['jobs']['build-and-push']
    steps = job.get('steps', [])
    step_names = [step.get('name') or step.get('uses', '') for step in steps]

    # Check for required step types
    has_checkout = any('checkout' in str(step).lower() for step in step_names)
    has_buildx = any('buildx' in str(step).lower() for step in step_names)
    has_ecr_login = any('login' in str(step).lower() or 'ecr' in str(step).lower() for step in step_names)
    has_docker_build = any('build' in str(step).lower() or 'docker' in str(step).lower() for step in step_names)

    assert has_checkout, "Workflow missing checkout step"
    assert has_buildx, "Workflow missing Docker Buildx setup step"
    assert has_ecr_login, "Workflow missing ECR login step"
    assert has_docker_build, "Workflow missing Docker build step"


def test_ecr_workflow_triggers_on_main():
    """Verify workflow triggers on push to main branch."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "ecr-build-push.yml"
    with open(workflow_path, 'r') as f:
        config = yaml.safe_load(f)

    # YAML parses 'on' as boolean True key
    on_config = config.get('on') or config.get(True)
    assert on_config is not None, "Workflow missing 'on' trigger section"

    if isinstance(on_config, dict) and 'push' in on_config:
        push_config = on_config['push']
        if isinstance(push_config, dict) and 'branches' in push_config:
            assert 'main' in push_config['branches'], "Workflow does not trigger on main branch"
        else:
            assert False, "Workflow push trigger not properly configured"
    else:
        assert False, "Workflow missing push trigger"


def test_ecr_workflow_correct_repository():
    """Verify workflow uses correct ECR repository."""
    workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "ecr-build-push.yml"
    with open(workflow_path, 'r') as f:
        content = f.read()

    expected_registry = "483013340174.dkr.ecr.eu-west-1.amazonaws.com/maptimize"
    assert expected_registry in content, f"Workflow does not contain expected ECR registry: {expected_registry}"
