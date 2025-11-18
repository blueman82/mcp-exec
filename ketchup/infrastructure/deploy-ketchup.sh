#!/usr/bin/env bash
#
# deploy-ketchup.sh - Automated deployment script for Ketchup services
#
# This script automates the deployment process for Ketchup services to production
# environments following the standard pattern: build locally, push to ECR, deploy
# versioned images to production servers.
#
# Usage: ./deploy-ketchup.sh [options]
#

# Exit on error, undefined variables, and propagate pipe failures
set -euo pipefail

# ========== CONSTANTS & VARIABLES ==========
# ECR repository
ECR_REPO="483013340174.dkr.ecr.eu-west-1.amazonaws.com"
AWS_REGION="eu-west-1"
AWS_PROFILE="campaign_prod_v7"

# Production servers
PROD1_SERVER="ketchup-prod1.campaign.adobe.com"
PROD2_SERVER="ketchup-prod2.campaign.adobe.com"
PROD_DIR="/opt/ketchup"

# Docker files
DOCKERFILE_APP="infrastructure/Dockerfile.app-multistage"
DOCKERFILE_UPDATER="infrastructure/Dockerfile.updater"
DOCKERFILE_MCP="infrastructure/Dockerfile.mcp-jira"
DOCKERFILE_STATUS_UPDATER="infrastructure/Dockerfile.status-updater"
DOCKERFILE_JIRA_REPORTER="infrastructure/Dockerfile.jira-reporter"
DOCKERFILE_ACCESS_MONITOR="infrastructure/Dockerfile.access-monitor"
DOCKERFILE_MAINTENANCE_FETCHER="infrastructure/Dockerfile.maintenance_fetcher"

# Service names
SERVICES=("ketchup-app" "ketchup-metadata-updater" "mcp-jira" "ketchup-status-updater" "ketchup-jira-reporter" "ketchup-access-monitor" "ketchup-maintenance-fetcher")

# Default values
VERSION=""
SKIP_BUILD=false
SKIP_PUSH=false
NO_GIT_COMMIT=false
PROD1_ONLY=false
PROD2_ONLY=false
ROLLBACK=""
FORCE=false
VERIFY_ONLY=false
CHECK_VERSION=false
SKIP_COMPOSE_SYNC=false
NO_CACHE=false

# Remote paths
PROD_DIR="/opt/ketchup"

# ========== COMPOSE SYNC (PER-SERVER) ==========
# Copy local docker-compose.yml to a target server if it differs from the remote.
# This ensures environment flag changes (e.g., KETCHUP_USE_TYPED_DI, KETCHUP_TYPED_DI_FALLBACK)
# and service config changes are applied, not only image tag updates.
sync_docker_compose_if_changed() {
    local server=$1
    log_section "Docker Compose Sync ($server)"

    # Compare local compose with remote; copy if different
    if ! diff -q infrastructure/docker-compose.yml <(ssh "$server" "sudo cat ${PROD_DIR}/docker-compose.yml") >/dev/null 2>&1; then
        log_info "docker-compose.yml differs on $server. Uploading updated file..."
        scp infrastructure/docker-compose.yml "$server":/tmp/docker-compose.yml
        ssh "$server" "sudo mv /tmp/docker-compose.yml ${PROD_DIR}/docker-compose.yml && sudo chown root:root ${PROD_DIR}/docker-compose.yml"

        # Server-specific overrides after upload
        if [[ "$server" == "$PROD2_SERVER" ]]; then
            # Enable status updater on prod2 and ensure TypedDI + fallback enabled during canary
            ssh "$server" "sudo sed -i 's|KETCHUP_STATUS_UPDATER_ENABLED=false|KETCHUP_STATUS_UPDATER_ENABLED=true|' ${PROD_DIR}/docker-compose.yml; \
                             sudo sed -i 's|KETCHUP_USE_TYPED_DI=false|KETCHUP_USE_TYPED_DI=true|' ${PROD_DIR}/docker-compose.yml; \
                             sudo sed -i 's|KETCHUP_TYPED_DI_FALLBACK=false|KETCHUP_TYPED_DI_FALLBACK=true|' ${PROD_DIR}/docker-compose.yml; \
                             sudo sed -i 's|KETCHUP_USE_ASYNC_MCP=true|KETCHUP_USE_ASYNC_MCP=false|' ${PROD_DIR}/docker-compose.yml"
        else
            # Ensure legacy DI on prod1
            ssh "$server" "sudo sed -i 's|KETCHUP_USE_TYPED_DI=false|KETCHUP_USE_TYPED_DI=true|' ${PROD_DIR}/docker-compose.yml; \
                             sudo sed -i 's|KETCHUP_TYPED_DI_FALLBACK=false|KETCHUP_TYPED_DI_FALLBACK=true|' ${PROD_DIR}/docker-compose.yml; \
                             sudo sed -i 's|KETCHUP_USE_ASYNC_MCP=true|KETCHUP_USE_ASYNC_MCP=false|' ${PROD_DIR}/docker-compose.yml"
        fi

        log_success "docker-compose.yml synchronized to $server"
    else
        log_info "docker-compose.yml is already up to date on $server"
    fi
}

