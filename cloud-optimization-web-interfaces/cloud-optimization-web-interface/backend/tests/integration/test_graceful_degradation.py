"""
Integration tests for graceful degradation scenarios.

Tests that both versions can handle service failures gracefully
and fall back to alternative implementations when needed.
"""

import asyncio
import json
import pytest
import requests
import time
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

# Test configuration
BEDROCKAGENT_URL = "http://localhost:8000"
AGENTCORE_URL = "http://localhost:8001"
REQUEST_TIMEOUT = 60


class TestGracefulDegradation:
    """Test graceful degradation scenarios for both versions."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Setup test environment."""
        # Ensure services are running
        self.ensure_services_running()
    
    def ensure_services_running(self):
        """Ensure both services are running."""
        try:
            bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health", timeout=10)
            agentcore_health = requests.get(f"{AGENTCORE_URL}/health", timeout=10)
            
            if bedrockagent_health.status_code != 200:
                pytest.skip("BedrockAgent service not available")
            if agentcore_health.status_code != 200:
                pytest.skip("AgentCore service not available")
        except Exception:
            pytest.skip("Services not available for testing")
    
    def test_bedrockagent_fallback_to_model(self):
        """Test BedrockAgent fallback to direct model when traditional agents fail."""
        # Test chat that should work even if traditional agents are unavailable
        chat_payload = {
            "message": "What are AWS security best practices?",
            "session_id": "bedrockagent-fallback-test"
        }
        
        response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=chat_payload, timeout=REQUEST_TIMEOUT)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have a response regardless of agent availability
        assert "response" in data
        assert "response_type" in data
        assert "session_id" in data
        
        # Response type should indicate what was used
        valid_types = ["traditional_agent", "model_fallback"]
        assert data["response_type"] in valid_types
        
        # If it's a fallback, should still provide useful response
        if data["response_type"] == "model_fallback":
            assert len(data["response"]) > 0
            assert "metadata" in data
    
    def test_agentcore_fallback_to_model(self):
        """Test AgentCore fallback to direct model when Strands agents fail."""
        # Test chat that should work even if Strands agents are unavailable
        chat_payload = {
            "message": "Help me optimize my AWS costs",
            "session_id": "agentcore-fallback-test"
        }
        
        response = requests.post(f"{AGENTCORE_URL}/api/chat", json=chat_payload, timeout=REQUEST_TIMEOUT)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have a response regardless of agent availability
        assert "response" in data
        assert "response_type" in data
        assert "session_id" in data
        
        # Response type should indicate what was used
        valid_types = ["strands_agent", "model_fallback"]
        assert data["response_type"] in valid_types
        
        # If it's a fallback, should still provide useful response
        if data["response_type"] == "model_fallback":
            assert len(data["response"]) > 0
            assert "metadata" in data
    
    def test_minimal_mode_functionality(self):
        """Test that minimal mode provides basic functionality."""
        # Check current mode from health endpoints
        bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health").json()
        agentcore_health = requests.get(f"{AGENTCORE_URL}/health").json()
        
        # Both should report their current mode
        assert "mode" in bedrockagent_health
        assert "mode" in agentcore_health
        
        bedrockagent_mode = bedrockagent_health["mode"]
        agentcore_mode = agentcore_health["mode"]
        
        # Test basic functionality regardless of mode
        test_payload = {
            "message": "Simple test for minimal mode",
            "session_id": "minimal-mode-test"
        }
        
        # BedrockAgent should work in any mode
        bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=test_payload)
        assert bedrockagent_response.status_code == 200
        bedrockagent_data = bedrockagent_response.json()
        assert "response" in bedrockagent_data
        
        # AgentCore should work in any mode
        agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=test_payload)
        assert agentcore_response.status_code == 200
        agentcore_data = agentcore_response.json()
        assert "response" in agentcore_data
        
        # In minimal mode, should use model fallback
        if bedrockagent_mode == "minimal":
            assert bedrockagent_data["response_type"] == "model_fallback"
        
        if agentcore_mode == "minimal":
            assert agentcore_data["response_type"] == "model_fallback"
    
    def test_service_degradation_handling(self):
        """Test handling of service degradation scenarios."""
        # Test health endpoints for degraded services
        bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health").json()
        agentcore_health = requests.get(f"{AGENTCORE_URL}/health").json()
        
        # Check service status
        bedrockagent_services = bedrockagent_health.get("services", {})
        agentcore_services = agentcore_health.get("services", {})
        
        # Core services should be healthy
        core_services = ["config", "auth", "bedrock_model"]
        
        for service in core_services:
            if service in bedrockagent_services:
                assert bedrockagent_services[service] in ["healthy", "degraded"]
            if service in agentcore_services:
                assert agentcore_services[service] in ["healthy", "degraded"]
        
        # Test that chat still works even with some degraded services
        test_payload = {
            "message": "Test with potentially degraded services",
            "session_id": "degradation-test"
        }
        
        bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=test_payload)
        agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=test_payload)
        
        # Should still get responses even with degraded services
        assert bedrockagent_response.status_code == 200
        assert agentcore_response.status_code == 200
    
    def test_parameter_store_fallback(self):
        """Test fallback when Parameter Store is unavailable."""
        # Test parameter manager configuration
        bedrockagent_params = requests.get(f"{BEDROCKAGENT_URL}/api/parameter-manager/config")
        agentcore_params = requests.get(f"{AGENTCORE_URL}/api/parameter-manager/config")
        
        # Services should handle parameter store unavailability gracefully
        # Status could be 200 (working) or 503 (unavailable but handled)
        assert bedrockagent_params.status_code in [200, 503]
        assert agentcore_params.status_code in [200, 503]
        
        # Even if parameter store is unavailable, basic chat should work
        test_payload = {
            "message": "Test without parameter store",
            "session_id": "param-fallback-test"
        }
        
        bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=test_payload)
        agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=test_payload)
        
        assert bedrockagent_response.status_code == 200
        assert agentcore_response.status_code == 200
    
    def test_aws_connectivity_fallback(self):
        """Test behavior when AWS connectivity is limited."""
        # This test checks that services handle AWS connectivity issues gracefully
        
        # Test version endpoints (should work without AWS)
        bedrockagent_version = requests.get(f"{BEDROCKAGENT_URL}/api/version")
        agentcore_version = requests.get(f"{AGENTCORE_URL}/api/version")
        
        assert bedrockagent_version.status_code == 200
        assert agentcore_version.status_code == 200
        
        # Test health endpoints (should report AWS connectivity status)
        bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health").json()
        agentcore_health = requests.get(f"{AGENTCORE_URL}/health").json()
        
        # Health should report overall status even with AWS issues
        assert bedrockagent_health["status"] in ["healthy", "degraded", "unhealthy"]
        assert agentcore_health["status"] in ["healthy", "degraded", "unhealthy"]
    
    def test_concurrent_degradation_scenarios(self):
        """Test multiple degradation scenarios happening concurrently."""
        import concurrent.futures
        
        def test_chat_under_load(url: str, session_id: str) -> Dict[str, Any]:
            """Test chat functionality under potential load/degradation."""
            payload = {
                "message": f"Concurrent test message for {session_id}",
                "session_id": session_id
            }
            
            try:
                response = requests.post(f"{url}/api/chat", json=payload, timeout=30)
                return {
                    "success": response.status_code == 200,
                    "data": response.json() if response.status_code == 200 else None,
                    "status_code": response.status_code
                }
            except Exception as e:
                return {
                    "success": False,
                    "data": None,
                    "error": str(e)
                }
        
        # Run concurrent requests to both versions
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            
            # Submit multiple requests to each version
            for i in range(3):
                futures.append(executor.submit(
                    test_chat_under_load, 
                    BEDROCKAGENT_URL, 
                    f"concurrent-bedrockagent-{i}"
                ))
                futures.append(executor.submit(
                    test_chat_under_load, 
                    AGENTCORE_URL, 
                    f"concurrent-agentcore-{i}"
                ))
            
            # Collect results
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Most requests should succeed even under load
        successful_results = [r for r in results if r["success"]]
        total_requests = len(results)
        success_rate = len(successful_results) / total_requests
        
        # Expect at least 70% success rate under degradation scenarios
        assert success_rate >= 0.7, f"Success rate too low: {success_rate:.2%} ({len(successful_results)}/{total_requests})"
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Test invalid requests to ensure proper error handling
        invalid_payloads = [
            {},  # Empty payload
            {"message": ""},  # Empty message
            {"message": "test"},  # Missing session_id
            {"session_id": "test"},  # Missing message
            {"message": "test", "session_id": ""},  # Empty session_id
        ]
        
        for payload in invalid_payloads:
            # Test BedrockAgent error handling
            bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=payload)
            # Should handle gracefully (either 400 for validation or 200 with defaults)
            assert bedrockagent_response.status_code in [200, 400, 422]
            
            # Test AgentCore error handling
            agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=payload)
            # Should handle gracefully (either 400 for validation or 200 with defaults)
            assert agentcore_response.status_code in [200, 400, 422]
        
        # Test recovery with valid request after invalid ones
        valid_payload = {
            "message": "Recovery test after errors",
            "session_id": "recovery-test"
        }
        
        bedrockagent_recovery = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=valid_payload)
        agentcore_recovery = requests.post(f"{AGENTCORE_URL}/api/chat", json=valid_payload)
        
        # Should recover and work normally
        assert bedrockagent_recovery.status_code == 200
        assert agentcore_recovery.status_code == 200
    
    def test_resource_exhaustion_handling(self):
        """Test handling of resource exhaustion scenarios."""
        # Test with very long messages to simulate resource pressure
        long_message = "This is a very long message. " * 100  # ~2800 characters
        
        payload = {
            "message": long_message,
            "session_id": "resource-test"
        }
        
        # Both versions should handle long messages gracefully
        bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=payload, timeout=REQUEST_TIMEOUT)
        agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=payload, timeout=REQUEST_TIMEOUT)
        
        # Should either process successfully or return appropriate error
        assert bedrockagent_response.status_code in [200, 400, 413, 500]
        assert agentcore_response.status_code in [200, 400, 413, 500]
        
        # If successful, should have valid response structure
        if bedrockagent_response.status_code == 200:
            bedrockagent_data = bedrockagent_response.json()
            assert "response" in bedrockagent_data
            assert "session_id" in bedrockagent_data
        
        if agentcore_response.status_code == 200:
            agentcore_data = agentcore_response.json()
            assert "response" in agentcore_data
            assert "session_id" in agentcore_data


