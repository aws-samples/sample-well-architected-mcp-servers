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
AWS Knowledge MCP Server Integration
Simplified handler for AWS Knowledge MCP Server using public endpoint
"""

import asyncio
import json
import re
import httpx
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from agent_config.interfaces import AWSKnowledgeIntegration, ToolResult
    from agent_config.utils.logging_utils import get_logger
    from agent_config.utils.error_handling import ErrorHandler
except ImportError:
    # Fallback for standalone testing
    from abc import ABC, abstractmethod
    from typing import Dict, List, Any
    import logging
    
    class AWSKnowledgeIntegration(ABC):
        @abstractmethod
        async def search_relevant_documentation(self, security_topic: str) -> List[Dict[str, Any]]:
            pass
        
        @abstractmethod
        async def get_best_practices_for_service(self, aws_service: str) -> Dict[str, Any]:
            pass
        
        @abstractmethod
        async def find_compliance_guidance(self, compliance_framework: str) -> Dict[str, Any]:
            pass
        
        @abstractmethod
        def format_documentation_results(self, docs: List[Dict[str, Any]]) -> str:
            pass
    
    class ToolResult:
        def __init__(self, tool_name, mcp_server, success, data, error_message=None, execution_time=0.0, metadata=None):
            self.tool_name = tool_name
            self.mcp_server = mcp_server
            self.success = success
            self.data = data
            self.error_message = error_message
            self.execution_time = execution_time
            self.metadata = metadata or {}
    
    def get_logger(name):
        return logging.getLogger(name)
    
    class ErrorHandler:
        pass

logger = get_logger(__name__)


@dataclass
class Document:
    """Represents an AWS documentation document"""
    title: str
    url: str
    content: str
    relevance_score: float
    service: Optional[str] = None
    category: Optional[str] = None
    last_updated: Optional[str] = None


@dataclass
class BestPractices:
    """Represents AWS service best practices"""
    service: str
    practices: List[Dict[str, Any]]
    compliance_frameworks: List[str]
    security_considerations: List[str]
    documentation_links: List[str]


@dataclass
class ComplianceGuide:
    """Represents compliance guidance"""
    framework: str
    requirements: List[Dict[str, Any]]
    aws_services: List[str]
    implementation_guidance: List[str]
    documentation_links: List[str]


class AWSKnowledgeIntegrationImpl(AWSKnowledgeIntegration):
    """
    Implementation of AWS Knowledge MCP Server integration using public endpoint
    Provides documentation search, best practices retrieval, and compliance guidance
    """
    
    def __init__(self, mcp_server_url: str = "https://knowledge-mcp.global.api.aws", cache_ttl: int = 3600):
        """
        Initialize AWS Knowledge integration
        
        Args:
            mcp_server_url: URL of the AWS Knowledge MCP server (default: public endpoint)
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.error_handler = ErrorHandler()
        self.cache_ttl = cache_ttl
        self._documentation_cache = {}
        self._best_practices_cache = {}
        self._compliance_cache = {}
        
        # HTTP client for direct API calls
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AWS-Enhanced-Security-Agent/1.0"
            }
        )
        
        # Security-related keywords for enhanced search
        self.security_keywords = {
            'encryption': ['encryption', 'kms', 'ssl', 'tls', 'crypto'],
            'access_control': ['iam', 'access', 'permissions', 'roles', 'policies'],
            'network_security': ['vpc', 'security groups', 'nacl', 'firewall', 'network'],
            'monitoring': ['cloudtrail', 'cloudwatch', 'logging', 'monitoring', 'audit'],
            'compliance': ['compliance', 'gdpr', 'hipaa', 'sox', 'pci', 'iso'],
            'data_protection': ['backup', 'disaster recovery', 'data protection', 'retention'],
            'identity': ['authentication', 'authorization', 'mfa', 'sso', 'identity']
        }
        
        # AWS service mappings for better search targeting
        self.service_mappings = {
            's3': ['Amazon S3', 'Simple Storage Service', 'object storage'],
            'ec2': ['Amazon EC2', 'Elastic Compute Cloud', 'virtual machines'],
            'rds': ['Amazon RDS', 'Relational Database Service', 'database'],
            'lambda': ['AWS Lambda', 'serverless', 'functions'],
            'iam': ['AWS IAM', 'Identity and Access Management', 'permissions'],
            'vpc': ['Amazon VPC', 'Virtual Private Cloud', 'networking'],
            'cloudtrail': ['AWS CloudTrail', 'audit logging', 'api logging'],
            'kms': ['AWS KMS', 'Key Management Service', 'encryption keys']
        }
        
        logger.info(f"AWS Knowledge Integration initialized with endpoint: {self.mcp_server_url}")
    
    async def close(self):
        """Close the HTTP client connection"""
        if hasattr(self, 'http_client'):
            await self.http_client.aclose()
    
    async def search_relevant_documentation(self, security_topic: str) -> List[Dict[str, Any]]:
        """
        Search AWS documentation for relevant security guidance
        
        Args:
            security_topic: The security topic to search for
            
        Returns:
            List of relevant documentation with metadata
        """
        try:
            # Check cache first
            cache_key = f"docs_{security_topic.lower()}"
            if self._is_cache_valid(cache_key, self._documentation_cache):
                logger.info(f"Returning cached documentation for topic: {security_topic}")
                return self._documentation_cache[cache_key]['data']
            
            # Enhance search query with related keywords
            enhanced_query = self._enhance_search_query(security_topic)
            
            # Search AWS documentation using Knowledge MCP server
            search_results = await self._search_aws_documentation(enhanced_query)
            
            # Process and rank results
            processed_docs = self._process_documentation_results(search_results, security_topic)
            
            # Cache results
            self._documentation_cache[cache_key] = {
                'data': processed_docs,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"Found {len(processed_docs)} relevant documents for topic: {security_topic}")
            return processed_docs
            
        except Exception as e:
            logger.error(f"Error searching documentation for topic '{security_topic}': {e}")
            return self._get_fallback_documentation(security_topic)
    
    async def get_best_practices_for_service(self, aws_service: str) -> Dict[str, Any]:
        """
        Get best practices for specific AWS service
        
        Args:
            aws_service: AWS service name (e.g., 's3', 'ec2', 'rds')
            
        Returns:
            Best practices information for the service
        """
        try:
            # Check cache first
            cache_key = f"practices_{aws_service.lower()}"
            if self._is_cache_valid(cache_key, self._best_practices_cache):
                logger.info(f"Returning cached best practices for service: {aws_service}")
                return self._best_practices_cache[cache_key]['data']
            
            # Get service-specific search terms
            service_terms = self._get_service_search_terms(aws_service)
            
            # Search for best practices documentation
            best_practices_query = f"{service_terms} security best practices configuration"
            search_results = await self._search_aws_documentation(best_practices_query)
            
            # Process results into structured best practices
            best_practices = self._extract_best_practices(search_results, aws_service)
            
            # Cache results
            self._best_practices_cache[cache_key] = {
                'data': best_practices,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"Retrieved best practices for service: {aws_service}")
            return best_practices
            
        except Exception as e:
            logger.error(f"Error getting best practices for service '{aws_service}': {e}")
            return self._get_fallback_best_practices(aws_service)
    
    async def find_compliance_guidance(self, compliance_framework: str) -> Dict[str, Any]:
        """
        Find compliance and regulatory guidance
        
        Args:
            compliance_framework: Compliance framework (e.g., 'GDPR', 'HIPAA', 'SOX')
            
        Returns:
            Compliance guidance information
        """
        try:
            # Check cache first
            cache_key = f"compliance_{compliance_framework.lower()}"
            if self._is_cache_valid(cache_key, self._compliance_cache):
                logger.info(f"Returning cached compliance guidance for: {compliance_framework}")
                return self._compliance_cache[cache_key]['data']
            
            # Search for compliance-specific documentation
            compliance_query = f"AWS {compliance_framework} compliance security requirements"
            search_results = await self._search_aws_documentation(compliance_query)
            
            # Process results into structured compliance guidance
            compliance_guide = self._extract_compliance_guidance(search_results, compliance_framework)
            
            # Cache results
            self._compliance_cache[cache_key] = {
                'data': compliance_guide,
                'timestamp': datetime.now().timestamp()
            }
            
            logger.info(f"Retrieved compliance guidance for: {compliance_framework}")
            return compliance_guide
            
        except Exception as e:
            logger.error(f"Error finding compliance guidance for '{compliance_framework}': {e}")
            return self._get_fallback_compliance_guidance(compliance_framework)
    
    def format_documentation_results(self, docs: List[Dict[str, Any]]) -> str:
        """
        Format documentation results for integration with security assessments
        
        Args:
            docs: List of documentation results
            
        Returns:
            Formatted documentation string
        """
        if not docs:
            return "No relevant documentation found."
        
        formatted_sections = []
        
        # Group documents by category
        categorized_docs = self._categorize_documents(docs)
        
        for category, category_docs in categorized_docs.items():
            if not category_docs:
                continue
                
            formatted_sections.append(f"\n## {category.replace('_', ' ').title()}")
            
            for doc in category_docs[:3]:  # Limit to top 3 per category
                title = doc.get('title', 'Untitled Document')
                url = doc.get('url', '')
                content_preview = self._get_content_preview(doc.get('content', ''))
                relevance = doc.get('relevance_score', 0.0)
                
                formatted_sections.append(f"\n### {title}")
                if content_preview:
                    formatted_sections.append(f"{content_preview}")
                if url:
                    formatted_sections.append(f"📖 [Read more]({url})")
                formatted_sections.append(f"*Relevance: {relevance:.1%}*")
        
        # Add summary section
        total_docs = len(docs)
        high_relevance_docs = len([d for d in docs if d.get('relevance_score', 0) > 0.7])
        
        summary = f"\n## Documentation Summary\n"
        summary += f"Found {total_docs} relevant documents, {high_relevance_docs} with high relevance.\n"
        
        return summary + "\n".join(formatted_sections)
    
    async def _search_aws_documentation(self, query: str) -> List[Dict[str, Any]]:
        """Search AWS documentation using direct HTTP calls to Knowledge MCP server"""
        try:
            # Prepare the MCP request payload
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"search_{datetime.now().timestamp()}",
                "method": "tools/call",
                "params": {
                    "name": "search_documentation",
                    "arguments": {
                        "search_phrase": query,
                        "limit": 20  # Get more results for better filtering
                    }
                }
            }
            
            # Make direct HTTP call to AWS Knowledge MCP server
            response = await self.http_client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request
            )
            
            if response.status_code == 200:
                result_data = response.json()
                
                # Extract results from MCP response
                if "result" in result_data and "content" in result_data["result"]:
                    content = result_data["result"]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # Parse the text content which should contain JSON results
                        text_content = content[0].get("text", "")
                        if text_content:
                            try:
                                # Try to parse as JSON
                                parsed_results = json.loads(text_content)
                                if isinstance(parsed_results, list):
                                    return parsed_results
                                elif isinstance(parsed_results, dict) and "results" in parsed_results:
                                    return parsed_results["results"]
                            except json.JSONDecodeError:
                                # If not JSON, treat as plain text and create a simple result
                                return [{
                                    "title": "AWS Documentation Search Result",
                                    "content": text_content,
                                    "url": "https://docs.aws.amazon.com/",
                                    "rank_order": 1
                                }]
                
                logger.warning(f"No results from knowledge server for query: {query}")
                return []
            else:
                logger.error(f"HTTP error from knowledge server: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error calling knowledge MCP server: {e}")
            # Re-raise the exception so the calling method can handle it with fallback
            raise
    
    def _enhance_search_query(self, topic: str) -> str:
        """Enhance search query with related security keywords"""
        topic_lower = topic.lower()
        enhanced_terms = [topic]
        
        # Add related security keywords
        for category, keywords in self.security_keywords.items():
            if any(keyword in topic_lower for keyword in keywords):
                enhanced_terms.extend(keywords[:2])  # Add top 2 related keywords
                break
        
        # Add AWS-specific terms
        enhanced_terms.extend(['AWS', 'security', 'best practices'])
        
        return ' '.join(set(enhanced_terms))  # Remove duplicates
    
    def _get_service_search_terms(self, service: str) -> str:
        """Get enhanced search terms for AWS service"""
        service_lower = service.lower()
        
        if service_lower in self.service_mappings:
            return ' '.join(self.service_mappings[service_lower])
        
        return service
    
    def _process_documentation_results(self, results: List[Dict[str, Any]], topic: str) -> List[Dict[str, Any]]:
        """Process and rank documentation results"""
        processed_docs = []
        
        for result in results:
            try:
                # Extract document information
                doc_info = {
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('context', result.get('content', '')),
                    'service': self._extract_service_from_content(result),
                    'category': self._categorize_content(result.get('context', '')),
                    'last_updated': result.get('last_updated'),
                    'relevance_score': self._calculate_relevance_score(result, topic)
                }
                
                processed_docs.append(doc_info)
                
            except Exception as e:
                logger.warning(f"Error processing documentation result: {e}")
                continue
        
        # Sort by relevance score
        processed_docs.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return processed_docs[:10]  # Return top 10 most relevant
    
    def _extract_best_practices(self, results: List[Dict[str, Any]], service: str) -> Dict[str, Any]:
        """Extract structured best practices from search results"""
        practices = []
        compliance_frameworks = set()
        security_considerations = []
        documentation_links = []
        
        for result in results:
            content = result.get('context', result.get('content', ''))
            url = result.get('url', '')
            
            # Extract best practices from content
            extracted_practices = self._extract_practices_from_content(content)
            practices.extend(extracted_practices)
            
            # Extract compliance mentions
            compliance_mentions = self._extract_compliance_mentions(content)
            compliance_frameworks.update(compliance_mentions)
            
            # Extract security considerations
            security_items = self._extract_security_considerations(content)
            security_considerations.extend(security_items)
            
            if url:
                documentation_links.append(url)
        
        return {
            'service': service,
            'practices': practices[:10],  # Top 10 practices
            'compliance_frameworks': list(compliance_frameworks),
            'security_considerations': security_considerations[:8],  # Top 8 considerations
            'documentation_links': documentation_links[:5]  # Top 5 links
        }
    
    def _extract_compliance_guidance(self, results: List[Dict[str, Any]], framework: str) -> Dict[str, Any]:
        """Extract structured compliance guidance from search results"""
        requirements = []
        aws_services = set()
        implementation_guidance = []
        documentation_links = []
        
        for result in results:
            content = result.get('context', result.get('content', ''))
            url = result.get('url', '')
            
            # Extract compliance requirements
            extracted_requirements = self._extract_compliance_requirements(content, framework)
            requirements.extend(extracted_requirements)
            
            # Extract AWS services mentioned
            service_mentions = self._extract_aws_services_from_content(content)
            aws_services.update(service_mentions)
            
            # Extract implementation guidance
            guidance_items = self._extract_implementation_guidance(content)
            implementation_guidance.extend(guidance_items)
            
            if url:
                documentation_links.append(url)
        
        return {
            'framework': framework,
            'requirements': requirements[:8],  # Top 8 requirements
            'aws_services': list(aws_services),
            'implementation_guidance': implementation_guidance[:10],  # Top 10 guidance items
            'documentation_links': documentation_links[:5]  # Top 5 links
        }
    
    def _calculate_relevance_score(self, result: Dict[str, Any], topic: str) -> float:
        """Calculate relevance score for a documentation result"""
        score = 0.0
        content = (result.get('context', '') + ' ' + result.get('title', '')).lower()
        topic_lower = topic.lower()
        
        # Title match bonus
        if topic_lower in result.get('title', '').lower():
            score += 0.3
        
        # Content relevance
        topic_words = topic_lower.split()
        content_words = content.split()
        
        matches = sum(1 for word in topic_words if word in content_words)
        if topic_words:
            score += (matches / len(topic_words)) * 0.4
        
        # Security keyword bonus
        security_terms = ['security', 'best practice', 'compliance', 'encryption', 'access control']
        security_matches = sum(1 for term in security_terms if term in content)
        score += min(security_matches * 0.1, 0.3)
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _categorize_content(self, content: str) -> str:
        """Categorize content based on keywords"""
        content_lower = content.lower()
        
        categories = {
            'security_best_practices': ['security', 'best practice', 'secure', 'protection'],
            'compliance': ['compliance', 'regulatory', 'gdpr', 'hipaa', 'sox'],
            'encryption': ['encryption', 'kms', 'ssl', 'tls', 'crypto'],
            'access_control': ['iam', 'access', 'permission', 'role', 'policy'],
            'monitoring': ['monitoring', 'logging', 'cloudtrail', 'cloudwatch'],
            'network_security': ['vpc', 'security group', 'network', 'firewall']
        }
        
        for category, keywords in categories.items():
            if any(keyword in content_lower for keyword in keywords):
                return category
        
        return 'general'
    
    def _extract_service_from_content(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract AWS service name from content"""
        content = (result.get('context', '') + ' ' + result.get('title', '')).lower()
        
        for service, terms in self.service_mappings.items():
            if any(term.lower() in content for term in terms):
                return service.upper()
        
        return None
    
    def _categorize_documents(self, docs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize documents by type"""
        categories = {
            'security_best_practices': [],
            'compliance': [],
            'encryption': [],
            'access_control': [],
            'monitoring': [],
            'network_security': [],
            'general': []
        }
        
        for doc in docs:
            category = doc.get('category', 'general')
            if category in categories:
                categories[category].append(doc)
            else:
                categories['general'].append(doc)
        
        return categories
    
    def _get_content_preview(self, content: str, max_length: int = 200) -> str:
        """Get a preview of content"""
        if not content:
            return ""
        
        # Clean up content
        cleaned = re.sub(r'\s+', ' ', content.strip())
        
        if len(cleaned) <= max_length:
            return cleaned
        
        # Find a good breaking point
        truncated = cleaned[:max_length]
        last_sentence = truncated.rfind('.')
        if last_sentence > max_length * 0.7:  # If we can break at a sentence
            return truncated[:last_sentence + 1]
        
        return truncated + "..."
    
    def _extract_practices_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract best practices from content"""
        practices = []
        
        # Look for common best practice patterns
        patterns = [
            r'(?:should|must|recommend|best practice)[^.]*\.([^.]*\.)?',
            r'(?:enable|configure|use|implement)[^.]*security[^.]*\.',
            r'(?:always|never|avoid)[^.]*\.'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:3]:  # Limit per pattern
                practice_text = match[0] if isinstance(match, tuple) else match
                if len(practice_text.strip()) > 10:  # Filter out very short matches
                    practices.append({
                        'description': practice_text.strip(),
                        'category': 'security'
                    })
        
        return practices[:5]  # Return top 5
    
    def _extract_compliance_mentions(self, content: str) -> List[str]:
        """Extract compliance framework mentions"""
        frameworks = ['GDPR', 'HIPAA', 'SOX', 'PCI DSS', 'ISO 27001', 'FedRAMP', 'SOC 2']
        mentions = []
        
        content_upper = content.upper()
        for framework in frameworks:
            if framework in content_upper:
                mentions.append(framework)
        
        return mentions
    
    def _extract_security_considerations(self, content: str) -> List[str]:
        """Extract security considerations from content"""
        considerations = []
        
        # Look for security-related sentences
        sentences = content.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence.lower() for keyword in ['security', 'secure', 'protect', 'encrypt']):
                if len(sentence) > 20 and len(sentence) < 200:  # Reasonable length
                    considerations.append(sentence)
        
        return considerations[:5]  # Return top 5
    
    def _extract_compliance_requirements(self, content: str, framework: str) -> List[Dict[str, Any]]:
        """Extract compliance requirements from content"""
        requirements = []
        
        # Look for requirement patterns
        patterns = [
            r'(?:require|must|shall)[^.]*\.',
            r'(?:compliance|regulatory)[^.]*requirement[^.]*\.',
            r'(?:' + framework.lower() + r')[^.]*requirement[^.]*\.'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:2]:  # Limit per pattern
                if len(match.strip()) > 15:
                    requirements.append({
                        'description': match.strip(),
                        'framework': framework
                    })
        
        return requirements[:4]  # Return top 4
    
    def _extract_aws_services_from_content(self, content: str) -> List[str]:
        """Extract AWS service mentions from content"""
        services = set()
        content_lower = content.lower()
        
        for service, terms in self.service_mappings.items():
            if any(term.lower() in content_lower for term in terms):
                services.add(service.upper())
        
        return list(services)
    
    def _extract_implementation_guidance(self, content: str) -> List[str]:
        """Extract implementation guidance from content"""
        guidance = []
        
        # Look for implementation-related sentences
        sentences = content.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence.lower() for keyword in ['implement', 'configure', 'setup', 'enable']):
                if len(sentence) > 25 and len(sentence) < 250:  # Reasonable length
                    guidance.append(sentence)
        
        return guidance[:5]  # Return top 5
    
    def _is_cache_valid(self, cache_key: str, cache_dict: Dict) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in cache_dict:
            return False
        
        cache_entry = cache_dict[cache_key]
        current_time = datetime.now().timestamp()
        
        return (current_time - cache_entry['timestamp']) < self.cache_ttl
    
    def _get_fallback_documentation(self, topic: str) -> List[Dict[str, Any]]:
        """Provide fallback documentation when search fails"""
        return [{
            'title': f'AWS Security Best Practices for {topic}',
            'url': 'https://docs.aws.amazon.com/security/',
            'content': f'General AWS security guidance related to {topic}. Please refer to AWS documentation for specific implementation details.',
            'relevance_score': 0.5,
            'category': 'general'
        }]
    
    def _get_fallback_best_practices(self, service: str) -> Dict[str, Any]:
        """Provide fallback best practices when search fails"""
        return {
            'service': service,
            'practices': [
                {'description': f'Follow AWS security best practices for {service}', 'category': 'security'},
                {'description': 'Enable encryption at rest and in transit', 'category': 'encryption'},
                {'description': 'Implement least privilege access controls', 'category': 'access_control'}
            ],
            'compliance_frameworks': ['General AWS Security'],
            'security_considerations': [
                'Review and update security configurations regularly',
                'Monitor access patterns and unusual activities'
            ],
            'documentation_links': ['https://docs.aws.amazon.com/security/']
        }
    
    def _get_fallback_compliance_guidance(self, framework: str) -> Dict[str, Any]:
        """Provide fallback compliance guidance when search fails"""
        return {
            'framework': framework,
            'requirements': [
                {'description': f'Implement {framework} compliance controls', 'framework': framework},
                {'description': 'Maintain audit trails and documentation', 'framework': framework}
            ],
            'aws_services': ['IAM', 'CloudTrail', 'CloudWatch'],
            'implementation_guidance': [
                'Consult with compliance experts for specific requirements',
                'Review AWS compliance documentation regularly'
            ],
            'documentation_links': ['https://aws.amazon.com/compliance/']
        }