# ========== COLOR DEFINITIONS ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
UNDERLINE='\033[4m'
NC='\033[0m' # No Color

# ========== HELPER FUNCTIONS ==========
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_section() {
    echo -e "\n${BOLD}${CYAN}===== $1 =====${NC}\n"
}

confirm() {
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    read -p "$1 [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# ========== MAIN FUNCTIONS ==========
show_help() {
    echo -e "${BOLD}Ketchup Deployment Script${NC}"
    echo -e "Automates the deployment process for Ketchup services."
    echo
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  ./deploy-ketchup.sh [options]"
    echo
    echo -e "${BOLD}Options:${NC}"
    echo -e "  -h, --help                Show this help message"
    echo -e "  -v, --version VERSION     Specify version to deploy (optional - auto-increments if not specified)"
    echo -e "  -s, --skip-build          Skip building Docker images"
    echo -e "  -p, --skip-push           Skip pushing to ECR"
    echo -e "  -1, --prod1-only          Deploy only to prod1 server"
    echo -e "  -2, --prod2-only          Deploy only to prod2 server"
    echo -e "  -r, --rollback VERSION    Rollback to specified version"
    echo -e "  -f, --force               Skip confirmation prompts"
    echo -e "      --no-git-commit       Do not commit local docker-compose.yml changes"
    echo -e "  --verify                  Only verify deployment status"
    echo -e "  --check-version           Check current versions in ECR and exit"
    echo -e "  --skip-compose-sync       Skip docker-compose.yml sync (useful when called by wrapper scripts)"
    echo
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  ./deploy-ketchup.sh                      # Auto-increment version and deploy"
    echo -e "  ./deploy-ketchup.sh --version v2.0.34    # Deploy specific version"
    echo -e "  ./deploy-ketchup.sh --rollback v2.0.33   # Rollback to v2.0.33"
    echo -e "  ./deploy-ketchup.sh --verify             # Verify deployment status"
    echo -e "  ./deploy-ketchup.sh --check-version      # Check current versions"
    echo
}

check_preflight() {
    log_section "Pre-flight Checks"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    else
        log_info "Docker is installed: $(docker --version)"
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    else
        log_info "AWS CLI is installed: $(aws --version)"
    fi
    
    # Check AWS profile
    if ! aws configure list-profiles | grep -q "$AWS_PROFILE"; then
        log_error "AWS profile '$AWS_PROFILE' not found. Please configure it first."
        exit 1
    else
        log_info "AWS profile '$AWS_PROFILE' is configured"
    fi
    
    # Check SSH access to production servers if not skipping deployment
    if [ "$VERIFY_ONLY" = false ] && [ "$CHECK_VERSION" = false ]; then
        if [ "$PROD2_ONLY" = false ]; then  # Deploy to prod1 unless --prod2-only
            log_info "Checking SSH access to $PROD1_SERVER..."
            if ! ssh -q -o BatchMode=yes -o ConnectTimeout=5 "$PROD1_SERVER" exit &>/dev/null; then
                log_error "Cannot SSH to $PROD1_SERVER. Check your SSH configuration."
                exit 1
            fi
            log_success "SSH access to $PROD1_SERVER confirmed"
        fi
        
        if [ "$PROD1_ONLY" = false ]; then  # Deploy to prod2 unless --prod1-only
            log_info "Checking SSH access to $PROD2_SERVER..."
            if ! ssh -q -o BatchMode=yes -o ConnectTimeout=5 "$PROD2_SERVER" exit &>/dev/null; then
                log_error "Cannot SSH to $PROD2_SERVER. Check your SSH configuration."
                exit 1
            fi
            log_success "SSH access to $PROD2_SERVER confirmed"
        fi
    fi
    
    log_success "All pre-flight checks passed"
}

check_current_versions() {
    log_section "Current Versions in ECR"
    
    for service in "${SERVICES[@]}"; do
        echo -e "${BOLD}${service}:${NC}"
        
        # Check if repository has any images first
        local image_count=$(aws ecr describe-images \
            --repository-name="${service}" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --filter tagStatus=TAGGED \
            --query 'length(imageDetails)' \
            --output text 2>/dev/null || echo "0")
            
        if [ "$image_count" = "0" ] || [ "$image_count" = "None" ]; then
            echo -e "${YELLOW}(no versions - first build)${NC}"
        else
            # Repository has images, list the versions
            aws ecr describe-images \
                --repository-name="${service}" \
                --profile "$AWS_PROFILE" \
                --region "$AWS_REGION" \
                --filter tagStatus=TAGGED \
                --query 'imageDetails[*].imageTags[]' \
                --output text | tr '\t' '\n' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -10 || echo -e "${YELLOW}(no valid version tags)${NC}"
        fi
        echo
    done
    
    if [ "$CHECK_VERSION" = true ]; then
        exit 0
    fi
}

check_running_versions() {
    local server=$1
    log_info "Checking running versions on $server..."
    
    ssh "$server" "sudo docker ps --format 'table {{.Names}}\t{{.Image}}' | grep -E '(ketchup-app|mcp-jira|metadata-updater|status-updater|jira-reporter)'"
}

build_images() {
    log_section "Building Docker Images"
    
    if [ "$SKIP_BUILD" = true ]; then
        log_warning "Skipping build phase as requested"
        return
    fi
    
    if [ -z "$VERSION" ]; then
        log_error "Version is required for building images"
        exit 1
    fi
    
    # Build ketchup-app
    log_info "Building ketchup-app:$VERSION..."
    BUILD_ARGS="-t ketchup-app:$VERSION -f $DOCKERFILE_APP --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        log_info "Building without cache..."
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build ketchup-app"
        exit 1
    }
    log_success "Built ketchup-app:$VERSION"
    
    # Build ketchup-metadata-updater
    log_info "Building ketchup-metadata-updater:$VERSION..."
    BUILD_ARGS="-t ketchup-metadata-updater:$VERSION -f $DOCKERFILE_UPDATER --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build ketchup-metadata-updater"
        exit 1
    }
    log_success "Built ketchup-metadata-updater:$VERSION"
    
    # Build mcp-jira
    log_info "Building mcp-jira:$VERSION..."
    BUILD_ARGS="-t mcp-jira:$VERSION -f $DOCKERFILE_MCP --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build mcp-jira"
        exit 1
    }
    log_success "Built mcp-jira:$VERSION"
    
    # Build ketchup-status-updater
    log_info "Building ketchup-status-updater:$VERSION..."
    BUILD_ARGS="-t ketchup-status-updater:$VERSION -f $DOCKERFILE_STATUS_UPDATER --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build ketchup-status-updater"
        exit 1
    }
    log_success "Built ketchup-status-updater:$VERSION"
    
    # Build ketchup-jira-reporter
    log_info "Building ketchup-jira-reporter:$VERSION..."
    BUILD_ARGS="-t ketchup-jira-reporter:$VERSION -f $DOCKERFILE_JIRA_REPORTER --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build ketchup-jira-reporter"
        exit 1
    }
    log_success "Built ketchup-jira-reporter:$VERSION"
    
    # Build ketchup-access-monitor
    log_info "Building ketchup-access-monitor:$VERSION..."
    BUILD_ARGS="-t ketchup-access-monitor:$VERSION -f $DOCKERFILE_ACCESS_MONITOR --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build ketchup-access-monitor"
        exit 1
    }
    log_success "Built ketchup-access-monitor:$VERSION"

    # Build ketchup-maintenance-fetcher
    log_info "Building ketchup-maintenance-fetcher:$VERSION..."
    BUILD_ARGS="-t ketchup-maintenance-fetcher:$VERSION -f $DOCKERFILE_MAINTENANCE_FETCHER --platform linux/amd64"
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    docker build $BUILD_ARGS . || {
        log_error "Failed to build ketchup-maintenance-fetcher"
        exit 1
    }
    log_success "Built ketchup-maintenance-fetcher:$VERSION"

}

