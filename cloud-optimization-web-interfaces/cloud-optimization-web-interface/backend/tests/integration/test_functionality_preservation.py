"""
Integration tests to validate that all current functionality is preserved
in the new architecture.

Tests that the refactored versions maintain all existing capabilities
and API compatibility.
"""

import asyncio
import json
import pytest
import requests
import time
from typing import Dict, Any, List, Optional

# Test configuration
BEDROCKAGENT_URL = "http://localhost:8000"
AGENTCORE_URL = "http://localhost:8001"
REQUEST_TIMEOUT = 60


class TestAPICompatibility:
    """Test that all existing APIs are preserved and compatible."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Setup test environment."""
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
    
    def test_health_endpoint_compatibility(self):
        """Test that health endpoints maintain expected format."""
        # Test BedrockAgent health endpoint
        bedrockagent_response = requests.get(f"{BEDROCKAGENT_URL}/health")
        assert bedrockagent_response.status_code == 200
        
        bedrockagent_health = bedrockagent_response.json()
        
        # Required fields for health endpoint
        required_fields = ["status", "version", "services", "timestamp"]
        for field in required_fields:
            assert field in bedrockagent_health, f"Missing required field: {field}"
        
        # Status should be valid
        assert bedrockagent_health["status"] in ["healthy", "degraded", "unhealthy", "emergency"]
        
        # Version should indicate backend type
        assert bedrockagent_health["version"] == "bedrockagent"
        
        # Services should be a dictionary
        assert isinstance(bedrockagent_health["services"], dict)
        
        # Test AgentCore health endpoint
        agentcore_response = requests.get(f"{AGENTCORE_URL}/health")
        assert agentcore_response.status_code == 200
        
        agentcore_health = agentcore_response.json()
        
        # Same requirements for AgentCore
        for field in required_fields:
            assert field in agentcore_health, f"Missing required field: {field}"
        
        assert agentcore_health["status"] in ["healthy", "degraded", "unhealthy", "emergency"]
        assert agentcore_health["version"] == "agentcore"
        assert isinstance(agentcore_health["services"], dict)
    
    def test_version_endpoint_compatibility(self):
        """Test that version endpoints maintain expected format."""
        # Test BedrockAgent version endpoint
        bedrockagent_response = requests.get(f"{BEDROCKAGENT_URL}/api/version")
        assert bedrockagent_response.status_code == 200
        
        bedrockagent_version = bedrockagent_response.json()
        
        # Required fields for version endpoint
        required_fields = ["backend_version", "version_info", "timestamp"]
        for field in required_fields:
            assert field in bedrockagent_version, f"Missing required field: {field}"
        
        assert bedrockagent_version["backend_version"] == "bedrockagent"
        
        # Test AgentCore version endpoint
        agentcore_response = requests.get(f"{AGENTCORE_URL}/api/version")
        assert agentcore_response.status_code == 200
        
        agentcore_version = agentcore_response.json()
        
        for field in required_fields:
            assert field in agentcore_version, f"Missing required field: {field}"
        
        assert agentcore_version["backend_version"] == "agentcore"
    
    def test_chat_endpoint_compatibility(self):
        """Test that chat endpoints maintain expected format and functionality."""
        # Test payload format
        test_payload = {
            "message": "Test message for API compatibility",
            "session_id": "compatibility-test"
        }
        
        # Test BedrockAgent chat endpoint
        bedrockagent_response = requests.post(
            f"{BEDROCKAGENT_URL}/api/chat", 
            json=test_payload, 
            timeout=REQUEST_TIMEOUT
        )
        assert bedrockagent_response.status_code == 200
        
        bedrockagent_data = bedrockagent_response.json()
        
        # Required fields for chat response
        required_fields = ["response", "session_id", "response_type", "timestamp"]
        for field in required_fields:
            assert field in bedrockagent_data, f"Missing required field: {field}"
        
        # Validate field types and values
        assert isinstance(bedrockagent_data["response"], str)
        assert len(bedrockagent_data["response"]) > 0
        assert bedrockagent_data["session_id"] == "compatibility-test"
        assert bedrockagent_data["response_type"] in ["traditional_agent", "model_fallback"]
        
        # Test AgentCore chat endpoint
        agentcore_response = requests.post(
            f"{AGENTCORE_URL}/api/chat", 
            json=test_payload, 
            timeout=REQUEST_TIMEOUT
        )
        assert agentcore_response.status_code == 200
        
        agentcore_data = agentcore_response.json()
        
        # Same requirements for AgentCore
        for field in required_fields:
            assert field in agentcore_data, f"Missing required field: {field}"
        
        assert isinstance(agentcore_data["response"], str)
        assert len(agentcore_data["response"]) > 0
        assert agentcore_data["session_id"] == "compatibility-test"
        assert agentcore_data["response_type"] in ["strands_agent", "model_fallback"]
    
    def test_parameter_manager_endpoint_compatibility(self):
        """Test parameter manager endpoint compatibility."""
        # Test BedrockAgent parameter manager
        bedrockagent_response = requests.get(f"{BEDROCKAGENT_URL}/api/parameter-manager/config")
        # Should respond with either success or service unavailable
        assert bedrockagent_response.status_code in [200, 503]
        
        if bedrockagent_response.status_code == 200:
            bedrockagent_config = bedrockagent_response.json()
            # Should have parameter prefix information
            assert "parameter_prefix" in bedrockagent_config
            assert "timestamp" in bedrockagent_config
        
        # Test AgentCore parameter manager
        agentcore_response = requests.get(f"{AGENTCORE_URL}/api/parameter-manager/config")
        assert agentcore_response.status_code in [200, 503]
        
        if agentcore_response.status_code == 200:
            agentcore_config = agentcore_response.json()
            assert "parameter_prefix" in agentcore_config
            assert "timestamp" in agentcore_config
    
    def test_agent_endpoints_compatibility(self):
        """Test agent-specific endpoints maintain compatibility."""
        # Test BedrockAgent traditional agents endpoint
        bedrockagent_agents_response = requests.get(f"{BEDROCKAGENT_URL}/api/agents/traditional")
        # Should respond appropriately (200 with data or 503 if unavailable)
        assert bedrockagent_agents_response.status_code in [200, 503]
        
        if bedrockagent_agents_response.status_code == 200:
            bedrockagent_agents = bedrockagent_agents_response.json()
            # Should have agents list and count
            assert "agents" in bedrockagent_agents
            assert "count" in bedrockagent_agents
            assert "timestamp" in bedrockagent_agents
            assert isinstance(bedrockagent_agents["agents"], list)
            assert isinstance(bedrockagent_agents["count"], int)
        
        # Test AgentCore Strands agents endpoint
        agentcore_agents_response = requests.get(f"{AGENTCORE_URL}/api/agents/strands")
        assert agentcore_agents_response.status_code in [200, 503]
        
        if agentcore_agents_response.status_code == 200:
            agentcore_agents = agentcore_agents_response.json()
            assert "agents" in agentcore_agents
            assert "count" in agentcore_agents
            assert "timestamp" in agentcore_agents
            assert isinstance(agentcore_agents["agents"], list)
            assert isinstance(agentcore_agents["count"], int)


