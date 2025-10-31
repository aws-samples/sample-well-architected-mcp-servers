# Local Testing Guide - Authentication Disabled

This guide explains how to run the COA backend with authentication disabled for local testing and development.

## 🚨 Security Warning

**NEVER use authentication disabled mode in production!** This mode is only for local development and testing.

## Environment Variables for Disabling Authentication

The backend supports several ways to disable authentication:

### Method 1: Explicit Disable Flag (Recommended)
```bash
export DISABLE_AUTH=true
```

### Method 2: Environment-based Detection
```bash
export ENVIRONMENT=local
# or
export ENVIRONMENT=development
# or  
export ENVIRONMENT=test
```

### Method 3: Automatic Detection
The system will automatically disable authentication if it detects certain local development patterns.

## Running AgentCore Backend with Authentication Disabled

### Option 1: Environment Variables + uvicorn
```bash
# Navigate to backend directory
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface/backend

# Set environment variables and run
DISABLE_AUTH=true BACKEND_MODE=agentcore PARAM_PREFIX=coacost uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Option 2: Export Variables First
```bash
# Set environment variables
export DISABLE_AUTH=true
export BACKEND_MODE=agentcore
export PARAM_PREFIX=coacost
export AWS_DEFAULT_REGION=us-east-1

# Run the backend
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Option 3: Using Docker with Authentication Disabled
```bash
# Build the image
./deployment/scripts/build-agentcore.sh

# Run with authentication disabled
docker run -p 8001:8000 \
  -e DISABLE_AUTH=true \
  -e BACKEND_MODE=agentcore \
  -e PARAM_PREFIX=coacost \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
  coa-agentcore:latest
```

## Running BedrockAgent Backend with Authentication Disabled

```bash
# For BedrockAgent version
DISABLE_AUTH=true BACKEND_MODE=bedrockagent PARAM_PREFIX=coacost uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Testing the Frontend with Authentication Disabled

### 1. Start the Backend
```bash
DISABLE_AUTH=true BACKEND_MODE=agentcore PARAM_PREFIX=coacost uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Start the Frontend
```bash
# In another terminal
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend
python -m http.server 8080
```

### 3. Access the Test Interface
- Open http://localhost:8080/local-test.html
- The environment should be set to "Local (localhost:8000)"
- If using port 8001, you may need to update the frontend configuration

### 4. Update Frontend Port (if needed)
If you're running the backend on port 8001, you can either:

**Option A: Update the frontend configuration**
Edit `local-test.html` and change:
```javascript
local: 'http://localhost:8000'
```
to:
```javascript
local: 'http://localhost:8001'
```

**Option B: Use the browser console**
Open browser developer tools and run:
```javascript
API_BASE_URL = 'http://localhost:8001';
```

## Verification

### 1. Check Backend Status
```bash
curl http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "agentcore",
  "mode": "full" or "minimal",
  "services": {...},
  "timestamp": "..."
}
```

### 2. Test Chat Endpoint
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, test message", "session_id": "test"}'
```

### 3. Run Automated Test
```bash
# Run the authentication test script
python test_local_auth.py
```

## What Happens When Authentication is Disabled

1. **Mock User Created**: A mock user is automatically created for all requests:
   ```json
   {
     "sub": "local-test-user",
     "email": "test@localhost", 
     "name": "Local Test User",
     "groups": ["local-testing"],
     "auth_disabled": true
   }
   ```

2. **All Endpoints Accessible**: No authentication checks are performed on any endpoints

3. **Warning Logged**: The backend logs a warning message when authentication is disabled

4. **Request State**: All requests have the mock user available in `request.state.user`

## Troubleshooting

### Issue: Still Getting 401 Authentication Required

**Solutions:**
1. Ensure `DISABLE_AUTH=true` is set before starting the backend
2. Restart the backend after setting the environment variable
3. Check the backend logs for the warning message about disabled authentication
4. Verify you're connecting to the correct port

### Issue: Frontend Can't Connect to Backend

**Solutions:**
1. Check that the backend is running on the expected port
2. Verify the frontend is pointing to the correct URL
3. Check for CORS issues in browser developer tools
4. Ensure both frontend and backend are running

### Issue: Chat Endpoint Not Working

**Solutions:**
1. Verify the endpoint URL is `/api/chat` (not `/api/chat/local`)
2. Check the request payload format
3. Look at backend logs for error messages
4. Test with curl first to isolate frontend issues

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DISABLE_AUTH` | Explicitly disable authentication | `true` |
| `ENVIRONMENT` | Environment type (auto-disables auth for local/dev/test) | `local` |
| `BACKEND_MODE` | Backend version to run | `agentcore` or `bedrockagent` |
| `PARAM_PREFIX` | Parameter prefix for AWS SSM | `coacost` |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |

## Security Notes

- 🚨 **Never use `DISABLE_AUTH=true` in production**
- 🔒 Authentication is automatically re-enabled when `DISABLE_AUTH` is not set
- 🛡️ The mock user has limited permissions and is only for testing
- 📝 All authentication bypass attempts are logged
- 🔍 Monitor logs for unauthorized access attempts

## Next Steps

Once authentication is disabled and the backend is running:

1. Test basic chat functionality
2. Test agent selection and routing
3. Test parameter prefix configuration
4. Verify AWS service integration (if credentials are configured)
5. Test graceful degradation scenarios

For production deployment, remove the `DISABLE_AUTH` environment variable and configure proper authentication through AWS Cognito or your chosen authentication provider.