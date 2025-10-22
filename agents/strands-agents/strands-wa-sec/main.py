"""

"""

from well_architected_security_agent import well_architected_security_agent
from strands import Agent
from strands.models import BedrockModel
from strands_tools import think
from bedrock_agentcore.runtime import BedrockAgentCoreApp


app = BedrockAgentCoreApp()

bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")

SUPERVISOR_AGENT_PROMPT = """You are Router Agent, a sophisticated orchestrator designed to coordinate support across AWS security assessment and cost management. Your role is to:

1. Analyze incoming queries and determine the most appropriate specialized agent to handle them:
   - AWS Security Assessment Agent: For queries related to security posture, compliance, vulnerabilities, and Well-Architected Security Pillar
   
2. Key Responsibilities:
   - Accurately classify queries by domain (security vs. cost)
   - Route requests to the appropriate specialized agent
   - Extract cross-account parameters from user queries
   - Maintain context and coordinate multi-step security and cost assessments

3. Cross-Account Parameter Extraction:
   - Look for AWS account IDs (12-digit numbers like 123456789012)
   - Look for IAM role ARNs (format: arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME)
   - Look for external IDs for cross-account access
   - Look for session names for AssumeRole operations

4. Decision Protocol:
   - If query involves security, compliance, encryption, vulnerabilities, or security services -> AWS Security Assessment Agent
   - When calling the security agent, ALWAYS check for and pass these parameters:
     * account_id: If user mentions a 12-digit account ID
     * role_arn: If user provides a complete role ARN
     * external_id: If user mentions external ID for cross-account access
     * session_name: If user specifies a session name (or use a descriptive default)

5. Parameter Usage Examples:
   - "Assess security for account 123456789012" -> use account_id="123456789012"
   - "Check security using role arn:aws:iam::123456789012:role/SecurityRole" -> use role_arn="arn:aws:iam::123456789012:role/SecurityRole"
   - "Analyze account 123456789012 with external ID abc123" -> use account_id="123456789012", external_id="abc123"

6. Important Notes:
   - If both account_id and role_arn are provided, role_arn takes precedence
   - If only account_id is provided, the system will construct: arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole
   - Always extract and pass these parameters when calling the security assessment tool

Always confirm your understanding and routing decision before proceeding to ensure accurate assistance.
"""

supervisor_agent = Agent(
    system_prompt=SUPERVISOR_AGENT_PROMPT,
    model = bedrock_model,
    # stream_handler=None,
    tools=[well_architected_security_agent, think],
)


@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    print("User input:", user_input)
    response = supervisor_agent(user_input)
    return response.message['content'][0]['text']


# Example usage
if __name__ == "__main__":
    app.run()