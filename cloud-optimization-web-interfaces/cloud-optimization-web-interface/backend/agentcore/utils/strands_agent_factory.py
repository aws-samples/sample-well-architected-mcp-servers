"""
Strands Agent Factory - Creates and configures Strands agents for AgentCore integration.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from agentcore.models.strands_models import (
    StrandsAgent,
    StrandsAgentType,
    StrandsAgentStatus,
    StrandsRuntimeType,
    StrandsAgentCapability,
    create_wa_security_agent,
    create_cost_optimization_agent,
    create_aws_api_agent
)

logger = logging.getLogger(__name__)


class StrandsAgentFactory:
    """Factory for creating and configuring Strands agents."""
    
    def __init__(self, parameter_prefix: str = "coa"):
        """
        Initialize the Strands agent factory.
        
        Args:
            parameter_prefix: Parameter prefix for agent configuration
        """
        self.parameter_prefix = parameter_prefix
        self.agent_templates = self._load_agent_templates()
    
    def create_agent_from_config(
        self,
        agent_config: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> StrandsAgent:
        """
        Create a Strands agent from configuration.
        
        Args:
            agent_config: Agent configuration dictionary
            agent_id: Optional agent ID override
            
        Returns:
            Configured StrandsAgent instance
        """
        agent_type_str = agent_config.get("agent_type", "general_purpose_agent")
        agent_type = StrandsAgentType(agent_type_str)
        
        # Generate agent ID if not provided
        if not agent_id:
            agent_id = self._generate_agent_id(agent_type)
        
        agent_name = agent_config.get("agent_name", f"{agent_type.value}_{agent_id}")
        agent_arn = agent_config.get("agent_arn", f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{agent_id}")
        
        # Use factory functions for known agent types
        if agent_type == StrandsAgentType.WA_SECURITY:
            agent = create_wa_security_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                endpoint_url=agent_config.get("endpoint_url")
            )
        elif agent_type == StrandsAgentType.COST_OPTIMIZATION:
            agent = create_cost_optimization_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                endpoint_url=agent_config.get("endpoint_url")
            )
        elif agent_type == StrandsAgentType.AWS_API:
            agent = create_aws_api_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                endpoint_url=agent_config.get("endpoint_url")
            )
        else:
            # Create generic agent
            agent = self._create_generic_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                agent_config=agent_config
            )
        
        # Apply additional configuration
        self._apply_agent_config(agent, agent_config)
        
        logger.info(f"Created Strands agent: {agent.agent_name} ({agent.agent_type.value})\")\n        return agent\n    \n    def create_agent_from_template(\n        self,\n        template_name: str,\n        agent_id: Optional[str] = None,\n        overrides: Optional[Dict[str, Any]] = None\n    ) -> StrandsAgent:\n        \"\"\"\n        Create a Strands agent from a predefined template.\n        \n        Args:\n            template_name: Name of the agent template\n            agent_id: Optional agent ID override\n            overrides: Optional configuration overrides\n            \n        Returns:\n            Configured StrandsAgent instance\n        \"\"\"\n        if template_name not in self.agent_templates:\n            raise ValueError(f\"Unknown agent template: {template_name}\")\n        \n        template_config = self.agent_templates[template_name].copy()\n        \n        # Apply overrides\n        if overrides:\n            template_config.update(overrides)\n        \n        return self.create_agent_from_config(template_config, agent_id)\n    \n    def create_multi_capability_agent(\n        self,\n        agent_id: str,\n        agent_name: str,\n        capabilities: List[StrandsAgentCapability],\n        agent_arn: Optional[str] = None,\n        metadata: Optional[Dict[str, Any]] = None\n    ) -> StrandsAgent:\n        \"\"\"\n        Create a Strands agent with multiple capabilities.\n        \n        Args:\n            agent_id: Agent ID\n            agent_name: Agent name\n            capabilities: List of agent capabilities\n            agent_arn: Optional agent ARN\n            metadata: Optional metadata\n            \n        Returns:\n            Configured StrandsAgent instance\n        \"\"\"\n        if not agent_arn:\n            agent_arn = f\"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{agent_id}\"\n        \n        # Determine agent type based on capabilities\n        agent_type = self._determine_agent_type_from_capabilities(capabilities)\n        \n        agent = StrandsAgent(\n            agent_id=agent_id,\n            agent_name=agent_name,\n            agent_arn=agent_arn,\n            agent_type=agent_type,\n            capabilities=capabilities,\n            metadata=metadata or {}\n        )\n        \n        # Set supported domains and services based on capabilities\n        self._configure_agent_from_capabilities(agent)\n        \n        logger.info(f\"Created multi-capability Strands agent: {agent_name} with {len(capabilities)} capabilities\")\n        return agent\n    \n    def clone_agent(\n        self,\n        source_agent: StrandsAgent,\n        new_agent_id: str,\n        new_agent_name: Optional[str] = None,\n        modifications: Optional[Dict[str, Any]] = None\n    ) -> StrandsAgent:\n        \"\"\"\n        Clone an existing Strands agent with modifications.\n        \n        Args:\n            source_agent: Source agent to clone\n            new_agent_id: New agent ID\n            new_agent_name: Optional new agent name\n            modifications: Optional modifications to apply\n            \n        Returns:\n            Cloned and modified StrandsAgent instance\n        \"\"\"\n        if not new_agent_name:\n            new_agent_name = f\"{source_agent.agent_name}_clone\"\n        \n        # Create new agent with copied attributes\n        cloned_agent = StrandsAgent(\n            agent_id=new_agent_id,\n            agent_name=new_agent_name,\n            agent_arn=f\"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{new_agent_id}\",\n            agent_type=source_agent.agent_type,\n            runtime_type=source_agent.runtime_type,\n            status=StrandsAgentStatus.DISCOVERED,  # Reset status\n            capabilities=source_agent.capabilities.copy(),\n            metadata=source_agent.metadata.copy(),\n            framework=source_agent.framework,\n            model_id=source_agent.model_id,\n            supported_domains=source_agent.supported_domains.copy(),\n            supported_aws_services=source_agent.supported_aws_services.copy()\n        )\n        \n        # Apply modifications\n        if modifications:\n            self._apply_agent_config(cloned_agent, modifications)\n        \n        logger.info(f\"Cloned Strands agent: {new_agent_name} from {source_agent.agent_name}\")\n        return cloned_agent\n    \n    def _generate_agent_id(self, agent_type: StrandsAgentType) -> str:\n        \"\"\"\n        Generate a unique agent ID.\n        \n        Args:\n            agent_type: Type of agent\n            \n        Returns:\n            Generated agent ID\n        \"\"\"\n        import uuid\n        timestamp = datetime.utcnow().strftime(\"%Y%m%d%H%M%S\")\n        short_uuid = str(uuid.uuid4())[:8]\n        return f\"{agent_type.value}_{timestamp}_{short_uuid}\"\n    \n    def _create_generic_agent(\n        self,\n        agent_id: str,\n        agent_name: str,\n        agent_arn: str,\n        agent_config: Dict[str, Any]\n    ) -> StrandsAgent:\n        \"\"\"\n        Create a generic Strands agent.\n        \n        Args:\n            agent_id: Agent ID\n            agent_name: Agent name\n            agent_arn: Agent ARN\n            agent_config: Agent configuration\n            \n        Returns:\n            Generic StrandsAgent instance\n        \"\"\"\n        capabilities = []\n        \n        # Create capabilities from config\n        capability_configs = agent_config.get(\"capabilities\", [])\n        for cap_config in capability_configs:\n            capability = StrandsAgentCapability(\n                name=cap_config.get(\"name\", \"general_capability\"),\n                description=cap_config.get(\"description\", \"General purpose capability\"),\n                aws_services=cap_config.get(\"aws_services\", []),\n                domains=cap_config.get(\"domains\", [\"general\"]),\n                keywords=cap_config.get(\"keywords\", []),\n                confidence_level=cap_config.get(\"confidence_level\", 1.0)\n            )\n            capabilities.append(capability)\n        \n        agent = StrandsAgent(\n            agent_id=agent_id,\n            agent_name=agent_name,\n            agent_arn=agent_arn,\n            agent_type=StrandsAgentType.GENERAL_PURPOSE,\n            capabilities=capabilities,\n            endpoint_url=agent_config.get(\"endpoint_url\"),\n            supported_domains=agent_config.get(\"supported_domains\", [\"general\"]),\n            supported_aws_services=agent_config.get(\"supported_aws_services\", [])\n        )\n        \n        return agent\n    \n    def _apply_agent_config(\n        self,\n        agent: StrandsAgent,\n        config: Dict[str, Any]\n    ):\n        \"\"\"\n        Apply configuration to an agent.\n        \n        Args:\n            agent: Agent to configure\n            config: Configuration to apply\n        \"\"\"\n        # Update metadata\n        if \"metadata\" in config:\n            agent.metadata.update(config[\"metadata\"])\n        \n        # Update model ID\n        if \"model_id\" in config:\n            agent.model_id = config[\"model_id\"]\n        \n        # Update status\n        if \"status\" in config:\n            agent.status = StrandsAgentStatus(config[\"status\"])\n        \n        # Update runtime type\n        if \"runtime_type\" in config:\n            agent.runtime_type = StrandsRuntimeType(config[\"runtime_type\"])\n        \n        # Update health check URL\n        if \"health_check_url\" in config:\n            agent.health_check_url = config[\"health_check_url\"]\n        \n        # Update supported domains and services\n        if \"supported_domains\" in config:\n            agent.supported_domains = config[\"supported_domains\"]\n        \n        if \"supported_aws_services\" in config:\n            agent.supported_aws_services = config[\"supported_aws_services\"]\n    \n    def _determine_agent_type_from_capabilities(\n        self,\n        capabilities: List[StrandsAgentCapability]\n    ) -> StrandsAgentType:\n        \"\"\"\n        Determine agent type based on capabilities.\n        \n        Args:\n            capabilities: List of capabilities\n            \n        Returns:\n            Determined agent type\n        \"\"\"\n        # Check for security-related capabilities\n        security_keywords = [\"security\", \"compliance\", \"vulnerability\", \"threat\"]\n        if any(\n            any(keyword in cap.keywords for keyword in security_keywords)\n            for cap in capabilities\n        ):\n            return StrandsAgentType.WA_SECURITY\n        \n        # Check for cost-related capabilities\n        cost_keywords = [\"cost\", \"billing\", \"optimization\", \"savings\"]\n        if any(\n            any(keyword in cap.keywords for keyword in cost_keywords)\n            for cap in capabilities\n        ):\n            return StrandsAgentType.COST_OPTIMIZATION\n        \n        # Check for API-related capabilities\n        api_keywords = [\"api\", \"list\", \"describe\", \"get\", \"create\"]\n        if any(\n            any(keyword in cap.keywords for keyword in api_keywords)\n            for cap in capabilities\n        ):\n            return StrandsAgentType.AWS_API\n        \n        return StrandsAgentType.GENERAL_PURPOSE\n    \n    def _configure_agent_from_capabilities(\n        self,\n        agent: StrandsAgent\n    ):\n        \"\"\"\n        Configure agent domains and services based on capabilities.\n        \n        Args:\n            agent: Agent to configure\n        \"\"\"\n        all_domains = set()\n        all_services = set()\n        \n        for capability in agent.capabilities:\n            all_domains.update(capability.domains)\n            all_services.update(capability.aws_services)\n        \n        agent.supported_domains = list(all_domains)\n        agent.supported_aws_services = list(all_services)\n    \n    def _load_agent_templates(self) -> Dict[str, Dict[str, Any]]:\n        \"\"\"\n        Load predefined agent templates.\n        \n        Returns:\n            Dictionary of agent templates\n        \"\"\"\n        return {\n            \"wa_security\": {\n                \"agent_type\": \"wa_security_agent\",\n                \"agent_name\": \"Well-Architected Security Agent\",\n                \"capabilities\": [\n                    {\n                        \"name\": \"security_assessment\",\n                        \"description\": \"AWS security posture assessment\",\n                        \"aws_services\": [\"guardduty\", \"inspector\", \"securityhub\"],\n                        \"domains\": [\"security\"],\n                        \"keywords\": [\"security\", \"vulnerability\", \"compliance\"]\n                    }\n                ],\n                \"supported_domains\": [\"security\", \"compliance\"],\n                \"supported_aws_services\": [\"guardduty\", \"inspector\", \"securityhub\", \"macie\"]\n            },\n            \"cost_optimization\": {\n                \"agent_type\": \"cost_optimization_agent\",\n                \"agent_name\": \"Cost Optimization Agent\",\n                \"capabilities\": [\n                    {\n                        \"name\": \"cost_analysis\",\n                        \"description\": \"AWS cost analysis and optimization\",\n                        \"aws_services\": [\"ce\", \"budgets\", \"compute-optimizer\"],\n                        \"domains\": [\"cost_optimization\"],\n                        \"keywords\": [\"cost\", \"billing\", \"optimization\"]\n                    }\n                ],\n                \"supported_domains\": [\"cost_optimization\"],\n                \"supported_aws_services\": [\"ce\", \"budgets\", \"compute-optimizer\"]\n            },\n            \"aws_api\": {\n                \"agent_type\": \"aws_api_agent\",\n                \"agent_name\": \"AWS API Agent\",\n                \"capabilities\": [\n                    {\n                        \"name\": \"aws_api_operations\",\n                        \"description\": \"AWS API operations and resource management\",\n                        \"aws_services\": [\"*\"],\n                        \"domains\": [\"general\"],\n                        \"keywords\": [\"list\", \"describe\", \"get\", \"api\"]\n                    }\n                ],\n                \"supported_domains\": [\"general\", \"operations\"],\n                \"supported_aws_services\": [\"*\"]\n            }\n        }\n    \n    def get_available_templates(self) -> List[str]:\n        \"\"\"\n        Get list of available agent templates.\n        \n        Returns:\n            List of template names\n        \"\"\"\n        return list(self.agent_templates.keys())\n    \n    def validate_agent_config(self, config: Dict[str, Any]) -> Dict[str, Any]:\n        \"\"\"\n        Validate agent configuration.\n        \n        Args:\n            config: Configuration to validate\n            \n        Returns:\n            Validation result with errors and warnings\n        \"\"\"\n        errors = []\n        warnings = []\n        \n        # Required fields\n        required_fields = [\"agent_type\"]\n        for field in required_fields:\n            if field not in config:\n                errors.append(f\"Missing required field: {field}\")\n        \n        # Validate agent type\n        if \"agent_type\" in config:\n            try:\n                StrandsAgentType(config[\"agent_type\"])\n            except ValueError:\n                errors.append(f\"Invalid agent_type: {config['agent_type']}\")\n        \n        # Validate capabilities\n        if \"capabilities\" in config:\n            if not isinstance(config[\"capabilities\"], list):\n                errors.append(\"capabilities must be a list\")\n            elif len(config[\"capabilities\"]) == 0:\n                warnings.append(\"Agent has no capabilities defined\")\n        \n        return {\n            \"valid\": len(errors) == 0,\n            \"errors\": errors,\n            \"warnings\": warnings\n        }\n\n\n# Convenience functions\n\ndef create_strands_agent_factory(parameter_prefix: str = \"coa\") -> StrandsAgentFactory:\n    \"\"\"\n    Create a Strands agent factory instance.\n    \n    Args:\n        parameter_prefix: Parameter prefix for agent configuration\n        \n    Returns:\n        StrandsAgentFactory instance\n    \"\"\"\n    return StrandsAgentFactory(parameter_prefix)\n\n\ndef create_agent_from_ssm_config(\n    ssm_parameter_path: str,\n    region: str = \"us-east-1\",\n    parameter_prefix: str = \"coa\"\n) -> Optional[StrandsAgent]:\n    \"\"\"\n    Create a Strands agent from SSM parameter configuration.\n    \n    Args:\n        ssm_parameter_path: SSM parameter path containing agent config\n        region: AWS region\n        parameter_prefix: Parameter prefix\n        \n    Returns:\n        StrandsAgent instance or None if creation fails\n    \"\"\"\n    try:\n        import boto3\n        import json\n        \n        ssm_client = boto3.client(\"ssm\", region_name=region)\n        response = ssm_client.get_parameter(Name=ssm_parameter_path)\n        \n        config = json.loads(response[\"Parameter\"][\"Value\"])\n        \n        factory = StrandsAgentFactory(parameter_prefix)\n        return factory.create_agent_from_config(config)\n        \n    except Exception as e:\n        logger.error(f\"Failed to create agent from SSM config {ssm_parameter_path}: {e}\")\n        return None