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
Complete Cloud Optimization Platform Deployment Script
Deploys the complete infrastructure with CI/CD pipeline and frontend in a single stack

This script uses the complete CloudFormation template that includes:
- Infrastructure (VPC, ECS, ALB, etc.)
- CI/CD Pipeline (CodePipeline, CodeBuild for backend and frontend)
- Frontend (S3, CloudFront, Cognito authentication)
- Cognito authentication
- ECR repository
"""

import boto3
import json
import time
import os
import sys
import argparse
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompletePlatformDeployer:
    def __init__(self, 
                 stack_name: str = "cloud-optimization-platform",
                 region: str = "us-east-1",
                 environment: str = "prod",
                 profile: Optional[str] = None):
        """
        Initialize the complete platform deployer
        
        Args:
            stack_name: Main CloudFormation stack name
            region: AWS region
            environment: Environment (dev, staging, prod)
            profile: AWS CLI profile name (optional)
        """
        self.stack_name = stack_name
        self.region = region
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
        self.cf_client = session.client('cloudformation', region_name=region)
        self.s3_client = session.client('s3', region_name=region)
        self.sts_client = session.client('sts', region_name=region)
        self.ssm_client = session.client('ssm', region_name=region)
        self.cognito_client = session.client('cognito-idp', region_name=region)
        
        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        logger.info(f"Initialized complete deployer for account {self.account_id} in region {region}")

    def create_s3_bucket_for_source(self) -> str:
        """Create S3 bucket for storing backend source code"""
        bucket_name = f"{self.stack_name}-source-{self.account_id}-{self.region}"
        
        try:
            if self.region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # Enable versioning for source code tracking
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            # Enable EventBridge for S3 events (will be configured by CloudFormation)
            try:
                self.s3_client.put_bucket_notification_configuration(
                    Bucket=bucket_name,
                    NotificationConfiguration={
                        'EventBridgeConfiguration': {}
                    }
                )
                logger.info(f"Enabled EventBridge notifications for bucket: {bucket_name}")
            except ClientError as e:
                logger.warning(f"Could not enable EventBridge notifications: {e}")
                # This is not critical for the deployment
            
            logger.info(f"Created source code bucket: {bucket_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
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
                            f"arn:aws:iam::{self.account_id}:role/{self.stack_name}-pipeline-role"
                        ]
                    },
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:ListBucket",
                        "s3:GetBucketVersioning"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{source_bucket}",
                        f"arn:aws:s3:::{source_bucket}/*"
                    ]
                }
            ]
        }
        
        try:
            self.s3_client.put_bucket_policy(
                Bucket=source_bucket,
                Policy=json.dumps(bucket_policy)
            )
            logger.info(f"Applied bucket policy to {source_bucket}")
        except ClientError as e:
            logger.warning(f"Failed to apply bucket policy: {e}")
            logger.info("Continuing deployment - IAM role permissions should be sufficient")

    def load_template(self) -> str:
        """Load the complete CloudFormation template"""
        template_path = Path(__file__).parent / "complete-platform-template.yaml"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r') as f:
            template_content = f.read()
        
        logger.info(f"Loaded template from {template_path}")
        return template_content

    def deploy_stack(self, source_bucket: str) -> Dict[str, Any]:
        """Deploy the complete CloudFormation stack"""
        
        template_body = self.load_template()
        
        parameters = [
            {
                'ParameterKey': 'Environment',
                'ParameterValue': self.environment
            },
            {
                'ParameterKey': 'SourceBucket',
                'ParameterValue': source_bucket
            }
        ]
        
        try:
            # Check if stack exists
            try:
                self.cf_client.describe_stacks(StackName=self.stack_name)
                stack_exists = True
                logger.info(f"Stack {self.stack_name} exists, updating...")
            except ClientError as e:
                if 'does not exist' in str(e):
                    stack_exists = False
                    logger.info(f"Stack {self.stack_name} does not exist, creating...")
                else:
                    raise
            
            # Deploy or update stack
            if stack_exists:
                response = self.cf_client.update_stack(
                    StackName=self.stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Project', 'Value': 'CloudOptimization'},
                        {'Key': 'DeployedBy', 'Value': 'CompletePlatformDeployer'}
                    ]
                )
                operation = 'UPDATE'
            else:
                response = self.cf_client.create_stack(
                    StackName=self.stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Project', 'Value': 'CloudOptimization'},
                        {'Key': 'DeployedBy', 'Value': 'CompletePlatformDeployer'}
                    ]
                )
                operation = 'CREATE'
            
            stack_id = response['StackId']
            logger.info(f"Stack {operation} initiated: {stack_id}")
            
            # Wait for stack operation to complete
            if operation == 'CREATE':
                waiter = self.cf_client.get_waiter('stack_create_complete')
                waiter_name = 'stack creation'
            else:
                waiter = self.cf_client.get_waiter('stack_update_complete')
                waiter_name = 'stack update'
            
            logger.info(f"Waiting for {waiter_name} to complete...")
            waiter.wait(
                StackName=self.stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 120  # 60 minutes max
                }
            )
            
            # Get stack outputs
            stack_info = self.cf_client.describe_stacks(StackName=self.stack_name)
            stack = stack_info['Stacks'][0]
            
            logger.info(f"Stack {operation.lower()} completed successfully!")
            
            return {
                'StackId': stack['StackId'],
                'StackStatus': stack['StackStatus'],
                'Outputs': {output['OutputKey']: output['OutputValue'] 
                           for output in stack.get('Outputs', [])}
            }
            
        except ClientError as e:
            if 'No updates are to be performed' in str(e):
                logger.info("No updates needed for the stack")
                stack_info = self.cf_client.describe_stacks(StackName=self.stack_name)
                stack = stack_info['Stacks'][0]
                return {
                    'StackId': stack['StackId'],
                    'StackStatus': stack['StackStatus'],
                    'Outputs': {output['OutputKey']: output['OutputValue'] 
                               for output in stack.get('Outputs', [])}
                }
            else:
                logger.error(f"Stack deployment failed: {e}")
                raise

    def create_demo_user(self, user_pool_id: str, client_id: str):
        """Create a demo user for testing"""
        demo_email = "testuser@example.com"
        demo_password = "TestPass123!"
        
        try:
            # Create user
            self.cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=demo_email,
                UserAttributes=[
                    {
                        'Name': 'email',
                        'Value': demo_email
                    },
                    {
                        'Name': 'email_verified',
                        'Value': 'true'
                    }
                ],
                TemporaryPassword=demo_password,
                MessageAction='SUPPRESS'
            )
            
            # Set permanent password
            self.cognito_client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=demo_email,
                Password=demo_password,
                Permanent=True
            )
            
            logger.info(f"Created demo user: {demo_email}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'UsernameExistsException':
                logger.info(f"Demo user already exists: {demo_email}")
            else:
                logger.warning(f"Failed to create demo user: {e}")

    def prepare_frontend_files(self, stack_outputs: Dict[str, str]):
        """Prepare frontend files with correct configuration"""
        frontend_dir = Path("cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend")
        
        if not frontend_dir.exists():
            logger.error(f"Frontend directory not found: {frontend_dir}")
            return
        
        # Create config.js with actual values
        config_content = f"""window.APP_CONFIG = {{
  "cognito": {{
    "userPoolId": "{stack_outputs.get('UserPoolId', '')}",
    "clientId": "{stack_outputs.get('WebAppClientId', '')}",
    "domain": "{stack_outputs.get('UserPoolDomain', '')}"
  }},
  "api": {{
    "baseUrl": "{stack_outputs.get('CloudFrontURL', '')}",
    "endpoints": {{
      "chat": "{stack_outputs.get('CloudFrontURL', '')}/api/chat",
      "health": "{stack_outputs.get('CloudFrontURL', '')}/api/health",
      "websocket": "{stack_outputs.get('CloudFrontURL', '').replace('https://', 'wss://')}/ws"
    }}
  }},
  "app": {{
    "name": "Cloud Optimization Platform",
    "version": "1.0.0"
  }}
}};"""
        
        config_file = frontend_dir / "config.js"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        logger.info(f"Created frontend configuration: {config_file}")

    def upload_frontend_files(self, frontend_bucket: str):
        """Upload frontend files to S3"""
        frontend_dir = Path("cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend")
        
        if not frontend_dir.exists():
            logger.error(f"Frontend directory not found: {frontend_dir}")
            return
        
        # Upload all files in the frontend directory
        for file_path in frontend_dir.glob("*"):
            if file_path.is_file():
                key = file_path.name
                try:
                    # Determine content type
                    content_type = 'text/html'
                    if key.endswith('.js'):
                        content_type = 'application/javascript'
                    elif key.endswith('.css'):
                        content_type = 'text/css'
                    elif key.endswith('.json'):
                        content_type = 'application/json'
                    
                    self.s3_client.upload_file(
                        str(file_path),
                        frontend_bucket,
                        key,
                        ExtraArgs={'ContentType': content_type}
                    )
                    logger.info(f"Uploaded {key} to s3://{frontend_bucket}/")
                except ClientError as e:
                    logger.error(f"Failed to upload {key}: {e}")

    def create_sample_source_zip(self, source_bucket: str):
        """Create a sample source.zip file for initial deployment"""
        
        # Create a simple Dockerfile for the sample application
        dockerfile_content = """FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
