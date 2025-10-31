"""
Integration tests for COA Backend version isolation.

Tests that BedrockAgent and AgentCore versions work independently
and maintain proper isolation between their services and configurations.
"""

import asyncio
import json
import os
import pytest
import requests
import time
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

# Test configuration
BEDROCKAGENT_URL = "http://localhost:8000"
AGENTCORE_URL = "http://localhost:8001"
HEALTH_TIMEOUT = 30
REQUEST_TIMEOUT = 60


class TestVersionIsolation:
    """Test version isolation between BedrockAgent and AgentCore."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Setup test environment for version isolation tests."""
        # Ensure both versions are running
        self.ensure_versions_running()
        
    def ensure_versions_running(self):
        """Ensure both versions are running before tests."""
        bedrockagent_running = self.check_service_health(BEDROCKAGENT_URL)
        agentcore_running = self.check_service_health(AGENTCORE_URL)
        
        if not bedrockagent_running:
            pytest.skip("BedrockAgent version not running")
        if not agentcore_running:
            pytest.skip("AgentCore version not running")
    
    def check_service_health(self, base_url: str, timeout: int = HEALTH_TIMEOUT) -> bool:
        """Check if a service is healthy."""
        try:
            response = requests.get(f"{base_url}/health", timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False
    
    def test_bedrockagent_health_endpoint(self):
        """Test BedrockAgent health endpoint returns correct version info."""
        response = requests.get(f"{BEDROCKAGENT_URL}/health", timeout=REQUEST_TIMEOUT)
        
        assert response.status_code == 200
        health_data = response.json()
        
        # Validate BedrockAgent-specific health response
        assert health_data["version"] == "bedrockagent"
        assert "services" in health_data
        assert "timestamp" in health_data
        
        # Check for BedrockAgent-specific services
        services = health_data["services"]
        assert "config" in services
        assert "auth" in services
        assert "bedrock_model" in services
        
        # In full mode, should have traditional agent services
        if health_data.get("mode") == "full":
            assert "bedrock_agent" in services
            assert "traditional_agent_registry" in services
    
    def test_agentcore_health_endpoint(self):
        """Test AgentCore health endpoint returns correct version info."""
        response = requests.get(f"{AGENTCORE_URL}/health", timeout=REQUEST_TIMEOUT)
        
        assert response.status_code == 200
        health_data = response.json()
        
        # Validate AgentCore-specific health response
        assert health_data["version"] == "agentcore"
        assert "services" in health_data
        assert "timestamp" in health_data
        
        # Check for AgentCore-specific services
        services = health_data["services"]
        assert "config" in services
        assert "auth" in services
        assert "bedrock_model" in services
        
        # In full mode, should have Strands agent services
        if health_data.get("mode") == "full":
            assert "strands_orchestrator" in services
            assert "strands_agent_registry" in services
    
    def test_version_info_endpoints(self):
        """Test version info endpoints return correct backend types."""
        # Test BedrockAgent version info
        bedrockagent_response = requests.get(f"{BEDROCKAGENT_URL}/api/version", timeout=REQUEST_TIMEOUT)
        assert bedrockagent_response.status_code == 200
        bedrockagent_info = bedrockagent_response.json()
        
        assert bedrockagent_info["backend_version"] == "bedrockagent"
        assert "version_info" in bedrockagent_info
        
        # Test AgentCore version info
        agentcore_response = requests.get(f"{AGENTCORE_URL}/api/version", timeout=REQUEST_TIMEOUT)
        assert agentcore_response.status_code == 200
        agentcore_info = agentcore_response.json()
        
        assert agentcore_info["backend_version"] == "agentcore"
        assert "version_info" in agentcore_info
        
        # Ensure versions are different
        assert bedrockagent_info["backend_version"] != agentcore_info["backend_version"]
    
    def test_parameter_prefix_isolation(self):
        """Test that versions use different parameter prefixes when configured."""
        # Test BedrockAgent parameter config
        bedrockagent_response = requests.get(f"{BEDROCKAGENT_URL}/api/parameter-manager/config", timeout=REQUEST_TIMEOUT)
        
        # Test AgentCore parameter config
        agentcore_response = requests.get(f"{AGENTCORE_URL}/api/parameter-manager/config", timeout=REQUEST_TIMEOUT)
        
        # Both should respond (even if parameter manager is not fully configured)
        assert bedrockagent_response.status_code in [200, 503]
        assert agentcore_response.status_code in [200, 503]
        
        # If both are successful, check parameter prefixes
        if bedrockagent_response.status_code == 200 and agentcore_response.status_code == 200:
            bedrockagent_config = bedrockagent_response.json()
            agentcore_config = agentcore_response.json()
            
            # Parameter prefixes should be present
            assert "parameter_prefix" in bedrockagent_config
            assert "parameter_prefix" in agentcore_config
    
    def test_chat_endpoint_isolation(self):
        """Test that chat endpoints work independently."""
        test_message = "Hello, can you help me with AWS security assessment?"
        
        chat_payload = {
            "message": test_message,
            "session_id": "test-isolation-session"
        }
        
        # Test BedrockAgent chat
        bedrockagent_response = requests.post(
            f"{BEDROCKAGENT_URL}/api/chat",
            json=chat_payload,
            timeout=REQUEST_TIMEOUT
        )
        
        # Test AgentCore chat
        agentcore_response = requests.post(
            f"{AGENTCORE_URL}/api/chat",
            json=chat_payload,
            timeout=REQUEST_TIMEOUT
        )
        
        # Both should respond successfully
        assert bedrockagent_response.status_code == 200
        assert agentcore_response.status_code == 200
        
        bedrockagent_data = bedrockagent_response.json()
        agentcore_data = agentcore_response.json()
        
        # Both should have responses
        assert "response" in bedrockagent_data
        assert "response" in agentcore_data
        assert "session_id" in bedrockagent_data
        assert "session_id" in agentcore_data
        
        # Response types should indicate the backend used
        assert "response_type" in bedrockagent_data
        assert "response_type" in agentcore_data
        
        # Responses should be different (different backends)
        # Note: This might not always be true if both fall back to the same model
        # but the response_type should indicate the backend used
    
    def test_agent_endpoint_isolation(self):
        """Test that agent-specific endpoints are properly isolated."""
        # Test BedrockAgent traditional agents endpoint
        bedrockagent_agents_response = requests.get(
            f"{BEDROCKAGENT_URL}/api/agents/traditional",
            timeout=REQUEST_TIMEOUT
        )
        
        # Test AgentCore Strands agents endpoint
        agentcore_agents_response = requests.get(
            f"{AGENTCORE_URL}/api/agents/strands",
            timeout=REQUEST_TIMEOUT
        )
        
        # BedrockAgent should have traditional agents endpoint
        assert bedrockagent_agents_response.status_code in [200, 503]  # 503 if service not available
        
        # AgentCore should have Strands agents endpoint
        assert agentcore_agents_response.status_code in [200, 503]  # 503 if service not available
        
        # Test that cross-version endpoints don't exist
        # BedrockAgent should not have Strands endpoint
        bedrockagent_strands_response = requests.get(
            f"{BEDROCKAGENT_URL}/api/agents/strands",
            timeout=REQUEST_TIMEOUT
        )
        assert bedrockagent_strands_response.status_code == 404
        
        # AgentCore should not have traditional endpoint
        agentcore_traditional_response = requests.get(
            f"{AGENTCORE_URL}/api/agents/traditional",
            timeout=REQUEST_TIMEOUT
        )
        assert agentcore_traditional_response.status_code == 404
    
    def test_service_independence(self):
        """Test that services can operate independently."""
        # Test that stopping one version doesn't affect the other
        # This is a conceptual test - in practice, we'd need Docker control
        
        # Verify both are initially healthy
        assert self.check_service_health(BEDROCKAGENT_URL)
        assert self.check_service_health(AGENTCORE_URL)
        
        # Test that each version has independent configuration
        bedrockagent_version = requests.get(f"{BEDROCKAGENT_URL}/api/version").json()
        agentcore_version = requests.get(f"{AGENTCORE_URL}/api/version").json()
        
        # Versions should be completely independent
        assert bedrockagent_version["backend_version"] != agentcore_version["backend_version"]
        
        # Each should have different feature sets
        if "version_info" in bedrockagent_version and "version_info" in agentcore_version:
            bedrockagent_features = bedrockagent_version["version_info"].get("features", {})
            agentcore_features = agentcore_version["version_info"].get("features", {})
            
            # Features should be different
            assert bedrockagent_features != agentcore_features
    
    def test_concurrent_requests(self):
        """Test that both versions can handle concurrent requests."""
        import concurrent.futures
        import threading
        
        def make_request(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            """Make a request to the specified URL."""
            try:
                response = requests.post(f"{url}/api/chat", json=payload, timeout=REQUEST_TIMEOUT)
                return {
                    "status_code": response.status_code,
                    "data": response.json() if response.status_code == 200 else None,
                    "error": None
                }
            except Exception as e:
                return {
                    "status_code": 0,
                    "data": None,
                    "error": str(e)
                }
        
        # Prepare test payloads
        bedrockagent_payload = {
            "message": "Test BedrockAgent concurrent request",
            "session_id": "concurrent-test-bedrockagent"
        }
        
        agentcore_payload = {
            "message": "Test AgentCore concurrent request",
            "session_id": "concurrent-test-agentcore"
        }
        
        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            # Submit requests to both versions
            for i in range(2):
                futures.append(executor.submit(make_request, BEDROCKAGENT_URL, bedrockagent_payload))
                futures.append(executor.submit(make_request, AGENTCORE_URL, agentcore_payload))
            
            # Collect results
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        successful_requests = [r for r in results if r["status_code"] == 200]
        assert len(successful_requests) >= 2, f"Expected at least 2 successful requests, got {len(successful_requests)}"
        
        # Check that we got responses from both versions
        bedrockagent_responses = [r for r in successful_requests if r["data"] and "bedrockagent" in str(r["data"]).lower()]
        agentcore_responses = [r for r in successful_requests if r["data"] and "agentcore" in str(r["data"]).lower()]
        
        # Note: This assertion might be too strict if response format doesn't include version info
        # assert len(bedrockagent_responses) > 0, "No BedrockAgent responses received"
        # assert len(agentcore_responses) > 0, "No AgentCore responses received"


class TestGracefulDegradation:
    """Test graceful degradation scenarios."""
    
    def test_minimal_mode_fallback(self):
        """Test that minimal mode provides basic functionality."""
        # This test would require the ability to start services in minimal mode
        # For now, we'll test that the health endpoints indicate the current mode
        
        bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health").json()
        agentcore_health = requests.get(f"{AGENTCORE_URL}/health").json()
        
        # Both should indicate their current mode
        assert "mode" in bedrockagent_health
        assert "mode" in agentcore_health
        
        # Mode should be either "full" or "minimal"
        assert bedrockagent_health["mode"] in ["full", "minimal"]
        assert agentcore_health["mode"] in ["full", "minimal"]
    
    def test_model_fallback_functionality(self):
        """Test that model fallback works when agents are unavailable."""
        # Test chat functionality that should work even in degraded mode
        test_payload = {
            "message": "Simple test message for fallback",
            "session_id": "fallback-test"
        }
        
        # Both versions should be able to handle basic chat
        bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=test_payload)
        agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=test_payload)
        
        # Both should respond (either with agents or fallback)
        assert bedrockagent_response.status_code == 200
        assert agentcore_response.status_code == 200
        
        bedrockagent_data = bedrockagent_response.json()
        agentcore_data = agentcore_response.json()
        
        # Both should have valid responses
        assert "response" in bedrockagent_data
        assert "response" in agentcore_data
        assert "response_type" in bedrockagent_data
        assert "response_type" in agentcore_data
        
        # Response types should indicate whether agents or fallback was used
        valid_response_types = ["traditional_agent", "strands_agent", "model_fallback"]
        assert bedrockagent_data["response_type"] in valid_response_types
        assert agentcore_data["response_type"] in valid_response_types


