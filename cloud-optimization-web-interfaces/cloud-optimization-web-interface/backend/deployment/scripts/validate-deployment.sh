#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Deployment validation script for COA Backend versions

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"

# Default configuration
DEFAULT_VERSION="agentcore"
DEFAULT_TIMEOUT=60
DEFAULT_RETRY_COUNT=3

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
Usage: $0 [OPTIONS] VERSION

Validate COA Backend deployment

VERSIONS:
  bedrockagent    Validate BedrockAgent version deployment
  agentcore       Validate AgentCore version deployment
  both            Validate both versions

OPTIONS:
  -t, --timeout SECONDS      Health check timeout [default: 60]
  -r, --retry COUNT         Retry count for health checks [default: 3]
  --skip-health             Skip health check validation
  --skip-config             Skip configuration validation
  --skip-connectivity       Skip connectivity validation
  --detailed                Show detailed validation results
  -v, --verbose             Enable verbose output
  -h, --help                Show this help message

VALIDATION CHECKS:
  1. Container Status       - Check if containers are running
  2. Health Endpoints       - Validate /health endpoints
  3. Configuration          - Validate environment variables and config
  4. Connectivity          - Test AWS and service connectivity
  5. Version Compatibility  - Validate version-specific features
  6. Resource Usage         - Check memory and CPU usage
  7. Log Analysis          - Check for errors in logs

EXAMPLES:
  $0 agentcore                    # Validate AgentCore deployment
  $0 bedrockagent --detailed      # Detailed BedrockAgent validation
  $0 both --timeout 120           # Validate both with extended timeout

EOF
}

# Function to check container status
check_container_status() {
    local version="$1"
    local container_name=""
    
    log_step "Checking container status for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            container_name="coa-bedrockagent"
            ;;
        "agentcore")
            container_name="coa-agentcore"
            ;;
        "both")
            check_container_status "bedrockagent"
            check_container_status "agentcore"
            return
            ;;
    esac
    
    # Check if container exists
    if ! docker ps -a --filter "name=${container_name}" --format "table {{.Names}}" | grep -q "${container_name}"; then
        log_error "Container ${container_name} not found"
        return 1
    fi
    
    # Check if container is running
    if docker ps --filter "name=${container_name}" --filter "status=running" --format "table {{.Names}}" | grep -q "${container_name}"; then
        log_success "Container ${container_name} is running"
        
        # Get container details
        if [[ "${DETAILED}" == "true" ]]; then
            local container_info=$(docker inspect "${container_name}" --format='
Image: {{.Config.Image}}
Status: {{.State.Status}}
Started: {{.State.StartedAt}}
Ports: {{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostPort}} {{end}}
Environment: {{range .Config.Env}}{{if or (contains . "BACKEND_") (contains . "PARAM_") (contains . "AWS_")}}{{.}} {{end}}{{end}}')
            echo "${container_info}"
        fi
        
        return 0
    else
        local status=$(docker ps -a --filter "name=${container_name}" --format "{{.Status}}")
        log_error "Container ${container_name} is not running (Status: ${status})"
        return 1
    fi
}

# Function to check health endpoints
check_health_endpoints() {
    local version="$1"
    local port=""
    local endpoint_url=""
    
    log_step "Checking health endpoints for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            port="8000"
            endpoint_url="http://localhost:${port}/health"
            ;;
        "agentcore")
            port="8001"
            endpoint_url="http://localhost:${port}/health"
            ;;
        "both")
            check_health_endpoints "bedrockagent"
            check_health_endpoints "agentcore"
            return
            ;;
    esac
    
    # Wait for service to be ready
    local retry_count=0
    local max_retries="${RETRY_COUNT}"
    local timeout="${TIMEOUT}"
    
    while [[ ${retry_count} -lt ${max_retries} ]]; do
        log_info "Attempting health check (${retry_count}/${max_retries}): ${endpoint_url}"
        
        if curl -f -s --max-time "${timeout}" "${endpoint_url}" > /dev/null; then
            log_success "Health endpoint ${endpoint_url} is responding"
            
            # Get detailed health information
            if [[ "${DETAILED}" == "true" ]]; then
                local health_response=$(curl -s --max-time "${timeout}" "${endpoint_url}" | jq . 2>/dev/null || curl -s --max-time "${timeout}" "${endpoint_url}")
                echo "Health Response:"
                echo "${health_response}"
            fi
            
            return 0
        else
            log_warning "Health check failed, retrying in 5 seconds..."
            sleep 5
            ((retry_count++))
        fi
    done
    
    log_error "Health endpoint ${endpoint_url} failed after ${max_retries} attempts"
    return 1
}

# Function to validate configuration
validate_configuration() {
    local version="$1"
    local container_name=""
    
    log_step "Validating configuration for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            container_name="coa-bedrockagent"
            ;;
        "agentcore")
            container_name="coa-agentcore"
            ;;
        "both")
            validate_configuration "bedrockagent"
            validate_configuration "agentcore"
            return
            ;;
    esac
    
    # Check environment variables
    local backend_mode=$(docker exec "${container_name}" python -c "import os; print(os.getenv('BACKEND_MODE', 'unknown'))" 2>/dev/null || echo "error")
    
    if [[ "${backend_mode}" == "${version}" ]]; then
        log_success "BACKEND_MODE correctly set to ${backend_mode}"
    elif [[ "${backend_mode}" == "error" ]]; then
        log_error "Failed to check BACKEND_MODE in container"
        return 1
    else
        log_error "BACKEND_MODE mismatch: expected ${version}, got ${backend_mode}"
        return 1
    fi
    
    # Version-specific configuration checks
    case "${version}" in
        "bedrockagent")
            # Check BedrockAgent-specific configuration
            local bedrock_config=$(docker exec "${container_name}" python -c "
try:
    from bedrockagent.app import get_bedrockagent_info
    info = get_bedrockagent_info()
    print(f\"backend_type:{info['backend_type']},features:{info['features']['traditional_agents']}\")
except Exception as e:
    print(f'error:{e}')
" 2>/dev/null || echo "error:import_failed")
            
            if [[ "${bedrock_config}" == *"backend_type:bedrockagent"* ]]; then
                log_success "BedrockAgent configuration validated"
            else
                log_error "BedrockAgent configuration validation failed: ${bedrock_config}"
                return 1
            fi
            ;;
        "agentcore")
            # Check AgentCore-specific configuration
            local agentcore_config=$(docker exec "${container_name}" python -c "
try:
    from agentcore.app import get_agentcore_info
    info = get_agentcore_info()
    print(f\"backend_type:{info['backend_type']},features:{info['features']['strands_agents']}\")
except Exception as e:
    print(f'error:{e}')
" 2>/dev/null || echo "error:import_failed")
            
            if [[ "${agentcore_config}" == *"backend_type:agentcore"* ]]; then
                log_success "AgentCore configuration validated"
            else
                log_error "AgentCore configuration validation failed: ${agentcore_config}"
                return 1
            fi
            ;;
    esac
    
    return 0
}

# Function to test connectivity
test_connectivity() {
    local version="$1"
    local container_name=""
    
    log_step "Testing connectivity for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            container_name="coa-bedrockagent"
            ;;
        "agentcore")
            container_name="coa-agentcore"
            ;;
        "both")
            test_connectivity "bedrockagent"
            test_connectivity "agentcore"
            return
            ;;
    esac
    
    # Test AWS connectivity
    log_info "Testing AWS connectivity..."
    local aws_test=$(docker exec "${container_name}" python -c "
import boto3
try:
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()
    print(f\"aws_ok:account:{identity.get('Account', 'unknown')}\")
except Exception as e:
    print(f'aws_error:{e}')
" 2>/dev/null || echo "aws_error:execution_failed")
    
    if [[ "${aws_test}" == *"aws_ok"* ]]; then
        log_success "AWS connectivity validated"
        if [[ "${DETAILED}" == "true" ]]; then
            echo "  ${aws_test}"
        fi
    else
        log_warning "AWS connectivity issue: ${aws_test}"
    fi
    
    # Test parameter store connectivity (for AgentCore)
    if [[ "${version}" == "agentcore" ]]; then
        log_info "Testing Parameter Store connectivity..."
        local param_test=$(docker exec "${container_name}" python -c "
import boto3
import os
try:
    ssm = boto3.client('ssm')
    param_prefix = os.getenv('PARAM_PREFIX', 'coa')
    # Try to list parameters with the prefix
    response = ssm.describe_parameters(
        ParameterFilters=[
            {'Key': 'Name', 'Option': 'BeginsWith', 'Values': [f'/{param_prefix}/']}
        ],
        MaxResults=1
    )
    print(f\"param_ok:prefix:{param_prefix}\")
except Exception as e:
    print(f'param_error:{e}')
" 2>/dev/null || echo "param_error:execution_failed")
        
        if [[ "${param_test}" == *"param_ok"* ]]; then
            log_success "Parameter Store connectivity validated"
            if [[ "${DETAILED}" == "true" ]]; then
                echo "  ${param_test}"
            fi
        else
            log_warning "Parameter Store connectivity issue: ${param_test}"
        fi
    fi
    
    return 0
}

# Function to check resource usage
check_resource_usage() {
    local version="$1"
    local container_name=""
    
    log_step "Checking resource usage for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            container_name="coa-bedrockagent"
            ;;
        "agentcore")
            container_name="coa-agentcore"
            ;;
        "both")
            check_resource_usage "bedrockagent"
            check_resource_usage "agentcore"
            return
            ;;
    esac
    
    # Get container stats
    local stats=$(docker stats "${container_name}" --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}")
    
    if [[ -n "${stats}" ]]; then
        log_success "Resource usage for ${container_name}:"
        echo "${stats}"
        
        # Parse memory usage and check if it's reasonable
        local mem_usage=$(echo "${stats}" | tail -n 1 | awk '{print $2}' | cut -d'/' -f1)
        local mem_unit=$(echo "${mem_usage}" | grep -o '[A-Za-z]*$')
        local mem_value=$(echo "${mem_usage}" | grep -o '^[0-9.]*')
        
        # Convert to MB for comparison
        local mem_mb=0
        case "${mem_unit}" in
            "GiB"|"GB")
                mem_mb=$(echo "${mem_value} * 1024" | bc -l 2>/dev/null || echo "0")
                ;;
            "MiB"|"MB")
                mem_mb="${mem_value}"
                ;;
            "KiB"|"KB")
                mem_mb=$(echo "${mem_value} / 1024" | bc -l 2>/dev/null || echo "0")
                ;;
        esac
        
        # Check if memory usage is reasonable (less than 2GB)
        if (( $(echo "${mem_mb} > 2048" | bc -l 2>/dev/null || echo "0") )); then
            log_warning "High memory usage detected: ${mem_usage}"
        fi
    else
        log_error "Failed to get resource usage for ${container_name}"
        return 1
    fi
    
    return 0
}

