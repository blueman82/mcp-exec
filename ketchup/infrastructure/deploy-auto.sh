#!/usr/bin/env bash
#
# deploy-auto.sh - Fully automated deployment script for Ketchup services
#
# This script automatically detects changes, determines version increment type,
# creates git tags, and deploys with zero user input required.
#
# Usage: ./deploy-auto.sh [options]
#

# Exit on error, undefined variables, and propagate pipe failures
set -euo pipefail

# ========== CONSTANTS & VARIABLES ==========
# ECR repository
ECR_REPO="483013340174.dkr.ecr.eu-west-1.amazonaws.com"
AWS_REGION="eu-west-1"
AWS_PROFILE="campaign_prod_v7"

# Main deployment script
DEPLOY_SCRIPT="$(dirname "$0")/deploy-ketchup.sh"

# Service to check for version (we use ketchup-app as reference)
VERSION_SERVICE="ketchup-app"

# Git configuration
GIT_TAG_PREFIX="release-"

# Default settings
DRY_RUN=false
NO_TAG=false
FORCE=false
CUSTOM_MESSAGE=""
SKIP_GIT_CHECKS=false
RELEASE_TYPE="auto"  # auto, patch, minor, major
NO_CACHE=false

# Target servers (optional scoping)
PROD1_ONLY=false
PROD2_ONLY=false

# Args to forward to deploy-ketchup.sh
CHILD_ARGS=()

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
    echo -e "${BOLD}Ketchup Auto Deployment Script${NC}"
    echo -e "Fully automated deployment with zero user input required."
    echo
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  ./deploy-auto.sh [options]"
    echo
    echo -e "${BOLD}Options:${NC}"
    echo -e "  -h, --help                Show this help message"
    echo -e "  -d, --dry-run             Show what would be done without actually deploying"
    echo -e "  -n, --no-tag              Skip creating git tag"
    echo -e "  -f, --force               Skip all confirmations"
    echo -e "  -m, --message \"TEXT\"      Custom release message"
    echo -e "  -t, --type TYPE           Force release type: patch, minor, or major"
    echo -e "  --skip-git-checks         Skip git status checks"
    echo -e "  --no-cache                Build Docker images without cache"
    echo -e "  --prod1-only              Deploy only to prod1 server"
    echo -e "  --prod2-only              Deploy only to prod2 server"
    echo
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  ./deploy-auto.sh                     # Fully automatic deployment"
    echo -e "  ./deploy-auto.sh --dry-run           # Show what would happen without deploying"
    echo -e "  ./deploy-auto.sh --type minor        # Force a minor version increment"
    echo -e "  ./deploy-auto.sh -m \"Hotfix deploy\"  # Deploy with custom message"
    echo
}

# ========== GIT FUNCTIONS ==========
check_git_status() {
    log_section "Git Status Check"
    
    if [ "$SKIP_GIT_CHECKS" = true ]; then
        log_warning "Skipping git status checks as requested"
        return 0
    fi
    
    # Check if we're in a git repository
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        log_error "Not in a git repository"
        exit 1
    fi
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        log_warning "Uncommitted changes detected"
        git status --short
        
        if [ "$DRY_RUN" = true ] || [ "$FORCE" = true ]; then
            log_warning "Proceeding despite uncommitted changes"
            return 0
        fi
        
        read -p "Uncommitted changes detected. Continue anyway? [y/N] " response
        case "$response" in
            [yY][eE][sS]|[yY]) 
                log_warning "Proceeding with uncommitted changes"
                return 0
                ;;
            *)
                log_error "Aborting deployment due to uncommitted changes"
                log_info "Commit or stash your changes before deploying"
                exit 1
                ;;
        esac
    fi
    
    log_success "Git repository is clean"
}

