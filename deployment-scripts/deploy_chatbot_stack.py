#!/usr/bin/env python3

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

"""
Cloud Optimization Assistant Chatbot Stack Deployment Script
Deploys the complete infrastructure with CI/CD pipeline and frontend in a single stack
Supports cloud-optimization-assistant templates versions 0.1.0, 0.1.2, and 0.1.3
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ChatbotStackDeployer:
    def __init__(
        self,
        stack_name: str = "coa",
        region: str = "us-east-1",
        environment: str = "prod",
        profile: Optional[str] = None,
        template_version: str = "0.1.3",
    ):
        """
        Initialize the chatbot stack deployer

        Args:
            stack_name: Main CloudFormation stack name
            region: AWS region
            environment: Environment (dev, staging, prod)
            profile: AWS CLI profile name (optional)
            template_version: CloudFormation template version (0.1.0, 0.1.2, or 0.1.3)
        """
        self.stack_name = stack_name
        self.region = region
        self.template_version = template_version
        self.environment = environment
        self.profile = profile

        # Create session with profile if specified
        if profile:
            session = boto3.Session(profile_name=profile)
            logger.info(f"Using AWS profile: {profile}")
        else:
            session = boto3.Session()
            logger.info("Using default AWS credentials")

        # Initialize AWS clients with session
        self.cf_client = session.client("cloudformation", region_name=region)
        self.s3_client = session.client("s3", region_name=region)
        self.sts_client = session.client("sts", region_name=region)
        self.ssm_client = session.client("ssm", region_name=region)
        self.cognito_client = session.client("cognito-idp", region_name=region)

        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()["Account"]

        # Load parameter prefix from configuration
        self.param_prefix = self._load_parameter_prefix()

        logger.info(
            f"Initialized chatbot deployer for account {self.account_id} in region {region}"
        )
        logger.info(f"Using parameter prefix: {self.param_prefix}")

    def _sanitize_bucket_name(self, name: str) -> str:
        """Sanitize name for S3 bucket naming requirements"""
        # Replace underscores with hyphens for S3 compatibility
        # S3 bucket names must be lowercase and cannot contain underscores
        sanitized = name.replace('_', '-').lower()
        return sanitized

    def _load_parameter_prefix(self) -> str:
        """Load parameter prefix from deployment configuration"""
        import json
        from pathlib import Path
        
        config_file = Path("deployment-config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                return config.get('deployment', {}).get('param_prefix', self.stack_name)
            except Exception as e:
                logger.warning(f"Could not load parameter prefix from config: {e}")
        
        # Fallback to stack name if config not available
        return self.stack_name

    def create_s3_bucket_for_source(self) -> str:
        """Create S3 bucket for storing backend source code"""
        sanitized_stack_name = self._sanitize_bucket_name(self.stack_name)
        bucket_name = f"{sanitized_stack_name}-source-{self.account_id}-{self.region}"

        try:
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            # Enable versioning for source code tracking
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

            # Enable EventBridge for S3 events (will be configured by CloudFormation)
            try:
                self.s3_client.put_bucket_notification_configuration(
                    Bucket=bucket_name,
                    NotificationConfiguration={"EventBridgeConfiguration": {}},
                )
                logger.info(
                    f"Enabled EventBridge notifications for bucket: {bucket_name}"
                )
            except ClientError as e:
                logger.warning(f"Could not enable EventBridge notifications: {e}")
                # This is not critical for the deployment

            logger.info(f"Created source code bucket: {bucket_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
                logger.info(f"Source bucket already exists: {bucket_name}")
            else:
                raise

        return bucket_name

    def apply_bucket_policy(self, source_bucket: str):
        """Apply bucket policy to allow CodeBuild and CodePipeline access"""
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCodeBuildAndPipelineAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": [
                            f"arn:aws:iam::{self.account_id}:role/{self.stack_name}-codebuild-role",
                            f"arn:aws:iam::{self.account_id}:role/{self.stack_name}-pipeline-role",
                        ]
                    },
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:ListBucket",
                        "s3:GetBucketVersioning",
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{source_bucket}",
                        f"arn:aws:s3:::{source_bucket}/*",
                    ],
                }
            ],
        }

        try:
            self.s3_client.put_bucket_policy(
                Bucket=source_bucket, Policy=json.dumps(bucket_policy)
            )
            logger.info(f"Applied bucket policy to {source_bucket}")
        except ClientError as e:
            logger.warning(f"Failed to apply bucket policy: {e}")
            logger.info(
                "Continuing deployment - IAM role permissions should be sufficient"
            )

    def load_template(self) -> str:
        """Load the chatbot CloudFormation template"""
        template_path = (
            Path(__file__).parent / f"cloud-optimization-assistant-{self.template_version}.yaml"
        )

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(template_path, "r") as f:
            return f.read()

    def upload_template_to_s3(self, template_body: str, bucket_name: str) -> str:
        """Upload CloudFormation template to S3 and return the URL"""
        template_key = f"templates/cloud-optimization-assistant-{self.template_version}.yaml"
        
        try:
            # Upload template to S3
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=template_key,
                Body=template_body,
                ContentType="text/yaml"
            )
            
            # Generate template URL
            template_url = f"https://{bucket_name}.s3.amazonaws.com/{template_key}"
            logger.info(f"Template uploaded to S3: {template_url}")
            logger.info(f"Template size: {len(template_body)} bytes")
            
            return template_url
            
        except ClientError as e:
            logger.error(f"Failed to upload template to S3: {e}")
            raise

    def configure_s3_bucket_for_eventbridge(self, bucket_name: str):
        """Configure S3 bucket for EventBridge notifications"""
        try:
            # Enable EventBridge for S3 events
            self.s3_client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={"EventBridgeConfiguration": {}},
            )
            logger.info(f"EventBridge notifications configured for bucket: {bucket_name}")
        except ClientError as e:
            logger.warning(f"Could not configure EventBridge notifications: {e}")
            # This is not critical for the basic deployment

    def deploy(self) -> Dict[str, Any]:
        """Deploy the chatbot CloudFormation stack using optimized 3-stage approach"""
        
        logger.info("=== STAGE 1: Infrastructure Preparation ===")
        
        # Stage 1: Create S3 bucket for source code (outside CloudFormation)
        actual_source_bucket = self.create_s3_bucket_for_source()
        
        # Configure EventBridge notifications for the bucket
        self.configure_s3_bucket_for_eventbridge(actual_source_bucket)
        
        logger.info("=== STAGE 2: CloudFormation Deployment ===")
        
        # Stage 2: Deploy CloudFormation stack using S3 template URL to avoid size limits
        template_body = self.load_template()
        
        # Upload template to S3 to avoid CloudFormation inline template size limits (51KB)
        template_url = self.upload_template_to_s3(template_body, actual_source_bucket)
        
        parameters = [
            {"ParameterKey": "Environment", "ParameterValue": self.environment},
            {"ParameterKey": "SourceBucket", "ParameterValue": actual_source_bucket},
            {"ParameterKey": "ParameterPrefix", "ParameterValue": self.param_prefix},
        ]

        logger.info(f"Deploying stack: {self.stack_name}")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Using existing SourceBucket: {actual_source_bucket}")
        logger.info(f"Template size: {len(template_body)} bytes (using S3 URL to avoid 51,200 byte inline limit)")

        try:
            # Check if stack exists
            try:
                self.cf_client.describe_stacks(StackName=self.stack_name)
                stack_exists = True
                logger.info(f"Stack {self.stack_name} exists, updating...")
            except ClientError as e:
                if "does not exist" in str(e):
                    stack_exists = False
                    logger.info(f"Stack {self.stack_name} does not exist, creating...")
                else:
                    raise

            if stack_exists:
                response = self.cf_client.update_stack(
                    StackName=self.stack_name,
                    TemplateURL=template_url,
                    Parameters=parameters,
                    Capabilities=["CAPABILITY_NAMED_IAM"],
                )
                operation = "UPDATE"
            else:
                response = self.cf_client.create_stack(
                    StackName=self.stack_name,
                    TemplateURL=template_url,
                    Parameters=parameters,
                    Capabilities=["CAPABILITY_NAMED_IAM"],
                    OnFailure="ROLLBACK",
                )
                operation = "CREATE"

            stack_id = response["StackId"]
            logger.info(f"Stack {operation} initiated: {stack_id}")

            # Wait for stack operation to complete
            if operation == "CREATE":
                waiter = self.cf_client.get_waiter("stack_create_complete")
                logger.info("Waiting for stack creation to complete...")
            else:
                waiter = self.cf_client.get_waiter("stack_update_complete")
                logger.info("Waiting for stack update to complete...")

            waiter.wait(
                StackName=self.stack_name,
                WaiterConfig={
                    "Delay": 30,
                    "MaxAttempts": 120,  # 60 minutes max
                },
            )

            # Apply bucket policy after stack creation
            self.apply_bucket_policy(actual_source_bucket)

            # Get stack outputs
            stack_info = self.cf_client.describe_stacks(StackName=self.stack_name)
            stack = stack_info["Stacks"][0]

            outputs = {}
            if "Outputs" in stack:
                for output in stack["Outputs"]:
                    outputs[output["OutputKey"]] = output["OutputValue"]

            logger.info(f"Stack {operation.lower()} completed successfully!")

            return {
                "StackName": self.stack_name,
                "StackId": stack_id,
                "StackStatus": stack["StackStatus"],
                "Region": self.region,
                "Environment": self.environment,
                "SourceBucket": outputs.get("SourceBucketName", ""),
                "Outputs": outputs,
            }

        except ClientError as e:
            if "No updates are to be performed" in str(e):
                logger.info("No updates needed for the stack")
                # Still return stack info
                stack_info = self.cf_client.describe_stacks(StackName=self.stack_name)
                stack = stack_info["Stacks"][0]

                outputs = {}
                if "Outputs" in stack:
                    for output in stack["Outputs"]:
                        outputs[output["OutputKey"]] = output["OutputValue"]

                return {
                    "StackName": self.stack_name,
                    "StackId": stack["StackId"],
                    "StackStatus": stack["StackStatus"],
                    "Region": self.region,
                    "Environment": self.environment,
                    "SourceBucket": outputs.get("SourceBucketName", ""),
                    "Outputs": outputs,
                }
            else:
                logger.error(f"Stack deployment failed: {e}")
                raise

    def check_cognito_deployment(self) -> bool:
        """Check if Cognito resources are deployed and accessible"""
        try:
            # Get stack outputs to find Cognito resources
            stack_info = self.cf_client.describe_stacks(StackName=self.stack_name)
            stack = stack_info["Stacks"][0]

            user_pool_id = None
            if "Outputs" in stack:
                for output in stack["Outputs"]:
                    if output["OutputKey"] == "UserPoolId":
                        user_pool_id = output["OutputValue"]
                        break

            if not user_pool_id:
                logger.error("UserPoolId not found in stack outputs")
                return False

            # Try to describe the user pool
            response = self.cognito_client.describe_user_pool(UserPoolId=user_pool_id)
            logger.info(f"Cognito User Pool verified: {user_pool_id}")
            logger.info(f"User Pool Name: {response['UserPool']['Name']}")
            return True

        except ClientError as e:
            logger.error(f"Failed to verify Cognito deployment: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Cloud Optimization Assistant Chatbot Stack"
    )
    parser.add_argument(
        "--stack-name",
        default="coa",
        help="CloudFormation stack name",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument(
        "--environment",
        default="prod",
        choices=["dev", "staging", "prod"],
        help="Environment name",
    )
    parser.add_argument("--profile", help="AWS CLI profile name")
    parser.add_argument(
        "--template-version",
        default="0.1.3",
        choices=["0.1.0", "0.1.2", "0.1.3"],
        help="CloudFormation template version to use",
    )

    args = parser.parse_args()

    try:
        deployer = ChatbotStackDeployer(
            stack_name=args.stack_name,
            region=args.region,
            environment=args.environment,
            profile=args.profile,
            template_version=args.template_version,
        )

        result = deployer.deploy()

        print("\n" + "=" * 80)
        print("CHATBOT STACK DEPLOYMENT SUMMARY")
        print("=" * 80)
        print(f"Stack Name: {result['StackName']}")
        print(f"Stack ID: {result['StackId']}")
        print(f"Status: {result['StackStatus']}")
        print(f"Region: {result['Region']}")
        print(f"Environment: {result['Environment']}")
        print(f"Source Bucket: {result['SourceBucket']}")

        print("\nKey Outputs:")
        for key, value in result["Outputs"].items():
            print(f"  {key}: {value}")

        # Verify Cognito deployment
        print("\n" + "=" * 80)
        print("COGNITO VERIFICATION")
        print("=" * 80)
        if deployer.check_cognito_deployment():
            print("✅ Cognito resources deployed and accessible")
        else:
            print("❌ Cognito verification failed")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
