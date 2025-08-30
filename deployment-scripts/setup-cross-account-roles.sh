#!/bin/bash

# Cross-Account Role Setup Script
# This script sets up cross-account role assumption between AgentCore Runtime and target accounts

set -e

# Configuration
SOURCE_ACCOUNT="384612698411"
TARGET_ACCOUNT="256358067059"
SOURCE_ROLE="AmazonBedrockAgentCoreSDKRuntime-us-east-1-0a5c2f9775"
TARGET_ROLE="ReadOnly"
EXTERNAL_ID="CloudOptimizationAssistant"

echo "🔧 Setting up Cross-Account Role Assumption"
echo "================================================"
echo "Source Account: $SOURCE_ACCOUNT"
echo "Source Role: $SOURCE_ROLE"
echo "Target Account: $TARGET_ACCOUNT"
echo "Target Role: $TARGET_ROLE"
echo "External ID: $EXTERNAL_ID"
echo ""

# Step 1: Create policy for source role to assume target roles
echo "📝 Step 1: Creating assume role policy for source role..."

cat > assume-role-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": [
        "arn:aws:iam::$TARGET_ACCOUNT:role/$TARGET_ROLE",
        "arn:aws:iam::*:role/$TARGET_ROLE"
      ],
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "$EXTERNAL_ID"
        }
      }
    }
  ]
}
EOF

# Create the policy in the source account
echo "Creating IAM policy in source account..."
aws iam create-policy \
    --policy-name "CrossAccountAssumeRolePolicy" \
    --policy-document file://assume-role-policy.json \
    --description "Allows AgentCore Runtime to assume ReadOnly roles in target accounts" \
    --profile source-account 2>/dev/null || echo "Policy may already exist"

# Attach policy to the source role
echo "Attaching policy to source role..."
aws iam attach-role-policy \
    --role-name "$SOURCE_ROLE" \
    --policy-arn "arn:aws:iam::$SOURCE_ACCOUNT:policy/CrossAccountAssumeRolePolicy" \
    --profile source-account

echo "✅ Step 1 completed"
echo ""

# Step 2: Update trust policy for target role
echo "📝 Step 2: Updating trust policy for target role..."

cat > target-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$SOURCE_ACCOUNT:role/$SOURCE_ROLE"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "$EXTERNAL_ID"
        }
      }
    }
  ]
}
EOF

# Update trust policy for target role
echo "Updating trust policy for target role..."
aws iam update-assume-role-policy \
    --role-name "$TARGET_ROLE" \
    --policy-document file://target-trust-policy.json \
    --profile target-account

echo "✅ Step 2 completed"
echo ""

# Step 3: Test the role assumption
echo "🧪 Step 3: Testing role assumption..."

echo "Testing role assumption from source account..."
aws sts assume-role \
    --role-arn "arn:aws:iam::$TARGET_ACCOUNT:role/$TARGET_ROLE" \
    --role-session-name "CloudOptimizationTest" \
    --external-id "$EXTERNAL_ID" \
    --profile source-account \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output table

echo "✅ Step 3 completed"
echo ""

# Cleanup temporary files
#rm -f assume-role-policy.json target-trust-policy.json

echo "🎉 Cross-account role setup completed successfully!"
echo ""
echo "📋 Summary:"
echo "- Source role can now assume target role with External ID: $EXTERNAL_ID"
echo "- Use the External ID when assuming the role programmatically"
echo "- Test the setup using the AWS CLI or your application"
echo ""
echo "🔧 Next steps:"
echo "1. Update your application to use the External ID when assuming roles"
echo "2. Test the cross-account access with your Cloud Optimization Assistant"
echo "3. Monitor CloudTrail logs for successful role assumptions"