determine_release_type() {
    if [ "$RELEASE_TYPE" != "auto" ]; then
        log_info "Using specified release type: $RELEASE_TYPE"
        echo "$RELEASE_TYPE"
        return 0
    fi
    
    log_section "Determining Release Type"
    
    # For auto detection, analyze only recent commits (last 5 commits)
    # This avoids issues with old/stale git tags vs ECR versions
    local commit_range="HEAD~5..HEAD"
    
    log_info "Analyzing commits from $commit_range"
    
    # Get commit messages
    local commit_messages
    commit_messages=$(git log "$commit_range" --pretty=format:"%s" 2>/dev/null || echo "")
    
    # Check for breaking changes
    if echo "$commit_messages" | grep -i -E "BREAKING:|breaking change" &>/dev/null; then
        log_info "Breaking change detected in commit messages"
        echo "major"
        return 0
    fi
    
    # Check for features
    if echo "$commit_messages" | grep -i -E "feat:|feature:|new feature" &>/dev/null; then
        log_info "New feature detected in commit messages"
        echo "minor"
        return 0
    fi
    
    # Check for significant file changes
    local changed_files
    changed_files=$(git diff --name-only "$commit_range" 2>/dev/null || echo "")
    
    # Filter out version-only docker-compose.yml changes
    local significant_files=""
    if echo "$changed_files" | grep -E "Dockerfile" &>/dev/null; then
        significant_files="Dockerfiles"
    fi
    
    # Check if docker-compose.yml has non-version changes
    if echo "$changed_files" | grep "docker-compose.yml" &>/dev/null; then
        # Check if the only changes are version numbers
        local docker_compose_diff
        docker_compose_diff=$(git diff "$commit_range" -- infrastructure/docker-compose.yml 2>/dev/null || echo "")
        
        # If there are changes beyond just version numbers, consider it significant
        if echo "$docker_compose_diff" | grep -v -E "^\+.*:v[0-9]+\.[0-9]+\.[0-9]+|^\-.*:v[0-9]+\.[0-9]+\.[0-9]+|@@|index|diff --git" | grep -E "^\+|^\-" &>/dev/null; then
            significant_files="$significant_files docker-compose.yml"
        fi
    fi
    
    # Check other infrastructure files
    if echo "$changed_files" | grep -v "docker-compose.yml" | grep "infrastructure/" &>/dev/null; then
        significant_files="$significant_files infrastructure-files"
    fi
    
    # If we found significant infrastructure changes, trigger minor release
    if [ -n "$significant_files" ]; then
        log_info "Significant infrastructure changes detected: $significant_files"
        echo "minor"
        return 0
    fi
    
    # Default to patch
    log_info "No major/minor changes detected, defaulting to patch"
    echo "patch"
}

create_git_tag() {
    if [ "$NO_TAG" = true ] || [ "$DRY_RUN" = true ]; then
        log_info "Skipping git tag creation"
        return 0
    fi
    
    log_section "Creating Git Tag"
    
    local version=$1
    local tag_name="${GIT_TAG_PREFIX}${version}"
    local tag_message
    
    if [ -n "$CUSTOM_MESSAGE" ]; then
        tag_message="$CUSTOM_MESSAGE"
    else
        tag_message="Release $version"
    fi
    
    log_info "Creating git tag: $tag_name"
    log_info "Tag message: $tag_message"
    
    if ! git tag -a "$tag_name" -m "$tag_message"; then
        log_error "Failed to create git tag"
        exit 1
    fi
    
    log_success "Created git tag: $tag_name"
    
    # Push tag if not in dry run mode
    log_info "Pushing git tag to remote..."
    if ! git push origin "$tag_name"; then
        log_warning "Failed to push git tag to remote"
        log_info "You can push it later with: git push origin $tag_name"
    else
        log_success "Pushed git tag to remote"
    fi
}

