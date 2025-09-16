#!/usr/bin/env python3
"""
AWS API MCP Server for AgentCore Runtime

This module runs the official awslabs.aws-api-mcp-server on AgentCore Runtime.
It uses the MCP protocol to provide AWS CLI functionality.
"""

import os
import sys
import asyncio
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the AWS API MCP Server"""
    logger.info("🚀 Starting AWS API MCP Server for AgentCore Runtime...")
    
    # Set environment variables for the MCP server
    os.environ.setdefault('MCP_SERVER_HOST', '0.0.0.0')
    os.environ.setdefault('MCP_SERVER_PORT', '8000')
    
    try:
        # Run the official AWS API MCP server using the installed executable
        # The package should already be installed via requirements.txt
        cmd = ['awslabs.aws-api-mcp-server', '--host', '0.0.0.0', '--port', '8000']
        logger.info(f"📡 Starting server with command: {' '.join(cmd)}")
        logger.info("🔧 Using official awslabs.aws-api-mcp-server package")
        logger.info("📍 Server will be available at http://0.0.0.0:8000/mcp")
        # Execute the MCP server
        result = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ MCP server failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.error("❌ awslabs.aws-api-mcp-server executable not found.")
        logger.error("💡 Trying alternative approaches...")
        try:
            # Try uvx if available
            cmd = ['uvx', 'awslabs.aws-api-mcp-server@latest', '--host', '0.0.0.0', '--port', '8000']
            logger.info(f"📡 Trying uvx: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True)
        except FileNotFoundError:
            try:
                # Try uv tool run
                cmd = ['uv', 'tool', 'run', 'awslabs.aws-api-mcp-server@latest', '--host', '0.0.0.0', '--port', '8000']
                logger.info(f"📡 Trying uv tool run: {' '.join(cmd)}")
                result = subprocess.run(cmd, check=True)
            except Exception as e3:
                logger.error(f"❌ All approaches failed: {e3}")
                logger.error("💡 Please ensure awslabs.aws-api-mcp-server is properly installed")
                sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()