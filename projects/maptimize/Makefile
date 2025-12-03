.PHONY: help validate fix test lint type-check coverage clean deploy deploy-dry deploy-skip-validation build push docker-shell install install-dev

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# Python paths
PYTHON := python3
SRC := src/maptimize
TESTS := tests
INFRA := infrastructure

help: ## Show this help message
	@echo "$(BLUE)Maptimize - Local CI/CD Helpers$(NC)"
	@echo ""
	@echo "$(GREEN)Quick Start:$(NC)"
	@echo "  make validate           Validate code (pytest, mypy, ruff, black)"
	@echo "  make deploy             Full deployment with validation"
	@echo "  make deploy-dry         Preview deployment without pushing"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make install            Install dependencies"
	@echo "  make install-dev        Install dev dependencies"
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

## ========== VALIDATION & TESTING ==========

validate: ## Validate code (pytest, mypy, ruff, black)
	@./$(INFRA)/validate.sh

validate-verbose: ## Validate with verbose output
	@./$(INFRA)/validate.sh -v

validate-quick: ## Quick validation (ruff only, skip slow checks)
	@./$(INFRA)/validate.sh --quick

fix: ## Auto-fix code style issues (black, ruff)
	@./$(INFRA)/validate.sh --fix

test: ## Run tests with coverage
	@$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=term-missing -v

test-quiet: ## Run tests without output
	@$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=term --quiet

test-unit: ## Run only unit tests
	@$(PYTHON) -m pytest $(TESTS) -m unit -v

test-integration: ## Run only integration tests
	@$(PYTHON) -m pytest $(TESTS) -m integration -v

coverage: ## Generate and show HTML coverage report
	@$(PYTHON) -m pytest $(TESTS) --cov=$(SRC) --cov-report=html
	@echo "Coverage report generated at htmlcov/index.html"

lint: ## Run linting checks (ruff)
	@ruff check $(SRC) $(TESTS)

type-check: ## Run type checking (mypy)
	@mypy $(SRC)

format-check: ## Check code formatting (black)
	@black $(SRC) $(TESTS) --check

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

install: ## Install project dependencies
	$(PYTHON) -m pip install -e .

install-dev: ## Install project with dev dependencies
	$(PYTHON) -m pip install -e ".[dev]"

install-upgrade: ## Upgrade all dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]" --upgrade

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

## ========== UTILITY ==========

show-config: ## Show Maptimize configuration
	@echo "$(BLUE)Maptimize Configuration$(NC)"
	@echo "Source: $(SRC)"
	@echo "Tests: $(TESTS)"
	@echo "Infrastructure: $(INFRA)"
	@echo "Python: $$($(PYTHON) --version)"

deps: ## Show installed dependencies
	$(PYTHON) -m pip list | grep -E "pytest|mypy|black|ruff|slack-bolt|pydantic"

check-tools: ## Check if required tools are installed
	@echo "Checking required tools..."
	@command -v docker >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) Docker" || echo "$(YELLOW)✗$(NC) Docker not found"
	@command -v aws >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) AWS CLI" || echo "$(YELLOW)✗$(NC) AWS CLI not found"
	@command -v $(PYTHON) >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) Python 3" || echo "$(YELLOW)✗$(NC) Python 3 not found"
	@command -v git >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) Git" || echo "$(YELLOW)✗$(NC) Git not found"
