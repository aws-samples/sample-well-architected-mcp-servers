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
# CONNECTION WITH SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# BedrockAgent Version Dockerfile
# Multi-stage build for BedrockAgent backend with traditional agent services and MCP integration

# Build stage - Install dependencies
FROM python:3.11-slim as builder

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create build directory
WORKDIR /build

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies to user directory
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Production stage - BedrockAgent runtime image
FROM python:3.11-slim as production

# Set production arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r bedrockagent && useradd -r -g bedrockagent bedrockagent

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/bedrockagent/.local

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/cache /app/tmp && \
    chown -R bedrockagent:bedrockagent /app && \
    chmod -R 755 /app

# Switch to non-root user
USER bedrockagent

# Set environment variables for BedrockAgent version
ENV PATH=/home/bedrockagent/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BACKEND_MODE=bedrockagent \
    BACKEND_VERSION=bedrockagent \
    LOG_LEVEL=INFO \
    ENABLE_TRADITIONAL_AGENTS=true \
    ENABLE_MCP_INTEGRATION=true \
    ENABLE_STRANDS_AGENTS=false \
    ENABLE_AGENTCORE_RUNTIME=false

# Expose application port
EXPOSE 8000

# Add health check specific to BedrockAgent
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Validate BedrockAgent configuration on startup
RUN python -c "import os; assert os.getenv('BACKEND_MODE') == 'bedrockagent', 'Invalid backend mode for BedrockAgent'"

# Run BedrockAgent application
CMD ["python", "-c", "from main import get_backend_mode, create_app; mode = get_backend_mode(); print(f'Starting COA Backend in {mode} mode'); app = create_app(); import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000, workers=1)"]

# Metadata labels
LABEL maintainer="AWS Cloud Optimization Assistant Team" \
      version="1.0.0" \
      description="COA BedrockAgent Backend - Traditional Bedrock Agents with MCP Integration" \
      backend.mode="bedrockagent" \
      backend.features="traditional_agents,mcp_integration" \
      backend.runtime="bedrock_agent_service"