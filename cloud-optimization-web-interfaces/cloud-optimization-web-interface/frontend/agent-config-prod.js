/**
 * Production Configuration Override
 * This file overrides the default configuration for production deployment
 */

// Production-specific configuration
const ProductionConfig = {
    // Production API endpoint - adjust as needed for your deployment
    API_BASE: '/api',  // Relative path for production
    
    // Environment
    ENVIRONMENT: 'production',
    
    // Feature flags for production
    FEATURES: {
        DEBUG_LOGGING: false,
        ORCHESTRATION: true,
        ADVANCED_DIAGNOSTICS: false,
        AUTO_REFRESH_INTERVAL: 30000, // 30 seconds
    },
    
    // Production UI settings
    UI: {
        SHOW_ENVIRONMENT_BADGE: false,
        TITLE_SUFFIX: '',
        THEME: 'default'
    }
};

// Override the default configuration
if (typeof window !== 'undefined') {
    window.AgentConfig = ProductionConfig;
    
    // Minimal logging for production
    window.debugLog = function(message, ...args) {
        // No logging in production
    };
    
    console.log('[AgentConfig] Production configuration loaded');
}