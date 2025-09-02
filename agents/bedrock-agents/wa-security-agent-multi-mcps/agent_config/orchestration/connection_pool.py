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
Connection Pool Manager for MCP Servers
Manages connection pooling, load balancing, and connection health monitoring
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_config.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a connection in the pool"""

    connection_id: str
    server_name: str
    created_at: datetime
    last_used: datetime
    is_active: bool = True
    use_count: int = 0
    error_count: int = 0
    connection_object: Any = None


@dataclass
class PoolStats:
    """Statistics for connection pool monitoring"""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    pool_utilization: float = 0.0


class ConnectionPoolManager:
    """
    Manages connection pools for multiple MCP servers with load balancing
    """

    def __init__(self, max_connections_per_server: int = 5, max_idle_time: int = 300):
        """Initialize the connection pool manager"""
        self.max_connections_per_server = max_connections_per_server
        self.max_idle_time = max_idle_time  # seconds

        # Connection pools by server name
        self.pools: Dict[str, List[ConnectionInfo]] = {}

        # Pool statistics
        self.stats: Dict[str, PoolStats] = {}

        # Load balancing - round robin counters
        self.round_robin_counters: Dict[str, int] = {}

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 60  # seconds

        # Locks for thread safety
        self._pool_locks: Dict[str, asyncio.Lock] = {}

        logger.info(
            f"Connection pool manager initialized - Max connections per server: {max_connections_per_server}"
        )

    async def get_connection(self, server_name: str) -> Optional[ConnectionInfo]:
        """Get an available connection from the pool using load balancing"""
        if server_name not in self._pool_locks:
            self._pool_locks[server_name] = asyncio.Lock()

        async with self._pool_locks[server_name]:
            # Initialize pool if it doesn't exist
            if server_name not in self.pools:
                self.pools[server_name] = []
                self.stats[server_name] = PoolStats()
                self.round_robin_counters[server_name] = 0

            pool = self.pools[server_name]
            stats = self.stats[server_name]

            # Find an available connection using round-robin load balancing
            available_connections = [
                conn for conn in pool if conn.is_active and conn.connection_object
            ]

            if available_connections:
                # Use round-robin to select connection
                counter = self.round_robin_counters[server_name]
                selected_connection = available_connections[
                    counter % len(available_connections)
                ]
                self.round_robin_counters[server_name] = (counter + 1) % len(
                    available_connections
                )

                # Update connection usage
                selected_connection.last_used = datetime.now()
                selected_connection.use_count += 1

                logger.debug(
                    f"Reusing connection {selected_connection.connection_id} for {server_name}"
                )
                return selected_connection

            # No available connections, check if we can create a new one
            if len(pool) < self.max_connections_per_server:
                connection_id = f"{server_name}_{len(pool)}_{int(time.time())}"
                new_connection = ConnectionInfo(
                    connection_id=connection_id,
                    server_name=server_name,
                    created_at=datetime.now(),
                    last_used=datetime.now(),
                    is_active=True,
                    use_count=1,
                )

                pool.append(new_connection)
                stats.total_connections += 1

                logger.info(f"Created new connection {connection_id} for {server_name}")
                return new_connection

            # Pool is full, wait for an available connection or return None
            logger.warning(
                f"Connection pool for {server_name} is full ({self.max_connections_per_server} connections)"
            )
            return None

    async def return_connection(
        self, connection: ConnectionInfo, success: bool = True
    ) -> None:
        """Return a connection to the pool and update statistics"""
        server_name = connection.server_name

        if server_name not in self._pool_locks:
            return

        async with self._pool_locks[server_name]:
            if server_name in self.stats:
                stats = self.stats[server_name]
                stats.total_requests += 1

                if success:
                    stats.successful_requests += 1
                    connection.error_count = 0  # Reset error count on success
                else:
                    stats.failed_requests += 1
                    connection.error_count += 1

                    # Mark connection as inactive if too many errors
                    if connection.error_count >= 3:
                        connection.is_active = False
                        logger.warning(
                            f"Connection {connection.connection_id} marked as inactive due to errors"
                        )

                # Update success rate
                if stats.total_requests > 0:
                    success_rate = stats.successful_requests / stats.total_requests
                    logger.debug(
                        f"Connection pool success rate for {server_name}: {success_rate:.2%}"
                    )

    async def close_connection(self, connection: ConnectionInfo) -> None:
        """Close and remove a connection from the pool"""
        server_name = connection.server_name

        if server_name not in self._pool_locks:
            return

        async with self._pool_locks[server_name]:
            if server_name in self.pools:
                pool = self.pools[server_name]
                if connection in pool:
                    pool.remove(connection)

                    # Close the actual connection object if it exists
                    if connection.connection_object and hasattr(
                        connection.connection_object, "close"
                    ):
                        try:
                            await connection.connection_object.close()
                        except Exception as e:
                            logger.error(
                                f"Error closing connection {connection.connection_id}: {e}"
                            )

                    if server_name in self.stats:
                        self.stats[server_name].total_connections -= 1

                    logger.info(
                        f"Closed and removed connection {connection.connection_id}"
                    )

    async def health_check_pool(self, server_name: str) -> Dict[str, Any]:
        """Perform health check on all connections in a pool"""
        if server_name not in self.pools:
            return {"healthy": 0, "unhealthy": 0, "total": 0}

        async with self._pool_locks.get(server_name, asyncio.Lock()):
            pool = self.pools[server_name]
            healthy_count = 0
            unhealthy_count = 0

            for connection in pool:
                if connection.is_active and connection.error_count < 3:
                    healthy_count += 1
                else:
                    unhealthy_count += 1

            return {
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "total": len(pool),
                "utilization": len(pool) / self.max_connections_per_server
                if self.max_connections_per_server > 0
                else 0,
            }

    async def cleanup_idle_connections(self) -> None:
        """Clean up idle connections that haven't been used recently"""
        current_time = datetime.now()
        cleanup_count = 0

        for server_name in list(self.pools.keys()):
            if server_name not in self._pool_locks:
                continue

            async with self._pool_locks[server_name]:
                pool = self.pools[server_name]
                connections_to_remove = []

                for connection in pool:
                    idle_time = (current_time - connection.last_used).total_seconds()

                    if idle_time > self.max_idle_time or not connection.is_active:
                        connections_to_remove.append(connection)

                # Remove idle connections
                for connection in connections_to_remove:
                    await self.close_connection(connection)
                    cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} idle connections")

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            return

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started connection pool cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up idle connections"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_idle_connections()
            except asyncio.CancelledError:
                logger.info("Connection pool cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in connection pool cleanup: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all connection pools"""
        total_stats = {
            "pools": {},
            "overall": {
                "total_servers": len(self.pools),
                "total_connections": 0,
                "total_requests": 0,
                "overall_success_rate": 0.0,
            },
        }

        total_connections = 0
        total_requests = 0
        total_successful = 0

        for server_name, pool in self.pools.items():
            stats = self.stats.get(server_name, PoolStats())
            health_info = await self.health_check_pool(server_name)

            pool_stats = {
                "connections": len(pool),
                "max_connections": self.max_connections_per_server,
                "active_connections": health_info["healthy"],
                "idle_connections": health_info["total"] - health_info["healthy"],
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
                "success_rate": stats.successful_requests / stats.total_requests
                if stats.total_requests > 0
                else 0.0,
                "utilization": health_info["utilization"],
            }

            total_stats["pools"][server_name] = pool_stats
            total_connections += len(pool)
            total_requests += stats.total_requests
            total_successful += stats.successful_requests

        # Calculate overall statistics
        total_stats["overall"]["total_connections"] = total_connections
        total_stats["overall"]["total_requests"] = total_requests
        total_stats["overall"]["overall_success_rate"] = (
            total_successful / total_requests if total_requests > 0 else 0.0
        )

        return total_stats

    async def close_all(self) -> None:
        """Close all connections and clean up resources"""
        logger.info("Closing all connection pools...")

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for server_name, pool in self.pools.items():
            async with self._pool_locks.get(server_name, asyncio.Lock()):
                for connection in pool[
                    :
                ]:  # Create a copy to avoid modification during iteration
                    await self.close_connection(connection)

        # Clear all data structures
        self.pools.clear()
        self.stats.clear()
        self.round_robin_counters.clear()
        self._pool_locks.clear()

        logger.info("All connection pools closed")

    def set_connection_object(
        self, connection: ConnectionInfo, connection_object: Any
    ) -> None:
        """Set the actual connection object for a ConnectionInfo"""
        connection.connection_object = connection_object
        logger.debug(f"Set connection object for {connection.connection_id}")

    async def get_pool_status(self, server_name: str) -> Dict[str, Any]:
        """Get detailed status for a specific pool"""
        if server_name not in self.pools:
            return {"exists": False}

        health_info = await self.health_check_pool(server_name)
        stats = self.stats.get(server_name, PoolStats())

        return {
            "exists": True,
            "server_name": server_name,
            "connections": health_info,
            "statistics": {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
                "success_rate": stats.successful_requests / stats.total_requests
                if stats.total_requests > 0
                else 0.0,
            },
            "configuration": {
                "max_connections": self.max_connections_per_server,
                "max_idle_time": self.max_idle_time,
            },
        }
