# Design Document

## Overview

The local backend authentication fix addresses the HTTP 401 errors that occur when developers try to test the Cloud Optimization Assistant locally. The current system enforces full Cognito authentication even in local development environments, which creates friction for developers who need to quickly test functionality.

The solution implements a dual-mode authentication system that can operate in either production mode (full Cognito authentication) or development mode (simplified/bypassed authentication) based on environment detection.

## Architecture

### Current Authentication Flow
```
Frontend Request → HTTPBearer Security → AuthService.verify_token() → Cognito JWT Validation → 401 if invalid
```

### Proposed Authentication Flow
```
Frontend Request → Environment Detection → [Production: Full Auth] OR [Development: Simplified Auth] → Continue Processing
```

### Environment Detection Logic
The system will detect the environment using multiple indicators:
1. **Environment Variables**: `ENVIRONMENT`, `DEBUG`, `LOCAL_DEVELOPMENT`
2. **Configuration Files**: Presence of `.env` file with local settings
3. **Network Context**: Localhost/127.0.0.1 origins
4. **AWS Context**: Local AWS profile vs production IAM roles

## Components and Interfaces

### 1. Enhanced AuthService

**Current Interface:**
```python
class AuthService:
    async def verify_token(self, token: str) -> Dict[str, Any]
```

**Enhanced Interface:**
```python
class AuthService:
    def __init__(self, environment_mode: str = "auto")
    async def verify_token(self, token: str) -> Dict[str, Any]
    def is_development_mode(self) -> bool
    def create_mock_user(self, session_id: str = None) -> Dict[str, Any]
    def bypass_authentication(self) -> bool
```

### 2. Environment Detection Service

**New Component:**
```python
class EnvironmentDetector:
    def detect_environment(self) -> EnvironmentMode
    def is_local_development(self) -> bool
    def get_environment_indicators(self) -> Dict[str, Any]
    def should_bypass_auth(self) -> bool
```

**Environment Modes:**
```python
class EnvironmentMode(Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    LOCAL = "local"
    TEST = "test"
```

### 3. Authentication Middleware

**Enhanced Middleware:**
```python
class AuthenticationMiddleware:
    def __init__(self, auth_service: AuthService, environment_detector: EnvironmentDetector)
    async def __call__(self, request: Request, call_next)
    def should_skip_auth(self, request: Request) -> bool
    def create_development_context(self, request: Request) -> Dict[str, Any]
```

### 4. Session Management for Local Development

**Enhanced Session Manager:**
```python
class LocalSessionManager:
    def create_mock_session(self, session_id: str) -> ChatSession
    def get_or_create_local_user(self, session_id: str) -> Dict[str, Any]
    def maintain_local_session_state(self, session_id: str) -> bool
```

## Data Models

### Environment Configuration
```python
@dataclass
class EnvironmentConfig:
    mode: EnvironmentMode
    bypass_auth: bool
    mock_user_enabled: bool
    debug_logging: bool
    cors_origins: List[str]
    jwt_validation: bool
    
    @classmethod
    def from_environment(cls) -> 'EnvironmentConfig'
```

### Mock User Model
```python
@dataclass
class MockUser:
    user_id: str
    username: str
    email: str
    roles: List[str]
    session_id: str
    created_at: datetime
    
    def to_auth_dict(self) -> Dict[str, Any]
```

### Authentication Context
```python
@dataclass
class AuthContext:
    user: Optional[Dict[str, Any]]
    is_authenticated: bool
    auth_method: str  # "cognito", "mock", "bypass"
    session_id: str
    environment_mode: EnvironmentMode
```

## Error Handling

### Authentication Error Hierarchy
```python
class AuthenticationError(Exception):
    pass

class TokenValidationError(AuthenticationError):
    pass

class EnvironmentConfigurationError(AuthenticationError):
    pass

class LocalDevelopmentError(AuthenticationError):
    pass
```

### Error Response Strategy
1. **Production Mode**: Return standard 401 responses with minimal information
2. **Development Mode**: Return detailed error information with troubleshooting hints
3. **Local Mode**: Log errors but allow requests to proceed with mock authentication

