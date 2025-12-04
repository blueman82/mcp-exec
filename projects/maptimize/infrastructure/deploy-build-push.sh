#!/usr/bin/env bash
#
# deploy-build-push.sh - Deploy Maptimize to ECR with validation gate
#
# This script validates code (pytest, mypy, ruff, black), then builds,
# tags, and pushes the Docker image to ECR with automatic version increment.
#
# Requires:
#   - Docker installed and running
#   - AWS CLI configured with campaign_prod_v7 profile
#   - validate.sh in the same directory
#
# Usage: ./deploy-build-push.sh [options]
#   -h, --help        Show this help message
#   -d, --dry-run     Show what would be done without pushing
#   -v, --verbose     Verbose output
#   --skip-validation Skip local validation checks
#   --no-cache        Build Docker image without cache
#

set -euo pipefail

# ========== CONSTANTS & VARIABLES ==========
# AWS Configuration
AWS_REGION="eu-west-1"
AWS_PROFILE="campaign_prod_v7"
AWS_ACCOUNT_ID="483013340174"
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPOSITORY="maptimize"

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATE_SCRIPT="${SCRIPT_DIR}/validate.sh"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile"
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
DRY_RUN=false
VERBOSE=false
SKIP_VALIDATION=false
NO_CACHE=false

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
${BOLD}Maptimize Deployment Script${NC}

Deploy Maptimize to ECR with automatic validation and version increment.

${BOLD}Usage:${NC}
  ./deploy-build-push.sh [options]

${BOLD}Options:${NC}
  -h, --help              Show this help message
  -d, --dry-run           Show what would be done without pushing
  -v, --verbose           Verbose output
  --skip-validation       Skip local validation checks
  --no-cache              Build Docker image without cache

${BOLD}Deployment Flow:${NC}
  1. Validate code (pytest, mypy, ruff, black)
  2. Get latest version from ECR
  3. Increment semantic version (auto-detect type)
  4. Build Docker image
  5. Tag image with new version
  6. Authenticate with ECR
  7. Push image to ECR

${BOLD}Examples:${NC}
  ./deploy-build-push.sh                         # Full deployment
  ./deploy-build-push.sh --dry-run               # Preview without pushing
  ./deploy-build-push.sh --dry-run --verbose     # Preview with details
  ./deploy-build-push.sh --skip-validation       # Skip validation checks
  ./deploy-build-push.sh --no-cache              # Build without Docker cache

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# ========== PRE-FLIGHT CHECKS ==========

check_requirements() {
    log_section "Pre-flight Checks"

    # Check Docker
    log_info "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    docker --version > /dev/null 2>&1 || {
        log_error "Docker daemon is not running"
        exit 1
    }
    log_success "Docker is available"

    # Check AWS CLI
    log_info "Checking AWS CLI installation..."
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
    log_success "AWS CLI is available"

    # Check AWS profile
    log_info "Checking AWS profile: $AWS_PROFILE"
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        log_error "Cannot authenticate with AWS profile: $AWS_PROFILE"
        log_error "Configure your AWS credentials and try again"
        exit 1
    fi
    log_success "AWS profile is valid"

    # Check Dockerfile
    if [ ! -f "$DOCKERFILE" ]; then
        log_error "Dockerfile not found: $DOCKERFILE"
        exit 1
    fi
    log_success "Dockerfile found"

    # Check validate.sh
    if [ ! -f "$VALIDATE_SCRIPT" ]; then
        log_error "validate.sh not found: $VALIDATE_SCRIPT"
        exit 1
    fi
    log_success "validate.sh found"
}

# ========== VERSION MANAGEMENT ==========

get_latest_version() {
    log_info "Fetching latest version from ECR..."

    local latest_version=$(
        aws ecr describe-images \
            --repository-name "$ECR_REPOSITORY" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --filter "tagStatus=TAGGED" \
            --query "imageDetails[*].imageTags[]" \
            --output text 2>/dev/null | \
        tr '\t' '\n' | \
        grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | \
        sort -V | \
        tail -1
    )

    if [ -z "$latest_version" ]; then
        log_warning "No version tags found in ECR, starting from v0.1.0"
        echo "v0.1.0"
    else
        echo "$latest_version"
    fi
}

increment_version() {
    local version=$1
    local version_num="${version:1}"  # Remove 'v' prefix
    local parts=(${version_num//./ })

    local major=${parts[0]}
    local minor=${parts[1]}
    local patch=${parts[2]}

    # Auto-detect increment type from git commits
    local increment_type="patch"
    if git log "$(git describe --tags --abbrev=0 2>/dev/null || echo 'HEAD')..HEAD" --oneline 2>/dev/null | grep -qi "^[a-f0-9]*.*feat"; then
        increment_type="minor"
    fi

    case $increment_type in
        major)
            ((major++))
            minor=0
            patch=0
            ;;
        minor)
            ((minor++))
            patch=0
            ;;
        patch|*)
            ((patch++))
            ;;
    esac

    echo "v${major}.${minor}.${patch}"
}

# ========== DOCKER OPERATIONS ==========

build_image() {
    local version=$1

    log_section "Building Docker Image"
    log_info "Building: ${ECR_REPO}/${ECR_REPOSITORY}:${version}"

    local build_args=""
    if [ "$NO_CACHE" = true ]; then
        build_args="--no-cache"
    fi

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would execute: docker buildx build --platform linux/amd64 $build_args -t ${ECR_REPO}/${ECR_REPOSITORY}:${version} -f ${DOCKERFILE} ${PROJECT_ROOT}"
        return 0
    fi

    if docker buildx build \
        --platform linux/amd64 \
        $build_args \
        -t "${ECR_REPO}/${ECR_REPOSITORY}:${version}" \
        -f "$DOCKERFILE" \
        "$PROJECT_ROOT"; then
        log_success "Docker image built successfully: ${version}"
        return 0
    else
        log_error "Docker build failed"
        return 1
    fi
}

