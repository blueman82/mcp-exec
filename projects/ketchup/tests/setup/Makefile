# Ketchup Test Runner
#
# Testing commands only. Lint checks are automated via git hooks.
# Run ./setup from project root for initial setup.
#
# Quick Reference:
#   make test-fast      - Critical tests (~10s)
#   make test-parallel  - All unit tests (~15s)
#   make test-unit      - All unit tests serial (~5min)

.PHONY: test test-fast test-parallel test-unit test-integration test-typed-di test-coverage clean help
ARGS?=

VENV?=.venv
SHELL := /bin/bash
export PYTHONDONTWRITEBYTECODE=1

PROJECT_ROOT := $(shell cd ../.. && pwd)

# ============================================================================
# TESTING
# ============================================================================

test-fast:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit/core/typed_di tests/unit/core/config \
	tests/unit/core/utils -v --timeout=10 $(ARGS)

test-parallel:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit --ignore=tests/setup -n auto --timeout=30 $(ARGS)

test-unit:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit --ignore=tests/setup --timeout=30 $(ARGS)

test-integration:
	@echo "Requires AWS_PROFILE=campaign_prod_v7"
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/integration --timeout=60 $(ARGS)

test-typed-di:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit/core/typed_di -v --timeout=10 $(ARGS)

test-coverage:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests/unit --ignore=tests/setup \
	--cov=packages --cov-report=html --cov-report=term-missing --timeout=30 $(ARGS)

test:
	. $(VENV)/bin/activate && cd $(PROJECT_ROOT) && \
	PYTHONPATH=. pytest tests --timeout=60 $(ARGS)

# ============================================================================
# CLEANUP
# ============================================================================

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find $(PROJECT_ROOT) -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned up cache files"

# ============================================================================
# HELP
# ============================================================================

help:
	@echo ""
	@echo "Ketchup Test Commands"
	@echo "====================="
	@echo ""
	@echo "  make test-fast       Critical tests only (~10s)"
	@echo "  make test-parallel   All unit tests, parallel (~15s)"
	@echo "  make test-unit       All unit tests, serial (~5min)"
	@echo "  make test-typed-di   TypedDI validation tests"
	@echo "  make test-integration AWS tests (needs AWS_PROFILE)"
	@echo "  make test-coverage   Tests with coverage report"
	@echo "  make clean           Remove cache files"
	@echo ""
	@echo "Lint checks are automated via git hooks."
	@echo "Run ./check from project root for manual lint."
	@echo ""
