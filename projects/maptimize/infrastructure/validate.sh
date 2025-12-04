#!/usr/bin/env bash
#
# validate.sh - Local CI validation for Maptimize
#
# This script runs all validation checks (pytest, mypy, ruff, black) before
# any Docker build or ECR push. All checks must pass for deployment to proceed.
#
# Usage: ./validate.sh [options]
#   -h, --help        Show this help message
#   -v, --verbose     Verbose output with detailed results
#   --fix             Auto-fix code style issues (black, ruff)
#   --quick           Skip slow checks (only run ruff)
#

set -euo pipefail

# ========== CONSTANTS & VARIABLES ==========
# Directories
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="${PROJECT_ROOT}/src/maptimize"
TESTS_DIR="${PROJECT_ROOT}/tests"
VENV_DIR="${PROJECT_ROOT}/.venv"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    source "${VENV_DIR}/bin/activate"
fi

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
VERBOSE=false
FIX=false
QUICK=false

# Track results
CHECKS_PASSED=0
CHECKS_FAILED=0
FAILED_CHECKS=()

# ========== HELPER FUNCTIONS ==========
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_section() {
    echo -e "\n${BOLD}${CYAN}===== $1 =====${NC}\n" >&2
}

show_help() {
    cat << EOF
${BOLD}Maptimize Local CI Validation${NC}

Run all validation checks before deployment. All checks must pass.

${BOLD}Usage:${NC}
  ./validate.sh [options]

${BOLD}Options:${NC}
  -h, --help          Show this help message
  -v, --verbose       Verbose output with detailed results
  --fix               Auto-fix code style issues (black, ruff)
  --quick             Skip slow checks (only run ruff)

${BOLD}Validation Checks:${NC}
  1. black            Code formatting check
  2. ruff             Linting (imports, style, warnings)
  3. mypy             Static type checking
  4. pytest           Unit and integration tests with coverage

${BOLD}Examples:${NC}
  ./validate.sh                  # Run all validation checks
  ./validate.sh --verbose        # Run with detailed output
  ./validate.sh --fix            # Auto-fix style issues
  ./validate.sh --quick          # Quick check (ruff only)

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --fix)
            FIX=true
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# ========== VALIDATION CHECKS ==========

check_black() {
    log_section "Black - Code Formatting"

    if [ "$FIX" = true ]; then
        log_info "Auto-fixing code formatting..."
        if black "$SRC_DIR" "$TESTS_DIR" --quiet; then
            log_success "Code formatted successfully"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Black formatting failed"
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("black")
            return 1
        fi
    else
        log_info "Checking code formatting..."
        if black "$SRC_DIR" "$TESTS_DIR" --check --quiet; then
            log_success "Code formatting is correct"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Code formatting issues found. Run 'black $SRC_DIR $TESTS_DIR' to fix"
            if [ "$VERBOSE" = true ]; then
                black "$SRC_DIR" "$TESTS_DIR" --diff
            fi
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("black")
            return 1
        fi
    fi
}

check_ruff() {
    log_section "Ruff - Linting"

    if [ "$FIX" = true ]; then
        log_info "Auto-fixing with ruff..."
        if ruff check "$SRC_DIR" "$TESTS_DIR" --fix --quiet; then
            log_success "Ruff issues fixed"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Ruff auto-fix failed or found unfixable issues"
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("ruff")
            return 1
        fi
    else
        log_info "Running linting checks..."
        if ruff check "$SRC_DIR" "$TESTS_DIR" --quiet; then
            log_success "No linting issues found"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Linting issues found. Run 'ruff check $SRC_DIR $TESTS_DIR' to see details"
            if [ "$VERBOSE" = true ]; then
                ruff check "$SRC_DIR" "$TESTS_DIR"
            fi
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("ruff")
            return 1
        fi
    fi
}

check_mypy() {
    log_section "MyPy - Type Checking"

    log_info "Running type checking..."
    if mypy "$SRC_DIR" --pretty; then
        log_success "Type checking passed"
        ((CHECKS_PASSED++))
        return 0
    else
        log_error "Type checking failed"
        ((CHECKS_FAILED++))
        FAILED_CHECKS+=("mypy")
        return 1
    fi
}

check_pytest() {
    log_section "PyTest - Unit and Integration Tests"

    log_info "Running tests with coverage..."
    if [ "$VERBOSE" = true ]; then
        pytest "$TESTS_DIR" --cov="$SRC_DIR" --cov-report=term-missing -v
    else
        pytest "$TESTS_DIR" --cov="$SRC_DIR" --cov-report=term --quiet
    fi

    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        log_success "All tests passed"
        ((CHECKS_PASSED++))
        return 0
    else
        log_error "Tests failed (exit code: $exit_code)"
        ((CHECKS_FAILED++))
        FAILED_CHECKS+=("pytest")
        return 1
    fi
}

# ========== MAIN EXECUTION ==========

log_section "Maptimize Local CI Validation"
log_info "Project root: $PROJECT_ROOT"
log_info "Source dir: $SRC_DIR"
log_info "Tests dir: $TESTS_DIR"

# Verify directories exist
if [ ! -d "$SRC_DIR" ]; then
    log_error "Source directory not found: $SRC_DIR"
    exit 1
fi

if [ ! -d "$TESTS_DIR" ]; then
    log_error "Tests directory not found: $TESTS_DIR"
    exit 1
fi

# Run checks
check_black
check_ruff

if [ "$QUICK" != true ]; then
    check_mypy
    check_pytest
fi

# ========== SUMMARY ==========
log_section "Validation Results"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ All Validation Stages Passed${NC}"
    echo ""
    echo -e "${GREEN}Validation Stages:${NC}"
    echo "  ✓ Code Formatting (black)"
    echo "  ✓ Linting (ruff)"
    if [ "$QUICK" != true ]; then
        echo "  ✓ Type Checking (mypy)"
        echo "  ✓ Unit & Integration Tests (pytest)"
    fi
    echo ""
    echo -e "${GREEN}${BOLD}Ready to commit and push!${NC}"
    exit 0
else
    log_error "Validation failed. Fix the errors above:"
    echo ""
    for check in "${FAILED_CHECKS[@]}"; do
        echo -e "${RED}  ✗ ${check}${NC}"
    done
    echo ""
    log_error "Try again after fixing errors."
    exit 1
fi
