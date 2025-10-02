"""
Tests for the Query Router.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from ..services.query_router import QueryRouter
from ..services.agent_manager import AgentManager
from ..models.data_models import ChatMessage, RouteType, AgentInfo, AgentFramework, AgentStatus


@pytest.fixture
def mock_agent_manager():
    """Mock AgentManager for testing."""
    manager = Mock(spec=AgentManager)
    
    # Mock agents
    mock_agents = {
        'wa-security-agent': AgentInfo(
            agent_id='wa-security-agent',
            name='WA Security Agent',
            description='Security analysis agent',
            capabilities=['security_analysis', 'compliance_check'],
            tool_count=6,
            framework=AgentFramework.BEDROCK
        ),
        'cost-optimization-agent': AgentInfo(
            agent_id='cost-optimization-agent',
            name='Cost Optimization Agent',
            description='Cost analysis agent',
            capabilities=['cost_analysis', 'resource_optimization'],
            tool_count=4,
            framework=AgentFramework.BEDROCK
        )
    }
    
    manager.discover_agents = AsyncMock(return_value=mock_agents)
    manager.get_selected_agent = Mock(return_value=None)
    manager.select_agent_for_session = Mock()
    manager.list_agents = AsyncMock()
    manager.clear_agent_selection = Mock()
    
    return manager


@pytest.fixture
def query_router(mock_agent_manager):
    """Create QueryRouter instance with mocked AgentManager."""
    return QueryRouter(mock_agent_manager)


class TestQueryRouter:
    """Test cases for QueryRouter."""

    @pytest.mark.asyncio
    async def test_route_simple_query(self, query_router):
        """Test routing of simple queries to models."""
        route = await query_router.route_query("Hello", "session1")
        
        assert route.route_type == RouteType.MODEL
        assert "claude-3-haiku" in route.target
        assert "simple" in route.reasoning.lower()

    @pytest.mark.asyncio
    async def test_route_complex_query(self, query_router):
        """Test routing of complex queries to agents."""
        route = await query_router.route_query(
            "Analyze the security posture of my AWS infrastructure and provide recommendations",
            "session1"
        )
        
        assert route.route_type == RouteType.AGENT
        assert route.target in ['wa-security-agent', 'cost-optimization-agent']
        assert route.confidence > 0.5

    @pytest.mark.asyncio
    async def test_route_agent_command(self, query_router):
        """Test routing of agent commands."""
        route = await query_router.route_query("/agent list", "session1")
        
        assert route.route_type == RouteType.AGENT
        assert route.target == "command_processor"
        assert route.confidence == 1.0

    @pytest.mark.asyncio
    async def test_route_with_selected_agent(self, query_router, mock_agent_manager):
        """Test routing when agent is already selected."""
        mock_agent_manager.get_selected_agent.return_value = "wa-security-agent"
        
        route = await query_router.route_query("What's my security status?", "session1")
        
        assert route.route_type == RouteType.AGENT
        assert route.target == "wa-security-agent"
        assert "selected agent" in route.reasoning.lower()

    @pytest.mark.asyncio
    async def test_should_use_agent_simple_query(self, query_router):
        """Test agent decision for simple queries."""
        should_use, confidence, reasoning = await query_router.should_use_agent("Hi there")
        
        assert should_use is False
        assert confidence > 0.5
        assert "simple" in reasoning.lower()

    @pytest.mark.asyncio
    async def test_should_use_agent_complex_query(self, query_router):
        """Test agent decision for complex queries."""
        should_use, confidence, reasoning = await query_router.should_use_agent(
            "Please analyze my AWS security configuration and check for compliance issues"
        )
        
        assert should_use is True
        assert confidence > 0.5
        assert "complex" in reasoning.lower()

    def test_select_model_for_query_simple(self, query_router):
        """Test model selection for simple queries."""
        model_id = query_router.select_model_for_query("Hi")
        
        assert "claude-3-haiku" in model_id

    def test_select_model_for_query_complex(self, query_router):
        """Test model selection for complex queries."""
        long_query = "Please provide a detailed explanation of " * 20
        model_id = query_router.select_model_for_query(long_query)
        
        assert "claude-3-5-sonnet" in model_id

    @pytest.mark.asyncio
    async def test_select_best_agent_security_query(self, query_router):
        """Test agent selection for security-related queries."""
        agent_id = await query_router.select_best_agent("security analysis of my infrastructure")
        
        assert agent_id == "wa-security-agent"

    @pytest.mark.asyncio
    async def test_select_best_agent_cost_query(self, query_router):
        """Test agent selection for cost-related queries."""
        agent_id = await query_router.select_best_agent("cost optimization recommendations")
        
        assert agent_id == "cost-optimization-agent"   
 @pytest.mark.asyncio
    async def test_process_agent_command_select(self, query_router, mock_agent_manager):
        """Test processing agent select command."""
        from ..models.data_models import CommandResponse
        
        mock_agent_manager.select_agent_for_session.return_value = CommandResponse(
            success=True,
            message="Agent selected",
            command_type="select"
        )
        
        response = await query_router.process_agent_command("/agent select wa-security-agent", "session1")
        
        assert response.success is True
        assert response.command_type == "select"
        mock_agent_manager.select_agent_for_session.assert_called_once_with("session1", "wa-security-agent")

    @pytest.mark.asyncio
    async def test_process_agent_command_list(self, query_router, mock_agent_manager):
        """Test processing agent list command."""
        from ..models.data_models import CommandResponse
        
        mock_agent_manager.list_agents.return_value = CommandResponse(
            success=True,
            message="Available agents listed",
            command_type="list"
        )
        
        response = await query_router.process_agent_command("/agent list", "session1")
        
        assert response.success is True
        assert response.command_type == "list"
        mock_agent_manager.list_agents.assert_called_once_with("session1")

    @pytest.mark.asyncio
    async def test_process_agent_command_clear(self, query_router, mock_agent_manager):
        """Test processing agent clear command."""
        from ..models.data_models import CommandResponse
        
        mock_agent_manager.clear_agent_selection.return_value = CommandResponse(
            success=True,
            message="Agent selection cleared",
            command_type="clear"
        )
        
        response = await query_router.process_agent_command("/agent clear", "session1")
        
        assert response.success is True
        assert response.command_type == "clear"
        mock_agent_manager.clear_agent_selection.assert_called_once_with("session1")

    @pytest.mark.asyncio
    async def test_process_agent_command_help(self, query_router):
        """Test processing agent help command."""
        response = await query_router.process_agent_command("/agent help", "session1")
        
        assert response.success is True
        assert response.command_type == "help"
        assert "Available agent commands" in response.message

    @pytest.mark.asyncio
    async def test_process_agent_command_unknown(self, query_router):
        """Test processing unknown agent command."""
        response = await query_router.process_agent_command("/agent unknown", "session1")
        
        assert response.success is False
        assert response.command_type == "unknown"
        assert "Unknown agent command" in response.message

    def test_get_routing_stats(self, query_router):
        """Test getting routing statistics."""
        stats = query_router.get_routing_stats()
        
        assert "total_routes" in stats
        assert "model_routes" in stats
        assert "agent_routes" in stats
        assert "command_routes" in stats
        assert "routing_patterns" in stats

    @pytest.mark.asyncio
    async def test_route_query_error_handling(self, query_router, mock_agent_manager):
        """Test error handling in route_query."""
        mock_agent_manager.get_selected_agent.side_effect = Exception("Test error")
        
        # Should not raise exception, should return fallback route
        route = await query_router.route_query("test query", "session1")
        
        assert route.route_type == RouteType.MODEL
        assert "fallback" in route.reasoning.lower()
        assert route.confidence == 0.5

    @pytest.mark.asyncio
    async def test_select_best_agent_no_agents(self, query_router, mock_agent_manager):
        """Test agent selection when no agents are available."""
        mock_agent_manager.discover_agents.return_value = {}
        
        with pytest.raises(Exception):  # Should raise QueryRouterError
            await query_router.select_best_agent("test query")

    @pytest.mark.asyncio
    async def test_conversation_history_influence(self, query_router):
        """Test how conversation history influences routing decisions."""
        history = [
            ChatMessage(role="user", content="I want to analyze security"),
            ChatMessage(role="assistant", content="I can help with security analysis"),
            ChatMessage(role="user", content="What about compliance?")
        ]
        
        should_use, confidence, reasoning = await query_router.should_use_agent(
            "Tell me more", history
        )
        
        # Should be influenced by security context in history
        assert should_use is True or confidence > 0.6