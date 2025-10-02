"""
Error Handler for graceful degradation and fallback mechanisms.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models.data_models import ChatMessage
from ..models.exceptions import (
    COABaseException, 
    BedrockCommunicationError, 
    AgentDiscoveryError,
    SessionManagementError,
    ConfigurationError
)


logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handles errors with fallback mechanisms and graceful degradation."""
    
    def __init__(self):
        """Initialize the Error Handler."""
        self.error_stats = {
            "total_errors": 0,
            "bedrock_errors": 0,
            "agent_errors": 0,
            "session_errors": 0,
            "config_errors": 0,
            "fallback_activations": 0,
            "last_error_time": None
        }
        
        # Fallback responses for different error types
        self.fallback_responses = {
            "bedrock_unavailable": "I'm experiencing technical difficulties connecting to AWS services. Please try again in a moment.",
            "agent_unavailable": "The requested agent is currently unavailable. I'll try to help you with a general response.",
            "session_error": "There was an issue with your session. Your conversation history may be affected.",
            "config_error": "There's a configuration issue that's preventing me from functioning properly.",
            "general_error": "I encountered an unexpected error. Please try rephrasing your question or try again later."
        }
        
        logger.info("ErrorHandler initialized")

    def handle_bedrock_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle Bedrock service errors with fallback strategies.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Tuple of (fallback_response, error_metadata)
        """
        try:
            self.error_stats["total_errors"] += 1
            self.error_stats["bedrock_errors"] += 1
            self.error_stats["last_error_time"] = datetime.utcnow().isoformat()
            
            context = context or {}
            
            # Log the error
            logger.error(f"Bedrock error: {error}", extra={"context": context})
            
            # Determine fallback strategy based on error type
            if isinstance(error, BedrockCommunicationError):
                service_type = getattr(error, 'service_type', 'unknown')
                target_id = getattr(error, 'target_id', 'unknown')
                
                if service_type == "model":
                    fallback_response = self._get_model_fallback_response(context)
                    error_metadata = {
                        "error_type": "model_communication_error",
                        "model_id": target_id,
                        "fallback_strategy": "lightweight_model",
                        "can_retry": True
                    }
                elif service_type == "agent":
                    fallback_response = self._get_agent_fallback_response(context)
                    error_metadata = {
                        "error_type": "agent_communication_error",
                        "agent_id": target_id,
                        "fallback_strategy": "direct_model",
                        "can_retry": True
                    }
                else:
                    fallback_response = self.fallback_responses["bedrock_unavailable"]
                    error_metadata = {
                        "error_type": "bedrock_communication_error",
                        "fallback_strategy": "static_response",
                        "can_retry": True
                    }
            else:
                # Generic Bedrock error
                fallback_response = self.fallback_responses["bedrock_unavailable"]
                error_metadata = {
                    "error_type": "bedrock_generic_error",
                    "error_message": str(error),
                    "fallback_strategy": "static_response",
                    "can_retry": True
                }
            
            self.error_stats["fallback_activations"] += 1
            
            return fallback_response, error_metadata
            
        except Exception as e:
            logger.error(f"Error in bedrock error handler: {e}")
            return self.fallback_responses["general_error"], {
                "error_type": "error_handler_failure",
                "original_error": str(error),
                "handler_error": str(e)
            }

    def handle_agent_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle agent-related errors with fallback strategies.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Tuple of (fallback_response, error_metadata)
        """
        try:
            self.error_stats["total_errors"] += 1
            self.error_stats["agent_errors"] += 1
            self.error_stats["last_error_time"] = datetime.utcnow().isoformat()
            
            context = context or {}
            
            logger.error(f"Agent error: {error}", extra={"context": context})
            
            if isinstance(error, AgentDiscoveryError):
                agent_id = getattr(error, 'agent_id', 'unknown')
                fallback_response = f"The agent '{agent_id}' is currently unavailable. I'll try to help you with a general response instead."
                error_metadata = {
                    "error_type": "agent_discovery_error",
                    "agent_id": agent_id,
                    "fallback_strategy": "model_fallback",
                    "can_retry": True
                }
            else:
                fallback_response = self.fallback_responses["agent_unavailable"]
                error_metadata = {
                    "error_type": "agent_generic_error",
                    "error_message": str(error),
                    "fallback_strategy": "model_fallback",
                    "can_retry": True
                }
            
            self.error_stats["fallback_activations"] += 1
            
            return fallback_response, error_metadata
            
        except Exception as e:
            logger.error(f"Error in agent error handler: {e}")
            return self.fallback_responses["general_error"], {
                "error_type": "error_handler_failure",
                "original_error": str(error),
                "handler_error": str(e)
            }

    def handle_session_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle session management errors.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Tuple of (fallback_response, error_metadata)
        """
        try:
            self.error_stats["total_errors"] += 1
            self.error_stats["session_errors"] += 1
            self.error_stats["last_error_time"] = datetime.utcnow().isoformat()
            
            context = context or {}
            
            logger.error(f"Session error: {error}", extra={"context": context})
            
            if isinstance(error, SessionManagementError):
                session_id = getattr(error, 'session_id', 'unknown')
                fallback_response = "There was an issue with your session. I'll continue without session history."
                error_metadata = {
                    "error_type": "session_management_error",
                    "session_id": session_id,
                    "fallback_strategy": "stateless_mode",
                    "can_retry": False
                }
            else:
                fallback_response = self.fallback_responses["session_error"]
                error_metadata = {
                    "error_type": "session_generic_error",
                    "error_message": str(error),
                    "fallback_strategy": "stateless_mode",
                    "can_retry": False
                }
            
            return fallback_response, error_metadata
            
        except Exception as e:
            logger.error(f"Error in session error handler: {e}")
            return self.fallback_responses["general_error"], {
                "error_type": "error_handler_failure",
                "original_error": str(error),
                "handler_error": str(e)
            }

    def handle_configuration_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle configuration errors.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Tuple of (fallback_response, error_metadata)
        """
        try:
            self.error_stats["total_errors"] += 1
            self.error_stats["config_errors"] += 1
            self.error_stats["last_error_time"] = datetime.utcnow().isoformat()
            
            context = context or {}
            
            logger.error(f"Configuration error: {error}", extra={"context": context})
            
            if isinstance(error, ConfigurationError):
                config_key = getattr(error, 'config_key', 'unknown')
                fallback_response = f"There's a configuration issue that's affecting functionality. Using default settings where possible."
                error_metadata = {
                    "error_type": "configuration_error",
                    "config_key": config_key,
                    "fallback_strategy": "default_config",
                    "can_retry": False
                }
            else:
                fallback_response = self.fallback_responses["config_error"]
                error_metadata = {
                    "error_type": "config_generic_error",
                    "error_message": str(error),
                    "fallback_strategy": "default_config",
                    "can_retry": False
                }
            
            return fallback_response, error_metadata
            
        except Exception as e:
            logger.error(f"Error in configuration error handler: {e}")
            return self.fallback_responses["general_error"], {
                "error_type": "error_handler_failure",
                "original_error": str(error),
                "handler_error": str(e)
            }

    def handle_generic_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle generic errors with basic fallback.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Tuple of (fallback_response, error_metadata)
        """
        try:
            self.error_stats["total_errors"] += 1
            self.error_stats["last_error_time"] = datetime.utcnow().isoformat()
            
            context = context or {}
            
            logger.error(f"Generic error: {error}", extra={"context": context})
            logger.debug(f"Error traceback: {traceback.format_exc()}")
            
            # Check if it's a known COA exception
            if isinstance(error, COABaseException):
                fallback_response = f"I encountered an issue: {error.message}"
                error_metadata = error.to_dict()
                error_metadata.update({
                    "fallback_strategy": "coa_exception_message",
                    "can_retry": True
                })
            else:
                fallback_response = self.fallback_responses["general_error"]
                error_metadata = {
                    "error_type": "generic_error",
                    "error_message": str(error),
                    "error_class": error.__class__.__name__,
                    "fallback_strategy": "static_response",
                    "can_retry": True
                }
            
            return fallback_response, error_metadata
            
        except Exception as e:
            logger.error(f"Error in generic error handler: {e}")
            return "I'm experiencing technical difficulties. Please try again later.", {
                "error_type": "critical_error_handler_failure",
                "original_error": str(error),
                "handler_error": str(e)
            }

    def _get_model_fallback_response(self, context: Dict[str, Any]) -> str:
        """Get fallback response for model errors."""
        query = context.get("query", "")
        
        if len(query) < 50:
            return "I'm having trouble processing your request right now. Could you try rephrasing your question?"
        else:
            return "I'm experiencing technical difficulties with the AI model. Please try a simpler question or try again in a moment."

    def _get_agent_fallback_response(self, context: Dict[str, Any]) -> str:
        """Get fallback response for agent errors."""
        agent_id = context.get("agent_id", "the requested agent")
        
        return f"I'm unable to connect to {agent_id} right now. I'll try to help you with a general response instead."

    def create_user_friendly_message(self, error_metadata: Dict[str, Any]) -> str:
        """
        Create a user-friendly error message from error metadata.
        
        Args:
            error_metadata: Error metadata dictionary
            
        Returns:
            User-friendly error message
        """
        try:
            error_type = error_metadata.get("error_type", "unknown")
            can_retry = error_metadata.get("can_retry", False)
            
            base_messages = {
                "model_communication_error": "I'm having trouble with the AI model right now.",
                "agent_communication_error": "The specialized agent is currently unavailable.",
                "agent_discovery_error": "I couldn't find the requested agent.",
                "session_management_error": "There's an issue with your conversation session.",
                "configuration_error": "There's a system configuration issue.",
                "bedrock_communication_error": "I'm having trouble connecting to AWS services.",
                "generic_error": "I encountered an unexpected issue."
            }
            
            message = base_messages.get(error_type, "I encountered an issue.")
            
            if can_retry:
                message += " Please try again in a moment."
            else:
                message += " I'll continue with limited functionality."
            
            return message
            
        except Exception as e:
            logger.error(f"Error creating user-friendly message: {e}")
            return "I encountered a technical issue. Please try again."

    def should_retry_operation(self, error_metadata: Dict[str, Any], attempt_count: int = 1) -> bool:
        """
        Determine if an operation should be retried based on error metadata.
        
        Args:
            error_metadata: Error metadata dictionary
            attempt_count: Current attempt count
            
        Returns:
            True if operation should be retried
        """
        try:
            # Don't retry if explicitly marked as non-retryable
            if not error_metadata.get("can_retry", False):
                return False
            
            # Don't retry after too many attempts
            if attempt_count >= 3:
                return False
            
            # Retry for specific error types
            retryable_errors = [
                "model_communication_error",
                "agent_communication_error",
                "bedrock_communication_error"
            ]
            
            error_type = error_metadata.get("error_type", "")
            return error_type in retryable_errors
            
        except Exception as e:
            logger.error(f"Error determining retry strategy: {e}")
            return False

    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get error handling statistics.
        
        Returns:
            Dictionary with error statistics
        """
        return {
            **self.error_stats,
            "error_rate": self._calculate_error_rate(),
            "most_common_errors": self._get_most_common_errors(),
            "fallback_success_rate": self._calculate_fallback_success_rate()
        }

    def _calculate_error_rate(self) -> float:
        """Calculate error rate (placeholder implementation)."""
        # This would be enhanced with actual request tracking
        total_requests = max(self.error_stats["total_errors"] * 10, 1)  # Estimate
        return (self.error_stats["total_errors"] / total_requests) * 100

    def _get_most_common_errors(self) -> List[Dict[str, Any]]:
        """Get most common error types."""
        error_counts = [
            {"type": "bedrock_errors", "count": self.error_stats["bedrock_errors"]},
            {"type": "agent_errors", "count": self.error_stats["agent_errors"]},
            {"type": "session_errors", "count": self.error_stats["session_errors"]},
            {"type": "config_errors", "count": self.error_stats["config_errors"]}
        ]
        
        return sorted(error_counts, key=lambda x: x["count"], reverse=True)

    def _calculate_fallback_success_rate(self) -> float:
        """Calculate fallback success rate."""
        if self.error_stats["total_errors"] == 0:
            return 100.0
        
        return (self.error_stats["fallback_activations"] / self.error_stats["total_errors"]) * 100

    def reset_stats(self) -> None:
        """Reset error statistics."""
        self.error_stats = {
            "total_errors": 0,
            "bedrock_errors": 0,
            "agent_errors": 0,
            "session_errors": 0,
            "config_errors": 0,
            "fallback_activations": 0,
            "last_error_time": None
        }
        logger.info("Error statistics reset")