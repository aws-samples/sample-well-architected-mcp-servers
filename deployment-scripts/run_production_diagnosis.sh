#!/bin/bash

# Production Runtime Diagnosis Script
# Run this in your production environment to diagnose the Bedrock issue

echo "==================================="
echo "Production Runtime Diagnosis"
echo "Account: 256358067059"
echo "==================================="

# Set the target account profile if available
export AWS_PROFILE=256358067059 2>/dev/null || true

# Run the diagnostic script
python3 diagnose_production_runtime.py

echo ""
echo "==================================="
echo "Additional AWS CLI Diagnostics"
echo "==================================="

# Check current AWS identity
echo "Current AWS Identity:"
aws sts get-caller-identity 2>&1 || echo "Failed to get caller identity"

echo ""
echo "Available Bedrock Models in us-east-1:"
aws bedrock list-foundation-models --region us-east-1 --by-output-modality TEXT --query 'modelSummaries[?contains(modelId, `claude`)].{ModelId:modelId,Provider:providerName}' --output table 2>&1 || echo "Failed to list Bedrock models"

echo ""
echo "Bedrock Service Quotas:"
aws service-quotas get-service-quota --service-code bedrock --quota-code L-12345678 --region us-east-1 2>&1 || echo "Failed to get service quotas"

echo ""
echo "Recent CloudTrail Events (Bedrock related):"
aws logs filter-log-events --log-group-name CloudTrail/BedrockEvents --start-time $(date -d '1 hour ago' +%s)000 --filter-pattern "bedrock" --region us-east-1 2>&1 || echo "No CloudTrail logs found or access denied"

echo ""
echo "==================================="
echo "Diagnosis Complete"
echo "==================================="