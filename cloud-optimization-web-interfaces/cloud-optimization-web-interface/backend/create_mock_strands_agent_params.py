#!/usr/bin/env python3
"""
Create mock SSM parameters for StrandsAgent testing
This simulates a deployed StrandsAgent in SSM Parameter Store
"""

import json
import boto3
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mock_strands_agent_params():
    """Create mock SSM parameters for StrandsAgent testing"""
    
    try:
        ssm_client = boto3.client("ssm")
        
        # Mock agent configuration
        agent_type = "strands_aws_wa_sec_cost"
        
        # Create mock agent ARN (using bedrock-agentcore format to trigger real mode)
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        region = "us-east-1"
        mock_agent_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/aws_wa_sec_cost_agent-MOCK123456"
        mock_agent_id = "MOCK123456"
        mock_endpoint_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/aws_wa_sec_cost_agent-MOCK123456"
        
        # Agent metadata
        metadata = {
            "deployment_id": f"deploy-strands-{agent_type}-mock",
            "status": "DEPLOYED",
            "deployed_at": datetime.utcnow().isoformat(),
            "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "embedded_mcp_packages": {
                "wa_security_mcp": "awslabs.well-architected-security-mcp-server@latest",
                "billing_cost_mcp": "awslabs.billing-cost-management-mcp-server@latest"
            },
            "framework": "strands",
            "agent_type": "dual_domain_specialist",
            "capabilities": [
                "aws_security_assessment",
                "well_architected_security_pillar",
                "security_service_analysis",
                "encryption_assessment",
                "network_security_analysis",
                "security_findings_analysis",
                "compliance_evaluation",
                "cost_analysis",
                "billing_optimization",
                "cost_forecasting",
                "rightsizing_recommendations",
                "reserved_instance_analysis",
                "savings_plan_optimization",
                "cost_anomaly_detection",
                "multi_account_cost_analysis",
                "cross_domain_analysis",
                "security_cost_correlation",
                "optimization_prioritization",
            ],
            "domains": {
                "security": {
                    "embedded_mcp_package": "awslabs.well-architected-security-mcp-server@latest",
                    "capabilities": [
                        "security_service_enablement",
                        "encryption_at_rest",
                        "encryption_in_transit",
                        "network_security",
                        "security_findings",
                        "compliance_assessment",
                        "well_architected_security"
                    ]
                },
                "cost_optimization": {
                    "embedded_mcp_package": "awslabs.billing-cost-management-mcp-server@latest",
                    "capabilities": [
                        "cost_analysis",
                        "usage_analysis",
                        "cost_forecasting",
                        "rightsizing",
                        "reserved_instances",
                        "savings_plans",
                        "cost_anomalies",
                        "billing_optimization"
                    ]
                }
            },
        }
        
        # Parameters to create
        parameters = [
            {
                "Name": f"/coa/agents/{agent_type}/agent_arn",
                "Value": mock_agent_arn,
                "Type": "String",
                "Description": "Mock ARN of the StrandsAgent for testing"
            },
            {
                "Name": f"/coa/agents/{agent_type}/endpoint_url",
                "Value": mock_endpoint_url,
                "Type": "String",
                "Description": "Mock endpoint URL for the StrandsAgent"
            },
            {
                "Name": f"/coa/agents/{agent_type}/agent_id",
                "Value": mock_agent_id,
                "Type": "String",
                "Description": "Mock Agent ID for the StrandsAgent"
            },
            {
                "Name": f"/coa/agents/{agent_type}/agent_alias_id",
                "Value": mock_agent_id,
                "Type": "String",
                "Description": "Mock Agent Alias ID for the StrandsAgent"
            },
            {
                "Name": f"/coa/agents/{agent_type}/metadata",
                "Value": json.dumps(metadata),
                "Type": "String",
                "Description": "Mock metadata for the StrandsAgent deployment"
            },
            {
                "Name": f"/coa/agents/{agent_type}/health_check_url",
                "Value": f"{mock_endpoint_url}/health",
                "Type": "String",
                "Description": "Mock health check URL for the StrandsAgent"
            }
        ]
        
        # Create parameters
        for param in parameters:
            try:
                ssm_client.put_parameter(
                    Name=param["Name"],
                    Value=param["Value"],
                    Type=param["Type"],
                    Description=param["Description"],
                    Overwrite=True
                )
                logger.info(f"✅ Created parameter: {param['Name']}")
            except Exception as e:
                logger.error(f"❌ Failed to create parameter {param['Name']}: {e}")
        
        logger.info(f"🎉 Mock StrandsAgent parameters created successfully!")
        logger.info(f"Agent Type: {agent_type}")
        logger.info(f"Agent ARN: {mock_agent_arn}")
        logger.info(f"Agent ID: {mock_agent_id}")
        logger.info(f"Framework: strands")
        
        logger.info("\n📋 To test with real AgentCore mode:")
        logger.info("export FORCE_REAL_AGENTCORE=true")
        logger.info("./start_coa.sh")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create mock parameters: {e}")
        return False

def cleanup_mock_params():
    """Clean up mock SSM parameters"""
    try:
        ssm_client = boto3.client("ssm")
        agent_type = "strands_aws_wa_sec_cost"
        
        parameters_to_delete = [
            f"/coa/agents/{agent_type}/agent_arn",
            f"/coa/agents/{agent_type}/endpoint_url", 
            f"/coa/agents/{agent_type}/agent_id",
            f"/coa/agents/{agent_type}/agent_alias_id",
            f"/coa/agents/{agent_type}/metadata",
            f"/coa/agents/{agent_type}/health_check_url"
        ]
        
        for param_name in parameters_to_delete:
            try:
                ssm_client.delete_parameter(Name=param_name)
                logger.info(f"🗑️ Deleted parameter: {param_name}")
            except ssm_client.exceptions.ParameterNotFound:
                logger.info(f"⚠️ Parameter not found: {param_name}")
            except Exception as e:
                logger.error(f"❌ Failed to delete parameter {param_name}: {e}")
        
        logger.info("🧹 Mock parameter cleanup completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage mock StrandsAgent SSM parameters")
    parser.add_argument("--cleanup", action="store_true", help="Clean up mock parameters")
    
    args = parser.parse_args()
    
    if args.cleanup:
        success = cleanup_mock_params()
    else:
        success = create_mock_strands_agent_params()
    
    exit(0 if success else 1)