# Function to analyze logs
analyze_logs() {
    local version="$1"
    local container_name=""
    
    log_step "Analyzing logs for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            container_name="coa-bedrockagent"
            ;;
        "agentcore")
            container_name="coa-agentcore"
            ;;
        "both")
            analyze_logs "bedrockagent"
            analyze_logs "agentcore"
            return
            ;;
    esac
    
    # Get recent logs
    local logs=$(docker logs "${container_name}" --tail 100 2>&1)
    
    # Count error messages
    local error_count=$(echo "${logs}" | grep -i "error" | wc -l)
    local warning_count=$(echo "${logs}" | grep -i "warning" | wc -l)
    
    log_info "Log analysis for ${container_name}:"
    echo "  Errors: ${error_count}"
    echo "  Warnings: ${warning_count}"
    
    # Show recent errors if any
    if [[ ${error_count} -gt 0 ]]; then
        log_warning "Recent errors found:"
        echo "${logs}" | grep -i "error" | tail -5 | sed 's/^/    /'
    fi
    
    # Check for startup success
    if echo "${logs}" | grep -q "startup completed successfully"; then
        log_success "Startup completed successfully"
    elif echo "${logs}" | grep -q "Application startup complete"; then
        log_success "Application startup complete"
    else
        log_warning "Startup completion message not found in logs"
    fi
    
    return 0
}