tag_latest() {
    local version=$1

    log_section "Tagging Latest"
    log_info "Tagging: ${ECR_REPO}/${ECR_REPOSITORY}:latest"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would execute: docker tag ${ECR_REPO}/${ECR_REPOSITORY}:${version} ${ECR_REPO}/${ECR_REPOSITORY}:latest"
        return 0
    fi

    if docker tag "${ECR_REPO}/${ECR_REPOSITORY}:${version}" "${ECR_REPO}/${ECR_REPOSITORY}:latest"; then
        log_success "Tagged as latest"
        return 0
    else
        log_error "Failed to tag image as latest"
        return 1
    fi
}

authenticate_ecr() {
    log_section "Authenticating with ECR"
    log_info "Region: $AWS_REGION"
    log_info "Account: $AWS_ACCOUNT_ID"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would authenticate with ECR"
        return 0
    fi

    local login_output
    if login_output=$(aws ecr get-login-password \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" 2>&1); then

        if echo "$login_output" | docker login \
            --username AWS \
            --password-stdin \
            "$ECR_REPO" > /dev/null 2>&1; then
            log_success "Authenticated with ECR"
            return 0
        else
            log_error "Docker login failed"
            return 1
        fi
    else
        log_error "Failed to get ECR login token: $login_output"
        return 1
    fi
}

push_image() {
    local version=$1

    log_section "Pushing to ECR"
    log_info "Pushing: ${ECR_REPO}/${ECR_REPOSITORY}:${version}"
    log_info "Also pushing: ${ECR_REPO}/${ECR_REPOSITORY}:latest"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would push ${version} and latest tags to ECR"
        return 0
    fi

    if docker push "${ECR_REPO}/${ECR_REPOSITORY}:${version}"; then
        log_success "Pushed ${version} to ECR"
    else
        log_error "Failed to push ${version} to ECR"
        return 1
    fi

    if docker push "${ECR_REPO}/${ECR_REPOSITORY}:latest"; then
        log_success "Pushed latest to ECR"
        return 0
    else
        log_error "Failed to push latest to ECR"
        return 1
    fi
}

# ========== MAIN EXECUTION ==========

log_section "Maptimize Deployment"

if [ "$DRY_RUN" = true ]; then
    log_warning "DRY RUN MODE - No changes will be made"
fi

# Pre-flight checks
check_requirements

# Validation gate
if [ "$SKIP_VALIDATION" = true ]; then
    log_warning "Skipping validation checks"
else
    log_section "Running Validation Checks"
    if ! "$VALIDATE_SCRIPT" $([ "$VERBOSE" = true ] && echo "-v" || echo ""); then
        log_error "Validation failed. Deployment aborted."
        exit 1
    fi
fi

# Version management
CURRENT_VERSION=$(get_latest_version)
NEW_VERSION=$(increment_version "$CURRENT_VERSION")
log_info "Current version: $CURRENT_VERSION"
log_info "New version: $NEW_VERSION"

# Build and push
build_image "$NEW_VERSION" || exit 1
tag_latest "$NEW_VERSION" || exit 1
authenticate_ecr || exit 1
push_image "$NEW_VERSION" || exit 1

# Deploy to server
log_section "Deploying to maptimize-prod"
MAPTIMIZE_HOST="maptimize-prod.campaign.adobe.com"

if [ "$DRY_RUN" = true ]; then
    log_warning "DRY RUN: Would SSH to $MAPTIMIZE_HOST and restart container"
else
    log_info "Connecting to $MAPTIMIZE_HOST..."
    if ssh -o ConnectTimeout=15 -o StrictHostKeyChecking=no "harrison@${MAPTIMIZE_HOST}" "
        echo 'Pulling new image...'
        sudo docker pull ${ECR_REPO}/${ECR_REPOSITORY}:latest
        echo 'Stopping old container...'
        sudo docker stop maptimize-bot 2>/dev/null || true
        sudo docker rm maptimize-bot 2>/dev/null || true
        echo 'Starting new container...'
        sudo docker run -d --restart=always --name maptimize-bot \
            -e LOG_LEVEL=INFO -e ENVIRONMENT=production \
            -e AWS_REGION=eu-west-1 -e AWS_DEFAULT_REGION=eu-west-1 \
            -e PYTHONUNBUFFERED=1 \
            ${ECR_REPO}/${ECR_REPOSITORY}:latest
        echo 'Verifying...'
        sleep 3
        sudo docker ps | grep maptimize-bot
    "; then
        log_success "Deployed to $MAPTIMIZE_HOST successfully"
    else
        log_error "Failed to deploy to $MAPTIMIZE_HOST"
        exit 1
    fi
fi

# Success
log_section "Deployment Summary"
log_success "Deployment complete!"
log_info "Version: $NEW_VERSION"
log_info "Repository: ${ECR_REPO}/${ECR_REPOSITORY}"
log_info "Image: ${ECR_REPO}/${ECR_REPOSITORY}:${NEW_VERSION}"

if [ "$DRY_RUN" = true ]; then
    log_warning "This was a dry run. No images were actually pushed."
fi

exit 0
