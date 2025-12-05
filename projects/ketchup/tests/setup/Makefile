# Ketchup Bot Makefile
#
# Simplified Makefile that provides convenience targets.
# Tool configurations are centralized in pyproject.toml at project root.
#
# Quick Reference:
#   make setup        - Set up virtual environment
#   make test-unit    - Run unit tests
#   make lint         - Run all linting checks
#   make lint-fix     - Auto-fix linting issues
#   make validate     - Run full validation (lint + tests)

.PHONY: setup test test-unit test-integration test-typed-di lint lint-fix validate clean help
ARGS?=

PYTHON=python3
PIP=pip3
VENV?=.venv
SHELL := /bin/bash
export PYTHONDONTWRITEBYTECODE=1

# Project paths
PROJECT_ROOT := $(shell cd ../.. && pwd)
PACKAGES_DIR := $(PROJECT_ROOT)/packages
TESTS_DIR := $(PROJECT_ROOT)/tests

# ============================================================================
# SETUP
# ============================================================================

setup:
	@echo "Setting up virtual environment..."
	@if [ ! -d $(VENV) ]; then $(PYTHON) -m venv $(VENV); fi
	. $(VENV)/bin/activate && $(PIP) install --upgrade pip
	. $(VENV)/bin/activate && $(PIP) install -r requirements.txt
	@echo ""
	@echo "Setup complete! Activate with: source $(VENV)/bin/activate"

# ============================================================================
# TESTING
# ============================================================================

test:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests $(ARGS)

test-unit:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit --ignore=tests/setup $(ARGS)

test-integration:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	AWS_PROFILE=campaign_prod_v7 PYTHONPATH=. pytest tests/integration $(ARGS)

test-typed-di:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit/core/typed_di -v $(ARGS)

test-jira-reporter:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter $(ARGS)

test-coverage:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit --ignore=tests/setup \
	--cov=packages --cov-report=html --cov-report=term-missing $(ARGS)

# ============================================================================
# LINTING & CODE QUALITY
# ============================================================================

lint:
	@echo "Running linting checks..."
	. $(VENV)/bin/activate && ruff check $(PACKAGES_DIR) $(TESTS_DIR)
	. $(VENV)/bin/activate && black --check $(PACKAGES_DIR) $(TESTS_DIR)
	. $(VENV)/bin/activate && isort --check $(PACKAGES_DIR) $(TESTS_DIR)
	@echo "All linting checks passed!"

lint-fix:
	@echo "Auto-fixing linting issues..."
	. $(VENV)/bin/activate && ruff check $(PACKAGES_DIR) $(TESTS_DIR) --fix
	. $(VENV)/bin/activate && black $(PACKAGES_DIR) $(TESTS_DIR)
	. $(VENV)/bin/activate && isort $(PACKAGES_DIR) $(TESTS_DIR)
	@echo "Linting issues fixed!"

# Legacy alias for backward compatibility
pylint: lint

# ============================================================================
# VALIDATION (Pre-deployment)
# ============================================================================

validate:
	@echo "Running full validation suite..."
	$(PROJECT_ROOT)/infrastructure/validate.sh

validate-fix:
	@echo "Running validation with auto-fix..."
	$(PROJECT_ROOT)/infrastructure/validate.sh --fix

validate-quick:
	@echo "Running quick validation (ruff only)..."
	$(PROJECT_ROOT)/infrastructure/validate.sh --quick

# ============================================================================
# CLEANUP
# ============================================================================

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find $(PROJECT_ROOT) -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find $(PROJECT_ROOT) -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "Cleaned up cache and compiled files"

# ============================================================================
# JIRA REPORTER SPECIFIC (Preserved for backward compatibility)
# ============================================================================

test-jira-reporter-unit:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter $(ARGS)

test-jira-reporter-integration:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	AWS_PROFILE=campaign_prod_v7 PYTHONPATH=. pytest tests/integration/test_jira_reporter $(ARGS)

test-jira-reporter-coverage:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter tests/integration/test_jira_reporter \
	--cov=jira_reporter --cov-report=html --cov-report=term-missing $(ARGS)

# ============================================================================
# DOCKER & LOCAL DEV
# ============================================================================

docker-build:
	@echo "Building Docker images..."
	cd $(PROJECT_ROOT)/infrastructure && docker-compose build

docker-up:
	@echo "Starting local Docker services..."
	cd $(PROJECT_ROOT)/infrastructure && docker-compose -f docker-compose.local.yml up -d

docker-down:
	@echo "Stopping local Docker services..."
	cd $(PROJECT_ROOT)/infrastructure && docker-compose -f docker-compose.local.yml down

docker-logs:
	cd $(PROJECT_ROOT)/infrastructure && docker-compose -f docker-compose.local.yml logs -f

# ============================================================================
# HELP
# ============================================================================

help:
	@echo ""
	@echo "Ketchup Development Commands"
	@echo "============================"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              Set up virtual environment and install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test-unit          Run unit tests"
	@echo "  make test-integration   Run integration tests (requires AWS)"
	@echo "  make test-coverage      Run tests with coverage report"
	@echo "  make test-typed-di      Run TypedDI validation tests"
	@echo "  make test-jira-reporter Run JIRA reporter tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint               Run all linting checks (ruff, black, isort)"
	@echo "  make lint-fix           Auto-fix linting issues"
	@echo "  make pylint             Alias for 'make lint' (backward compatibility)"
	@echo ""
	@echo "Validation (Pre-deployment):"
	@echo "  make validate           Run full validation suite (lint + tests)"
	@echo "  make validate-fix       Run validation with auto-fix for style issues"
	@echo "  make validate-quick     Quick validation (ruff only)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build       Build Docker images"
	@echo "  make docker-up          Start local Docker services"
	@echo "  make docker-down        Stop local Docker services"
	@echo "  make docker-logs        Follow Docker logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean              Remove cache and compiled files"
	@echo ""
	@echo "Use ARGS='...' to pass additional arguments to commands."
	@echo "Example: make test-unit ARGS='-k test_name -v'"
	@echo ""
