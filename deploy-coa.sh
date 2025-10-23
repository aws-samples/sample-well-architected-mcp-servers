#!/bin/bash

# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Cloud Optimization Assistant (COA) End-to-End Deployment Script
# This script deploys the complete COA stack including chatbot, MCP servers, and Bedrock agents

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_STACK_NAME="coa"
STACK_NAME=""
REGION="us-east-1"
ENVIRONMENT="prod"
PROFILE=""
SKIP_PREREQUISITES=false
CLEANUP_ONLY=false
RESUME_FROM_STAGE=0
PROGRESS_FILE=".coa-deployment-progress"
USE_DATE_SUFFIX=true

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Cloud Optimization Assistant (COA) end-to-end stack

OPTIONS:
    -n, --stack-name NAME       CloudFormation stack name (default: coa-MMDD)
    -r, --region REGION         AWS region (default: us-east-1)
    -e, --environment ENV       Environment: dev, staging, prod (default: prod)
    -p, --profile PROFILE       AWS CLI profile name
    -s, --skip-prerequisites    Skip prerequisite checks
    -c, --cleanup               Comprehensive cleanup: delete CloudFormation stack, S3 source buckets, and SSM parameters, then exit
    --no-date-suffix            Don't append date suffix to stack name
    --resume-from-stage N       Resume deployment from stage N (1-7)
    --show-progress             Show current deployment progress and exit
    --reset-progress            Reset deployment progress tracking
    -h, --help                  Show this help message

DEPLOYMENT STAGES:
    1. Deploy chatbot stack and update Cognito callbacks
    2. Generate Cognito SSM parameters
    3. Deploy MCP servers
    4. Deploy Bedrock agent
    5. Generate and upload remote IAM role template
    6. Upload backend source code to trigger CI/CD
    7. Show deployment summary
    8. Final completion

EXAMPLES:
    $0                                          # Deploy with defaults (stack name includes today's date)
    $0 -p gameday -e dev                       # Deploy with gameday profile in dev environment
    $0 -n my-coa-stack -r us-west-2           # Deploy with custom stack name and region
    $0 --no-date-suffix                        # Deploy without date suffix in stack name
    $0 -s                                      # Skip prerequisite checks
    $0 -c                                      # Comprehensive cleanup: delete stack, buckets, and parameters only
    $0 --resume-from-stage 3                   # Resume from stage 3 (Deploy MCP servers)
    $0 --show-progress                         # Show current progress
    $0 --reset-progress                        # Reset progress tracking

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--stack-name)
            STACK_NAME="$2"
            USE_DATE_SUFFIX=false
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        -s|--skip-prerequisites)
            SKIP_PREREQUISITES=true
            shift
            ;;
        -c|--cleanup)
            CLEANUP_ONLY=true
            shift
            ;;
        --no-date-suffix)
            USE_DATE_SUFFIX=false
            shift
            ;;
        --resume-from-stage)
            RESUME_FROM_STAGE="$2"
            if [[ ! "$RESUME_FROM_STAGE" =~ ^[1-8]$ ]]; then
                print_error "Invalid stage number: $RESUME_FROM_STAGE. Must be between 1-8"
                exit 1
            fi
            shift 2
            ;;
        --show-progress)
            # Load and show progress - function will be defined later
            if [[ -f "$PROGRESS_FILE" ]]; then
                source "$PROGRESS_FILE"
                echo "================================================================================"
                echo "                        DEPLOYMENT PROGRESS STATUS"
                echo "================================================================================"
                echo "Last completed stage: $LAST_COMPLETED_STAGE ($LAST_STAGE_NAME)"
                echo "Stack Name:          $STACK_NAME"
                echo "Region:              $REGION"
                echo "Environment:         $ENVIRONMENT"
                if [[ -n "$PROFILE" ]]; then
                    echo "AWS Profile:         $PROFILE"
                fi
                echo "Last updated:        $TIMESTAMP"
                echo
                echo "DEPLOYMENT STAGES:"

                for i in {1..8}; do
                    stage_name=""
                    case $i in
                        1) stage_name="Deploy chatbot stack and update Cognito callbacks" ;;
                        2) stage_name="Generate Cognito SSM parameters" ;;
                        3) stage_name="Deploy MCP servers" ;;
                        4) stage_name="Deploy Bedrock agent" ;;
                        5) stage_name="Generate and upload remote IAM role template" ;;
                        6) stage_name="Upload backend source code to trigger CI/CD" ;;
                        7) stage_name="Show deployment summary" ;;
                        8) stage_name="Final completion" ;;
                    esac

                    if [[ $i -le $LAST_COMPLETED_STAGE ]]; then
                        echo "  ✅ Stage $i: $stage_name"
                    else
                        echo "  ⏳ Stage $i: $stage_name"
                    fi
                done

                echo
                if [[ $LAST_COMPLETED_STAGE -lt 8 ]]; then
                    next_stage=$((LAST_COMPLETED_STAGE + 1))
                    echo "To resume from the next stage, run:"
                    echo "  $0 --resume-from-stage $next_stage"
                else
                    echo "✅ Deployment completed successfully!"
                fi
                echo "================================================================================"
            else
                print_status "No deployment progress found. Start a new deployment with: $0"
            fi
            exit 0
            ;;
        --reset-progress)
            if [[ -f "$PROGRESS_FILE" ]]; then
                rm "$PROGRESS_FILE"
                print_success "Deployment progress reset"
            else
                print_status "No deployment progress found to reset"
            fi
            exit 0
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to save deployment progress
save_progress() {
    local stage=$1
    local stage_name="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    cat > "$PROGRESS_FILE" << EOF
LAST_COMPLETED_STAGE=$stage
LAST_STAGE_NAME="$stage_name"
STACK_NAME="$STACK_NAME"
REGION="$REGION"
ENVIRONMENT="$ENVIRONMENT"
PROFILE="$PROFILE"
TIMESTAMP="$timestamp"
EOF

    print_success "Progress saved: Stage $stage completed ($stage_name)"
}

# Function to load deployment progress
load_progress() {
    if [[ -f "$PROGRESS_FILE" ]]; then
        source "$PROGRESS_FILE"
        return 0
    else
        return 1
    fi
}

# Function to show deployment progress
show_deployment_progress() {
    if load_progress; then
        echo "================================================================================"
        echo "                        DEPLOYMENT PROGRESS STATUS"
        echo "================================================================================"
        echo "Last completed stage: $LAST_COMPLETED_STAGE ($LAST_STAGE_NAME)"
        echo "Stack Name:          $STACK_NAME"
        echo "Region:              $REGION"
        echo "Environment:         $ENVIRONMENT"
        if [[ -n "$PROFILE" ]]; then
            echo "AWS Profile:         $PROFILE"
        fi
        echo "Last updated:        $TIMESTAMP"
        echo
        echo "DEPLOYMENT STAGES:"

        for i in {1..8}; do
            local stage_name=""
            case $i in
                1) stage_name="Deploy chatbot stack and update Cognito callbacks" ;;
                2) stage_name="Generate Cognito SSM parameters" ;;
                3) stage_name="Deploy MCP servers" ;;
                4) stage_name="Deploy Bedrock agent" ;;
                5) stage_name="Generate and upload remote IAM role template" ;;
                6) stage_name="Upload backend source code to trigger CI/CD" ;;
                7) stage_name="Show deployment summary" ;;
                8) stage_name="Final completion" ;;
            esac

            if [[ $i -le $LAST_COMPLETED_STAGE ]]; then
                echo "  ✅ Stage $i: $stage_name"
            else
                echo "  ⏳ Stage $i: $stage_name"
            fi
        done

        echo
        if [[ $LAST_COMPLETED_STAGE -lt 8 ]]; then
            local next_stage=$((LAST_COMPLETED_STAGE + 1))
            echo "To resume from the next stage, run:"
            echo "  $0 --resume-from-stage $next_stage"
        else
            echo "✅ Deployment completed successfully!"
        fi
        echo "================================================================================"
    else
        print_status "No deployment progress found. Start a new deployment with: $0"
    fi
}

