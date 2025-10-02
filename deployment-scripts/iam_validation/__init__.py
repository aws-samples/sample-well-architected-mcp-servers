"""
IAM Validation and CloudFormation Template Update Module

This module provides functionality to validate IAM policies and update
CloudFormation templates for Bedrock AgentCore integration.
"""

from .data_models import ValidationResult, UpdateResult, IntegrationResult
from .config import CONFIG
from .orchestrator import BedrockAgentCoreIntegrator

__all__ = [
    'ValidationResult',
    'UpdateResult', 
    'IntegrationResult',
    'CONFIG',
    'BedrockAgentCoreIntegrator'
]