# Function to validate version compatibility
validate_version_compatibility() {
    local version="$1"
    
    log_step "Validating version compatibility for ${version}..."
    
    case "${version}" in
        "bedrockagent")
            # Test BedrockAgent-specific features
            log_info "Testing BedrockAgent features..."
            
            # Test traditional agent endpoint
            local agent_test=$(curl -s --max-time 10 "http://localhost:8000/api/agents/traditional" 2>/dev/null || echo "error")
            if [[ "${agent_test}" != "error" ]]; then
                log_success "Traditional agent endpoint accessible"
            else
                log_warning "Traditional agent endpoint not accessible"
            fi
            ;;
        "agentcore")
            # Test AgentCore-specific features
            log_info "Testing AgentCore features..."
            
            # Test Strands agent endpoint
            local strands_test=$(curl -s --max-time 10 "http://localhost:8001/api/agents/strands" 2>/dev/null || echo "error")
            if [[ "${strands_test}" != "error" ]]; then
                log_success "Strands agent endpoint accessible"
            else
                log_warning "Strands agent endpoint not accessible"
            fi
            ;;
        "both")
            validate_version_compatibility "bedrockagent"
            validate_version_compatibility "agentcore"
            return
            ;;
    esac
    
    return 0
}

# Parse command line arguments
VERSION="${DEFAULT_VERSION}"
TIMEOUT="${DEFAULT_TIMEOUT}"
RETRY_COUNT="${DEFAULT_RETRY_COUNT}"
SKIP_HEALTH="false"
SKIP_CONFIG="false"
SKIP_CONNECTIVITY="false"
DETAILED="false"
VERBOSE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        bedrockagent|agentcore|both)
            VERSION="$1"
            shift
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -r|--retry)
            RETRY_COUNT="$2"
            shift 2
            ;;
        --skip-health)
            SKIP_HEALTH="true"
            shift
            ;;
        --skip-config)
            SKIP_CONFIG="true"
            shift
            ;;
        --skip-connectivity)
            SKIP_CONNECTIVITY="true"
            shift
            ;;
        --detailed)
            DETAILED="true"
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

# Main validation function
main() {
    log_info "COA Backend Deployment Validation"
    log_info "Version: ${VERSION}"
    log_info "Timeout: ${TIMEOUT}s"
    log_info "Retry Count: ${RETRY_COUNT}"
    
    local validation_failed=false
    
    # Run validation checks
    echo ""
    
    # 1. Container Status
    if ! check_container_status "${VERSION}"; then
        validation_failed=true
    fi
    
    echo ""
    
    # 2. Health Endpoints
    if [[ "${SKIP_HEALTH}" != "true" ]]; then
        if ! check_health_endpoints "${VERSION}"; then
            validation_failed=true
        fi
    else
        log_info "Skipping health endpoint validation"
    fi
    
    echo ""
    
    # 3. Configuration
    if [[ "${SKIP_CONFIG}" != "true" ]]; then
        if ! validate_configuration "${VERSION}"; then
            validation_failed=true
        fi
    else
        log_info "Skipping configuration validation"
    fi
    
    echo ""
    
    # 4. Connectivity
    if [[ "${SKIP_CONNECTIVITY}" != "true" ]]; then
        if ! test_connectivity "${VERSION}"; then
            validation_failed=true
        fi
    else
        log_info "Skipping connectivity validation"
    fi
    
    echo ""
    
    # 5. Version Compatibility
    if ! validate_version_compatibility "${VERSION}"; then
        validation_failed=true
    fi
    
    echo ""
    
    # 6. Resource Usage
    if ! check_resource_usage "${VERSION}"; then
        validation_failed=true
    fi
    
    echo ""
    
    # 7. Log Analysis
    if ! analyze_logs "${VERSION}"; then
        validation_failed=true
    fi
    
    echo ""
    
    # Final result
    if [[ "${validation_failed}" == "true" ]]; then
        log_error "Deployment validation failed!"
        log_info "Some validation checks failed. Please review the output above."
        exit 1
    else
        log_success "Deployment validation passed!"
        log_info "All validation checks completed successfully."
        exit 0
    fi
}

# Execute main function
main "$@"