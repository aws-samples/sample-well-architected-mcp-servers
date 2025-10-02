# Requirements Document

## Introduction

This specification outlines the requirements for refactoring the Cloud Optimization Assistant backend to create a simplified, agent-centric architecture. The refactored backend will focus on direct communication with Bedrock models and agents, eliminating direct MCP server connections and implementing agent selection capabilities.

## Requirements

### Requirement 1

**User Story:** As a developer, I want a simplified backend architecture with main.py as the single entry point, so that the application is easier to maintain and understand.

#### Acceptance Criteria

1. WHEN the application starts THEN main.py SHALL be the single entry point for the FastAPI application
2. WHEN the backend initializes THEN it SHALL load only essential services (auth, config, bedrock communication)
3. WHEN examining the codebase THEN there SHALL be no complex service orchestration or multiple initialization points
4. WHEN the application runs THEN all API endpoints SHALL be defined in main.py or imported modules with clear separation

### Requirement 2

**User Story:** As a user, I want to select which agent handles my queries using "/agent select" command, so that I can choose the most appropriate agent for my specific needs.

#### Acceptance Criteria

1. WHEN a user types "/agent select" THEN the system SHALL display a list of available agents
2. WHEN a user selects an agent THEN the system SHALL store the selection for the current session
3. WHEN a user sends subsequent messages THEN the system SHALL route them to the selected agent
4. WHEN no agent is selected THEN the system SHALL use a default agent or intelligent routing
5. WHEN a user types "/agent list" THEN the system SHALL show currently available agents with their capabilities
6. WHEN a user types "/agent clear" THEN the system SHALL clear the current agent selection

### Requirement 3

**User Story:** As a backend service, I want to communicate primarily with Bedrock models and agents, so that I can leverage AWS's managed AI services without complex integrations.

#### Acceptance Criteria

1. WHEN processing user queries THEN the backend SHALL send requests directly to Amazon Bedrock models or Bedrock agents
2. WHEN communicating with Bedrock THEN the system SHALL use the AWS SDK (boto3) for bedrock-runtime and bedrock-agent-runtime
3. WHEN handling responses THEN the system SHALL process Bedrock's native response format
4. WHEN errors occur THEN the system SHALL handle Bedrock-specific error codes and retry logic

### Requirement 4

**User Story:** As a backend service, I want to discover agent capabilities and MCP tool counts through agent metadata, so that I can provide users with accurate information about what each agent can do.

#### Acceptance Criteria

1. WHEN discovering agents THEN the backend SHALL retrieve agent metadata from AWS Systems Manager Parameter Store
2. WHEN an agent is queried THEN the system SHALL know how many MCP tools belong to that agent
3. WHEN displaying agent information THEN the system SHALL show tool counts and capabilities for each agent
4. WHEN agent metadata changes THEN the system SHALL refresh its cache within a reasonable time (5-10 minutes)
5. WHEN agent discovery fails THEN the system SHALL log errors and continue with available agents

### Requirement 5

**User Story:** As a backend architecture, I want to eliminate direct MCP server connections, so that all tool execution goes through agents and the system is simplified.

#### Acceptance Criteria

1. WHEN the backend starts THEN it SHALL NOT establish direct connections to MCP servers
2. WHEN tools need to be executed THEN the system SHALL invoke them through Bedrock agents only
3. WHEN listing available tools THEN the information SHALL come from agent metadata, not direct MCP server queries
4. WHEN MCP servers are updated THEN the backend SHALL rely on agents to handle the updated tools
5. WHEN troubleshooting tool issues THEN the system SHALL provide agent-level diagnostics, not MCP server diagnostics

### Requirement 6

**User Story:** As a user, I want the chatbot to handle text queries efficiently, so that I can get quick responses for both simple questions and complex analysis requests.

#### Acceptance Criteria

1. WHEN a user sends a text query THEN the system SHALL determine whether to use a Bedrock model directly or route to an agent
2. WHEN the query is simple (greetings, basic questions) THEN the system SHALL use a lightweight Bedrock model
3. WHEN the query requires tools or analysis THEN the system SHALL route to the appropriate agent
4. WHEN processing queries THEN the system SHALL maintain conversation context and session state
5. WHEN responses are generated THEN they SHALL be formatted consistently regardless of the processing path

### Requirement 7

**User Story:** As a system administrator, I want simplified service dependencies, so that the backend is easier to deploy, monitor, and troubleshoot.

#### Acceptance Criteria

1. WHEN examining service dependencies THEN there SHALL be minimal service classes (auth, config, bedrock communication)
2. WHEN the system starts THEN it SHALL have clear initialization order and dependency resolution
3. WHEN monitoring the system THEN health checks SHALL be straightforward and cover essential components only
4. WHEN errors occur THEN they SHALL be traceable to specific components without complex service interactions
5. WHEN deploying THEN the system SHALL require minimal configuration beyond AWS credentials and agent metadata

### Requirement 8

**User Story:** As a developer, I want clear separation between direct Bedrock model calls and agent invocations, so that I can optimize performance and costs appropriately.

#### Acceptance Criteria

1. WHEN implementing query routing THEN there SHALL be clear logic for choosing between direct model calls and agent invocations
2. WHEN using direct model calls THEN the system SHALL handle model selection, token limits, and response parsing
3. WHEN using agent invocations THEN the system SHALL handle agent selection, session management, and tool execution results
4. WHEN switching between approaches THEN the user experience SHALL remain consistent
5. WHEN monitoring usage THEN the system SHALL track both direct model usage and agent invocation costs separately