"""
Shared Bedrock Model Service for direct model access without agent functionality.
Used by both BedrockAgent and AgentCore versions for fallback scenarios.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from shared.models.chat_models import ChatMessage
from shared.models.exceptions import BedrockServiceError, ModelInvocationError


logger = logging.getLogger(__name__)


class BedrockModelService:
    """Service for direct communication with Amazon Bedrock models (no agents)."""
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the Bedrock Model Service.
        
        Args:
            region: AWS region for Bedrock services
        """
        self.region = region
        
        # Initialize AWS client for model access only
        try:
            self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
            logger.info(f"BedrockModelService initialized for region {region}")
        except (NoCredentialsError, ClientError, Exception) as e:
            logger.error(f"Failed to initialize Bedrock runtime client: {e}")
            raise BedrockServiceError(f"Failed to initialize Bedrock runtime client: {e}")
        
        # Default model configurations
        self.default_models = {
            "lightweight": "anthropic.claude-3-haiku-20240307-v1:0",
            "standard": "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
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

    async def invoke_model_streaming(
        self, 
        model_id: str, 
        messages: List[ChatMessage], 
        max_tokens: int = 4096,
        temperature: float = 0.1
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Invoke a Bedrock model with streaming response.
        
        Args:
            model_id: The Bedrock model identifier
            messages: List of chat messages for context
            max_tokens: Maximum tokens to generate
            temperature: Model temperature for randomness
            
        Yields:
            Streaming response chunks
            
        Raises:
            ModelInvocationError: If model invocation fails
        """
        response = await self.invoke_model(
            model_id=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            streaming=True
        )
        
        if response.get("streaming") and "stream_generator" in response:
            async for chunk in response["stream_generator"]:
                yield self.parse_streaming_chunk(chunk)

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

    def format_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format Bedrock model responses into consistent format.
        
        Args:
            response: Raw response from model invocation
            
        Returns:
            Formatted response dictionary
        """
        try:
            formatted = {
                "success": True,
                "response_type": "model",
                "content": response.get("content", ""),
                "metadata": {
                    "model_id": response.get("model_id", "unknown"),
                    "usage": response.get("usage", {}),
                    "timestamp": response.get("timestamp", datetime.utcnow().isoformat()),
                    "response_time_ms": response.get("response_time_ms", 0),
                    "streaming": response.get("streaming", False)
                }
            }
            
            # Handle streaming responses
            if response.get("streaming"):
                formatted["stream_generator"] = response.get("stream_generator")
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting model response: {e}")
            return {
                "success": False,
                "response_type": "model",
                "content": "",
                "error": str(e),
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "response_time_ms": 0,
                    "streaming": False
                }
            }

    def parse_streaming_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse individual streaming chunks into consistent format.
        
        Args:
            chunk: Individual chunk from streaming response
            
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
            elif chunk.get("type") == "stream_end":
                parsed.update({
                    "full_content": chunk.get("full_content", ""),
                    "response_time_ms": chunk.get("response_time_ms", 0)
                })
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing streaming chunk: {e}")
            return {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def create_streaming_response(self, response: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create async generator for streaming responses.
        
        Args:
            response: Response containing stream_generator
            
        Yields:
            Formatted streaming chunks
        """
        try:
            if not response.get("streaming") or "stream_generator" not in response:
                # Not a streaming response, yield the complete response
                yield self.format_response(response)
                return
            
            stream_generator = response["stream_generator"]
            async for chunk in stream_generator:
                parsed_chunk = self.parse_streaming_chunk(chunk)
                yield parsed_chunk
                
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def get_response_summary(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get summary information from a model response.
        
        Args:
            response: Formatted response dictionary
            
        Returns:
            Summary information
        """
        try:
            metadata = response.get("metadata", {})
            usage = metadata.get("usage", {})
            
            summary = {
                "success": response.get("success", False),
                "response_type": "model",
                "content_length": len(response.get("content", "")),
                "response_time_ms": metadata.get("response_time_ms", 0),
                "streaming": metadata.get("streaming", False),
                "model_id": metadata.get("model_id", "unknown"),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "timestamp": metadata.get("timestamp", "")
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error creating response summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def health_check(self) -> str:
        """
        Perform health check for Bedrock model service.
        
        Returns:
            Health status string ("healthy", "degraded", "unhealthy")
        """
        try:
            # Test basic connectivity by listing foundation models
            bedrock_client = boto3.client('bedrock', region_name=self.region)
            models_response = bedrock_client.list_foundation_models()
            model_count = len(models_response.get('modelSummaries', []))
            
            if model_count > 0:
                return "healthy"
            else:
                return "degraded"
            
        except Exception as e:
            logger.error(f"Bedrock model service health check failed: {e}")
            return "unhealthy"

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information and configuration.
        
        Returns:
            Dictionary with service information
        """
        return {
            "service": "bedrock_model_service",
            "region": self.region,
            "default_models": self.default_models,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timestamp": datetime.utcnow().isoformat()
        }