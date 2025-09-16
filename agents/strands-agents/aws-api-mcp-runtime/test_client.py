"""
Local testing client for AWS API MCP Server

This client tests the MCP server running locally before deployment.
"""

import asyncio
from datetime import timedelta
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_local_server():
    """Test the locally running MCP server"""
    mcp_url = "http://localhost:8000/mcp"
    headers = {}

    print("🔄 Connecting to local MCP server...")
    print(f"URL: {mcp_url}")

    try:
        async with streamablehttp_client(
            mcp_url, 
            headers, 
            timeout=timedelta(seconds=120), 
            terminate_on_close=False
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("✓ Connected to MCP server")
                
                # Initialize session
                await session.initialize()
                print("✓ Session initialized")
                
                # List available tools
                print("\n📋 Listing available tools...")
                tool_result = await session.list_tools()
                
                print(f"\n🔧 Available AWS API MCP Tools ({len(tool_result.tools)} total):")
                print("=" * 60)
                for tool in tool_result.tools:
                    print(f"• {tool.name}")
                    print(f"  Description: {tool.description}")
                    print()
                
                # Test some tools
                print("🧪 Testing AWS API MCP Tools:")
                print("=" * 60)
                
                # Test caller identity
                try:
                    print("\n🔍 Testing get_caller_identity()...")
                    identity_result = await session.call_tool(
                        name="get_caller_identity",
                        arguments={}
                    )
                    print(f"Result: {identity_result.content[0].text}")
                except Exception as e:
                    print(f"Error: {e}")
                
                # Test AWS regions
                try:
                    print("\n🌍 Testing get_aws_regions()...")
                    regions_result = await session.call_tool(
                        name="get_aws_regions",
                        arguments={}
                    )
                    print(f"Result: {regions_result.content[0].text}")
                except Exception as e:
                    print(f"Error: {e}")
                
                # Test command suggestions
                try:
                    print("\n💡 Testing suggest_aws_commands('list ec2 instances')...")
                    suggest_result = await session.call_tool(
                        name="suggest_aws_commands",
                        arguments={"query": "list ec2 instances"}
                    )
                    print(f"Result: {suggest_result.content[0].text}")
                except Exception as e:
                    print(f"Error: {e}")
                
                # Test direct AWS command
                try:
                    print("\n⚡ Testing call_aws('aws sts get-caller-identity')...")
                    aws_result = await session.call_tool(
                        name="call_aws",
                        arguments={"cli_command": "aws sts get-caller-identity"}
                    )
                    print(f"Result: {aws_result.content[0].text}")
                except Exception as e:
                    print(f"Error: {e}")
                
                print("\n✅ Local testing completed!")
                
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        print("\nMake sure the MCP server is running locally:")
        print("python mcp_server.py")

if __name__ == "__main__":
    print("AWS API MCP Server - Local Testing Client")
    print("=" * 50)
    asyncio.run(test_local_server())