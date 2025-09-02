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
Unit tests for AWS Knowledge Integration
Tests documentation search, best practices retrieval, and compliance guidance
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from agent_config.integrations.aws_knowledge_integration import (
    AWSKnowledgeIntegrationImpl, Document, BestPractices, ComplianceGuide
)
from agent_config.interfaces import ToolResult


class TestAWSKnowledgeIntegration:
    """Test suite for AWS Knowledge Integration"""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock MCP orchestrator"""
        orchestrator = Mock()
        orchestrator.call_knowledge_tool = AsyncMock()
        return orchestrator
    
    @pytest.fixture
    def knowledge_integration(self, mock_orchestrator):
        """Create AWS Knowledge Integration instance"""
        return AWSKnowledgeIntegrationImpl(mock_orchestrator, cache_ttl=60)
    
    @pytest.fixture
    def sample_documentation_results(self):
        """Sample documentation search results"""
        return [
            {
                'title': 'Amazon S3 Security Best Practices',
                'url': 'https://docs.aws.amazon.com/s3/security',
                'context': 'Amazon S3 provides comprehensive security features including encryption at rest and in transit. Best practices include enabling bucket versioning, configuring access controls, and implementing monitoring.',
                'rank_order': 1
            },
            {
                'title': 'AWS IAM Security Guidelines',
                'url': 'https://docs.aws.amazon.com/iam/security',
                'context': 'AWS Identity and Access Management (IAM) security guidelines recommend implementing least privilege access, enabling MFA, and regular access reviews.',
                'rank_order': 2
            },
            {
                'title': 'VPC Security Configuration',
                'url': 'https://docs.aws.amazon.com/vpc/security',
                'context': 'Virtual Private Cloud security configuration involves setting up security groups, NACLs, and VPC flow logs for network monitoring.',
                'rank_order': 3
            }
        ]
    
    @pytest.fixture
    def sample_best_practices_results(self):
        """Sample best practices search results"""
        return [
            {
                'title': 'S3 Security Best Practices Guide',
                'url': 'https://docs.aws.amazon.com/s3/best-practices',
                'context': 'S3 security best practices: 1. Enable server-side encryption 2. Use bucket policies for access control 3. Enable versioning and MFA delete 4. Configure CloudTrail logging 5. Implement cross-region replication for disaster recovery. Compliance frameworks supported include GDPR, HIPAA, and SOX.',
                'rank_order': 1
            }
        ]
    
    @pytest.fixture
    def sample_compliance_results(self):
        """Sample compliance guidance results"""
        return [
            {
                'title': 'AWS GDPR Compliance Guide',
                'url': 'https://aws.amazon.com/compliance/gdpr',
                'context': 'GDPR compliance on AWS requires implementing data protection measures. Key requirements include data encryption, access controls, audit logging, and data retention policies. AWS services like IAM, KMS, CloudTrail, and S3 support GDPR compliance.',
                'rank_order': 1
            }
        ]
    
    @pytest.mark.asyncio
    async def test_search_relevant_documentation_success(self, knowledge_integration, mock_orchestrator, sample_documentation_results):
        """Test successful documentation search"""
        # Setup mock response
        mock_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data=sample_documentation_results
        )
        
        # Execute search
        results = await knowledge_integration.search_relevant_documentation("S3 security")
        
        # Verify results
        assert len(results) > 0
        assert all('title' in doc for doc in results)
        assert all('url' in doc for doc in results)
        assert all('relevance_score' in doc for doc in results)
        
        # Verify MCP call
        mock_orchestrator.call_knowledge_tool.assert_called_once_with(
            "search_documentation",
            {
                "search_phrase": "S3 security encryption access control AWS security best practices",
                "limit": 20
            }
        )
    
    @pytest.mark.asyncio
    async def test_search_relevant_documentation_with_caching(self, knowledge_integration, mock_orchestrator, sample_documentation_results):
        """Test documentation search with caching"""
        # Setup mock response
        mock_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data=sample_documentation_results
        )
        
        # First call
        results1 = await knowledge_integration.search_relevant_documentation("S3 security")
        
        # Second call (should use cache)
        results2 = await knowledge_integration.search_relevant_documentation("S3 security")
        
        # Verify results are identical
        assert results1 == results2
        
        # Verify MCP was called only once
        assert mock_orchestrator.call_knowledge_tool.call_count == 1
    
    @pytest.mark.asyncio
    async def test_search_relevant_documentation_failure(self, knowledge_integration, mock_orchestrator):
        """Test documentation search failure handling"""
        # Setup mock to raise exception
        mock_orchestrator.call_knowledge_tool.side_effect = Exception("Connection failed")
        
        # Execute search
        results = await knowledge_integration.search_relevant_documentation("S3 security")
        
        # Verify fallback results
        assert len(results) == 1
        assert "AWS Security Best Practices" in results[0]['title']
        assert results[0]['relevance_score'] == 0.5
    
    @pytest.mark.asyncio
    async def test_get_best_practices_for_service_success(self, knowledge_integration, mock_orchestrator, sample_best_practices_results):
        """Test successful best practices retrieval"""
        # Setup mock response
        mock_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data=sample_best_practices_results
        )
        
        # Execute search
        result = await knowledge_integration.get_best_practices_for_service("s3")
        
        # Verify result structure
        assert result['service'] == 's3'
        assert 'practices' in result
        assert 'compliance_frameworks' in result
        assert 'security_considerations' in result
        assert 'documentation_links' in result
        
        # Verify practices were extracted
        assert len(result['practices']) > 0
        assert any('encryption' in practice['description'].lower() for practice in result['practices'])
    
    @pytest.mark.asyncio
    async def test_get_best_practices_for_service_with_caching(self, knowledge_integration, mock_orchestrator, sample_best_practices_results):
        """Test best practices retrieval with caching"""
        # Setup mock response
        mock_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data=sample_best_practices_results
        )
        
        # First call
        result1 = await knowledge_integration.get_best_practices_for_service("s3")
        
        # Second call (should use cache)
        result2 = await knowledge_integration.get_best_practices_for_service("s3")
        
        # Verify results are identical
        assert result1 == result2
        
        # Verify MCP was called only once
        assert mock_orchestrator.call_knowledge_tool.call_count == 1
    
    @pytest.mark.asyncio
    async def test_find_compliance_guidance_success(self, knowledge_integration, mock_orchestrator, sample_compliance_results):
        """Test successful compliance guidance retrieval"""
        # Setup mock response
        mock_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data=sample_compliance_results
        )
        
        # Execute search
        result = await knowledge_integration.find_compliance_guidance("GDPR")
        
        # Verify result structure
        assert result['framework'] == 'GDPR'
        assert 'requirements' in result
        assert 'aws_services' in result
        assert 'implementation_guidance' in result
        assert 'documentation_links' in result
        
        # Verify AWS services were extracted
        assert len(result['aws_services']) > 0
        assert any(service in ['IAM', 'S3', 'KMS'] for service in result['aws_services'])
    
    @pytest.mark.asyncio
    async def test_find_compliance_guidance_failure(self, knowledge_integration, mock_orchestrator):
        """Test compliance guidance failure handling"""
        # Setup mock to raise exception
        mock_orchestrator.call_knowledge_tool.side_effect = Exception("Connection failed")
        
        # Execute search
        result = await knowledge_integration.find_compliance_guidance("GDPR")
        
        # Verify fallback result
        assert result['framework'] == 'GDPR'
        assert len(result['requirements']) > 0
        assert len(result['aws_services']) > 0
    
    def test_format_documentation_results_success(self, knowledge_integration):
        """Test documentation results formatting"""
        docs = [
            {
                'title': 'S3 Security Guide',
                'url': 'https://docs.aws.amazon.com/s3/security',
                'content': 'Amazon S3 provides comprehensive security features for data protection.',
                'relevance_score': 0.9,
                'category': 'security_best_practices'
            },
            {
                'title': 'IAM Best Practices',
                'url': 'https://docs.aws.amazon.com/iam/best-practices',
                'content': 'AWS IAM best practices include implementing least privilege access.',
                'relevance_score': 0.8,
                'category': 'access_control'
            }
        ]
        
        formatted = knowledge_integration.format_documentation_results(docs)
        
        # Verify formatting
        assert "Documentation Summary" in formatted
        assert "Found 2 relevant documents" in formatted
        assert "S3 Security Guide" in formatted
        assert "IAM Best Practices" in formatted
        assert "📖 [Read more]" in formatted
        assert "Relevance: 90.0%" in formatted
    
    def test_format_documentation_results_empty(self, knowledge_integration):
        """Test formatting with empty results"""
        formatted = knowledge_integration.format_documentation_results([])
        assert formatted == "No relevant documentation found."
    
    def test_enhance_search_query(self, knowledge_integration):
        """Test search query enhancement"""
        # Test encryption topic
        enhanced = knowledge_integration._enhance_search_query("S3 encryption")
        assert "encryption" in enhanced
        assert "kms" in enhanced
        assert "AWS" in enhanced
        assert "security" in enhanced
        
        # Test access control topic
        enhanced = knowledge_integration._enhance_search_query("IAM permissions")
        assert "iam" in enhanced
        assert "access" in enhanced
        assert "permissions" in enhanced
    
    def test_get_service_search_terms(self, knowledge_integration):
        """Test service search terms generation"""
        # Test known service
        terms = knowledge_integration._get_service_search_terms("s3")
        assert "Amazon S3" in terms
        assert "Simple Storage Service" in terms
        
        # Test unknown service
        terms = knowledge_integration._get_service_search_terms("unknown")
        assert terms == "unknown"
    
    def test_calculate_relevance_score(self, knowledge_integration):
        """Test relevance score calculation"""
        result = {
            'title': 'S3 Security Best Practices',
            'context': 'Amazon S3 security best practices include encryption and access control'
        }
        
        # High relevance for matching topic
        score = knowledge_integration._calculate_relevance_score(result, "S3 security")
        assert score > 0.5
        
        # Lower relevance for non-matching topic
        score = knowledge_integration._calculate_relevance_score(result, "Lambda functions")
        assert score < 0.5
    
    def test_categorize_content(self, knowledge_integration):
        """Test content categorization"""
        # Test security content
        category = knowledge_integration._categorize_content("AWS security best practices for encryption")
        assert category == "security_best_practices"
        
        # Test compliance content
        category = knowledge_integration._categorize_content("GDPR compliance requirements")
        assert category == "compliance"
        
        # Test encryption content
        category = knowledge_integration._categorize_content("KMS encryption keys")
        assert category == "encryption"
        
        # Test general content
        category = knowledge_integration._categorize_content("General AWS information")
        assert category == "general"
    
    def test_extract_service_from_content(self, knowledge_integration):
        """Test AWS service extraction from content"""
        result = {
            'title': 'Amazon S3 Security Guide',
            'context': 'Amazon S3 Simple Storage Service provides secure object storage'
        }
        
        service = knowledge_integration._extract_service_from_content(result)
        assert service == "S3"
        
        # Test with no service
        result = {
            'title': 'General Security Guide',
            'context': 'General security information'
        }
        
        service = knowledge_integration._extract_service_from_content(result)
        assert service is None
    
    def test_get_content_preview(self, knowledge_integration):
        """Test content preview generation"""
        # Test short content
        short_content = "This is a short content."
        preview = knowledge_integration._get_content_preview(short_content)
        assert preview == short_content
        
        # Test long content
        long_content = "This is a very long content that exceeds the maximum length limit. " * 10
        preview = knowledge_integration._get_content_preview(long_content, max_length=100)
        assert len(preview) <= 103  # 100 + "..."
        assert preview.endswith("...")
    
    def test_extract_practices_from_content(self, knowledge_integration):
        """Test best practices extraction"""
        content = "You should enable encryption for all S3 buckets. Always implement least privilege access. Never store credentials in code."
        
        practices = knowledge_integration._extract_practices_from_content(content)
        
        assert len(practices) > 0
        assert all('description' in practice for practice in practices)
        assert all('category' in practice for practice in practices)
    
    def test_extract_compliance_mentions(self, knowledge_integration):
        """Test compliance framework extraction"""
        content = "This solution supports GDPR and HIPAA compliance requirements. SOX compliance is also available."
        
        mentions = knowledge_integration._extract_compliance_mentions(content)
        
        assert "GDPR" in mentions
        assert "HIPAA" in mentions
        assert "SOX" in mentions
    
    def test_extract_security_considerations(self, knowledge_integration):
        """Test security considerations extraction"""
        content = "Security considerations include enabling encryption at rest. Protect sensitive data with proper access controls. Secure network communications using TLS."
        
        considerations = knowledge_integration._extract_security_considerations(content)
        
        assert len(considerations) > 0
        assert any("encryption" in consideration.lower() for consideration in considerations)
        assert any("access controls" in consideration.lower() for consideration in considerations)
    
    def test_extract_aws_services_from_content(self, knowledge_integration):
        """Test AWS services extraction"""
        content = "Use Amazon S3 for storage, AWS Lambda for compute, and Amazon RDS for databases."
        
        services = knowledge_integration._extract_aws_services_from_content(content)
        
        assert "S3" in services
        assert "LAMBDA" in services
        assert "RDS" in services
    
    def test_cache_expiration(self, knowledge_integration):
        """Test cache expiration logic"""
        # Test valid cache
        cache_key = "test_key"
        cache_dict = {
            cache_key: {
                'data': 'test_data',
                'timestamp': datetime.now().timestamp()
            }
        }
        
        assert knowledge_integration._is_cache_valid(cache_key, cache_dict) is True
        
        # Test expired cache
        cache_dict[cache_key]['timestamp'] = (datetime.now() - timedelta(hours=2)).timestamp()
        assert knowledge_integration._is_cache_valid(cache_key, cache_dict) is False
        
        # Test missing cache
        assert knowledge_integration._is_cache_valid("missing_key", cache_dict) is False
    
    def test_fallback_methods(self, knowledge_integration):
        """Test fallback methods when searches fail"""
        # Test fallback documentation
        fallback_docs = knowledge_integration._get_fallback_documentation("S3 security")
        assert len(fallback_docs) == 1
        assert "S3 security" in fallback_docs[0]['title']
        
        # Test fallback best practices
        fallback_practices = knowledge_integration._get_fallback_best_practices("s3")
        assert fallback_practices['service'] == 's3'
        assert len(fallback_practices['practices']) > 0
        
        # Test fallback compliance guidance
        fallback_compliance = knowledge_integration._get_fallback_compliance_guidance("GDPR")
        assert fallback_compliance['framework'] == 'GDPR'
        assert len(fallback_compliance['requirements']) > 0


class TestAWSKnowledgeIntegrationEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def knowledge_integration(self):
        """Create AWS Knowledge Integration instance with mock orchestrator"""
        mock_orchestrator = Mock()
        mock_orchestrator.call_knowledge_tool = AsyncMock()
        return AWSKnowledgeIntegrationImpl(mock_orchestrator, cache_ttl=60)
    
    @pytest.mark.asyncio
    async def test_search_with_empty_results(self, knowledge_integration):
        """Test search with empty results from MCP server"""
        knowledge_integration.mcp_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=True,
            data=[]
        )
        
        results = await knowledge_integration.search_relevant_documentation("nonexistent topic")
        
        # Should return fallback documentation
        assert len(results) == 1
        assert "nonexistent topic" in results[0]['title']
    
    @pytest.mark.asyncio
    async def test_search_with_failed_tool_result(self, knowledge_integration):
        """Test search with failed tool result"""
        knowledge_integration.mcp_orchestrator.call_knowledge_tool.return_value = ToolResult(
            tool_name="search_documentation",
            mcp_server="knowledge",
            success=False,
            data=None,
            error_message="Tool execution failed"
        )
        
        results = await knowledge_integration.search_relevant_documentation("test topic")
        
        # Should return fallback documentation
        assert len(results) == 1
        assert "test topic" in results[0]['title']
    
    def test_process_malformed_documentation_results(self, knowledge_integration):
        """Test processing of malformed documentation results"""
        malformed_results = [
            {},  # Empty result
            {'title': 'Valid Title'},  # Missing other fields
            {'url': 'https://example.com'},  # Missing title
            None  # None result
        ]
        
        processed = knowledge_integration._process_documentation_results(malformed_results, "test")
        
        # Should handle malformed results gracefully
        assert isinstance(processed, list)
        # Valid results should be processed, invalid ones skipped
        assert len(processed) <= len(malformed_results)
    
    def test_extract_practices_from_empty_content(self, knowledge_integration):
        """Test practice extraction from empty content"""
        practices = knowledge_integration._extract_practices_from_content("")
        assert practices == []
        
        practices = knowledge_integration._extract_practices_from_content("   ")
        assert practices == []
    
    def test_categorize_documents_with_unknown_categories(self, knowledge_integration):
        """Test document categorization with unknown categories"""
        docs = [
            {'category': 'unknown_category'},
            {'category': 'security_best_practices'},
            {}  # Missing category
        ]
        
        categorized = knowledge_integration._categorize_documents(docs)
        
        # Unknown categories should go to 'general'
        assert len(categorized['general']) >= 1
        assert len(categorized['security_best_practices']) == 1
    
    def test_content_preview_with_special_characters(self, knowledge_integration):
        """Test content preview with special characters and formatting"""
        content_with_special_chars = "Content with\n\nnewlines\t\tand\r\rcarriage returns   and   spaces."
        
        preview = knowledge_integration._get_content_preview(content_with_special_chars)
        
        # Should clean up whitespace
        assert "\n\n" not in preview
        assert "\t\t" not in preview
        assert "\r\r" not in preview
        assert "   " not in preview


if __name__ == "__main__":
    pytest.main([__file__])