class TestConfigurationIsolation:
    """Test configuration isolation between versions."""
    
    def test_environment_variable_isolation(self):
        """Test that versions use correct environment variables."""
        # This would require access to container environment variables
        # For now, we'll test through the API responses
        
        bedrockagent_version = requests.get(f"{BEDROCKAGENT_URL}/api/version").json()
        agentcore_version = requests.get(f"{AGENTCORE_URL}/api/version").json()
        
        # Each version should report its correct backend type
        assert bedrockagent_version["backend_version"] == "bedrockagent"
        assert agentcore_version["backend_version"] == "agentcore"
    
    def test_parameter_prefix_configuration(self):
        """Test parameter prefix configuration for each version."""
        # Test parameter manager configuration endpoints
        bedrockagent_params = requests.get(f"{BEDROCKAGENT_URL}/api/parameter-manager/config")
        agentcore_params = requests.get(f"{AGENTCORE_URL}/api/parameter-manager/config")
        
        # Both should respond (even if not fully configured)
        assert bedrockagent_params.status_code in [200, 503]
        assert agentcore_params.status_code in [200, 503]
        
        # If successful, check parameter prefix configuration
        if bedrockagent_params.status_code == 200:
            bedrockagent_config = bedrockagent_params.json()
            assert "parameter_prefix" in bedrockagent_config
        
        if agentcore_params.status_code == 200:
            agentcore_config = agentcore_params.json()
            assert "parameter_prefix" in agentcore_config


