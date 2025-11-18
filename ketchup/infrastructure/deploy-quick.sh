#!/usr/bin/env bash
#
# deploy-quick.sh - Quick deployment helper for Ketchup services
#
# This script provides shortcuts for common deployment scenarios by wrapping
# the main deploy-ketchup.sh script with smart version detection and user-friendly
# shortcuts.
#
# Usage: ./deploy-quick.sh [command]
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

# Debug mode (set to true for verbose output)
DEBUG=false

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

log_debug() {
    if [ "$DEBUG" = true ]; then
        echo -e "${MAGENTA}[DEBUG]${NC} $1"
    fi
}

log_section() {
    echo -e "\n${BOLD}${CYAN}===== $1 =====${NC}\n"
}

confirm() {
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

# ========== VERSION MANAGEMENT FUNCTIONS ==========
get_latest_version() {
    log_info "Retrieving latest version from ECR..."
    
    # Get the latest version from ECR
    local latest_version
    
    # First check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI first."
        exit 1
    fi
    
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq first."
        exit 1
    fi
    
    # Try to get versions from ECR
    local versions_json
    versions_json=$(aws ecr describe-images \
        --repository-name="$VERSION_SERVICE" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'sort_by(imageDetails,& imagePushedAt)[-10:].imageTags[]' \
        --output json 2>/dev/null) || {
            log_error "Failed to retrieve versions from ECR. Check your AWS credentials and connection."
            exit 1
        }
    
    log_debug "Raw versions from ECR: $versions_json"
    
    # Extract versions matching our format
    latest_version=$(echo "$versions_json" | jq -r '.[]' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
    
    if [ -z "$latest_version" ]; then
        log_error "No valid versions found in ECR. Check repository: $VERSION_SERVICE"
        exit 1
    fi
    
    log_success "Latest version: $latest_version"
    echo "$latest_version"
}

get_previous_version() {
    log_info "Retrieving previous version from ECR..."
    
    # Get the previous version from ECR
    local previous_version
    
    # Check if AWS CLI and jq are available
    if ! command -v aws &> /dev/null || ! command -v jq &> /dev/null; then
        log_error "AWS CLI or jq not found. Please install required tools."
        exit 1
    fi
    
    # Try to get versions from ECR
    local versions_json
    versions_json=$(aws ecr describe-images \
        --repository-name="$VERSION_SERVICE" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'sort_by(imageDetails,& imagePushedAt)[-10:].imageTags[]' \
        --output json 2>/dev/null) || {
            log_error "Failed to retrieve versions from ECR. Check your AWS credentials and connection."
            exit 1
        }
    
    # Extract versions matching our format and get the second-to-last one
    local versions
    versions=$(echo "$versions_json" | jq -r '.[]' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V)
    
    # Count the number of versions
    local version_count
    version_count=$(echo "$versions" | wc -l)
    
    if [ "$version_count" -lt 2 ]; then
        log_error "Not enough versions found in ECR to determine previous version."
        exit 1
    fi
    
    previous_version=$(echo "$versions" | tail -2 | head -1)
    
    if [ -z "$previous_version" ]; then
        log_error "Failed to determine previous version."
        exit 1
    fi
    
    log_success "Previous version: $previous_version"
    echo "$previous_version"
}

increment_version() {
    local version=$1
    local part=$2  # major, minor, or patch
    
    log_debug "Incrementing version: $version ($part)"
    
    # Validate input parameters
    if [ -z "$version" ]; then
        log_error "Version parameter is empty"
        exit 1
    fi
    
    if [ -z "$part" ]; then
        log_error "Part parameter is empty"
        exit 1
    fi
    
    # Extract version components using regex
    if [[ ! "$version" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        log_error "Invalid version format: '$version'. Expected format: v<major>.<minor>.<patch> (e.g., v2.0.34)"
        log_debug "Regex match failed for: '$version'"
        exit 1
    fi
    
    # Extract components from regex match
    local major="${BASH_REMATCH[1]}"
    local minor="${BASH_REMATCH[2]}"
    local patch="${BASH_REMATCH[3]}"
    
    log_debug "Parsed version: major=$major, minor=$minor, patch=$patch"
    
    # Validate extracted components
    if [ -z "$major" ] || [ -z "$minor" ] || [ -z "$patch" ]; then
        log_error "Failed to extract version components from: $version"
        exit 1
    fi
    
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
            log_error "Invalid version part: '$part'. Must be 'major', 'minor', or 'patch'."
            exit 1
            ;;
    esac
    
    # Return the new version
    local new_version="v$major.$minor.$patch"
    log_debug "New version: $new_version"
    echo "$new_version"
}

# ========== DEPLOYMENT FUNCTIONS ==========
deploy_version() {
    local version=$1
    shift
    
    log_section "Deploying Version $version"
    
    # Execute the main deployment script
    "$DEPLOY_SCRIPT" --version "$version" "$@"
}

deploy_increment() {
    local part=$1
    shift
    
    # Get the latest version
    local latest_version
    latest_version=$(get_latest_version)
    
    # Increment the version
    local new_version
    new_version=$(increment_version "$latest_version" "$part")
    
    log_info "Incrementing $part version: $latest_version -> $new_version"
    
    # Confirm deployment
    if ! confirm "Deploy $part release $new_version?"; then
        log_warning "Deployment cancelled"
        exit 0
    fi
    
    # Deploy the new version
    deploy_version "$new_version" "$@"
}

rollback_to_previous() {
    # Get the previous version
    local previous_version
    previous_version=$(get_previous_version)
    
    log_section "Rolling Back to Previous Version $previous_version"
    
    # Confirm rollback
    if ! confirm "Roll back to previous version $previous_version?"; then
        log_warning "Rollback cancelled"
        exit 0
    fi
    
    # Execute the main deployment script with rollback option
    "$DEPLOY_SCRIPT" --rollback "$previous_version" "$@"
}

emergency_rollback() {
    log_section "Emergency Rollback"
    
    # Get the latest 5 versions
    log_info "Retrieving recent versions from ECR..."
    local versions
    versions=$(aws ecr describe-images \
        --repository-name="$VERSION_SERVICE" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'sort_by(imageDetails,& imagePushedAt)[-10:].imageTags[]' \
        --output json | jq -r '.[]' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -5)
    
    if [ -z "$versions" ]; then
        log_error "Failed to retrieve versions from ECR"
        exit 1
    fi
    
    # Display versions for selection
    echo -e "${BOLD}Select a version to roll back to:${NC}"
    local i=1
    local version_array=()
    while IFS= read -r version; do
        echo -e "  ${BOLD}$i)${NC} $version"
        version_array+=("$version")
        i=$((i + 1))
    done <<< "$versions"
    
    # Get user selection
    local selection
    read -p "Enter selection [1-${#version_array[@]}]: " selection
    
    # Validate selection
    if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt "${#version_array[@]}" ]; then
        log_error "Invalid selection"
        exit 1
    fi
    
    # Get selected version
    local selected_version="${version_array[$((selection - 1))]}"
    
    log_info "Selected version: $selected_version"
    
    # Confirm emergency rollback
    if ! confirm "EMERGENCY ROLLBACK to version $selected_version?"; then
        log_warning "Emergency rollback cancelled"
        exit 0
    fi
    
    # Execute the main deployment script with rollback option and force flag
    "$DEPLOY_SCRIPT" --rollback "$selected_version" --force "$@"
}

show_help() {
    echo -e "${BOLD}Ketchup Quick Deployment Helper${NC}"
    echo -e "Provides shortcuts for common deployment scenarios."
    echo
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  ./deploy-quick.sh [command] [options]"
    echo
    echo -e "${BOLD}Commands:${NC}"
    echo -e "  patch               Deploy patch release (increment patch version)"
    echo -e "  minor               Deploy minor release (increment minor version)"
    echo -e "  major               Deploy major release (increment major version)"
    echo -e "  rollback            Quick rollback to previous version"
    echo -e "  emergency           Emergency rollback with version selection"
    echo -e "  version             Show latest version in ECR"
    echo -e "  help                Show this help message"
    echo
    echo -e "${BOLD}Options:${NC}"
    echo -e "  Any additional options will be passed to deploy-ketchup.sh"
    echo -e "  --debug             Enable debug output"
    echo
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  ./deploy-quick.sh patch"
    echo -e "  ./deploy-quick.sh minor --prod1-only"
    echo -e "  ./deploy-quick.sh rollback"
    echo -e "  ./deploy-quick.sh emergency"
    echo
}

show_menu() {
    echo -e "${BOLD}${MAGENTA}"
    echo "╔═════════════════════════════════════════╗"
    echo "║       Ketchup Quick Deployment Menu     ║"
    echo "╚═════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BOLD}Select an action:${NC}"
    echo -e "  ${BOLD}1)${NC} Deploy patch release (increment patch version)"
    echo -e "  ${BOLD}2)${NC} Deploy minor release (increment minor version)"
    echo -e "  ${BOLD}3)${NC} Deploy major release (increment major version)"
    echo -e "  ${BOLD}4)${NC} Quick rollback to previous version"
    echo -e "  ${BOLD}5)${NC} Emergency rollback"
    echo -e "  ${BOLD}6)${NC} Show latest version"
    echo -e "  ${BOLD}q)${NC} Quit"
    echo
    
    local selection
    read -p "Enter selection [1-6 or q]: " selection
    
    case "$selection" in
        1)
            deploy_increment "patch"
            ;;
        2)
            deploy_increment "minor"
            ;;
        3)
            deploy_increment "major"
            ;;
        4)
            rollback_to_previous
            ;;
        5)
            emergency_rollback
            ;;
        6)
            get_latest_version
            ;;
        q|Q)
            echo "Exiting..."
            exit 0
            ;;
        *)
            log_error "Invalid selection"
            exit 1
            ;;
    esac
}

# ========== MAIN EXECUTION ==========
# Check for debug flag
for arg in "$@"; do
    if [ "$arg" = "--debug" ]; then
        DEBUG=true
        # Remove --debug from arguments
        set -- "${@/--debug/}"
        log_debug "Debug mode enabled"
    fi
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

# Parse command line arguments
if [ $# -eq 0 ]; then
    # No arguments, show menu
    show_menu
    exit 0
fi

# Handle commands
command="$1"
shift

case "$command" in
    patch)
        deploy_increment "patch" "$@"
        ;;
    minor)
        deploy_increment "minor" "$@"
        ;;
    major)
        deploy_increment "major" "$@"
        ;;
    rollback)
        rollback_to_previous "$@"
        ;;
    emergency)
        emergency_rollback "$@"
        ;;
    version)
        get_latest_version
        ;;
    help)
        show_help
        ;;
    *)
        log_error "Unknown command: $command"
        show_help
        exit 1
        ;;
esac

exit 0