# Function to reset deployment progress
reset_deployment_progress() {
    if [[ -f "$PROGRESS_FILE" ]]; then
        rm "$PROGRESS_FILE"
        print_success "Deployment progress reset"
    else
        print_status "No deployment progress found to reset"
    fi
}

# Function to generate stack name with date suffix
generate_stack_name() {
    if [[ -z "$STACK_NAME" ]]; then
        if [[ "$USE_DATE_SUFFIX" == "true" ]]; then
            local date_suffix=$(date '+%m%d')  # Use MMDD format to keep names shorter
            STACK_NAME="${DEFAULT_STACK_NAME}-${date_suffix}"
        else
            STACK_NAME="$DEFAULT_STACK_NAME"
        fi
    fi
    print_status "Using stack name: $STACK_NAME"
}

# Function to validate resume stage
validate_resume_stage() {
    local resume_stage=$1

    if [[ $resume_stage -eq 0 ]]; then
        return 0  # Normal deployment from start
    fi

    if ! load_progress; then
        print_error "No deployment progress found. Cannot resume from stage $resume_stage"
        print_status "Start a new deployment with: $0"
        exit 1
    fi

    if [[ $resume_stage -le $LAST_COMPLETED_STAGE ]]; then
        print_warning "Stage $resume_stage was already completed (last completed: $LAST_COMPLETED_STAGE)"
        read -p "Do you want to re-run this stage? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Use --resume-from-stage $((LAST_COMPLETED_STAGE + 1)) to resume from the next stage"
            exit 0
        fi
    fi

    # Load previous deployment configuration if not explicitly provided
    # Only override defaults with saved values, don't override user-provided values
    local saved_stack_name saved_region saved_environment saved_profile

    # Extract saved values from progress file
    if [[ -f "$PROGRESS_FILE" ]]; then
        saved_stack_name=$(grep '^STACK_NAME=' "$PROGRESS_FILE" | cut -d'"' -f2)
        saved_region=$(grep '^REGION=' "$PROGRESS_FILE" | cut -d'"' -f2)
        saved_environment=$(grep '^ENVIRONMENT=' "$PROGRESS_FILE" | cut -d'"' -f2)
        saved_profile=$(grep '^PROFILE=' "$PROGRESS_FILE" | cut -d'"' -f2)

        # Use saved values if current values are defaults and saved values exist
        if [[ "$STACK_NAME" == "coa" && -n "$saved_stack_name" ]]; then
            STACK_NAME="$saved_stack_name"
            print_status "Using stack name from previous deployment: $STACK_NAME"
        fi

        if [[ "$REGION" == "us-east-1" && -n "$saved_region" ]]; then
            REGION="$saved_region"
            print_status "Using region from previous deployment: $REGION"
        fi

        if [[ "$ENVIRONMENT" == "prod" && -n "$saved_environment" ]]; then
            ENVIRONMENT="$saved_environment"
            print_status "Using environment from previous deployment: $ENVIRONMENT"
        fi

        if [[ -z "$PROFILE" && -n "$saved_profile" ]]; then
            PROFILE="$saved_profile"
            print_status "Using AWS profile from previous deployment: $PROFILE"
        fi
    fi
}

# Function to check prerequisites
check_prerequisites() {
    if [[ "$SKIP_PREREQUISITES" == "true" ]]; then
        print_warning "Skipping prerequisite checks as requested"
        return 0
    fi

    print_status "Checking prerequisites..."

    local failed=false

    # Check shell
    if [[ -z "$BASH_VERSION" ]]; then
        print_error "This script requires Bash shell"
        failed=true
    else
        print_success "Bash shell: $BASH_VERSION"
    fi

    # Check AWS CLI
    if ! command_exists aws; then
        print_error "AWS CLI is not installed. Please install AWS CLI v2"
        print_status "Installation guide: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        failed=true
    else
        local aws_version=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
        print_success "AWS CLI: $aws_version"
    fi

    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is not installed"
        failed=true
    else
        local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_success "Python: $python_version"
    fi

    # Check pip
    if ! command_exists pip3; then
        print_error "pip3 is not installed"
        failed=true
    else
        local pip_version=$(pip3 --version 2>&1 | cut -d' ' -f2)
        print_success "pip3: $pip_version"
    fi

    # Check virtualenv
    if ! command_exists virtualenv && ! python3 -m venv --help >/dev/null 2>&1; then
        print_error "Neither virtualenv nor python3 venv is available"
        print_status "Install with: pip3 install virtualenv"
        failed=true
    else
        print_success "Python virtual environment support available"
    fi

    # Check jq for JSON processing
    if ! command_exists jq; then
        print_warning "jq is not installed. Some JSON processing may be limited"
        print_status "Install with: brew install jq (macOS) or apt-get install jq (Ubuntu)"
    else
        print_success "jq: $(jq --version)"
    fi

    if [[ "$failed" == "true" ]]; then
        print_error "Prerequisites check failed. Please install missing dependencies."
        exit 1
    fi

    print_success "All prerequisites satisfied"
}

# Function to check AWS credentials and permissions
check_aws_credentials() {
    print_status "Checking AWS credentials and permissions..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
        print_status "Using AWS profile: $PROFILE"
    fi

    # Check if credentials are valid
    if ! $aws_cmd sts get-caller-identity >/dev/null 2>&1; then
        print_error "AWS credentials are not valid or not configured"
        if [[ -n "$PROFILE" ]]; then
            print_error "Profile '$PROFILE' may not exist or have invalid credentials"
        fi
        print_status "Configure AWS credentials with: aws configure"
        exit 1
    fi

    local account_id=$($aws_cmd sts get-caller-identity --query Account --output text)
    local user_arn=$($aws_cmd sts get-caller-identity --query Arn --output text)

    print_success "AWS Account: $account_id"
    print_success "User/Role: $user_arn"
    print_success "Region: $REGION"
}

