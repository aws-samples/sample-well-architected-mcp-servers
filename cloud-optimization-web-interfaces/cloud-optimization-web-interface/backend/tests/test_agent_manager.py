"""
Tests for the Agent Manager service.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from ..services.agent_manager import AgentManager
from ..models.data_models import AgentInfo, AgentFramework, AgentStatus, CommandResponse


@pytest.fixture
def mock_ssm_client():
    """Mock SSM client for testing."""
    client = Mock()
    return client


@pytest.fixture
def agent_manager(mock_ssm_client):
    """Create AgentManager instance with mocked SSM client."""
    with patch('boto3.client', return_value=mock_ssm_client):
        manager = AgentManager(region="us-east-1", cache_ttl_seconds=300)
        manager.ssm_client = mock_ssm_client
    return manager


@pytest.fixture
def sample_agent_parameters():
    """Sample SSM parameters for testing."""
    return [
        {
            'Name': '/coa/agents/wa-security-agent/metadata',
            'Value': json.dumps({
                'name': 'WA Security Agent',
                'description': 'Well-Architected Security analysis agent',
                'capabilities': ['security_analysis', 'compliance_check'],
                'tool_count': 6,
                'framework': 'bedrock',
                'status': 'available'
            })
        },
        {
            'Name': '/coa/agents/cost-optimization-agent/metadata',
            'Value': json.dumps({
                'name': 'Cost Optimization Agent',
                'description': 'AWS cost analysis and optimization agent',
                'capabilities': ['cost_analysis', 'resource_optimization'],
                'tool_count': 4,
                'framework': 'agentcore',
                'endpoint_url': 'https://example.com/agent',
                'status': 'available'
            })
        }
    ]


class TestAgentManager:
    """Test cases for AgentManager."""

    def test_init(self):
        """Test AgentManager initialization."""
        with patch('boto3.client') as mock_boto:
            manager = AgentManager(region="us-west-2", cache_ttl_seconds=600)
            
            mock_boto.assert_called_once_with('ssm', region_name="us-west-2")
            assert manager.region == "us-west-2"
            assert manager.cache_ttl == timedelta(seconds=600)
            assert manager.agents == {}
            assert manager.last_discovery is None
            assert manager.session_agents == {}

    def test_init_no_credentials(self):
        """Test AgentManager initialization with no AWS credentials."""
        with patch('boto3.client', side_effect=Exception("No credentials")):
            manager = AgentManager()
            assert manager.ssm_client is None

    @pytest.mark.asyncio
    async def test_discover_agents_success(self, agent_manager, mock_ssm_client, sample_agent_parameters):
        """Test successful agent discovery."""
        # Mock SSM paginator
        mock_paginator = Mock()
        mock_page_iterator = Mock()
        mock_page_iterator.__iter__ = Mock(return_value=iter([
            {'Parameters': sample_agent_parameters}
        ]))
        mock_paginator.paginate.return_value = mock_page_iterator
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        # Discover agents
        agents = await agent_manager.discover_agents()
        
        # Verify results
        assert len(agents) == 2
        assert 'wa-security-agent' in agents
        assert 'cost-optimization-agent' in agents
        
        # Check first agent
        wa_agent = agents['wa-security-agent']
        assert wa_agent.name == 'WA Security Agent'
        assert wa_agent.tool_count == 6
        assert wa_agent.framework == AgentFramework.BEDROCK
        assert wa_agent.status == AgentStatus.AVAILABLE
        
        # Check second agent
        cost_agent = agents['cost-optimization-agent']
        assert cost_agent.name == 'Cost Optimization Agent'
        assert cost_agent.tool_count == 4
        assert cost_agent.framework == AgentFramework.AGENTCORE
        assert cost_agent.endpoint_url == 'https://example.com/agent'

    @pytest.mark.asyncio
    async def test_discover_agents_no_ssm_client(self, agent_manager):
        """Test agent discovery with no SSM client."""
        agent_manager.ssm_client = None
        
        agents = await agent_manager.discover_agents()
        
        assert agents == {}

    @pytest.mark.asyncio
    async def test_discover_agents_cache_valid(self, agent_manager):
        """Test that cached data is returned when cache is valid."""
        # Set up cache
        agent_manager.agents = {'test-agent': Mock()}
        agent_manager.last_discovery = datetime.utcnow()
        
        agents = await agent_manager.discover_agents()
        
        # Should return cached data without calling SSM
        assert agents == agent_manager.agents

    @pytest.mark.asyncio
    async def test_discover_agents_force_refresh(self, agent_manager, mock_ssm_client):
        """Test force refresh bypasses cache."""
        # Set up cache
        agent_manager.agents = {'old-agent': Mock()}
        agent_manager.last_discovery = datetime.utcnow()
        
        # Mock empty SSM response
        mock_paginator = Mock()
        mock_page_iterator = Mock()
        mock_page_iterator.__iter__ = Mock(return_value=iter([{'Parameters': []}]))
        mock_paginator.paginate.return_value = mock_page_iterator
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        agents = await agent_manager.discover_agents(force_refresh=True)
        
        # Should have called SSM and updated cache
        assert agents == {}
        assert agent_manager.agents == {}

    def test_parse_agent_parameter_success(self, agent_manager):
        """Test successful agent parameter parsing."""
        parameter = {
            'Name': '/coa/agents/test-agent/metadata',
            'Value': json.dumps({
                'name': 'Test Agent',
                'description': 'Test description',
                'capabilities': ['test_capability'],
                'tool_count': 3,
                'framework': 'bedrock'
            })
        }
        
        agent_info = agent_manager._parse_agent_parameter(parameter)
        
        assert agent_info is not None
        assert agent_info.agent_id == 'test-agent'
        assert agent_info.name == 'Test Agent'
        assert agent_info.description == 'Test description'
        assert agent_info.capabilities == ['test_capability']
        assert agent_info.tool_count == 3
        assert agent_info.framework == AgentFramework.BEDROCK

    def test_parse_agent_parameter_invalid_json(self, agent_manager):
        """Test agent parameter parsing with invalid JSON."""
        parameter = {
            'Name': '/coa/agents/test-agent/metadata',
            'Value': 'invalid json'
        }
        
        agent_info = agent_manager._parse_agent_parameter(parameter)
        
        assert agent_info is None

    def test_parse_agent_parameter_invalid_name(self, agent_manager):
        """Test agent parameter parsing with invalid parameter name."""
        parameter = {
            'Name': '/invalid/path',
            'Value': json.dumps({'name': 'Test'})
        }
        
        agent_info = agent_manager._parse_agent_parameter(parameter)
        
        assert agent_info is None

    @pytest.mark.asyncio
    async def test_get_agent_info(self, agent_manager, mock_ssm_client, sample_agent_parameters):
        """Test getting specific agent info."""
        # Mock SSM response
        mock_paginator = Mock()
        mock_page_iterator = Mock()
        mock_page_iterator.__iter__ = Mock(return_value=iter([
            {'Parameters': sample_agent_parameters}
        ]))
        mock_paginator.paginate.return_value = mock_page_iterator
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        agent_info = await agent_manager.get_agent_info('wa-security-agent')
        
        assert agent_info is not None
        assert agent_info.agent_id == 'wa-security-agent'
        assert agent_info.name == 'WA Security Agent'

    @pytest.mark.asyncio
    async def test_get_agent_info_not_found(self, agent_manager, mock_ssm_client):
        """Test getting info for non-existent agent."""
        # Mock empty SSM response
        mock_paginator = Mock()
        mock_page_iterator = Mock()
        mock_page_iterator.__iter__ = Mock(return_value=iter([{'Parameters': []}]))
        mock_paginator.paginate.return_value = mock_paginator
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        agent_info = await agent_manager.get_agent_info('non-existent')
        
        assert agent_info is None

    @pytest.mark.asyncio
    async def test_get_agent_capabilities(self, agent_manager):
        """Test getting agent capabilities."""
        # Set up mock agent
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test',
                capabilities=['cap1', 'cap2'],
                tool_count=2,
                framework=AgentFramework.BEDROCK
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        capabilities = await agent_manager.get_agent_capabilities('test-agent')
        
        assert capabilities == ['cap1', 'cap2']

    @pytest.mark.asyncio
    async def test_get_agent_tool_count(self, agent_manager):
        """Test getting agent tool count."""
        # Set up mock agent
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test',
                capabilities=[],
                tool_count=5,
                framework=AgentFramework.BEDROCK
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        tool_count = await agent_manager.get_agent_tool_count('test-agent')
        
        assert tool_count == 5

    def test_select_agent_for_session_success(self, agent_manager):
        """Test successful agent selection for session."""
        # Set up mock agent
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test',
                capabilities=[],
                tool_count=3,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.AVAILABLE
            )
        }
        
        response = agent_manager.select_agent_for_session('session1', 'test-agent')
        
        assert response.success is True
        assert 'Test Agent' in response.message
        assert agent_manager.session_agents['session1'] == 'test-agent'

    def test_select_agent_for_session_not_found(self, agent_manager):
        """Test agent selection for non-existent agent."""
        response = agent_manager.select_agent_for_session('session1', 'non-existent')
        
        assert response.success is False
        assert 'not found' in response.message

    def test_select_agent_for_session_unavailable(self, agent_manager):
        """Test agent selection for unavailable agent."""
        # Set up unavailable agent
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test',
                capabilities=[],
                tool_count=3,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.UNAVAILABLE
            )
        }
        
        response = agent_manager.select_agent_for_session('session1', 'test-agent')
        
        assert response.success is False
        assert 'unavailable' in response.message

    def test_get_selected_agent(self, agent_manager):
        """Test getting selected agent for session."""
        agent_manager.session_agents['session1'] = 'test-agent'
        
        selected = agent_manager.get_selected_agent('session1')
        
        assert selected == 'test-agent'

    def test_get_selected_agent_none(self, agent_manager):
        """Test getting selected agent when none selected."""
        selected = agent_manager.get_selected_agent('session1')
        
        assert selected is None

    def test_clear_agent_selection_success(self, agent_manager):
        """Test clearing agent selection."""
        agent_manager.session_agents['session1'] = 'test-agent'
        
        response = agent_manager.clear_agent_selection('session1')
        
        assert response.success is True
        assert 'cleared' in response.message.lower()
        assert 'session1' not in agent_manager.session_agents

    def test_clear_agent_selection_none_selected(self, agent_manager):
        """Test clearing agent selection when none selected."""
        response = agent_manager.clear_agent_selection('session1')
        
        assert response.success is True
        assert 'No agent was selected' in response.message

    @pytest.mark.asyncio
    async def test_list_agents_success(self, agent_manager):
        """Test listing agents successfully."""
        # Set up mock agents
        agent_manager.agents = {
            'agent1': AgentInfo(
                agent_id='agent1',
                name='Agent 1',
                description='First agent',
                capabilities=['cap1'],
                tool_count=2,
                framework=AgentFramework.BEDROCK
            ),
            'agent2': AgentInfo(
                agent_id='agent2',
                name='Agent 2',
                description='Second agent',
                capabilities=['cap2'],
                tool_count=3,
                framework=AgentFramework.AGENTCORE
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        agent_manager.session_agents['session1'] = 'agent1'
        
        response = await agent_manager.list_agents('session1')
        
        assert response.success is True
        assert 'Available agents:' in response.message
        assert response.data['total_count'] == 2
        assert response.data['selected_agent'] == 'agent1'

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, agent_manager, mock_ssm_client):
        """Test listing agents when none available."""
        # Mock empty SSM response
        mock_paginator = Mock()
        mock_page_iterator = Mock()
        mock_page_iterator.__iter__ = Mock(return_value=iter([{'Parameters': []}]))
        mock_paginator.paginate.return_value = mock_paginator
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        response = await agent_manager.list_agents()
        
        assert response.success is True
        assert 'No agents are currently available' in response.message

    @pytest.mark.asyncio
    async def test_check_agent_health_available(self, agent_manager):
        """Test checking health of available agent."""
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test',
                capabilities=[],
                tool_count=1,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.AVAILABLE
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        health = await agent_manager.check_agent_health('test-agent')
        
        assert health is True

    @pytest.mark.asyncio
    async def test_check_agent_health_unavailable(self, agent_manager):
        """Test checking health of unavailable agent."""
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test',
                capabilities=[],
                tool_count=1,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.UNAVAILABLE
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        health = await agent_manager.check_agent_health('test-agent')
        
        assert health is False

    def test_get_cache_info(self, agent_manager):
        """Test getting cache information."""
        agent_manager.agents = {'agent1': Mock()}
        agent_manager.last_discovery = datetime.utcnow()
        agent_manager.session_agents = {'session1': 'agent1'}
        
        cache_info = agent_manager.get_cache_info()
        
        assert cache_info['agent_count'] == 1
        assert cache_info['last_discovery'] is not None
        assert cache_info['cache_valid'] is True
        assert cache_info['active_sessions'] == 1

    def test_is_cache_valid_no_discovery(self, agent_manager):
        """Test cache validity when no discovery has occurred."""
        assert agent_manager._is_cache_valid() is False

    def test_is_cache_valid_expired(self, agent_manager):
        """Test cache validity when cache has expired."""
        agent_manager.last_discovery = datetime.utcnow() - timedelta(seconds=400)
        
        assert agent_manager._is_cache_valid() is False

    def test_is_cache_valid_fresh(self, agent_manager):
        """Test cache validity when cache is fresh."""
        agent_manager.last_discovery = datetime.utcnow() - timedelta(seconds=100)
        
        assert agent_manager._is_cache_valid() is True

    @pytest.mark.asyncio
    async def test_get_detailed_agent_capabilities(self, agent_manager):
        """Test getting detailed agent capabilities."""
        # Set up mock agent
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test description',
                capabilities=['cap1', 'cap2'],
                tool_count=5,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.AVAILABLE,
                endpoint_url='https://example.com'
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        capabilities = await agent_manager.get_detailed_agent_capabilities('test-agent')
        
        assert capabilities['found'] is True
        assert capabilities['agent_id'] == 'test-agent'
        assert capabilities['name'] == 'Test Agent'
        assert capabilities['capabilities']['list'] == ['cap1', 'cap2']
        assert capabilities['capabilities']['count'] == 2
        assert capabilities['tools']['count'] == 5
        assert capabilities['is_healthy'] is True

    @pytest.mark.asyncio
    async def test_get_detailed_agent_capabilities_not_found(self, agent_manager):
        """Test getting detailed capabilities for non-existent agent."""
        agent_manager.agents = {}
        agent_manager.last_discovery = datetime.utcnow()
        
        capabilities = await agent_manager.get_detailed_agent_capabilities('non-existent')
        
        assert capabilities['found'] is False
        assert capabilities['agent_id'] == 'non-existent'
        assert 'error' in capabilities

    @pytest.mark.asyncio
    async def test_get_agent_status_summary(self, agent_manager):
        """Test getting agent status summary."""
        # Set up mock agents
        agent_manager.agents = {
            'agent1': AgentInfo(
                agent_id='agent1',
                name='Agent 1',
                description='First agent',
                capabilities=['cap1'],
                tool_count=2,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.AVAILABLE
            ),
            'agent2': AgentInfo(
                agent_id='agent2',
                name='Agent 2',
                description='Second agent',
                capabilities=['cap2', 'cap3'],
                tool_count=3,
                framework=AgentFramework.AGENTCORE,
                status=AgentStatus.UNAVAILABLE
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        summary = await agent_manager.get_agent_status_summary()
        
        assert summary['total_agents'] == 2
        assert summary['status_breakdown']['available'] == 1
        assert summary['status_breakdown']['unavailable'] == 1
        assert summary['framework_breakdown']['bedrock'] == 1
        assert summary['framework_breakdown']['agentcore'] == 1
        assert summary['total_tools_available'] == 5
        assert summary['healthy_agents'] == 1
        assert len(summary['agent_details']) == 2

    def test_get_discovery_metrics(self, agent_manager):
        """Test getting discovery metrics."""
        # Set up some metrics
        agent_manager.discovery_metrics = {
            "total_discoveries": 10,
            "successful_discoveries": 8,
            "failed_discoveries": 2,
            "last_error": "Test error",
            "last_error_time": "2024-01-01T00:00:00",
            "average_discovery_time_ms": 150.5
        }
        
        metrics = agent_manager.get_discovery_metrics()
        
        assert metrics['total_discoveries'] == 10
        assert metrics['successful_discoveries'] == 8
        assert metrics['failed_discoveries'] == 2
        assert metrics['success_rate_percent'] == 80.0
        assert metrics['average_discovery_time_ms'] == 150.5

    def test_extract_mcp_tool_count_primary_field(self, agent_manager):
        """Test MCP tool count extraction from primary field."""
        metadata = {"tool_count": 5}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 5

    def test_extract_mcp_tool_count_alternative_fields(self, agent_manager):
        """Test MCP tool count extraction from alternative fields."""
        # Test mcp_tool_count field
        metadata = {"mcp_tool_count": 3}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 3
        
        # Test tools array
        metadata = {"tools": ["tool1", "tool2", "tool3", "tool4"]}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 4
        
        # Test tools object with count
        metadata = {"tools": {"count": 7}}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 7

    def test_extract_mcp_tool_count_invalid_values(self, agent_manager):
        """Test MCP tool count extraction with invalid values."""
        # Test invalid tool_count
        metadata = {"tool_count": "invalid"}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 0
        
        # Test negative tool_count
        metadata = {"tool_count": -1}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 0
        
        # Test empty metadata
        metadata = {}
        count = agent_manager._extract_mcp_tool_count(metadata, "test-agent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_agent_health_details(self, agent_manager):
        """Test getting detailed agent health information."""
        # Set up mock agent
        agent_manager.agents = {
            'test-agent': AgentInfo(
                agent_id='test-agent',
                name='Test Agent',
                description='Test description',
                capabilities=['cap1', 'cap2'],
                tool_count=5,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.AVAILABLE,
                last_updated=datetime.utcnow()
            )
        }
        agent_manager.last_discovery = datetime.utcnow()
        
        health_details = await agent_manager.get_agent_health_details('test-agent')
        
        assert health_details['healthy'] is True
        assert health_details['agent_id'] == 'test-agent'
        assert health_details['status'] == 'healthy'
        assert health_details['checks']['agent_exists'] is True
        assert health_details['checks']['status_available'] is True
        assert health_details['checks']['valid_tool_count'] is True
        assert health_details['details']['tool_count'] == 5
        assert health_details['details']['capabilities_count'] == 2

    @pytest.mark.asyncio
    async def test_get_agent_health_details_not_found(self, agent_manager):
        """Test getting health details for non-existent agent."""
        agent_manager.agents = {}
        agent_manager.last_discovery = datetime.utcnow()
        
        health_details = await agent_manager.get_agent_health_details('non-existent')
        
        assert health_details['healthy'] is False
        assert health_details['agent_id'] == 'non-existent'
        assert health_details['status'] == 'not_found'
        assert health_details['checks']['agent_exists'] is False

    @pytest.mark.asyncio
    async def test_monitor_agent_status_changes(self, agent_manager, mock_ssm_client):
        """Test monitoring agent status changes."""
        # Set up initial agents
        agent_manager.agents = {
            'agent1': AgentInfo(
                agent_id='agent1',
                name='Agent 1',
                description='First agent',
                capabilities=['cap1'],
                tool_count=2,
                framework=AgentFramework.BEDROCK,
                status=AgentStatus.AVAILABLE
            )
        }
        
        # Mock SSM response with changes
        sample_parameters = [
            {
                'Name': '/coa/agents/agent1/metadata',
                'Value': json.dumps({
                    'name': 'Agent 1',
                    'description': 'First agent',
                    'capabilities': ['cap1', 'cap2'],  # Added capability
                    'tool_count': 3,  # Changed tool count
                    'framework': 'bedrock',
                    'status': 'unavailable'  # Changed status
                })
            },
            {
                'Name': '/coa/agents/agent2/metadata',  # New agent
                'Value': json.dumps({
                    'name': 'Agent 2',
                    'description': 'Second agent',
                    'capabilities': ['cap3'],
                    'tool_count': 1,
                    'framework': 'bedrock',
                    'status': 'available'
                })
            }
        ]
        
        mock_paginator = Mock()
        mock_page_iterator = Mock()
        mock_page_iterator.__iter__ = Mock(return_value=iter([
            {'Parameters': sample_parameters}
        ]))
        mock_paginator.paginate.return_value = mock_page_iterator
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        changes = await agent_manager.monitor_agent_status_changes()
        
        assert len(changes['new_agents']) == 1
        assert changes['new_agents'][0]['agent_id'] == 'agent2'
        assert len(changes['status_changes']) == 1
        assert changes['status_changes'][0]['agent_id'] == 'agent1'
        assert changes['status_changes'][0]['old_status'] == 'available'
        assert changes['status_changes'][0]['new_status'] == 'unavailable'
        assert len(changes['capability_changes']) == 1
        assert changes['capability_changes'][0]['agent_id'] == 'agent1'
        assert 'cap2' in changes['capability_changes'][0]['added_capabilities']
        assert len(changes['tool_count_changes']) == 1
        assert changes['tool_count_changes'][0]['agent_id'] == 'agent1'
        assert changes['tool_count_changes'][0]['old_count'] == 2
        assert changes['tool_count_changes'][0]['new_count'] == 3