tag_images() {
    log_section "Tagging Images for ECR"
    
    if [ "$SKIP_BUILD" = true ] && [ "$SKIP_PUSH" = false ]; then
        log_warning "Build was skipped, but tagging is required for push. Checking if images exist locally..."
        
        for service in "${SERVICES[@]}"; do
            if ! docker image inspect "$service:$VERSION" &>/dev/null; then
                log_error "Image $service:$VERSION does not exist locally. Cannot tag."
                exit 1
            fi
        done
    fi
    
    if [ "$SKIP_PUSH" = true ]; then
        log_warning "Skipping tagging as push is also skipped"
        return
    fi
    
    # Tag all images
    for service in "${SERVICES[@]}"; do
        log_info "Tagging $service:$VERSION for ECR..."
        docker tag "$service:$VERSION" "$ECR_REPO/$service:$VERSION" || {
            log_error "Failed to tag $service:$VERSION"
            exit 1
        }
        log_success "Tagged $ECR_REPO/$service:$VERSION"
    done
}

authenticate_ecr() {
    log_section "Authenticating with ECR"
    
    if [ "$SKIP_PUSH" = true ]; then
        log_warning "Skipping ECR authentication as push is skipped"
        return
    fi
    
    log_info "Logging in to ECR..."
    aws ecr get-login-password \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" | \
        docker login \
            --username AWS \
            --password-stdin "$ECR_REPO" || {
        log_error "Failed to authenticate with ECR"
        exit 1
    }
    log_success "Authenticated with ECR"
}

