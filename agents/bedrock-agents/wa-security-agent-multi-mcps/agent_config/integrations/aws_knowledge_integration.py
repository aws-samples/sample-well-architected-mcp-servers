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
Handler for AWS Knowledge MCP Server providing documentation search and recommendations
Uses the actual MCP tools: aws___search_documentation, aws___read_documentation, aws___recommend
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from agent_config.interfaces import AWSKnowledgeIntegration, ToolResult
    from agent_config.utils.error_handling import ErrorHandler
    from agent_config.utils.logging_utils import get_logger
except ImportError:
    # Fallback for standalone testing
    import logging
    from abc import ABC, abstractmethod
    from typing import Any, Dict, List

    class AWSKnowledgeIntegration(ABC):
        @abstractmethod
        async def search_relevant_documentation(
            self, security_topic: str
        ) -> List[Dict[str, Any]]:
            pass

        @abstractmethod
        async def get_best_practices_for_service(
            self, aws_service: str
        ) -> Dict[str, Any]:
            pass

        @abstractmethod
        async def find_compliance_guidance(
            self, compliance_framework: str
        ) -> Dict[str, Any]:
            pass

        @abstractmethod
        def format_documentation_results(self, docs: List[Dict[str, Any]]) -> str:
            pass

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

    def get_logger(name):
        return logging.getLogger(name)

    class ErrorHandler:
        pass


logger = get_logger(__name__)


@dataclass
class DocumentationResult:
    """Represents a documentation search result"""

    title: str
    url: str
    content: str
    rank_order: int
    context: Optional[str] = None
    relevance_score: float = 0.0


@dataclass
class BestPracticesResult:
    """Represents best practices for an AWS service"""

    service: str
    practices: List[Dict[str, Any]]
    documentation_links: List[str]
    recommendations: List[str]
    compliance_notes: List[str]


@dataclass
class ComplianceGuidance:
    """Represents compliance guidance"""

    framework: str
    requirements: List[str]
    aws_services: List[str]
    documentation_links: List[str]
    implementation_steps: List[str]


