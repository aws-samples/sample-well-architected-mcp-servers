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
Deployment script for Enhanced Security Agent with Multi-MCP Integration
Configures and deploys the enhanced agent with multiple MCP server connections
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict

import boto3

# Add the parent directory to the path to import deployment utilities
sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "..", "deployment-scripts")
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedSecurityAgentDeployer:
    """Deploys Enhanced Security Agent with Multi-MCP Integration"""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.bedrock_agent = boto3.client("bedrock-agent", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        self.secrets_manager = boto3.client("secretsmanager", region_name=region)
        self.iam = boto3.client("iam", region_name=region)

    def create_agent_configuration(self) -> Dict[str, Any]:
        """Create enhanced agent configuration"""
        return {
            "agentName": "enhanced-security-agent-multi-mcp",
            "description": "Enhanced AWS Security Agent with Multi-MCP Integration for comprehensive security assessments",
            "foundationModel": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "instruction": """You are an Enhanced AWS Security Expert with access to multiple specialized MCP servers:

1. **Security MCP Server**: Real-time AWS security assessments and findings
2. **AWS Knowledge MCP Server**: Official AWS documentation and best practices
3. **AWS API MCP Server**: Direct AWS service interactions and detailed resource analysis

Your role is to provide comprehensive security guidance by intelligently orchestrating these MCP servers to deliver:

- **Real-time Security Analysis**: Current security posture and findings
- **Authoritative Guidance**: Official AWS documentation and best practices
- **Deep Resource Analysis**: Detailed configuration analysis through AWS APIs
- **Automated Remediation**: Safe, guided remediation actions when appropriate
- **Executive Reporting**: Business-focused summaries with risk prioritization

## Enhanced Capabilities:

### Multi-Source Intelligence
- Combine real-time data with authoritative AWS documentation
- Cross-reference findings with official AWS security frameworks
- Provide context-aware recommendations with implementation guidance

### Intelligent Orchestration
- Automatically determine which MCP servers to query based on user requests
- Execute parallel calls for optimal performance
- Gracefully handle server unavailability with fallback responses

### Enhanced Response Quality
- Visual formatting with structured layouts and emojis
- Risk-based prioritization aligned with AWS Well-Architected principles
- Actionable recommendations with step-by-step implementation guides
- Direct links to relevant AWS documentation

## Response Guidelines:
- Always provide authoritative, well-sourced security guidance
- Include both immediate fixes and long-term strategic improvements
- Reference official AWS documentation and best practices
- Prioritize recommendations based on risk and business impact
- Maintain context across conversation for personalized guidance

Focus on being a comprehensive AWS security advisor that combines the power of real-time assessment, authoritative knowledge, and deep technical analysis.""",
            "idleSessionTTLInSeconds": 1800,
            "agentResourceRoleArn": None,  # Will be set during deployment
            "tags": {
                "Project": "Enhanced-Security-Agent",
                "MCP-Integration": "Multi-Server",
                "Version": "1.0.0",
            },
        }

    def create_agent_role(self) -> str:
        """Create IAM role for the enhanced agent"""
        role_name = "EnhancedSecurityAgentRole"

        # Trust policy for Bedrock
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        # Permissions policy
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [f"arn:aws:bedrock:{self.region}::foundation-model/*"],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath",
                    ],
                    "Resource": [
                        f"arn:aws:ssm:{self.region}:*:parameter/enhanced_security_agent/*",
                        f"arn:aws:ssm:{self.region}:*:parameter/wa_security_direct_mcp/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": [
                        f"arn:aws:secretsmanager:{self.region}:*:secret:enhanced_security_agent/*",
                        f"arn:aws:secretsmanager:{self.region}:*:secret:wa_security_direct_mcp/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:*:log-group:/aws/bedrock/agents/*",
                },
            ],
        }

        try:
            # Create role
            response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="IAM role for Enhanced Security Agent with Multi-MCP Integration",
            )
            role_arn = response["Role"]["Arn"]

            # Attach permissions policy
            self.iam.put_role_policy(
                RoleName=role_name,
                PolicyName="EnhancedSecurityAgentPermissions",
                PolicyDocument=json.dumps(permissions_policy),
            )

            logger.info(f"Created IAM role: {role_arn}")
            return role_arn

        except self.iam.exceptions.EntityAlreadyExistsException:
            # Role already exists, get its ARN
            response = self.iam.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            logger.info(f"Using existing IAM role: {role_arn}")
            return role_arn

    def store_configuration_parameters(self):
        """Store configuration parameters in SSM Parameter Store"""
        parameters = {
            "/enhanced_security_agent/development/feature_flags": json.dumps(
                {
                    "multi_mcp_orchestration": True,
                    "parallel_tool_execution": True,
                    "enhanced_response_formatting": True,
                    "session_context_management": True,
                    "automated_remediation": False,
                    "comprehensive_reporting": True,
                    "health_monitoring": True,
                }
            ),
            "/enhanced_security_agent/development/mcp_servers": json.dumps(
                {
                    "security": {
                        "enabled": True,
                        "connection_type": "agentcore",
                        "timeout": 120,
                    },
                    "aws_knowledge": {
                        "enabled": True,
                        "connection_type": "direct",
                        "timeout": 60,
                    },
                    "aws_api": {
                        "enabled": False,  # Will be enabled when AWS API MCP is deployed
                        "connection_type": "api",
                        "timeout": 180,
                    },
                }
            ),
        }

        for param_name, param_value in parameters.items():
            try:
                self.ssm.put_parameter(
                    Name=param_name,
                    Value=param_value,
                    Type="String",
                    Overwrite=True,
                    Description=f"Configuration for Enhanced Security Agent: {param_name.split('/')[-1]}",
                )
                logger.info(f"Stored parameter: {param_name}")
            except Exception as e:
                logger.error(f"Failed to store parameter {param_name}: {e}")

    def deploy_agent(self) -> str:
        """Deploy the enhanced security agent"""
        try:
            # Create IAM role
            role_arn = self.create_agent_role()

            # Store configuration parameters
            self.store_configuration_parameters()

            # Create agent configuration
            agent_config = self.create_agent_configuration()
            agent_config["agentResourceRoleArn"] = role_arn

            # Create the agent
            response = self.bedrock_agent.create_agent(**agent_config)
            agent_id = response["agent"]["agentId"]

            logger.info(f"Created Enhanced Security Agent: {agent_id}")

            # Prepare the agent (this creates a version)
            prepare_response = self.bedrock_agent.prepare_agent(agentId=agent_id)
            logger.info(f"Prepared agent version: {prepare_response['agentStatus']}")

            # Create an alias
            alias_response = self.bedrock_agent.create_agent_alias(
                agentId=agent_id,
                agentAliasName="enhanced-security-multi-mcp",
                description="Enhanced Security Agent with Multi-MCP Integration",
            )
            alias_id = alias_response["agentAlias"]["agentAliasId"]

            logger.info(f"Created agent alias: {alias_id}")

            # Store agent information in SSM
            self.ssm.put_parameter(
                Name="/enhanced_security_agent/runtime/agent_id",
                Value=agent_id,
                Type="String",
                Overwrite=True,
                Description="Enhanced Security Agent ID",
            )

            self.ssm.put_parameter(
                Name="/enhanced_security_agent/runtime/agent_alias_id",
                Value=alias_id,
                Type="String",
                Overwrite=True,
                Description="Enhanced Security Agent Alias ID",
            )

            return agent_id

        except Exception as e:
            logger.error(f"Failed to deploy Enhanced Security Agent: {e}")
            raise

    def validate_deployment(self, agent_id: str) -> bool:
        """Validate the agent deployment"""
        try:
            # Get agent details
            response = self.bedrock_agent.get_agent(agentId=agent_id)
            agent_status = response["agent"]["agentStatus"]

            if agent_status in ["CREATING", "UPDATING", "PREPARING"]:
                logger.info(f"Agent is still being prepared: {agent_status}")
                return False
            elif agent_status == "PREPARED":
                logger.info("Agent deployment validated successfully")
                return True
            else:
                logger.error(f"Agent deployment failed with status: {agent_status}")
                return False

        except Exception as e:
            logger.error(f"Failed to validate deployment: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Enhanced Security Agent with Multi-MCP Integration"
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region for deployment"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate existing deployment"
    )
    parser.add_argument("--agent-id", help="Agent ID for validation")

    args = parser.parse_args()

    deployer = EnhancedSecurityAgentDeployer(region=args.region)

    if args.validate and args.agent_id:
        success = deployer.validate_deployment(args.agent_id)
        if success:
            print("✅ Enhanced Security Agent deployment validated successfully")
        else:
            print("❌ Enhanced Security Agent deployment validation failed")
            sys.exit(1)
    else:
        try:
            agent_id = deployer.deploy_agent()
            print("✅ Enhanced Security Agent deployed successfully!")
            print(f"Agent ID: {agent_id}")
            print(f"Region: {args.region}")
            print("\nNext steps:")
            print("1. Wait for agent preparation to complete")
            print("2. Test the agent with multi-MCP queries")
            print("3. Monitor CloudWatch logs for performance metrics")
            print("4. Configure additional MCP servers as needed")

        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
