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

"""General utility functions for AWS resource operations."""

from typing import Any, Dict

import boto3
from botocore.config import Config
from mcp.server.fastmcp import Context

from src import __version__

# User agent configuration for AWS API calls
USER_AGENT_CONFIG = Config(
    user_agent_extra=f"awslabs/mcp/well-architected-security-mcp-server/{__version__}"
)


async def list_services_in_region(
    region: str, session: boto3.Session, ctx: Context
) -> Dict[str, Any]:
    """List all AWS services being used in a specific region.

    Args:
        region: AWS region to list services for
        session: boto3 Session for AWS API calls
        ctx: MCP context for error reporting

    Returns:
        Dictionary with services information and counts
    """
    try:
        # Initialize the result dictionary
        result = {"region": region, "services": [], "service_counts": {}, "total_resources": 0}

        # Use Resource Explorer to efficiently discover resources
        try:
            resource_explorer = session.client(
                "resource-explorer-2", region_name=region, config=USER_AGENT_CONFIG
            )

            # Check if Resource Explorer is available in this region
            try:
                # Try to search with Resource Explorer
                resource_explorer.search(
                    QueryString="*",
                    MaxResults=1,  # Just checking if it works
                )
            except Exception as e:
                if "Resource Explorer has not been set up" in str(e):
                    await ctx.warning(
                        f"Resource Explorer not set up in {region}. Using alternative method."
                    )
                    return {"region": region, "services": [], "error": str(e)}
                else:
                    raise e

            # Resource Explorer is available, use it to get all resources
            paginator = resource_explorer.get_paginator("search")
            page_iterator = paginator.paginate(QueryString="*", MaxResults=1000)

            # Track unique services
            services_set = set()
            service_resource_counts = {}

            # Process each page of results
            for page in page_iterator:
                for resource in page.get("Resources", []):
                    # Extract service from ARN
                    arn = resource.get("Arn", "")
                    if arn:
                        arn_parts = arn.split(":")
                        if len(arn_parts) >= 3:
                            service = arn_parts[2]
                            services_set.add(service)

                            # Update count for this service
                            if service in service_resource_counts:
                                service_resource_counts[service] += 1
                            else:
                                service_resource_counts[service] = 1

            # Update result with discovered services
            result["services"] = sorted(list(services_set))
            result["service_counts"] = service_resource_counts
            result["total_resources"] = sum(service_resource_counts.values())

        except Exception as e:
            await ctx.warning(f"Error using Resource Explorer in {region}: {e}")
            # Fall back to alternative method
            return {"region": region, "services": [], "error": str(e)}

        return result

    except Exception as e:
        await ctx.error(f"Error listing services in region {region}: {e}")
        return {"region": region, "services": [], "error": str(e)}
