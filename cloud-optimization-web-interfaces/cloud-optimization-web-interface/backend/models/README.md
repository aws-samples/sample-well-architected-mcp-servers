# Core Data Models and Interfaces

This directory contains the core data models, interfaces, and exception classes for the simplified backend refactor.

## Overview

The models package provides:
- **Data Models**: Core data structures using dataclasses
- **Response Models**: Pydantic models for API responses
- **Interfaces**: Abstract base classes defining service contracts
- **Exceptions**: Custom exception hierarchy for error handling

## Data Models (`data_models.py`)

### Core Models

- **`AgentInfo`**: Information about available agents including capabilities and tool counts
- **`QueryRoute`**: Routing information for queries (model vs agent)
- **`ChatSession`**: Session management with agent selection and conversation history
- **`ChatMessage`**: Individual messages in conversations
- **`ToolExecution`**: Information about tool executions during processing
- **`CommandResponse`**: Responses from agent command processing

### Enums

- **`RouteType`**: MODEL or AGENT routing types
- **`AgentFramework`**: BEDROCK or AGENTCORE frameworks
- **`AgentStatus`**: AVAILABLE, UNAVAILABLE, or ERROR statuses

## Response Models (`response_models.py`)

Pydantic models for API responses:

- **`ChatResponse`**: Complete chat interaction response
- **`AgentListResponse`**: List of available agents
- **`HealthResponse`**: System health check information
- **`AgentSelectionResponse`**: Agent selection operation results
- **`ErrorResponse`**: Standardized error responses

## Interfaces (`interfaces.py`)

Abstract base classes defining service contracts:

### `AgentManagerInterface`
- Agent discovery and metadata management
- Session-based agent selection
- Agent capability and tool count queries

### `BedrockServiceInterface`
- Direct model invocation
- Agent invocation with session management
- Streaming response support
- Availability checking

### `QueryRouterInterface`
- Intelligent query routing
- Agent command processing
- Model selection logic

### `SessionManagerInterface`
- Session lifecycle management
- Conversation history tracking
- Session cleanup and monitoring

### Response Classes
- **`ModelResponse`**: Bedrock model invocation results
- **`AgentResponse`**: Bedrock agent invocation results

## Exceptions (`exceptions.py`)

Custom exception hierarchy:

### Base Exception
- **`COABaseException`**: Base class with error codes and structured details

### Specific Exceptions
- **`AgentDiscoveryError`**: Agent discovery and metadata issues
- **`BedrockCommunicationError`**: Bedrock service communication failures
- **`SessionManagementError`**: Session lifecycle issues
- **`CommandProcessingError`**: Agent command processing failures
- **`ConfigurationError`**: Configuration validation issues
- **`AuthenticationError`**: Authentication failures
- **`RateLimitError`**: Rate limiting issues
- **`ValidationError`**: Input validation failures

## Usage Examples

### Creating an Agent Info
```python
from models import AgentInfo, AgentFramework, AgentStatus

agent = AgentInfo(
    agent_id="wa-security-agent",
    name="Well-Architected Security Agent",
    description="Security analysis and recommendations",
    capabilities=["security-assessment", "compliance-check"],
    tool_count=6,
    framework=AgentFramework.BEDROCK,
    status=AgentStatus.AVAILABLE
)
```

### Creating a Query Route
```python
from models import QueryRoute, RouteType

route = QueryRoute(
    route_type=RouteType.AGENT,
    target="wa-security-agent",
    reasoning="Query requires security analysis tools",
    requires_streaming=True,
    confidence=0.95
)
```

### Handling Exceptions
```python
from models import AgentDiscoveryError

try:
    # Agent discovery logic
    pass
except Exception as e:
    raise AgentDiscoveryError(
        message="Failed to discover agents from SSM",
        details={"original_error": str(e)}
    )
```

### Using Interfaces
```python
from models.interfaces import AgentManagerInterface

class ConcreteAgentManager(AgentManagerInterface):
    async def discover_agents(self) -> Dict[str, AgentInfo]:
        # Implementation here
        pass
    
    # Implement other abstract methods...
```

## Testing

Run the validation scripts to ensure models work correctly:

```bash
# Test data models and response models
python test_models.py

# Validate interface definitions
python validate_interfaces.py
```

## Design Principles

1. **Type Safety**: All models use proper type hints
2. **Validation**: Pydantic models provide automatic validation
3. **Extensibility**: Interfaces allow for multiple implementations
4. **Error Handling**: Structured exception hierarchy with details
5. **Documentation**: Clear docstrings and examples
6. **Testing**: Comprehensive test coverage for all components

## Integration

These models integrate with the simplified backend architecture:

- **main.py**: Uses response models for API endpoints
- **Agent Manager**: Implements `AgentManagerInterface`
- **Bedrock Service**: Implements `BedrockServiceInterface`
- **Query Router**: Implements `QueryRouterInterface`
- **Session Manager**: Implements `SessionManagerInterface`

The models provide a clean contract between components while maintaining flexibility for different implementations.