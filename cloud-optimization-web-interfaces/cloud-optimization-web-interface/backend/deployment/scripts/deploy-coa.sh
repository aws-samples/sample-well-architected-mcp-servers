#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Unified deployment script for COA Backend versions

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"

# Default configuration
DEFAULT_VERSION="agentcore"
DEFAULT_ACTION="deploy"
DEFAULT_ENVIRONMENT="dev"

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

Unified deployment script for COA Backend versions

VERSIONS:
  bedrockagent    Deploy BedrockAgent version (traditional agents + MCP)
  agentcore       Deploy AgentCore version (Strands agents + graceful degradation)
  both            Deploy both versions simultaneously

ACTIONS:
  build           Build Docker image only
  deploy          Build and deploy with Docker Compose
  start           Start existing deployment
  stop            Stop running deployment
  restart         Restart deployment
  status          Show deployment status
  logs            Show deployment logs
  clean           Stop and remove containers/images

OPTIONS:
  -e, --env ENV           Set environment (dev/staging/prod) [default: dev]
  -t, --tag TAG          Set image tag [default: latest]
  -p, --port PORT        Set port for single version deployment [default: 8000]
  --no-cache             Build without using cache
  --pull                 Pull latest base images before building
  --validate-only        Only validate configuration, don't build/deploy
  --with-monitoring      Include monitoring stack
  --with-loadbalancer    Include load balancer (for both versions)
  -v, --verbose          Enable verbose output
  -h, --help             Show this help message

ENVIRONMENT VARIABLES:
  BACKEND_VERSION         Version to deploy (bedrockagent/agentcore/both)
  DEPLOYMENT_ENV          Environment (dev/staging/prod)
  IMAGE_TAG              Image tag to use
  PARAM_PREFIX           Parameter prefix for AgentCore
  AWS_DEFAULT_REGION     AWS region
  DOCKER_BUILDKIT        Enable Docker BuildKit (recommended: 1)

EXAMPLES:
  $0 agentcore deploy                    # Deploy AgentCore version
  $0 bedrockagent build                  # Build BedrockAgent image only
  $0 both deploy --with-loadbalancer     # Deploy both with load balancer
  $0 agentcore status                    # Check AgentCore deployment status
  $0 both logs                           # Show logs for both versions
  $0 agentcore clean                     # Clean up AgentCore deployment

EOF
}

# Function to validate environment
validate_environment() {
    log_step "Validating deployment environment..."
    
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
    
    log_success "Environment validation passed"
}

# Function to validate version-specific configuration
validate_version_config() {
    local version="$1"
    
    log_step "Validating ${version} configuration..."
    
    case "${version}" in
        "bedrockagent")
            if [[ ! -f "${DEPLOYMENT_DIR}/bedrockagent.dockerfile" ]]; then
                log_error "BedrockAgent Dockerfile not found"
                exit 1
            fi
            if [[ ! -d "${PROJECT_ROOT}/bedrockagent" ]]; then
                log_error "BedrockAgent directory not found"
                exit 1
            fi
            ;;
        "agentcore")
            if [[ ! -f "${DEPLOYMENT_DIR}/agentcore.dockerfile" ]]; then
                log_error "AgentCore Dockerfile not found"
                exit 1
            fi
            if [[ ! -d "${PROJECT_ROOT}/agentcore" ]]; then
                log_error "AgentCore directory not found"
                exit 1
            fi
            ;;
        "both")
            validate_version_config "bedrockagent"
            validate_version_config "agentcore"
            return
            ;;
        *)
            log_error "Unknown version: ${version}"
            exit 1
            ;;
    esac
    
    log_success "${version} configuration validation passed"
}

# Function to build version
build_version() {
    local version="$1"
    local build_args="$2"
    
    log_step "Building ${version} version..."
    
    case "${version}" in
        "bedrockagent")
            "${SCRIPT_DIR}/build-bedrockagent.sh" ${build_args}
            ;;
        "agentcore")
            "${SCRIPT_DIR}/build-agentcore.sh" ${build_args}
            ;;
        "both")
            build_version "bedrockagent" "${build_args}"
            build_version "agentcore" "${build_args}"
            ;;
    esac
}

# Function to get Docker Compose profiles
get_compose_profiles() {
    local version="$1"
    local profiles=""
    
    case "${version}" in
        "bedrockagent")
            profiles="--profile bedrockagent"
            ;;
        "agentcore")
            profiles="--profile agentcore"
            ;;
        "both")
            profiles="--profile all"
            ;;
    esac
    
    # Add optional profiles
    if [[ "${WITH_MONITORING}" == "true" ]]; then
        profiles="${profiles} --profile monitoring"
    fi
    
    if [[ "${WITH_LOADBALANCER}" == "true" ]]; then
        profiles="${profiles} --profile loadbalancer"
    fi
    
    echo "${profiles}"
}

