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
Deployment script for Enhanced AWS Security Agent with Multi-MCP Integration
Configurable agent name with default 'wa-security-agent'
Includes all configurations from agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Configuration classes from agent_config
class MCPServerType(Enum):
    """Types of MCP servers supported"""

    SECURITY = "security"
    KNOWLEDGE = "knowledge"
    API = "api"


class Environment(Enum):
    """Deployment environments"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class AuthConfig:
    """Authentication configuration for MCP servers"""

    type: str  # 'bearer', 'aws_iam', 'api_key', 'none'
    credentials: Dict[str, str]
    refresh_mechanism: Optional[str] = None
    token_expiry: Optional[int] = None


@dataclass
class RetryConfig:
    """Retry configuration for MCP server calls"""

    max_attempts: int = 3
    backoff_factor: float = 2.0
    max_delay: int = 60
    exponential_base: float = 2.0


@dataclass
class HealthCheckConfig:
    """Health check configuration for MCP servers"""

    enabled: bool = True
    interval: int = 300  # seconds
    timeout: int = 30
    failure_threshold: int = 3
    recovery_threshold: int = 2


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection"""

    name: str
    server_type: MCPServerType
    connection_type: str  # 'agentcore', 'direct', 'api'
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: int = 120
    retry_attempts: int = 3
    health_check_interval: int = 300
    auth_config: Optional[AuthConfig] = None
    retry_config: Optional[RetryConfig] = None
    health_check_config: Optional[HealthCheckConfig] = None
    feature_flags: Optional[Dict[str, bool]] = None
    region_specific: Optional[Dict[str, Any]] = None


