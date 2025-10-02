"""

"""

from aws_api_agent import aws_api_agent
from strands import Agent
from strands.models import BedrockModel
from strands_tools import think
from bedrock_agentcore.runtime import BedrockAgentCoreApp


app = BedrockAgentCoreApp()

bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")

SUPERVISOR_AGENT_PROMPT = """You are Router Agent, a sophisticated orchestrator designed to coordinate support across AWS operations. Your role is to:

1. Analyze the user's request and determine the appropriate tool to use.
2. Execute the selected tool and provide the results.
3. Provide a summary of the results to the user.

The available tools are:
- aws_api_agent: To get the suggest aws command, and to call aws api.
- think: Provides a thought to the user.

You will use the tools in the following order:
1. If the user's request is related to AWS API, use the aws_api_agent tool.
2. If the user's request is not related to direct AWS API call, use the think tool.

Begin by analyzing the user's request and selecting the appropriate tool.
"""

supervisor_agent = Agent(
    system_prompt=SUPERVISOR_AGENT_PROMPT,
    model = bedrock_model,
    # stream_handler=None,
    tools=[aws_api_agent, think],
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