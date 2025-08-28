# MIT No Attribution
"""
AWS Configuration Service
"""

import boto3
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AWSConfigService:
    def __init__(self):
        self._sts_client = None
        
    @property
    def sts_client(self):
        """Lazy initialization of STS client"""
        if self._sts_client is None:
            try:
                self._sts_client = boto3.client('sts')
            except Exception as e:
                logger.warning(f"Could not initialize STS client: {str(e)}")
                self._sts_client = None
        return self._sts_client
        
    async def get_current_config(self) -> Dict[str, Any]:
        """Get current AWS configuration"""
        try:
            if self.sts_client:
                identity = self.sts_client.get_caller_identity()
                return {
                    "account_id": identity.get('Account'),
                    "region": os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                    "role_arn": identity.get('Arn'),
                    "status": "configured"
                }
            else:
                raise Exception("STS client not available")
        except Exception as e:
            logger.error(f"Failed to get AWS config: {str(e)}")
            return {
                "account_id": None,
                "region": os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                "role_arn": None,
                "status": "not_configured"
            }
    
    async def update_config(self, **kwargs) -> Dict[str, Any]:
        """Update AWS configuration"""
        # For demo purposes, just return current config
        return await self.get_current_config()