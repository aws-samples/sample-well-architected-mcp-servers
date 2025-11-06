#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Build script for COA BedrockAgent version

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"

# Build configuration
IMAGE_NAME="coa-bedrockagent"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE="${DEPLOYMENT_DIR}/bedrockagent.dockerfile"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Function to validate environment
validate_environment() {
    log_info "Validating build environment..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Dockerfile exists
    if [[ ! -f "${DOCKERFILE}" ]]; then
        log_error "BedrockAgent Dockerfile not found: ${DOCKERFILE}"
        exit 1
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "${PROJECT_ROOT}/main.py" ]]; then
        log_error "main.py not found. Please run this script from the correct directory."
        exit 1
    fi
    
    log_success "Environment validation passed"
}

# Function to validate BedrockAgent configuration
validate_bedrockagent_config() {
    log_info "Validating BedrockAgent configuration..."
    
    # Check if BedrockAgent directory exists
    if [[ ! -d "${PROJECT_ROOT}/bedrockagent" ]]; then
        log_error "BedrockAgent directory not found: ${PROJECT_ROOT}/bedrockagent"
        exit 1
    fi
    
    # Check if BedrockAgent app exists
    if [[ ! -f "${PROJECT_ROOT}/bedrockagent/app.py" ]]; then
        log_error "BedrockAgent app.py not found"
        exit 1
    fi
    
    # Check if shared directory exists
    if [[ ! -d "${PROJECT_ROOT}/shared" ]]; then
        log_error "Shared directory not found: ${PROJECT_ROOT}/shared"
        exit 1
    fi
    
    log_success "BedrockAgent configuration validation passed"
}

# Function to build Docker image
build_image() {
    log_info "Building BedrockAgent Docker image..."
    log_info "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
    log_info "Dockerfile: ${DOCKERFILE}"
    log_info "Context: ${PROJECT_ROOT}"
    
    # Build the Docker image
    if docker build \
        -f "${DOCKERFILE}" \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        --build-arg BACKEND_MODE=bedrockagent \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
        "${PROJECT_ROOT}"; then
        log_success "BedrockAgent Docker image built successfully"
    else
        log_error "Failed to build BedrockAgent Docker image"
        exit 1
    fi
}

# Function to validate built image
validate_image() {
    log_info "Validating built image..."
    
    # Check if image exists
    if ! docker image inspect "${IMAGE_NAME}:${IMAGE_TAG}" &> /dev/null; then
        log_error "Built image not found: ${IMAGE_NAME}:${IMAGE_TAG}"
        exit 1
    fi
    
    # Test image configuration
    log_info "Testing image configuration..."
    
    # Check environment variables
    BACKEND_MODE=$(docker run --rm "${IMAGE_NAME}:${IMAGE_TAG}" python -c "import os; print(os.getenv('BACKEND_MODE', 'unknown'))")
    if [[ "${BACKEND_MODE}" != "bedrockagent" ]]; then
        log_error "Invalid BACKEND_MODE in image: ${BACKEND_MODE}"
        exit 1
    fi
    
    log_success "Image validation passed"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build COA BedrockAgent Docker image"
    echo ""
    echo "Options:"
    echo "  -t, --tag TAG        Set image tag (default: latest)"
    echo "  -n, --name NAME      Set image name (default: coa-bedrockagent)"
    echo "  --no-cache          Build without using cache"
    echo "  --validate-only     Only validate configuration, don't build"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  IMAGE_TAG           Image tag to use (default: latest)"
    echo "  DOCKER_BUILDKIT     Enable Docker BuildKit (recommended: 1)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Build with default settings"
    echo "  $0 -t v1.0.0               # Build with specific tag"
    echo "  $0 --no-cache              # Build without cache"
    echo "  IMAGE_TAG=dev $0           # Build with dev tag"
}

# Parse command line arguments
VALIDATE_ONLY=false
NO_CACHE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
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

# Main execution
main() {
    log_info "Starting BedrockAgent build process..."
    log_info "Project root: ${PROJECT_ROOT}"
    
    # Validate environment and configuration
    validate_environment
    validate_bedrockagent_config
    
    if [[ "${VALIDATE_ONLY}" == "true" ]]; then
        log_success "Validation completed successfully"
        exit 0
    fi
    
    # Build and validate image
    build_image
    validate_image
    
    # Show final information
    log_success "BedrockAgent build completed successfully!"
    log_info "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
    log_info "Size: $(docker image inspect "${IMAGE_NAME}:${IMAGE_TAG}" --format='{{.Size}}' | numfmt --to=iec)"
    
    echo ""
    log_info "To run the BedrockAgent container:"
    echo "  docker run -p 8000:8000 ${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    log_info "To run with Docker Compose:"
    echo "  cd ${DEPLOYMENT_DIR} && docker-compose --profile bedrockagent up -d"
}

# Execute main function
main "$@"