# ========== VERSION MANAGEMENT FUNCTIONS ==========
get_latest_version() {
    log_info "Retrieving latest version from ECR..."
    
    # Get the latest version from ECR
    local latest_version
    latest_version=$(aws ecr describe-images \
        --repository-name="$VERSION_SERVICE" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --filter tagStatus=TAGGED \
        --query 'imageDetails[*].imageTags[]' \
        --output text | tr '\t' '\n' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
    
    if [ -z "$latest_version" ]; then
        log_error "Failed to retrieve latest version from ECR"
        exit 1
    fi
    
    log_success "Latest version: $latest_version"
    echo "$latest_version"
}

increment_version() {
    local version=$1
    local part=$2  # major, minor, or patch
    
    # Extract version components
    if [[ ! "$version" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        log_error "Invalid version format: $version"
        exit 1
    fi
    
    local major="${BASH_REMATCH[1]}"
    local minor="${BASH_REMATCH[2]}"
    local patch="${BASH_REMATCH[3]}"
    
    # Increment the requested part
    case "$part" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            log_error "Invalid version part: $part"
            exit 1
            ;;
    esac
    
    # Return the new version
    echo "v$major.$minor.$patch"
}

# ========== DEPLOYMENT FUNCTIONS ==========
deploy_version() {
    local version=$1
    shift
    
    log_section "Deployment"
    
    local deploy_args=("--version" "$version" "--no-git-commit" "--skip-compose-sync")
    
    # Add force flag if specified
    if [ "$FORCE" = true ]; then
        deploy_args+=("--force")
    fi
    
    # Add any additional arguments
    deploy_args+=("$@")
    
    if [ "$DRY_RUN" = true ]; then
        log_info "DRY RUN: Would execute: $DEPLOY_SCRIPT ${deploy_args[*]}"
    else
        log_info "Executing: $DEPLOY_SCRIPT ${deploy_args[*]}"
        "$DEPLOY_SCRIPT" "${deploy_args[@]}"
    fi
}

# ========== MAIN EXECUTION ==========
# Display script header
echo -e "${BOLD}${MAGENTA}"
echo "╔═════════════════════════════════════════╗"
echo "║      Ketchup Auto Deployment Script     ║"
echo "╚═════════════════════════════════════════╝"
echo -e "${NC}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -n|--no-tag)
            NO_TAG=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -m|--message)
            CUSTOM_MESSAGE="$2"
            shift 2
            ;;
        -t|--type)
            RELEASE_TYPE="$2"
            if [[ ! "$RELEASE_TYPE" =~ ^(patch|minor|major)$ ]]; then
                log_error "Invalid release type: $RELEASE_TYPE. Must be patch, minor, or major."
                exit 1
            fi
            shift 2
            ;;
        --skip-git-checks)
            SKIP_GIT_CHECKS=true
            shift
            ;;
        --prod1-only)
            PROD1_ONLY=true
            CHILD_ARGS+=("--prod1-only")
            shift
            ;;
        --prod2-only)
            PROD2_ONLY=true
            CHILD_ARGS+=("--prod2-only")
            shift
            ;;
        --skip-build)
            CHILD_ARGS+=("--skip-build")
            shift
            ;;
        --skip-push)
            CHILD_ARGS+=("--skip-push")
            shift
            ;;
        --verify)
            CHILD_ARGS+=("--verify")
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            CHILD_ARGS+=("--no-cache")
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if deploy-ketchup.sh exists
if [ ! -f "$DEPLOY_SCRIPT" ]; then
    log_error "Main deployment script not found: $DEPLOY_SCRIPT"
    exit 1
fi

# Check if deploy-ketchup.sh is executable
if [ ! -x "$DEPLOY_SCRIPT" ]; then
    log_error "Main deployment script is not executable: $DEPLOY_SCRIPT"
    log_info "Run: chmod +x $DEPLOY_SCRIPT"
    exit 1
fi

# Check git status
check_git_status

# Get the latest version
latest_version=$(get_latest_version)

# Determine release type
release_type=$(determine_release_type)

# Increment version
new_version=$(increment_version "$latest_version" "$release_type")
log_info "New version will be: $latest_version -> $new_version ($release_type)"

