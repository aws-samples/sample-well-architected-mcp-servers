#!/usr/bin/env python3
"""
Test script to verify that authentication can be disabled for local testing.
"""

import os
import sys
import requests
import time

def test_auth_disabled():
    """Test that authentication is disabled when DISABLE_AUTH=true"""
    
    # Test configuration
    base_url = "http://localhost:8001"  # AgentCore port
    
    print("🧪 Testing Authentication Disable Functionality")
    print(f"Backend URL: {base_url}")
    print(f"DISABLE_AUTH environment variable: {os.getenv('DISABLE_AUTH', 'not set')}")
    
    # Test endpoints that would normally require authentication
    test_endpoints = [
        "/health",
        "/api/version", 
        "/api/config/status",
        "/api/chat"
    ]
    
    print("\n📋 Testing endpoints...")
    
    for endpoint in test_endpoints:
        url = f"{base_url}{endpoint}"
        
        try:
            if endpoint == "/api/chat":
                # POST request for chat endpoint
                response = requests.post(url, json={
                    "message": "Hello, this is a test message",
                    "session_id": "test-session"
                }, timeout=10)
            else:
                # GET request for other endpoints
                response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {endpoint}: SUCCESS (200)")
                
                # For chat endpoint, check if we got a response
                if endpoint == "/api/chat":
                    try:
                        data = response.json()
                        if "response" in data:
                            print(f"   💬 Chat response received: {data['response'][:50]}...")
                        else:
                            print(f"   ⚠️  Chat response format: {list(data.keys())}")
                    except:
                        print(f"   ⚠️  Non-JSON response from chat")
                        
            elif response.status_code == 401:
                print(f"❌ {endpoint}: AUTHENTICATION REQUIRED (401)")
                print(f"   🔒 Authentication is still enabled!")
                return False
            else:
                print(f"⚠️  {endpoint}: {response.status_code} - {response.text[:100]}")
                
        except requests.exceptions.ConnectionError:
            print(f"🔌 {endpoint}: CONNECTION FAILED - Is the backend running?")
            return False
        except requests.exceptions.Timeout:
            print(f"⏰ {endpoint}: TIMEOUT")
        except Exception as e:
            print(f"💥 {endpoint}: ERROR - {e}")
    
    print("\n✅ Authentication disable test completed!")
    print("\n💡 If you see 401 errors above, make sure to:")
    print("   1. Set DISABLE_AUTH=true environment variable")
    print("   2. Restart the backend server")
    print("   3. Check that the backend is running in local/development mode")
    
    return True

def main():
    """Main test function"""
    print("🚀 COA Backend Authentication Disable Test")
    print("=" * 50)
    
    # Check if backend is running
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"⚠️  Backend responded with status: {response.status_code}")
    except:
        print("❌ Backend is not running on localhost:8001")
        print("\n💡 To start the backend with authentication disabled:")
        print("   DISABLE_AUTH=true BACKEND_MODE=agentcore PARAM_PREFIX=coacost uvicorn main:app --host 0.0.0.0 --port 8001 --reload")
        return 1
    
    # Run the test
    success = test_auth_disabled()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())