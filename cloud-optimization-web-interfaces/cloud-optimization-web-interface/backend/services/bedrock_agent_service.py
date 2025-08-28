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
Bedrock Agent Service for communicating with Enhanced Security Agent
Provides comprehensive AWS security assessments using multi-MCP orchestration
"""

import json
import boto3
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from botocore.exceptions import ClientError

from models.chat_models import ChatSession, BedrockResponse, ToolExecution, ToolExecutionStatus

logger = logging.getLogger(__name__)

class BedrockAgentService:
    def __init__(self):
        self.region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        
        # Get agent configuration from environment
        self.agent_id = os.getenv('ENHANCED_SECURITY_AGENT_ID')
        self.agent_alias_id = os.getenv('ENHANCED_SECURITY_AGENT_ALIAS_ID')
        
        # Initialize Bedrock Agent Runtime client using default credential chain (lazy)
        logger.info("Using default AWS credential chain for Bedrock Agent")
        self._bedrock_agent_runtime = None
        self._bedrock_agent = None
        self._bedrock_runtime = None
        
        if not self.agent_id or not self.agent_alias_id:
            logger.warning("Enhanced Security Agent not configured. Please set ENHANCED_SECURITY_AGENT_ID and ENHANCED_SECURITY_AGENT_ALIAS_ID")
        else:
            logger.info(f"Initialized Enhanced Security Agent: {self.agent_id} (alias: {self.agent_alias_id})")
    
    @property
    def bedrock_agent_runtime(self):
        """Lazy initialization of Bedrock Agent Runtime client"""
        if self._bedrock_agent_runtime is None:
            try:
                self._bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=self.region)
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock Agent Runtime client: {str(e)}")
                self._bedrock_agent_runtime = None
        return self._bedrock_agent_runtime
    
    @property
    def bedrock_agent(self):
        """Lazy initialization of Bedrock Agent client"""
        if self._bedrock_agent is None:
            try:
                self._bedrock_agent = boto3.client('bedrock-agent', region_name=self.region)
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock Agent client: {str(e)}")
                self._bedrock_agent = None
        return self._bedrock_agent
    
    @property
    def bedrock_runtime(self):
        """Lazy initialization of Bedrock Runtime client"""
        if self._bedrock_runtime is None:
            try:
                self._bedrock_runtime = boto3.client('bedrock-runtime', region_name=self.region)
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock Runtime client: {str(e)}")
                self._bedrock_runtime = None
        return self._bedrock_runtime

    async def health_check(self) -> str:
        """Check if Bedrock Agent service is healthy"""
        try:
            if not self.agent_id or not self.agent_alias_id:
                return "degraded"
            
            if not self.bedrock_agent:
                return "degraded"
            
            # Test agent connectivity by getting agent info
            response = self.bedrock_agent.get_agent(agentId=self.agent_id)
            if response['agent']['agentStatus'] in ['PREPARED', 'CREATING', 'UPDATING']:
                return "healthy"
            else:
                return "unhealthy"
        except Exception as e:
            logger.error(f"Bedrock Agent health check failed: {str(e)}")
            return "degraded"
    
    async def process_message(
        self, 
        message: str, 
        session: ChatSession, 
        mcp_service=None  # For compatibility with existing interface
    ) -> BedrockResponse:
        """Process a chat message using Enhanced Security Agent"""
        
        if not self.agent_id or not self.agent_alias_id:
            return BedrockResponse(
                response="Enhanced Security Agent is not configured. Please check your environment variables.",
                tool_executions=[],
                model_id="enhanced-security-agent"
            )
        
        try:
            logger.info(f"Sending message to Enhanced Security Agent {self.agent_id}")
            
            # Prepare the request
            request_params = {
                'agentId': self.agent_id,
                'agentAliasId': self.agent_alias_id,
                'inputText': message
            }
            
            # Use session ID if available
            if session and session.session_id:
                request_params['sessionId'] = session.session_id
            
            # Invoke the agent
            response = self.bedrock_agent_runtime.invoke_agent(**request_params)
            
            # Process the streaming response
            response_text = ""
            tool_executions = []
            return_control_payload = None
            
            if 'completion' in response:
                for event in response['completion']:
                    if 'chunk' in event:
                        chunk = event['chunk']
                        if 'bytes' in chunk:
                            chunk_text = chunk['bytes'].decode('utf-8')
                            response_text += chunk_text
                    
                    # Handle return control events (for MCP server execution)
                    elif 'returnControl' in event:
                        return_control_payload = event['returnControl']
                        logger.info(f"Received return control: {return_control_payload}")
                        
                        # Execute MCP server tools and include results in response
                        mcp_results = await self._handle_return_control(return_control_payload, session)
                        
                        # Add the MCP results to the response text
                        response_text += f"\n\n{mcp_results}"
                    
                    # Handle action group invocations (tool executions)
                    elif 'trace' in event:
                        trace = event['trace']['trace']
                        if 'orchestrationTrace' in trace:
                            orchestration = trace['orchestrationTrace']
                            if 'invocationInput' in orchestration:
                                # Tool invocation started
                                invocation = orchestration['invocationInput']
                                if 'actionGroupInvocationInput' in invocation:
                                    action_group = invocation['actionGroupInvocationInput']
                                    tool_execution = ToolExecution(
                                        tool_name=action_group.get('actionGroupName', 'unknown'),
                                        tool_input=action_group.get('parameters', {}),
                                        status=ToolExecutionStatus.RUNNING,
                                        timestamp=datetime.utcnow()
                                    )
                                    tool_executions.append(tool_execution)
                            
                            elif 'observation' in orchestration:
                                # Tool execution completed
                                observation = orchestration['observation']
                                if 'actionGroupInvocationOutput' in observation and tool_executions:
                                    output = observation['actionGroupInvocationOutput']
                                    # Update the last tool execution
                                    tool_executions[-1].tool_output = output.get('text', '')
                                    tool_executions[-1].status = ToolExecutionStatus.COMPLETED
            
            # Update session if provided
            if session:
                session.session_id = response.get('sessionId', session.session_id)
            
            # Extract structured data if present in response
            structured_data = None
            human_summary = None
            
            # Try to extract JSON data from response text
            if response_text and "```json" in response_text:
                try:
                    # Extract JSON from markdown code blocks
                    import re
                    json_matches = re.findall(r'```json\n(.*?)\n```', response_text, re.DOTALL)
                    if json_matches:
                        structured_data = json.loads(json_matches[0])
                except:
                    pass
            
            return BedrockResponse(
                response=response_text or "I've processed your request using the Enhanced Security Agent.",
                tool_executions=tool_executions,
                model_id="enhanced-security-agent",
                session_id=response.get('sessionId'),
                structured_data=structured_data,
                human_summary=human_summary
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Bedrock Agent error: {error_code} - {error_message}")
            
            return BedrockResponse(
                response=f"I encountered an error while processing your request: {error_message}",
                tool_executions=[],
                model_id="enhanced-security-agent"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in Bedrock Agent service: {e}")
            return BedrockResponse(
                response="I encountered an unexpected error. Please try again.",
                tool_executions=[],
                model_id="enhanced-security-agent"
            )
    
    async def _handle_return_control(self, return_control_payload: Dict[str, Any], session: ChatSession) -> str:
        """Handle return control events by executing MCP server tools"""
        try:
            invocation_inputs = return_control_payload.get('invocationInputs', [])
            
            if not invocation_inputs:
                return "No tools to execute."
            
            results = []
            
            for invocation in invocation_inputs:
                if 'functionInvocationInput' in invocation:
                    function_input = invocation['functionInvocationInput']
                    action_group_name = function_input.get('actionGroup', '')
                    function_name = function_input.get('function', '')
                    
                    # Parse parameters from the function input format
                    parameters = {}
                    for param in function_input.get('parameters', []):
                        param_name = param.get('name', '')
                        param_value = param.get('value', '')
                        param_type = param.get('type', 'string')
                        
                        # Convert parameter based on type
                        if param_type == 'array':
                            # Parse array values (e.g., "[GuardDuty, SecurityHub, Inspector]")
                            try:
                                # Remove brackets and split by comma
                                param_value = param_value.strip('[]')
                                parameters[param_name] = [item.strip() for item in param_value.split(',')]
                            except:
                                parameters[param_name] = [param_value]
                        else:
                            parameters[param_name] = param_value
                    
                    logger.info(f"Executing {action_group_name}.{function_name} with params: {parameters}")
                    
                    # Execute the appropriate MCP server function
                    if action_group_name == 'security-mcp-server':
                        result = await self._execute_security_mcp_function(function_name, parameters)
                    elif action_group_name == 'aws-api-mcp-server-public':
                        result = await self._execute_aws_api_mcp_function(function_name, parameters)
                    else:
                        result = f"Unknown action group: {action_group_name}"
                    
                    # Generate human-readable summary for structured data
                    if isinstance(result, dict):
                        summary = await self._generate_human_readable_summary(result, function_name)
                        formatted_result = f"## {function_name} Results\n\n{summary}\n\n<details>\n<summary>📊 View Raw Data</summary>\n\n```json\n{json.dumps(result, indent=2)}\n```\n</details>"
                        results.append(formatted_result)
                    else:
                        results.append(f"Function {function_name} result: {result}")
            
            return "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Error handling return control: {e}")
            return f"Error executing tools: {str(e)}"
    
    async def _execute_security_mcp_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security MCP server functions and return structured data"""
        try:
            # For now, provide realistic mock responses based on the function
            if function_name == 'CheckSecurityServices':
                services = parameters.get('services', ['GuardDuty', 'SecurityHub', 'Inspector'])
                region = parameters.get('region', 'us-east-1')
                
                # Mock response for security services check
                result = {
                    "region": region,
                    "services_checked": services,
                    "all_enabled": False,
                    "service_statuses": {
                        "GuardDuty": {"enabled": True, "status": "healthy"},
                        "SecurityHub": {"enabled": False, "status": "not_enabled"},
                        "Inspector": {"enabled": True, "status": "healthy"}
                    },
                    "summary": f"Checked {len(services)} security services in {region}. 2 out of 3 services are enabled.",
                    "recommendations": [
                        "Enable AWS Security Hub for centralized security findings",
                        "Configure GuardDuty threat detection rules",
                        "Review Inspector findings for vulnerabilities"
                    ]
                }
                return result
                
            elif function_name == 'GetSecurityFindings':
                service = parameters.get('service', 'guardduty')
                region = parameters.get('region', 'us-east-1')
                
                # Mock response for security findings
                result = {
                    "service": service,
                    "region": region,
                    "findings_count": 3,
                    "findings": [
                        {
                            "id": "finding-001",
                            "severity": "HIGH",
                            "title": "Suspicious network activity detected",
                            "description": "Unusual outbound traffic pattern detected from EC2 instance"
                        },
                        {
                            "id": "finding-002", 
                            "severity": "MEDIUM",
                            "title": "Unencrypted S3 bucket found",
                            "description": "S3 bucket without server-side encryption enabled"
                        },
                        {
                            "id": "finding-003",
                            "severity": "LOW", 
                            "title": "Outdated security group rule",
                            "description": "Security group allows broad access on port 22"
                        }
                    ]
                }
                return result
                
            elif function_name == 'CheckStorageEncryption':
                services = parameters.get('services', ['s3', 'ebs'])
                region = parameters.get('region', 'us-east-1')
                
                # Mock response for storage encryption check
                result = {
                    "region": region,
                    "services_checked": services,
                    "compliant_resources": 5,
                    "non_compliant_resources": 2,
                    "compliance_by_service": {
                        "s3": {"total": 4, "encrypted": 3, "unencrypted": 1},
                        "ebs": {"total": 3, "encrypted": 2, "unencrypted": 1}
                    },
                    "recommendations": [
                        "Enable default encryption for S3 buckets",
                        "Encrypt existing EBS volumes",
                        "Use AWS KMS for key management"
                    ]
                }
                return result
            
            else:
                return {"error": f"Unknown security function: {function_name}"}
                
        except Exception as e:
            logger.error(f"Error executing security MCP function {function_name}: {e}")
            return {"error": f"Error executing {function_name}: {str(e)}"}
    
    async def _execute_aws_api_mcp_function(self, function_name: str, parameters: Dict[str, Any]) -> str:
        """Execute AWS API MCP server functions"""
        try:
            # For now, return a placeholder since AWS API MCP server integration is complex
            return f"AWS API function {function_name} executed with parameters: {parameters}"
            
        except Exception as e:
            logger.error(f"Error executing AWS API MCP function {function_name}: {e}")
            return f"Error executing {function_name}: {str(e)}"

    async def _generate_human_readable_summary(self, data: Dict[str, Any], function_name: str) -> str:
        """Generate human-readable summary of structured data using Bedrock"""
        try:
            # Create a prompt to summarize the data
            prompt = f"""
            Please create a clear, human-readable summary of the following {function_name} results. 
            Focus on the key findings, status, and actionable recommendations. Use emojis and formatting to make it easy to scan.
            
            Data to summarize:
            {json.dumps(data, indent=2)}
            
            Please format your response with:
            - A brief overview with key metrics
            - Status indicators using emojis (✅ for good, ⚠️ for warnings, ❌ for issues)
            - Clear bullet points for findings
            - Actionable recommendations if any
            
            Keep it concise but informative.
            """
            
            # Use Claude 3.7 cross-region inference profile for fast summarization
            response = self.bedrock_runtime.invoke_model(
                modelId="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            response_body = json.loads(response['body'].read())
            summary = response_body['content'][0]['text']
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # Fallback to basic summary
            return self._generate_basic_summary(data, function_name)
    
    def _generate_basic_summary(self, data: Dict[str, Any], function_name: str) -> str:
        """Generate a basic summary without using Bedrock"""
        try:
            if function_name == 'CheckSecurityServices':
                services_checked = len(data.get('services_checked', []))
                all_enabled = data.get('all_enabled', False)
                status_emoji = "✅" if all_enabled else "⚠️"
                
                summary = f"<h3>{status_emoji} Security Services Status</h3>\n\n"
                summary += f"<p><strong>📊 Overview:</strong> Checked {services_checked} security services</p>\n"
                summary += f"<p><strong>🎯 Status:</strong> {'All services enabled' if all_enabled else 'Some services need attention'}</p>\n\n"
                
                if 'service_statuses' in data:
                    summary += "<p><strong>Service Details:</strong></p>\n<ul>\n"
                    for service, status in data['service_statuses'].items():
                        emoji = "✅" if status.get('enabled') else "❌"
                        summary += f"<li>{emoji} <strong>{service}:</strong> {status.get('status', 'unknown')}</li>\n"
                    summary += "</ul>\n"
                
                if 'recommendations' in data:
                    summary += f"<p><strong>🔧 Recommendations:</strong></p>\n<ul>\n"
                    for rec in data['recommendations']:
                        summary += f"<li>{rec}</li>\n"
                    summary += "</ul>\n"
                
                return summary
                
            elif function_name == 'GetSecurityFindings':
                findings_count = data.get('findings_count', 0)
                service = data.get('service', 'unknown')
                
                summary = f"<h3>🔍 Security Findings from {service.title()}</h3>\n\n"
                summary += f"<p><strong>📊 Total Findings:</strong> {findings_count}</p>\n\n"
                
                if 'findings' in data and data['findings']:
                    summary += "<p><strong>Key Findings:</strong></p>\n<ul>\n"
                    for finding in data['findings'][:3]:  # Show top 3
                        severity = finding.get('severity', 'UNKNOWN')
                        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")
                        summary += f"<li>{emoji} <strong>{severity}:</strong> {finding.get('title', 'Unknown finding')}</li>\n"
                    summary += "</ul>\n"
                
                return summary
                
            elif function_name == 'CheckStorageEncryption':
                compliant = data.get('compliant_resources', 0)
                non_compliant = data.get('non_compliant_resources', 0)
                total = compliant + non_compliant
                
                summary = f"<h3>🔐 Storage Encryption Status</h3>\n\n"
                summary += f"<p><strong>📊 Overview:</strong> {compliant}/{total} resources properly encrypted</p>\n"
                
                if non_compliant > 0:
                    summary += f"<p><strong>⚠️ Issues:</strong> {non_compliant} resources need encryption</p>\n"
                else:
                    summary += f"<p><strong>✅ Status:</strong> All resources properly encrypted</p>\n"
                
                if 'compliance_by_service' in data:
                    summary += f"<p><strong>Service Breakdown:</strong></p>\n<ul>\n"
                    for service, stats in data['compliance_by_service'].items():
                        encrypted = stats.get('encrypted', 0)
                        total_service = stats.get('total', 0)
                        emoji = "✅" if stats.get('unencrypted', 0) == 0 else "⚠️"
                        summary += f"<li>{emoji} <strong>{service.upper()}:</strong> {encrypted}/{total_service} encrypted</li>\n"
                    summary += "</ul>\n"
                
                return summary
            
            else:
                # Generic summary for unknown function types
                summary = f"<h3>📋 {function_name} Results</h3>\n\n"
                if isinstance(data, dict):
                    summary += "<ul>\n"
                    for key, value in list(data.items())[:5]:  # Show first 5 keys
                        summary += f"<li><strong>{key}:</strong> {value}</li>\n"
                    summary += "</ul>\n"
                return summary
                
        except Exception as e:
            logger.error(f"Error generating basic summary: {e}")
            return f"<h3>📋 {function_name} completed successfully</h3>\n<p>Results available in raw data below.</p>"

    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the configured agent"""
        return {
            "agent_id": self.agent_id,
            "agent_alias_id": self.agent_alias_id,
            "region": self.region,
            "configured": bool(self.agent_id and self.agent_alias_id)
        }