#!/bin/bash
"""
One-Click Agent Registration Launcher

This is the simplest way to register manually deployed agents with the COA system.
Just run this script and follow the interactive prompts!

Usage:
    ./register_agent.sh
    ./register_agent.sh --region eu-west-1
    ./register_agent.sh --help
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERACTIVE_SCRIPT="$SCRIPT_DIR/interactive_agent_registration.py"

# Source global configuration
CONFIG_LOADER="$SCRIPT_DIR/../utils/load_config.sh"
if [ -f "$CONFIG_LOADER" ]; then
    source "$CONFIG_LOADER"
else
    print_error "Global configuration loader not found: $CONFIG_LOADER"
    exit 1
fi

# Helper functions
print_header() {
    echo -e "\n${BOLD}${BLUE}============================================================${NC}"
    echo -e "${BOLD}${WHITE}                 🚀 COA Agent Registration                 ${NC}"
    echo -e "${BOLD}${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️ $1${NC}"
}

print_step() {
    echo -e "${PURPLE}${BOLD}$1${NC}"
}

# Check if the interactive script exists
check_prerequisites() {
    if [[ ! -f "$INTERACTIVE_SCRIPT" ]]; then
        print_error "Interactive registration script not found: $INTERACTIVE_SCRIPT"
        print_info "Make sure you're running this from the deployment-scripts/components directory"
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check if required Python modules are available
    if ! python3 -c "import boto3" 2>/dev/null; then
        print_error "boto3 Python module is required but not installed"
        print_info "Install with: pip install boto3"
        exit 1
    fi
    
    if ! python3 -c "import yaml" 2>/dev/null; then
        print_warning "PyYAML module not found - some features may be limited"
        print_info "Install with: pip install PyYAML"
    fi
}

# Show help information
show_help() {
    cat << EOF
🚀 COA Agent Registration Tool

This tool provides an interactive way to register manually deployed 
Bedrock AgentCore agents with the COA (Cloud Optimization Assistant) system.

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --region REGION     AWS region to use (default: $DEFAULT_REGION)
    --log-level LEVEL   Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
    --help, -h          Show this help message

EXAMPLES:
    # Use default region (us-east-1)
    $0

    # Specify different region
    $0 --region eu-west-1

    # Enable debug logging
    $0 --region us-east-1 --log-level DEBUG

WHAT THIS TOOL DOES:
    1. 🔍 Discovers available Bedrock AgentCore runtimes in your project
    2. 📋 Shows already registered agents
    3. 🎯 Guides you through selecting and registering new agents
    4. ✅ Verifies integration with COA chatbot system

PREREQUISITES:
    - AWS CLI configured with valid credentials
    - Python 3 with boto3 installed
    - Agents already deployed using agentcore CLI
    - Appropriate IAM permissions for SSM Parameter Store

NEXT STEPS AFTER REGISTRATION:
    1. Launch the COA chatbot web interface
    2. Verify your agent appears in the available agents
    3. Test agent functionality through the chatbot

For more information, see:
    - deployment-scripts/register-agentcore-runtime/README_manual_agent_registration.md
    - deployment-scripts/register-agentcore-runtime/ONE_CLICK_REGISTRATION_GUIDE.md
    - agents/MANUAL_AGENT_REGISTRATION_INSTRUCTIONS.md

EOF
}

# Parse command line arguments
parse_arguments() {
    REGION="$DEFAULT_REGION"
    LOG_LEVEL="INFO"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --region)
                REGION="$2"
                shift 2
                ;;
            --log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                print_info "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# Validate AWS setup
validate_aws_setup() {
    print_step "Validating AWS setup..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is required but not installed"
        print_info "Install from: https://aws.amazon.com/cli/"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured or invalid"
        print_info "Run 'aws configure' to set up your credentials"
        exit 1
    fi
    
    # Get account info
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
    
    print_success "AWS credentials validated"
    print_info "Account: $ACCOUNT_ID"
    print_info "Region: $REGION"
    print_info "User: $USER_ARN"
}

# Check for agentcore CLI
check_agentcore_cli() {
    if command -v agentcore &> /dev/null; then
        print_success "AgentCore CLI found"
        AGENTCORE_VERSION=$(agentcore --version 2>/dev/null || echo "unknown")
        print_info "Version: $AGENTCORE_VERSION"
    else
        print_warning "AgentCore CLI not found"
        print_info "Some discovery features may be limited"
        print_info "Install from: https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-cli.html"
    fi
}

# Main execution
main() {
    # Parse arguments
    parse_arguments "$@"
    
    # Show header
    print_header
    
    echo -e "${BOLD}Welcome to the COA Agent Registration Tool!${NC}"
    echo "This tool will help you register manually deployed agents with the COA chatbot system."
    echo ""
    
    # Check prerequisites
    print_step "Step 1: Checking prerequisites..."
    check_prerequisites
    print_success "Prerequisites validated"
    echo ""
    
    # Load global configuration
    print_step "Step 2: Loading global configuration..."
    if load_deployment_config; then
        print_success "Configuration loaded successfully"
        print_info "Using parameter prefix: $PARAM_PREFIX"
        print_info "Stack name: $STACK_NAME"
    else
        print_error "Failed to load global configuration"
        print_info "Please ensure deployment-config.json exists and is valid"
        exit 1
    fi
    echo ""
    
    # Validate AWS setup
    print_step "Step 3: Validating AWS setup..."
    validate_aws_setup
    echo ""
    
    # Check agentcore CLI
    print_step "Step 4: Checking AgentCore CLI..."
    check_agentcore_cli
    echo ""
    
    # Launch interactive tool
    print_step "Step 5: Launching interactive registration tool..."
    print_info "Starting interactive session..."
    echo ""
    
    # Execute the Python script with stack prefix
    python3 "$INTERACTIVE_SCRIPT" --region "$REGION" --log-level "$LOG_LEVEL" --stack-prefix "$PARAM_PREFIX"
    
    # Check exit code
    EXIT_CODE=$?
    
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo ""
        print_success "Registration tool completed successfully!"
        print_info "Your agents are now ready for use with the COA chatbot"
    elif [[ $EXIT_CODE -eq 130 ]]; then
        echo ""
        print_warning "Registration cancelled by user"
    else
        echo ""
        print_error "Registration tool exited with error code: $EXIT_CODE"
        print_info "Check the logs above for details"
    fi
    
    exit $EXIT_CODE
}

# Run main function with all arguments
main "$@"