class TestModeTransitions:
    """Test mode transitions and configuration changes."""
    
    def test_mode_detection(self):
        """Test that services correctly detect and report their mode."""
        # Get current mode from health endpoints
        bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health").json()
        agentcore_health = requests.get(f"{AGENTCORE_URL}/health").json()
        
        # Both should report a valid mode
        assert "mode" in bedrockagent_health
        assert "mode" in agentcore_health
        
        bedrockagent_mode = bedrockagent_health["mode"]
        agentcore_mode = agentcore_health["mode"]
        
        # Modes should be valid
        valid_modes = ["full", "minimal", "emergency"]
        assert bedrockagent_mode in valid_modes
        assert agentcore_mode in valid_modes
        
        # Service status should be consistent with mode
        bedrockagent_status = bedrockagent_health["status"]
        agentcore_status = agentcore_health["status"]
        
        # Emergency mode should have unhealthy status
        if bedrockagent_mode == "emergency":
            assert bedrockagent_status in ["unhealthy", "emergency"]
        if agentcore_mode == "emergency":
            assert agentcore_status in ["unhealthy", "emergency"]
    
    def test_feature_availability_by_mode(self):
        """Test that features are available based on the current mode."""
        # Get mode and version info
        bedrockagent_health = requests.get(f"{BEDROCKAGENT_URL}/health").json()
        agentcore_health = requests.get(f"{AGENTCORE_URL}/health").json()
        
        bedrockagent_version = requests.get(f"{BEDROCKAGENT_URL}/api/version").json()
        agentcore_version = requests.get(f"{AGENTCORE_URL}/api/version").json()
        
        # Check feature availability based on mode
        bedrockagent_mode = bedrockagent_health.get("mode", "unknown")
        agentcore_mode = agentcore_health.get("mode", "unknown")
        
        # In full mode, version-specific features should be available
        if bedrockagent_mode == "full":
            # BedrockAgent should have traditional agent features
            bedrockagent_agents = requests.get(f"{BEDROCKAGENT_URL}/api/agents/traditional")
            assert bedrockagent_agents.status_code in [200, 503]  # Available or temporarily unavailable
        
        if agentcore_mode == "full":
            # AgentCore should have Strands agent features
            agentcore_agents = requests.get(f"{AGENTCORE_URL}/api/agents/strands")
            assert agentcore_agents.status_code in [200, 503]  # Available or temporarily unavailable
        
        # In minimal mode, basic chat should still work
        if bedrockagent_mode == "minimal":
            test_payload = {"message": "minimal mode test", "session_id": "minimal-test"}
            response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=test_payload)
            assert response.status_code == 200
            assert response.json()["response_type"] == "model_fallback"
        
        if agentcore_mode == "minimal":
            test_payload = {"message": "minimal mode test", "session_id": "minimal-test"}
            response = requests.post(f"{AGENTCORE_URL}/api/chat", json=test_payload)
            assert response.status_code == 200
            assert response.json()["response_type"] == "model_fallback"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])