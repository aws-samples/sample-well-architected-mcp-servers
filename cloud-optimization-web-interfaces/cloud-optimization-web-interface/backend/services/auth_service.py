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
Authentication Service - Cognito integration
"""

import boto3
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self._cognito_client = None

    @property
    def cognito_client(self):
        """Lazy initialization of Cognito client"""
        if self._cognito_client is None:
            try:
                self._cognito_client = boto3.client("cognito-idp")
            except Exception as e:
                logger.warning(f"Could not initialize Cognito client: {str(e)}")
                self._cognito_client = None
        return self._cognito_client

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token"""
        try:
            # For demo purposes, return a mock user
            # In production, this would verify the JWT token with Cognito
            return {"user_id": "demo_user", "email": "demo@example.com"}
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise
