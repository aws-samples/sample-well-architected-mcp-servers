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
Handler for AWS API MCP Server providing AWS CLI command execution and suggestions
Uses the actual MCP tools: call_aws and suggest_aws_commands
"""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from agent_config.interfaces import AWSAPIIntegration, ToolResult
    from agent_config.utils.error_handling import ErrorHandler
    from agent_config.utils.logging_utils import get_logger
except ImportError:
    # Fallback for standalone testing
    import logging
    from abc import ABC, abstractmethod
    from typing import Any, Dict, List

    class AWSAPIIntegration(ABC):
        @abstractmethod
        async def suggest_aws_commands(self, query: str) -> Dict[str, Any]:
            pass

        @abstractmethod
        async def execute_aws_command(
            self, cli_command: str, max_results: Optional[int] = None
        ) -> Dict[str, Any]:
            pass

        @abstractmethod
        async def validate_permissions(
            self, required_permissions: List[str]
        ) -> Dict[str, Any]:
            pass

        @abstractmethod
        async def get_resource_details(
            self, resource_type: str, resource_id: str, region: str = "us-east-1"
        ) -> Dict[str, Any]:
            pass

    class ToolResult:
        def __init__(
            self,
            tool_name,
            mcp_server,
            success,
            data,
            error_message=None,
            execution_time=0.0,
            metadata=None,
        ):
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


logger = get_logger(__name__)


@dataclass
class AWSCommand:
    """Represents an AWS CLI command suggestion"""

    command: str
    confidence: float
    description: str
    required_parameters: List[str]
    example: str


@dataclass
class CommandResult:
    """Result from AWS CLI command execution"""

    command: str
    success: bool
    output: Any
    error_message: Optional[str] = None
    execution_time: float = 0.0


class AWSAPIIntegrationImpl(AWSAPIIntegration):
    """
    Implementation of AWS API MCP Server integration
    Routes to actual MCP tools: suggest_aws_commands and call_aws
    """

    def __init__(self, mcp_orchestrator, region: str = "us-east-1"):
        """
        Initialize AWS API integration

        Args:
            mcp_orchestrator: The MCP orchestrator for calling tools
            region: Default AWS region
        """
        self.mcp_orchestrator = mcp_orchestrator
        self.region = region
        self.error_handler = ErrorHandler()

        # Common AWS CLI patterns for different operations
        self.operation_patterns = {
            "list_resources": {
                "s3": "aws s3api list-buckets",
                "ec2": "aws ec2 describe-instances",
                "rds": "aws rds describe-db-instances",
                "lambda": "aws lambda list-functions",
                "iam": "aws iam list-users",
            },
            "describe_resource": {
                "s3": "aws s3api get-bucket-{attribute} --bucket {resource_id}",
                "ec2": "aws ec2 describe-instances --instance-ids {resource_id}",
                "rds": "aws rds describe-db-instances --db-instance-identifier {resource_id}",
                "lambda": "aws lambda get-function --function-name {resource_id}",
                "iam": "aws iam get-user --user-name {resource_id}",
            },
        }

        logger.info(f"AWS API Integration initialized for region: {self.region}")

    async def suggest_aws_commands(self, query: str) -> Dict[str, Any]:
        """
        Get AWS CLI command suggestions using the suggest_aws_commands MCP tool

        Args:
            query: Natural language description of what to do

        Returns:
            Dictionary with command suggestions and metadata
        """
        try:
            start_time = time.time()

            # Call the suggest_aws_commands MCP tool
            result = await self.mcp_orchestrator.call_api_tool(
                "suggest_aws_commands", {"query": query}
            )

            execution_time = time.time() - start_time

            if result and result.success:
                suggestions = result.data

                # Process and enhance suggestions
                processed_suggestions = self._process_command_suggestions(
                    suggestions, query
                )

                logger.info(
                    f"Generated {len(processed_suggestions)} command suggestions for query: {query}"
                )

                return {
                    "success": True,
                    "query": query,
                    "suggestions": processed_suggestions,
                    "execution_time": execution_time,
                    "metadata": {
                        "mcp_server": "aws-api-mcp-server",
                        "tool_used": "suggest_aws_commands",
                    },
                }
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(f"Failed to get command suggestions: {error_msg}")

                return {
                    "success": False,
                    "query": query,
                    "error": error_msg,
                    "fallback_suggestions": self._get_fallback_suggestions(query),
                    "execution_time": execution_time,
                }

        except Exception as e:
            logger.error(f"Error getting command suggestions for '{query}': {e}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "fallback_suggestions": self._get_fallback_suggestions(query),
            }

    async def execute_aws_command(
        self, cli_command: str, max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute AWS CLI command using the call_aws MCP tool

        Args:
            cli_command: AWS CLI command to execute
            max_results: Optional limit for number of results

        Returns:
            Dictionary with command execution results
        """
        try:
            start_time = time.time()

            # Validate command format
            if not cli_command.strip().startswith("aws "):
                return {
                    "success": False,
                    "command": cli_command,
                    "error": 'Command must start with "aws "',
                    "execution_time": 0.0,
                }

            # Prepare arguments for call_aws tool
            call_args = {"cli_command": cli_command}
            if max_results:
                call_args["max_results"] = max_results

            # Call the call_aws MCP tool
            result = await self.mcp_orchestrator.call_api_tool("call_aws", call_args)

            execution_time = time.time() - start_time

            if result and result.success:
                output_data = result.data

                logger.info(f"Successfully executed AWS command: {cli_command}")

                return {
                    "success": True,
                    "command": cli_command,
                    "output": output_data,
                    "execution_time": execution_time,
                    "metadata": {
                        "mcp_server": "aws-api-mcp-server",
                        "tool_used": "call_aws",
                        "max_results": max_results,
                    },
                }
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(
                    f"Failed to execute AWS command '{cli_command}': {error_msg}"
                )

                return {
                    "success": False,
                    "command": cli_command,
                    "error": error_msg,
                    "execution_time": execution_time,
                }

        except Exception as e:
            logger.error(f"Error executing AWS command '{cli_command}': {e}")
            return {
                "success": False,
                "command": cli_command,
                "error": str(e),
                "execution_time": time.time() - start_time
                if "start_time" in locals()
                else 0.0,
            }

    async def validate_permissions(
        self, required_permissions: List[str]
    ) -> Dict[str, Any]:
        """
        Validate AWS permissions by attempting to execute test commands

        Args:
            required_permissions: List of IAM permissions to validate

        Returns:
            Dictionary with validation results
        """
        try:
            validation_results = {}

            for permission in required_permissions:
                # Map permission to a test command
                test_command = self._get_test_command_for_permission(permission)

                if test_command:
                    # Execute test command with dry-run or minimal impact
                    result = await self.execute_aws_command(test_command)

                    validation_results[permission] = {
                        "granted": result["success"],
                        "test_command": test_command,
                        "error": result.get("error") if not result["success"] else None,
                    }
                else:
                    validation_results[permission] = {
                        "granted": None,
                        "test_command": None,
                        "error": "No test command available for this permission",
                    }

            # Calculate overall status
            granted_count = sum(
                1 for v in validation_results.values() if v["granted"] is True
            )
            total_count = len(required_permissions)

            overall_status = (
                "granted"
                if granted_count == total_count
                else "partial"
                if granted_count > 0
                else "denied"
            )

            logger.info(
                f"Permission validation completed: {granted_count}/{total_count} permissions granted"
            )

            return {
                "success": True,
                "overall_status": overall_status,
                "permissions": validation_results,
                "summary": {
                    "total_permissions": total_count,
                    "granted_permissions": granted_count,
                    "denied_permissions": total_count - granted_count,
                },
            }

        except Exception as e:
            logger.error(f"Error validating permissions: {e}")
            return {"success": False, "error": str(e), "permissions": {}}

    async def get_resource_details(
        self, resource_type: str, resource_id: str, region: str = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about an AWS resource

        Args:
            resource_type: Type of AWS resource (e.g., 's3', 'ec2', 'rds')
            resource_id: Resource identifier
            region: AWS region (defaults to instance region)

        Returns:
            Dictionary with resource details
        """
        try:
            target_region = region or self.region

            # Generate appropriate AWS CLI command for the resource type
            command = self._build_describe_command(
                resource_type, resource_id, target_region
            )

            if not command:
                return {
                    "success": False,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "error": f"Unsupported resource type: {resource_type}",
                }

            # Execute the command
            result = await self.execute_aws_command(command)

            if result["success"]:
                # Process and structure the output
                processed_data = self._process_resource_data(
                    result["output"], resource_type
                )

                return {
                    "success": True,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "region": target_region,
                    "details": processed_data,
                    "raw_command": command,
                }
            else:
                return {
                    "success": False,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "region": target_region,
                    "error": result.get("error", "Unknown error"),
                    "command_used": command,
                }

        except Exception as e:
            logger.error(
                f"Error getting resource details for {resource_type}/{resource_id}: {e}"
            )
            return {
                "success": False,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "error": str(e),
            }

    def _process_command_suggestions(
        self, suggestions: Any, query: str
    ) -> List[Dict[str, Any]]:
        """Process raw command suggestions from MCP tool"""
        processed = []

        if isinstance(suggestions, list):
            for suggestion in suggestions:
                if isinstance(suggestion, dict):
                    processed.append(
                        {
                            "command": suggestion.get("command", ""),
                            "confidence": suggestion.get("confidence", 0.0),
                            "description": suggestion.get("description", ""),
                            "required_parameters": suggestion.get(
                                "required_parameters", []
                            ),
                            "example": suggestion.get(
                                "example", suggestion.get("command", "")
                            ),
                        }
                    )
                elif isinstance(suggestion, str):
                    processed.append(
                        {
                            "command": suggestion,
                            "confidence": 0.8,
                            "description": f"Suggested command for: {query}",
                            "required_parameters": [],
                            "example": suggestion,
                        }
                    )

        return processed

    def _get_fallback_suggestions(self, query: str) -> List[Dict[str, Any]]:
        """Provide fallback suggestions when MCP tool fails"""
        query_lower = query.lower()

        fallback_suggestions = []

        # Common patterns
        if "list" in query_lower:
            if "s3" in query_lower or "bucket" in query_lower:
                fallback_suggestions.append(
                    {
                        "command": "aws s3api list-buckets",
                        "confidence": 0.7,
                        "description": "List all S3 buckets",
                        "required_parameters": [],
                        "example": "aws s3api list-buckets",
                    }
                )
            elif "ec2" in query_lower or "instance" in query_lower:
                fallback_suggestions.append(
                    {
                        "command": "aws ec2 describe-instances",
                        "confidence": 0.7,
                        "description": "List EC2 instances",
                        "required_parameters": [],
                        "example": "aws ec2 describe-instances",
                    }
                )

        return fallback_suggestions

    def _get_test_command_for_permission(self, permission: str) -> Optional[str]:
        """Map IAM permission to a test command"""
        permission_tests = {
            "s3:ListBucket": "aws s3api list-buckets",
            "s3:GetBucketLocation": "aws s3api get-bucket-location --bucket test-bucket-name",
            "ec2:DescribeInstances": "aws ec2 describe-instances --max-items 1",
            "rds:DescribeDBInstances": "aws rds describe-db-instances --max-items 1",
            "lambda:ListFunctions": "aws lambda list-functions --max-items 1",
            "iam:ListUsers": "aws iam list-users --max-items 1",
            "iam:GetUser": "aws sts get-caller-identity",
        }

        return permission_tests.get(permission)

    def _build_describe_command(
        self, resource_type: str, resource_id: str, region: str
    ) -> Optional[str]:
        """Build appropriate describe command for resource type"""
        commands = {
            "s3": f"aws s3api get-bucket-location --bucket {resource_id}",
            "ec2": f"aws ec2 describe-instances --instance-ids {resource_id} --region {region}",
            "rds": f"aws rds describe-db-instances --db-instance-identifier {resource_id} --region {region}",
            "lambda": f"aws lambda get-function --function-name {resource_id} --region {region}",
            "iam": f"aws iam get-user --user-name {resource_id}",
        }

        return commands.get(resource_type.lower())

    def _process_resource_data(
        self, raw_data: Any, resource_type: str
    ) -> Dict[str, Any]:
        """Process raw AWS CLI output into structured data"""
        if isinstance(raw_data, dict):
            return raw_data
        elif isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError:
                return {"raw_output": raw_data}
        else:
            return {"data": raw_data}


# Legacy interface methods for backward compatibility
class AWSAPIIntegrationImpl(AWSAPIIntegrationImpl):
    """Extended implementation with legacy method support"""

    async def get_detailed_resource_config(self, resource_arn: str) -> Dict[str, Any]:
        """Legacy method - get resource details from ARN"""
        try:
            # Parse ARN to extract resource info
            arn_parts = resource_arn.split(":")
            if len(arn_parts) >= 6:
                service = arn_parts[2]
                region = arn_parts[3]
                resource_part = arn_parts[5]

                # Extract resource ID from resource part
                if "/" in resource_part:
                    resource_id = resource_part.split("/")[-1]
                else:
                    resource_id = resource_part

                return await self.get_resource_details(service, resource_id, region)
            else:
                return {
                    "success": False,
                    "error": f"Invalid ARN format: {resource_arn}",
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parsing ARN {resource_arn}: {str(e)}",
            }

    async def analyze_service_configuration(
        self, service_name: str, region: str
    ) -> Dict[str, Any]:
        """Legacy method - analyze service configuration"""
        try:
            # Use suggest_aws_commands to get appropriate analysis commands
            query = f"analyze {service_name} service configuration in {region}"
            suggestions = await self.suggest_aws_commands(query)

            if suggestions["success"] and suggestions["suggestions"]:
                # Execute the first suggested command
                first_suggestion = suggestions["suggestions"][0]
                result = await self.execute_aws_command(first_suggestion["command"])

                return {
                    "success": result["success"],
                    "service_name": service_name,
                    "region": region,
                    "analysis": result.get("output", {}),
                    "command_used": first_suggestion["command"],
                    "error": result.get("error"),
                }
            else:
                return {
                    "success": False,
                    "service_name": service_name,
                    "region": region,
                    "error": "No analysis commands suggested",
                }
        except Exception as e:
            return {
                "success": False,
                "service_name": service_name,
                "region": region,
                "error": str(e),
            }

    async def execute_remediation_action(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Legacy method - execute remediation action"""
        try:
            action_type = action.get("action_type", "")
            target_resource = action.get("target_resource", "")
            parameters = action.get("parameters", {})

            # Generate remediation command based on action type
            query = f"execute {action_type} on {target_resource} with parameters {parameters}"
            suggestions = await self.suggest_aws_commands(query)

            if suggestions["success"] and suggestions["suggestions"]:
                # Execute the remediation command
                command = suggestions["suggestions"][0]["command"]
                result = await self.execute_aws_command(command)

                return {
                    "success": result["success"],
                    "action_id": action.get("action_id", "unknown"),
                    "action_type": action_type,
                    "target_resource": target_resource,
                    "result": result.get("output", {}),
                    "command_executed": command,
                    "error": result.get("error"),
                }
            else:
                return {
                    "success": False,
                    "action_id": action.get("action_id", "unknown"),
                    "error": "No remediation commands suggested",
                }
        except Exception as e:
            return {
                "success": False,
                "action_id": action.get("action_id", "unknown"),
                "error": str(e),
            }
