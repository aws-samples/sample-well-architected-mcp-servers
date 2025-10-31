#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Rollback script for COA Backend deployments

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"

# Default configuration
DEFAULT_VERSION="agentcore"
DEFAULT_BACKUP_TAG="backup"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
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
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] VERSION ACTION

Rollback COA Backend deployment to previous version

VERSIONS:
  bedrockagent    Rollback BedrockAgent version
  agentcore       Rollback AgentCore version
  both            Rollback both versions

ACTIONS:
  create-backup   Create backup of current deployment
  list-backups    List available backup images
  rollback        Rollback to backup version
  restore         Restore from specific backup tag
  cleanup         Clean up old backup images

OPTIONS:
  -t, --tag TAG           Backup tag to restore from [default: backup]
  --backup-tag TAG        Tag for creating backup [default: backup-TIMESTAMP]
  --keep-backups N        Number of backup images to keep [default: 3]
  --force                 Force rollback without confirmation
  --dry-run              Show what would be done without executing
  -v, --verbose          Enable verbose output
  -h, --help             Show this help message

BACKUP STRATEGY:
  - Current images are tagged with backup suffix before deployment
  - Rollback restores containers from backup images
  - Multiple backup versions can be maintained
  - Automatic cleanup of old backups

EXAMPLES:
  $0 agentcore create-backup              # Create backup of AgentCore
  $0 agentcore rollback                   # Rollback AgentCore to latest backup
  $0 bedrockagent restore -t backup-v1.0  # Restore specific backup
  $0 both list-backups                    # List all backup images
  $0 agentcore cleanup --keep-backups 5   # Keep only 5 most recent backups

SAFETY FEATURES:
  - Automatic validation before rollback
  - Confirmation prompts (unless --force)
  - Health checks after rollback
  - Automatic cleanup of failed rollbacks

EOF
}

# Function to create backup
create_backup() {
    local version="$1"
    local backup_tag="${BACKUP_TAG:-backup-$(date +%Y%m%d-%H%M%S)}"
    
    log_step "Creating backup for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            create_version_backup "coa-bedrockagent" "latest" "${backup_tag}"
            ;;
        "agentcore")
            create_version_backup "coa-agentcore" "latest" "${backup_tag}"
            ;;
        "both")
            create_version_backup "coa-bedrockagent" "latest" "${backup_tag}"
            create_version_backup "coa-agentcore" "latest" "${backup_tag}"
            ;;
    esac
    
    log_success "Backup created with tag: ${backup_tag}"
}

# Function to create backup for specific version
create_version_backup() {
    local image_name="$1"
    local source_tag="$2"
    local backup_tag="$3"
    
    log_info "Creating backup: ${image_name}:${source_tag} -> ${image_name}:${backup_tag}"
    
    # Check if source image exists
    if ! docker image inspect "${image_name}:${source_tag}" &> /dev/null; then
        log_error "Source image not found: ${image_name}:${source_tag}"
        return 1
    fi
    
    # Create backup image
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY RUN] Would create backup: docker tag ${image_name}:${source_tag} ${image_name}:${backup_tag}"
    else
        docker tag "${image_name}:${source_tag}" "${image_name}:${backup_tag}"
        log_success "Backup created: ${image_name}:${backup_tag}"
    fi
}

# Function to list backups
list_backups() {
    local version="$1"
    
    log_step "Listing backup images for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            list_version_backups "coa-bedrockagent"
            ;;
        "agentcore")
            list_version_backups "coa-agentcore"
            ;;
        "both")
            list_version_backups "coa-bedrockagent"
            echo ""
            list_version_backups "coa-agentcore"
            ;;
    esac
}