# Function to check for existing SSM parameters that might conflict
check_existing_ssm_parameters() {
    print_status "Checking for existing SSM parameters that might conflict..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    local conflicts_found=false
    local conflicting_params=()
    local conflicting_stacks=()

    # Define the specific parameters that are known to cause conflicts
    local critical_params=(
        "/cloud-optimization-platform/BEDROCK_MODEL_ID"
        "/cloud-optimization-platform/BEDROCK_REGION"
        "/cloud-optimization-platform/USE_ENHANCED_AGENT"
        "/coa/cognito/region"
        "/coa/cognito/user_pool_id"
        "/coa/cognito/web_app_client_id"
        "/coa/cognito/api_client_id"
        "/coa/cognito/mcp_server_client_id"
        "/coa/cognito/user_pool_domain"
        "/coa/cognito/discovery_url"
        "/coa/cognito/user_pool_arn"
        "/coa/cognito/identity_pool_id"
    )

    # Check each critical parameter individually
    print_status "Checking for specific conflicting parameters..."
    for param in "${critical_params[@]}"; do
        if $aws_cmd ssm get-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
            print_warning "Found conflicting parameter: $param"
            conflicting_params+=("$param")
            conflicts_found=true
        fi
    done

    # Check for existing Cognito parameters (broader check)
    local cognito_params
    if cognito_params=$($aws_cmd ssm get-parameters-by-path --path "/coa/cognito" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$cognito_params" && "$cognito_params" != "" ]]; then
            print_warning "Found existing Cognito SSM parameters:"
            for param in $cognito_params; do
                echo "  - $param"
                # Add to conflicting_params if not already there
                if [[ ! " ${conflicting_params[@]} " =~ " ${param} " ]]; then
                    conflicting_params+=("$param")
                fi
            done
            conflicts_found=true
        fi
    fi

    # Check for existing Bedrock parameters (broader check)
    local bedrock_params
    if bedrock_params=$($aws_cmd ssm get-parameters-by-path --path "/cloud-optimization-platform" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$bedrock_params" && "$bedrock_params" != "" ]]; then
            print_warning "Found existing Bedrock SSM parameters:"
            for param in $bedrock_params; do
                echo "  - $param"
                # Add to conflicting_params if not already there
                if [[ ! " ${conflicting_params[@]} " =~ " ${param} " ]]; then
                    conflicting_params+=("$param")
                fi
            done
            conflicts_found=true
        fi
    fi

    # Check for existing CloudFormation stacks that might conflict
    local existing_stacks
    if existing_stacks=$($aws_cmd cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE --query "StackSummaries[?contains(StackName, '$STACK_NAME')].StackName" --output text --region $REGION 2>/dev/null); then
        if [[ -n "$existing_stacks" && "$existing_stacks" != "" ]]; then
            print_warning "Found existing CloudFormation stacks with similar names:"
            for stack in $existing_stacks; do
                echo "  - $stack"
                conflicting_stacks+=("$stack")
            done
            conflicts_found=true
        fi
    fi

    # Check for stacks in DELETE_IN_PROGRESS status that might still have resources
    local deleting_stacks
    if deleting_stacks=$($aws_cmd cloudformation list-stacks --stack-status-filter DELETE_IN_PROGRESS --query "StackSummaries[?contains(StackName, '$STACK_NAME')].StackName" --output text --region $REGION 2>/dev/null); then
        if [[ -n "$deleting_stacks" && "$deleting_stacks" != "" ]]; then
            print_warning "Found CloudFormation stacks currently being deleted:"
            for stack in $deleting_stacks; do
                echo "  - $stack (DELETE_IN_PROGRESS)"
            done
            print_status "Waiting for stack deletion to complete before proceeding..."

            # Wait for deletion to complete
            for stack in $deleting_stacks; do
                print_status "Waiting for stack deletion: $stack"
                if ! $aws_cmd cloudformation wait stack-delete-complete --stack-name "$stack" --region $REGION; then
                    print_error "Stack deletion failed or timed out: $stack"
                    print_status "You may need to manually clean up resources and try again"
                    exit 1
                fi
                print_success "Stack deleted successfully: $stack"
            done
        fi
    fi

    if [[ "$conflicts_found" == "true" ]]; then
        echo
        print_error "Conflicting resources found that may cause deployment failures"
        print_status "Options to resolve:"
        echo "  1. Delete the conflicting resources manually"
        echo "  2. Use a different stack name with --stack-name option"
        echo "  3. Use a different region with --region option"
        echo "  4. Run with --cleanup flag to automatically delete conflicting parameters"
        echo

        if [[ ${#conflicting_params[@]} -gt 0 ]]; then
            print_status "To delete conflicting SSM parameters, run:"
            for param in "${conflicting_params[@]}"; do
                echo "  $aws_cmd ssm delete-parameter --name '$param' --region $REGION"
            done
            echo
        fi

        if [[ ${#conflicting_stacks[@]} -gt 0 ]]; then
            print_status "To delete conflicting CloudFormation stacks, run:"
            for stack in "${conflicting_stacks[@]}"; do
                echo "  $aws_cmd cloudformation delete-stack --stack-name '$stack' --region $REGION"
            done
            echo
        fi

        read -p "Do you want to continue anyway? This may cause deployment failures (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled. Please resolve conflicts and try again."
            print_status "Tip: Run '$0 --cleanup' to automatically delete conflicting SSM parameters"
            exit 1
        fi
        print_warning "Continuing with deployment despite conflicts..."
    else
        print_success "No conflicting SSM parameters or stacks found"
    fi
}

# Function to empty and delete S3 bucket with all versions
empty_s3_bucket_completely() {
    local bucket_name="$1"
    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    print_status "Completely emptying S3 bucket: $bucket_name"
    
    # Check if bucket exists
    if ! $aws_cmd s3api head-bucket --bucket "$bucket_name" --region $REGION >/dev/null 2>&1; then
        print_status "Bucket does not exist: $bucket_name"
        return 0
    fi
    
    # Delete all object versions
    print_status "Deleting all object versions in $bucket_name..."
    local versions
    if versions=$($aws_cmd s3api list-object-versions --bucket "$bucket_name" --query 'Versions[].{Key:Key,VersionId:VersionId}' --output json 2>/dev/null); then
        if [[ "$versions" != "[]" && "$versions" != "null" ]]; then
            $aws_cmd s3api delete-objects --bucket "$bucket_name" --delete "{\"Objects\": $versions}" >/dev/null 2>&1 || true
            print_success "Deleted object versions"
        fi
    fi
    
    # Delete all delete markers
    print_status "Deleting all delete markers in $bucket_name..."
    local delete_markers
    if delete_markers=$($aws_cmd s3api list-object-versions --bucket "$bucket_name" --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' --output json 2>/dev/null); then
        if [[ "$delete_markers" != "[]" && "$delete_markers" != "null" ]]; then
            $aws_cmd s3api delete-objects --bucket "$bucket_name" --delete "{\"Objects\": $delete_markers}" >/dev/null 2>&1 || true
            print_success "Deleted delete markers"
        fi
    fi
    
    # Delete the bucket
    if $aws_cmd s3api delete-bucket --bucket "$bucket_name" --region $REGION >/dev/null 2>&1; then
        print_success "Deleted S3 bucket: $bucket_name"
        return 0
    else
        print_warning "Failed to delete S3 bucket: $bucket_name"
        return 1
    fi
}

# Function to clean up all S3 buckets
cleanup_s3_buckets() {
    print_status "Cleaning up all S3 buckets..."
    
    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    local buckets_deleted=0
    local buckets_failed=0
    
    # Get account ID
    local account_id
    if account_id=$($aws_cmd sts get-caller-identity --query Account --output text 2>/dev/null); then
        
        # List of expected bucket patterns
        local bucket_patterns=(
            "${STACK_NAME}-source-${account_id}-${REGION}"
            "${STACK_NAME}-frontend-${account_id}-${REGION}"
            "${STACK_NAME}-artifacts-${account_id}-${REGION}"
        )
        
        for bucket_name in "${bucket_patterns[@]}"; do
            if empty_s3_bucket_completely "$bucket_name"; then
                ((buckets_deleted++))
            else
                ((buckets_failed++))
            fi
        done
        
        # Also look for any other buckets with the stack name
        print_status "Checking for additional buckets with stack name pattern..."
        local all_buckets
        if all_buckets=$($aws_cmd s3api list-buckets --query "Buckets[?contains(Name, '${STACK_NAME}')].Name" --output text 2>/dev/null); then
            if [[ -n "$all_buckets" && "$all_buckets" != "" ]]; then
                for bucket in $all_buckets; do
                    # Skip if already processed
                    local already_processed=false
                    for pattern in "${bucket_patterns[@]}"; do
                        if [[ "$bucket" == "$pattern" ]]; then
                            already_processed=true
                            break
                        fi
                    done
                    
                    if [[ "$already_processed" == "false" ]]; then
                        print_warning "Found additional bucket: $bucket"
                        if empty_s3_bucket_completely "$bucket"; then
                            ((buckets_deleted++))
                        else
                            ((buckets_failed++))
                        fi
                    fi
                done
            fi
        fi
    else
        print_error "Failed to get AWS account ID"
        return 1
    fi
    
    # Summary
    print_success "Processed S3 buckets: $buckets_deleted deleted, $buckets_failed failed"
}

# Function to clean up CloudFormation stack
cleanup_cloudformation_stack() {
    print_status "Cleaning up CloudFormation stack..."
    
    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    # Check if stack exists
    if $aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION >/dev/null 2>&1; then
        print_status "Found CloudFormation stack: $STACK_NAME"
        
        # Get stack status
        local stack_status
        if stack_status=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].StackStatus' --output text 2>/dev/null); then
            print_status "Current stack status: $stack_status"
            
            case $stack_status in
                "DELETE_IN_PROGRESS")
                    print_status "Stack is already being deleted, waiting for completion..."
                    if $aws_cmd cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION; then
                        print_success "Stack deletion completed successfully"
                    else
                        print_warning "Stack deletion may have failed or timed out"
                    fi
                    ;;
                "DELETE_FAILED")
                    print_warning "Stack is in DELETE_FAILED state, attempting to delete again..."
                    if $aws_cmd cloudformation delete-stack --stack-name $STACK_NAME --region $REGION; then
                        print_status "Stack deletion re-initiated, waiting for completion..."
                        if $aws_cmd cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION; then
                            print_success "Stack deletion completed successfully"
                        else
                            print_warning "Stack deletion may have failed or timed out"
                        fi
                    else
                        print_error "Failed to initiate stack deletion"
                    fi
                    ;;
                *)
                    print_status "Initiating stack deletion..."
                    if $aws_cmd cloudformation delete-stack --stack-name $STACK_NAME --region $REGION; then
                        print_status "Stack deletion initiated, waiting for completion..."
                        if $aws_cmd cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION; then
                            print_success "Stack deletion completed successfully"
                        else
                            print_warning "Stack deletion may have failed or timed out"
                        fi
                    else
                        print_error "Failed to initiate stack deletion"
                    fi
                    ;;
            esac
        fi
    else
        print_status "CloudFormation stack not found: $STACK_NAME"
    fi
}

# Function to clean up existing SSM parameters
cleanup_existing_parameters() {
    print_status "Cleaning up existing SSM parameters..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    local params_deleted=0
    local params_failed=0

    # Define the specific parameters that are known to cause conflicts
    local critical_params=(
        "/cloud-optimization-platform/BEDROCK_MODEL_ID"
        "/cloud-optimization-platform/BEDROCK_REGION"
        "/cloud-optimization-platform/USE_ENHANCED_AGENT"
        "/coa/cognito/region"
        "/coa/cognito/user_pool_id"
        "/coa/cognito/web_app_client_id"
        "/coa/cognito/api_client_id"
        "/coa/cognito/mcp_server_client_id"
        "/coa/cognito/user_pool_domain"
        "/coa/cognito/discovery_url"
        "/coa/cognito/user_pool_arn"
        "/coa/cognito/identity_pool_id"
    )

    # First, try to delete specific critical parameters
    print_status "Deleting critical SSM parameters that cause conflicts..."
    for param in "${critical_params[@]}"; do
        if $aws_cmd ssm get-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
            if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                print_success "Deleted: $param"
                ((params_deleted++))
            else
                print_warning "Failed to delete: $param (may be protected by CloudFormation)"
                ((params_failed++))
            fi
        fi
    done

    # Clean up Cognito parameters (broader cleanup)
    local cognito_params
    if cognito_params=$($aws_cmd ssm get-parameters-by-path --path "/coa/cognito" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$cognito_params" && "$cognito_params" != "" ]]; then
            print_status "Deleting remaining Cognito SSM parameters..."
            for param in $cognito_params; do
                if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                    print_success "Deleted: $param"
                    ((params_deleted++))
                else
                    print_warning "Failed to delete: $param (may be protected by CloudFormation)"
                    ((params_failed++))
                fi
            done
        fi
    fi

    # Clean up Bedrock parameters (broader cleanup)
    local bedrock_params
    if bedrock_params=$($aws_cmd ssm get-parameters-by-path --path "/cloud-optimization-platform" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$bedrock_params" && "$bedrock_params" != "" ]]; then
            print_status "Deleting remaining Bedrock SSM parameters..."
            for param in $bedrock_params; do
                if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                    print_success "Deleted: $param"
                    ((params_deleted++))
                else
                    print_warning "Failed to delete: $param (may be protected by CloudFormation)"
                    ((params_failed++))
                fi
            done
        fi
    fi

    # Clean up MCP component parameters
    local mcp_params
    if mcp_params=$($aws_cmd ssm get-parameters-by-path --path "/coa/components" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$mcp_params" && "$mcp_params" != "" ]]; then
            print_status "Deleting MCP component SSM parameters..."
            for param in $mcp_params; do
                if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                    print_success "Deleted: $param"
                    ((params_deleted++))
                else
                    print_warning "Failed to delete: $param"
                    ((params_failed++))
                fi
            done
        fi
    fi

    # Clean up agent parameters
    local agent_params
    if agent_params=$($aws_cmd ssm get-parameters-by-path --path "/coa/agent" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$agent_params" && "$agent_params" != "" ]]; then
            print_status "Deleting agent SSM parameters..."
            for param in $agent_params; do
                if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                    print_success "Deleted: $param"
                    ((params_deleted++))
                else
                    print_warning "Failed to delete: $param"
                    ((params_failed++))
                fi
            done
        fi
    fi

    # Summary
    if [[ $params_deleted -eq 0 && $params_failed -eq 0 ]]; then
        print_status "No SSM parameters found to clean up"
    else
        print_success "Cleaned up $params_deleted SSM parameters"
        if [[ $params_failed -gt 0 ]]; then
            print_warning "$params_failed parameters could not be deleted (likely protected by CloudFormation)"
        fi
    fi

    # Check for CloudFormation stacks that might be protecting parameters
    local existing_stacks
    if existing_stacks=$($aws_cmd cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE --query "StackSummaries[?contains(StackName, '$STACK_NAME')].StackName" --output text --region $REGION 2>/dev/null); then
        if [[ -n "$existing_stacks" && "$existing_stacks" != "" ]]; then
            print_warning "Found existing CloudFormation stacks that may be protecting SSM parameters:"
            for stack in $existing_stacks; do
                echo "  - $stack"
                print_status "To delete stack and its parameters: $aws_cmd cloudformation delete-stack --stack-name $stack --region $REGION"
            done
            echo
            print_status "Note: Deleting CloudFormation stacks will also delete their associated SSM parameters"
        fi
    fi

    # Check for stacks in DELETE_IN_PROGRESS status
    local deleting_stacks
    if deleting_stacks=$($aws_cmd cloudformation list-stacks --stack-status-filter DELETE_IN_PROGRESS --query "StackSummaries[?contains(StackName, '$STACK_NAME')].StackName" --output text --region $REGION 2>/dev/null); then
        if [[ -n "$deleting_stacks" && "$deleting_stacks" != "" ]]; then
            print_status "Found CloudFormation stacks currently being deleted:"
            for stack in $deleting_stacks; do
                echo "  - $stack (DELETE_IN_PROGRESS)"
            done
            print_status "These stacks are being deleted and their parameters will be cleaned up automatically"
        fi
    fi
}

# Function to check Bedrock model access
check_bedrock_model_access() {
    print_status "Checking Bedrock model access..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    # Check if Bedrock service is available in the region
    if ! $aws_cmd bedrock list-foundation-models --region $REGION >/dev/null 2>&1; then
        print_error "Cannot access Bedrock service in region $REGION"
        print_error "Bedrock may not be available in this region or you may lack permissions"
        exit 1
    fi

    # Check specific model access (Claude 3 Haiku)
    local model_id="anthropic.claude-3-haiku-20240307-v1:0"
    if $aws_cmd bedrock get-foundation-model --model-identifier $model_id --region $REGION >/dev/null 2>&1; then
        print_success "Bedrock model access verified: $model_id"
    else
        print_warning "Cannot access model $model_id"
        print_warning "You may need to request model access in the Bedrock console"
        print_status "Continue anyway? The deployment will proceed but the agent may not work properly."
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to create demo user with correct credentials
create_demo_user() {
    print_status "Creating demo user with credentials matching the login page..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    # Get User Pool ID from stack outputs
    local user_pool_id
    if user_pool_id=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' --output text 2>/dev/null); then
        if [[ -n "$user_pool_id" && "$user_pool_id" != "None" ]]; then
            print_status "Creating demo user in User Pool: $user_pool_id"

            # Demo credentials that match the login page
            local demo_email="testuser@example.com"
            local demo_password="TestPass123!"

            # Check if user already exists
            if $aws_cmd cognito-idp admin-get-user --user-pool-id "$user_pool_id" --username "$demo_email" --region $REGION >/dev/null 2>&1; then
                print_status "Demo user already exists, updating password..."
                # Update existing user password
                if $aws_cmd cognito-idp admin-set-user-password --user-pool-id "$user_pool_id" --username "$demo_email" --password "$demo_password" --permanent --region $REGION >/dev/null 2>&1; then
                    print_success "Demo user password updated successfully"
                else
                    print_warning "Failed to update demo user password"
                fi
            else
                print_status "Creating new demo user..."
                # Create new user
                if $aws_cmd cognito-idp admin-create-user --user-pool-id "$user_pool_id" --username "$demo_email" --user-attributes Name=email,Value="$demo_email" Name=email_verified,Value=true --temporary-password "TempPass123!" --message-action SUPPRESS --region $REGION >/dev/null 2>&1; then
                    # Set permanent password
                    if $aws_cmd cognito-idp admin-set-user-password --user-pool-id "$user_pool_id" --username "$demo_email" --password "$demo_password" --permanent --region $REGION >/dev/null 2>&1; then
                        print_success "Demo user created successfully"
                        echo "  📧 Email: $demo_email"
                        echo "  🔑 Password: $demo_password"
                    else
                        print_warning "Demo user created but failed to set permanent password"
                    fi
                else
                    print_warning "Failed to create demo user"
                fi
            fi
        else
            print_warning "Could not retrieve User Pool ID from stack outputs"
        fi
    else
        print_warning "Failed to get User Pool information from CloudFormation stack"
    fi
}

# Function to invalidate CloudFront cache
invalidate_cloudfront_cache() {
    print_status "Invalidating CloudFront cache..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    # Get CloudFront distribution ID
    local cloudfront_domain distribution_id
    if cloudfront_domain=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomainName`].OutputValue' --output text 2>/dev/null); then
        if distribution_id=$($aws_cmd cloudfront list-distributions --query "DistributionList.Items[?contains(DomainName, '$cloudfront_domain')].Id" --output text 2>/dev/null); then
            if [[ -n "$distribution_id" && "$distribution_id" != "" ]]; then
                print_status "Invalidating cache for distribution: $distribution_id"
                if $aws_cmd cloudfront create-invalidation --distribution-id "$distribution_id" --paths "/config.js" "/index.html" "/*" >/dev/null 2>&1; then
                    print_success "CloudFront cache invalidation created successfully"
                else
                    print_warning "Failed to create CloudFront cache invalidation"
                fi
            else
                print_warning "Could not find CloudFront distribution ID"
            fi
        else
            print_warning "Failed to list CloudFront distributions"
        fi
    else
        print_warning "Could not retrieve CloudFront domain from stack outputs"
    fi
}

# Function to validate frontend configuration
validate_frontend_config() {
    print_status "Validating frontend configuration..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    # Get stack outputs
    local user_pool_id web_app_client_id frontend_bucket cloudfront_domain
    if user_pool_id=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' --output text 2>/dev/null) &&
       web_app_client_id=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`WebAppClientId`].OutputValue' --output text 2>/dev/null) &&
       frontend_bucket=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text 2>/dev/null) &&
       cloudfront_domain=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomainName`].OutputValue' --output text 2>/dev/null); then

        print_status "Expected configuration:"
        echo "  User Pool ID: $user_pool_id"
        echo "  Client ID: $web_app_client_id"
        echo "  CloudFront Domain: $cloudfront_domain"

        # Check current config.js in S3
        print_status "Checking current frontend configuration..."
        local current_config
        if current_config=$($aws_cmd s3 cp s3://$frontend_bucket/config.js - --region $REGION 2>/dev/null); then
            if echo "$current_config" | grep -q "$user_pool_id" && echo "$current_config" | grep -q "$web_app_client_id"; then
                print_success "Frontend configuration is correct"
                return 0
            else
                print_warning "Frontend configuration is incorrect, needs update"
                return 1
            fi
        else
            print_warning "Could not retrieve current frontend configuration"
            return 1
        fi
    else
        print_error "Failed to get required stack outputs for validation"
        return 1
    fi
}

# Function to deploy chatbot stack
deploy_chatbot_stack() {
    print_status "Deploying chatbot stack..."

    local python_args="--stack-name $STACK_NAME --region $REGION --environment $ENVIRONMENT"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    if ! python3 deployment-scripts/deploy_chatbot_stack.py $python_args; then
        print_error "Chatbot stack deployment failed"
        exit 1
    fi

    print_success "Chatbot stack deployed successfully"
}

# Function to generate Cognito SSM parameters
generate_cognito_params() {
    print_status "Generating Cognito SSM parameters..."

    local python_args="--stack-name $STACK_NAME --region $REGION"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    if ! python3 deployment-scripts/generate_cognito_ssm_parameters.py $python_args; then
        print_error "Cognito SSM parameters generation failed"
        exit 1
    fi

    print_success "Cognito SSM parameters generated successfully"
}

# Function to deploy MCP servers
deploy_mcp_servers() {
    print_status "Deploying MCP servers..."

    local python_args="--region $REGION"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    # Deploy WA Security MCP Server (AWS API MCP Server not available in this repository)
    print_status "Deploying WA Security MCP Server..."
    if ! python3 deployment-scripts/components/deploy_component_wa_security_mcp.py $python_args; then
        print_warning "WA Security MCP Server deployment failed - continuing with deployment"
        print_status "You can deploy MCP servers manually later if needed"
        return 0  # Don't fail the entire deployment
    fi

    print_success "MCP servers deployed successfully"
}

# Function to deploy Bedrock agent
deploy_bedrock_agent() {
    print_status "Deploying Bedrock agent..."

    local python_args="--region $REGION"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    if ! python3 deployment-scripts/components/deploy_bedrockagent_wa_security_agent.py $python_args; then
        print_error "Bedrock agent deployment failed"
        exit 1
    fi

    print_success "Bedrock agent deployed successfully"
}

# Function to generate and upload remote role stack template
generate_and_upload_remote_role_stack() {
    print_status "Generating remote IAM role CloudFormation template..."

    local python_args="--environment $ENVIRONMENT"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    # Generate the remote role stack template
    if ! python3 deployment-scripts/generate_remote_role_stack.py $python_args; then
        print_error "Remote role stack template generation failed"
        exit 1
    fi

    print_success "Remote role stack template generated successfully"

    # Upload template to S3 and get public URL
    print_status "Uploading remote role template to S3..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    # Get the S3 bucket name from the chatbot stack outputs
    local s3_bucket
    if s3_bucket=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text 2>/dev/null); then
        if [[ -n "$s3_bucket" && "$s3_bucket" != "None" ]]; then
            print_status "Using S3 bucket: $s3_bucket"

            # Find the generated template file
            local template_file
            if template_file=$(find generated-templates/remote-role-stack -name "remote-role-*.yaml" -type f | head -1 2>/dev/null); then
                if [[ -f "$template_file" ]]; then
                    local template_filename=$(basename "$template_file")

                    # Upload template to S3
                    if $aws_cmd s3 cp "$template_file" "s3://$s3_bucket/templates/$template_filename" --region $REGION; then
                        # Generate public URL
                        local template_url="https://$s3_bucket.s3.amazonaws.com/templates/$template_filename"
                        print_success "Template uploaded successfully: $template_url"

                        # Update the index.html file with the new template URL
                        update_index_html_template_url "$template_url"

                        # Re-deploy frontend with updated template URL
                        print_status "Re-deploying frontend with updated template URL..."
                        local python_args="--stack-name $STACK_NAME --region $REGION"
                        if [[ -n "$PROFILE" ]]; then
                            python_args="$python_args --profile $PROFILE"
                        fi

                        if python3 deployment-scripts/deploy_frontend.py $python_args; then
                            print_success "Frontend re-deployed with updated template URL"
                        else
                            print_warning "Failed to re-deploy frontend - template URL may not be updated"
                        fi

                        return 0
                    else
                        print_error "Failed to upload template to S3"
                        return 1
                    fi
                else
                    print_error "Generated template file not found: $template_file"
                    return 1
                fi
            else
                print_error "No generated template files found in generated-templates/remote-role-stack/"
                return 1
            fi
        else
            print_error "Could not retrieve S3 bucket name from stack outputs"
            return 1
        fi
    else
        print_error "Failed to get S3 bucket information from CloudFormation stack"
        return 1
    fi
}

# Function to update index.html with new template URL
update_index_html_template_url() {
    local new_template_url="$1"
    local index_file="cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend/index.html"

    print_status "Updating index.html with new template URL..."

    if [[ -f "$index_file" ]]; then
        # Create a backup
        cp "$index_file" "$index_file.backup"

        # Generate CloudFormation deployment URL
        local cf_url="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?templateURL=${new_template_url}&stackName=remote-mcp-role&capabilities=CAPABILITY_IAM"

        # Update the href in the deployment link
        if command_exists sed; then
            # Use sed to replace the href URL
            sed -i.tmp "s|href=\"[^\"]*\"|href=\"${cf_url}\"|g" "$index_file" && rm "$index_file.tmp"
            print_success "Updated deployment link in index.html"
        else
            print_warning "sed not available - please manually update the deployment link in $index_file"
            print_status "New CloudFormation URL: $cf_url"
        fi
    else
        print_warning "index.html file not found at $index_file"
    fi
}

# Function to upload backend source code and trigger CI/CD pipeline
upload_backend_source_code() {
    print_status "=== STAGE 3: Application Code Deployment ==="
    print_status "Packaging and uploading backend source code..."
    
    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    # Calculate SourceBucket name (same pattern as in deploy_chatbot_stack.py)
    local account_id
    if account_id=$($aws_cmd sts get-caller-identity --query Account --output text 2>/dev/null); then
        local source_bucket="${STACK_NAME}-source-${account_id}-${REGION}"
        print_status "Using SourceBucket: $source_bucket"
        
        # Create source code archive
        print_status "Creating source code archive..."
        local temp_dir=$(mktemp -d)
        local source_zip="$temp_dir/source.zip"
        
        # Create zip from the cloud-optimization-web-interfaces directory
        if [[ -d "cloud-optimization-web-interfaces" ]]; then
            cd cloud-optimization-web-interfaces/
            if zip -r "$source_zip" . -x "*.git*" "*__pycache__*" "*.pyc" "*.DS_Store" "node_modules/*" >/dev/null 2>&1; then
                cd ..
                print_success "Source code archive created: $(du -h "$source_zip" | cut -f1)"
                
                # Upload to S3 to trigger CI/CD pipeline
                print_status "Uploading source code to trigger CI/CD pipeline..."
                if $aws_cmd s3 cp "$source_zip" "s3://$source_bucket/source.zip" --region $REGION; then
                        print_success "Backend source code uploaded successfully"
                        print_status "CI/CD pipeline should be triggered automatically"
                        
                        # Monitor pipeline execution
                        monitor_pipeline_execution
                        
                        # Cleanup temp file
                        rm -rf "$temp_dir"
                    return 0
                else
                    print_error "Failed to upload backend source code to S3"
                    rm -rf "$temp_dir"
                    return 1
                fi
            else
                cd ..
                print_error "Failed to create source code archive"
                rm -rf "$temp_dir"
                return 1
            fi
        else
            print_error "cloud-optimization-web-interfaces directory not found"
            rm -rf "$temp_dir"
            return 1
        fi
    else
        print_error "Failed to get AWS account ID"
        return 1
    fi
}

# Function to monitor CodePipeline execution
monitor_pipeline_execution() {
    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    local pipeline_name="$STACK_NAME-pipeline"
    print_status "Monitoring CodePipeline execution: $pipeline_name"
    
    # Wait for pipeline to start executing (up to 2 minutes)
    local timeout=120
    local elapsed=0
    local pipeline_found=false
    
    while [[ $elapsed -lt $timeout ]]; do
        if $aws_cmd codepipeline get-pipeline-state --name "$pipeline_name" --region $REGION >/dev/null 2>&1; then
            pipeline_found=true
            print_success "CodePipeline found and monitoring execution"
            
            # Get current execution status
            local pipeline_state
            if pipeline_state=$($aws_cmd codepipeline get-pipeline-state --name "$pipeline_name" --region $REGION --query 'stageStates[0].latestExecution.status' --output text 2>/dev/null); then
                if [[ "$pipeline_state" != "None" && "$pipeline_state" != "" ]]; then
                    print_status "Pipeline execution started with status: $pipeline_state"
                    break
                fi
            fi
        fi
        sleep 10
        elapsed=$((elapsed + 10))
        print_status "Waiting for pipeline to start... ($elapsed/${timeout}s)"
    done
    
    if [[ "$pipeline_found" == "true" ]]; then
        print_success "CodePipeline execution initiated successfully"
        print_status "Monitor progress in AWS Console: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/$pipeline_name/view"
    else
        print_warning "CodePipeline may not have started yet - check AWS Console manually"
    fi
}

# Function to display deployment summary
show_deployment_summary() {
    print_status "Retrieving deployment information..."

    local aws_cmd="aws"
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi

    # Get CloudFormation stack outputs
    local stack_outputs
    if stack_outputs=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs' --output json 2>/dev/null); then
        echo
        echo "================================================================================"
        echo "                    CLOUD OPTIMIZATION ASSISTANT DEPLOYMENT SUMMARY"
        echo "================================================================================"
        echo "Stack Name:    $STACK_NAME"
        echo "Region:        $REGION"
        echo "Environment:   $ENVIRONMENT"
        if [[ -n "$PROFILE" ]]; then
            echo "AWS Profile:   $PROFILE"
        fi
        echo
        echo "Stack Outputs:"

        if command_exists jq && [[ "$stack_outputs" != "null" ]]; then
            echo "$stack_outputs" | jq -r '.[] | "  \(.OutputKey): \(.OutputValue)"'
        else
            echo "  (Install jq for formatted output)"
        fi

        echo
        echo "================================================================================"
        echo "                                NEXT STEPS"
        echo "================================================================================"
        echo "1. 🌐 Access your application via the CloudFront URL above"
        echo "2. 👤 Configure users in the Cognito User Pool"
        echo "3. 📦 Monitor Backend CI/CD Pipeline:"
        echo "   - CodePipeline: Source → Build → Deploy stages"
        echo "   - Backend will be built from Docker and deployed to ECS automatically"
        echo "   - Check AWS Console for pipeline execution status"
        echo "4. 📊 Monitor the deployment in AWS Console"
        echo "5. 🤖 Test the Bedrock agent functionality"
        echo "6. 🔐 Deploy the remote IAM role in target AWS accounts using the one-click link"
        echo "   in the web interface for cross-account security scanning"
        echo
        echo "================================================================================"
        echo "                              DEMO CREDENTIALS"
        echo "================================================================================"
        echo "📧 Email: testuser@example.com"
        echo "🔑 Password: TestPass123!"
        echo
        echo "These credentials match what is displayed on the login page."
        echo "================================================================================"
        echo
        echo "For troubleshooting, check CloudWatch logs and CloudFormation events."
        echo "================================================================================"
    else
        print_warning "Could not retrieve stack information"
    fi
}

# Function to execute deployment stage
execute_stage() {
    local stage=$1
    local stage_name="$2"
    local stage_function="$3"

    echo
    print_status "Step $stage/7: $stage_name..."

    if $stage_function; then
        save_progress $stage "$stage_name"
        return 0
    else
        print_error "Stage $stage failed: $stage_name"
        print_status "To resume from this stage after fixing the issue, run:"
        print_status "  $0 --resume-from-stage $stage"
        exit 1
    fi
}

# Stage 1: Deploy chatbot stack and update configurations
stage_1_deploy_chatbot() {
    deploy_chatbot_stack

    # Update Cognito callback URLs with CloudFront domain
    print_status "Updating Cognito callback URLs with CloudFront domain..."
    local python_args="--stack-name $STACK_NAME --region $REGION"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    if python3 deployment-scripts/update_cognito_callbacks.py $python_args; then
        print_success "Cognito callback URLs updated successfully"
    else
        print_warning "Failed to update Cognito callback URLs - you may need to update them manually"
    fi

    # Deploy frontend files
    print_status "Deploying frontend files to S3..."
    if python3 deployment-scripts/deploy_frontend.py $python_args; then
        print_success "Frontend files deployed successfully"

        # Validate frontend configuration
        if ! validate_frontend_config; then
            print_warning "Frontend configuration validation failed, attempting to redeploy..."
            # Wait a moment and try again
            sleep 5
            if python3 deployment-scripts/deploy_frontend.py $python_args; then
                print_success "Frontend redeployed successfully"
                # Invalidate CloudFront cache to ensure new config is served
                invalidate_cloudfront_cache
                # Wait for cache invalidation to start propagating
                sleep 10
                if validate_frontend_config; then
                    print_success "Frontend configuration validated successfully"
                else
                    print_warning "Frontend configuration still incorrect after redeploy - cache may need time to propagate"
                fi
            else
                print_warning "Frontend redeploy failed"
            fi
        else
            # Even if validation passes, invalidate cache to ensure fresh content
            invalidate_cloudfront_cache
        fi
    else
        print_warning "Failed to deploy frontend files - you may need to deploy them manually"
    fi

    # Note: Backend source code upload will be handled in a later stage
    # after MCP servers and Bedrock agents are deployed

    # Create demo user with correct credentials
    create_demo_user

    return 0
}

# Stage 2: Generate Cognito SSM parameters
stage_2_generate_cognito_params() {
    generate_cognito_params
    return $?
}

# Stage 3: Deploy MCP servers
stage_3_deploy_mcp_servers() {
    deploy_mcp_servers
    return $?
}

# Stage 4: Deploy Bedrock agent
stage_4_deploy_bedrock_agent() {
    deploy_bedrock_agent
    return $?
}

# Stage 5: Generate and upload remote role stack template
stage_5_generate_remote_role() {
    print_status "Generating remote IAM role CloudFormation template..."
    
    local python_args="--environment $ENVIRONMENT"
    if [[ -n "$PROFILE" ]]; then
        python_args="$python_args --profile $PROFILE"
    fi

    # Try to generate the remote role stack template
    if python3 deployment-scripts/generate_remote_role_stack.py $python_args; then
        print_success "Remote role stack template generated successfully"
        
        # Try to upload template to S3 and get public URL
        local aws_cmd="aws"
        if [[ -n "$PROFILE" ]]; then
            aws_cmd="aws --profile $PROFILE"
        fi

        # Get the S3 bucket name from the chatbot stack outputs
        local s3_bucket
        if s3_bucket=$($aws_cmd cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text 2>/dev/null); then
            if [[ -n "$s3_bucket" && "$s3_bucket" != "None" ]]; then
                # Find the generated template file
                local template_file
                if template_file=$(find generated-templates/remote-role-stack -name "remote-role-*.yaml" -type f | head -1 2>/dev/null); then
                    if [[ -f "$template_file" ]]; then
                        local template_filename=$(basename "$template_file")
                        # Upload template to S3
                        if $aws_cmd s3 cp "$template_file" "s3://$s3_bucket/templates/$template_filename" --region $REGION; then
                            local template_url="https://$s3_bucket.s3.amazonaws.com/templates/$template_filename"
                            print_success "Template uploaded successfully: $template_url"
                        else
                            print_warning "Failed to upload template to S3"
                        fi
                    fi
                fi
            fi
        fi
        return 0
    else
        print_warning "Remote role template generation failed - this is optional"
        print_status "You can generate cross-account roles manually later if needed"
        print_status "The main COA platform is functional without cross-account roles"
        return 0  # Don't fail the deployment for this optional step
    fi
}

# Stage 6: Upload backend source code to trigger CI/CD
stage_6_upload_backend_code() {
    print_status "=== STAGE 6: Backend Code Deployment ==="
    if upload_backend_source_code; then
        print_success "Backend CI/CD pipeline initiated successfully"
        print_status "The backend will be automatically built and deployed via CodePipeline"
        return 0
    else
        print_warning "Backend source code upload failed - you may need to upload manually"
        print_status "Manual upload: Upload cloud-optimization-web-interfaces/ as source.zip to the SourceBucket"
        print_status "This will not prevent the rest of the deployment from continuing"
        return 0  # Don't fail the deployment for this
    fi
}

# Stage 7: Show deployment summary
stage_7_show_summary() {
    show_deployment_summary
    return 0
}

# Stage 8: Final completion
stage_8_final_completion() {
    print_success "Cloud Optimization Assistant deployment completed successfully! 🎉"
    return 0
}

# Main execution flow
main() {
    echo "================================================================================"
    echo "           Cloud Optimization Assistant (COA) Deployment Script"
    echo "================================================================================"
    echo

    # Handle cleanup-only mode
    if [[ "$CLEANUP_ONLY" == "true" ]]; then
        print_status "Running in comprehensive cleanup mode..."
        
        # Generate stack name for cleanup
        generate_stack_name
        
        check_aws_credentials
        
        echo "================================================================================"
        echo "                           COMPREHENSIVE CLEANUP"
        echo "================================================================================"
        echo "Stack Name:   $STACK_NAME"
        echo "Region:       $REGION"
        echo "Environment:  $ENVIRONMENT"
        if [[ -n "$PROFILE" ]]; then
            echo "AWS Profile:  $PROFILE"
        fi
        echo
        
        # Confirm cleanup for production
        if [[ "$ENVIRONMENT" == "prod" ]]; then
            print_warning "You are cleaning up PRODUCTION environment resources"
            read -p "Are you sure you want to continue? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_status "Cleanup cancelled"
                exit 0
            fi
        fi
        
        # Step 1: Clean up CloudFormation stack (this should clean up most resources)
        cleanup_cloudformation_stack
        echo
        
        # Step 2: Clean up S3 source buckets (created outside CloudFormation)
        cleanup_s3_source_buckets
        echo
        
        # Step 3: Clean up SSM parameters (may be left over from previous deployments)
        cleanup_existing_parameters
        
        echo
        print_success "Comprehensive cleanup completed!"
        echo "================================================================================"
        exit 0
    fi

    # Generate stack name with date suffix if needed
    generate_stack_name
    
    # Validate resume stage and load previous configuration if resuming
    validate_resume_stage $RESUME_FROM_STAGE

    # Show resume information if applicable
    if [[ $RESUME_FROM_STAGE -gt 0 ]]; then
        print_status "Resuming deployment from stage $RESUME_FROM_STAGE"
        if load_progress; then
            print_status "Previous deployment info:"
            echo "  Last completed stage: $LAST_COMPLETED_STAGE ($LAST_STAGE_NAME)"
            echo "  Timestamp: $TIMESTAMP"
        fi
        echo
    fi

    # Run initial checks only if starting from beginning or stage 1
    if [[ $RESUME_FROM_STAGE -le 1 ]]; then
        # Check prerequisites
        check_prerequisites

        # Check AWS credentials and permissions
        check_aws_credentials

        # Check for existing SSM parameters and stacks
        check_existing_ssm_parameters

        # Check Bedrock model access
        check_bedrock_model_access
    else
        # For resume, just check AWS credentials
        check_aws_credentials
    fi

    echo
    print_status "Deployment configuration:"
    echo "  Stack Name:   $STACK_NAME"
    echo "  Region:       $REGION"
    echo "  Environment:  $ENVIRONMENT"
    if [[ -n "$PROFILE" ]]; then
        echo "  AWS Profile:  $PROFILE"
    fi
    if [[ $RESUME_FROM_STAGE -gt 0 ]]; then
        echo "  Resume from:  Stage $RESUME_FROM_STAGE"
    fi
    echo

    # Confirm deployment for production (only if starting fresh or from stage 1)
    if [[ "$ENVIRONMENT" == "prod" && $RESUME_FROM_STAGE -le 1 ]]; then
        print_warning "You are deploying to PRODUCTION environment"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled"
            exit 0
        fi
    fi

    # Execute deployment stages
    local start_stage=${RESUME_FROM_STAGE:-1}

    if [[ $start_stage -le 1 ]]; then
        execute_stage 1 "Deploy chatbot stack and update Cognito callbacks" "stage_1_deploy_chatbot"
    fi

    if [[ $start_stage -le 2 ]]; then
        execute_stage 2 "Generate Cognito SSM parameters" "stage_2_generate_cognito_params"
    fi

    if [[ $start_stage -le 3 ]]; then
        execute_stage 3 "Deploy MCP servers" "stage_3_deploy_mcp_servers"
    fi

    if [[ $start_stage -le 4 ]]; then
        execute_stage 4 "Deploy Bedrock agent" "stage_4_deploy_bedrock_agent"
    fi

    if [[ $start_stage -le 5 ]]; then
        execute_stage 5 "Generate and upload remote IAM role template" "stage_5_generate_remote_role"
    fi

    if [[ $start_stage -le 6 ]]; then
        execute_stage 6 "Upload backend source code to trigger CI/CD" "stage_6_upload_backend_code"
    fi

    if [[ $start_stage -le 7 ]]; then
        execute_stage 7 "Show deployment summary" "stage_7_show_summary"
    fi

    if [[ $start_stage -le 8 ]]; then
        execute_stage 8 "Final completion" "stage_8_final_completion"
    fi

    # Clean up progress file on successful completion
    if [[ -f "$PROGRESS_FILE" ]]; then
        rm "$PROGRESS_FILE"
    fi
}

# Trap to handle script interruption
trap 'print_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"
