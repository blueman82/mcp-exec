.PHONY: help venv validate fix test lint type-check coverage clean deploy deploy-dry deploy-skip-validation build push docker-shell install install-dev

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# Virtual environment
VENV := .venv
VENV_BIN := $(VENV)/bin
PYTHON := $(VENV_BIN)/python3
PIP := $(VENV_BIN)/pip

# Python paths
SRC := src/maptimize
TESTS := tests
INFRA := infrastructure

help: ## Show this help message
	@echo "$(BLUE)Maptimize - Local CI/CD Helpers$(NC)"
	@echo ""
	@echo "$(GREEN)Quick Start:$(NC)"
	@echo "  make venv               Create virtual environment"
	@echo "  make install-dev        Install dev dependencies in venv"
	@echo "  make validate           Validate code (pytest, mypy, ruff, black)"
	@echo "  make deploy             Full deployment with validation"
	@echo "  make deploy-dry         Preview deployment without pushing"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make test               Run tests with coverage"
	@echo "  make coverage           Show coverage report"
	@echo "  make fix                Auto-fix code style (black, ruff)"
	@echo "  make lint               Run linting checks"
	@echo "  make type-check         Run type checking with mypy"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@echo "  make build              Build Docker image"
	@echo "  make docker-shell       Start Python shell in Docker"
	@echo ""
	@echo "$(GREEN)Cleanup:$(NC)"
	@echo "  make clean              Remove build artifacts and cache"
	@echo ""
	@echo "$(YELLOW)For more info: ./$(INFRA)/validate.sh --help | ./$(INFRA)/deploy-build-push.sh --help$(NC)"

## ========== VIRTUAL ENVIRONMENT ==========

venv: ## Create Python virtual environment
	@test -d $(VENV) || (echo "Creating virtual environment..." && python3 -m venv $(VENV))
	@echo "$(GREEN)✓ Virtual environment ready$(NC)"
	@echo "Activate with: source $(VENV_BIN)/activate"

## ========== VALIDATION & TESTING ==========

validate: venv ## Validate code (pytest, mypy, ruff, black)
	@. $(VENV_BIN)/activate && ./$(INFRA)/validate.sh

validate-verbose: venv ## Validate with verbose output
	@. $(VENV_BIN)/activate && ./$(INFRA)/validate.sh -v

validate-quick: venv ## Quick validation (ruff only, skip slow checks)
	@. $(VENV_BIN)/activate && ./$(INFRA)/validate.sh --quick

fix: venv ## Auto-fix code style issues (black, ruff)
	@. $(VENV_BIN)/activate && ./$(INFRA)/validate.sh --fix

test: venv ## Run tests with coverage
	@$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=term-missing -v

test-quiet: venv ## Run tests without output
	@$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=term --quiet

test-unit: venv ## Run only unit tests
	@$(PYTHON) -m pytest $(TESTS) -m unit -v

test-integration: venv ## Run only integration tests
	@$(PYTHON) -m pytest $(TESTS) -m integration -v

coverage: venv ## Generate and show HTML coverage report
	@$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=html
	@echo "Coverage report generated at htmlcov/index.html"

lint: venv ## Run linting checks (ruff)
	@$(VENV_BIN)/ruff check $(SRC) $(TESTS)

type-check: venv ## Run type checking (mypy)
	@$(VENV_BIN)/mypy $(SRC)

format-check: venv ## Check code formatting (black)
	@$(VENV_BIN)/black $(SRC) $(TESTS) --check

## ========== DEPLOYMENT ==========

deploy: ## Full deployment with validation (builds, tags, pushes to ECR)
	@./$(INFRA)/deploy-build-push.sh

deploy-dry: ## Preview deployment without pushing
	@./$(INFRA)/deploy-build-push.sh --dry-run

deploy-dry-verbose: ## Preview deployment with verbose output
	@./$(INFRA)/deploy-build-push.sh --dry-run --verbose

deploy-skip-validation: ## Deploy without validation checks (dangerous)
	@./$(INFRA)/deploy-build-push.sh --skip-validation

deploy-no-cache: ## Deploy without Docker layer cache
	@./$(INFRA)/deploy-build-push.sh --no-cache

deploy-verbose: ## Deploy with verbose output
	@./$(INFRA)/deploy-build-push.sh --verbose

## ========== DOCKER OPERATIONS ==========

build: ## Build Docker image locally
	docker build -t maptimize:dev -f $(INFRA)/Dockerfile .

run-dev: ## Run Docker container in dev mode (with volume mount)
	docker run -it --rm \
		-v $$(pwd):/app \
		-e ENVIRONMENT=development \
		maptimize:dev bash

docker-shell: ## Start Python shell in Docker
	docker run -it --rm \
		-v $$(pwd):/app \
		maptimize:dev $(PYTHON)

docker-logs: ## Show Docker container logs
	docker logs -f maptimize-dev 2>/dev/null || echo "Container not running"

## ========== SETUP & CLEANUP ==========

install: venv ## Install project dependencies
	@$(PIP) install -e .

install-dev: venv ## Install project with dev dependencies
	@$(PIP) install -e ".[dev]"

install-upgrade: venv ## Upgrade all dependencies
	@$(PIP) install --upgrade pip
	@$(PIP) install -e ".[dev]" --upgrade

clean: ## Remove build artifacts, cache, and temp files
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/
	@echo "$(GREEN)Clean complete$(NC)"

clean-venv: ## Remove virtual environment (WARNING: destructive)
	@rm -rf $(VENV)
	@echo "$(GREEN)Virtual environment removed$(NC)"

## ========== UTILITY ==========

show-config: ## Show Maptimize configuration
	@echo "$(BLUE)Maptimize Configuration$(NC)"
	@echo "Source: $(SRC)"
	@echo "Tests: $(TESTS)"
	@echo "Infrastructure: $(INFRA)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Venv: $(VENV)"

deps: venv ## Show installed dependencies
	@$(PIP) list | grep -E "pytest|mypy|black|ruff|slack-bolt|pydantic"

check-tools: ## Check if required tools are installed
	@echo "Checking required tools..."
	@command -v docker >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) Docker" || echo "$(YELLOW)✗$(NC) Docker not found"
	@command -v aws >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) AWS CLI" || echo "$(YELLOW)✗$(NC) AWS CLI not found"
	@command -v python3 >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) Python 3" || echo "$(YELLOW)✗$(NC) Python 3 not found"
	@command -v git >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) Git" || echo "$(YELLOW)✗$(NC) Git not found"
	@test -d $(VENV) && echo "$(GREEN)✓$(NC) Venv exists" || echo "$(YELLOW)✗$(NC) Venv not found (run: make venv)"
