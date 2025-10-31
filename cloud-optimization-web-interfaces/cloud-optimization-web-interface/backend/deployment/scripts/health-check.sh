#!/bin/bash
# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Health check script for COA Backend versions

set -e

# Default configuration
DEFAULT_VERSION="agentcore"
DEFAULT_TIMEOUT=30
DEFAULT_RETRY_COUNT=3

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

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] VERSION

Health check for COA Backend deployment

VERSIONS:
  bedrockagent    Check BedrockAgent version
  agentcore       Check AgentCore version
  both            Check both versions

OPTIONS:
  -t, --timeout SECONDS      Health check timeout [default: 30]
  -r, --retry COUNT         Retry count [default: 3]
  --json                    Output results in JSON format
  --exit-code               Exit with non-zero code on failure
  -q, --quiet               Quiet mode (minimal output)
  -h, --help                Show this help message

EXIT CODES:
  0    All health checks passed
  1    Some health checks failed
  2    Critical failure (container not running)

EXAMPLES:
  $0 agentcore                    # Check AgentCore health
  $0 bedrockagent --json          # JSON output for BedrockAgent
  $0 both --timeout 60            # Check both with extended timeout

EOF
}

# Function to check container health
check_container_health() {
    local version="$1"
    local container_name=""
    local port=""
    
    case "${version}" in
        "bedrockagent")
            container_name="coa-bedrockagent"
            port="8000"
            ;;
        "agentcore")
            container_name="coa-agentcore"
            port="8001"
            ;;
        *)
            log_error "Unknown version: ${version}"
            return 2
            ;;
    esac
    
    # Check if container is running
    if ! docker ps --filter "name=${container_name}" --filter "status=running" --format "{{.Names}}" | grep -q "${container_name}"; then
        if [[ "${QUIET}" != "true" ]]; then
            log_error "Container ${container_name} is not running"
        fi
        return 2
    fi
    
    # Check health endpoint
    local retry_count=0
    local max_retries="${RETRY_COUNT}"
    local timeout="${TIMEOUT}"
    local health_url="http://localhost:${port}/health"
    
    while [[ ${retry_count} -lt ${max_retries} ]]; do
        if curl -f -s --max-time "${timeout}" "${health_url}" > /dev/null 2>&1; then
            if [[ "${QUIET}" != "true" ]]; then
                log_success "${version} health check passed"
            fi
            return 0
        else
            ((retry_count++))
            if [[ ${retry_count} -lt ${max_retries} ]]; then
                sleep 2
            fi
        fi
    done
    
    if [[ "${QUIET}" != "true" ]]; then
        log_error "${version} health check failed after ${max_retries} attempts"
    fi
    return 1
}

# Function to get detailed health info
get_health_info() {
    local version="$1"
    local port=""
    
    case "${version}" in
        "bedrockagent")
            port="8000"
            ;;
        "agentcore")
            port="8001"
            ;;
        *)
            echo "{\"error\": \"Unknown version: ${version}\"}"
            return 1
            ;;
    esac
    
    local health_url="http://localhost:${port}/health"
    local health_response=$(curl -s --max-time "${TIMEOUT}" "${health_url}" 2>/dev/null || echo "{\"status\": \"unreachable\"}")
    
    echo "${health_response}"
}

# Function to output JSON results
output_json() {
    local version="$1"
    local results="$2"
    
    echo "{"
    echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"version\": \"${version}\","
    echo "  \"results\": ${results}"
    echo "}"
}

# Parse command line arguments
VERSION="${DEFAULT_VERSION}"
TIMEOUT="${DEFAULT_TIMEOUT}"
RETRY_COUNT="${DEFAULT_RETRY_COUNT}"
JSON_OUTPUT="false"
EXIT_CODE="false"
QUIET="false"

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
        --json)
            JSON_OUTPUT="true"
            shift
            ;;
        --exit-code)
            EXIT_CODE="true"
            shift
            ;;
        -q|--quiet)
            QUIET="true"
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
    local overall_status=0
    local results=""
    
    case "${VERSION}" in
        "bedrockagent")
            if [[ "${JSON_OUTPUT}" == "true" ]]; then
                local health_info=$(get_health_info "bedrockagent")
                results="{ \"bedrockagent\": ${health_info} }"
                output_json "bedrockagent" "${results}"
            else
                if ! check_container_health "bedrockagent"; then
                    overall_status=$?
                fi
            fi
            ;;
        "agentcore")
            if [[ "${JSON_OUTPUT}" == "true" ]]; then
                local health_info=$(get_health_info "agentcore")
                results="{ \"agentcore\": ${health_info} }"
                output_json "agentcore" "${results}"
            else
                if ! check_container_health "agentcore"; then
                    overall_status=$?
                fi
            fi
            ;;
        "both")
            if [[ "${JSON_OUTPUT}" == "true" ]]; then
                local bedrockagent_info=$(get_health_info "bedrockagent")
                local agentcore_info=$(get_health_info "agentcore")
                results="{ \"bedrockagent\": ${bedrockagent_info}, \"agentcore\": ${agentcore_info} }"
                output_json "both" "${results}"
            else
                local bedrockagent_status=0
                local agentcore_status=0
                
                if ! check_container_health "bedrockagent"; then
                    bedrockagent_status=$?
                fi
                
                if ! check_container_health "agentcore"; then
                    agentcore_status=$?
                fi
                
                # Use the highest status code
                if [[ ${bedrockagent_status} -gt ${overall_status} ]]; then
                    overall_status=${bedrockagent_status}
                fi
                if [[ ${agentcore_status} -gt ${overall_status} ]]; then
                    overall_status=${agentcore_status}
                fi
            fi
            ;;
        *)
            log_error "Unknown version: ${VERSION}"
            exit 1
            ;;
    esac
    
    # Exit with appropriate code if requested
    if [[ "${EXIT_CODE}" == "true" ]]; then
        exit ${overall_status}
    fi
    
    exit 0
}

# Execute main function
main "$@"