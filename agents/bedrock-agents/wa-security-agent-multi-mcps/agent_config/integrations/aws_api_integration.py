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
AWS API MCP Server Integration
Handler for AWS API MCP Server providing detailed resource analysis and remediation capabilities
Integrates with Bedrock Core Runtime for MCP server communication
"""

import asyncio
import json
import re
import time
import boto3
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from agent_config.interfaces import AWSAPIIntegration, ToolResult
    from agent_config.utils.logging_utils import get_logger
    from agent_config.utils.error_handling import ErrorHandler
except ImportError:
    # Fallback for standalone testing
    from abc import ABC, abstractmethod
    from typing import Dict, List, Any
    import logging
    
    class AWSAPIIntegration(ABC):
        @abstractmethod
        async def get_detailed_resource_config(self, resource_arn: str) -> Dict[str, Any]:
            pass
        
        @abstractmethod
        async def analyze_service_configuration(self, service_name: str, region: str) -> Dict[str, Any]:
            pass
        
        @abstractmethod
        async def execute_remediation_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
            pass
        
        @abstractmethod
        async def validate_permissions(self, required_permissions: List[str]) -> Dict[str, Any]:
            pass
    
    class ToolResult:
        def __init__(self, tool_name, mcp_server, success, data, error_message=None, execution_time=0.0, metadata=None):
            self.tool_name = tool_name
            self.mcp_server = mcp_server
            self.success = success
            self.data = data
            self.error_message = error_message
            self.execution_time = execution_time
            self.metadata = metadata or {}
    
    def get_logger(name):
        return logging.getLogger(name)
    
    class ErrorHandler:
        pass
    
    # Mock MCP classes for standalone testing
    class ClientSession:
        def __init__(self, read_stream, write_stream):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def initialize(self):
            pass
        async def call_tool(self, name, arguments):
            class MockResult:
                def __init__(self):
                    self.content = [{"text": json.dumps({"test": "data"})}]
            return MockResult()
    
    def streamablehttp_client(url, headers, timeout):
        class MockClient:
            async def __aenter__(self):
                return None, None, None
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        return MockClient()

logger = get_logger(__name__)


class RemediationActionType(Enum):
    """Types of remediation actions supported"""
    ENABLE_ENCRYPTION = "enable_encryption"
    UPDATE_SECURITY_GROUP = "update_security_group"
    ENABLE_LOGGING = "enable_logging"
    UPDATE_IAM_POLICY = "update_iam_policy"
    ENABLE_MFA = "enable_mfa"
    UPDATE_BUCKET_POLICY = "update_bucket_policy"
    ENABLE_VERSIONING = "enable_versioning"
    UPDATE_ACCESS_CONTROL = "update_access_control"


class PermissionValidationResult(Enum):
    """Results of permission validation"""
    GRANTED = "granted"
    DENIED = "denied"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class ResourceConfig:
    """Represents detailed AWS resource configuration"""
    resource_arn: str
    resource_type: str
    service: str
    region: str
    configuration: Dict[str, Any]
    security_attributes: Dict[str, Any]
    compliance_status: Dict[str, Any]
    last_modified: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


@dataclass
class ServiceAnalysis:
    """Represents comprehensive service configuration analysis"""
    service_name: str
    region: str
    resources: List[ResourceConfig]
    security_findings: List[Dict[str, Any]]
    compliance_gaps: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    overall_security_score: float
    analysis_timestamp: str


@dataclass
class RemediationAction:
    """Represents an automated remediation action"""
    action_id: str
    action_type: RemediationActionType
    target_resource: str
    description: str
    parameters: Dict[str, Any]
    safety_checks: List[str]
    rollback_plan: Optional[Dict[str, Any]] = None
    estimated_impact: str = "low"
    requires_approval: bool = True


@dataclass
class ActionResult:
    """Result of executing a remediation action"""
    action_id: str
    success: bool
    message: str
    changes_made: List[Dict[str, Any]]
    rollback_info: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    warnings: List[str] = None


@dataclass
class PermissionStatus:
    """Status of permission validation"""
    overall_status: PermissionValidationResult
    permission_details: Dict[str, Dict[str, Any]]
    missing_permissions: List[str]
    recommendations: List[str]
    validation_timestamp: str


class AWSAPIIntegrationImpl(AWSAPIIntegration):
    """
    Implementation of AWS API MCP Server integration via Bedrock Core Runtime
    Provides detailed resource analysis, service configuration analysis, and automated remediation
    """
    
    def __init__(self, region: str = "us-east-1", cache_ttl: int = 1800):
        """
        Initialize AWS API integration
        
        Args:
            region: AWS region for the integration
            cache_ttl: Cache time-to-live in seconds (default: 30 minutes)
        """
        self.region = region
        self.error_handler = ErrorHandler()
        self.cache_ttl = cache_ttl
        self._resource_cache = {}
        self._service_cache = {}
        self._permission_cache = {}
        
        # Bedrock Core Runtime connection details
        self.mcp_url = None
        self.mcp_headers = None
        self.is_initialized = False
        
        # AWS service to resource type mappings
        self.service_resource_mappings = {
            's3': ['AWS::S3::Bucket', 'AWS::S3::BucketPolicy'],
            'ec2': ['AWS::EC2::Instance', 'AWS::EC2::SecurityGroup', 'AWS::EC2::Volume'],
            'rds': ['AWS::RDS::DBInstance', 'AWS::RDS::DBCluster', 'AWS::RDS::DBSubnetGroup'],
            'lambda': ['AWS::Lambda::Function', 'AWS::Lambda::LayerVersion'],
            'iam': ['AWS::IAM::Role', 'AWS::IAM::Policy', 'AWS::IAM::User'],
            'vpc': ['AWS::EC2::VPC', 'AWS::EC2::Subnet', 'AWS::EC2::RouteTable'],
            'kms': ['AWS::KMS::Key', 'AWS::KMS::Alias'],
            'cloudtrail': ['AWS::CloudTrail::Trail'],
            'cloudwatch': ['AWS::CloudWatch::Alarm', 'AWS::Logs::LogGroup']
        }
        
        # Security-critical attributes by service
        self.security_attributes = {
            's3': ['PublicAccessBlock', 'BucketEncryption', 'BucketVersioning', 'BucketLogging'],
            'ec2': ['SecurityGroups', 'IamInstanceProfile', 'EbsOptimized', 'Monitoring'],
            'rds': ['StorageEncrypted', 'VpcSecurityGroups', 'BackupRetentionPeriod', 'MultiAZ'],
            'lambda': ['Environment', 'VpcConfig', 'DeadLetterConfig', 'TracingConfig'],
            'iam': ['AssumeRolePolicyDocument', 'ManagedPolicyArns', 'MaxSessionDuration'],
            'kms': ['KeyPolicy', 'KeyRotationEnabled', 'KeyUsage', 'KeySpec']
        }
        
        # Common remediation actions by service
        self.remediation_templates = {
            's3': {
                'enable_encryption': {
                    'description': 'Enable default encryption for S3 bucket',
                    'api_call': 'put_bucket_encryption',
                    'safety_checks': ['verify_bucket_exists', 'check_existing_encryption']
                },
                'block_public_access': {
                    'description': 'Enable S3 bucket public access block',
                    'api_call': 'put_public_access_block',
                    'safety_checks': ['verify_bucket_exists', 'check_current_policy']
                }
            },
            'ec2': {
                'update_security_group': {
                    'description': 'Update EC2 security group rules',
                    'api_call': 'authorize_security_group_ingress',
                    'safety_checks': ['verify_sg_exists', 'validate_rules']
                },
                'enable_detailed_monitoring': {
                    'description': 'Enable detailed monitoring for EC2 instance',
                    'api_call': 'monitor_instances',
                    'safety_checks': ['verify_instance_exists', 'check_monitoring_status']
                }
            },
            'rds': {
                'enable_encryption': {
                    'description': 'Enable encryption for RDS instance',
                    'api_call': 'modify_db_instance',
                    'safety_checks': ['verify_instance_exists', 'check_encryption_support']
                }
            }
        }
        
        logger.info(f"AWS API Integration initialized for region: {self.region}")
    
    async def initialize(self) -> bool:
        """Initialize connection to AWS API MCP Server via Bedrock Core Runtime"""
        try:
            logger.info("Initializing AWS API MCP Server connection via Bedrock Core Runtime...")
            
            # Get MCP server credentials from AgentCore deployment
            ssm_client = boto3.client('ssm', region_name=self.region)
            secrets_client = boto3.client('secretsmanager', region_name=self.region)
            
            try:
                # Get Agent ARN for AWS API MCP Server
                agent_arn_response = ssm_client.get_parameter(Name='/aws_api_mcp/runtime/agent_arn')
                agent_arn = agent_arn_response['Parameter']['Value']
                
                # Get bearer token
                response = secrets_client.get_secret_value(SecretId='aws_api_mcp/cognito/credentials')
                secret_value = response['SecretString']
                parsed_secret = json.loads(secret_value)
                bearer_token = parsed_secret['bearer_token']
                
                # Build MCP connection details
                encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
                self.mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
                self.mcp_headers = {
                    "authorization": f"Bearer {bearer_token}",
                    "Content-Type": "application/json"
                }
                
                # Test connection
                await self._test_connection()
                
                self.is_initialized = True
                logger.info("✅ AWS API MCP Server connection initialized via Bedrock Core Runtime")
                return True
                
            except Exception as e:
                logger.warning(f"AWS API MCP Server not available via Bedrock Core Runtime: {e}")
                self.is_initialized = False
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize AWS API MCP Server: {e}")
            self.is_initialized = False
            return False
    
    async def _test_connection(self) -> None:
        """Test the connection to AWS API MCP Server"""
        if not self.mcp_url or not self.mcp_headers:
            raise ValueError("MCP connection not configured")
        
        async with streamablehttp_client(
            self.mcp_url, 
            self.mcp_headers, 
            timeout=timedelta(seconds=30)
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                # Test with a simple tool list call
                await session.list_tools()
    
    async def close(self):
        """Close the MCP connection"""
        self.is_initialized = False
        logger.info("AWS API MCP Server connection closed")
    
    async def connect_to_agentcore_runtime(self, agent_arn: str, bearer_token: str) -> bool:
        """Connect to AWS API MCP Server via AgentCore Runtime"""
        try:
            # Configure connection to AgentCore Runtime
            self.agentcore_config = {
                'agent_arn': agent_arn,
                'bearer_token': bearer_token,
                'endpoint_url': f"https://bedrock-agent-runtime.{self.region}.amazonaws.com"
            }
            
            # Initialize Bedrock Agent Runtime client
            self.bedrock_agent_runtime = boto3.client(
                'bedrock-agent-runtime',
                region_name=self.region
            )
            
            # Test connection
            test_result = await self.test_agentcore_connection()
            if test_result:
                logger.info("Successfully connected to AWS API MCP Server via AgentCore Runtime")
                return True
            else:
                logger.error("Failed to connect to AWS API MCP Server via AgentCore Runtime")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to AgentCore Runtime: {e}")
            return False
    
    async def test_agentcore_connection(self) -> bool:
        """Test connection to AgentCore Runtime"""
        try:
            # Extract agent ID from ARN
            agent_id = self.agentcore_config['agent_arn'].split('/')[-1]
            
            # Test with a simple query
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId='TSTALIASID',
                sessionId='test-session',
                inputText='list available tools'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"AgentCore connection test failed: {e}")
            return False
    
    async def invoke_aws_api_tool_via_agentcore(self, tool_name: str, parameters: dict) -> dict:
        """Invoke AWS API tool via AgentCore Runtime"""
        try:
            # Extract agent ID from ARN
            agent_id = self.agentcore_config['agent_arn'].split('/')[-1]
            
            # Prepare the input text with tool invocation
            input_text = f"Use the {tool_name} tool with parameters: {json.dumps(parameters)}"
            
            # Invoke the agent
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId='TSTALIASID',
                sessionId=f"aws-api-{int(time.time())}",
                inputText=input_text
            )
            
            # Process the response
            result = {}
            for event in response['completion']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        result['output'] = chunk['bytes'].decode('utf-8')
            
            return result
            
        except Exception as e:
            logger.error(f"Error invoking AWS API tool via AgentCore: {e}")
            return {'error': str(e)}
    
    async def get_detailed_resource_config(self, resource_arn: str) -> Dict[str, Any]:
        """
        Get detailed resource configuration through AWS APIs
        
        Args:
            resource_arn: ARN of the AWS resource
            
        Returns:
            Detailed resource configuration with security attributes
        """
        try:
            # Check cache first
            cache_key = f"resource_{resource_arn}"
            if self._is_cache_valid(cache_key, self._resource_cache):
                logger.info(f"Returning cached resource config for: {resource_arn}")
                return self._resource_cache[cache_key]['data']
            
            # Parse ARN to extract service and resource information
            arn_parts = self._parse_arn(resource_arn)
            if not arn_parts:
                raise ValueError(f"Invalid ARN format: {resource_arn}")
            
            # Get resource configuration using AWS API MCP server
            resource_config = await self._get_resource_configuration(arn_parts)
            
            # If no configuration returned, return fallback
            if not resource_config:
                return self._get_fallback_resource_config(resource_arn)
            
            # Enhance with security analysis
            enhanced_config = await self._enhance_with_security_analysis(resource_config, arn_parts)
            
            # Cache results
            self._resource_cache[cache_key] = {
                'data': enhanced_config,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"Retrieved detailed config for resource: {resource_arn}")
            return enhanced_config
            
        except Exception as e:
            logger.error(f"Error getting resource config for '{resource_arn}': {e}")
            return self._get_fallback_resource_config(resource_arn)
    
    async def analyze_service_configuration(self, service_name: str, region: str) -> Dict[str, Any]:
        """
        Analyze service configuration using AWS APIs
        
        Args:
            service_name: AWS service name (e.g., 's3', 'ec2', 'rds')
            region: AWS region
            
        Returns:
            Comprehensive service configuration analysis
        """
        try:
            # Check cache first
            cache_key = f"service_{service_name}_{region}"
            if self._is_cache_valid(cache_key, self._service_cache):
                logger.info(f"Returning cached service analysis for: {service_name} in {region}")
                return self._service_cache[cache_key]['data']
            
            # Get all resources for the service in the region
            resources = await self._discover_service_resources(service_name, region)
            
            # Analyze each resource configuration
            resource_configs = []
            for resource in resources:
                try:
                    config = await self.get_detailed_resource_config(resource['arn'])
                    resource_configs.append(config)
                except Exception as e:
                    logger.warning(f"Failed to analyze resource {resource['arn']}: {e}")
                    continue
            
            # Perform comprehensive service analysis
            service_analysis = await self._perform_service_analysis(
                service_name, region, resource_configs
            )
            
            # Cache results
            self._service_cache[cache_key] = {
                'data': service_analysis,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"Completed service analysis for {service_name} in {region}")
            return service_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing service '{service_name}' in region '{region}': {e}")
            return self._get_fallback_service_analysis(service_name, region)
    
    async def execute_remediation_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute automated remediation action
        
        Args:
            action: Remediation action details
            
        Returns:
            Result of the remediation action execution
        """
        try:
            # Validate action structure
            if not self._validate_remediation_action(action):
                return {
                    'success': False,
                    'message': 'Invalid remediation action structure',
                    'action_id': action.get('action_id', 'unknown')
                }
            
            action_id = action['action_id']
            action_type = action['action_type']
            target_resource = action['target_resource']
            
            logger.info(f"Executing remediation action {action_id}: {action_type} on {target_resource}")
            
            # Perform safety checks
            safety_check_result = await self._perform_safety_checks(action)
            if not safety_check_result['passed']:
                return {
                    'success': False,
                    'message': f"Safety checks failed: {safety_check_result['message']}",
                    'action_id': action_id,
                    'warnings': safety_check_result.get('warnings', [])
                }
            
            # Execute the remediation action
            execution_result = await self._execute_remediation_via_api(action)
            
            # Log the action result
            if execution_result['success']:
                logger.info(f"Successfully executed remediation action {action_id}")
            else:
                logger.error(f"Failed to execute remediation action {action_id}: {execution_result['message']}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error executing remediation action: {e}")
            return {
                'success': False,
                'message': f'Execution error: {str(e)}',
                'action_id': action.get('action_id', 'unknown'),
                'execution_time': 0.0
            }
    
    async def validate_permissions(self, required_permissions: List[str]) -> Dict[str, Any]:
        """
        Validate required permissions for API operations
        
        Args:
            required_permissions: List of required IAM permissions
            
        Returns:
            Permission validation status and recommendations
        """
        try:
            # Check cache first
            cache_key = f"permissions_{hash(tuple(sorted(required_permissions)))}"
            if self._is_cache_valid(cache_key, self._permission_cache):
                logger.info("Returning cached permission validation results")
                return self._permission_cache[cache_key]['data']
            
            # Validate permissions using AWS API MCP server
            validation_results = await self._validate_permissions_via_api(required_permissions)
            
            # Process validation results
            processed_results = self._process_permission_validation(validation_results, required_permissions)
            
            # Cache results
            self._permission_cache[cache_key] = {
                'data': processed_results,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"Validated {len(required_permissions)} permissions")
            return processed_results
            
        except Exception as e:
            logger.error(f"Error validating permissions: {e}")
            return self._get_fallback_permission_validation(required_permissions)
    
    async def _get_resource_configuration(self, arn_parts: Dict[str, str]) -> Dict[str, Any]:
        """Get resource configuration using AWS API MCP server via Bedrock Core Runtime"""
        if not self.is_initialized:
            await self.initialize()
        
        if not self.is_initialized:
            raise RuntimeError("AWS API MCP Server not initialized")
        
        try:
            service = arn_parts['service']
            resource_type = arn_parts['resource_type']
            resource_id = arn_parts['resource_id']
            region = arn_parts['region']
            
            # Determine tool name and arguments based on service type
            if service == 's3':
                tool_name = "get_bucket_configuration"
                arguments = {
                    "bucket_name": resource_id,
                    "include_policy": True,
                    "include_encryption": True,
                    "include_versioning": True,
                    "include_logging": True
                }
            elif service == 'ec2':
                tool_name = "describe_instances"
                arguments = {
                    "instance_ids": [resource_id],
                    "region": region,
                    "include_security_groups": True,
                    "include_iam_profile": True
                }
            elif service == 'rds':
                tool_name = "describe_db_instances"
                arguments = {
                    "db_instance_identifier": resource_id,
                    "region": region,
                    "include_security_groups": True,
                    "include_parameter_groups": True
                }
            else:
                # Generic resource description
                tool_name = "describe_resource"
                arguments = {
                    "resource_arn": f"arn:aws:{service}:{region}::{resource_type}/{resource_id}",
                    "include_tags": True,
                    "include_security_attributes": True
                }
            
            # Call tool via MCP client session
            async with streamablehttp_client(
                self.mcp_url, 
                self.mcp_headers, 
                timeout=timedelta(seconds=60)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    
                    if result.content and len(result.content) > 0:
                        text_content = result.content[0].text
                        if text_content:
                            try:
                                return json.loads(text_content)
                            except json.JSONDecodeError:
                                return {"raw_response": text_content}
                    
                    logger.warning(f"No configuration data returned for resource")
                    return {}
                
        except Exception as e:
            logger.error(f"Error calling AWS API MCP server: {e}")
            raise
    
    async def _enhance_with_security_analysis(self, config: Dict[str, Any], arn_parts: Dict[str, str]) -> Dict[str, Any]:
        """Enhance resource configuration with security analysis"""
        service = arn_parts['service']
        
        # Extract security-relevant attributes
        security_attributes = {}
        if service in self.security_attributes:
            for attr in self.security_attributes[service]:
                if attr in config:
                    security_attributes[attr] = config[attr]
        
        # Analyze compliance status
        compliance_status = self._analyze_compliance_status(config, service)
        
        # Generate security recommendations
        recommendations = self._generate_security_recommendations(config, service)
        
        # Reconstruct ARN properly for S3 buckets (no resource type prefix)
        if service == 's3':
            resource_arn = f"arn:aws:{service}:{arn_parts['region']}::{arn_parts['resource_id']}"
        else:
            resource_arn = f"arn:aws:{service}:{arn_parts['region']}::{arn_parts['resource_type']}/{arn_parts['resource_id']}"
        
        return {
            'resource_arn': resource_arn,
            'resource_type': arn_parts['resource_type'],
            'service': service,
            'region': arn_parts['region'],
            'configuration': config,
            'security_attributes': security_attributes,
            'compliance_status': compliance_status,
            'recommendations': recommendations,
            'last_modified': config.get('LastModified', datetime.now().isoformat()),
            'tags': config.get('Tags', {})
        }
    
    async def _discover_service_resources(self, service_name: str, region: str) -> List[Dict[str, Any]]:
        """Discover all resources for a service in a region"""
        if not self.is_initialized:
            await self.initialize()
        
        if not self.is_initialized:
            logger.warning("AWS API MCP Server not initialized, returning empty resource list")
            return []
        
        try:
            # Get resource types for the service
            resource_types = self.service_resource_mappings.get(service_name, [])
            
            resources = []
            for resource_type in resource_types:
                try:
                    # Use AWS Config or Resource Groups API to discover resources
                    async with streamablehttp_client(
                        self.mcp_url, 
                        self.mcp_headers, 
                        timeout=timedelta(seconds=60)
                    ) as (read_stream, write_stream, _):
                        async with ClientSession(read_stream, write_stream) as session:
                            await session.initialize()
                            result = await session.call_tool("list_resources", {
                                "resource_type": resource_type,
                                "region": region,
                                "max_results": 100
                            })
                            
                            if result.content and len(result.content) > 0:
                                text_content = result.content[0].text
                                if text_content:
                                    try:
                                        resource_list = json.loads(text_content)
                                        if isinstance(resource_list, list):
                                            resources.extend(resource_list)
                                        elif isinstance(resource_list, dict) and "resources" in resource_list:
                                            resources.extend(resource_list["resources"])
                                    except json.JSONDecodeError:
                                        logger.warning(f"Failed to parse resource list for {resource_type}")
                
                except Exception as e:
                    logger.warning(f"Failed to discover resources for {resource_type}: {e}")
                    continue
            
            return resources
            
        except Exception as e:
            logger.error(f"Error discovering resources for service {service_name}: {e}")
            return []
    
    async def _perform_service_analysis(self, service_name: str, region: str, resource_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform comprehensive service analysis"""
        security_findings = []
        compliance_gaps = []
        recommendations = []
        security_scores = []
        
        for config in resource_configs:
            # Extract security findings
            if 'compliance_status' in config:
                for finding in config['compliance_status'].get('findings', []):
                    security_findings.append(finding)
            
            # Extract compliance gaps
            if 'compliance_status' in config:
                for gap in config['compliance_status'].get('gaps', []):
                    compliance_gaps.append(gap)
            
            # Extract recommendations
            if 'recommendations' in config:
                recommendations.extend(config['recommendations'])
            
            # Calculate security score for this resource
            resource_score = self._calculate_resource_security_score(config)
            security_scores.append(resource_score)
        
        # Calculate overall security score
        overall_score = sum(security_scores) / len(security_scores) if security_scores else 0.0
        
        return {
            'service_name': service_name,
            'region': region,
            'resources': resource_configs,
            'security_findings': security_findings,
            'compliance_gaps': compliance_gaps,
            'recommendations': recommendations[:10],  # Top 10 recommendations
            'overall_security_score': overall_score,
            'analysis_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_resources': len(resource_configs),
                'high_risk_findings': len([f for f in security_findings if f.get('severity') == 'HIGH']),
                'compliance_gaps': len(compliance_gaps),
                'actionable_recommendations': len([r for r in recommendations if r.get('actionable', False)])
            }
        }
    
    async def _perform_safety_checks(self, action: Dict[str, Any]) -> Dict[str, bool]:
        """Perform safety checks before executing remediation action"""
        try:
            action_type = action['action_type']
            target_resource = action['target_resource']
            safety_checks = action.get('safety_checks', [])
            
            check_results = []
            warnings = []
            
            for check in safety_checks:
                if check == 'verify_resource_exists':
                    # Verify the target resource exists
                    exists = await self._verify_resource_exists(target_resource)
                    check_results.append(exists)
                    if not exists:
                        warnings.append(f"Target resource {target_resource} does not exist")
                
                elif check == 'check_existing_configuration':
                    # Check if the configuration change is needed
                    needed = await self._check_configuration_change_needed(action)
                    check_results.append(needed)
                    if not needed:
                        warnings.append("Configuration change may not be necessary")
                
                elif check == 'validate_parameters':
                    # Validate action parameters
                    valid = self._validate_action_parameters(action)
                    check_results.append(valid)
                    if not valid:
                        warnings.append("Invalid action parameters")
                
                else:
                    # Unknown safety check
                    check_results.append(True)
                    warnings.append(f"Unknown safety check: {check}")
            
            all_passed = all(check_results) if check_results else True
            
            return {
                'passed': all_passed,
                'message': 'All safety checks passed' if all_passed else 'Some safety checks failed',
                'warnings': warnings,
                'check_details': dict(zip(safety_checks, check_results))
            }
            
        except Exception as e:
            logger.error(f"Error performing safety checks: {e}")
            return {
                'passed': False,
                'message': f'Safety check error: {str(e)}',
                'warnings': ['Safety check system error']
            }
    
    async def _execute_remediation_via_api(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute remediation action via AWS API MCP server"""
        if not self.is_initialized:
            await self.initialize()
        
        if not self.is_initialized:
            return {
                'action_id': action.get('action_id', 'unknown'),
                'success': False,
                'message': 'AWS API MCP Server not initialized',
                'changes_made': [],
                'execution_time': 0.0
            }
        
        try:
            action_id = action['action_id']
            action_type = action['action_type']
            target_resource = action['target_resource']
            parameters = action.get('parameters', {})
            
            start_time = datetime.now().timestamp()
            
            # Determine tool name and arguments based on action type
            if action_type == 'enable_encryption':
                tool_name = "enable_resource_encryption"
                arguments = {
                    "resource_arn": target_resource,
                    "encryption_config": parameters.get('encryption_config', {}),
                    "dry_run": parameters.get('dry_run', False)
                }
            elif action_type == 'update_security_group':
                tool_name = "update_security_group_rules"
                arguments = {
                    "security_group_id": parameters.get('security_group_id'),
                    "rules": parameters.get('rules', []),
                    "dry_run": parameters.get('dry_run', False)
                }
            elif action_type == 'enable_logging':
                tool_name = "enable_resource_logging"
                arguments = {
                    "resource_arn": target_resource,
                    "logging_config": parameters.get('logging_config', {}),
                    "dry_run": parameters.get('dry_run', False)
                }
            else:
                # Generic remediation action
                tool_name = "execute_remediation_action"
                arguments = {
                    "action_type": action_type,
                    "target_resource": target_resource,
                    "parameters": parameters
                }
            
            # Execute the remediation action via MCP client session
            async with streamablehttp_client(
                self.mcp_url, 
                self.mcp_headers, 
                timeout=timedelta(seconds=120)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    
                    execution_time = datetime.now().timestamp() - start_time
                    
                    if result.content and len(result.content) > 0:
                        text_content = result.content[0].text
                        if text_content:
                            try:
                                execution_result = json.loads(text_content)
                                return {
                                    'action_id': action_id,
                                    'success': execution_result.get('success', False),
                                    'message': execution_result.get('message', 'Action completed'),
                                    'changes_made': execution_result.get('changes_made', []),
                                    'rollback_info': execution_result.get('rollback_info'),
                                    'execution_time': execution_time,
                                    'warnings': execution_result.get('warnings', [])
                                }
                            except json.JSONDecodeError:
                                return {
                                    'action_id': action_id,
                                    'success': True,
                                    'message': text_content,
                                    'changes_made': [],
                                    'execution_time': execution_time
                                }
                    
                    return {
                        'action_id': action_id,
                        'success': False,
                        'message': 'No response content from API server',
                        'changes_made': [],
                        'execution_time': execution_time
                    }
                
        except Exception as e:
            logger.error(f"Error executing remediation via API: {e}")
            return {
                'action_id': action.get('action_id', 'unknown'),
                'success': False,
                'message': f'Execution error: {str(e)}',
                'changes_made': [],
                'execution_time': 0.0
            }
    
    async def _validate_permissions_via_api(self, required_permissions: List[str]) -> Dict[str, Any]:
        """Validate permissions using AWS API MCP server"""
        if not self.is_initialized:
            await self.initialize()
        
        if not self.is_initialized:
            raise RuntimeError("AWS API MCP Server not initialized")
        
        try:
            # Call permission validation tool via MCP client session
            async with streamablehttp_client(
                self.mcp_url, 
                self.mcp_headers, 
                timeout=timedelta(seconds=60)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool("simulate_principal_policy", {
                        "policy_source_arn": "current_user",
                        "action_names": required_permissions,
                        "resource_arns": ["*"],
                        "context_entries": []
                    })
                    
                    if result.content and len(result.content) > 0:
                        text_content = result.content[0].text
                        if text_content:
                            try:
                                return json.loads(text_content)
                            except json.JSONDecodeError:
                                return {"raw_response": text_content}
                    
                    return {}
                
        except Exception as e:
            logger.error(f"Error validating permissions via API: {e}")
            raise
    
    def _process_permission_validation(self, validation_results: Dict[str, Any], required_permissions: List[str]) -> Dict[str, Any]:
        """Process permission validation results"""
        permission_details = {}
        missing_permissions = []
        recommendations = []
        
        # Process each permission
        for permission in required_permissions:
            if permission in validation_results:
                result = validation_results[permission]
                permission_details[permission] = result
                
                if result.get('decision') == 'denied':
                    missing_permissions.append(permission)
                    recommendations.append(f"Grant {permission} permission to the current user/role")
            else:
                # Permission not found in results, assume denied
                missing_permissions.append(permission)
                permission_details[permission] = {
                    'decision': 'denied',
                    'reason': 'Permission not evaluated'
                }
        
        # Determine overall status
        if not missing_permissions:
            overall_status = PermissionValidationResult.GRANTED
        elif len(missing_permissions) == len(required_permissions):
            overall_status = PermissionValidationResult.DENIED
        else:
            overall_status = PermissionValidationResult.PARTIAL
        
        return {
            'overall_status': overall_status.value,
            'permission_details': permission_details,
            'missing_permissions': missing_permissions,
            'recommendations': recommendations,
            'validation_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_permissions': len(required_permissions),
                'granted_permissions': len(required_permissions) - len(missing_permissions),
                'denied_permissions': len(missing_permissions)
            }
        }
    
    def _parse_arn(self, arn: str) -> Optional[Dict[str, str]]:
        """Parse AWS ARN into components"""
        try:
            # ARN format: arn:partition:service:region:account-id:resource-type/resource-id
            parts = arn.split(':')
            if len(parts) < 6:
                return None
            
            resource_part = parts[5]
            
            # Handle different ARN formats
            if parts[2] == 's3':
                # S3 ARN format: arn:aws:s3:::bucket-name
                resource_type = 'bucket'
                resource_id = resource_part
            elif '/' in resource_part:
                resource_type, resource_id = resource_part.split('/', 1)
            else:
                resource_type = resource_part
                resource_id = parts[6] if len(parts) > 6 else resource_part
            
            return {
                'partition': parts[1],
                'service': parts[2],
                'region': parts[3],
                'account_id': parts[4],
                'resource_type': resource_type,
                'resource_id': resource_id
            }
        except Exception:
            return None
    
    def _analyze_compliance_status(self, config: Dict[str, Any], service: str) -> Dict[str, Any]:
        """Analyze compliance status of resource configuration"""
        findings = []
        gaps = []
        
        if service == 's3':
            # Check S3 security configurations
            if not config.get('PublicAccessBlock', {}).get('BlockPublicAcls', False):
                findings.append({
                    'severity': 'HIGH',
                    'finding': 'S3 bucket allows public ACLs',
                    'recommendation': 'Enable Block Public ACLs'
                })
            
            if not config.get('BucketEncryption'):
                gaps.append({
                    'gap': 'Missing default encryption',
                    'impact': 'Data at rest not encrypted by default'
                })
        
        elif service == 'ec2':
            # Check EC2 security configurations
            security_groups = config.get('SecurityGroups', [])
            for sg in security_groups:
                for rule in sg.get('IpPermissions', []):
                    if rule.get('IpRanges') and any(ip.get('CidrIp') == '0.0.0.0/0' for ip in rule.get('IpRanges', [])):
                        findings.append({
                            'severity': 'MEDIUM',
                            'finding': 'Security group allows access from 0.0.0.0/0',
                            'recommendation': 'Restrict source IP ranges'
                        })
        
        elif service == 'rds':
            # Check RDS security configurations
            if not config.get('StorageEncrypted', False):
                findings.append({
                    'severity': 'HIGH',
                    'finding': 'RDS instance storage not encrypted',
                    'recommendation': 'Enable storage encryption'
                })
            
            if config.get('PubliclyAccessible', False):
                findings.append({
                    'severity': 'HIGH',
                    'finding': 'RDS instance is publicly accessible',
                    'recommendation': 'Disable public accessibility'
                })
        
        return {
            'findings': findings,
            'gaps': gaps,
            'compliance_score': max(0, 100 - (len(findings) * 20) - (len(gaps) * 10))
        }
    
    def _generate_security_recommendations(self, config: Dict[str, Any], service: str) -> List[Dict[str, Any]]:
        """Generate security recommendations based on configuration"""
        recommendations = []
        
        if service == 's3':
            if not config.get('BucketEncryption'):
                recommendations.append({
                    'priority': 'HIGH',
                    'category': 'encryption',
                    'title': 'Enable S3 bucket encryption',
                    'description': 'Configure default encryption for the S3 bucket',
                    'actionable': True,
                    'remediation_action': 'enable_encryption'
                })
            
            if not config.get('BucketVersioning', {}).get('Status') == 'Enabled':
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'data_protection',
                    'title': 'Enable S3 bucket versioning',
                    'description': 'Enable versioning to protect against accidental deletion',
                    'actionable': True,
                    'remediation_action': 'enable_versioning'
                })
        
        elif service == 'ec2':
            if not config.get('Monitoring', {}).get('State') == 'enabled':
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'monitoring',
                    'title': 'Enable detailed monitoring',
                    'description': 'Enable detailed CloudWatch monitoring for the instance',
                    'actionable': True,
                    'remediation_action': 'enable_detailed_monitoring'
                })
        
        elif service == 'rds':
            backup_retention = config.get('BackupRetentionPeriod', 0)
            if backup_retention < 7:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'backup',
                    'title': 'Increase backup retention period',
                    'description': 'Set backup retention period to at least 7 days',
                    'actionable': True,
                    'remediation_action': 'update_backup_retention'
                })
        
        return recommendations
    
    def _calculate_resource_security_score(self, config: Dict[str, Any]) -> float:
        """Calculate security score for a resource (0-100)"""
        score = 100.0
        
        # Deduct points for security findings
        compliance_status = config.get('compliance_status', {})
        findings = compliance_status.get('findings', [])
        
        for finding in findings:
            severity = finding.get('severity', 'LOW')
            if severity == 'HIGH':
                score -= 25
            elif severity == 'MEDIUM':
                score -= 15
            elif severity == 'LOW':
                score -= 5
        
        # Deduct points for compliance gaps
        gaps = compliance_status.get('gaps', [])
        score -= len(gaps) * 10
        
        return max(0.0, score)
    
    def _validate_remediation_action(self, action: Dict[str, Any]) -> bool:
        """Validate remediation action structure"""
        required_fields = ['action_id', 'action_type', 'target_resource']
        return all(field in action for field in required_fields)
    
    async def _verify_resource_exists(self, resource_arn: str) -> bool:
        """Verify that a resource exists"""
        try:
            config = await self.get_detailed_resource_config(resource_arn)
            return bool(config and config.get('resource_arn') and 'error' not in config)
        except Exception:
            return False
    
    async def _check_configuration_change_needed(self, action: Dict[str, Any]) -> bool:
        """Check if configuration change is actually needed"""
        try:
            target_resource = action['target_resource']
            action_type = action['action_type']
            
            config = await self.get_detailed_resource_config(target_resource)
            
            # If there's an error getting config, assume change is needed
            if 'error' in config:
                return True
            
            if action_type == 'enable_encryption':
                # Check if encryption is already enabled
                return not bool(config.get('configuration', {}).get('BucketEncryption'))
            elif action_type == 'enable_logging':
                # Check if logging is already enabled
                return not bool(config.get('configuration', {}).get('BucketLogging'))
            
            # For other actions, assume change is needed
            return True
            
        except Exception:
            # If we can't determine, assume change is needed
            return True
    
    def _validate_action_parameters(self, action: Dict[str, Any]) -> bool:
        """Validate action parameters"""
        parameters = action.get('parameters', {})
        action_type = action['action_type']
        
        if action_type == 'enable_encryption':
            # Validate encryption parameters
            encryption_config = parameters.get('encryption_config', {})
            return 'SSEAlgorithm' in encryption_config
        elif action_type == 'update_security_group':
            # Validate security group parameters
            return 'security_group_id' in parameters and 'rules' in parameters
        
        # For other actions, basic validation
        return isinstance(parameters, dict)
    
    def _is_cache_valid(self, cache_key: str, cache_dict: Dict) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in cache_dict:
            return False
        
        cache_entry = cache_dict[cache_key]
        current_time = datetime.now().timestamp()
        
        return (current_time - cache_entry['timestamp']) < self.cache_ttl
    
    def _get_fallback_resource_config(self, resource_arn: str) -> Dict[str, Any]:
        """Provide fallback resource configuration when API calls fail"""
        arn_parts = self._parse_arn(resource_arn)
        if not arn_parts:
            return {'error': 'Invalid ARN format'}
        
        return {
            'resource_arn': resource_arn,
            'resource_type': arn_parts.get('resource_type', 'unknown'),
            'service': arn_parts.get('service', 'unknown'),
            'region': arn_parts.get('region', 'unknown'),
            'configuration': {},
            'security_attributes': {},
            'compliance_status': {
                'findings': [],
                'gaps': [],
                'compliance_score': 0
            },
            'recommendations': [],
            'error': 'Failed to retrieve resource configuration from AWS API'
        }
    
    def _get_fallback_service_analysis(self, service_name: str, region: str) -> Dict[str, Any]:
        """Provide fallback service analysis when API calls fail"""
        return {
            'service_name': service_name,
            'region': region,
            'resources': [],
            'security_findings': [],
            'compliance_gaps': [],
            'recommendations': [],
            'overall_security_score': 0.0,
            'analysis_timestamp': datetime.now().isoformat(),
            'error': 'Failed to analyze service configuration via AWS API'
        }
    
    def _get_fallback_permission_validation(self, required_permissions: List[str]) -> Dict[str, Any]:
        """Provide fallback permission validation when API calls fail"""
        return {
            'overall_status': PermissionValidationResult.UNKNOWN.value,
            'permission_details': {perm: {'decision': 'unknown', 'reason': 'Validation failed'} for perm in required_permissions},
            'missing_permissions': required_permissions,
            'recommendations': ['Verify AWS API MCP server connectivity', 'Check IAM permissions for policy simulation'],
            'validation_timestamp': datetime.now().isoformat(),
            'error': 'Failed to validate permissions via AWS API'
        }


# Factory function for creating AWS API integration instance
def create_aws_api_integration(region: str = "us-east-1", cache_ttl: int = 1800) -> AWSAPIIntegration:
    """
    Factory function to create AWS API integration instance
    
    Args:
        region: AWS region for the integration
        cache_ttl: Cache time-to-live in seconds
        
    Returns:
        AWSAPIIntegration instance
    """
    return AWSAPIIntegrationImpl(region, cache_ttl)