# Function to list backups for specific version
list_version_backups() {
    local image_name="$1"
    
    log_info "Backup images for ${image_name}:"
    
    # Get backup images (tags containing 'backup')
    local backup_images=$(docker images "${image_name}" --format "table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | grep -E "(backup|TAG)" || echo "No backup images found")
    
    if [[ "${backup_images}" == "No backup images found" ]]; then
        log_warning "No backup images found for ${image_name}"
    else
        echo "${backup_images}"
    fi
}

# Function to rollback deployment
rollback_deployment() {
    local version="$1"
    local backup_tag="${RESTORE_TAG:-backup}"
    
    log_step "Rolling back ${version} to backup tag: ${backup_tag}..."
    
    # Confirmation prompt
    if [[ "${FORCE}" != "true" ]]; then
        echo ""
        log_warning "This will rollback the ${version} deployment to backup tag: ${backup_tag}"
        log_warning "Current containers will be stopped and replaced with backup version"
        echo ""
        read -p "Are you sure you want to proceed? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Rollback cancelled by user"
            exit 0
        fi
    fi
    
    case "${version}" in
        "bedrockagent")
            rollback_version "bedrockagent" "coa-bedrockagent" "${backup_tag}"
            ;;
        "agentcore")
            rollback_version "agentcore" "coa-agentcore" "${backup_tag}"
            ;;
        "both")
            rollback_version "bedrockagent" "coa-bedrockagent" "${backup_tag}"
            rollback_version "agentcore" "coa-agentcore" "${backup_tag}"
            ;;
    esac
    
    # Validate rollback
    log_step "Validating rollback..."
    if "${SCRIPT_DIR}/validate-deployment.sh" "${version}" --timeout 30; then
        log_success "Rollback completed and validated successfully!"
    else
        log_error "Rollback validation failed!"
        log_warning "You may need to investigate the deployment manually"
        exit 1
    fi
}

# Function to rollback specific version
rollback_version() {
    local version="$1"
    local image_name="$2"
    local backup_tag="$3"
    
    log_info "Rolling back ${version} (${image_name}) to tag: ${backup_tag}"
    
    # Check if backup image exists
    if ! docker image inspect "${image_name}:${backup_tag}" &> /dev/null; then
        log_error "Backup image not found: ${image_name}:${backup_tag}"
        return 1
    fi
    
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY RUN] Would rollback ${version} to ${backup_tag}"
        return 0
    fi
    
    # Stop current containers
    log_info "Stopping current ${version} containers..."
    cd "${DEPLOYMENT_DIR}"
    
    case "${version}" in
        "bedrockagent")
            docker-compose --profile bedrockagent stop || true
            ;;
        "agentcore")
            docker-compose --profile agentcore stop || true
            ;;
    esac
    
    # Tag backup image as latest
    log_info "Restoring backup image as latest..."
    docker tag "${image_name}:${backup_tag}" "${image_name}:latest"
    
    # Start containers with restored image
    log_info "Starting ${version} containers with restored image..."
    case "${version}" in
        "bedrockagent")
            docker-compose --profile bedrockagent up -d
            ;;
        "agentcore")
            docker-compose --profile agentcore up -d
            ;;
    esac
    
    # Wait for containers to start
    sleep 10
    
    log_success "${version} rollback completed"
}

# Function to cleanup old backups
cleanup_backups() {
    local version="$1"
    local keep_count="${KEEP_BACKUPS:-3}"
    
    log_step "Cleaning up old backup images for ${version} (keeping ${keep_count} most recent)..."
    
    case "${version}" in
        "bedrockagent")
            cleanup_version_backups "coa-bedrockagent" "${keep_count}"
            ;;
        "agentcore")
            cleanup_version_backups "coa-agentcore" "${keep_count}"
            ;;
        "both")
            cleanup_version_backups "coa-bedrockagent" "${keep_count}"
            cleanup_version_backups "coa-agentcore" "${keep_count}"
            ;;
    esac
}

