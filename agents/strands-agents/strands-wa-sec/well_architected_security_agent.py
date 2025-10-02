import os
import boto3
from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

@tool
def well_architected_security_agent(query: str, env=None, role_arn=None) -> str:
    """
    Process and respond AWS cost related queries.

    Args:
        query: The user's question

    Returns:
        A helpful response addressing user query
    """

    bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")


    response = str()
    print("debug",query,env,role_arn)
    sts_client = boto3.client('sts')
    print(sts_client.get_caller_identity())
    try:
        if env is None:
            env = {}
        if role_arn is not None:
            # Create a boto3 session with the specified role            
            sts_client = boto3.client('sts')
            assumed_role_object = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="AssumedRoleSession"
            )
            credentials = assumed_role_object['Credentials']
            env["AWS_ACCESS_KEY_ID"] = credentials['AccessKeyId']
            env["AWS_SECRET_ACCESS_KEY"] = credentials['SecretAccessKey']
            env["AWS_SESSION_TOKEN"] = credentials['SessionToken']                  
        else:
            env["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID")
            env["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY")     

        if os.getenv("AWS_REGION") is not None:
            env["AWS_REGION"] = os.getenv("AWS_REGION")
        if os.getenv("BEDROCK_LOG_GROUP_NAME") is not None:
            env["BEDROCK_LOG_GROUP_NAME"] = os.getenv("BEDROCK_LOG_GROUP_NAME")
        print("debug",env)
        mcp_server = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="awslabs.well-architected-security-mcp-server",
                    args=[],
                    env=env,
                )
            )
        )

        with mcp_server:

            tools = mcp_server.list_tools_sync()
            # Create the research agent with specific capabilities
            mcp_agent = Agent(
                model=bedrock_model,
                system_prompt="""You are an AWS Security Assessment Assistant with access to comprehensive security analysis tools through the well_architected_security_mcp_server.

## Core Capabilities
- Assess AWS security posture across multiple services and regions
- Identify security misconfigurations and compliance gaps
- Analyze encryption status for data at rest and in transit
- Evaluate security service enablement (GuardDuty, Security Hub, Inspector, etc.)
- Provide Well-Architected Framework Security Pillar recommendations

## Tool Usage Guidelines
1. **Security Overview**: Use CheckSecurityServices to assess overall security service status
2. **Encryption Analysis**: Use CheckStorageEncryption for data-at-rest protection
3. **Network Security**: Use CheckNetworkSecurity for data-in-transit protection
4. **Findings Review**: Use GetSecurityFindings to retrieve specific security issues
5. **Service Discovery**: Use ListServicesInRegion to identify resources in scope

## Assessment Workflow
1. Start with CheckSecurityServices for baseline security posture
2. Follow with encryption and network security checks
3. Retrieve specific findings from enabled security services
4. Prioritize findings by severity and business impact

## Response Format
- Lead with security risk level (Critical/High/Medium/Low)
- Summarize compliance status and key gaps
- Provide prioritized remediation steps with effort estimates
- Include specific resource ARNs and configuration details
- Reference relevant AWS security best practices and compliance frameworks

## Security Focus Areas
- Identity and Access Management (IAM)
- Data protection (encryption at rest/in transit)
- Infrastructure protection (network security, VPC configuration)
- Detective controls (logging, monitoring, alerting)
- Incident response preparedness

When users ask about AWS security assessments, compliance, or security posture, use the available MCP tools to provide comprehensive security analysis with specific, actionable remediation guidance prioritized by risk level.

""",
                tools=tools,
            )
            response = str(mcp_agent(query))
            print("\n\n")

        if len(response) > 0:
            return response

        return "I apologize, but I couldn't properly analyze your question. Could you please rephrase or provide more context?"

    except Exception as e:
        print(e)
        return f"Error processing your query: {str(e)}"



if __name__ == "__main__":
    well_architected_security_agent("Get my guardduty findings", role_arn="arn:aws:iam::384612698411:role/cloud-optimization-assistant-bedrock-agentcore-runtime-role")