class EnhancedSecurityAgentV2Deployer:
    """Enhanced deployer for Multi-MCP Security Agent with comprehensive configuration"""

    def __init__(
        self,
        region: str = "us-east-1",
        agent_name: str = "wa-security-agent",
        environment: str = "production",
    ):
        self.region = region
        self.account_id = boto3.client("sts").get_caller_identity()["Account"]
        self.environment = Environment(environment.lower())

        # Initialize AWS clients
        self.bedrock_agent = boto3.client("bedrock-agent", region_name=region)
        self.iam = boto3.client("iam", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        self.secrets_client = boto3.client("secretsmanager", region_name=region)

        # Configuration
        self.agent_name = agent_name
        # Create role name based on agent name (sanitized for IAM)
        sanitized_name = agent_name.replace("-", "").replace("_", "").title()
        self.role_name = f"{sanitized_name}Role"

        # Initialize MCP configurations
        self.mcp_configs = self._initialize_mcp_configurations()

        logger.info(
            f"Initialized enhanced deployer for region: {region}, agent: {agent_name}, environment: {environment}"
        )

    def _initialize_mcp_configurations(self) -> Dict[str, MCPServerConfig]:
        """Initialize MCP server configurations"""
        return {
            "security": MCPServerConfig(
                name="security",
                server_type=MCPServerType.SECURITY,
                connection_type="agentcore",
                timeout=120,
                retry_attempts=3,
                health_check_interval=300,
                auth_config=AuthConfig(
                    type="bearer",
                    credentials={},
                    refresh_mechanism="aws_secrets_manager",
                ),
                retry_config=RetryConfig(
                    max_attempts=3, backoff_factor=2.0, max_delay=60
                ),
                health_check_config=HealthCheckConfig(
                    enabled=True, interval=300, timeout=30, failure_threshold=3
                ),
                feature_flags={
                    "parallel_execution": True,
                    "response_caching": True,
                    "enhanced_error_handling": True,
                },
                region_specific={
                    "parameter_prefix": "/coa/mcp/wa_security_mcp",
                    "secret_name": "/coa/mcp/wa_security_mcp/cognito/credentials",
                },
            ),
            "aws_knowledge": MCPServerConfig(
                name="aws_knowledge",
                server_type=MCPServerType.KNOWLEDGE,
                connection_type="direct",
                url="https://knowledge-mcp.global.api.aws",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "AWS-Enhanced-Security-Agent/2.0",
                },
                timeout=60,
                retry_attempts=2,
                health_check_interval=600,
                auth_config=AuthConfig(type="none", credentials={}),
                retry_config=RetryConfig(
                    max_attempts=2, backoff_factor=1.5, max_delay=30
                ),
                health_check_config=HealthCheckConfig(
                    enabled=True, interval=600, timeout=20, failure_threshold=2
                ),
                feature_flags={
                    "documentation_caching": True,
                    "relevance_scoring": True,
                    "content_summarization": True,
                    "direct_http_calls": True,
                },
                region_specific={
                    "documentation_regions": ["us-east-1", "us-west-2", "eu-west-1"],
                    "cache_ttl": 3600,
                    "public_endpoint": "https://knowledge-mcp.global.api.aws",
                },
            ),
            "aws_api": MCPServerConfig(
                name="aws_api",
                server_type=MCPServerType.API,
                connection_type="api",
                timeout=180,
                retry_attempts=3,
                health_check_interval=300,
                auth_config=AuthConfig(
                    type="aws_iam", credentials={}, refresh_mechanism="aws_sts"
                ),
                retry_config=RetryConfig(
                    max_attempts=3, backoff_factor=2.0, max_delay=120
                ),
                health_check_config=HealthCheckConfig(
                    enabled=True, interval=300, timeout=45, failure_threshold=3
                ),
                feature_flags={
                    "automated_remediation": False,  # Disabled by default for safety
                    "resource_analysis": True,
                    "permission_validation": True,
                    "rate_limiting": True,
                },
                region_specific={
                    "api_endpoints": {},
                    "rate_limits": {
                        "default": 100,  # requests per minute
                        "describe": 200,
                        "list": 150,
                    },
                },
            ),
        }

    def create_agent_role(self) -> str:
        """Create or get IAM role for the agent"""
        logger.info("Creating IAM role for Enhanced Security Agent...")

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

        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BedrockModelAccess",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [f"arn:aws:bedrock:{self.region}::foundation-model/*"],
                },
                {
                    "Sid": "ParameterStoreAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath",
                    ],
                    "Resource": [
                        f"arn:aws:ssm:{self.region}:{self.account_id}:parameter/{self.agent_name}/*"
                    ],
                },
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/bedrock/agents/*",
                },
            ],
        }

        try:
            # Try to create the role
            response = self.iam.create_role(
                RoleName=self.role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"IAM role for {self.agent_name} agent",
            )
            role_arn = response["Role"]["Arn"]
            logger.info(f"Created new IAM role: {role_arn}")

            # Attach the permissions policy
            self.iam.put_role_policy(
                RoleName=self.role_name,
                PolicyName=f"{self.agent_name.replace('-', '').title()}Permissions",
                PolicyDocument=json.dumps(permissions_policy),
            )
            logger.info("Attached permissions policy to role")

        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityAlreadyExists":
                # Role exists, get its ARN
                response = self.iam.get_role(RoleName=self.role_name)
                role_arn = response["Role"]["Arn"]
                logger.info(f"Using existing IAM role: {role_arn}")

                # Update the policy
                try:
                    self.iam.put_role_policy(
                        RoleName=self.role_name,
                        PolicyName=f"{self.agent_name.replace('-', '').title()}Permissions",
                        PolicyDocument=json.dumps(permissions_policy),
                    )
                    logger.info("Updated permissions policy")
                except Exception as policy_error:
                    logger.warning(f"Failed to update policy: {policy_error}")
            else:
                raise

        return role_arn

    def get_agent_instruction(self) -> str:
        """Get the enhanced agent instruction prompt with multi-MCP capabilities"""
        return """You are an Enhanced AWS Security Expert with Multi-MCP Integration, specializing in comprehensive security assessments and guidance.

## Your Enhanced Capabilities:

### 🛡️ Real-Time Security Assessment (Security MCP Server)
- Live AWS security service status monitoring
- Real-time vulnerability and finding analysis
- Storage encryption compliance checking
- Network security configuration validation
- Security service enablement verification

### 📚 AWS Knowledge Integration (Knowledge MCP Server)
- Access to comprehensive AWS documentation
- Security best practices and compliance frameworks
- Implementation guides and troubleshooting resources
- Well-Architected Framework security pillar guidance
- Real-time access to latest AWS security updates

### 🔧 AWS API Integration (API MCP Server)
- Direct AWS service configuration analysis
- Resource-level security assessment
- Automated remediation capabilities (when enabled)
- Cross-service security dependency mapping
- Permission and policy validation

## Multi-Source Intelligence Approach:

### 1. **Comprehensive Security Analysis**
- Combine real-time security data with authoritative AWS documentation
- Cross-reference current configurations with AWS best practices
- Provide context-aware recommendations with official guidance
- Risk assessment with Well-Architected Framework alignment

### 2. **Enhanced Response Generation**
- Visual formatting with emojis and structured layouts
- Risk-based prioritization with business impact analysis
- Executive summaries with actionable insights
- Implementation roadmaps with documentation links

### 3. **Intelligent Orchestration**
- Parallel execution of multiple MCP server queries
- Conflict resolution between different data sources
- Session context management for continuous improvement
- Automated tool selection based on query analysis

## Core Security Focus Areas:
- **Identity and Access Management (IAM)**: Real-time policy analysis + AWS IAM best practices
- **Data Protection**: Live encryption status + AWS encryption documentation
- **Infrastructure Protection**: Current VPC/SG configs + AWS network security guides
- **Detective Controls**: Active security service status + AWS monitoring best practices
- **Incident Response**: Real-time findings + AWS incident response frameworks
- **Compliance and Governance**: Current compliance posture + regulatory guidance

## Enhanced Response Methodology:

### For Security Assessments:
1. **Gather Real-Time Data**: Query Security MCP for current AWS security status
2. **Enhance with Knowledge**: Search AWS documentation for relevant best practices
3. **API Deep-Dive**: Use AWS API MCP for detailed resource analysis (when available)
4. **Synthesize Insights**: Combine all sources into comprehensive analysis
5. **Provide Actionable Plan**: Include immediate fixes and long-term improvements

### For Security Questions:
1. **Search AWS Documentation**: Find official guidance on the topic
2. **Validate with Real-Time Data**: Check current implementation against best practices
3. **Cross-Reference APIs**: Verify with actual AWS service configurations
4. **Provide Enhanced Answer**: Combine theoretical knowledge with practical assessment

## Response Format Standards:
- **Executive Summary**: Business-focused overview with key findings
- **Technical Analysis**: Detailed technical findings with evidence
- **Risk Assessment**: Prioritized findings with impact analysis
- **Remediation Plan**: Step-by-step implementation guide
- **Documentation Links**: Direct references to AWS official documentation
- **Preventive Measures**: Long-term security posture improvements

## Key Enhancement Features:
- 🔄 **Multi-MCP Orchestration**: Intelligent coordination of multiple data sources
- 📊 **Visual Reporting**: Enhanced formatting with charts, tables, and visual indicators
- 🎯 **Context Awareness**: Session-based learning and recommendation refinement
- 🚀 **Parallel Processing**: Simultaneous queries for faster response times
- 🔍 **Deep Analysis**: Combination of surface-level and deep-dive assessments
- 💡 **Proactive Insights**: Predictive recommendations based on comprehensive data

## Session Context Management:
- Track assessment history for trend analysis
- Build cumulative security posture understanding
- Provide progressive recommendations based on implementation progress
- Maintain context across multiple security domains

Remember: You're not just a security assessment tool - you're a comprehensive AWS security advisor that combines real-time data, authoritative documentation, and API-level insights to provide the most complete security guidance possible."""

    def create_agent(self, role_arn: str) -> str:
        """Create the Bedrock agent"""
        logger.info(f"Creating {self.agent_name} agent...")

        agent_config = {
            "agentName": self.agent_name,
            "description": f"{self.agent_name} - AWS Security Agent for comprehensive security assessments and guidance",
            "foundationModel": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "instruction": self.get_agent_instruction(),
            "agentResourceRoleArn": role_arn,
            "idleSessionTTLInSeconds": 1800,
            "tags": {
                "Project": self.agent_name,
                "Version": "2.0",
                "Environment": "Production",
            },
        }

        try:
            response = self.bedrock_agent.create_agent(**agent_config)
            agent_id = response["agent"]["agentId"]
            logger.info(f"Created agent with ID: {agent_id}")

            # Wait for agent creation to complete
            logger.info("Waiting for agent creation to complete...")
            max_attempts = 20
            for attempt in range(max_attempts):
                time.sleep(5)

                agent_response = self.bedrock_agent.get_agent(agentId=agent_id)
                current_status = agent_response["agent"]["agentStatus"]

                logger.info(
                    f"Agent creation status: {current_status} (attempt {attempt + 1}/{max_attempts})"
                )

                if current_status in ["NOT_PREPARED", "PREPARED"]:
                    logger.info("Agent creation completed successfully")
                    return agent_id
                elif current_status == "FAILED":
                    raise Exception(
                        f"Agent creation failed with status: {current_status}"
                    )

            raise Exception("Agent creation timed out")

            return agent_id

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                logger.info("Agent already exists, retrieving existing agent...")
                # List agents to find existing one
                agents = self.bedrock_agent.list_agents()
                for agent in agents["agentSummaries"]:
                    if agent["agentName"] == self.agent_name:
                        agent_id = agent["agentId"]
                        logger.info(f"Found existing agent with ID: {agent_id}")
                        return agent_id
                raise Exception(f"Agent {self.agent_name} exists but couldn't be found")
            else:
                raise

    def prepare_agent(self, agent_id: str) -> bool:
        """Prepare the agent (create a version)"""
        logger.info("Preparing agent...")

        try:
            # First check current status
            agent_response = self.bedrock_agent.get_agent(agentId=agent_id)
            current_status = agent_response["agent"]["agentStatus"]

            if current_status == "PREPARED":
                logger.info("Agent is already prepared")
                return True

            response = self.bedrock_agent.prepare_agent(agentId=agent_id)
            status = response["agentStatus"]
            logger.info(f"Agent preparation started with status: {status}")

            # Wait for preparation to complete
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(10)

                agent_response = self.bedrock_agent.get_agent(agentId=agent_id)
                current_status = agent_response["agent"]["agentStatus"]

                logger.info(
                    f"Preparation status: {current_status} (attempt {attempt + 1}/{max_attempts})"
                )

                if current_status == "PREPARED":
                    logger.info("Agent preparation completed successfully")
                    return True
                elif current_status in ["FAILED", "NOT_PREPARED"]:
                    logger.error(
                        f"Agent preparation failed with status: {current_status}"
                    )
                    return False

            logger.error("Agent preparation timed out")
            return False

        except Exception as e:
            logger.error(f"Failed to prepare agent: {e}")
            return False

    def create_agent_alias(self, agent_id: str) -> str:
        """Create an alias for the agent"""
        logger.info("Creating agent alias...")

        alias_name = "PROD"

        try:
            response = self.bedrock_agent.create_agent_alias(
                agentId=agent_id,
                agentAliasName=alias_name,
                description=f"Production alias for {self.agent_name}",
            )
            alias_id = response["agentAlias"]["agentAliasId"]
            logger.info(f"Created alias with ID: {alias_id}")
            return alias_id

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                # Alias exists, get existing one
                aliases = self.bedrock_agent.list_agent_aliases(agentId=agent_id)
                for alias in aliases["agentAliasSummaries"]:
                    if alias["agentAliasName"] == alias_name:
                        alias_id = alias["agentAliasId"]
                        logger.info(f"Using existing alias with ID: {alias_id}")
                        return alias_id
                raise Exception(f"Alias {alias_name} exists but couldn't be found")
            else:
                raise

    def store_agent_info(self, agent_id: str, alias_id: str):
        """Store agent information and MCP configurations in Parameter Store"""
        logger.info(
            "Storing agent information and MCP configurations in Parameter Store..."
        )

        # Basic agent parameters
        parameters = {
            f"/coa/agent/{self.agent_name}/agent-id": agent_id,
            f"/coa/agent/{self.agent_name}/alias-id": alias_id,
            f"/coa/agent/{self.agent_name}/region": self.region,
            f"/coa/agent/{self.agent_name}/version": "2.0",
            f"/coa/agent/{self.agent_name}/environment": self.environment.value,
        }

        # Store MCP configurations
        for mcp_name, config in self.mcp_configs.items():
            config_dict = self._config_to_dict(config)
            parameters[f"/coa/agent/{self.agent_name}/mcp/{mcp_name}/config"] = (
                json.dumps(config_dict)
            )

        # Store feature flags
        feature_flags = {
            "multi_mcp_orchestration": True,
            "parallel_tool_execution": True,
            "enhanced_response_formatting": True,
            "session_context_management": True,
            "automated_remediation": False,  # Disabled by default
            "comprehensive_reporting": True,
            "health_monitoring": True,
            "knowledge_integration": True,
            "api_integration": True,
        }
        parameters[f"/coa/agent/{self.agent_name}/feature_flags"] = json.dumps(
            feature_flags
        )

        # Store deployment metadata
        deployment_metadata = {
            "deployment_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "deployer_version": "2.0",
            "mcp_servers": list(self.mcp_configs.keys()),
            "capabilities": [
                "real_time_security_assessment",
                "aws_knowledge_integration",
                "api_level_analysis",
                "multi_source_synthesis",
                "enhanced_reporting",
            ],
        }
        parameters[f"/coa/agent/{self.agent_name}/deployment_metadata"] = json.dumps(
            deployment_metadata
        )

        for param_name, param_value in parameters.items():
            try:
                self.ssm.put_parameter(
                    Name=param_name,
                    Value=param_value,
                    Type="String",
                    Overwrite=True,
                    Description=f"{self.agent_name} enhanced agent configuration",
                )
                logger.info(f"Stored parameter: {param_name}")
            except Exception as e:
                logger.error(f"Failed to store parameter {param_name}: {e}")

    def _config_to_dict(self, config: MCPServerConfig) -> Dict[str, Any]:
        """Convert MCP config to dictionary for storage"""
        config_dict = {
            "name": config.name,
            "server_type": config.server_type.value,
            "connection_type": config.connection_type,
            "url": config.url,
            "headers": config.headers,
            "timeout": config.timeout,
            "retry_attempts": config.retry_attempts,
            "health_check_interval": config.health_check_interval,
        }

        if config.auth_config:
            config_dict["auth_config"] = {
                "type": config.auth_config.type,
                "refresh_mechanism": config.auth_config.refresh_mechanism,
                "token_expiry": config.auth_config.token_expiry,
            }

        if config.retry_config:
            config_dict["retry_config"] = {
                "max_attempts": config.retry_config.max_attempts,
                "backoff_factor": config.retry_config.backoff_factor,
                "max_delay": config.retry_config.max_delay,
                "exponential_base": config.retry_config.exponential_base,
            }

        if config.health_check_config:
            config_dict["health_check_config"] = {
                "enabled": config.health_check_config.enabled,
                "interval": config.health_check_config.interval,
                "timeout": config.health_check_config.timeout,
                "failure_threshold": config.health_check_config.failure_threshold,
                "recovery_threshold": config.health_check_config.recovery_threshold,
            }

        if config.feature_flags:
            config_dict["feature_flags"] = config.feature_flags

        if config.region_specific:
            config_dict["region_specific"] = config.region_specific

        return config_dict

    def validate_mcp_configurations(self) -> Dict[str, bool]:
        """Validate MCP server configurations"""
        logger.info("Validating MCP server configurations...")
        validation_results = {}

        for name, config in self.mcp_configs.items():
            try:
                is_valid = True
                issues = []

                # Basic validation
                if not config.name or not config.server_type:
                    is_valid = False
                    issues.append("Missing name or server_type")

                # Connection-specific validation
                if config.connection_type == "agentcore" and not config.region_specific:
                    is_valid = False
                    issues.append(
                        "AgentCore connection requires region_specific configuration"
                    )

                # Authentication validation
                if config.auth_config and config.auth_config.type == "bearer":
                    if (
                        config.connection_type == "agentcore"
                        and not config.region_specific.get("secret_name")
                    ):
                        is_valid = False
                        issues.append(
                            "Bearer auth requires secret_name in region_specific"
                        )

                validation_results[name] = is_valid

                if is_valid:
                    logger.info(f"✅ Configuration for {name} is valid")
                else:
                    logger.warning(
                        f"⚠️ Configuration for {name} has issues: {', '.join(issues)}"
                    )

            except Exception as e:
                logger.error(f"Failed to validate configuration for {name}: {e}")
                validation_results[name] = False

        return validation_results

    def copy_agent_config_files(self) -> bool:
        """Copy agent configuration files to deployment location"""
        logger.info("Copying agent configuration files...")

        try:
            # Define source and destination paths
            source_dir = (
                "agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config"
            )
            dest_dir = f"/tmp/{self.agent_name}_config"

            # Check if source directory exists
            if not os.path.exists(source_dir):
                logger.warning(f"Source config directory not found: {source_dir}")
                return False

            # Create destination directory
            os.makedirs(dest_dir, exist_ok=True)

            # Copy configuration files
            import shutil

            shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)

            logger.info(f"✅ Agent configuration files copied to {dest_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to copy agent configuration files: {e}")
            return False

    def store_agent_config_archive(self) -> bool:
        """Store agent configuration as a compressed archive in S3 or Parameter Store"""
        logger.info("Storing agent configuration archive...")

        try:
            import base64
            import zipfile

            # Create a zip archive of the configuration
            config_dir = (
                "agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config"
            )
            if not os.path.exists(config_dir):
                logger.warning(
                    "Agent config directory not found, skipping archive storage"
                )
                return False

            # Create zip file in memory
            import io

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(config_dir):
                    for file in files:
                        if file.endswith(".py"):
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, config_dir)
                            zip_file.write(file_path, arc_name)

            # Encode as base64 for storage
            zip_data = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")

            # Store in Parameter Store (if small enough) or log location
            if len(zip_data) < 4096:  # Parameter Store limit
                self.ssm.put_parameter(
                    Name=f"/coa/agent/{self.agent_name}/config_archive",
                    Value=zip_data,
                    Type="String",
                    Overwrite=True,
                    Description=f"Compressed agent configuration archive for {self.agent_name}",
                )
                logger.info("✅ Agent configuration archive stored in Parameter Store")
            else:
                logger.info(
                    "Configuration archive too large for Parameter Store, consider S3 storage"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to store agent configuration archive: {e}")
            return False

    def deploy(self) -> Dict[str, str]:
        """Deploy the complete enhanced security agent with multi-MCP integration"""
        logger.info(
            f"🚀 Starting Enhanced {self.agent_name} deployment with Multi-MCP integration..."
        )

        try:
            # Step 1: Validate MCP configurations
            logger.info("Step 1: Validating MCP configurations...")
            validation_results = self.validate_mcp_configurations()
            failed_validations = [
                name for name, valid in validation_results.items() if not valid
            ]
            if failed_validations:
                logger.warning(
                    f"Some MCP configurations have issues: {failed_validations}"
                )
                logger.info(
                    "Continuing with deployment - configurations can be updated post-deployment"
                )

            # Step 2: Create IAM role with enhanced permissions
            logger.info("Step 2: Creating enhanced IAM role...")
            role_arn = self.create_agent_role()

            # Step 3: Create agent with enhanced configuration
            logger.info("Step 3: Creating enhanced security agent...")
            agent_id = self.create_agent(role_arn)

            # Step 4: Prepare agent
            logger.info("Step 4: Preparing agent...")
            if not self.prepare_agent(agent_id):
                raise Exception("Agent preparation failed")

            # Step 5: Create alias
            logger.info("Step 5: Creating agent alias...")
            alias_id = self.create_agent_alias(agent_id)

            # Step 6: Copy and store agent configuration files
            logger.info("Step 6: Handling agent configuration files...")
            self.copy_agent_config_files()
            self.store_agent_config_archive()

            # Step 7: Store comprehensive configuration
            logger.info("Step 7: Storing enhanced configuration...")
            self.store_agent_info(agent_id, alias_id)

            # Step 8: Validate deployment
            logger.info("Step 8: Validating deployment...")
            if not self.validate_deployment(agent_id):
                logger.warning(
                    "Deployment validation had issues, but agent was created successfully"
                )

            result = {
                "agent_id": agent_id,
                "alias_id": alias_id,
                "role_arn": role_arn,
                "region": self.region,
                "environment": self.environment.value,
                "mcp_servers": list(self.mcp_configs.keys()),
                "validation_results": validation_results,
            }

            logger.info(
                f"✅ Enhanced {self.agent_name} deployment completed successfully!"
            )
            logger.info(
                f"🔧 MCP Servers configured: {', '.join(self.mcp_configs.keys())}"
            )
            logger.info(f"🌍 Environment: {self.environment.value}")

            return result

        except Exception as e:
            logger.error(f"❌ Enhanced deployment failed: {e}")
            raise

    def validate_deployment(self, agent_id: str) -> bool:
        """Validate the agent deployment"""
        logger.info("Validating deployment...")

        try:
            # Check agent status
            response = self.bedrock_agent.get_agent(agentId=agent_id)
            status = response["agent"]["agentStatus"]

            if status == "PREPARED":
                logger.info("✅ Agent is ready and operational")
                return True
            else:
                logger.warning(f"⚠️ Agent status: {status}")
                return False

        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Enhanced AWS Security Agent with Multi-MCP Integration"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument(
        "--agent-name",
        default="wa-security-agent",
        help="Name of the agent to create (default: wa-security-agent)",
    )
    parser.add_argument(
        "--environment",
        default="production",
        choices=["development", "staging", "production"],
        help="Deployment environment",
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate existing deployment"
    )
    parser.add_argument("--agent-id", help="Agent ID for validation")
    parser.add_argument(
        "--show-config", action="store_true", help="Show MCP configurations and exit"
    )

    args = parser.parse_args()

    deployer = EnhancedSecurityAgentV2Deployer(
        region=args.region, agent_name=args.agent_name, environment=args.environment
    )

    if args.show_config:
        print(f"\n📋 MCP Server Configurations for {args.agent_name}")
        print("=" * 60)
        for name, config in deployer.mcp_configs.items():
            print(f"\n🔧 {name.upper()} MCP Server:")
            print(f"   Type: {config.server_type.value}")
            print(f"   Connection: {config.connection_type}")
            print(f"   Timeout: {config.timeout}s")
            print(f"   Retry Attempts: {config.retry_attempts}")
            if config.feature_flags:
                print(
                    f"   Feature Flags: {', '.join([k for k, v in config.feature_flags.items() if v])}"
                )
        print(f"\n🌍 Environment: {args.environment}")
        print(f"🌎 Region: {args.region}")
        return

    if args.validate:
        if not args.agent_id:
            print("❌ --agent-id required for validation")
            sys.exit(1)

        success = deployer.validate_deployment(args.agent_id)
        if success:
            print("✅ Deployment validation successful")
        else:
            print("❌ Deployment validation failed")
            sys.exit(1)
    else:
        try:
            result = deployer.deploy()

            print(f"\n🎉 Enhanced {args.agent_name} Deployment Complete!")
            print("=" * 80)
            print(f"Agent Name: {args.agent_name}")
            print(f"Agent ID: {result['agent_id']}")
            print(f"Alias ID: {result['alias_id']}")
            print(f"Region: {result['region']}")
            print(f"Environment: {result['environment']}")
            print(f"Role ARN: {result['role_arn']}")

            print("\n🔧 MCP Server Integration:")
            for server in result["mcp_servers"]:
                status = (
                    "✅ Configured"
                    if result["validation_results"].get(server, False)
                    else "⚠️ Needs Setup"
                )
                print(f"   {server.upper()}: {status}")

            print("\n📊 Enhanced Capabilities:")
            print("   🛡️ Real-time Security Assessment")
            print("   📚 AWS Knowledge Integration")
            print("   🔧 API-level Analysis")
            print("   🧠 Multi-source Intelligence")
            print("   📈 Enhanced Reporting")

            print("\n📋 Next Steps:")
            print("1. Test the enhanced agent using the Bedrock console or API")
            print("2. Verify MCP server connections are working")
            print("3. Monitor CloudWatch logs for multi-MCP performance")
            print("4. Configure Security MCP server credentials if needed")
            print("5. Set up comprehensive monitoring and alerting")
            print("6. Review stored configurations in Parameter Store")

            print("\n🔍 Configuration Storage:")
            print(f"   Parameters: /coa/agent/{args.agent_name}/*")
            print(f"   MCP Configs: /coa/agent/{args.agent_name}/mcp/*")
            print(f"   Feature Flags: /coa/agent/{args.agent_name}/feature_flags")

        except Exception as e:
            print(f"❌ Enhanced deployment failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
