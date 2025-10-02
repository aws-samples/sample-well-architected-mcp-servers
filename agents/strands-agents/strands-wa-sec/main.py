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
   - Maintain context and coordinate multi-step security and cost assessments

3. Decision Protocol:
   - If query involves security, compliance, encryption, vulnerabilities, or security services -> AWS Security Assessment Agent

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