class AWSKnowledgeIntegrationImpl(AWSKnowledgeIntegration):
    """
    Implementation of AWS Knowledge MCP Server integration
    Routes to actual MCP tools: aws___search_documentation, aws___read_documentation, aws___recommend
    """

    def __init__(self, mcp_orchestrator, cache_ttl: int = 3600):
        """
        Initialize AWS Knowledge integration

        Args:
            mcp_orchestrator: The MCP orchestrator for calling tools
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        self.mcp_orchestrator = mcp_orchestrator
        self.error_handler = ErrorHandler()
        self.cache_ttl = cache_ttl
        self._cache = {}

        # Security-related search terms for enhanced queries
        self.security_keywords = {
            "encryption": [
                "encryption",
                "kms",
                "ssl",
                "tls",
                "crypto",
                "at-rest",
                "in-transit",
            ],
            "access_control": [
                "iam",
                "access",
                "permissions",
                "roles",
                "policies",
                "rbac",
            ],
            "network_security": [
                "vpc",
                "security groups",
                "nacl",
                "firewall",
                "network",
                "subnets",
            ],
            "monitoring": [
                "cloudtrail",
                "cloudwatch",
                "logging",
                "monitoring",
                "audit",
                "alerts",
            ],
            "compliance": [
                "compliance",
                "gdpr",
                "hipaa",
                "sox",
                "pci",
                "iso",
                "regulatory",
            ],
            "data_protection": [
                "backup",
                "disaster recovery",
                "data protection",
                "retention",
                "versioning",
            ],
            "identity": [
                "authentication",
                "authorization",
                "mfa",
                "sso",
                "identity",
                "federation",
            ],
        }

        # AWS service mappings for better search targeting
        self.service_mappings = {
            "s3": ["Amazon S3", "Simple Storage Service", "object storage", "bucket"],
            "ec2": [
                "Amazon EC2",
                "Elastic Compute Cloud",
                "virtual machines",
                "instances",
            ],
            "rds": [
                "Amazon RDS",
                "Relational Database Service",
                "database",
                "mysql",
                "postgresql",
            ],
            "lambda": ["AWS Lambda", "serverless", "functions", "compute"],
            "iam": [
                "AWS IAM",
                "Identity and Access Management",
                "permissions",
                "users",
                "roles",
            ],
            "vpc": ["Amazon VPC", "Virtual Private Cloud", "networking", "subnets"],
            "cloudtrail": [
                "AWS CloudTrail",
                "audit logging",
                "api logging",
                "governance",
            ],
            "kms": [
                "AWS KMS",
                "Key Management Service",
                "encryption keys",
                "cryptography",
            ],
            "cloudwatch": [
                "Amazon CloudWatch",
                "monitoring",
                "metrics",
                "alarms",
                "logs",
            ],
            "route53": ["Amazon Route 53", "DNS", "domain", "routing"],
            "elb": ["Elastic Load Balancing", "load balancer", "ALB", "NLB", "CLB"],
            "cloudfront": ["Amazon CloudFront", "CDN", "content delivery", "edge"],
            "apigateway": ["Amazon API Gateway", "REST API", "HTTP API", "websocket"],
        }

        logger.info("AWS Knowledge Integration initialized")

    async def search_relevant_documentation(
        self, security_topic: str
    ) -> List[Dict[str, Any]]:
        """
        Search AWS documentation for relevant security guidance using aws___search_documentation

        Args:
            security_topic: The security topic to search for

        Returns:
            List of relevant documentation with metadata
        """
        try:
            # Check cache first
            cache_key = f"search_{security_topic.lower()}"
            if self._is_cache_valid(cache_key):
                logger.info(
                    f"Returning cached documentation for topic: {security_topic}"
                )
                return self._cache[cache_key]["data"]

            start_time = time.time()

            # Enhance search query with related keywords
            enhanced_query = self._enhance_search_query(security_topic)

            # Call the aws___search_documentation MCP tool
            result = await self.mcp_orchestrator.call_knowledge_tool(
                "aws___search_documentation",
                {"search_phrase": enhanced_query, "limit": 20},
            )

            execution_time = time.time() - start_time

            if result and result.success:
                # Process the search results
                search_results = result.data
                processed_docs = self._process_search_results(
                    search_results, security_topic
                )

                # Cache results
                self._cache[cache_key] = {
                    "data": processed_docs,
                    "timestamp": datetime.now().timestamp(),
                }

                logger.info(
                    f"Found {len(processed_docs)} relevant documents for topic: {security_topic}"
                )
                return processed_docs
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(f"Failed to search documentation: {error_msg}")
                return self._get_fallback_documentation(security_topic)

        except Exception as e:
            logger.error(
                f"Error searching documentation for topic '{security_topic}': {e}"
            )
            return self._get_fallback_documentation(security_topic)

    async def get_best_practices_for_service(self, aws_service: str) -> Dict[str, Any]:
        """
        Get best practices for specific AWS service using documentation search

        Args:
            aws_service: AWS service name (e.g., 's3', 'ec2', 'rds')

        Returns:
            Best practices information for the service
        """
        try:
            # Check cache first
            cache_key = f"practices_{aws_service.lower()}"
            if self._is_cache_valid(cache_key):
                logger.info(
                    f"Returning cached best practices for service: {aws_service}"
                )
                return self._cache[cache_key]["data"]

            start_time = time.time()

            # Build search query for best practices
            service_terms = self._get_service_search_terms(aws_service)
            search_query = f"{service_terms} security best practices configuration"

            # Search for best practices documentation
            result = await self.mcp_orchestrator.call_knowledge_tool(
                "aws___search_documentation",
                {"search_phrase": search_query, "limit": 15},
            )

            execution_time = time.time() - start_time

            if result and result.success:
                search_results = result.data

                # Process results into structured best practices
                best_practices = self._extract_best_practices_from_results(
                    search_results, aws_service
                )

                # Try to get additional recommendations
                try:
                    # Get the first documentation URL for recommendations
                    if search_results and len(search_results) > 0:
                        first_doc_url = search_results[0].get("url", "")
                        if first_doc_url:
                            recommendations = await self._get_recommendations_for_url(
                                first_doc_url
                            )
                            if recommendations:
                                best_practices["related_documentation"] = (
                                    recommendations
                                )
                except Exception as e:
                    logger.warning(f"Failed to get recommendations: {e}")

                # Cache results
                self._cache[cache_key] = {
                    "data": best_practices,
                    "timestamp": datetime.now().timestamp(),
                }

                logger.info(f"Retrieved best practices for service: {aws_service}")
                return best_practices
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(f"Failed to get best practices: {error_msg}")
                return self._get_fallback_best_practices(aws_service)

        except Exception as e:
            logger.error(
                f"Error getting best practices for service '{aws_service}': {e}"
            )
            return self._get_fallback_best_practices(aws_service)

    async def find_compliance_guidance(
        self, compliance_framework: str
    ) -> Dict[str, Any]:
        """
        Find compliance and regulatory guidance using documentation search

        Args:
            compliance_framework: Compliance framework (e.g., 'GDPR', 'HIPAA', 'SOX')

        Returns:
            Compliance guidance information
        """
        try:
            # Check cache first
            cache_key = f"compliance_{compliance_framework.lower()}"
            if self._is_cache_valid(cache_key):
                logger.info(
                    f"Returning cached compliance guidance for: {compliance_framework}"
                )
                return self._cache[cache_key]["data"]

            start_time = time.time()

            # Search for compliance-specific documentation
            search_query = (
                f"AWS {compliance_framework} compliance security requirements"
            )

            result = await self.mcp_orchestrator.call_knowledge_tool(
                "aws___search_documentation",
                {"search_phrase": search_query, "limit": 15},
            )

            execution_time = time.time() - start_time

            if result and result.success:
                search_results = result.data

                # Process results into structured compliance guidance
                compliance_guide = self._extract_compliance_guidance_from_results(
                    search_results, compliance_framework
                )

                # Cache results
                self._cache[cache_key] = {
                    "data": compliance_guide,
                    "timestamp": datetime.now().timestamp(),
                }

                logger.info(
                    f"Retrieved compliance guidance for: {compliance_framework}"
                )
                return compliance_guide
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(f"Failed to get compliance guidance: {error_msg}")
                return self._get_fallback_compliance_guidance(compliance_framework)

        except Exception as e:
            logger.error(
                f"Error finding compliance guidance for '{compliance_framework}': {e}"
            )
            return self._get_fallback_compliance_guidance(compliance_framework)

    async def read_documentation_page(
        self, url: str, max_length: int = 5000
    ) -> Dict[str, Any]:
        """
        Read a specific AWS documentation page using aws___read_documentation

        Args:
            url: URL of the AWS documentation page
            max_length: Maximum content length to retrieve

        Returns:
            Dictionary with page content and metadata
        """
        try:
            start_time = time.time()

            # Call the aws___read_documentation MCP tool
            result = await self.mcp_orchestrator.call_knowledge_tool(
                "aws___read_documentation", {"url": url, "max_length": max_length}
            )

            execution_time = time.time() - start_time

            if result and result.success:
                content_data = result.data

                logger.info(f"Successfully read documentation page: {url}")

                return {
                    "success": True,
                    "url": url,
                    "content": content_data,
                    "execution_time": execution_time,
                    "metadata": {
                        "mcp_server": "aws-knowledge-mcp-server",
                        "tool_used": "aws___read_documentation",
                    },
                }
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(f"Failed to read documentation page: {error_msg}")

                return {
                    "success": False,
                    "url": url,
                    "error": error_msg,
                    "execution_time": execution_time,
                }

        except Exception as e:
            logger.error(f"Error reading documentation page '{url}': {e}")
            return {"success": False, "url": url, "error": str(e)}

    async def get_recommendations_for_page(self, url: str) -> Dict[str, Any]:
        """
        Get content recommendations for a documentation page using aws___recommend

        Args:
            url: URL of the AWS documentation page

        Returns:
            Dictionary with recommendations
        """
        try:
            start_time = time.time()

            # Call the aws___recommend MCP tool
            result = await self.mcp_orchestrator.call_knowledge_tool(
                "aws___recommend", {"url": url}
            )

            execution_time = time.time() - start_time

            if result and result.success:
                recommendations_data = result.data

                logger.info(f"Successfully got recommendations for page: {url}")

                return {
                    "success": True,
                    "url": url,
                    "recommendations": recommendations_data,
                    "execution_time": execution_time,
                    "metadata": {
                        "mcp_server": "aws-knowledge-mcp-server",
                        "tool_used": "aws___recommend",
                    },
                }
            else:
                error_msg = (
                    result.error_message if result else "No result from MCP tool"
                )
                logger.error(f"Failed to get recommendations: {error_msg}")

                return {
                    "success": False,
                    "url": url,
                    "error": error_msg,
                    "execution_time": execution_time,
                }

        except Exception as e:
            logger.error(f"Error getting recommendations for page '{url}': {e}")
            return {"success": False, "url": url, "error": str(e)}

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

        # Sort by relevance if available
        sorted_docs = sorted(
            docs, key=lambda x: x.get("relevance_score", x.get("rank_order", 999))
        )

        formatted_sections.append("## AWS Documentation Results\n")

        for i, doc in enumerate(sorted_docs[:5], 1):  # Limit to top 5
            title = doc.get("title", "Untitled Document")
            url = doc.get("url", "")
            context = doc.get("context", doc.get("content", ""))
            rank = doc.get("rank_order", i)

            formatted_sections.append(f"### {i}. {title}")

            if context:
                # Truncate context if too long
                preview = context[:300] + "..." if len(context) > 300 else context
                formatted_sections.append(f"{preview}")

            if url:
                formatted_sections.append(f"📖 [Read full documentation]({url})")

            formatted_sections.append(f"*Relevance rank: {rank}*\n")

        # Add summary
        total_docs = len(docs)
        formatted_sections.append(
            f"**Summary:** Found {total_docs} relevant documentation pages."
        )

        return "\n".join(formatted_sections)

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
        enhanced_terms.extend(["AWS", "security"])

        return " ".join(set(enhanced_terms))  # Remove duplicates

    def _get_service_search_terms(self, service: str) -> str:
        """Get enhanced search terms for AWS service"""
        service_lower = service.lower()

        if service_lower in self.service_mappings:
            return " ".join(self.service_mappings[service_lower])

        return service

    def _process_search_results(self, results: Any, topic: str) -> List[Dict[str, Any]]:
        """Process raw search results from MCP tool"""
        processed_docs = []

        if isinstance(results, list):
            for result in results:
                if isinstance(result, dict):
                    doc_info = {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("context", ""),
                        "rank_order": result.get("rank_order", 999),
                        "relevance_score": self._calculate_relevance_score(
                            result, topic
                        ),
                    }
                    processed_docs.append(doc_info)

        # Sort by rank order (lower is better)
        processed_docs.sort(key=lambda x: x["rank_order"])

        return processed_docs

    def _extract_best_practices_from_results(
        self, results: List[Dict[str, Any]], service: str
    ) -> Dict[str, Any]:
        """Extract structured best practices from search results"""
        practices = []
        documentation_links = []
        recommendations = []
        compliance_notes = []

        for result in results:
            title = result.get("title", "")
            url = result.get("url", "")
            context = result.get("context", "")

            # Extract practices from content
            if "best practice" in context.lower() or "recommend" in context.lower():
                practice_text = self._extract_practice_text(context)
                if practice_text:
                    practices.append(
                        {"description": practice_text, "source": title, "url": url}
                    )

            # Extract recommendations
            if "should" in context.lower() or "must" in context.lower():
                recommendation_text = self._extract_recommendation_text(context)
                if recommendation_text:
                    recommendations.append(recommendation_text)

            # Extract compliance information
            if any(
                compliance in context.lower()
                for compliance in ["compliance", "regulatory", "gdpr", "hipaa"]
            ):
                compliance_text = self._extract_compliance_text(context)
                if compliance_text:
                    compliance_notes.append(compliance_text)

            if url:
                documentation_links.append(url)

        return {
            "service": service,
            "practices": practices[:8],  # Top 8 practices
            "documentation_links": documentation_links[:5],  # Top 5 links
            "recommendations": recommendations[:6],  # Top 6 recommendations
            "compliance_notes": compliance_notes[:4],  # Top 4 compliance notes
            "search_timestamp": datetime.now().isoformat(),
        }

    def _extract_compliance_guidance_from_results(
        self, results: List[Dict[str, Any]], framework: str
    ) -> Dict[str, Any]:
        """Extract structured compliance guidance from search results"""
        requirements = []
        aws_services = set()
        documentation_links = []
        implementation_steps = []

        for result in results:
            title = result.get("title", "")
            url = result.get("url", "")
            context = result.get("context", "")

            # Extract requirements
            if "requirement" in context.lower() or "must" in context.lower():
                requirement_text = self._extract_requirement_text(context, framework)
                if requirement_text:
                    requirements.append(requirement_text)

            # Extract AWS services mentioned
            for service, terms in self.service_mappings.items():
                if any(term.lower() in context.lower() for term in terms):
                    aws_services.add(service.upper())

            # Extract implementation steps
            if "implement" in context.lower() or "configure" in context.lower():
                implementation_text = self._extract_implementation_text(context)
                if implementation_text:
                    implementation_steps.append(implementation_text)

            if url:
                documentation_links.append(url)

        return {
            "framework": framework,
            "requirements": requirements[:6],  # Top 6 requirements
            "aws_services": list(aws_services),
            "documentation_links": documentation_links[:5],  # Top 5 links
            "implementation_steps": implementation_steps[:8],  # Top 8 steps
            "search_timestamp": datetime.now().isoformat(),
        }

    def _calculate_relevance_score(self, result: Dict[str, Any], topic: str) -> float:
        """Calculate relevance score for a documentation result"""
        score = 0.0
        content = (result.get("context", "") + " " + result.get("title", "")).lower()
        topic_lower = topic.lower()

        # Title match bonus
        if topic_lower in result.get("title", "").lower():
            score += 0.3

        # Content relevance
        topic_words = topic_lower.split()
        content_words = content.split()

        matches = sum(1 for word in topic_words if word in content_words)
        if topic_words:
            score += (matches / len(topic_words)) * 0.4

        # Security keyword bonus
        security_terms = [
            "security",
            "best practice",
            "compliance",
            "encryption",
            "access control",
        ]
        security_matches = sum(1 for term in security_terms if term in content)
        score += min(security_matches * 0.1, 0.3)

        # Rank order penalty (lower rank is better)
        rank = result.get("rank_order", 999)
        if rank <= 5:
            score += 0.2
        elif rank <= 10:
            score += 0.1

        return min(score, 1.0)  # Cap at 1.0

    def _extract_practice_text(self, content: str) -> str:
        """Extract best practice text from content"""
        sentences = content.split(".")
        for sentence in sentences:
            if any(
                keyword in sentence.lower()
                for keyword in ["best practice", "recommend", "should"]
            ):
                if len(sentence.strip()) > 20 and len(sentence.strip()) < 200:
                    return sentence.strip()
        return ""

    def _extract_recommendation_text(self, content: str) -> str:
        """Extract recommendation text from content"""
        sentences = content.split(".")
        for sentence in sentences:
            if any(
                keyword in sentence.lower()
                for keyword in ["should", "must", "recommend"]
            ):
                if len(sentence.strip()) > 15 and len(sentence.strip()) < 150:
                    return sentence.strip()
        return ""

    def _extract_compliance_text(self, content: str) -> str:
        """Extract compliance-related text from content"""
        sentences = content.split(".")
        for sentence in sentences:
            if any(
                keyword in sentence.lower()
                for keyword in ["compliance", "regulatory", "requirement"]
            ):
                if len(sentence.strip()) > 20 and len(sentence.strip()) < 200:
                    return sentence.strip()
        return ""

    def _extract_requirement_text(self, content: str, framework: str) -> str:
        """Extract requirement text from content"""
        sentences = content.split(".")
        for sentence in sentences:
            if any(
                keyword in sentence.lower()
                for keyword in ["requirement", "must", framework.lower()]
            ):
                if len(sentence.strip()) > 20 and len(sentence.strip()) < 200:
                    return sentence.strip()
        return ""

    def _extract_implementation_text(self, content: str) -> str:
        """Extract implementation text from content"""
        sentences = content.split(".")
        for sentence in sentences:
            if any(
                keyword in sentence.lower()
                for keyword in ["implement", "configure", "setup", "enable"]
            ):
                if len(sentence.strip()) > 25 and len(sentence.strip()) < 200:
                    return sentence.strip()
        return ""

    async def _get_recommendations_for_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get recommendations for a specific URL"""
        try:
            result = await self.get_recommendations_for_page(url)
            if result["success"]:
                return result["recommendations"]
        except Exception as e:
            logger.warning(f"Failed to get recommendations for {url}: {e}")
        return None

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self._cache:
            return False

        cache_entry = self._cache[cache_key]
        current_time = datetime.now().timestamp()

        return (current_time - cache_entry["timestamp"]) < self.cache_ttl

    def _get_fallback_documentation(self, topic: str) -> List[Dict[str, Any]]:
        """Provide fallback documentation when search fails"""
        return [
            {
                "title": f"AWS Security Best Practices for {topic}",
                "url": "https://docs.aws.amazon.com/security/",
                "content": f"General AWS security guidance for {topic}. Please refer to the AWS Security documentation for comprehensive information.",
                "rank_order": 1,
                "relevance_score": 0.5,
            }
        ]

    def _get_fallback_best_practices(self, service: str) -> Dict[str, Any]:
        """Provide fallback best practices when search fails"""
        return {
            "service": service,
            "practices": [
                {
                    "description": f"Follow AWS Well-Architected Framework security pillar for {service}",
                    "source": "AWS Well-Architected Framework",
                    "url": "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/",
                }
            ],
            "documentation_links": [f"https://docs.aws.amazon.com/{service}/"],
            "recommendations": [
                f"Review {service} security best practices in AWS documentation"
            ],
            "compliance_notes": [
                "Ensure compliance with your organization's security policies"
            ],
            "search_timestamp": datetime.now().isoformat(),
            "fallback": True,
        }

    def _get_fallback_compliance_guidance(self, framework: str) -> Dict[str, Any]:
        """Provide fallback compliance guidance when search fails"""
        return {
            "framework": framework,
            "requirements": [
                f"Review {framework} compliance requirements for AWS services"
            ],
            "aws_services": ["IAM", "CloudTrail", "CloudWatch", "KMS"],
            "documentation_links": ["https://aws.amazon.com/compliance/"],
            "implementation_steps": [
                f"Consult AWS compliance documentation for {framework} implementation"
            ],
            "search_timestamp": datetime.now().isoformat(),
            "fallback": True,
        }