# Function to deploy with Docker Compose
deploy_compose() {
    local version="$1"
    local action="$2"
    
    local profiles=$(get_compose_profiles "${version}")
    
    log_step "Executing Docker Compose ${action} for ${version}..."
    
    cd "${DEPLOYMENT_DIR}"
    
    case "${action}" in
        "deploy"|"up")
            docker-compose ${profiles} up -d
            ;;
        "start")
            docker-compose ${profiles} start
            ;;
        "stop")
            docker-compose ${profiles} stop
            ;;
        "restart")
            docker-compose ${profiles} restart
            ;;
        "down")
            docker-compose ${profiles} down
            ;;
        "logs")
            docker-compose ${profiles} logs -f
            ;;
        "status"|"ps")
            docker-compose ${profiles} ps
            ;;
    esac
}

# Function to show deployment status
show_status() {
    local version="$1"
    
    log_step "Checking ${version} deployment status..."
    
    cd "${DEPLOYMENT_DIR}"
    
    local profiles=$(get_compose_profiles "${version}")
    
    echo ""
    log_info "Container Status:"
    docker-compose ${profiles} ps
    
    echo ""
    log_info "Image Information:"
    case "${version}" in
        "bedrockagent")
            if docker image inspect coa-bedrockagent:${IMAGE_TAG} &> /dev/null; then
                echo "  BedrockAgent: coa-bedrockagent:${IMAGE_TAG} ($(docker image inspect coa-bedrockagent:${IMAGE_TAG} --format='{{.Size}}' | numfmt --to=iec))"
            fi
            ;;
        "agentcore")
            if docker image inspect coa-agentcore:${IMAGE_TAG} &> /dev/null; then
                echo "  AgentCore: coa-agentcore:${IMAGE_TAG} ($(docker image inspect coa-agentcore:${IMAGE_TAG} --format='{{.Size}}' | numfmt --to=iec))"
            fi
            ;;
        "both")
            if docker image inspect coa-bedrockagent:${IMAGE_TAG} &> /dev/null; then
                echo "  BedrockAgent: coa-bedrockagent:${IMAGE_TAG} ($(docker image inspect coa-bedrockagent:${IMAGE_TAG} --format='{{.Size}}' | numfmt --to=iec))"
            fi
            if docker image inspect coa-agentcore:${IMAGE_TAG} &> /dev/null; then
                echo "  AgentCore: coa-agentcore:${IMAGE_TAG} ($(docker image inspect coa-agentcore:${IMAGE_TAG} --format='{{.Size}}' | numfmt --to=iec))"
            fi
            ;;
    esac
    
    echo ""
    log_info "Health Status:"
    case "${version}" in
        "bedrockagent")
            if docker ps --filter "name=coa-bedrockagent" --filter "status=running" | grep -q coa-bedrockagent; then
                echo "  BedrockAgent: Running (http://localhost:8000/health)"
            else
                echo "  BedrockAgent: Not running"
            fi
            ;;
        "agentcore")
            if docker ps --filter "name=coa-agentcore" --filter "status=running" | grep -q coa-agentcore; then
                echo "  AgentCore: Running (http://localhost:8001/health)"
            else
                echo "  AgentCore: Not running"
            fi
            ;;
        "both")
            if docker ps --filter "name=coa-bedrockagent" --filter "status=running" | grep -q coa-bedrockagent; then
                echo "  BedrockAgent: Running (http://localhost:8000/health)"
            else
                echo "  BedrockAgent: Not running"
            fi
            if docker ps --filter "name=coa-agentcore" --filter "status=running" | grep -q coa-agentcore; then
                echo "  AgentCore: Running (http://localhost:8001/health)"
            else
                echo "  AgentCore: Not running"
            fi
            ;;
    esac
}

