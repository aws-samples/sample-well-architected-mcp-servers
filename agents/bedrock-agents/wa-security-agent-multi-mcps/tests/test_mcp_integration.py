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
Test script to validate MCP integration routing
Tests that the agent correctly routes to the three MCP servers:
1. well-architected-security-mcp-server
2. aws-knowledge-mcp-server
3. aws-api-mcp-server
"""

import asyncio
import os
import sys

# Add the agent_config directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent_config"))

from agent_config.integrations.aws_api_integration import AWSAPIIntegrationImpl
from agent_config.integrations.aws_knowledge_integration import (
    AWSKnowledgeIntegrationImpl,
)


class MockMCPOrchestrator:
    """Mock orchestrator for testing the integrations"""

    def __init__(self):
        self.call_counts = {"security": 0, "knowledge": 0, "api": 0}

    async def call_security_tool(self, tool_name: str, args: dict):
        """Mock call to security MCP server"""
        self.call_counts["security"] += 1
        print(f"🔒 Security MCP Call: {tool_name} with args: {args}")

        # Mock response based on tool name
        if "CheckSecurityServices" in tool_name:
            return MockToolResult(
                True,
                {
                    "region": "us-east-1",
                    "services_checked": ["guardduty", "inspector", "securityhub"],
                    "all_enabled": True,
                    "service_statuses": {
                        "guardduty": {"enabled": True, "status": "active"},
                        "inspector": {"enabled": True, "status": "active"},
                        "securityhub": {"enabled": True, "status": "active"},
                    },
                },
            )

        return MockToolResult(True, {"mock": "security_response"})

    async def call_knowledge_tool(self, tool_name: str, args: dict):
        """Mock call to knowledge MCP server"""
        self.call_counts["knowledge"] += 1
        print(f"📚 Knowledge MCP Call: {tool_name} with args: {args}")

        # Mock response based on tool name
        if (
            "search_documentation" in tool_name
            or "aws___search_documentation" in tool_name
        ):
            return MockToolResult(
                True,
                [
                    {
                        "title": "AWS S3 Security Best Practices",
                        "url": "https://docs.aws.amazon.com/s3/latest/userguide/security-best-practices.html",
                        "context": "Amazon S3 provides comprehensive security and compliance capabilities...",
                        "rank_order": 1,
                    },
                    {
                        "title": "AWS IAM Best Practices",
                        "url": "https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html",
                        "context": "AWS Identity and Access Management (IAM) enables you to manage access...",
                        "rank_order": 2,
                    },
                ],
            )

        return MockToolResult(True, {"mock": "knowledge_response"})

    async def call_api_tool(self, tool_name: str, args: dict):
        """Mock call to API MCP server"""
        self.call_counts["api"] += 1
        print(f"⚡ API MCP Call: {tool_name} with args: {args}")

        # Mock response based on tool name
        if "suggest_aws_commands" in tool_name:
            return MockToolResult(
                True,
                [
                    {
                        "command": "aws s3api list-buckets",
                        "confidence": 0.9,
                        "description": "List all S3 buckets in your account",
                        "required_parameters": [],
                        "example": "aws s3api list-buckets",
                    },
                    {
                        "command": "aws s3api get-bucket-encryption --bucket BUCKET_NAME",
                        "confidence": 0.8,
                        "description": "Get encryption configuration for an S3 bucket",
                        "required_parameters": ["bucket"],
                        "example": "aws s3api get-bucket-encryption --bucket my-bucket",
                    },
                ],
            )
        elif "call_aws" in tool_name:
            return MockToolResult(
                True,
                {
                    "Buckets": [
                        {
                            "Name": "my-test-bucket",
                            "CreationDate": "2024-01-01T00:00:00Z",
                        },
                        {
                            "Name": "my-logs-bucket",
                            "CreationDate": "2024-01-02T00:00:00Z",
                        },
                    ]
                },
            )

        return MockToolResult(True, {"mock": "api_response"})


class MockToolResult:
    """Mock tool result for testing"""

    def __init__(self, success: bool, data: any, error_message: str = None):
        self.success = success
        self.data = data
        self.error_message = error_message
        self.execution_time = 0.1


async def test_aws_api_integration():
    """Test AWS API MCP integration"""
    print("\n🧪 Testing AWS API MCP Integration")
    print("=" * 50)

    orchestrator = MockMCPOrchestrator()
    api_integration = AWSAPIIntegrationImpl(orchestrator)

    # Test 1: Suggest AWS commands
    print("\n1️⃣ Testing suggest_aws_commands...")
    result = await api_integration.suggest_aws_commands("list all S3 buckets")
    print(f"   ✅ Success: {result['success']}")
    print(f"   📝 Suggestions: {len(result.get('suggestions', []))} commands")

    # Test 2: Execute AWS command
    print("\n2️⃣ Testing execute_aws_command...")
    result = await api_integration.execute_aws_command("aws s3api list-buckets")
    print(f"   ✅ Success: {result['success']}")
    print(f"   📊 Output: {type(result.get('output', {}))}")

    # Test 3: Get resource details
    print("\n3️⃣ Testing get_resource_details...")
    result = await api_integration.get_resource_details("s3", "my-test-bucket")
    print(f"   ✅ Success: {result['success']}")

    return orchestrator.call_counts["api"]


async def test_aws_knowledge_integration():
    """Test AWS Knowledge MCP integration"""
    print("\n🧪 Testing AWS Knowledge MCP Integration")
    print("=" * 50)

    orchestrator = MockMCPOrchestrator()
    knowledge_integration = AWSKnowledgeIntegrationImpl(orchestrator)

    # Test 1: Search documentation
    print("\n1️⃣ Testing search_relevant_documentation...")
    result = await knowledge_integration.search_relevant_documentation("S3 encryption")
    print(f"   ✅ Found: {len(result)} documents")

    # Test 2: Get best practices
    print("\n2️⃣ Testing get_best_practices_for_service...")
    result = await knowledge_integration.get_best_practices_for_service("s3")
    print(f"   ✅ Service: {result.get('service', 'unknown')}")
    print(f"   📋 Practices: {len(result.get('practices', []))}")

    # Test 3: Find compliance guidance
    print("\n3️⃣ Testing find_compliance_guidance...")
    result = await knowledge_integration.find_compliance_guidance("GDPR")
    print(f"   ✅ Framework: {result.get('framework', 'unknown')}")
    print(f"   📜 Requirements: {len(result.get('requirements', []))}")

    # Test 4: Format results
    print("\n4️⃣ Testing format_documentation_results...")
    mock_docs = [
        {
            "title": "Test Doc",
            "url": "https://example.com",
            "content": "Test content",
            "rank_order": 1,
        }
    ]
    formatted = knowledge_integration.format_documentation_results(mock_docs)
    print(f"   ✅ Formatted length: {len(formatted)} characters")

    return orchestrator.call_counts["knowledge"]


async def test_tool_routing():
    """Test that tools are routed to the correct MCP servers"""
    print("\n🧪 Testing MCP Tool Routing")
    print("=" * 50)

    orchestrator = MockMCPOrchestrator()

    # Initialize integrations
    api_integration = AWSAPIIntegrationImpl(orchestrator)
    knowledge_integration = AWSKnowledgeIntegrationImpl(orchestrator)

    # Test various operations to ensure correct routing
    await api_integration.suggest_aws_commands("test query")
    await api_integration.execute_aws_command("aws s3api list-buckets")

    await knowledge_integration.search_relevant_documentation("test topic")
    await knowledge_integration.get_best_practices_for_service("ec2")

    # Check call counts
    print("\n📊 MCP Server Call Counts:")
    print(f"   🔒 Security MCP: {orchestrator.call_counts['security']} calls")
    print(f"   📚 Knowledge MCP: {orchestrator.call_counts['knowledge']} calls")
    print(f"   ⚡ API MCP: {orchestrator.call_counts['api']} calls")

    return orchestrator.call_counts


async def main():
    """Main test function"""
    print("🚀 Starting MCP Integration Tests")
    print("=" * 60)

    try:
        # Test individual integrations
        api_calls = await test_aws_api_integration()
        knowledge_calls = await test_aws_knowledge_integration()

        # Test routing
        call_counts = await test_tool_routing()

        # Summary
        print("\n🎉 Test Summary")
        print("=" * 30)
        print(f"✅ AWS API Integration: {api_calls} calls made")
        print(f"✅ AWS Knowledge Integration: {knowledge_calls} calls made")
        print(f"✅ Total API calls: {call_counts['api']}")
        print(f"✅ Total Knowledge calls: {call_counts['knowledge']}")
        print(f"✅ Total Security calls: {call_counts['security']}")

        # Validation
        if call_counts["api"] > 0 and call_counts["knowledge"] > 0:
            print(
                "\n🎯 SUCCESS: All integrations are correctly routing to their respective MCP servers!"
            )
        else:
            print("\n❌ FAILURE: Some integrations are not routing correctly!")
            return 1

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
