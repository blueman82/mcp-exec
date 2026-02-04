#!/usr/bin/env bash
#
# deploy-build-push.sh - Deploy AskSplunk to ECR with validation gate
#
# This script validates code (pytest, ruff, black), then builds,
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
#   --no-deploy       Build and push only, don't deploy to server
#   --reindex         Force re-index ChromaDB (clears existing collection)
#

set -euo pipefail

# ========== CONSTANTS & VARIABLES ==========
# Load .env.test if it exists (for AWS_PROFILE)
SCRIPT_DIR_TMP="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT_TMP="$(cd "${SCRIPT_DIR_TMP}/.." && pwd)"
if [ -f "${PROJECT_ROOT_TMP}/.env.test" ]; then
    source "${PROJECT_ROOT_TMP}/.env.test"
fi

# AWS Configuration (can be overridden by .env.test or environment)
AWS_REGION="${AWS_REGION:-eu-west-1}"
AWS_PROFILE="${AWS_PROFILE:-campaign_prod_v7}"
AWS_ACCOUNT_ID="483013340174"
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPOSITORY="asksplunk"

# Server Configuration
INSTANCE_HOST="asksplunk-prod"
APP_DIR="/opt/asksplunk"

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATE_SCRIPT="${SCRIPT_DIR}/validate.sh"
DOCKERFILE="${PROJECT_ROOT}/Dockerfile"
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
NO_DEPLOY=false
REINDEX=false

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
${BOLD}AskSplunk Deployment Script${NC}

Deploy AskSplunk to ECR with automatic validation and version increment.

${BOLD}Usage:${NC}
  ./deploy-build-push.sh [options]

${BOLD}Options:${NC}
  -h, --help              Show this help message
  -d, --dry-run           Show what would be done without pushing
  -v, --verbose           Verbose output
  --skip-validation       Skip local validation checks
  --no-cache              Build Docker image without cache
  --no-deploy             Build and push only, don't deploy to server
  --reindex               Force re-index ChromaDB (clears existing collection)

${BOLD}Deployment Flow:${NC}
  1. Validate code (pytest, ruff, black)
  2. Get latest version from ECR
  3. Increment semantic version (auto-detect type)
  4. Build Docker image
  5. Tag image with new version
  6. Authenticate with ECR
  7. Push image to ECR
  8. Deploy to EC2 server

${BOLD}Examples:${NC}
  ./deploy-build-push.sh                         # Full deployment
  ./deploy-build-push.sh --dry-run               # Preview without pushing
  ./deploy-build-push.sh --skip-validation       # Skip validation checks
  ./deploy-build-push.sh --no-deploy             # Build and push only
  ./deploy-build-push.sh --reindex               # Deploy and force re-index schema

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
        --no-deploy)
            NO_DEPLOY=true
            shift
            ;;
        --reindex)
            REINDEX=true
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
    if git log "$(git describe --tags --abbrev=0 2>/dev/null || echo 'HEAD~10')..HEAD" --oneline 2>/dev/null | grep -qi "feat"; then
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

