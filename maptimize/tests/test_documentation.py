"""Tests for documentation files and structure."""
from pathlib import Path
import re
import ast


def test_readme_exists():
    """Test that README.md exists."""
    assert Path("README.md").exists(), "README.md does not exist in project root"


def test_readme_has_overview_section():
    """Test that README has Overview section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Overview" in content, "README missing 'Overview' section"


def test_readme_has_features_section():
    """Test that README has Features section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Features" in content, "README missing 'Features' section"


def test_readme_has_architecture_section():
    """Test that README has Architecture section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Architecture" in content, "README missing 'Architecture' section"


def test_readme_has_quick_start_section():
    """Test that README has Quick Start section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Quick Start" in content, "README missing 'Quick Start' section"


def test_readme_has_deployment_section():
    """Test that README has Deployment section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Deployment" in content, "README missing 'Deployment' section"


def test_readme_has_contributing_section():
    """Test that README has Contributing section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Contributing" in content, "README missing 'Contributing' section"


def test_readme_has_tech_stack_section():
    """Test that README has Tech Stack section."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "Tech Stack" in content or "Technology" in content, \
        "README missing technology information"


def test_readme_has_minimum_length():
    """Test that README has sufficient content."""
    with open("README.md", "r") as f:
        content = f.read()
    assert len(content) > 1000, "README is too short, should be comprehensive"


def test_deployment_guide_exists():
    """Test that deployment guide exists."""
    assert Path("docs/DEPLOYMENT.md").exists(), \
        "docs/DEPLOYMENT.md does not exist"


def test_deployment_guide_has_prerequisites():
    """Test that deployment guide has prerequisites section."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Prerequisites" in content or "Requirements" in content, \
        "Deployment guide missing prerequisites section"


def test_deployment_guide_has_setup_instructions():
    """Test that deployment guide has setup instructions."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Setup" in content or "Installation" in content, \
        "Deployment guide missing setup/installation section"


def test_deployment_guide_has_deployment_steps():
    """Test that deployment guide has deployment steps."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Deploy" in content or "Deployment" in content, \
        "Deployment guide missing deployment steps"


def test_deployment_guide_has_monitoring():
    """Test that deployment guide has monitoring section."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Monitor" in content or "Monitoring" in content or "Health" in content, \
        "Deployment guide missing monitoring section"


def test_deployment_guide_has_rollback():
    """Test that deployment guide has rollback instructions."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Rollback" in content or "Revert" in content, \
        "Deployment guide missing rollback instructions"


def test_deployment_guide_has_troubleshooting():
    """Test that deployment guide has troubleshooting section."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Troubleshoot" in content or "Issues" in content, \
        "Deployment guide missing troubleshooting section"


def test_deployment_guide_has_minimum_length():
    """Test that deployment guide has sufficient content."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert len(content) > 2000, \
        "Deployment guide is too short, should be comprehensive"


def test_troubleshooting_guide_exists():
    """Test that troubleshooting guide exists."""
    assert Path("docs/TROUBLESHOOTING.md").exists(), \
        "docs/TROUBLESHOOTING.md does not exist"


def test_troubleshooting_guide_has_common_issues():
    """Test that troubleshooting guide has common issues section."""
    with open("docs/TROUBLESHOOTING.md", "r") as f:
        content = f.read()
    assert "Issue" in content or "Problem" in content or "Error" in content, \
        "Troubleshooting guide missing issues/problems section"


def test_troubleshooting_guide_has_solutions():
    """Test that troubleshooting guide has solutions."""
    with open("docs/TROUBLESHOOTING.md", "r") as f:
        content = f.read()
    assert "Solution" in content or "Fix" in content or "Resolution" in content, \
        "Troubleshooting guide missing solutions section"


def test_troubleshooting_guide_has_debugging():
    """Test that troubleshooting guide has debugging section."""
    with open("docs/TROUBLESHOOTING.md", "r") as f:
        content = f.read()
    assert "Debug" in content or "Logs" in content, \
        "Troubleshooting guide missing debugging/logs section"


def test_troubleshooting_guide_has_minimum_content():
    """Test that troubleshooting guide has sufficient content."""
    with open("docs/TROUBLESHOOTING.md", "r") as f:
        content = f.read()
    assert len(content) > 1500, \
        "Troubleshooting guide is too short, should cover multiple scenarios"


def test_readme_code_examples_valid_python():
    """Test that Python code examples in README are syntactically valid."""
    with open("README.md", "r") as f:
        content = f.read()

    # Find Python code blocks
    python_blocks = re.findall(r"```python\n(.*?)\n```", content, re.DOTALL)

    for block in python_blocks:
        try:
            ast.parse(block)
        except SyntaxError as e:
            raise AssertionError(
                f"Invalid Python code in README: {e}\n\nCode:\n{block}"
            )


def test_deployment_code_examples_valid_bash():
    """Test that bash code examples in deployment guide are valid."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()

    # Find bash code blocks
    bash_blocks = re.findall(r"```bash\n(.*?)\n```", content, re.DOTALL)

    # Basic validation - check for common bash syntax issues
    for block in bash_blocks:
        # Check for unmatched quotes
        single_quotes = block.count("'") - block.count("\\'")
        double_quotes = block.count('"') - block.count('\\"')

        if single_quotes % 2 != 0:
            raise AssertionError(
                f"Unmatched single quotes in bash block:\n{block}"
            )
        if double_quotes % 2 != 0:
            raise AssertionError(
                f"Unmatched double quotes in bash block:\n{block}"
            )


def test_deployment_yaml_examples_valid():
    """Test that YAML examples in deployment guide are valid."""
    import yaml

    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()

    # Find YAML code blocks
    yaml_blocks = re.findall(r"```yaml\n(.*?)\n```", content, re.DOTALL)

    for block in yaml_blocks:
        try:
            yaml.safe_load(block)
        except yaml.YAMLError as e:
            raise AssertionError(
                f"Invalid YAML in deployment guide: {e}\n\nCode:\n{block}"
            )


def test_docs_directory_exists():
    """Test that docs directory exists."""
    assert Path("docs").is_dir(), "docs directory does not exist"


def test_readme_has_installation_instructions():
    """Test that README has installation instructions."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "install" in content.lower(), \
        "README missing installation instructions"


def test_readme_has_usage_examples():
    """Test that README has usage examples."""
    with open("README.md", "r") as f:
        content = f.read()
    assert "example" in content.lower() or "usage" in content.lower(), \
        "README missing usage examples"


def test_deployment_guide_docker_mentioned():
    """Test that deployment guide mentions Docker."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "Docker" in content or "docker" in content, \
        "Deployment guide does not mention Docker"


def test_deployment_guide_aws_mentioned():
    """Test that deployment guide mentions AWS."""
    with open("docs/DEPLOYMENT.md", "r") as f:
        content = f.read()
    assert "AWS" in content or "aws" in content, \
        "Deployment guide does not mention AWS configuration"
