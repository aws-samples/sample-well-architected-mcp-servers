#!/bin/bash

# Helper script to update the template URL in index.html
# Usage: ./update-template-url.sh <new-template-url>

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if template URL is provided
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <template-url>"
    echo ""
    echo "Example:"
    echo "  $0 https://my-bucket.s3.amazonaws.com/templates/remote-role-template.yaml"
    exit 1
fi

NEW_TEMPLATE_URL="$1"
INDEX_FILE="cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend/index.html"

print_status "Updating index.html with new template URL..."
print_status "New template URL: $NEW_TEMPLATE_URL"

# Check if index.html exists
if [[ ! -f "$INDEX_FILE" ]]; then
    print_error "index.html file not found at $INDEX_FILE"
    exit 1
fi

# Create a backup
cp "$INDEX_FILE" "$INDEX_FILE.backup.$(date +%Y%m%d_%H%M%S)"
print_status "Created backup of index.html"

# Generate CloudFormation deployment URL
CF_URL="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?templateURL=${NEW_TEMPLATE_URL}&stackName=remote-mcp-role&capabilities=CAPABILITY_IAM"

print_status "Generated CloudFormation URL: $CF_URL"

# Update the href in the deployment link
if command -v sed >/dev/null 2>&1; then
    # Find and replace the href URL in the deployment link
    if grep -q "templateURL=" "$INDEX_FILE"; then
        # Replace existing templateURL
        sed -i.tmp "s|templateURL=[^&\"]*|templateURL=${NEW_TEMPLATE_URL}|g" "$INDEX_FILE" && rm "$INDEX_FILE.tmp"
        print_success "Updated existing templateURL in index.html"
    elif grep -q "href=\"https://console.aws.amazon.com/cloudformation" "$INDEX_FILE"; then
        # Replace entire CloudFormation href
        sed -i.tmp "s|href=\"https://console.aws.amazon.com/cloudformation[^\"]*\"|href=\"${CF_URL}\"|g" "$INDEX_FILE" && rm "$INDEX_FILE.tmp"
        print_success "Updated CloudFormation deployment link in index.html"
    else
        print_warning "Could not find existing deployment link to update"
        print_status "Please manually update the deployment link in $INDEX_FILE"
        print_status "Use this URL: $CF_URL"
    fi
else
    print_error "sed command not available"
    print_status "Please manually update the deployment link in $INDEX_FILE"
    print_status "Use this URL: $CF_URL"
    exit 1
fi

# Verify the update
if grep -q "$NEW_TEMPLATE_URL" "$INDEX_FILE"; then
    print_success "Template URL successfully updated in index.html"
else
    print_warning "Template URL may not have been updated correctly"
    print_status "Please verify the changes in $INDEX_FILE"
fi

print_status "Update completed!"