deploy_to_server() {
    local version=$1

    log_section "Deploying to ${INSTANCE_HOST}"

    # Set indexer flags based on REINDEX option
    local INDEXER_FLAGS=""
    if [ "$REINDEX" = true ]; then
        INDEXER_FLAGS="--force"
        log_info "Force re-index enabled: ChromaDB collection will be cleared"
    fi

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would SSH to $INSTANCE_HOST and restart container"
        return 0
    fi

    # Check SSH connectivity
    log_info "Checking SSH connectivity..."
    if ! ssh -q -o ConnectTimeout=10 ${INSTANCE_HOST} exit 2>/dev/null; then
        log_error "Cannot connect to ${INSTANCE_HOST}"
        log_warning "Ensure SSH config is set up:"
        echo ""
        echo "Host asksplunk-prod"
        echo "    HostName 34.242.6.61"
        echo "    User harrison"
        echo "    ProxyJump balabit"
        echo ""
        return 1
    fi
    log_success "SSH connection successful"

    # Copy docker-compose file to server (via temp location due to permissions)
    log_info "Copying docker-compose.yml to server..."
    scp "${PROJECT_ROOT}/docker-compose.production.yml" "${INSTANCE_HOST}:/tmp/docker-compose.yml"
    ssh ${INSTANCE_HOST} "sudo mkdir -p ${APP_DIR} && sudo mv /tmp/docker-compose.yml ${APP_DIR}/docker-compose.yml && sudo chown \$(whoami) ${APP_DIR}/docker-compose.yml"
    
    # Copy schema file if it exists
    if [ -f "${PROJECT_ROOT}/docs/schema/campaign_prod_schema.json" ]; then
        log_info "Copying schema file to server..."
        scp "${PROJECT_ROOT}/docs/schema/campaign_prod_schema.json" "${INSTANCE_HOST}:/tmp/campaign_prod_schema.json"
        ssh ${INSTANCE_HOST} "sudo mkdir -p ${APP_DIR}/docs/schema && sudo mv /tmp/campaign_prod_schema.json ${APP_DIR}/docs/schema/ && sudo chown -R \$(whoami) ${APP_DIR}/docs"
    fi

    # Copy indexer script to server
    log_info "Copying indexer script to server..."
    scp "${SCRIPT_DIR}/run-indexer.py" "${INSTANCE_HOST}:/tmp/run-indexer.py"

    log_info "Deploying to server..."
    if ssh ${INSTANCE_HOST} "
        echo 'Pulling new image (using ECR credential helper)...'
        sudo docker pull ${ECR_REPO}/${ECR_REPOSITORY}:latest
        
        echo 'Stopping old container...'
        cd ${APP_DIR} && sudo docker compose down || true
        
        echo 'Starting new container...'
        cd ${APP_DIR} && sudo docker compose up -d
        
        echo 'Waiting for services to start...'
        sleep 10
        cd ${APP_DIR} && sudo docker compose ps
        
        echo 'Running indexer check...'
        sudo docker cp /tmp/run-indexer.py asksplunk-bot-prod:/tmp/run-indexer.py
        sudo docker exec asksplunk-bot-prod python /tmp/run-indexer.py ${INDEXER_FLAGS}
    "; then
        log_success "Deployed to $INSTANCE_HOST successfully"
    else
        log_error "Failed to deploy to $INSTANCE_HOST"
        return 1
    fi
}

# ========== MAIN EXECUTION ==========

log_section "AskSplunk Deployment"

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
        log_info "Run './validate.sh --fix' to auto-fix style issues."
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
if [ "$NO_DEPLOY" = true ]; then
    log_warning "Skipping deployment to server (--no-deploy)"
else
    deploy_to_server "$NEW_VERSION" || exit 1
fi

# Success
log_section "Deployment Summary"
log_success "Deployment complete!"
echo ""
echo "Version:     $NEW_VERSION"
echo "Repository:  ${ECR_REPO}/${ECR_REPOSITORY}"
echo "Image:       ${ECR_REPO}/${ECR_REPOSITORY}:${NEW_VERSION}"
if [ "$NO_DEPLOY" != true ]; then
    echo "Server:      ${INSTANCE_HOST}"
fi

if [ "$DRY_RUN" = true ]; then
    echo ""
    log_warning "This was a dry run. No images were actually pushed."
fi

echo ""
echo "Post-deployment commands:"
echo "  View logs:     ssh ${INSTANCE_HOST} 'cd ${APP_DIR} && docker compose logs -f'"
echo "  Check status:  ssh ${INSTANCE_HOST} 'docker ps'"
echo "  Restart:       ssh ${INSTANCE_HOST} 'cd ${APP_DIR} && docker compose restart'"
echo ""

exit 0
