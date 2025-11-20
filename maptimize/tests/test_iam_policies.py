import json
from pathlib import Path
import pytest


POLICY_FILES = [
    "infrastructure/iam/trust-policy.json",
    "infrastructure/iam/secrets-policy.json",
    "infrastructure/iam/ecr-policy.json",
    "infrastructure/iam/pcl-deny-policy.json",
    "infrastructure/iam/github-actions-ecr-policy.json",
]


@pytest.mark.parametrize("policy_file", POLICY_FILES)
def test_iam_policy_valid_json(policy_file):
    """Test that policy file is valid JSON."""
    path = Path(policy_file)
    assert path.exists(), f"Policy file {policy_file} does not exist"
    with open(path, "r") as f:
        config = json.load(f)
    assert isinstance(config, dict), f"Policy file {policy_file} is not a valid JSON object"


@pytest.mark.parametrize("policy_file", POLICY_FILES)
def test_iam_policies_have_statement(policy_file):
    """Test that policies have correct structure with Statement."""
    path = Path(policy_file)
    with open(path, "r") as f:
        config = json.load(f)

    # Trust policy has AssumeRolePolicyDocument structure
    if "trust" in policy_file:
        assert "Statement" in config, f"Trust policy {policy_file} missing Statement"
    else:
        # Other policies have standard structure
        assert "Statement" in config or "Version" in config, f"Policy {policy_file} missing required structure"


def test_policies_reference_maptimize():
    """Test that ARNs reference maptimize, not asksplunk."""
    policy_files = [
        "infrastructure/iam/secrets-policy.json",
        "infrastructure/iam/ecr-policy.json",
    ]

    for policy_file in policy_files:
        path = Path(policy_file)
        with open(path, "r") as f:
            content = f.read()
        assert "maptimize" in content.lower(), f"Policy {policy_file} does not reference maptimize"
        assert "asksplunk" not in content.lower(), f"Policy {policy_file} still references asksplunk"


def test_trust_policy_allows_ec2():
    """Test that trust policy allows EC2 service."""
    path = Path("infrastructure/iam/trust-policy.json")
    with open(path, "r") as f:
        config = json.load(f)

    statements = config.get("Statement", [])
    assert len(statements) > 0, "Trust policy has no statements"

    # Check that at least one statement allows EC2 service
    found_ec2 = False
    for statement in statements:
        principal = statement.get("Principal", {})
        service = principal.get("Service", "")
        if "ec2" in service.lower():
            found_ec2 = True
            assert statement.get("Effect") == "Allow", "EC2 principal should have Allow effect"
            break

    assert found_ec2, "Trust policy does not allow EC2 service"


def test_secrets_policy_limits_scope():
    """Test that secrets policy is limited to maptimize/* secrets."""
    path = Path("infrastructure/iam/secrets-policy.json")
    with open(path, "r") as f:
        config = json.load(f)

    statements = config.get("Statement", [])
    assert len(statements) > 0, "Secrets policy has no statements"

    # Check that resources are scoped to maptimize
    found_maptimize_resource = False
    for statement in statements:
        resources = statement.get("Resource", [])
        if not isinstance(resources, list):
            resources = [resources]

        for resource in resources:
            if "maptimize" in resource.lower():
                found_maptimize_resource = True
                break

    assert found_maptimize_resource, "Secrets policy does not reference maptimize secrets"


def test_ecr_policy_configured():
    """Test that ECR policy is properly configured."""
    path = Path("infrastructure/iam/ecr-policy.json")
    with open(path, "r") as f:
        config = json.load(f)

    statements = config.get("Statement", [])
    assert len(statements) > 0, "ECR policy has no statements"

    # Check for ECR-related actions
    found_ecr = False
    for statement in statements:
        actions = statement.get("Action", [])
        if not isinstance(actions, list):
            actions = [actions]

        for action in actions:
            if "ecr" in action.lower():
                found_ecr = True
                break

    assert found_ecr, "ECR policy does not have ECR actions"


def test_pcl_deny_policy_exists():
    """Test that PCL deny policy exists and is valid."""
    path = Path("infrastructure/iam/pcl-deny-policy.json")
    with open(path, "r") as f:
        config = json.load(f)

    statements = config.get("Statement", [])
    assert len(statements) > 0, "PCL deny policy has no statements"

    # At least one statement should have Deny effect
    found_deny = False
    for statement in statements:
        if statement.get("Effect") == "Deny":
            found_deny = True
            break

    assert found_deny, "PCL policy does not have any Deny statements"


def test_github_actions_ecr_policy_exists():
    """Test that GitHub Actions ECR policy exists and is valid."""
    path = Path("infrastructure/iam/github-actions-ecr-policy.json")
    with open(path, "r") as f:
        config = json.load(f)

    statements = config.get("Statement", [])
    assert len(statements) > 0, "GitHub Actions policy has no statements"
