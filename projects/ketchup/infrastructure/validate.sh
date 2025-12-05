#!/usr/bin/env bash
#
# validate.sh - Local CI validation for Ketchup
#
# This script runs all validation checks (pytest, ruff, black, isort) before
# any Docker build or ECR push. All checks must pass for deployment to proceed.
#
# Usage: ./validate.sh [options]
#   -h, --help        Show this help message
#   -v, --verbose     Verbose output with detailed results
#   --fix             Auto-fix code style issues (black, ruff, isort)
#   --quick           Skip slow checks (only run ruff)
#   --no-tests        Skip pytest (only run linting)
#

set -euo pipefail

# ========== CONSTANTS & VARIABLES ==========
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PACKAGES_DIR="${PROJECT_ROOT}/packages"
TESTS_DIR="${PROJECT_ROOT}/tests"
VENV_DIR="${PROJECT_ROOT}/tests/setup/.venv"

# Load .env.test if it exists (for AWS_PROFILE)
if [ -f "${PROJECT_ROOT}/.env.test" ]; then
    source "${PROJECT_ROOT}/.env.test"
fi

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
NO_TESTS=false

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
${BOLD}Ketchup Local CI Validation${NC}

Run all validation checks before deployment. All checks must pass.

${BOLD}Usage:${NC}
  ./validate.sh [options]

${BOLD}Options:${NC}
  -h, --help          Show this help message
  -v, --verbose       Verbose output with detailed results
  --fix               Auto-fix code style issues (black, ruff, isort)
  --quick             Skip slow checks (only run ruff)
  --no-tests          Skip pytest (only run linting)

${BOLD}Validation Checks:${NC}
  1. ruff             Linting (imports, style, warnings)
  2. black            Code formatting check
  3. isort            Import sorting check
  4. pytest           Unit tests

${BOLD}Examples:${NC}
  ./validate.sh                  # Run all validation checks
  ./validate.sh --verbose        # Run with detailed output
  ./validate.sh --fix            # Auto-fix style issues
  ./validate.sh --quick          # Quick check (ruff only)
  ./validate.sh --no-tests       # Linting only, skip tests

${BOLD}Pre-deployment:${NC}
  This script is called automatically by deploy-ketchup.sh unless
  --skip-validation is passed. You can also run it manually before
  committing changes.

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
        --no-tests)
            NO_TESTS=true
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

check_ruff() {
    log_section "Ruff - Linting"

    if [ "$FIX" = true ]; then
        log_info "Auto-fixing with ruff..."
        if ruff check "$PACKAGES_DIR" "$TESTS_DIR" --fix --quiet 2>/dev/null; then
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
        if ruff check "$PACKAGES_DIR" "$TESTS_DIR" --quiet 2>/dev/null; then
            log_success "No linting issues found"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Linting issues found"
            if [ "$VERBOSE" = true ]; then
                ruff check "$PACKAGES_DIR" "$TESTS_DIR"
            else
                log_info "Run with --verbose to see details, or --fix to auto-fix"
            fi
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("ruff")
            return 1
        fi
    fi
}

check_black() {
    log_section "Black - Code Formatting"

    if [ "$FIX" = true ]; then
        log_info "Auto-fixing code formatting..."
        if black "$PACKAGES_DIR" "$TESTS_DIR" --quiet 2>/dev/null; then
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
        if black "$PACKAGES_DIR" "$TESTS_DIR" --check --quiet 2>/dev/null; then
            log_success "Code formatting is correct"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Code formatting issues found"
            if [ "$VERBOSE" = true ]; then
                black "$PACKAGES_DIR" "$TESTS_DIR" --diff
            else
                log_info "Run with --verbose to see details, or --fix to auto-fix"
            fi
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("black")
            return 1
        fi
    fi
}

check_isort() {
    log_section "isort - Import Sorting"

    if [ "$FIX" = true ]; then
        log_info "Auto-fixing import sorting..."
        if isort "$PACKAGES_DIR" "$TESTS_DIR" --quiet 2>/dev/null; then
            log_success "Imports sorted successfully"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "isort failed"
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("isort")
            return 1
        fi
    else
        log_info "Checking import sorting..."
        if isort "$PACKAGES_DIR" "$TESTS_DIR" --check --quiet 2>/dev/null; then
            log_success "Import sorting is correct"
            ((CHECKS_PASSED++))
            return 0
        else
            log_error "Import sorting issues found"
            if [ "$VERBOSE" = true ]; then
                isort "$PACKAGES_DIR" "$TESTS_DIR" --diff
            else
                log_info "Run with --verbose to see details, or --fix to auto-fix"
            fi
            ((CHECKS_FAILED++))
            FAILED_CHECKS+=("isort")
            return 1
        fi
    fi
}

check_pytest() {
    log_section "PyTest - Unit Tests"

    log_info "Running unit tests..."

    local pytest_args=("$TESTS_DIR/unit" "--ignore=$TESTS_DIR/setup")

    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    else
        pytest_args+=("-q" "--tb=line")
    fi

    cd "$PROJECT_ROOT"
    if PYTHONPATH="$PROJECT_ROOT" pytest "${pytest_args[@]}"; then
        log_success "All tests passed"
        ((CHECKS_PASSED++))
        return 0
    else
        log_error "Tests failed"
        ((CHECKS_FAILED++))
        FAILED_CHECKS+=("pytest")
        return 1
    fi
}

# ========== MAIN EXECUTION ==========

log_section "Ketchup Local CI Validation"
log_info "Project root: $PROJECT_ROOT"
log_info "Packages dir: $PACKAGES_DIR"
log_info "Tests dir: $TESTS_DIR"

# Verify directories exist
if [ ! -d "$PACKAGES_DIR" ]; then
    log_error "Packages directory not found: $PACKAGES_DIR"
    exit 1
fi

if [ ! -d "$TESTS_DIR" ]; then
    log_error "Tests directory not found: $TESTS_DIR"
    exit 1
fi

# Check if tools are available
for tool in ruff black isort pytest; do
    if ! command -v $tool &> /dev/null; then
        log_warning "$tool not found in PATH"
        if [ -d "$VENV_DIR" ]; then
            log_info "Activating virtual environment..."
            source "${VENV_DIR}/bin/activate"
        else
            log_error "Please run 'make setup' in tests/setup/ first"
            exit 1
        fi
    fi
done

# Run checks
check_ruff || true

if [ "$QUICK" != true ]; then
    check_black || true
    check_isort || true

    if [ "$NO_TESTS" != true ]; then
        check_pytest || true
    fi
fi

# ========== SUMMARY ==========
log_section "Validation Results"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ All Validation Stages Passed${NC}"
    echo ""
    echo -e "${GREEN}Validation Stages:${NC}"
    echo "  ✓ Linting (ruff)"
    if [ "$QUICK" != true ]; then
        echo "  ✓ Code Formatting (black)"
        echo "  ✓ Import Sorting (isort)"
        if [ "$NO_TESTS" != true ]; then
            echo "  ✓ Unit Tests (pytest)"
        fi
    fi
    echo ""
    echo -e "${GREEN}${BOLD}Ready to build and deploy!${NC}"
    exit 0
else
    log_error "Validation failed. Fix the errors above:"
    echo ""
    for check in "${FAILED_CHECKS[@]}"; do
        echo -e "${RED}  ✗ ${check}${NC}"
    done
    echo ""
    if [ "$FIX" != true ]; then
        log_info "Try './validate.sh --fix' to auto-fix style issues."
    fi
    exit 1
fi