ensure_ecr_repositories() {
    log_section "Ensuring ECR Repositories Exist"
    
    if [ "$SKIP_PUSH" = true ]; then
        log_warning "Skipping ECR repository check as push is skipped"
        return
    fi
    
    for service in "${SERVICES[@]}"; do
        log_info "Checking if ECR repository '$service' exists..."
        
        if ! aws ecr describe-repositories \
            --repository-names "$service" \
            --region "$AWS_REGION" \
            --profile "$AWS_PROFILE" \
            &>/dev/null; then
            
            log_warning "ECR repository '$service' does not exist. Creating it..."
            
            aws ecr create-repository \
                --repository-name "$service" \
                --region "$AWS_REGION" \
                --profile "$AWS_PROFILE" \
                &>/dev/null || {
                log_error "Failed to create ECR repository '$service'"
                exit 1
            }
            
            log_success "Created ECR repository '$service'"
        else
            log_info "ECR repository '$service' already exists"
        fi
    done
    
    log_success "All ECR repositories verified/created"
}

push_images() {
    log_section "Pushing Images to ECR"
    
    if [ "$SKIP_PUSH" = true ]; then
        log_warning "Skipping push phase as requested"
        return
    fi
    
    # Push all images
    for service in "${SERVICES[@]}"; do
        log_info "Pushing $service:$VERSION to ECR..."
        docker push "$ECR_REPO/$service:$VERSION" || {
            log_error "Failed to push $service:$VERSION to ECR"
            exit 1
        }
        log_success "Pushed $ECR_REPO/$service:$VERSION"
    done
}