class TestFunctionalityPreservation:
    """Test that all existing functionality is preserved."""
    
    def test_chat_functionality_preservation(self):
        """Test that chat functionality works as expected."""
        # Test various types of messages that should work
        test_cases = [
            {
                "message": "What are AWS security best practices?",
                "expected_keywords": ["security", "aws", "best", "practice"]
            },
            {
                "message": "Help me optimize my AWS costs",
                "expected_keywords": ["cost", "optimize", "aws"]
            },
            {
                "message": "How do I configure VPC security groups?",
                "expected_keywords": ["vpc", "security", "group"]
            },
            {
                "message": "What is the Well-Architected Framework?",
                "expected_keywords": ["well", "architected", "framework"]
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            session_id = f"functionality-test-{i}"
            payload = {
                "message": test_case["message"],
                "session_id": session_id
            }
            
            # Test BedrockAgent
            bedrockagent_response = requests.post(
                f"{BEDROCKAGENT_URL}/api/chat", 
                json=payload, 
                timeout=REQUEST_TIMEOUT
            )
            assert bedrockagent_response.status_code == 200
            
            bedrockagent_data = bedrockagent_response.json()
            assert "response" in bedrockagent_data
            assert len(bedrockagent_data["response"]) > 0
            
            # Test AgentCore
            agentcore_response = requests.post(
                f"{AGENTCORE_URL}/api/chat", 
                json=payload, 
                timeout=REQUEST_TIMEOUT
            )
            assert agentcore_response.status_code == 200
            
            agentcore_data = agentcore_response.json()
            assert "response" in agentcore_data
            assert len(agentcore_data["response"]) > 0
            
            # Both should provide meaningful responses
            # (We can't easily test content quality, but we can test structure)
            assert bedrockagent_data["session_id"] == session_id
            assert agentcore_data["session_id"] == session_id
    
    def test_session_management_preservation(self):
        """Test that session management functionality is preserved."""
        session_id = "session-management-test"
        
        # Send multiple messages in the same session
        messages = [
            "Hello, I need help with AWS security",
            "Can you tell me about IAM best practices?",
            "What about VPC security?"
        ]
        
        bedrockagent_responses = []
        agentcore_responses = []
        
        for i, message in enumerate(messages):
            payload = {
                "message": message,
                "session_id": session_id
            }
            
            # Test BedrockAgent session continuity
            bedrockagent_response = requests.post(
                f"{BEDROCKAGENT_URL}/api/chat", 
                json=payload, 
                timeout=REQUEST_TIMEOUT
            )
            assert bedrockagent_response.status_code == 200
            bedrockagent_data = bedrockagent_response.json()
            bedrockagent_responses.append(bedrockagent_data)
            
            # Test AgentCore session continuity
            agentcore_response = requests.post(
                f"{AGENTCORE_URL}/api/chat", 
                json=payload, 
                timeout=REQUEST_TIMEOUT
            )
            assert agentcore_response.status_code == 200
            agentcore_data = agentcore_response.json()
            agentcore_responses.append(agentcore_data)
            
            # Small delay between messages
            time.sleep(1)
        
        # All responses should have the same session_id
        for response in bedrockagent_responses:
            assert response["session_id"] == session_id
        
        for response in agentcore_responses:
            assert response["session_id"] == session_id
        
        # All responses should have valid content
        for response in bedrockagent_responses + agentcore_responses:
            assert "response" in response
            assert len(response["response"]) > 0
            assert "timestamp" in response
    
    def test_error_handling_preservation(self):
        """Test that error handling functionality is preserved."""
        # Test various error scenarios
        error_test_cases = [
            {
                "payload": {},
                "description": "Empty payload"
            },
            {
                "payload": {"message": ""},
                "description": "Empty message"
            },
            {
                "payload": {"session_id": "test"},
                "description": "Missing message"
            },
            {
                "payload": {"message": "test"},
                "description": "Missing session_id"
            }
        ]
        
        for test_case in error_test_cases:
            payload = test_case["payload"]
            description = test_case["description"]
            
            # Test BedrockAgent error handling
            bedrockagent_response = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=payload)
            # Should handle gracefully (either validation error or default handling)
            assert bedrockagent_response.status_code in [200, 400, 422], f"BedrockAgent failed for: {description}"
            
            # Test AgentCore error handling
            agentcore_response = requests.post(f"{AGENTCORE_URL}/api/chat", json=payload)
            assert agentcore_response.status_code in [200, 400, 422], f"AgentCore failed for: {description}"
        
        # Test recovery after errors
        valid_payload = {
            "message": "Recovery test after errors",
            "session_id": "error-recovery-test"
        }
        
        bedrockagent_recovery = requests.post(f"{BEDROCKAGENT_URL}/api/chat", json=valid_payload)
        agentcore_recovery = requests.post(f"{AGENTCORE_URL}/api/chat", json=valid_payload)
        
        # Should recover and work normally
        assert bedrockagent_recovery.status_code == 200
        assert agentcore_recovery.status_code == 200
    
    def test_concurrent_request_handling_preservation(self):
        """Test that concurrent request handling is preserved."""
        import concurrent.futures
        
        def make_chat_request(url: str, message: str, session_id: str) -> Dict[str, Any]:
            """Make a chat request."""
            payload = {
                "message": message,
                "session_id": session_id
            }
            
            try:
                response = requests.post(f"{url}/api/chat", json=payload, timeout=REQUEST_TIMEOUT)
                return {
                    "success": response.status_code == 200,
                    "data": response.json() if response.status_code == 200 else None,
                    "status_code": response.status_code
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "status_code": 0
                }
        
        # Prepare concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            
            # Submit requests to both versions
            for i in range(4):
                # BedrockAgent requests
                futures.append(executor.submit(
                    make_chat_request,
                    BEDROCKAGENT_URL,
                    f"Concurrent BedrockAgent test {i}",
                    f"concurrent-bedrockagent-{i}"
                ))
                
                # AgentCore requests
                futures.append(executor.submit(
                    make_chat_request,
                    AGENTCORE_URL,
                    f"Concurrent AgentCore test {i}",
                    f"concurrent-agentcore-{i}"
                ))
            
            # Collect results
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Analyze results
        successful_results = [r for r in results if r["success"]]
        total_requests = len(results)
        success_rate = len(successful_results) / total_requests
        
        # Should handle concurrent requests well
        assert success_rate >= 0.8, f"Concurrent request success rate too low: {success_rate:.2%}"
        
        # All successful responses should have valid structure
        for result in successful_results:
            data = result["data"]
            assert "response" in data
            assert "session_id" in data
            assert "response_type" in data
            assert "timestamp" in data


class TestBackwardCompatibility:
    """Test backward compatibility with existing clients."""
    
    def test_legacy_endpoint_compatibility(self):
        """Test that legacy endpoints still work or provide appropriate redirects."""
        # Test root endpoint
        bedrockagent_root = requests.get(f"{BEDROCKAGENT_URL}/")
        agentcore_root = requests.get(f"{AGENTCORE_URL}/")
        
        # Should respond appropriately (either content or redirect)
        assert bedrockagent_root.status_code in [200, 301, 302, 404]
        assert agentcore_root.status_code in [200, 301, 302, 404]
    
    def test_api_response_format_compatibility(self):
        """Test that API response formats are compatible with existing clients."""
        # Test that all API responses are valid JSON
        endpoints_to_test = [
            "/health",
            "/api/version",
            "/api/parameter-manager/config"
        ]
        
        for endpoint in endpoints_to_test:
            # Test BedrockAgent
            bedrockagent_response = requests.get(f"{BEDROCKAGENT_URL}{endpoint}")
            if bedrockagent_response.status_code == 200:
                # Should be valid JSON
                try:
                    bedrockagent_data = bedrockagent_response.json()
                    assert isinstance(bedrockagent_data, dict)
                except json.JSONDecodeError:
                    pytest.fail(f"BedrockAgent {endpoint} returned invalid JSON")
            
            # Test AgentCore
            agentcore_response = requests.get(f"{AGENTCORE_URL}{endpoint}")
            if agentcore_response.status_code == 200:
                # Should be valid JSON
                try:
                    agentcore_data = agentcore_response.json()
                    assert isinstance(agentcore_data, dict)
                except json.JSONDecodeError:
                    pytest.fail(f"AgentCore {endpoint} returned invalid JSON")
    
    def test_content_type_compatibility(self):
        """Test that content types are handled correctly."""
        # Test JSON content type for chat endpoint
        payload = {
            "message": "Content type test",
            "session_id": "content-type-test"
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Test BedrockAgent
        bedrockagent_response = requests.post(
            f"{BEDROCKAGENT_URL}/api/chat",
            json=payload,
            headers=headers
        )
        assert bedrockagent_response.status_code == 200
        assert bedrockagent_response.headers.get("content-type", "").startswith("application/json")
        
        # Test AgentCore
        agentcore_response = requests.post(
            f"{AGENTCORE_URL}/api/chat",
            json=payload,
            headers=headers
        )
        assert agentcore_response.status_code == 200
        assert agentcore_response.headers.get("content-type", "").startswith("application/json")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])