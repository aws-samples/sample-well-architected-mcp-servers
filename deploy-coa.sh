#!/bin/bash

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
STACK_NAME="cloud-optimization-assistant"
REGION="us-east-1"
ENVIRONMENT="prod"
PROFILE=""
SKIP_PREREQUISITES=false
CLEANUP_ONLY=false

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
    -n, --stack-name NAME       CloudFormation stack name (default: cloud-optimization-assistant)
    -r, --region REGION         AWS region (default: us-east-1)
    -e, --environment ENV       Environment: dev, staging, prod (default: prod)
    -p, --profile PROFILE       AWS CLI profile name
    -s, --skip-prerequisites    Skip prerequisite checks
    -c, --cleanup               Clean up existing SSM parameters and exit
    -h, --help                  Show this help message

EXAMPLES:
    $0                                          # Deploy with defaults
    $0 -p gameday -e dev                       # Deploy with gameday profile in dev environment
    $0 -n my-coa-stack -r us-west-2           # Deploy with custom stack name and region
    $0 -s                                      # Skip prerequisite checks
    $0 -c                                      # Clean up existing SSM parameters only

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--stack-name)
            STACK_NAME="$2"
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
    
    # Check for existing Cognito parameters
    local cognito_params
    if cognito_params=$($aws_cmd ssm get-parameters-by-path --path "/coa/cognito" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$cognito_params" && "$cognito_params" != "" ]]; then
            print_warning "Found existing Cognito SSM parameters:"
            for param in $cognito_params; do
                echo "  - $param"
                conflicting_params+=("$param")
            done
            conflicts_found=true
        fi
    fi
    
    # Check for existing Bedrock parameters
    local bedrock_params
    if bedrock_params=$($aws_cmd ssm get-parameters-by-path --path "/cloud-optimization-platform" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$bedrock_params" && "$bedrock_params" != "" ]]; then
            print_warning "Found existing Bedrock SSM parameters:"
            for param in $bedrock_params; do
                echo "  - $param"
                conflicting_params+=("$param")
            done
            conflicts_found=true
        fi
    fi
    
    # Check for existing CloudFormation stacks that might conflict
    local existing_stacks
    if existing_stacks=$($aws_cmd cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[?contains(StackName, '$STACK_NAME')].StackName" --output text --region $REGION 2>/dev/null); then
        if [[ -n "$existing_stacks" && "$existing_stacks" != "" ]]; then
            print_warning "Found existing CloudFormation stacks with similar names:"
            for stack in $existing_stacks; do
                echo "  - $stack"
            done
            conflicts_found=true
        fi
    fi
    
    if [[ "$conflicts_found" == "true" ]]; then
        echo
        print_error "Conflicting resources found that may cause deployment failures"
        print_status "Options to resolve:"
        echo "  1. Delete the conflicting resources manually"
        echo "  2. Use a different stack name with --stack-name option"
        echo "  3. Use a different region with --region option"
        echo
        
        if [[ ${#conflicting_params[@]} -gt 0 ]]; then
            print_status "To delete conflicting SSM parameters, run:"
            for param in "${conflicting_params[@]}"; do
                echo "  $aws_cmd ssm delete-parameter --name '$param' --region $REGION"
            done
            echo
        fi
        
        read -p "Do you want to continue anyway? This may cause deployment failures (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled. Please resolve conflicts and try again."
            exit 1
        fi
        print_warning "Continuing with deployment despite conflicts..."
    else
        print_success "No conflicting SSM parameters or stacks found"
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
    
    # Clean up Cognito parameters
    local cognito_params
    if cognito_params=$($aws_cmd ssm get-parameters-by-path --path "/coa/cognito" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$cognito_params" && "$cognito_params" != "" ]]; then
            print_status "Deleting Cognito SSM parameters..."
            for param in $cognito_params; do
                if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                    print_success "Deleted: $param"
                    ((params_deleted++))
                else
                    print_warning "Failed to delete: $param"
                fi
            done
        fi
    fi
    
    # Clean up Bedrock parameters
    local bedrock_params
    if bedrock_params=$($aws_cmd ssm get-parameters-by-path --path "/cloud-optimization-platform" --query 'Parameters[].Name' --output text --region $REGION 2>/dev/null); then
        if [[ -n "$bedrock_params" && "$bedrock_params" != "" ]]; then
            print_status "Deleting Bedrock SSM parameters..."
            for param in $bedrock_params; do
                if $aws_cmd ssm delete-parameter --name "$param" --region $REGION >/dev/null 2>&1; then
                    print_success "Deleted: $param"
                    ((params_deleted++))
                else
                    print_warning "Failed to delete: $param"
                fi
            done
        fi
    fi
    
    if [[ $params_deleted -eq 0 ]]; then
        print_status "No SSM parameters found to clean up"
    else
        print_success "Cleaned up $params_deleted SSM parameters"
    fi
    
    # List any remaining CloudFormation stacks for manual cleanup
    local existing_stacks
    if existing_stacks=$($aws_cmd cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE --query "StackSummaries[?contains(StackName, '$STACK_NAME')].StackName" --output text --region $REGION 2>/dev/null); then
        if [[ -n "$existing_stacks" && "$existing_stacks" != "" ]]; then
            print_warning "Found existing CloudFormation stacks that may need manual cleanup:"
            for stack in $existing_stacks; do
                echo "  - $stack"
                print_status "To delete: $aws_cmd cloudformation delete-stack --stack-name $stack --region $REGION"
            done
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
    
    # Deploy AWS API MCP Server
    print_status "Deploying AWS API MCP Server..."
    if ! python3 deployment-scripts/components/deploy_component_aws_api_mcp_server.py $python_args; then
        print_error "AWS API MCP Server deployment failed"
        exit 1
    fi
    
    # Deploy WA Security MCP Server
    print_status "Deploying WA Security MCP Server..."
    if ! python3 deployment-scripts/components/deploy_component_wa_security_mcp.py $python_args; then
        print_error "WA Security MCP Server deployment failed"
        exit 1
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
    
    local python_args="--region $REGION --environment $ENVIRONMENT"
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
        echo "3. 🔧 Upload source code to trigger CI/CD pipeline"
        echo "4. 📊 Monitor the deployment in AWS Console"
        echo "5. 🤖 Test the Bedrock agent functionality"
        echo "6. 🔐 Deploy the remote IAM role in target AWS accounts using the one-click link"
        echo "   in the web interface for cross-account security scanning"
        echo
        echo "For troubleshooting, check CloudWatch logs and CloudFormation events."
        echo "================================================================================"
    else
        print_warning "Could not retrieve stack information"
    fi
}

# Main execution flow
main() {
    echo "================================================================================"
    echo "           Cloud Optimization Assistant (COA) Deployment Script"
    echo "================================================================================"
    echo
    
    # Handle cleanup-only mode
    if [[ "$CLEANUP_ONLY" == "true" ]]; then
        print_status "Running in cleanup mode..."
        check_aws_credentials
        cleanup_existing_parameters
        print_success "Cleanup completed!"
        exit 0
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Check AWS credentials and permissions
    check_aws_credentials
    
    # Check for existing SSM parameters and stacks
    check_existing_ssm_parameters
    
    # Check Bedrock model access
    check_bedrock_model_access
    
    echo
    print_status "Starting deployment with the following configuration:"
    echo "  Stack Name:   $STACK_NAME"
    echo "  Region:       $REGION"
    echo "  Environment:  $ENVIRONMENT"
    if [[ -n "$PROFILE" ]]; then
        echo "  AWS Profile:  $PROFILE"
    fi
    echo
    
    # Confirm deployment
    if [[ "$ENVIRONMENT" == "prod" ]]; then
        print_warning "You are deploying to PRODUCTION environment"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled"
            exit 0
        fi
    fi
    
    # Step 1: Deploy chatbot stack
    echo
    print_status "Step 1/6: Deploying chatbot stack..."
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
    else
        print_warning "Failed to deploy frontend files - you may need to deploy them manually"
    fi
    
    # Step 2: Generate Cognito SSM parameters
    echo
    print_status "Step 2/6: Generating Cognito SSM parameters..."
    generate_cognito_params
    
    # Step 3: Deploy MCP servers
    echo
    print_status "Step 3/6: Deploying MCP servers..."
    deploy_mcp_servers
    
    # Step 4: Deploy Bedrock agent
    echo
    print_status "Step 4/7: Deploying Bedrock agent..."
    deploy_bedrock_agent
    
    # Step 5: Generate and upload remote role stack template
    echo
    print_status "Step 5/7: Generating and uploading remote IAM role template..."
    if generate_and_upload_remote_role_stack; then
        print_success "Remote role template generated and uploaded successfully"
    else
        print_warning "Remote role template generation/upload failed - continuing with deployment"
    fi
    
    # Step 6: Show deployment summary
    echo
    print_status "Step 6/7: Deployment complete!"
    show_deployment_summary
    
    # Step 7: Final success message
    echo
    print_status "Step 7/7: All deployment steps completed!"
    print_success "Cloud Optimization Assistant deployment completed successfully! 🎉"
}

# Trap to handle script interruption
trap 'print_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"