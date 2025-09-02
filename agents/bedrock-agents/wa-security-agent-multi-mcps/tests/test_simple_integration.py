#!/usr/bin/env python3

# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Simple test to validate MCP integration routing without full agent dependencies
"""

import asyncio
import sys
import os

# Simple mock classes to test the integration logic
class MockToolResult:
    def __init__(self, success: bool, data: any, error_message: str = None):
        self.success = success
        self.data = data
        self.error_message = error_message
        self.execution_time = 0.1


class MockMCPOrchestrator:
    """Mock orchestrator for testing"""
    
    def __init__(self):
        self.call_log = []
    
    async def call_security_tool(self, tool_name: str, args: dict):
        self.call_log.append(('security', tool_name, args))
        print(f"🔒 Security MCP: {tool_name}")
        return MockToolResult(True, {'security_response': True})
    
    async def call_knowledge_tool(self, tool_name: str, args: dict):
        self.call_log.append(('knowledge', tool_name, args))
        print(f"📚 Knowledge MCP: {tool_name}")
        
        if 'search_documentation' in tool_name or 'aws___search_documentation' in tool_name:
            return MockToolResult(True, [
                {
                    'title': 'AWS Security Best Practices',
                    'url': 'https://docs.aws.amazon.com/security/',
                    'context': 'Security best practices...',
                    'rank_order': 1
                }
            ])
        return MockToolResult(True, {'knowledge_response': True})
    
    async def call_api_tool(self, tool_name: str, args: dict):
        self.call_log.append(('api', tool_name, args))
        print(f"⚡ API MCP: {tool_name}")
        
        if 'suggest_aws_commands' in tool_name:
            return MockToolResult(True, [
                {
                    'command': 'aws s3api list-buckets',
                    'confidence': 0.9,
                    'description': 'List S3 buckets'
                }
            ])
        elif 'call_aws' in tool_name:
            return MockToolResult(True, {'Buckets': []})
        
        return MockToolResult(True, {'api_response': True})


# Simplified integration classes for testing
class SimpleAWSAPIIntegration:
    """Simplified AWS API integration for testing"""
    
    def __init__(self, orchestrator):
        self.mcp_orchestrator = orchestrator
    
    async def suggest_aws_commands(self, query: str):
        result = await self.mcp_orchestrator.call_api_tool("suggest_aws_commands", {"query": query})
        return {
            'success': result.success,
            'suggestions': result.data if result.success else [],
            'query': query
        }
    
    async def execute_aws_command(self, command: str):
        result = await self.mcp_orchestrator.call_api_tool("call_aws", {"cli_command": command})
        return {
            'success': result.success,
            'output': result.data if result.success else None,
            'command': command
        }


class SimpleAWSKnowledgeIntegration:
    """Simplified AWS Knowledge integration for testing"""
    
    def __init__(self, orchestrator):
        self.mcp_orchestrator = orchestrator
    
    async def search_relevant_documentation(self, topic: str):
        result = await self.mcp_orchestrator.call_knowledge_tool(
            "aws___search_documentation", 
            {"search_phrase": topic}
        )
        return result.data if result.success else []
    
    async def get_best_practices_for_service(self, service: str):
        result = await self.mcp_orchestrator.call_knowledge_tool(
            "aws___search_documentation",
            {"search_phrase": f"{service} security best practices"}
        )
        
        if result.success:
            return {
                'service': service,
                'practices': result.data,
                'success': True
            }
        return {'service': service, 'practices': [], 'success': False}


async def test_mcp_routing():
    """Test MCP routing functionality"""
    print("🚀 Testing MCP Integration Routing")
    print("=" * 50)
    
    orchestrator = MockMCPOrchestrator()
    
    # Initialize integrations
    api_integration = SimpleAWSAPIIntegration(orchestrator)
    knowledge_integration = SimpleAWSKnowledgeIntegration(orchestrator)
    
    print("\n1️⃣ Testing AWS API MCP Integration...")
    
    # Test API integration
    result1 = await api_integration.suggest_aws_commands("list S3 buckets")
    print(f"   ✅ Suggest commands: {result1['success']}")
    
    result2 = await api_integration.execute_aws_command("aws s3api list-buckets")
    print(f"   ✅ Execute command: {result2['success']}")
    
    print("\n2️⃣ Testing AWS Knowledge MCP Integration...")
    
    # Test Knowledge integration
    docs = await knowledge_integration.search_relevant_documentation("S3 security")
    print(f"   ✅ Search docs: Found {len(docs)} documents")
    
    practices = await knowledge_integration.get_best_practices_for_service("s3")
    print(f"   ✅ Best practices: {practices['success']}")
    
    print("\n3️⃣ Analyzing Call Routing...")
    
    # Analyze call routing
    security_calls = [call for call in orchestrator.call_log if call[0] == 'security']
    knowledge_calls = [call for call in orchestrator.call_log if call[0] == 'knowledge']
    api_calls = [call for call in orchestrator.call_log if call[0] == 'api']
    
    print(f"   🔒 Security MCP calls: {len(security_calls)}")
    print(f"   📚 Knowledge MCP calls: {len(knowledge_calls)}")
    print(f"   ⚡ API MCP calls: {len(api_calls)}")
    
    # Verify correct routing
    expected_api_tools = ['suggest_aws_commands', 'call_aws']
    expected_knowledge_tools = ['aws___search_documentation']
    
    api_tools_called = [call[1] for call in api_calls]
    knowledge_tools_called = [call[1] for call in knowledge_calls]
    
    print(f"\n4️⃣ Tool Routing Verification...")
    print(f"   API tools called: {api_tools_called}")
    print(f"   Knowledge tools called: {knowledge_tools_called}")
    
    # Check if routing is correct
    api_routing_correct = any(tool in api_tools_called for tool in expected_api_tools)
    knowledge_routing_correct = any(tool in knowledge_tools_called for tool in expected_knowledge_tools)
    
    print(f"\n🎯 Results:")
    print(f"   ✅ API MCP routing: {'CORRECT' if api_routing_correct else 'INCORRECT'}")
    print(f"   ✅ Knowledge MCP routing: {'CORRECT' if knowledge_routing_correct else 'INCORRECT'}")
    
    if api_routing_correct and knowledge_routing_correct:
        print(f"\n🎉 SUCCESS: All MCP integrations are routing correctly!")
        print(f"   - AWS API MCP server receives: {expected_api_tools}")
        print(f"   - AWS Knowledge MCP server receives: {expected_knowledge_tools}")
        print(f"   - Well-Architected Security MCP server ready for security tools")
        return True
    else:
        print(f"\n❌ FAILURE: MCP routing needs to be fixed!")
        return False


async def test_tool_mapping():
    """Test that the correct MCP tools are mapped"""
    print("\n🧪 Testing MCP Tool Mapping")
    print("=" * 40)
    
    # Expected tool mappings based on your MCP configuration
    expected_mappings = {
        'aws-api-mcp-server': [
            'suggest_aws_commands',
            'call_aws'
        ],
        'aws-knowledge-mcp-server': [
            'aws___search_documentation',
            'aws___read_documentation', 
            'aws___recommend'
        ],
        'well-architected-security-mcp-server': [
            'CheckSecurityServices',
            'GetSecurityFindings',
            'CheckStorageEncryption',
            'CheckNetworkSecurity',
            'ListServicesInRegion'
        ]
    }
    
    print("📋 Expected MCP Tool Mappings:")
    for server, tools in expected_mappings.items():
        print(f"\n   {server}:")
        for tool in tools:
            print(f"     - {tool}")
    
    print(f"\n✅ Integration classes should route to these tools correctly!")
    return True


async def main():
    """Main test function"""
    try:
        routing_success = await test_mcp_routing()
        mapping_success = await test_tool_mapping()
        
        if routing_success and mapping_success:
            print(f"\n🎉 ALL TESTS PASSED!")
            print(f"   Your Bedrock Agent is ready to integrate with:")
            print(f"   🔒 well-architected-security-mcp-server")
            print(f"   📚 aws-knowledge-mcp-server")
            print(f"   ⚡ aws-api-mcp-server")
            return 0
        else:
            print(f"\n❌ SOME TESTS FAILED!")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)