# Function to clean up deployment
clean_deployment() {
    local version="$1"
    
    log_step "Cleaning up ${version} deployment..."
    
    cd "${DEPLOYMENT_DIR}"
    
    local profiles=$(get_compose_profiles "${version}")
    
    # Stop and remove containers
    docker-compose ${profiles} down --remove-orphans
    
    # Remove images if requested
    if [[ "${CLEAN_IMAGES}" == "true" ]]; then
        case "${version}" in
            "bedrockagent")
                docker rmi coa-bedrockagent:${IMAGE_TAG} 2>/dev/null || true
                ;;
            "agentcore")
                docker rmi coa-agentcore:${IMAGE_TAG} 2>/dev/null || true
                ;;
            "both")
                docker rmi coa-bedrockagent:${IMAGE_TAG} 2>/dev/null || true
                docker rmi coa-agentcore:${IMAGE_TAG} 2>/dev/null || true
                ;;
        esac
    fi
    
    log_success "Cleanup completed"
}

# Parse command line arguments
VERSION="${DEFAULT_VERSION}"
ACTION="${DEFAULT_ACTION}"
ENVIRONMENT="${DEFAULT_ENVIRONMENT}"
IMAGE_TAG="latest"
PORT="8000"
BUILD_ARGS=""
WITH_MONITORING="false"
WITH_LOADBALANCER="false"
VERBOSE="false"
VALIDATE_ONLY="false"
CLEAN_IMAGES="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        bedrockagent|agentcore|both)
            VERSION="$1"
            shift
            ;;
        build|deploy|start|stop|restart|status|logs|clean)
            ACTION="$1"
            shift
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --no-cache)
            BUILD_ARGS="${BUILD_ARGS} --no-cache"
            shift
            ;;
        --pull)
            BUILD_ARGS="${BUILD_ARGS} --pull"
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY="true"
            shift
            ;;
        --with-monitoring)
            WITH_MONITORING="true"
            shift
            ;;
        --with-loadbalancer)
            WITH_LOADBALANCER="true"
            shift
            ;;
        --clean-images)
            CLEAN_IMAGES="true"
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

# Set verbose mode
if [[ "${VERBOSE}" == "true" ]]; then
    set -x
fi

# Main execution
main() {
    log_info "COA Backend Deployment Script"
    log_info "Version: ${VERSION}"
    log_info "Action: ${ACTION}"
    log_info "Environment: ${ENVIRONMENT}"
    log_info "Image Tag: ${IMAGE_TAG}"
    
    # Validate environment
    validate_environment
    validate_version_config "${VERSION}"
    
    if [[ "${VALIDATE_ONLY}" == "true" ]]; then
        log_success "Validation completed successfully"
        exit 0
    fi
    
    # Execute action
    case "${ACTION}" in
        "build")
            build_version "${VERSION}" "${BUILD_ARGS}"
            ;;
        "deploy")
            # Create backup before deployment
            log_step "Creating backup before deployment..."
            "${SCRIPT_DIR}/rollback-deployment.sh" "${VERSION}" create-backup --backup-tag "pre-deploy-$(date +%Y%m%d-%H%M%S)" || log_warning "Backup creation failed"
            
            build_version "${VERSION}" "${BUILD_ARGS}"
            deploy_compose "${VERSION}" "up"
            
            # Validate deployment
            log_step "Validating deployment..."
            if "${SCRIPT_DIR}/validate-deployment.sh" "${VERSION}" --timeout 60; then
                log_success "Deployment validation passed"
                show_status "${VERSION}"
            else
                log_error "Deployment validation failed!"
                log_warning "Consider rolling back using: ${SCRIPT_DIR}/rollback-deployment.sh ${VERSION} rollback"
                exit 1
            fi
            ;;
        "start")
            deploy_compose "${VERSION}" "start"
            
            # Quick health check after start
            sleep 10
            if "${SCRIPT_DIR}/health-check.sh" "${VERSION}" --timeout 30 --exit-code; then
                log_success "Service started successfully"
            else
                log_warning "Service may not be fully ready yet"
            fi
            show_status "${VERSION}"
            ;;
        "stop")
            deploy_compose "${VERSION}" "stop"
            ;;
        "restart")
            deploy_compose "${VERSION}" "restart"
            
            # Quick health check after restart
            sleep 10
            if "${SCRIPT_DIR}/health-check.sh" "${VERSION}" --timeout 30 --exit-code; then
                log_success "Service restarted successfully"
            else
                log_warning "Service may not be fully ready yet"
            fi
            show_status "${VERSION}"
            ;;
        "status")
            show_status "${VERSION}"
            ;;
        "logs")
            deploy_compose "${VERSION}" "logs"
            ;;
        "clean")
            clean_deployment "${VERSION}"
            ;;
        *)
            log_error "Unknown action: ${ACTION}"
            show_usage
            exit 1
            ;;
    esac
    
    log_success "Deployment operation completed successfully!"
}

# Execute main function
main "$@"