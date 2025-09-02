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

# MIT No Attribution
"""
Bedrock Chat Service - Basic chat functionality
"""

import boto3
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BedrockChatService:
    def __init__(self):
        self._bedrock_client = None

    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client"""
        if self._bedrock_client is None:
            try:
                self._bedrock_client = boto3.client("bedrock-runtime")
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock client: {str(e)}")
                self._bedrock_client = None
        return self._bedrock_client

    async def health_check(self) -> str:
        """Health check for the service"""
        try:
            # Simple check - just verify we can create the client
            if self.bedrock_client:
                return "healthy"
            else:
                return "degraded"
        except Exception as e:
            logger.error(f"Bedrock chat service health check failed: {str(e)}")
            return "unhealthy"

    async def process_message(
        self, message: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a chat message"""
        try:
            # Basic response for now
            return {
                "response": f"Echo: {message}",
                "timestamp": datetime.utcnow().isoformat(),
                "tool_executions": [],
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            raise