deploy_to_server() {
    local server=$1
    local version=$2
    
    log_section "Deploying to $server"
    
    log_info "Updating docker-compose.yml with version $version..."
    local update_cmd=""
    for service in "${SERVICES[@]}"; do
        # Update both short form (service:version) and full ECR URLs - expand variables locally
        update_cmd+="sudo sed -i 's|${ECR_REPO}/${service}:v[0-9.]*|${ECR_REPO}/${service}:${version}|g' /opt/ketchup/docker-compose.yml; "
        update_cmd+="sudo sed -i 's|${service}:v[0-9.]*|${service}:${version}|g' /opt/ketchup/docker-compose.yml; "
    done

    # Deploy status-updater and metadata-updater ONLY to prod1, exclude from prod2
    if [[ "$server" == "$PROD1_SERVER" ]]; then
        log_info "Deploying to prod1 (including status-updater and metadata-updater as singletons)..."
        # Ensure TypedDI + fallback on prod1
        update_cmd+="sudo sed -i 's|KETCHUP_USE_TYPED_DI=false|KETCHUP_USE_TYPED_DI=true|g' /opt/ketchup/docker-compose.yml; "
        update_cmd+="sudo sed -i 's|KETCHUP_TYPED_DI_FALLBACK=false|KETCHUP_TYPED_DI_FALLBACK=true|g' /opt/ketchup/docker-compose.yml; "
        update_cmd+="sudo sed -i 's|KETCHUP_STATUS_UPDATER_ENABLED=false|KETCHUP_STATUS_UPDATER_ENABLED=true|g' /opt/ketchup/docker-compose.yml; "
        ssh "$server" "cd $PROD_DIR && \
            $update_cmd \
            sudo docker-compose pull && \
            sudo docker-compose up -d --force-recreate" || {
            log_error "Failed to deploy to $server"
            return 1
        }
    else
        # Deploy all services EXCEPT status-updater, metadata-updater, jira-reporter, and maintenance-fetcher on prod2
        log_info "Deploying to prod2 (core services only, excluding singleton services)..."
        # Ensure TypedDI + fallback on prod2
        update_cmd+="sudo sed -i 's|KETCHUP_USE_TYPED_DI=false|KETCHUP_USE_TYPED_DI=true|g' /opt/ketchup/docker-compose.yml; "
        update_cmd+="sudo sed -i 's|KETCHUP_TYPED_DI_FALLBACK=false|KETCHUP_TYPED_DI_FALLBACK=true|g' /opt/ketchup/docker-compose.yml; "
        update_cmd+="sudo sed -i 's|KETCHUP_STATUS_UPDATER_ENABLED=true|KETCHUP_STATUS_UPDATER_ENABLED=false|g' /opt/ketchup/docker-compose.yml; "

        # Explicitly stop and remove singleton services that should only run on prod1
        cleanup_cmd="sudo docker-compose stop ketchup-status-updater ketchup-metadata-updater ketchup-jira-reporter ketchup-maintenance-fetcher 2>/dev/null; "
        cleanup_cmd+="sudo docker-compose rm -f ketchup-status-updater ketchup-metadata-updater ketchup-jira-reporter ketchup-maintenance-fetcher 2>/dev/null; "

        ssh "$server" "cd $PROD_DIR && \
            $update_cmd \
            $cleanup_cmd \
            sudo docker-compose pull ketchup-app mcp-jira nginx ketchup-access-monitor && \
            sudo docker-compose up -d --force-recreate --remove-orphans ketchup-app mcp-jira nginx ketchup-access-monitor" || {
            log_error "Failed to deploy to $server"
            return 1
        }
    fi
    
    log_success "Deployed version $version to $server"
    return 0
}