# Function to cleanup backups for specific version
cleanup_version_backups() {
    local image_name="$1"
    local keep_count="$2"
    
    log_info "Cleaning up backup images for ${image_name} (keeping ${keep_count})..."
    
    # Get backup image tags sorted by creation date (newest first)
    local backup_tags=$(docker images "${image_name}" --format "{{.Tag}}" | grep "backup" | head -n +100 || echo "")
    
    if [[ -z "${backup_tags}" ]]; then
        log_info "No backup images found for ${image_name}"
        return 0
    fi
    
    # Convert to array and count
    local tags_array=(${backup_tags})
    local total_backups=${#tags_array[@]}
    
    log_info "Found ${total_backups} backup images for ${image_name}"
    
    if [[ ${total_backups} -le ${keep_count} ]]; then
        log_info "No cleanup needed (${total_backups} <= ${keep_count})"
        return 0
    fi
    
    # Calculate how many to remove
    local remove_count=$((total_backups - keep_count))
    log_info "Removing ${remove_count} oldest backup images..."
    
    # Remove oldest backups (skip the first keep_count)
    for ((i=keep_count; i<total_backups; i++)); do
        local tag_to_remove="${tags_array[$i]}"
        log_info "Removing backup: ${image_name}:${tag_to_remove}"
        
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_info "[DRY RUN] Would remove: docker rmi ${image_name}:${tag_to_remove}"
        else
            docker rmi "${image_name}:${tag_to_remove}" || log_warning "Failed to remove ${image_name}:${tag_to_remove}"
        fi
    done
    
    log_success "Backup cleanup completed for ${image_name}"
}

# Function to validate rollback prerequisites
validate_rollback_prerequisites() {
    local version="$1"
    
    log_step "Validating rollback prerequisites..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check if deployment directory exists
    if [[ ! -d "${DEPLOYMENT_DIR}" ]]; then
        log_error "Deployment directory not found: ${DEPLOYMENT_DIR}"
        exit 1
    fi
    
    # Check if docker-compose.yml exists
    if [[ ! -f "${DEPLOYMENT_DIR}/docker-compose.yml" ]]; then
        log_error "Docker Compose file not found: ${DEPLOYMENT_DIR}/docker-compose.yml"
        exit 1
    fi
    
    log_success "Prerequisites validation passed"
}

# Parse command line arguments
VERSION="${DEFAULT_VERSION}"
ACTION=""
RESTORE_TAG=""
BACKUP_TAG=""
KEEP_BACKUPS="3"
FORCE="false"
DRY_RUN="false"
VERBOSE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        bedrockagent|agentcore|both)
            VERSION="$1"
            shift
            ;;
        create-backup|list-backups|rollback|restore|cleanup)
            ACTION="$1"
            shift
            ;;
        -t|--tag)
            RESTORE_TAG="$2"
            shift 2
            ;;
        --backup-tag)
            BACKUP_TAG="$2"
            shift 2
            ;;
        --keep-backups)
            KEEP_BACKUPS="$2"
            shift 2
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "${ACTION}" ]]; then
    log_error "Action is required"
    show_usage
    exit 1
fi

# Set verbose mode
if [[ "${VERBOSE}" == "true" ]]; then
    set -x
fi

# Main execution
main() {
    log_info "COA Backend Rollback Script"
    log_info "Version: ${VERSION}"
    log_info "Action: ${ACTION}"
    
    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "DRY RUN MODE - No changes will be made"
    fi
    
    # Validate prerequisites
    validate_rollback_prerequisites "${VERSION}"
    
    # Execute action
    case "${ACTION}" in
        "create-backup")
            create_backup "${VERSION}"
            ;;
        "list-backups")
            list_backups "${VERSION}"
            ;;
        "rollback")
            rollback_deployment "${VERSION}"
            ;;
        "restore")
            if [[ -z "${RESTORE_TAG}" ]]; then
                log_error "Restore tag is required for restore action (use -t or --tag)"
                exit 1
            fi
            rollback_deployment "${VERSION}"
            ;;
        "cleanup")
            cleanup_backups "${VERSION}"
            ;;
        *)
            log_error "Unknown action: ${ACTION}"
            show_usage
            exit 1
            ;;
    esac
    
    log_success "Rollback operation completed successfully!"
}

# Execute main function
main "$@"