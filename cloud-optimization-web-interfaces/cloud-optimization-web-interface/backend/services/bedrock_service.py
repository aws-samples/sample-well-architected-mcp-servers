"""
Bedrock Service for direct model and agent communication.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from models.data_models import ChatMessage, ToolExecution
from models.exceptions import BedrockServiceError, ModelInvocationError, AgentInvocationError


logger = logging.getLogger(__name__)


class BedrockService:
    """Service for communicating with Amazon Bedrock models and agents."""
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the Bedrock Service.
        
        Args:
            region: AWS region for Bedrock services
        """
        self.region = region
        
        # Initialize AWS clients
        try:
            self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
            self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
            logger.info(f"BedrockService initialized for region {region}")
        except (NoCredentialsError, ClientError, Exception) as e:
            logger.error(f"Failed to initialize Bedrock clients: {e}")
            raise BedrockServiceError(f"Failed to initialize Bedrock clients: {e}")
        
        # Default model configurations
        self.default_models = {
            "lightweight": "anthropic.claude-3-haiku-20240307-v1:0",
            "standard": "anthropic.claude-3-5-sonnet-20241022-v2:0"
        }
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0

    async def invoke_model(
        self, 
        model_id: str, 
        messages: List[ChatMessage], 
        max_tokens: int = 4096,
        temperature: float = 0.1,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Invoke a Bedrock model with direct communication.
        
        Args:
            model_id: The Bedrock model identifier
            messages: List of chat messages for context
            max_tokens: Maximum tokens to generate
            temperature: Model temperature for randomness
            streaming: Whether to use streaming response
            
        Returns:
            Dictionary with model response and metadata
            
        Raises:
            ModelInvocationError: If model invocation fails
        """
        try:
            logger.debug(f"Invoking model {model_id} with {len(messages)} messages")
            
            # Prepare request body based on model type
            if "anthropic.claude" in model_id:
                body = self._prepare_claude_request(messages, max_tokens, temperature)
            else:
                raise ModelInvocationError(f"Unsupported model type: {model_id}")
            
            # Invoke model with retry logic
            for attempt in range(self.max_retries):
                try:
                    if streaming:
                        return await self._invoke_model_streaming(model_id, body)
                    else:
                        return await self._invoke_model_sync(model_id, body)
                        
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    
                    if error_code in ['ThrottlingException', 'ServiceUnavailableException'] and attempt < self.max_retries - 1:
                        logger.warning(f"Retrying model invocation due to {error_code} (attempt {attempt + 1})")
                        await self._wait_for_retry(attempt)
                        continue
                    else:
                        raise ModelInvocationError(f"Model invocation failed: {e}")
                        
        except Exception as e:
            logger.error(f"Error invoking model {model_id}: {e}")
            if isinstance(e, ModelInvocationError):
                raise
            raise ModelInvocationError(f"Unexpected error during model invocation: {e}")

    async def _invoke_model_sync(self, model_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke model synchronously."""
        start_time = datetime.utcnow()
        
        response = self.bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType='application/json'
        )
        
        end_time = datetime.utcnow()
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Parse response
        response_body = json.loads(response['body'].read())
        
        # Extract content based on model type
        if "anthropic.claude" in model_id:
            content = response_body.get('content', [{}])[0].get('text', '')
            usage = response_body.get('usage', {})
        else:
            content = str(response_body)
            usage = {}
        
        logger.debug(f"Model {model_id} responded in {response_time_ms:.1f}ms")
        
        return {
            "content": content,
            "model_id": model_id,
            "usage": usage,
            "response_time_ms": response_time_ms,
            "streaming": False,
            "timestamp": end_time.isoformat()
        }

    async def _invoke_model_streaming(self, model_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke model with streaming response."""
        start_time = datetime.utcnow()
        
        response = self.bedrock_runtime.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body),
            contentType='application/json'
        )
        
        # For streaming, we'll return a generator function
        async def stream_generator():
            full_content = ""
            for event in response['body']:
                if 'chunk' in event:
                    chunk_data = json.loads(event['chunk']['bytes'])
                    if "anthropic.claude" in model_id:
                        if chunk_data.get('type') == 'content_block_delta':
                            delta = chunk_data.get('delta', {}).get('text', '')
                            full_content += delta
                            yield {
                                "type": "content_delta",
                                "delta": delta,
                                "full_content": full_content
                            }
                        elif chunk_data.get('type') == 'message_stop':
                            end_time = datetime.utcnow()
                            response_time_ms = (end_time - start_time).total_seconds() * 1000
                            yield {
                                "type": "stream_end",
                                "full_content": full_content,
                                "response_time_ms": response_time_ms,
                                "timestamp": end_time.isoformat()
                            }
        
        return {
            "content": "",  # Will be populated through streaming
            "model_id": model_id,
            "streaming": True,
            "stream_generator": stream_generator(),
            "timestamp": start_time.isoformat()
        }

    def _prepare_claude_request(
        self, 
        messages: List[ChatMessage], 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        """Prepare request body for Claude models."""
        # Convert ChatMessage objects to Claude format
        claude_messages = []
        system_message = None
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": claude_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        if system_message:
            body["system"] = system_message
            
        return body

    async def _wait_for_retry(self, attempt: int) -> None:
        """Wait before retrying with exponential backoff."""
        import asyncio
        wait_time = self.retry_delay * (2 ** attempt)
        await asyncio.sleep(wait_time)

    def get_lightweight_model(self) -> str:
        """Get the default lightweight model ID."""
        return self.default_models["lightweight"]

    def get_standard_model(self) -> str:
        """Get the default standard model ID."""
        return self.default_models["standard"]

    async def invoke_agent(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        input_text: str,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Invoke a Bedrock agent with session management.
        
        Args:
            agent_id: The Bedrock agent identifier
            agent_alias_id: The agent alias identifier
            session_id: Session ID for conversation continuity
            input_text: User input text
            streaming: Whether to use streaming response
            
        Returns:
            Dictionary with agent response and metadata
            
        Raises:
            AgentInvocationError: If agent invocation fails
        """
        try:
            logger.debug(f"Invoking agent {agent_id} with session {session_id}")
            
            # Prepare agent request
            request_params = {
                'agentId': agent_id,
                'agentAliasId': agent_alias_id,
                'sessionId': session_id,
                'inputText': input_text
            }
            
            # Invoke agent with retry logic
            for attempt in range(self.max_retries):
                try:
                    if streaming:
                        return await self._invoke_agent_streaming(request_params)
                    else:
                        return await self._invoke_agent_sync(request_params)
                        
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    
                    if error_code in ['ThrottlingException', 'ServiceUnavailableException'] and attempt < self.max_retries - 1:
                        logger.warning(f"Retrying agent invocation due to {error_code} (attempt {attempt + 1})")
                        await self._wait_for_retry(attempt)
                        continue
                    else:
                        raise AgentInvocationError(f"Agent invocation failed: {e}")
                        
        except Exception as e:
            logger.error(f"Error invoking agent {agent_id}: {e}")
            if isinstance(e, AgentInvocationError):
                raise
            raise AgentInvocationError(f"Unexpected error during agent invocation: {e}")

    async def _invoke_agent_sync(self, request_params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke agent synchronously."""
        start_time = datetime.utcnow()
        
        response = self.bedrock_agent_runtime.invoke_agent(**request_params)
        
        end_time = datetime.utcnow()
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Parse agent response
        completion = ""
        tool_executions = []
        
        for event in response.get('completion', []):
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    chunk_data = json.loads(chunk['bytes'])
                    if chunk_data.get('type') == 'chunk':
                        completion += chunk_data.get('bytes', '').decode('utf-8')
                    elif chunk_data.get('type') == 'trace':
                        # Handle tool execution traces
                        trace_data = chunk_data.get('trace', {})
                        if 'orchestrationTrace' in trace_data:
                            orch_trace = trace_data['orchestrationTrace']
                            if 'invocationInput' in orch_trace:
                                tool_executions.append(self._parse_tool_execution(orch_trace))
        
        logger.debug(f"Agent {request_params['agentId']} responded in {response_time_ms:.1f}ms")
        
        return {
            "content": completion,
            "agent_id": request_params['agentId'],
            "session_id": request_params['sessionId'],
            "tool_executions": tool_executions,
            "response_time_ms": response_time_ms,
            "streaming": False,
            "timestamp": end_time.isoformat()
        }

    async def _invoke_agent_streaming(self, request_params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke agent with streaming response."""
        start_time = datetime.utcnow()
        
        response = self.bedrock_agent_runtime.invoke_agent(**request_params)
        
        # For streaming, we'll return a generator function
        async def stream_generator():
            full_content = ""
            tool_executions = []
            
            for event in response.get('completion', []):
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        try:
                            chunk_data = json.loads(chunk['bytes'])
                            
                            if chunk_data.get('type') == 'chunk':
                                delta = chunk_data.get('bytes', '').decode('utf-8')
                                full_content += delta
                                yield {
                                    "type": "content_delta",
                                    "delta": delta,
                                    "full_content": full_content
                                }
                            elif chunk_data.get('type') == 'trace':
                                # Handle tool execution traces
                                trace_data = chunk_data.get('trace', {})
                                if 'orchestrationTrace' in trace_data:
                                    orch_trace = trace_data['orchestrationTrace']
                                    if 'invocationInput' in orch_trace:
                                        tool_exec = self._parse_tool_execution(orch_trace)
                                        tool_executions.append(tool_exec)
                                        yield {
                                            "type": "tool_execution",
                                            "tool_execution": tool_exec
                                        }
                        except json.JSONDecodeError:
                            # Handle non-JSON chunks
                            delta = chunk['bytes'].decode('utf-8')
                            full_content += delta
                            yield {
                                "type": "content_delta",
                                "delta": delta,
                                "full_content": full_content
                            }
            
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            yield {
                "type": "stream_end",
                "full_content": full_content,
                "tool_executions": tool_executions,
                "response_time_ms": response_time_ms,
                "timestamp": end_time.isoformat()
            }
        
        return {
            "content": "",  # Will be populated through streaming
            "agent_id": request_params['agentId'],
            "session_id": request_params['sessionId'],
            "streaming": True,
            "stream_generator": stream_generator(),
            "timestamp": start_time.isoformat()
        }

    def _parse_tool_execution(self, orchestration_trace: Dict[str, Any]) -> ToolExecution:
        """Parse tool execution from orchestration trace."""
        try:
            invocation_input = orchestration_trace.get('invocationInput', {})
            tool_name = invocation_input.get('actionGroupInvocationInput', {}).get('actionGroupName', 'unknown')
            tool_input = invocation_input.get('actionGroupInvocationInput', {}).get('parameters', {})
            
            # Extract output if available
            tool_output = orchestration_trace.get('observation', {}).get('actionGroupInvocationOutput', {}).get('text', '')
            
            # Determine success based on presence of output
            success = bool(tool_output and 'error' not in tool_output.lower())
            error_message = None if success else tool_output
            
            return ToolExecution(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                execution_time_ms=0,  # Not available in trace
                success=success,
                error_message=error_message
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse tool execution: {e}")
            return ToolExecution(
                tool_name="unknown",
                tool_input={},
                tool_output="",
                execution_time_ms=0,
                success=False,
                error_message=f"Failed to parse tool execution: {e}"
            )

    def format_response(self, response: Dict[str, Any], response_type: str = "model") -> Dict[str, Any]:
        """
        Format Bedrock responses into consistent format.
        
        Args:
            response: Raw response from model or agent invocation
            response_type: Type of response ("model" or "agent")
            
        Returns:
            Formatted response dictionary
        """
        try:
            formatted = {
                "success": True,
                "response_type": response_type,
                "content": response.get("content", ""),
                "metadata": {
                    "timestamp": response.get("timestamp", datetime.utcnow().isoformat()),
                    "response_time_ms": response.get("response_time_ms", 0),
                    "streaming": response.get("streaming", False)
                }
            }
            
            if response_type == "model":
                formatted["metadata"].update({
                    "model_id": response.get("model_id", "unknown"),
                    "usage": response.get("usage", {})
                })
            elif response_type == "agent":
                formatted["metadata"].update({
                    "agent_id": response.get("agent_id", "unknown"),
                    "session_id": response.get("session_id", "unknown"),
                    "tool_executions": response.get("tool_executions", [])
                })
            
            # Handle streaming responses
            if response.get("streaming"):
                formatted["stream_generator"] = response.get("stream_generator")
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting {response_type} response: {e}")
            return {
                "success": False,
                "response_type": response_type,
                "content": "",
                "error": str(e),
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "response_time_ms": 0,
                    "streaming": False
                }
            }

    def parse_streaming_chunk(self, chunk: Dict[str, Any], response_type: str = "model") -> Dict[str, Any]:
        """
        Parse individual streaming chunks into consistent format.
        
        Args:
            chunk: Individual chunk from streaming response
            response_type: Type of response ("model" or "agent")
            
        Returns:
            Parsed chunk dictionary
        """
        try:
            parsed = {
                "type": chunk.get("type", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if chunk.get("type") == "content_delta":
                parsed.update({
                    "delta": chunk.get("delta", ""),
                    "full_content": chunk.get("full_content", "")
                })
            elif chunk.get("type") == "tool_execution":
                parsed.update({
                    "tool_execution": chunk.get("tool_execution")
                })
            elif chunk.get("type") == "stream_end":
                parsed.update({
                    "full_content": chunk.get("full_content", ""),
                    "response_time_ms": chunk.get("response_time_ms", 0),
                    "tool_executions": chunk.get("tool_executions", []) if response_type == "agent" else []
                })
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing streaming chunk: {e}")
            return {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def create_streaming_response(self, response: Dict[str, Any], response_type: str = "model") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create async generator for streaming responses.
        
        Args:
            response: Response containing stream_generator
            response_type: Type of response ("model" or "agent")
            
        Yields:
            Formatted streaming chunks
        """
        try:
            if not response.get("streaming") or "stream_generator" not in response:
                # Not a streaming response, yield the complete response
                yield self.format_response(response, response_type)
                return
            
            stream_generator = response["stream_generator"]
            async for chunk in stream_generator:
                parsed_chunk = self.parse_streaming_chunk(chunk, response_type)
                yield parsed_chunk
                
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def extract_tool_results(self, response: Dict[str, Any]) -> List[ToolExecution]:
        """
        Extract tool execution results from agent response.
        
        Args:
            response: Agent response containing tool executions
            
        Returns:
            List of ToolExecution objects
        """
        try:
            tool_executions = response.get("tool_executions", [])
            if isinstance(tool_executions, list):
                return tool_executions
            else:
                logger.warning("Tool executions is not a list, returning empty list")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting tool results: {e}")
            return []

    def get_response_summary(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get summary information from a response.
        
        Args:
            response: Formatted response dictionary
            
        Returns:
            Summary information
        """
        try:
            metadata = response.get("metadata", {})
            summary = {
                "success": response.get("success", False),
                "response_type": response.get("response_type", "unknown"),
                "content_length": len(response.get("content", "")),
                "response_time_ms": metadata.get("response_time_ms", 0),
                "streaming": metadata.get("streaming", False),
                "timestamp": metadata.get("timestamp", "")
            }
            
            # Add type-specific information
            if response.get("response_type") == "model":
                usage = metadata.get("usage", {})
                summary.update({
                    "model_id": metadata.get("model_id", "unknown"),
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0)
                })
            elif response.get("response_type") == "agent":
                tool_executions = metadata.get("tool_executions", [])
                summary.update({
                    "agent_id": metadata.get("agent_id", "unknown"),
                    "session_id": metadata.get("session_id", "unknown"),
                    "tool_count": len(tool_executions),
                    "successful_tools": sum(1 for tool in tool_executions if tool.success)
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error creating response summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for Bedrock service.
        
        Returns:
            Dictionary with health status information
        """
        try:
            # Test basic connectivity by listing foundation models
            models_response = self.bedrock_runtime.list_foundation_models()
            model_count = len(models_response.get('modelSummaries', []))
            
            return {
                "service": "bedrock",
                "status": "healthy",
                "region": self.region,
                "available_models": model_count,
                "default_models": self.default_models,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Bedrock health check failed: {e}")
            return {
                "service": "bedrock",
                "status": "unhealthy",
                "region": self.region,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }