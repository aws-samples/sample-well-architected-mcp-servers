# Implementation Plan

- [x] 1. Create core data models and interfaces
  - Create new data models for AgentInfo, QueryRoute, ChatSession, and response models
  - Define interfaces for AgentManager, BedrockService, and QueryRouter
  - Implement base exception classes for error handling
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Implement Agent Manager service
  - [x] 2.1 Create AgentManager class with agent discovery from SSM
    - Implement SSM Parameter Store queries for agent metadata
    - Parse agent metadata including capabilities and tool counts
    - Implement caching mechanism with TTL (5 minutes)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 2.2 Implement agent selection and session management
    - Create session-based agent selection storage
    - Implement select_agent_for_session, get_selected_agent, clear_agent_selection methods
    - Add agent validation and error handling
    - _Requirements: 2.1, 2.2, 2.6_

  - [x] 2.3 Add agent capability and tool count discovery
    - Parse agent metadata to extract MCP tool counts
    - Implement get_agent_capabilities and get_agent_tool_count methods
    - Add agent status monitoring and health checks
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3. Implement Bedrock Service for model and agent communication
  - [x] 3.1 Create BedrockService class with direct model invocation
    - Initialize bedrock-runtime client with proper configuration
    - Implement invoke_model method with error handling and retries
    - Add support for streaming model responses
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 3.2 Implement agent invocation capabilities
    - Initialize bedrock-agent-runtime client
    - Implement invoke_agent method with session management
    - Add support for streaming agent responses
    - Handle agent-specific error codes and responses
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 3.3 Add response parsing and formatting
    - Parse Bedrock model responses into consistent format
    - Parse agent responses including tool execution results
    - Implement response streaming for both models and agents
    - _Requirements: 3.3, 6.5_

- [x] 4. Implement Query Router for intelligent routing
  - [x] 4.1 Create QueryRouter class with routing logic
    - Implement should_use_agent method based on query analysis
    - Add select_model_for_query for direct model selection
    - Create route_query method that determines routing strategy
    - _Requirements: 6.1, 6.2, 6.3, 8.1, 8.4_

  - [x] 4.2 Implement agent command processing
    - Parse and handle "/agent select", "/agent list", "/agent clear" commands
    - Implement process_agent_command method with proper validation
    - Add command response formatting and error handling
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 4.3 Add intelligent routing decision logic
    - Implement query classification (simple vs complex)
    - Add routing logic based on selected agent and query type
    - Implement fallback strategies for unavailable agents/models
    - _Requirements: 6.1, 6.2, 6.3, 8.1, 8.2, 8.3_

- [x] 5. Refactor main.py as single entry point
  - [x] 5.1 Create new simplified main.py structure
    - Remove complex service imports and orchestration
    - Initialize only essential services (AgentManager, BedrockService, QueryRouter)
    - Set up FastAPI app with CORS and middleware
    - _Requirements: 1.1, 1.2, 1.3, 7.1, 7.2_

  - [x] 5.2 Implement core API endpoints
    - Create POST /api/chat endpoint with query routing
    - Implement GET /api/agents endpoint for agent listing
    - Add POST /api/agents/select endpoint for agent selection
    - Create GET /api/health endpoint with simplified health checks
    - _Requirements: 1.4, 2.1, 7.3_

  - [x] 5.3 Implement WebSocket support for real-time chat
    - Create WebSocket endpoint /ws/{session_id}
    - Implement connection management and session handling
    - Add real-time message processing with agent routing
    - Handle WebSocket errors and disconnections gracefully
    - _Requirements: 1.4, 6.4_

- [x] 6. Implement session and context management
  - [x] 6.1 Create session management system
    - Implement ChatSession data model with agent selection
    - Add session storage and retrieval mechanisms
    - Implement session cleanup for inactive sessions
    - _Requirements: 6.4, 7.4_

  - [x] 6.2 Add conversation context handling
    - Maintain conversation history within sessions
    - Implement context passing to models and agents
    - Add context-aware routing decisions
    - _Requirements: 6.4, 6.5_

- [x] 7. Implement simplified authentication and configuration
  - [x] 7.1 Simplify authentication service
    - Keep only essential JWT token validation
    - Remove complex authentication orchestration
    - Add basic rate limiting for agent commands
    - _Requirements: 7.1, 7.4_

  - [x] 7.2 Simplify configuration service
    - Keep only essential configuration loading from SSM
    - Remove complex configuration orchestration
    - Add basic configuration validation and defaults
    - _Requirements: 7.1, 7.2_

- [x] 8. Add comprehensive error handling and logging
  - [x] 8.1 Implement error handling strategies
    - Create ErrorHandler class with fallback mechanisms
    - Add graceful degradation for agent/model failures
    - Implement user-friendly error messages
    - _Requirements: 7.4, 8.4_

  - [x] 8.2 Add logging and monitoring
    - Implement structured logging for all components
    - Add performance metrics tracking
    - Create health check endpoints with detailed status
    - _Requirements: 7.3, 7.4_

- [x] 9. Create comprehensive test suite
  - [x] 9.1 Write unit tests for all components
    - Test AgentManager agent discovery and selection
    - Test BedrockService model and agent invocation
    - Test QueryRouter routing logic and command processing
    - Test main.py endpoint functionality
    - _Requirements: All requirements_

  - [x] 9.2 Write integration tests
    - Test end-to-end chat flow through REST and WebSocket
    - Test agent selection and query routing integration
    - Test error handling and fallback scenarios
    - Test real AWS service integration (with mocks for CI)
    - _Requirements: All requirements_

  - [x] 9.3 Add performance and load tests
    - Test concurrent session handling
    - Test agent discovery caching behavior
    - Test streaming response performance
    - Validate memory usage and cleanup
    - _Requirements: 7.2, 7.3_

- [x] 10. Update deployment and documentation
  - [x] 10.1 Update deployment scripts
    - Modify deployment scripts to use simplified backend
    - Update environment variable configuration
    - Test deployment in development environment
    - _Requirements: 7.1, 7.2_

  - [x] 10.2 Create migration guide and documentation
    - Document changes from old to new architecture
    - Create API documentation for new endpoints
    - Update README with new architecture overview
    - Create troubleshooting guide for common issues
    - _Requirements: 1.1, 7.3_

- [x] 11. Remove deprecated services and clean up codebase
  - [x] 11.1 Remove unused service files
    - Remove enhanced_bedrock_agent_service.py
    - Remove llm_orchestrator_service.py
    - Remove dynamic_mcp_service.py
    - Remove mcp_client_service.py
    - _Requirements: 5.1, 5.2, 5.3, 7.1_

  - [x] 11.2 Clean up imports and dependencies
    - Remove unused imports from main.py
    - Update requirements.txt to remove unnecessary dependencies
    - Clean up any remaining references to old services
    - _Requirements: 1.2, 7.1_

- [x] 12. Final integration testing and validation
  - [x] 12.1 Validate all requirements are met
    - Test single entry point functionality
    - Validate agent selection commands work correctly
    - Confirm no direct MCP server connections exist
    - Test Bedrock communication for both models and agents
    - _Requirements: All requirements_

  - [x] 12.2 Performance validation and optimization
    - Validate response times for different query types
    - Test agent discovery caching performance
    - Optimize any performance bottlenecks found
    - Validate resource usage is within acceptable limits
    - _Requirements: 6.1, 6.2, 6.3, 7.2_