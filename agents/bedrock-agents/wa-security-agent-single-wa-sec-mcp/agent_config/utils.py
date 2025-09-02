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
Utility functions for Security Agent
"""

import boto3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_ssm_parameter(parameter_name: str, region: str = "us-east-1") -> Optional[str]:
    """Get parameter from AWS Systems Manager Parameter Store"""
    try:
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(Name=parameter_name)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.error(f"Failed to get SSM parameter {parameter_name}: {e}")
        return None


def get_secret_value(secret_name: str, region: str = "us-east-1") -> Optional[str]:
    """Get secret from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client("secretsmanager", region_name=region)
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        return None


def format_security_response(data: dict) -> str:
    """Format security tool response for better readability"""
    if "services_checked" in data:
        # Security services response
        output = []
        output.append(
            f"🔒 **Security Services Assessment - {data.get('region', 'Unknown')}**"
        )

        services_checked = data.get("services_checked", [])
        all_enabled = data.get("all_enabled", False)

        output.append(f"📊 Services Checked: {', '.join(services_checked)}")
        output.append(f"✅ All Enabled: {'Yes' if all_enabled else 'No'}")
        output.append("")

        # Service statuses
        service_statuses = data.get("service_statuses", {})
        for service, status in service_statuses.items():
            enabled = status.get("enabled", False)
            status_icon = "✅" if enabled else "❌"
            output.append(
                f"{status_icon} **{service.upper()}**: {'Enabled' if enabled else 'Disabled'}"
            )

            if not enabled and "setup_instructions" in status:
                output.append("   💡 Setup instructions available")

        # Summary
        if "summary" in data:
            output.append("")
            output.append(f"📝 **Summary**: {data['summary']}")

        return "\n".join(output)

    elif "resources_checked" in data:
        # Storage/Network security response
        output = []
        output.append(f"🔐 **Security Assessment - {data.get('region', 'Unknown')}**")

        total_resources = data.get("resources_checked", 0)
        compliant = data.get("compliant_resources", 0)
        non_compliant = data.get("non_compliant_resources", 0)

        output.append(f"📊 Resources Checked: {total_resources}")
        output.append(f"✅ Compliant: {compliant}")
        output.append(f"❌ Non-Compliant: {non_compliant}")

        if total_resources > 0:
            compliance_rate = (compliant / total_resources) * 100
            output.append(f"📈 Compliance Rate: {compliance_rate:.1f}%")

        return "\n".join(output)

    elif "services" in data:
        # Service listing response
        output = []
        output.append(f"📋 **AWS Services in {data.get('region', 'Unknown')}**")

        services = data.get("services", [])
        total_resources = data.get("total_resources", 0)

        output.append(f"🔧 Services Found: {len(services)}")
        output.append(f"📦 Total Resources: {total_resources}")

        if services:
            output.append("\n**Active Services:**")
            for service in services[:10]:  # Show first 10
                output.append(f"• {service}")
            if len(services) > 10:
                output.append(f"... and {len(services) - 10} more")

        return "\n".join(output)

    else:
        # Generic response
        return str(data)
