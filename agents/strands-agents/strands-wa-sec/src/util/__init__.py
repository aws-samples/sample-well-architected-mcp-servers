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

"""Utility functions for AWS Security Pillar MCP Server."""

from .resource_utils import list_services_in_region
from .security_services import (
    check_access_analyzer,
    check_guard_duty,
    check_inspector,
    check_security_hub,
    get_access_analyzer_findings,
    get_guardduty_findings,
    get_inspector_findings,
    get_securityhub_findings,
)

# Export all imported functions
__all__ = [
    # Security service functions
    "check_access_analyzer",
    "check_security_hub",
    "check_guard_duty",
    "check_inspector",
    "get_guardduty_findings",
    "get_securityhub_findings",
    "get_inspector_findings",
    "get_access_analyzer_findings",
    # Resource utility functions
    "list_services_in_region",
]