### Graceful Degradation
- If Cognito is unavailable in production → Return 503 Service Unavailable
- If environment detection fails → Default to production mode (secure by default)
- If mock user creation fails → Use anonymous user with limited permissions

## Testing Strategy

### Unit Tests
1. **Environment Detection Tests**
   - Test various environment variable combinations
   - Test configuration file detection
   - Test network context detection

2. **Authentication Service Tests**
   - Test production mode JWT validation
   - Test development mode bypass
   - Test mock user creation
   - Test rate limiting in both modes

3. **Middleware Tests**
   - Test request routing based on environment
   - Test header handling in different modes
   - Test CORS configuration

### Integration Tests
1. **End-to-End Authentication Flow**
   - Test complete request flow in production mode
   - Test complete request flow in development mode
   - Test mode switching

2. **WebSocket Authentication**
   - Test WebSocket connections in both modes
   - Test session persistence
   - Test connection management

### Local Development Tests
1. **Quick Start Tests**
   - Test that developers can start backend without configuration
   - Test that frontend connects successfully
   - Test that chat functionality works immediately

2. **Configuration Tests**
   - Test various local development configurations
   - Test environment variable overrides
   - Test .env file loading

## Implementation Details

### Environment Detection Logic
```python
def detect_environment(self) -> EnvironmentMode:
    # Check explicit environment variable
    if os.getenv("ENVIRONMENT") == "production":
        return EnvironmentMode.PRODUCTION
    
    # Check for development indicators
    development_indicators = [
        os.getenv("DEBUG") == "true",
        os.getenv("LOCAL_DEVELOPMENT") == "true",
        os.path.exists(".env"),
        os.getenv("AWS_PROFILE") in ["default", "dev", "local"],
        self._is_localhost_context()
    ]
    
    if any(development_indicators):
        return EnvironmentMode.DEVELOPMENT
    
    # Default to production for security
    return EnvironmentMode.PRODUCTION
```

### Authentication Bypass Logic
```python
async def verify_token_with_environment_awareness(self, token: str, request: Request) -> Dict[str, Any]:
    environment_mode = self.environment_detector.detect_environment()
    
    if environment_mode == EnvironmentMode.DEVELOPMENT:
        if self.should_bypass_auth(request):
            return self.create_mock_user(self._extract_session_id(request))
    
    # Fall back to standard JWT validation
    return await self.verify_token(token)
```

### Mock User Creation
```python
def create_mock_user(self, session_id: str = None) -> Dict[str, Any]:
    session_id = session_id or str(uuid.uuid4())
    
    return {
        "user_id": f"dev_user_{session_id[:8]}",
        "username": "developer",
        "email": "developer@localhost",
        "roles": ["user", "developer"],
        "session_id": session_id,
        "auth_method": "mock",
        "created_at": datetime.utcnow().isoformat()
    }
```

### Configuration Management
The system will support multiple configuration methods:

1. **Environment Variables**
   ```bash
   ENVIRONMENT=development
   DEBUG=true
   LOCAL_DEVELOPMENT=true
   BYPASS_AUTH=true
   ```

2. **Configuration File** (`.env`)
   ```
   ENVIRONMENT=development
   DEBUG=true
   CORS_ORIGINS=http://localhost:3000,http://localhost:8080
   MOCK_USER_ENABLED=true
   ```

3. **Runtime Detection**
   - Automatic detection based on network context
   - AWS profile detection
   - File system indicators

### Logging and Debugging
- **Development Mode**: Verbose logging with authentication decisions
- **Production Mode**: Minimal security-focused logging
- **Debug Mode**: Detailed request/response logging with sensitive data masked

### Security Considerations
1. **Secure by Default**: Unknown environments default to production mode
2. **Clear Mode Indication**: Logs clearly indicate which authentication mode is active
3. **No Production Bypass**: Production environments cannot accidentally enable bypass mode
4. **Rate Limiting**: Both modes implement appropriate rate limiting
5. **Session Security**: Mock sessions have limited lifetime and scope