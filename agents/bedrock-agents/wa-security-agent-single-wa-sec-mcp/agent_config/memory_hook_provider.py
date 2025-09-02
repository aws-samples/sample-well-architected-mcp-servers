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
Memory Hook Provider for Security Agent
"""

import logging
from typing import Any, Dict

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory import MemoryHook as BaseMemoryHook

logger = logging.getLogger(__name__)


class MemoryHook(BaseMemoryHook):
    """
    Memory hook for Security Agent to maintain conversation context
    """

    def __init__(
        self,
        memory_client: MemoryClient,
        memory_id: str,
        actor_id: str,
        session_id: str,
    ):
        super().__init__(memory_client, memory_id, actor_id, session_id)
        self.security_context = {}

    async def store_security_assessment(
        self, assessment_type: str, results: Dict[str, Any]
    ):
        """Store security assessment results in memory"""
        try:
            memory_entry = {
                "type": "security_assessment",
                "assessment_type": assessment_type,
                "results": results,
                "timestamp": results.get("timestamp", "unknown"),
            }

            await self.add_memory(
                content=f"Security Assessment - {assessment_type}",
                metadata=memory_entry,
            )

            # Also store in local context for quick access
            self.security_context[assessment_type] = results

            logger.info(f"Stored {assessment_type} assessment in memory")

        except Exception as e:
            logger.error(f"Failed to store security assessment: {e}")

    async def get_security_context(self, assessment_type: str = None) -> Dict[str, Any]:
        """Retrieve security context from memory"""
        try:
            if assessment_type and assessment_type in self.security_context:
                return self.security_context[assessment_type]

            # Retrieve from persistent memory
            memories = await self.get_memories(limit=10)
            security_memories = [
                m
                for m in memories
                if m.get("metadata", {}).get("type") == "security_assessment"
            ]

            if assessment_type:
                security_memories = [
                    m
                    for m in security_memories
                    if m.get("metadata", {}).get("assessment_type") == assessment_type
                ]

            return {"memories": security_memories, "count": len(security_memories)}

        except Exception as e:
            logger.error(f"Failed to retrieve security context: {e}")
            return {}

    async def clear_security_context(self):
        """Clear security context"""
        self.security_context.clear()
        logger.info("Security context cleared")