verify_deployment() {
    log_section "Verifying Deployment"
    
    if [ "$PROD2_ONLY" = false ]; then  # Verify prod1 unless --prod2-only
        log_info "Verifying deployment on $PROD1_SERVER..."
        check_running_versions "$PROD1_SERVER"
    fi
    
    if [ "$PROD1_ONLY" = false ]; then  # Verify prod2 unless --prod1-only
        log_info "Verifying deployment on $PROD2_SERVER..."
        check_running_versions "$PROD2_SERVER"
    fi
    
    log_success "Verification complete"
}

rollback_deployment() {
    local version=$1
    
    log_section "Rolling Back to Version $version"
    
    if [ -z "$version" ]; then
        log_error "Version is required for rollback"
        exit 1
    fi
    
    # Confirm rollback
    if ! confirm "Are you sure you want to roll back to version $version?"; then
        log_warning "Rollback cancelled"
        exit 0
    fi
    
    if [ "$PROD2_ONLY" = false ]; then  # Rollback prod1 unless --prod2-only
        log_info "Rolling back $PROD1_SERVER to version $version..."
        deploy_to_server "$PROD1_SERVER" "$version" || {
            log_error "Failed to roll back $PROD1_SERVER"
            exit 1
        }
    fi
    
    if [ "$PROD1_ONLY" = false ]; then  # Rollback prod2 unless --prod1-only
        log_info "Rolling back $PROD2_SERVER to version $version..."
        deploy_to_server "$PROD2_SERVER" "$version" || {
            log_error "Failed to roll back $PROD2_SERVER"
            exit 1
        }
    fi
    
    log_success "Rollback to version $version complete"
}

# ========== PARSE COMMAND LINE ARGUMENTS ==========
# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -s|--skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -p|--skip-push)
            SKIP_PUSH=true
            shift
            ;;
        --no-git-commit)
            NO_GIT_COMMIT=true
            shift
            ;;
        -1|--prod1-only)
            PROD1_ONLY=true
            shift
            ;;
        -2|--prod2-only)
            PROD2_ONLY=true
            shift
            ;;
        -r|--rollback)
            ROLLBACK="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        --check-version)
            CHECK_VERSION=true
            shift
            ;;
        --skip-compose-sync)
            SKIP_COMPOSE_SYNC=true
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

# ========== MAIN EXECUTION ==========
# Display script header
echo -e "${BOLD}${MAGENTA}"
echo "╔═════════════════════════════════════════╗"
echo "║         Ketchup Deployment Script       ║"
echo "╚═════════════════════════════════════════╝"
echo -e "${NC}"

# Run pre-flight checks
check_preflight

# Check current versions in ECR
check_current_versions

# If only verifying deployment
if [ "$VERIFY_ONLY" = true ]; then
    verify_deployment
    exit 0
fi

# If rolling back
if [ -n "$ROLLBACK" ]; then
    rollback_deployment "$ROLLBACK"
    verify_deployment
    exit 0
fi