# Create git tag
if [ "$DRY_RUN" = false ] && [ "$NO_TAG" = false ]; then
    create_git_tag "$new_version"
fi

# Update docker-compose.yml with the new version (only if not dry run)
if [ "$DRY_RUN" = false ]; then
    log_info "Updating docker-compose.yml with version $new_version"
    
    # Define services that need version updates (matches SERVICES array in deploy-ketchup.sh)
    SERVICES=("ketchup-app" "ketchup-metadata-updater" "mcp-jira" "ketchup-status-updater" "ketchup-jira-reporter" "ketchup-access-monitor" "ketchup-maintenance-fetcher")
    
    # Update version for each service dynamically
    for service in "${SERVICES[@]}"; do
        log_info "Updating $service to $new_version"
        sed -i.bak "s|$service:v[0-9.]*|$service:${new_version}|g" infrastructure/docker-compose.yml
    done
    
    # Clean up backup files
    rm -f infrastructure/docker-compose.yml.bak
    
    log_success "Updated docker-compose.yml with version $new_version"
    
    # Sync docker-compose.yml to servers BEFORE deployment (so new services are defined)
    log_section "Pre-Deployment Docker Compose Sync"
    
    PROD1_SERVER="ketchup-prod1.campaign.adobe.com"
    PROD2_SERVER="ketchup-prod2.campaign.adobe.com"
    
    # Function to sync docker-compose.yml only if different
    sync_compose_if_changed() {
        local server=$1
        local server_name=$2

        log_info "Checking if docker-compose.yml needs syncing to $server_name..."

        # Use diff to compare files (more reliable than checksums, handles line endings properly)
        # Compare local file with remote file via SSH
        if diff -q infrastructure/docker-compose.yml <(ssh "$server" "sudo cat /opt/ketchup/docker-compose.yml 2>/dev/null") >/dev/null 2>&1; then
            log_info "docker-compose.yml on $server_name is already up to date"
            return 0
        fi

        log_info "docker-compose.yml differs, syncing to $server_name..."

        scp infrastructure/docker-compose.yml "$server":/tmp/docker-compose.yml
        ssh "$server" "sudo mv /tmp/docker-compose.yml /opt/ketchup/docker-compose.yml && sudo chown root:root /opt/ketchup/docker-compose.yml"
        log_success "Synced docker-compose.yml to $server_name"
    }
    
    # Determine which servers to sync based on target flags
    if [ "$PROD2_ONLY" != true ]; then
        sync_compose_if_changed "$PROD1_SERVER" "prod1"
    fi
    
    if [ "$PROD1_ONLY" != true ]; then
        sync_compose_if_changed "$PROD2_SERVER" "prod2"
    fi
fi

# Deploy the new version (only forward child-safe args)
if [ ${#CHILD_ARGS[@]} -gt 0 ]; then
    deploy_version "$new_version" "${CHILD_ARGS[@]}"
else
    deploy_version "$new_version"
fi

if [ "$DRY_RUN" = true ]; then
    log_section "Dry Run Summary"
    echo -e "${YELLOW}This was a dry run. No changes were made.${NC}"
    echo -e "Would have deployed version: ${BOLD}$new_version${NC}"
    echo -e "Release type: ${BOLD}$release_type${NC}"
    if [ "$NO_TAG" = false ]; then
        echo -e "Would have created git tag: ${BOLD}${GIT_TAG_PREFIX}${new_version}${NC}"
    fi
else
    log_section "Deployment Summary"
    echo -e "${GREEN}${BOLD}Deployment of version $new_version completed successfully!${NC}"
    echo -e "Release type: ${BOLD}$release_type${NC}"
    if [ "$NO_TAG" = false ]; then
        echo -e "Git tag: ${BOLD}${GIT_TAG_PREFIX}${new_version}${NC}"
    fi
    echo -e "Check running versions with: ${CYAN}$DEPLOY_SCRIPT --verify${NC}"
    log_info "docker-compose.yml was synced before deployment"
fi

exit 0
