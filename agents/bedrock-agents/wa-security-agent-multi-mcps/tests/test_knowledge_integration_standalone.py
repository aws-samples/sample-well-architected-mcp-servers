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
Standalone test for AWS Knowledge Integration
Tests the core functionality without requiring full agent infrastructure
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, Mock

# Add the agent_config directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent_config"))

# Import directly to avoid circular imports
from integrations.aws_knowledge_integration import AWSKnowledgeIntegrationImpl


# Define ToolResult locally to avoid import issues
class ToolResult:
    def __init__(
        self,
        tool_name,
        mcp_server,
        success,
        data,
        error_message=None,
        execution_time=0.0,
        metadata=None,
    ):
        self.tool_name = tool_name
        self.mcp_server = mcp_server
        self.success = success
        self.data = data
        self.error_message = error_message
        self.execution_time = execution_time
        self.metadata = metadata or {}


async def test_aws_knowledge_integration():
    """Test AWS Knowledge Integration functionality"""
    print("🧪 Testing AWS Knowledge Integration...")

    # Create integration instance with mock endpoint for testing
    integration = AWSKnowledgeIntegrationImpl(
        mcp_server_url="https://mock-knowledge-mcp.example.com", cache_ttl=60
    )

    # Mock the HTTP client for testing
    mock_response = Mock()
    mock_response.status_code = 200
    integration.http_client.post = AsyncMock(return_value=mock_response)

    # Test 1: Documentation Search
    print("\n📚 Test 1: Documentation Search")

    sample_docs = [
        {
            "title": "Amazon S3 Security Best Practices",
            "url": "https://docs.aws.amazon.com/s3/security",
            "context": "Amazon S3 provides comprehensive security features including encryption at rest and in transit. Best practices include enabling bucket versioning, configuring access controls, and implementing monitoring.",
            "rank_order": 1,
        },
        {
            "title": "AWS IAM Security Guidelines",
            "url": "https://docs.aws.amazon.com/iam/security",
            "context": "AWS Identity and Access Management (IAM) security guidelines recommend implementing least privilege access, enabling MFA, and regular access reviews.",
            "rank_order": 2,
        },
    ]

    # Mock the HTTP response
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "search_123",
        "result": {"content": [{"type": "text", "text": json.dumps(sample_docs)}]},
    }

    results = await integration.search_relevant_documentation("S3 security")

    assert len(results) > 0, "Should return documentation results"
    assert all("title" in doc for doc in results), "All docs should have titles"
    assert all("relevance_score" in doc for doc in results), (
        "All docs should have relevance scores"
    )
    print(f"✅ Found {len(results)} documentation results")

    # Test 2: Best Practices Retrieval
    print("\n🏆 Test 2: Best Practices Retrieval")

    sample_best_practices = [
        {
            "title": "S3 Security Best Practices Guide",
            "url": "https://docs.aws.amazon.com/s3/best-practices",
            "context": "S3 security best practices: 1. Enable server-side encryption 2. Use bucket policies for access control 3. Enable versioning and MFA delete 4. Configure CloudTrail logging 5. Implement cross-region replication for disaster recovery. Compliance frameworks supported include GDPR, HIPAA, and SOX.",
            "rank_order": 1,
        }
    ]

    # Mock the HTTP response for best practices
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "search_456",
        "result": {
            "content": [{"type": "text", "text": json.dumps(sample_best_practices)}]
        },
    }

    best_practices = await integration.get_best_practices_for_service("s3")

    assert best_practices["service"] == "s3", "Should return correct service"
    assert "practices" in best_practices, "Should contain practices"
    assert "compliance_frameworks" in best_practices, (
        "Should contain compliance frameworks"
    )
    assert len(best_practices["practices"]) > 0, "Should have extracted practices"
    print(f"✅ Retrieved {len(best_practices['practices'])} best practices for S3")

    # Test 3: Compliance Guidance
    print("\n📋 Test 3: Compliance Guidance")

    sample_compliance = [
        {
            "title": "AWS GDPR Compliance Guide",
            "url": "https://aws.amazon.com/compliance/gdpr",
            "context": "GDPR compliance on AWS requires implementing data protection measures. Key requirements include data encryption, access controls, audit logging, and data retention policies. AWS services like IAM, KMS, CloudTrail, and S3 support GDPR compliance.",
            "rank_order": 1,
        }
    ]

    # Mock the HTTP response for compliance
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "search_789",
        "result": {
            "content": [{"type": "text", "text": json.dumps(sample_compliance)}]
        },
    }

    compliance_guide = await integration.find_compliance_guidance("GDPR")

    assert compliance_guide["framework"] == "GDPR", "Should return correct framework"
    assert "requirements" in compliance_guide, "Should contain requirements"
    assert "aws_services" in compliance_guide, "Should contain AWS services"
    assert len(compliance_guide["aws_services"]) > 0, (
        "Should have extracted AWS services"
    )
    print(
        f"✅ Retrieved compliance guidance for GDPR with {len(compliance_guide['aws_services'])} AWS services"
    )

    # Test 4: Documentation Formatting
    print("\n📝 Test 4: Documentation Formatting")

    formatted = integration.format_documentation_results(results)

    assert "Documentation Summary" in formatted, "Should contain summary"
    assert "Found" in formatted, "Should show count"
    assert "📖 [Read more]" in formatted, "Should contain links"
    print("✅ Documentation formatting works correctly")

    # Test 5: Caching
    print("\n💾 Test 5: Caching")

    # Reset call count
    integration.http_client.post.reset_mock()

    # First call
    await integration.search_relevant_documentation("S3 security")
    first_call_count = integration.http_client.post.call_count

    # Second call (should use cache)
    await integration.search_relevant_documentation("S3 security")
    second_call_count = integration.http_client.post.call_count

    assert second_call_count == first_call_count, "Second call should use cache"
    print("✅ Caching works correctly")

    # Test 6: Error Handling
    print("\n🚨 Test 6: Error Handling")

    # Setup mock to raise exception
    integration.http_client.post.side_effect = Exception("Connection failed")

    fallback_results = await integration.search_relevant_documentation("test topic")

    print(f"Debug: Fallback results count: {len(fallback_results)}")
    if len(fallback_results) > 0:
        print(
            f"Debug: First result title: {fallback_results[0].get('title', 'No title')}"
        )

    assert len(fallback_results) >= 1, (
        f"Should return fallback results, got {len(fallback_results)}"
    )
    if len(fallback_results) > 0:
        assert "test topic" in fallback_results[0]["title"], (
            "Should include topic in fallback"
        )
    print("✅ Error handling works correctly")

    # Test 7: Query Enhancement
    print("\n🔍 Test 7: Query Enhancement")

    enhanced = integration._enhance_search_query("S3 encryption")
    assert "encryption" in enhanced, "Should contain original term"
    assert "AWS" in enhanced, "Should add AWS term"
    assert "security" in enhanced, "Should add security term"
    print(f"✅ Query enhancement: '{enhanced}'")

    # Test 8: Content Processing
    print("\n⚙️ Test 8: Content Processing")

    # Test relevance scoring
    result = {
        "title": "S3 Security Best Practices",
        "context": "Amazon S3 security best practices include encryption and access control",
    }

    score = integration._calculate_relevance_score(result, "S3 security")
    assert score > 0.5, "Should have high relevance for matching topic"
    print(f"✅ Relevance scoring: {score:.2f}")

    # Test categorization
    category = integration._categorize_content(
        "AWS security best practices for encryption"
    )
    assert category == "security_best_practices", "Should categorize correctly"
    print(f"✅ Content categorization: {category}")

    # Test service extraction
    service = integration._extract_service_from_content(
        {
            "title": "Amazon S3 Security Guide",
            "context": "Amazon S3 Simple Storage Service provides secure object storage",
        }
    )
    assert service == "S3", "Should extract service correctly"
    print(f"✅ Service extraction: {service}")

    print("\n🎉 All tests passed! AWS Knowledge Integration is working correctly.")

    # Cleanup
    await integration.close()

    return True


