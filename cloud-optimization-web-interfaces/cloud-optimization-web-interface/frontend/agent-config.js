/**
 * Agent Management Configuration
 * This file contains environment-specific configuration for the agent management interface
 */

// Environment detection
const isLocalDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const isProduction = window.location.hostname.includes('amazonaws.com') || window.location.hostname.includes('cloudfront.net');

// Configuration based on environment
const AgentConfig = {
    // API Base URL Configuration
    API_BASE: (() => {
        if (isLocalDevelopment) {
            // Local development - backend running on localhost:8000
            return 'http://localhost:8000/api';
        } else if (isProduction) {
            // Production - use relative path to current domain
            return '/api';
        } else {
            // Default fallback - assume production setup
            return '/api';
        }
    })(),
    
    // Environment info
    ENVIRONMENT: (() => {
        if (isLocalDevelopment) return 'development';
        if (isProduction) return 'production';
        return 'unknown';
    })(),
    
    // Feature flags
    FEATURES: {
        // Enable debug logging in development
        DEBUG_LOGGING: isLocalDevelopment,
        
        // Enable orchestration features (always on)
        ORCHESTRATION: true,
        
        // Enable advanced diagnostics in development
        ADVANCED_DIAGNOSTICS: isLocalDevelopment,
        
        // Auto-refresh intervals (ms)
        AUTO_REFRESH_INTERVAL: isLocalDevelopment ? 10000 : 30000, // 10s dev, 30s prod
    },
    
    // UI Configuration
    UI: {
        // Show environment indicator
        SHOW_ENVIRONMENT_BADGE: isLocalDevelopment,
        
        // Page title suffix
        TITLE_SUFFIX: isLocalDevelopment ? ' (Local Dev)' : '',
        
        // Theme
        THEME: 'default'
    }
};

// Debug logging function
function debugLog(message, ...args) {
    if (AgentConfig.FEATURES.DEBUG_LOGGING) {
        console.log(`[AgentConfig] ${message}`, ...args);
    }
}

// Log current configuration
debugLog('Configuration loaded:', {
    environment: AgentConfig.ENVIRONMENT,
    apiBase: AgentConfig.API_BASE,
    hostname: window.location.hostname
});

// Export for use in other scripts
window.AgentConfig = AgentConfig;
window.debugLog = debugLog;