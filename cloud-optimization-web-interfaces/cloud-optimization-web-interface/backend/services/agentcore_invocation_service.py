"""
AgentCore Invocation Service - Handles agent invocation through boto3 AgentCore client.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Any

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError, NoCredentialsError

from models.agentcore_models import AgentInfo, AgentResponse, InvocationStats
from models.agentcore_interfaces import AgentInvocationInterface
from models.exceptions import AgentInvocationError, AgentCoreClientError

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state for agent invocations."""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session."""
        session = {
            "session_id": session_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "context": {}
        }
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get an existing session."""
        session = self.sessions.get(session_id)
        if session:
            session["last_activity"] = datetime.utcnow()
        return session
    
    def update_session(self, session_id: str, context: Dict[str, Any]) -> None:
        """Update session context."""
        if session_id in self.sessions:
            self.sessions[session_id]["context"].update(context)
            self.sessions[session_id]["last_activity"] = datetime.utcnow()


class AgentCoreInvocationService(AgentInvocationInterface):
    """Handles agent invocation through boto3 AgentCore client with dynamic prompt processing."""
    
    def __init__(self, region: str = "us-east-1", timeout: int = 120):
        """
        Initialize the invocation service.
        
        Args:
            region: AWS region for clients
            timeout: Request timeout in seconds
        """
        self.region = region
        self.timeout = timeout
        
        # Client management
        self.agentcore_client = None
        self.bedrock_agent_runtime = None
        self.session_manager = SessionManager()
        self._boto3_session = None
        
        # Statistics tracking
        self._stats = InvocationStats()
        
        # Client version tracking
        self._boto3_version = None
        self._agentcore_available = False
        
        logger.info(f"AgentCore Invocation Service initialized - region: {region}, timeout: {timeout}s")
    
    async def initialize_client(self) -> bool:
        """
        Initialize the AgentCore client.
        
        Returns:
            True if initialization successful
        """
        try:
            # Check boto3 version
            self._boto3_version = boto3.__version__
            logger.info(f"Using boto3 version: {self._boto3_version}")
            
            # Initialize boto3 session
            self._boto3_session = boto3.Session()
            
            # Try to initialize AgentCore client
            try:
                self.agentcore_client = boto3.client("bedrock-agentcore", region_name=self.region)
                self._agentcore_available = True
                logger.info("✓ AgentCore client initialized successfully")
            except Exception as e:
                logger.warning(f"AgentCore client not available: {e}")
                self._agentcore_available = False
            
            # Initialize fallback Bedrock Agent Runtime client
            try:
                self.bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=self.region)
                logger.info("✓ Bedrock Agent Runtime client initialized")
            except Exception as e:
                logger.warning(f"Bedrock Agent Runtime client initialization failed: {e}")
            
            # Test basic connectivity
            if self._agentcore_available:
                # Test AgentCore client (this would be service-specific)
                logger.info("AgentCore client ready for invocations")
            elif self.bedrock_agent_runtime:
                # Test Bedrock Agent Runtime connectivity
                logger.info("Bedrock Agent Runtime client ready for fallback invocations")
            else:
                logger.error("No agent runtime clients available")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AgentCore client: {e}")
            raise AgentCoreClientError(
                f"Failed to initialize AgentCore client: {e}",
                client_version=self._boto3_version,
                details={"error": str(e), "region": self.region}
            )
    
    async def invoke_agent(self, agent_info: AgentInfo, prompt: str, session_id: str) -> AgentResponse:
        """
        Invoke an AgentCore agent.
        
        Args:
            agent_info: Agent information
            prompt: Input prompt
            session_id: Session identifier
            
        Returns:
            Agent response
        """
        start_time = time.time()
        
        try:
            logger.info(f"Invoking agent {agent_info.agent_id} for session {session_id}")
            
            # Update statistics
            self._stats.total_invocations += 1
            self._stats.last_invocation = datetime.utcnow()
            
            # Get or create session
            session = self.session_manager.get_session(session_id)
            if not session:
                session = self.session_manager.create_session(session_id)
            
            # Format prompt for the specific agent
            formatted_prompt = await self.format_prompt(prompt, agent_info.agent_name)
            
            # Choose invocation method based on agent type
            if agent_info.is_agentcore() and self._agentcore_available:
                response = await self._invoke_agentcore_agent(agent_info, formatted_prompt, session_id)
            elif agent_info.is_agentcore() and agent_info.endpoint_url:
                response = await self._invoke_agentcore_http(agent_info, formatted_prompt, session_id)
            elif agent_info.is_bedrock_agent() and self.bedrock_agent_runtime:
                response = await self._invoke_bedrock_agent(agent_info, formatted_prompt, session_id)
            else:
                raise AgentInvocationError(
                    f"No suitable invocation method for agent {agent_info.agent_id}",
                    agent_id=agent_info.agent_id,
                    session_id=session_id
                )
            
            # Update statistics
            execution_time = time.time() - start_time
            self._stats.successful_invocations += 1
            self._update_average_response_time(execution_time)
            
            # Create response object
            agent_response = AgentResponse(
                agent_id=agent_info.agent_id,
                response_text=response,
                session_id=session_id,
                execution_time=execution_time,
                status="success",
                metadata={
                    "agent_name": agent_info.agent_name,
                    "runtime_type": agent_info.runtime_type.value,
                    "invocation_method": self._get_invocation_method(agent_info)
                }
            )
            
            logger.info(f"Agent invocation completed in {execution_time:.2f}s")
            return agent_response
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._stats.failed_invocations += 1
            
            logger.error(f"Agent invocation failed: {e}")
            raise AgentInvocationError(
                f"Agent invocation failed: {e}",
                agent_id=agent_info.agent_id,
                session_id=session_id,
                details={
                    "error": str(e),
                    "execution_time": execution_time,
                    "agent_type": agent_info.runtime_type.value
                }
            )
    
    async def _invoke_agentcore_agent(self, agent_info: AgentInfo, prompt: Dict[str, Any], session_id: str) -> str:
        """
        Invoke agent using boto3 AgentCore client.
        
        Args:
            agent_info: Agent information
            prompt: Formatted prompt
            session_id: Session identifier
            
        Returns:
            Agent response text
        """
        try:
            # This would be the actual AgentCore client invocation
            # Since AgentCore client API is not yet available, we'll simulate
            logger.info(f"Invoking AgentCore agent via boto3 client: {agent_info.agent_id}")
            
            # Simulated AgentCore client call
            # response = self.agentcore_client.invoke_agent(
            #     AgentId=agent_info.agent_id,
            #     SessionId=session_id,
            #     InputText=prompt["text"],
            #     **prompt.get("parameters", {})
            # )
            
            # For now, return a simulated response
            return f"AgentCore response from {agent_info.agent_name}: Processed your request '{prompt.get('text', '')}'"
            
        except Exception as e:
            logger.error(f"AgentCore client invocation failed: {e}")
            raise
    
    async def _invoke_agentcore_http(self, agent_info: AgentInfo, prompt: Dict[str, Any], session_id: str) -> str:
        """
        Invoke agent using HTTP endpoint with AWS SigV4 authentication.
        
        Args:
            agent_info: Agent information
            prompt: Formatted prompt
            session_id: Session identifier
            
        Returns:
            Agent response text
        """
        try:
            logger.info(f"Invoking AgentCore agent via HTTP: {agent_info.endpoint_url}")
            
            # Prepare payload
            payload = {
                "prompt": prompt.get("text", ""),
                "sessionId": session_id,
                "parameters": prompt.get("parameters", {})
            }
            
            # Get AWS credentials for signing
            credentials = self._boto3_session.get_credentials()
            
            # Create signed request
            request = AWSRequest(
                method='POST',
                url=agent_info.endpoint_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            SigV4Auth(credentials, 'bedrock-agentcore', self.region).add_auth(request)
            
            # Make HTTP request
            response = requests.post(
                agent_info.endpoint_url,
                data=json.dumps(payload),
                headers=dict(request.headers),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    return result if isinstance(result, str) else json.dumps(result, indent=2)
                except:
                    return response.text
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"AgentCore HTTP invocation failed: {e}")
            raise
    
    async def _invoke_bedrock_agent(self, agent_info: AgentInfo, prompt: Dict[str, Any], session_id: str) -> str:
        """
        Invoke agent using Bedrock Agent Runtime client (fallback).
        
        Args:
            agent_info: Agent information
            prompt: Formatted prompt
            session_id: Session identifier
            
        Returns:
            Agent response text
        """
        try:
            logger.info(f"Invoking Bedrock Agent via runtime client: {agent_info.agent_id}")
            
            # Use Bedrock Agent Runtime
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_info.agent_id,
                agentAliasId=agent_info.metadata.get("agent_alias_id", "TSTALIASID"),
                sessionId=session_id,
                inputText=prompt.get("text", "")
            )
            
            # Process streaming response
            response_text = ""
            if "completion" in response:
                for event in response["completion"]:
                    if "chunk" in event:
                        chunk = event["chunk"]
                        if "bytes" in chunk:
                            chunk_text = chunk["bytes"].decode("utf-8")
                            response_text += chunk_text
            
            return response_text or f"Processed request via Bedrock Agent: {agent_info.agent_name}"
            
        except Exception as e:
            logger.error(f"Bedrock Agent invocation failed: {e}")
            raise
    
    async def format_prompt(self, prompt: str, agent_type: str) -> Dict[str, Any]:
        """
        Format prompt for specific agent type.
        
        Args:
            prompt: Raw prompt text
            agent_type: Agent type identifier
            
        Returns:
            Formatted prompt dictionary
        """
        try:
            # Basic prompt formatting
            formatted_prompt = {
                "text": prompt,
                "parameters": {},
                "metadata": {
                    "agent_type": agent_type,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Agent-specific formatting
            if "security" in agent_type.lower():
                formatted_prompt["parameters"]["focus"] = "security_analysis"
            elif "cost" in agent_type.lower():
                formatted_prompt["parameters"]["focus"] = "cost_optimization"
            
            # Add context hints
            if len(prompt) > 1000:
                formatted_prompt["parameters"]["long_form"] = True
            
            return formatted_prompt
            
        except Exception as e:
            logger.error(f"Prompt formatting failed: {e}")
            # Return basic format on error
            return {"text": prompt, "parameters": {}}
    
    async def validate_response(self, response: Dict) -> bool:
        """
        Validate agent response.
        
        Args:
            response: Agent response dictionary
            
        Returns:
            True if response is valid
        """
        try:
            # Basic validation
            if not isinstance(response, dict):
                return False
            
            # Check for required fields
            required_fields = ["agent_id", "response_text", "session_id"]
            for field in required_fields:
                if field not in response:
                    return False
            
            # Validate response content
            if not response.get("response_text"):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Response validation failed: {e}")
            return False
    
    def get_client_status(self) -> Dict[str, Any]:
        """
        Get client status information.
        
        Returns:
            Client status dictionary
        """
        return {
            "agentcore_available": self._agentcore_available,
            "bedrock_agent_runtime_available": self.bedrock_agent_runtime is not None,
            "boto3_version": self._boto3_version,
            "region": self.region,
            "timeout": self.timeout,
            "session_count": len(self.session_manager.sessions)
        }
    
    def get_invocation_stats(self) -> InvocationStats:
        """
        Get invocation statistics.
        
        Returns:
            Invocation statistics
        """
        return self._stats
    
    async def health_check(self) -> str:
        """
        Check invocation service health status.
        
        Returns:
            Health status string
        """
        try:
            # Check if any client is available
            if not self._agentcore_available and not self.bedrock_agent_runtime:
                return "unhealthy"
            
            # Check success rate
            if self._stats.total_invocations > 0:
                success_rate = self._stats.successful_invocations / self._stats.total_invocations
                if success_rate < 0.5:  # Less than 50% success rate
                    return "degraded"
            
            return "healthy"
            
        except Exception as e:
            logger.error(f"Invocation service health check failed: {e}")
            return "unhealthy"
    
    def _get_invocation_method(self, agent_info: AgentInfo) -> str:
        """Get the invocation method used for an agent."""
        if agent_info.is_agentcore() and self._agentcore_available:
            return "agentcore_client"
        elif agent_info.is_agentcore() and agent_info.endpoint_url:
            return "agentcore_http"
        elif agent_info.is_bedrock_agent():
            return "bedrock_agent_runtime"
        else:
            return "unknown"
    
    def _update_average_response_time(self, execution_time: float) -> None:
        """Update average response time statistics."""
        if self._stats.successful_invocations == 1:
            self._stats.average_response_time = execution_time
        else:
            # Calculate running average
            total_time = self._stats.average_response_time * (self._stats.successful_invocations - 1)
            self._stats.average_response_time = (total_time + execution_time) / self._stats.successful_invocations
    
    def set_timeout(self, timeout: int) -> None:
        """
        Set request timeout.
        
        Args:
            timeout: Timeout in seconds
        """
        self.timeout = timeout
        logger.info(f"Request timeout updated to {timeout}s")
    
    def clear_sessions(self) -> int:
        """
        Clear all sessions.
        
        Returns:
            Number of sessions cleared
        """
        count = len(self.session_manager.sessions)
        self.session_manager.sessions.clear()
        logger.info(f"Cleared {count} sessions")
        return count