# Validate version if not rolling back or just verifying
if [ -z "$VERSION" ]; then
    # Auto-increment version from the latest in ECR
    log_section "Auto-incrementing Version"
    
    # Get the latest version from ECR (check first service as reference)
    latest_version=$(aws ecr describe-images \
        --repository-name="${SERVICES[0]}" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --filter tagStatus=TAGGED \
        --query 'imageDetails[*].imageTags[]' \
        --output text 2>/dev/null | tr '\t' '\n' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
    
    if [ -z "$latest_version" ]; then
        # No version found, start with v2.1.0
        VERSION="v2.1.0"
        log_warning "No existing versions found. Starting with $VERSION"
    else
        # Parse version and increment patch number
        version_regex="^v([0-9]+)\.([0-9]+)\.([0-9]+)$"
        if [[ $latest_version =~ $version_regex ]]; then
            major="${BASH_REMATCH[1]}"
            minor="${BASH_REMATCH[2]}"
            patch="${BASH_REMATCH[3]}"
            new_patch=$((patch + 1))
            VERSION="v${major}.${minor}.${new_patch}"
            log_info "Latest version: $latest_version"
            log_info "New version: $VERSION"
        else
            log_error "Failed to parse latest version: $latest_version"
            exit 1
        fi
    fi
fi

# Validate version format
if ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_error "Invalid version format. Expected format: v<major>.<minor>.<patch> (e.g., v2.0.34)"
    exit 1
fi

# Update local docker-compose.yml with new version
update_local_docker_compose() {
    log_section "Updating Local docker-compose.yml"
    
    log_info "Updating docker-compose.yml with version $VERSION..."
    for service in "${SERVICES[@]}"; do
        # Update both short form (service:version) and full ECR URLs
        sed -i.bak "s|${ECR_REPO}/${service}:v[0-9.]*|${ECR_REPO}/${service}:${VERSION}|g" infrastructure/docker-compose.yml || {
            log_error "Failed to update $service version in infrastructure/docker-compose.yml"
            exit 1
        }
        sed -i.bak "s|${service}:v[0-9.]*|${service}:${VERSION}|g" infrastructure/docker-compose.yml || {
            log_error "Failed to update $service version in infrastructure/docker-compose.yml"
            exit 1
        }
    done
    
    # Clean up backup files
    rm -f infrastructure/docker-compose.yml.bak
    
    if [ "$NO_GIT_COMMIT" = true ]; then
        log_warning "Skipping git commit for docker-compose.yml (per --no-git-commit)"
    else
        # Commit the changes to git
        if git diff --quiet infrastructure/docker-compose.yml; then
            log_info "No changes to commit (infrastructure/docker-compose.yml already at version $VERSION)"
        else
            git add infrastructure/docker-compose.yml
            git commit -m "Update docker-compose.yml to version $VERSION

Automated version update during deployment" || {
                log_warning "Failed to commit docker-compose.yml changes. Continue anyway..."
            }
            log_success "Committed docker-compose.yml version update"
        fi
    fi
    
    log_success "Updated local docker-compose.yml to version $VERSION"
}

# Confirm deployment
if ! confirm "Are you sure you want to deploy version $VERSION to production?"; then
    log_warning "Deployment cancelled"
    exit 0
fi

# Update local docker-compose.yml first
update_local_docker_compose

# Build images
build_images

# Tag images
tag_images

# Authenticate with ECR
authenticate_ecr

# Ensure ECR repositories exist
ensure_ecr_repositories

# Push images
push_images

# Deploy to production servers
if [ "$PROD2_ONLY" = false ]; then  # Deploy to prod1 unless --prod2-only
    # Ensure docker-compose.yml is in sync on prod1 (so flags are respected)
    if [ "$SKIP_COMPOSE_SYNC" = false ]; then
        sync_docker_compose_if_changed "$PROD1_SERVER"
    fi
    deploy_to_server "$PROD1_SERVER" "$VERSION"
fi

if [ "$PROD1_ONLY" = false ]; then  # Deploy to prod2 unless --prod1-only
    # Ensure docker-compose.yml is in sync on prod2 (so flags are respected)
    if [ "$SKIP_COMPOSE_SYNC" = false ]; then
        sync_docker_compose_if_changed "$PROD2_SERVER"
    fi
    deploy_to_server "$PROD2_SERVER" "$VERSION"
fi

# Verify deployment
verify_deployment

log_section "Deployment Summary"
echo -e "${GREEN}${BOLD}Deployment of version $VERSION completed successfully!${NC}"
echo -e "Services deployed:"
for service in "${SERVICES[@]}"; do
    echo -e " - ${CYAN}$service:$VERSION${NC}"
done
echo

exit 0