def test_data_models():
    """Test data model functionality"""
    print("\n📊 Testing Data Models...")

    from integrations.aws_knowledge_integration import (
        BestPractices,
        ComplianceGuide,
        Document,
    )

    # Test Document model
    doc = Document(
        title="Test Document",
        url="https://example.com",
        content="Test content",
        relevance_score=0.8,
        service="S3",
        category="security",
    )

    assert doc.title == "Test Document"
    assert doc.relevance_score == 0.8
    print("✅ Document model works correctly")

    # Test BestPractices model
    practices = BestPractices(
        service="S3",
        practices=[{"description": "Enable encryption", "category": "security"}],
        compliance_frameworks=["GDPR"],
        security_considerations=["Use strong encryption"],
        documentation_links=["https://example.com"],
    )

    assert practices.service == "S3"
    assert len(practices.practices) == 1
    print("✅ BestPractices model works correctly")

    # Test ComplianceGuide model
    guide = ComplianceGuide(
        framework="GDPR",
        requirements=[{"description": "Data encryption", "framework": "GDPR"}],
        aws_services=["S3", "KMS"],
        implementation_guidance=["Enable encryption"],
        documentation_links=["https://example.com"],
    )

    assert guide.framework == "GDPR"
    assert len(guide.aws_services) == 2
    print("✅ ComplianceGuide model works correctly")


def main():
    """Run all tests"""
    print("🚀 Starting AWS Knowledge Integration Tests")
    print("=" * 60)

    try:
        # Test data models
        test_data_models()

        # Test integration functionality
        asyncio.run(test_aws_knowledge_integration())

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED! AWS Knowledge Integration is ready.")
        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
