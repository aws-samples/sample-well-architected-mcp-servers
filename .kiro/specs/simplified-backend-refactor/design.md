# Design Document

## Overview

The simplified backend refactor transforms the current complex multi-service architecture into a streamlined, agent-centric system. The new design eliminates direct MCP server connections, centralizes all functionality in main.py, and provides intelligent routing between direct Bedrock model calls and agent invocations.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Simplified Backend                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │    main.py      │  │  Agent Manager  │  │ Bedrock      │ │
│  │  (Entry Point)  │◄─┤  (Discovery &   │◄─┤ Service      │ │
│  │                 │  │   Selection)    │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│           │                     │                   │       │
│           ▼                     ▼                   ▼       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Auth Service  │  │ Config Service  │  │ Query Router │ │
│  │                 │  │                 │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS Services                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Bedrock Models  │  │ Bedrock Agents  │  │ SSM Parameter│ │
│  │ (Claude, etc.)  │  │ (with MCP tools)│  │ Store        │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

1. **main.py**: Single entry point, FastAPI app definition, endpoint routing
2. **Agent Manager**: Agent discovery, selection, and metadata management
3. **Bedrock Service**: Direct model calls and agent invocations
4. **Query Router**: Intelligent routing between models and agents
5. **Auth Service**: Authentication and authorization (simplified)
6. **Config Service**: Configuration management (simplified)

## Components and Interfaces

### 1. Main Application (main.py)

**Purpose**: Single entry point for the FastAPI application with all endpoints defined.

**Key Responsibilities**:
- FastAPI app initialization and configuration
- CORS and middleware setup
- All API endpoint definitions
- WebSocket connection management
- Session management
- Agent selection command processing

**Key Endpoints**:
- `POST /api/chat` - Main chat endpoint
- `GET /api/agents` - List available agents
- `POST /api/agents/select` - Select agent for session
- `GET /api/health` - Health check
- `WebSocket /ws/{session_id}` - Real-time chat

### 2. Agent Manager

**Purpose**: Manages agent discovery, selection, and metadata.

```python
class AgentManager:
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.cache_ttl: int = 300  # 5 minutes
        self.last_discovery: Optional[datetime] = None
    
    async def discover_agents(self) -> Dict[str, AgentInfo]
    async def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]
    async def get_agent_capabilities(self, agent_id: str) -> List[str]
    async def get_agent_tool_count(self, agent_id: str) -> int
    def select_agent_for_session(self, session_id: str, agent_id: str)
    def get_selected_agent(self, session_id: str) -> Optional[str]
    def clear_agent_selection(self, session_id: str)
```

**Agent Discovery Process**:
1. Query SSM Parameter Store for `/coa/agents/*/metadata`
2. Parse agent metadata including capabilities and tool counts
3. Cache results with TTL
4. Provide agent selection interface

### 3. Bedrock Service

**Purpose**: Handles all communication with Amazon Bedrock (models and agents).

```python
class BedrockService:
    def __init__(self):
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
    
    async def invoke_model(self, model_id: str, prompt: str, **kwargs) -> ModelResponse
    async def invoke_agent(self, agent_id: str, agent_alias_id: str, 
                          session_id: str, input_text: str) -> AgentResponse
    async def stream_model_response(self, model_id: str, prompt: str) -> AsyncIterator[str]
    async def stream_agent_response(self, agent_id: str, agent_alias_id: str,
                                   session_id: str, input_text: str) -> AsyncIterator[str]
```

### 4. Query Router

**Purpose**: Intelligent routing between direct model calls and agent invocations.

```python
class QueryRouter:
    def __init__(self, agent_manager: AgentManager, bedrock_service: BedrockService):
        self.agent_manager = agent_manager
        self.bedrock_service = bedrock_service
    
    async def route_query(self, query: str, session_id: str, 
                         context: Dict[str, Any]) -> QueryRoute
    def should_use_agent(self, query: str, selected_agent: Optional[str]) -> bool
    def select_model_for_query(self, query: str) -> str
    async def process_agent_command(self, command: str, session_id: str) -> CommandResponse
```

**Routing Logic**:
1. Check for agent commands (`/agent select`, `/agent list`, `/agent clear`)
2. If agent selected for session, route to agent
3. If query requires tools/analysis, route to appropriate agent
4. If simple query, use direct model call
5. Handle streaming responses appropriately

## Data Models

### Core Data Models

```python
@dataclass
class AgentInfo:
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    tool_count: int
    framework: str  # 'bedrock' or 'agentcore'
    endpoint_url: Optional[str] = None
    status: str = 'available'

@dataclass
class QueryRoute:
    route_type: str  # 'model' or 'agent'
    target: str  # model_id or agent_id
    reasoning: str
    requires_streaming: bool = False

@dataclass
class ChatSession:
    session_id: str
    selected_agent: Optional[str] = None
    messages: List[ChatMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class CommandResponse:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
```

### Response Models