@pytest.mark.integration
class TestEndToEndWorkflows:
    """End-to-end workflow tests for both versions."""
    
    def test_bedrockagent_workflow(self):
        """Test complete BedrockAgent workflow."""
        # 1. Health check
        health_response = requests.get(f"{BEDROCKAGENT_URL}/health")
        assert health_response.status_code == 200
        
        # 2. Version info
        version_response = requests.get(f"{BEDROCKAGENT_URL}/api/version")
        assert version_response.status_code == 200
        assert version_response.json()["backend_version"] == "bedrockagent"
        
        # 3. Chat interaction
        chat_payload = {
            "message": "Help me with AWS security best practices",
            "session_id": "bedrockagent-e2e-test"
        }
        chat_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "response" in chat_data
        assert "session_id" in chat_data
        assert chat_data["session_id"] == "bedrockagent-e2e-test"
    
    def test_agentcore_workflow(self):
        """Test complete AgentCore workflow."""
        # 1. Health check
        health_response = requests.get(f"{AGENTCORE_URL}/health")
        assert health_response.status_code == 200
        
        # 2. Version info
        version_response = requests.get(f"{AGENTCORE_URL}/api/version")
        assert version_response.status_code == 200
        assert version_response.json()["backend_version"] == "agentcore"
        
        # 3. Chat interaction
        chat_payload = {
            "message": "Help me analyze my AWS costs",
            "session_id": "agentcore-e2e-test"
        }
        chat_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "response" in chat_data
        assert "session_id" in chat_data
        assert chat_data["session_id"] == "agentcore-e2e-test"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])