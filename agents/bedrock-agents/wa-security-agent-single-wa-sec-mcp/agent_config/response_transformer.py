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
# COPYRIGHT HOLDERS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Response Transformer for Security Agent
Transforms raw MCP server responses into comprehensive, human-readable information
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SecurityResponseTransformer:
    """
    Transforms raw MCP server responses into comprehensive, human-readable security assessments
    """
    
    def __init__(self):
        self.risk_levels = {
            'CRITICAL': {'emoji': '🔴', 'color': '#dc3545', 'priority': 1},
            'HIGH': {'emoji': '🟠', 'color': '#fd7e14', 'priority': 2},
            'MEDIUM': {'emoji': '🟡', 'color': '#ffc107', 'priority': 3},
            'LOW': {'emoji': '🟢', 'color': '#28a745', 'priority': 4},
            'INFO': {'emoji': '🔵', 'color': '#17a2b8', 'priority': 5}
        }
        
        self.service_icons = {
            'guardduty': '🛡️',
            'securityhub': '🔒',
            'inspector': '🔍',
            'accessanalyzer': '👁️',
            'macie': '📊',
            'trustedadvisor': '💡',
            's3': '🪣',
            'ebs': '💾',
            'rds': '🗄️',
            'dynamodb': '⚡',
            'elb': '⚖️',
            'apigateway': '🌐',
            'cloudfront': '☁️'
        }
    
    def transform_response(self, tool_name: str, raw_response: str, user_query: str = "") -> str:
        """
        Transform raw MCP response into comprehensive human-readable format
        """
        try:
            # Parse JSON response if it's a string
            if isinstance(raw_response, str):
                try:
                    response_data = json.loads(raw_response)
                except json.JSONDecodeError:
                    # If not JSON, treat as plain text
                    return self._format_plain_text_response(tool_name, raw_response, user_query)
            else:
                response_data = raw_response
            
            # Route to specific transformer based on tool name
            transformer_map = {
                'CheckSecurityServices': self._transform_security_services,
                'CheckStorageEncryption': self._transform_storage_encryption,
                'CheckNetworkSecurity': self._transform_network_security,
                'ListServicesInRegion': self._transform_services_list,
                'GetSecurityFindings': self._transform_security_findings,
                'GetStoredSecurityContext': self._transform_stored_context
            }
            
            transformer = transformer_map.get(tool_name, self._transform_generic)
            return transformer(response_data, user_query)
            
        except Exception as e:
            logger.error(f"Error transforming response for {tool_name}: {e}")
            return self._format_error_response(tool_name, str(e), raw_response)
    
    def _transform_security_services(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Transform CheckSecurityServices response"""
        region = data.get('region', 'Unknown')
        services_checked = data.get('services_checked', [])
        all_enabled = data.get('all_enabled', False)
        service_statuses = data.get('service_statuses', {})
        
        # Header
        status_emoji = "✅" if all_enabled else "⚠️"
        header = f"## {status_emoji} Security Services Assessment - {region.upper()}\n\n"
        
        # Overall status
        overall_status = "🟢 **All security services are properly configured**" if all_enabled else "🟡 **Some security services need attention**"
        header += f"{overall_status}\n\n"
        
        # Service details
        enabled_services = []
        disabled_services = []
        
        for service, status_info in service_statuses.items():
            icon = self.service_icons.get(service.lower(), '🔧')
            service_name = service.replace('_', ' ').title()
            
            if isinstance(status_info, dict):
                enabled = status_info.get('enabled', False)
                details = status_info.get('details', '')
                
                if enabled:
                    enabled_services.append(f"  {icon} **{service_name}**: ✅ Active {details}")
                else:
                    disabled_services.append(f"  {icon} **{service_name}**: ❌ Not Active {details}")
            else:
                # Simple boolean status
                if status_info:
                    enabled_services.append(f"  {icon} **{service_name}**: ✅ Active")
                else:
                    disabled_services.append(f"  {icon} **{service_name}**: ❌ Not Active")
        
        result = header
        
        if enabled_services:
            result += "### ✅ Active Security Services\n"
            result += "\n".join(enabled_services) + "\n\n"
        
        if disabled_services:
            result += "### ⚠️ Services Requiring Attention\n"
            result += "\n".join(disabled_services) + "\n\n"
            
            # Add recommendations
            result += "### 🎯 Recommendations\n"
            for service in [s.split('**')[1].split('**')[0] for s in disabled_services]:
                result += f"- Enable {service} for enhanced security monitoring\n"
            result += "\n"
        
        # Add security score
        enabled_count = len(enabled_services)
        total_count = len(services_checked)
        score = (enabled_count / total_count * 100) if total_count > 0 else 0
        
        result += f"### 📊 Security Score: {score:.0f}% ({enabled_count}/{total_count} services active)\n\n"
        
        # Add next steps
        if not all_enabled:
            result += "### 🚀 Next Steps\n"
            result += "1. Review and enable missing security services\n"
            result += "2. Configure appropriate alerting and monitoring\n"
            result += "3. Regularly review security service findings\n"
        
        return result
    
    def _transform_storage_encryption(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Transform CheckStorageEncryption response"""
        region = data.get('region', 'Unknown')
        services_checked = data.get('services_checked', [])
        encryption_summary = data.get('encryption_summary', {})
        
        header = f"## 🔐 Storage Encryption Assessment - {region.upper()}\n\n"
        
        total_resources = 0
        encrypted_resources = 0
        
        result = header
        
        for service, service_data in encryption_summary.items():
            if not isinstance(service_data, dict):
                continue
                
            icon = self.service_icons.get(service.lower(), '💾')
            service_name = service.upper()
            
            resources = service_data.get('resources', [])
            service_total = len(resources)
            service_encrypted = sum(1 for r in resources if r.get('encrypted', False))
            
            total_resources += service_total
            encrypted_resources += service_encrypted
            
            if service_total > 0:
                encryption_rate = (service_encrypted / service_total * 100)
                status_emoji = "✅" if encryption_rate == 100 else "⚠️" if encryption_rate > 50 else "❌"
                
                result += f"### {icon} {service_name} Encryption Status\n"
                result += f"{status_emoji} **{service_encrypted}/{service_total} resources encrypted** ({encryption_rate:.0f}%)\n\n"
                
                # List unencrypted resources
                unencrypted = [r for r in resources if not r.get('encrypted', False)]
                if unencrypted:
                    result += "**Unencrypted Resources:**\n"
                    for resource in unencrypted[:5]:  # Limit to first 5
                        resource_id = resource.get('id', 'Unknown')
                        result += f"- `{resource_id}`\n"
                    if len(unencrypted) > 5:
                        result += f"- ... and {len(unencrypted) - 5} more\n"
                    result += "\n"
        
        # Overall encryption score
        overall_rate = (encrypted_resources / total_resources * 100) if total_resources > 0 else 0
        score_emoji = "🟢" if overall_rate >= 90 else "🟡" if overall_rate >= 70 else "🔴"
        
        result += f"## {score_emoji} Overall Encryption Score: {overall_rate:.0f}%\n"
        result += f"**{encrypted_resources}/{total_resources} total resources encrypted**\n\n"
        
        # Recommendations
        if overall_rate < 100:
            result += "### 🎯 Recommendations\n"
            result += "- Enable encryption for all unencrypted storage resources\n"
            result += "- Use AWS KMS for centralized key management\n"
            result += "- Implement encryption-at-rest policies\n"
            result += "- Regular encryption compliance audits\n\n"
        
        return result
    
    def _transform_network_security(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Transform CheckNetworkSecurity response"""
        region = data.get('region', 'Unknown')
        network_summary = data.get('network_summary', {})
        
        header = f"## 🌐 Network Security Assessment - {region.upper()}\n\n"
        result = header
        
        total_resources = 0
        secure_resources = 0
        
        for service, service_data in network_summary.items():
            if not isinstance(service_data, dict):
                continue
                
            icon = self.service_icons.get(service.lower(), '🌐')
            service_name = service.upper()
            
            resources = service_data.get('resources', [])
            service_total = len(resources)
            service_secure = sum(1 for r in resources if r.get('secure', False))
            
            total_resources += service_total
            secure_resources += service_secure
            
            if service_total > 0:
                security_rate = (service_secure / service_total * 100)
                status_emoji = "✅" if security_rate == 100 else "⚠️" if security_rate > 50 else "❌"
                
                result += f"### {icon} {service_name} Security Status\n"
                result += f"{status_emoji} **{service_secure}/{service_total} resources secure** ({security_rate:.0f}%)\n\n"
                
                # List insecure resources
                insecure = [r for r in resources if not r.get('secure', False)]
                if insecure:
                    result += "**Resources needing attention:**\n"
                    for resource in insecure[:5]:
                        resource_id = resource.get('id', 'Unknown')
                        issue = resource.get('issue', 'Security configuration needed')
                        result += f"- `{resource_id}`: {issue}\n"
                    if len(insecure) > 5:
                        result += f"- ... and {len(insecure) - 5} more\n"
                    result += "\n"
        
        # Overall security score
        overall_rate = (secure_resources / total_resources * 100) if total_resources > 0 else 0
        score_emoji = "🟢" if overall_rate >= 90 else "🟡" if overall_rate >= 70 else "🔴"
        
        result += f"## {score_emoji} Overall Network Security Score: {overall_rate:.0f}%\n"
        result += f"**{secure_resources}/{total_resources} total resources secure**\n\n"
        
        return result
    
    def _transform_services_list(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Transform ListServicesInRegion response"""
        region = data.get('region', 'Unknown')
        services = data.get('services', [])
        
        header = f"## 📋 AWS Services Inventory - {region.upper()}\n\n"
        result = header
        
        if not services:
            result += "No AWS services found in this region.\n"
            return result
        
        # Group services by category
        service_categories = {
            'Compute': ['ec2', 'lambda', 'ecs', 'eks', 'batch'],
            'Storage': ['s3', 'ebs', 'efs', 'fsx'],
            'Database': ['rds', 'dynamodb', 'redshift', 'elasticache'],
            'Networking': ['vpc', 'elb', 'cloudfront', 'apigateway', 'route53'],
            'Security': ['iam', 'guardduty', 'securityhub', 'inspector', 'kms'],
            'Monitoring': ['cloudwatch', 'cloudtrail', 'config', 'xray'],
            'Other': []
        }
        
        categorized_services = {cat: [] for cat in service_categories.keys()}
        
        for service in services:
            service_name = service.lower()
            categorized = False
            
            for category, service_list in service_categories.items():
                if category == 'Other':
                    continue
                if any(svc in service_name for svc in service_list):
                    categorized_services[category].append(service)
                    categorized = True
                    break
            
            if not categorized:
                categorized_services['Other'].append(service)
        
        # Display categorized services
        for category, service_list in categorized_services.items():
            if service_list:
                result += f"### {category} Services ({len(service_list)})\n"
                for service in sorted(service_list):
                    icon = self.service_icons.get(service.lower(), '🔧')
                    result += f"- {icon} {service}\n"
                result += "\n"
        
        result += f"**Total: {len(services)} services active in {region}**\n"
        
        return result
    
    def _transform_security_findings(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Transform GetSecurityFindings response"""
        service = data.get('service', 'Unknown')
        findings = data.get('findings', [])
        region = data.get('region', 'Unknown')
        
        header = f"## 🚨 Security Findings - {service.upper()} ({region})\n\n"
        result = header
        
        if not findings:
            result += "✅ **No active security findings found**\n"
            result += "Your environment appears to be secure based on current scans.\n"
            return result
        
        # Group findings by severity
        severity_groups = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': [], 'INFO': []}
        
        for finding in findings:
            severity = finding.get('severity', 'UNKNOWN').upper()
            if severity not in severity_groups:
                severity = 'INFO'
            severity_groups[severity].append(finding)
        
        # Display findings by severity
        total_findings = len(findings)
        result += f"**{total_findings} security findings require attention**\n\n"
        
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
            findings_list = severity_groups[severity]
            if not findings_list:
                continue
                
            risk_info = self.risk_levels.get(severity, self.risk_levels['INFO'])
            result += f"### {risk_info['emoji']} {severity} Severity ({len(findings_list)} findings)\n"
            
            for i, finding in enumerate(findings_list[:3]):  # Show first 3 per severity
                title = finding.get('title', 'Security Finding')
                description = finding.get('description', 'No description available')
                resource = finding.get('resource', 'Unknown resource')
                
                result += f"**{i+1}. {title}**\n"
                result += f"   - Resource: `{resource}`\n"
                result += f"   - Issue: {description[:100]}{'...' if len(description) > 100 else ''}\n"
            
            if len(findings_list) > 3:
                result += f"   - ... and {len(findings_list) - 3} more {severity.lower()} findings\n"
            result += "\n"
        
        # Add recommendations
        critical_high = len(severity_groups['CRITICAL']) + len(severity_groups['HIGH'])
        if critical_high > 0:
            result += "### 🚨 Immediate Action Required\n"
            result += f"- **{critical_high} critical/high severity findings** need immediate attention\n"
            result += "- Review and remediate these findings as soon as possible\n"
            result += "- Consider implementing automated remediation where appropriate\n\n"
        
        return result
    
    def _transform_stored_context(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Transform GetStoredSecurityContext response"""
        context_data = data.get('context', {})
        
        if not context_data:
            return "📋 **No stored security context available**\n\nRun security assessments to build context.\n"
        
        result = "## 📋 Stored Security Context\n\n"
        
        for key, value in context_data.items():
            if isinstance(value, dict):
                result += f"### {key.replace('_', ' ').title()}\n"
                result += f"```json\n{json.dumps(value, indent=2)}\n```\n\n"
            else:
                result += f"**{key.replace('_', ' ').title()}**: {value}\n"
        
        return result
    
    def _transform_generic(self, data: Dict[str, Any], user_query: str = "") -> str:
        """Generic transformer for unknown tool responses"""
        result = "## 🔧 Security Assessment Results\n\n"
        
        if isinstance(data, dict):
            for key, value in data.items():
                result += f"**{key.replace('_', ' ').title()}**: "
                if isinstance(value, (dict, list)):
                    result += f"\n```json\n{json.dumps(value, indent=2)}\n```\n\n"
                else:
                    result += f"{value}\n"
        else:
            result += f"{data}\n"
        
        return result
    
    def _format_plain_text_response(self, tool_name: str, response: str, user_query: str = "") -> str:
        """Format plain text responses"""
        result = f"## 🔧 {tool_name} Results\n\n"
        
        # Clean up the response
        cleaned_response = response.strip()
        
        # Add some basic formatting
        lines = cleaned_response.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append("")
                continue
                
            # Make headers bold
            if line.endswith(':') and len(line) < 50:
                formatted_lines.append(f"**{line}**")
            # Add bullet points for list items
            elif line.startswith('- ') or line.startswith('* '):
                formatted_lines.append(line)
            # Regular text
            else:
                formatted_lines.append(line)
        
        result += '\n'.join(formatted_lines)
        return result
    
    def _format_error_response(self, tool_name: str, error: str, raw_response: str = "") -> str:
        """Format error responses"""
        result = f"## ❌ Error in {tool_name}\n\n"
        result += f"**Error**: {error}\n\n"
        
        if raw_response:
            result += "**Raw Response**:\n"
            result += f"```\n{raw_response[:500]}{'...' if len(raw_response) > 500 else ''}\n```\n"
        
        result += "\n**Troubleshooting**:\n"
        result += "- Check AWS credentials and permissions\n"
        result += "- Verify the target region is accessible\n"
        result += "- Ensure required AWS services are available in the region\n"
        
        return result
    
    def create_executive_summary(self, all_responses: List[Dict[str, Any]]) -> str:
        """Create an executive summary from multiple tool responses"""
        summary = "# 📊 Security Assessment Executive Summary\n\n"
        
        # Analyze all responses to create high-level insights
        total_issues = 0
        critical_issues = 0
        services_checked = set()
        
        for response in all_responses:
            tool_name = response.get('tool_name', '')
            data = response.get('data', {})
            
            if tool_name == 'CheckSecurityServices':
                services_checked.update(data.get('services_checked', []))
                if not data.get('all_enabled', True):
                    total_issues += 1
            
            elif tool_name == 'GetSecurityFindings':
                findings = data.get('findings', [])
                for finding in findings:
                    severity = finding.get('severity', '').upper()
                    if severity in ['CRITICAL', 'HIGH']:
                        critical_issues += 1
                    total_issues += 1
        
        # Overall security posture
        if critical_issues == 0 and total_issues == 0:
            posture = "🟢 **STRONG** - No critical issues identified"
        elif critical_issues == 0:
            posture = "🟡 **MODERATE** - Some improvements needed"
        else:
            posture = "🔴 **NEEDS ATTENTION** - Critical issues require immediate action"
        
        summary += f"## Overall Security Posture: {posture}\n\n"
        
        # Key metrics
        summary += "### 📈 Key Metrics\n"
        summary += f"- **Services Assessed**: {len(services_checked)}\n"
        summary += f"- **Total Issues**: {total_issues}\n"
        summary += f"- **Critical Issues**: {critical_issues}\n\n"
        
        # Top recommendations
        summary += "### 🎯 Top Recommendations\n"
        if critical_issues > 0:
            summary += f"1. **Immediate**: Address {critical_issues} critical security findings\n"
        if total_issues > critical_issues:
            summary += f"2. **Short-term**: Resolve {total_issues - critical_issues} additional security issues\n"
        summary += "3. **Ongoing**: Implement continuous security monitoring\n"
        summary += "4. **Governance**: Regular security assessments and reviews\n\n"
        
        return summary