```python
class ChatResponse(BaseModel):
    response: str
    session_id: str
    route_info: QueryRoute
    tool_executions: List[ToolExecution] = []
    timestamp: datetime
    agent_used: Optional[str] = None
    model_used: Optional[str] = None

class AgentListResponse(BaseModel):
    agents: List[AgentInfo]
    total_count: int
    selected_agent: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]
    agent_count: int
    timestamp: datetime
```

## Error Handling

### Error Categories

1. **Agent Discovery Errors**: SSM access issues, malformed metadata
2. **Bedrock Communication Errors**: Model/agent invocation failures
3. **Session Management Errors**: Invalid session states
4. **Command Processing Errors**: Invalid agent commands

### Error Handling Strategy

```python
class ErrorHandler:
    @staticmethod
    async def handle_agent_error(error: Exception, fallback_agent: Optional[str] = None):
        """Handle agent invocation errors with fallback options"""
        
    @staticmethod
    async def handle_model_error(error: Exception, fallback_model: str = "claude-3-haiku"):
        """Handle direct model errors with fallback models"""
        
    @staticmethod
    def handle_command_error(command: str, error: Exception) -> CommandResponse:
        """Handle agent command errors with user-friendly messages"""
```

### Graceful Degradation

1. **Agent Unavailable**: Fall back to direct model calls
2. **Model Unavailable**: Try alternative models
3. **SSM Unavailable**: Use cached agent data
4. **Network Issues**: Provide offline-capable responses where possible

## Testing Strategy

### Unit Tests

1. **Agent Manager Tests**:
   - Agent discovery from SSM
   - Agent selection and session management
   - Cache behavior and TTL handling

2. **Bedrock Service Tests**:
   - Model invocation with various parameters
   - Agent invocation with session management
   - Streaming response handling

3. **Query Router Tests**:
   - Routing logic for different query types
   - Agent command processing
   - Fallback behavior

4. **Main Application Tests**:
   - Endpoint functionality
   - WebSocket connection handling
   - Session management

### Integration Tests

1. **End-to-End Chat Flow**:
   - Complete chat interactions through REST and WebSocket
   - Agent selection and query routing
   - Error handling and recovery

2. **Agent Discovery Integration**:
   - SSM Parameter Store integration
   - Agent metadata parsing and caching
   - Real agent invocation testing

3. **Bedrock Integration**:
   - Real model and agent invocations
   - Response parsing and formatting
   - Error handling with AWS services

### Mock Strategy

```python
# Mock AWS services for unit tests
@pytest.fixture
def mock_bedrock_runtime():
    with patch('boto3.client') as mock_client:
        mock_bedrock = MagicMock()
        mock_client.return_value = mock_bedrock
        yield mock_bedrock

# Mock SSM for agent discovery tests
@pytest.fixture
def mock_ssm_client():
    with patch('boto3.client') as mock_client:
        mock_ssm = MagicMock()
        mock_client.return_value = mock_ssm
        yield mock_ssm
```

## Performance Considerations

### Caching Strategy

1. **Agent Metadata**: Cache for 5 minutes with automatic refresh
2. **Session Data**: In-memory storage with cleanup for inactive sessions
3. **Model Responses**: Optional caching for repeated queries

### Optimization Techniques

1. **Lazy Loading**: Load agent metadata only when needed
2. **Connection Pooling**: Reuse Bedrock client connections
3. **Streaming**: Use streaming responses for long-running queries
4. **Async Processing**: Fully async architecture for better concurrency

### Resource Management

```python
class ResourceManager:
    def __init__(self):
        self.session_cleanup_interval = 3600  # 1 hour
        self.max_sessions = 1000
        self.agent_cache_size = 50
    
    async def cleanup_inactive_sessions(self):
        """Remove sessions inactive for more than cleanup_interval"""
        
    async def manage_agent_cache(self):
        """Manage agent metadata cache size and freshness"""
```

## Security Considerations

### Authentication

- Simplified JWT token validation
- Session-based agent selection (no cross-session access)
- Rate limiting on agent selection commands

### Authorization

- Agent access based on user permissions
- Secure handling of AWS credentials
- Input validation for all commands and queries

### Data Protection

- No sensitive data in logs
- Secure session management
- Proper error message sanitization

## Deployment Considerations

### Configuration

```python
# Environment variables
BEDROCK_REGION = "us-east-1"
DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
AGENT_DISCOVERY_TTL = 300
MAX_SESSIONS = 1000
SESSION_CLEANUP_INTERVAL = 3600
```

### Health Checks

```python
async def health_check() -> HealthResponse:
    """Comprehensive health check covering all essential services"""
    services = {
        "bedrock": await check_bedrock_connectivity(),
        "ssm": await check_ssm_connectivity(),
        "agents": await check_agent_availability(),
        "auth": check_auth_service()
    }
    
    return HealthResponse(
        status="healthy" if all(s == "healthy" for s in services.values()) else "degraded",
        services=services,
        agent_count=len(await agent_manager.discover_agents()),
        timestamp=datetime.utcnow()
    )
```

### Monitoring

- CloudWatch metrics for agent usage
- Request/response time tracking
- Error rate monitoring
- Agent selection patterns

This design provides a clean, maintainable architecture that meets all the requirements while simplifying the current complex system.