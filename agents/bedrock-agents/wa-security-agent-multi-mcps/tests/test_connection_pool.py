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
Unit tests for Connection Pool Manager
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from agent_config.orchestration.connection_pool import ConnectionPoolManager, ConnectionInfo, PoolStats


class TestConnectionPoolManager:
    """Test cases for Connection Pool Manager"""
    
    @pytest.fixture
    def pool_manager(self):
        """Create connection pool manager for testing"""
        return ConnectionPoolManager(max_connections_per_server=3, max_idle_time=60)
    
    @pytest.fixture
    def mock_connection_object(self):
        """Create mock connection object"""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()
        return mock_conn
    
    @pytest.mark.asyncio
    async def test_initialization(self, pool_manager):
        """Test pool manager initialization"""
        assert pool_manager.max_connections_per_server == 3
        assert pool_manager.max_idle_time == 60
        assert len(pool_manager.pools) == 0
        assert len(pool_manager.stats) == 0
        assert len(pool_manager.round_robin_counters) == 0
    
    @pytest.mark.asyncio
    async def test_get_connection_new_pool(self, pool_manager):
        """Test getting connection from new pool"""
        connection = await pool_manager.get_connection("test_server")
        
        assert connection is not None
        assert connection.server_name == "test_server"
        assert connection.is_active is True
        assert connection.use_count == 1
        assert "test_server" in pool_manager.pools
        assert len(pool_manager.pools["test_server"]) == 1
        assert pool_manager.stats["test_server"].total_connections == 1
    
    @pytest.mark.asyncio
    async def test_get_connection_reuse_existing(self, pool_manager, mock_connection_object):
        """Test reusing existing connection"""
        # Create first connection
        connection1 = await pool_manager.get_connection("test_server")
        connection1.connection_object = mock_connection_object
        
        # Get second connection (should reuse)
        connection2 = await pool_manager.get_connection("test_server")
        
        assert connection2 == connection1
        assert connection1.use_count == 2
        assert len(pool_manager.pools["test_server"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_connection_pool_full(self, pool_manager, mock_connection_object):
        """Test getting connection when pool is full"""
        # Fill the pool to max capacity
        connections = []
        for i in range(3):  # max_connections_per_server = 3
            conn = await pool_manager.get_connection("test_server")
            conn.connection_object = mock_connection_object
            connections.append(conn)
        
        # Try to get another connection
        connection = await pool_manager.get_connection("test_server")
        
        # Should reuse one of the existing connections
        assert connection in connections
        assert len(pool_manager.pools["test_server"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_connection_round_robin(self, pool_manager, mock_connection_object):
        """Test round-robin load balancing"""
        # Create multiple connections
        connections = []
        for i in range(3):
            conn = await pool_manager.get_connection("test_server")
            conn.connection_object = mock_connection_object
            connections.append(conn)
        
        # Reset use counts
        for conn in connections:
            conn.use_count = 1
        
        # Get connections and verify round-robin
        selected_connections = []
        for i in range(6):  # Get more connections than pool size
            conn = await pool_manager.get_connection("test_server")
            selected_connections.append(conn)
        
        # Each connection should be selected twice (6 requests / 3 connections = 2)
        use_counts = [conn.use_count for conn in connections]
        assert all(count == 3 for count in use_counts)  # 1 initial + 2 from round-robin
    
    @pytest.mark.asyncio
    async def test_return_connection_success(self, pool_manager):
        """Test returning connection with success"""
        connection = await pool_manager.get_connection("test_server")
        initial_requests = pool_manager.stats["test_server"].total_requests
        
        await pool_manager.return_connection(connection, success=True)
        
        stats = pool_manager.stats["test_server"]
        assert stats.total_requests == initial_requests + 1
        assert stats.successful_requests == 1
        assert stats.failed_requests == 0
        assert connection.error_count == 0
    
    @pytest.mark.asyncio
    async def test_return_connection_failure(self, pool_manager):
        """Test returning connection with failure"""
        connection = await pool_manager.get_connection("test_server")
        
        await pool_manager.return_connection(connection, success=False)
        
        stats = pool_manager.stats["test_server"]
        assert stats.failed_requests == 1
        assert connection.error_count == 1
        assert connection.is_active is True  # Still active after 1 error
    
    @pytest.mark.asyncio
    async def test_return_connection_multiple_failures(self, pool_manager):
        """Test connection marked inactive after multiple failures"""
        connection = await pool_manager.get_connection("test_server")
        
        # Simulate multiple failures
        for i in range(3):
            await pool_manager.return_connection(connection, success=False)
        
        assert connection.error_count == 3
        assert connection.is_active is False  # Should be marked inactive
    
    @pytest.mark.asyncio
    async def test_close_connection(self, pool_manager, mock_connection_object):
        """Test closing a connection"""
        connection = await pool_manager.get_connection("test_server")
        connection.connection_object = mock_connection_object
        
        initial_count = pool_manager.stats["test_server"].total_connections
        
        await pool_manager.close_connection(connection)
        
        assert connection not in pool_manager.pools["test_server"]
        assert pool_manager.stats["test_server"].total_connections == initial_count - 1
        mock_connection_object.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_pool(self, pool_manager, mock_connection_object):
        """Test health check for a pool"""
        # Create healthy and unhealthy connections
        healthy_conn = await pool_manager.get_connection("test_server")
        healthy_conn.connection_object = mock_connection_object
        
        unhealthy_conn = await pool_manager.get_connection("test_server")
        unhealthy_conn.connection_object = mock_connection_object
        unhealthy_conn.is_active = False
        unhealthy_conn.error_count = 5
        
        health_info = await pool_manager.health_check_pool("test_server")
        
        assert health_info["healthy"] == 1
        assert health_info["unhealthy"] == 1
        assert health_info["total"] == 2
        assert health_info["utilization"] == 2/3  # 2 connections out of max 3
    
    @pytest.mark.asyncio
    async def test_health_check_nonexistent_pool(self, pool_manager):
        """Test health check for non-existent pool"""
        health_info = await pool_manager.health_check_pool("nonexistent")
        
        assert health_info["healthy"] == 0
        assert health_info["unhealthy"] == 0
        assert health_info["total"] == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_idle_connections(self, pool_manager, mock_connection_object):
        """Test cleanup of idle connections"""
        # Create connection and make it idle
        connection = await pool_manager.get_connection("test_server")
        connection.connection_object = mock_connection_object
        connection.last_used = datetime.now() - timedelta(seconds=120)  # 2 minutes ago
        
        initial_count = len(pool_manager.pools["test_server"])
        
        await pool_manager.cleanup_idle_connections()
        
        # Connection should be removed due to being idle
        assert len(pool_manager.pools["test_server"]) == initial_count - 1
        mock_connection_object.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_connections(self, pool_manager, mock_connection_object):
        """Test cleanup of inactive connections"""
        # Create inactive connection
        connection = await pool_manager.get_connection("test_server")
        connection.connection_object = mock_connection_object
        connection.is_active = False
        
        initial_count = len(pool_manager.pools["test_server"])
        
        await pool_manager.cleanup_idle_connections()
        
        # Connection should be removed due to being inactive
        assert len(pool_manager.pools["test_server"]) == initial_count - 1
        mock_connection_object.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, pool_manager):
        """Test starting cleanup task"""
        await pool_manager.start_cleanup_task()
        
        assert pool_manager._cleanup_task is not None
        assert not pool_manager._cleanup_task.done()
        
        # Cancel the task to clean up
        pool_manager._cleanup_task.cancel()
        try:
            await pool_manager._cleanup_task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_get_stats(self, pool_manager, mock_connection_object):
        """Test getting comprehensive statistics"""
        # Create connections in multiple pools
        conn1 = await pool_manager.get_connection("server1")
        conn1.connection_object = mock_connection_object
        await pool_manager.return_connection(conn1, success=True)
        
        conn2 = await pool_manager.get_connection("server2")
        conn2.connection_object = mock_connection_object
        await pool_manager.return_connection(conn2, success=False)
        
        stats = await pool_manager.get_stats()
        
        assert stats["overall"]["total_servers"] == 2
        assert stats["overall"]["total_connections"] == 2
        assert stats["overall"]["total_requests"] == 2
        assert stats["overall"]["overall_success_rate"] == 0.5
        
        assert "server1" in stats["pools"]
        assert "server2" in stats["pools"]
        assert stats["pools"]["server1"]["success_rate"] == 1.0
        assert stats["pools"]["server2"]["success_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_close_all(self, pool_manager, mock_connection_object):
        """Test closing all connections"""
        # Create connections in multiple pools
        conn1 = await pool_manager.get_connection("server1")
        conn1.connection_object = mock_connection_object
        
        conn2 = await pool_manager.get_connection("server2")
        conn2.connection_object = mock_connection_object
        
        # Start cleanup task
        await pool_manager.start_cleanup_task()
        
        await pool_manager.close_all()
        
        # All pools should be empty
        assert len(pool_manager.pools) == 0
        assert len(pool_manager.stats) == 0
        assert len(pool_manager.round_robin_counters) == 0
        
        # Cleanup task should be cancelled
        assert pool_manager._cleanup_task.cancelled() or pool_manager._cleanup_task.done()
    
    def test_set_connection_object(self, pool_manager):
        """Test setting connection object"""
        connection = ConnectionInfo(
            connection_id="test_id",
            server_name="test_server",
            created_at=datetime.now(),
            last_used=datetime.now()
        )
        
        mock_obj = Mock()
        pool_manager.set_connection_object(connection, mock_obj)
        
        assert connection.connection_object == mock_obj
    
    @pytest.mark.asyncio
    async def test_get_pool_status_existing(self, pool_manager, mock_connection_object):
        """Test getting status for existing pool"""
        conn = await pool_manager.get_connection("test_server")
        conn.connection_object = mock_connection_object
        await pool_manager.return_connection(conn, success=True)
        
        status = await pool_manager.get_pool_status("test_server")
        
        assert status["exists"] is True
        assert status["server_name"] == "test_server"
        assert status["connections"]["total"] == 1
        assert status["statistics"]["total_requests"] == 1
        assert status["configuration"]["max_connections"] == 3
    
    @pytest.mark.asyncio
    async def test_get_pool_status_nonexistent(self, pool_manager):
        """Test getting status for non-existent pool"""
        status = await pool_manager.get_pool_status("nonexistent")
        
        assert status["exists"] is False


class TestConnectionInfo:
    """Test cases for ConnectionInfo dataclass"""
    
    def test_connection_info_creation(self):
        """Test creating ConnectionInfo instance"""
        now = datetime.now()
        conn = ConnectionInfo(
            connection_id="test_id",
            server_name="test_server",
            created_at=now,
            last_used=now
        )
        
        assert conn.connection_id == "test_id"
        assert conn.server_name == "test_server"
        assert conn.created_at == now
        assert conn.last_used == now
        assert conn.is_active is True
        assert conn.use_count == 0
        assert conn.error_count == 0
        assert conn.connection_object is None


class TestPoolStats:
    """Test cases for PoolStats dataclass"""
    
    def test_pool_stats_creation(self):
        """Test creating PoolStats instance"""
        stats = PoolStats()
        
        assert stats.total_connections == 0
        assert stats.active_connections == 0
        assert stats.idle_connections == 0
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.average_response_time == 0.0
        assert stats.pool_utilization == 0.0


if __name__ == "__main__":
    pytest.main([__file__])