"""
        
        # Create a simple Python app
        app_content = """#!/usr/bin/env python3
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'service': 'cloud-optimization-platform',
                'environment': os.environ.get('ENVIRONMENT', 'unknown'),
                'version': '1.0.0'
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path.startswith('/api/'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'message': 'API endpoint placeholder',
                'path': self.path,
                'method': 'GET'
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f'Starting server on port {port}')
    server.serve_forever()
"""
        
        requirements_content = "# No additional requirements for basic health check\n"
        
        # Create temporary directory and files
        import tempfile
        import zipfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create frontend directory structure in the zip
            frontend_temp_dir = os.path.join(temp_dir, 'cloud-optimization-web-interfaces', 'cloud-optimization-web-interface', 'frontend')
            os.makedirs(frontend_temp_dir, exist_ok=True)
            
            # Copy frontend files
            frontend_source = Path("cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend")
            if frontend_source.exists():
                for file_path in frontend_source.glob("*"):
                    if file_path.is_file():
                        shutil.copy2(file_path, frontend_temp_dir)
            
            # Write backend files
            with open(os.path.join(temp_dir, 'Dockerfile'), 'w') as f:
                f.write(dockerfile_content)
            
            with open(os.path.join(temp_dir, 'app.py'), 'w') as f:
                f.write(app_content)
            
            with open(os.path.join(temp_dir, 'requirements.txt'), 'w') as f:
                f.write(requirements_content)
            
            # Create zip file
            zip_path = os.path.join(temp_dir, 'source.zip')
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add backend files
                zipf.write(os.path.join(temp_dir, 'Dockerfile'), 'Dockerfile')
                zipf.write(os.path.join(temp_dir, 'app.py'), 'app.py')
                zipf.write(os.path.join(temp_dir, 'requirements.txt'), 'requirements.txt')
                
                # Add frontend files
                for root, dirs, files in os.walk(frontend_temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            # Upload to S3
            try:
                self.s3_client.upload_file(zip_path, source_bucket, 'source.zip')
                logger.info(f"Uploaded sample source.zip to s3://{source_bucket}/source.zip")
            except ClientError as e:
                logger.error(f"Failed to upload source.zip: {e}")
                raise

    def store_configuration(self, stack_outputs: Dict[str, str]):
        """Store configuration in SSM Parameter Store"""
        
        parameters = {
            f"/{self.stack_name}/{self.environment}/cognito/user-pool-id": 
                stack_outputs.get('UserPoolId', ''),
            f"/{self.stack_name}/{self.environment}/cognito/user-pool-domain": 
                stack_outputs.get('UserPoolDomain', ''),
            f"/{self.stack_name}/{self.environment}/cognito/web-app-client-id": 
                stack_outputs.get('WebAppClientId', ''),
            f"/{self.stack_name}/{self.environment}/cognito/api-client-id": 
                stack_outputs.get('APIClientId', ''),
            f"/{self.stack_name}/{self.environment}/cognito/mcp-server-client-id": 
                stack_outputs.get('MCPServerClientId', ''),
            f"/{self.stack_name}/{self.environment}/infrastructure/backend-image-uri": 
                stack_outputs.get('BackendImageURI', ''),
            f"/{self.stack_name}/{self.environment}/infrastructure/load-balancer-dns": 
                stack_outputs.get('LoadBalancerDNS', ''),
            f"/{self.stack_name}/{self.environment}/infrastructure/vpc-id": 
                stack_outputs.get('VPCId', ''),
            f"/{self.stack_name}/{self.environment}/ecs/cluster-name": 
                stack_outputs.get('ECSClusterName', ''),
            f"/{self.stack_name}/{self.environment}/ecs/service-name": 
                stack_outputs.get('ECSServiceName', ''),
            f"/{self.stack_name}/{self.environment}/frontend/cloudfront-url": 
                stack_outputs.get('CloudFrontURL', ''),
            f"/{self.stack_name}/{self.environment}/frontend/bucket-name": 
                stack_outputs.get('FrontendBucketName', ''),
            f"/{self.stack_name}/{self.environment}/cicd/pipeline-name": 
                stack_outputs.get('PipelineName', ''),

            f"/{self.stack_name}/{self.environment}/cicd/frontend-build-project-name": 
                stack_outputs.get('FrontendBuildProjectName', ''),
            f"/{self.stack_name}/{self.environment}/cicd/artifacts-bucket-name": 
                stack_outputs.get('ArtifactsBucketName', ''),
            f"/{self.stack_name}/{self.environment}/source/bucket-name": 
                stack_outputs.get('SourceBucket', '')
        }
        
        for param_name, param_value in parameters.items():
            if param_value:
                try:
                    self.ssm_client.put_parameter(
                        Name=param_name,
                        Value=param_value,
                        Type='String',
                        Overwrite=True,
                        Description=f'Auto-generated by CompletePlatformDeployer for {self.stack_name}'
                    )
                    logger.info(f"Stored parameter: {param_name}")
                except ClientError as e:
                    logger.warning(f"Failed to store parameter {param_name}: {e}")

    def deploy(self) -> Dict[str, Any]:
        """Main deployment method"""
        
        logger.info("Starting complete platform deployment...")
        
        # Step 1: Create source bucket
        source_bucket = self.create_s3_bucket_for_source()
        
        # Step 2: Create sample source code BEFORE deploying stack
        self.create_sample_source_zip(source_bucket)
        
        # Step 3: Deploy the complete stack
        result = self.deploy_stack(source_bucket)
        
        # Step 4: Apply bucket policy (after IAM roles are created)
        self.apply_bucket_policy(source_bucket)
        
        # Step 5: Create demo user
        user_pool_id = result['Outputs'].get('UserPoolId')
        web_app_client_id = result['Outputs'].get('WebAppClientId')
        if user_pool_id and web_app_client_id:
            self.create_demo_user(user_pool_id, web_app_client_id)
        
        # Step 6: Prepare and upload frontend files
        frontend_bucket = result['Outputs'].get('FrontendBucketName')
        if frontend_bucket:
            self.prepare_frontend_files(result['Outputs'])
            self.upload_frontend_files(frontend_bucket)
        
        # Step 7: Store configuration in Parameter Store
        self.store_configuration(result['Outputs'])
        
        logger.info("Deployment completed successfully!")
        
        return {
            'StackName': self.stack_name,
            'StackId': result['StackId'],
            'StackStatus': result['StackStatus'],
            'SourceBucket': source_bucket,
            'Outputs': result['Outputs'],
            'Region': self.region,
            'Environment': self.environment
        }

def main():
    parser = argparse.ArgumentParser(description='Deploy complete Cloud Optimization Platform')
    parser.add_argument('--stack-name', default='cloud-optimization-platform',
                       help='CloudFormation stack name')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--environment', default='prod',
                       choices=['dev', 'staging', 'prod'],
                       help='Environment name')
    parser.add_argument('--profile',
                       help='AWS CLI profile name')
    
    args = parser.parse_args()
    
    try:
        deployer = CompletePlatformDeployer(
            stack_name=args.stack_name,
            region=args.region,
            environment=args.environment,
            profile=args.profile
        )
        
        result = deployer.deploy()
        
        print("\n" + "="*80)
        print("DEPLOYMENT SUMMARY")
        print("="*80)
        print(f"Stack Name: {result['StackName']}")
        print(f"Stack ID: {result['StackId']}")
        print(f"Status: {result['StackStatus']}")
        print(f"Region: {result['Region']}")
        print(f"Environment: {result['Environment']}")
        print(f"Source Bucket: {result['SourceBucket']}")
        
        print("\nKey Outputs:")
        for key, value in result['Outputs'].items():
            print(f"  {key}: {value}")
        
        print("\n" + "="*80)
        print("ACCESS INFORMATION")
        print("="*80)
        cloudfront_url = result['Outputs'].get('CloudFrontURL', '')
        if cloudfront_url:
            print(f"🌐 Frontend URL: {cloudfront_url}")
            print(f"📧 Demo Login: testuser@example.com")
            print(f"🔑 Demo Password: TestPass123!")
        
        print("\nNext Steps:")
        print("1. Wait for the CodePipeline to complete (check AWS Console)")
        print("2. Access your application via the CloudFront URL above")
        print("3. Use the demo credentials to log in")
        print("4. Upload your application source code to trigger new deployments")
        print("5. Configure additional users in Cognito User Pool")
        
        return 0
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())