/**
 * Template Discovery Service
 * Handles automatic discovery and loading of prompt templates from the file system
 */
class TemplateDiscoveryService {
    constructor() {
        this.templateCache = new Map();
        this.structureCache = null;
        this.lastCacheUpdate = null;
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
        this.baseUrl = './prompt-templates/';
        this.localStorageKey = 'coa_template_cache';
        this.maxCacheSize = 50; // Maximum number of templates to cache
        
        // Initialize cache from localStorage
        this.loadCacheFromStorage();
    }

    /**
     * Scan the template directory structure and return organized template data
     * @returns {Promise<Object>} Template structure organized by category
     */
    async scanTemplateDirectory() {
        try {
            // Check if we have valid cached data
            if (this.structureCache && this.isCacheValid()) {
                console.log('Using cached template structure');
                return this.structureCache;
            }

            console.log('Scanning template directory structure...');
            const structure = {};

            // Try to discover categories by attempting to fetch known directories
            const knownCategories = ['Security', 'Cost Optimization', 'Performance', 'Reliability', 'Operational Excellence'];
            
            for (const category of knownCategories) {
                try {
                    const templates = await this.scanCategoryDirectory(category);
                    if (templates.length > 0) {
                        structure[category] = templates;
                    }
                } catch (error) {
                    console.warn(`Category ${category} not found or inaccessible:`, error.message);
                }
            }

            // Try to discover additional categories dynamically
            await this.discoverAdditionalCategories(structure);

            this.structureCache = structure;
            this.lastCacheUpdate = new Date();
            
            // Save to localStorage
            this.saveCacheToStorage();
            
            console.log('Template structure discovered:', structure);
            return structure;

        } catch (error) {
            console.error('Error scanning template directory:', error);
            throw new Error(`Failed to scan template directory: ${error.message}`);
        }
    }

    /**
     * Scan a specific category directory for template files
     * @param {string} category - Category name to scan
     * @returns {Promise<Array>} Array of template file objects
     */
    async scanCategoryDirectory(category) {
        const templates = [];
        const categoryPath = `${this.baseUrl}${category}/`;

        // Common template file names to check
        const commonTemplates = [
            'Security Services.md',
            'Check Network Encryption.md', 
            'Storage Encryption Analysis.md',
            'Scan for saving plans options.md',
            'Insights from Compute Optimizer.md',
            'Performance Analysis.md',
            'Reliability Assessment.md',
            'Operational Excellence Review.md'
        ];

        for (const templateName of commonTemplates) {
            try {
                const response = await fetch(`${categoryPath}${templateName}`, { method: 'HEAD' });
                if (response.ok) {
                    templates.push({
                        name: templateName.replace('.md', ''),
                        displayName: templateName.replace('.md', ''),
                        path: `${categoryPath}${templateName}`,
                        category: category,
                        lastModified: response.headers.get('last-modified') ? new Date(response.headers.get('last-modified')) : null
                    });
                }
            } catch (error) {
                // Template doesn't exist, continue checking others
                continue;
            }
        }

        return templates;
    }

    /**
     * Attempt to discover additional categories beyond the known ones
     * @param {Object} structure - Current structure to add to
     */
    async discoverAdditionalCategories(structure) {
        // This is a simplified approach since we can't directly list directories in a browser
        // In a real implementation, this would be handled by a backend API
        const additionalCategories = ['Monitoring', 'Compliance', 'Disaster Recovery'];
        
        for (const category of additionalCategories) {
            if (!structure[category]) {
                try {
                    const templates = await this.scanCategoryDirectory(category);
                    if (templates.length > 0) {
                        structure[category] = templates;
                    }
                } catch (error) {
                    // Category doesn't exist, continue
                    continue;
                }
            }
        }
    }

    /**
     * Get cached template structure if available
     * @returns {Object|null} Cached template structure or null
     */
    getCachedTemplates() {
        if (this.structureCache && this.isCacheValid()) {
            return this.structureCache;
        }
        return null;
    }

    /**
     * Force refresh of template cache
     * @returns {Promise<Object>} Fresh template structure
     */
    async refreshTemplates() {
        console.log('Forcing template cache refresh...');
        this.structureCache = null;
        this.lastCacheUpdate = null;
        this.templateCache.clear();
        return await this.scanTemplateDirectory();
    }

    /**
     * Check if the current cache is still valid
     * @returns {boolean} True if cache is valid
     */
    isCacheValid() {
        if (!this.lastCacheUpdate) {
            return false;
        }
        const now = new Date();
        return (now - this.lastCacheUpdate) < this.cacheTimeout;
    }

    /**
     * Get template categories from cached structure
     * @returns {Array<string>} Array of category names
     */
    getCategories() {
        const cached = this.getCachedTemplates();
        return cached ? Object.keys(cached) : [];
    }

    /**
     * Get templates for a specific category
     * @param {string} category - Category name
     * @returns {Array} Array of template objects for the category
     */
    getTemplatesForCategory(category) {
        const cached = this.getCachedTemplates();
        return cached && cached[category] ? cached[category] : [];
    }

    /**
     * Check if templates are available
     * @returns {boolean} True if templates are available
     */
    hasTemplates() {
        const cached = this.getCachedTemplates();
        return cached && Object.keys(cached).length > 0;
    }

    /**
     * Get total number of templates across all categories
     * @returns {number} Total template count
     */
    getTotalTemplateCount() {
        const cached = this.getCachedTemplates();
        if (!cached) return 0;
        
        return Object.values(cached).reduce((total, templates) => total + templates.length, 0);
    }

    /**
     * Search templates by name across all categories
     * @param {string} searchTerm - Search term
     * @returns {Array} Array of matching templates
     */
    searchTemplates(searchTerm) {
        const cached = this.getCachedTemplates();
        if (!cached || !searchTerm) return [];

        const results = [];
        const term = searchTerm.toLowerCase();

        for (const [category, templates] of Object.entries(cached)) {
            for (const template of templates) {
                if (template.name.toLowerCase().includes(term) || 
                    template.displayName.toLowerCase().includes(term)) {
                    results.push({ ...template, category });
                }
            }
        }

        return results;
    }

    /**
     * Load template content from a file
     * @param {string} templatePath - Full path to template file
     * @returns {Promise<string>} Template content
     */
    async loadTemplateContent(templatePath) {
        try {
            // Check cache first
            if (this.templateCache.has(templatePath)) {
                console.log(`Loading template from cache: ${templatePath}`);
                return this.templateCache.get(templatePath);
            }

            console.log(`Loading template content: ${templatePath}`);
            const response = await fetch(templatePath);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const content = await response.text();
            
            // Validate content
            const validatedContent = this.validateTemplateContent(content, templatePath);
            
            // Cache the content
            this.templateCache.set(templatePath, validatedContent);
            this.manageCacheSize();
            
            // Update localStorage cache
            this.saveCacheToStorage();
            
            return validatedContent;

        } catch (error) {
            console.error(`Error loading template ${templatePath}:`, error);
            
            // Try to provide fallback content
            return this.getFallbackContent(templatePath, error);
        }
    }

    /**
     * Load template content by category and name
     * @param {string} category - Template category
     * @param {string} templateName - Template name
     * @returns {Promise<string>} Template content
     */
    async loadTemplateByName(category, templateName) {
        const templatePath = `${this.baseUrl}${category}/${templateName}.md`;
        return await this.loadTemplateContent(templatePath);
    }

    /**
     * Validate template content and handle malformed files
     * @param {string} content - Raw template content
     * @param {string} templatePath - Path to template for error context
     * @returns {string} Validated content
     */
    validateTemplateContent(content, templatePath) {
        if (!content || content.trim().length === 0) {
            console.warn(`Empty template content: ${templatePath}`);
            return this.getEmptyTemplateContent(templatePath);
        }

        // Check for basic Markdown structure
        if (!content.includes('#') && !content.includes('##')) {
            console.warn(`Template may not be properly formatted: ${templatePath}`);
        }

        // Remove any potential security risks (basic sanitization)
        const sanitizedContent = content
            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
            .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '');

        if (sanitizedContent !== content) {
            console.warn(`Removed potentially unsafe content from: ${templatePath}`);
        }

        return sanitizedContent;
    }

    /**
     * Provide fallback content when template loading fails
     * @param {string} templatePath - Path that failed to load
     * @param {Error} error - Original error
     * @returns {string} Fallback content
     */
    getFallbackContent(templatePath, error) {
        const templateName = templatePath.split('/').pop().replace('.md', '');
        
        console.warn(`Using fallback content for: ${templateName}`);
        
        return `# ${templateName}

I apologize, but there was an error loading this template.

**Error Details:** ${error.message}

**Template Path:** ${templatePath}

Please try one of the following:
1. Refresh the page and try again
2. Check if the template file exists
3. Use free-form input to describe your request

You can still ask me questions directly in the chat input below.`;
    }

    /**
     * Generate content for empty templates
     * @param {string} templatePath - Path to empty template
     * @returns {string} Default content
     */
    getEmptyTemplateContent(templatePath) {
        const templateName = templatePath.split('/').pop().replace('.md', '');
        
        return `# ${templateName}

This template is currently empty. Please describe what you would like me to help you with regarding ${templateName.toLowerCase()}.

## What I can help with:

- Analysis and assessment
- Best practices recommendations  
- Configuration reviews
- Troubleshooting guidance

Please provide details about your specific requirements and I'll assist you accordingly.`;
    }

    /**
     * Preload frequently used templates
     * @param {Array<string>} templatePaths - Array of template paths to preload
     */
    async preloadTemplates(templatePaths = []) {
        console.log('Preloading templates...');
        
        const defaultTemplates = [
            'Security/Security Services.md',
            'Security/Check Network Encryption.md',
            'Cost Optimization/Scan for saving plans options.md'
        ];

        const toPreload = templatePaths.length > 0 ? templatePaths : defaultTemplates;
        
        const preloadPromises = toPreload.map(async (templatePath) => {
            try {
                const fullPath = templatePath.startsWith(this.baseUrl) ? templatePath : `${this.baseUrl}${templatePath}`;
                await this.loadTemplateContent(fullPath);
            } catch (error) {
                console.warn(`Failed to preload template: ${templatePath}`, error);
            }
        });

        await Promise.allSettled(preloadPromises);
        console.log('Template preloading completed');
    }

    /**
     * Clear template content cache
     */
    clearContentCache() {
        console.log('Clearing template content cache');
        this.templateCache.clear();
    }

    /**
     * Load cache from localStorage
     */
    loadCacheFromStorage() {
        try {
            const cached = localStorage.getItem(this.localStorageKey);
            if (cached) {
                const cacheData = JSON.parse(cached);
                
                // Check if cache is still valid
                if (cacheData.timestamp && (Date.now() - cacheData.timestamp) < this.cacheTimeout) {
                    console.log('Loading template cache from localStorage');
                    
                    // Restore structure cache
                    if (cacheData.structure) {
                        this.structureCache = cacheData.structure;
                        this.lastCacheUpdate = new Date(cacheData.timestamp);
                    }
                    
                    // Restore content cache
                    if (cacheData.content) {
                        this.templateCache = new Map(Object.entries(cacheData.content));
                    }
                } else {
                    console.log('Template cache expired, clearing localStorage');
                    localStorage.removeItem(this.localStorageKey);
                }
            }
        } catch (error) {
            console.warn('Failed to load template cache from localStorage:', error);
            localStorage.removeItem(this.localStorageKey);
        }
    }

    /**
     * Save cache to localStorage
     */
    saveCacheToStorage() {
        try {
            const cacheData = {
                timestamp: Date.now(),
                structure: this.structureCache,
                content: Object.fromEntries(this.templateCache)
            };
            
            localStorage.setItem(this.localStorageKey, JSON.stringify(cacheData));
            console.log('Template cache saved to localStorage');
        } catch (error) {
            console.warn('Failed to save template cache to localStorage:', error);
            
            // If storage is full, try to clear old cache and retry
            if (error.name === 'QuotaExceededError') {
                this.clearStorageCache();
                try {
                    localStorage.setItem(this.localStorageKey, JSON.stringify(cacheData));
                } catch (retryError) {
                    console.error('Failed to save cache even after clearing:', retryError);
                }
            }
        }
    }

    /**
     * Clear cache from localStorage
     */
    clearStorageCache() {
        try {
            localStorage.removeItem(this.localStorageKey);
            console.log('Template cache cleared from localStorage');
        } catch (error) {
            console.warn('Failed to clear template cache from localStorage:', error);
        }
    }

    /**
     * Manage cache size to prevent memory issues
     */
    manageCacheSize() {
        if (this.templateCache.size > this.maxCacheSize) {
            console.log('Template cache size exceeded, removing oldest entries');
            
            // Convert to array and sort by access time (if we had that data)
            // For now, just remove the first entries
            const entries = Array.from(this.templateCache.entries());
            const toRemove = entries.slice(0, entries.length - this.maxCacheSize);
            
            for (const [key] of toRemove) {
                this.templateCache.delete(key);
            }
            
            console.log(`Removed ${toRemove.length} entries from template cache`);
        }
    }

    /**
     * Invalidate cache based on conditions
     * @param {string} reason - Reason for invalidation
     */
    invalidateCache(reason = 'manual') {
        console.log(`Invalidating template cache: ${reason}`);
        
        this.structureCache = null;
        this.lastCacheUpdate = null;
        this.templateCache.clear();
        this.clearStorageCache();
        
        // Emit cache invalidation event
        const event = new CustomEvent('templateCacheInvalidated', {
            detail: { reason }
        });
        document.dispatchEvent(event);
    }

    /**
     * Update cache with new data
     * @param {Object} structure - New template structure
     * @param {Map} contentCache - New content cache
     */
    updateCache(structure, contentCache = null) {
        this.structureCache = structure;
        this.lastCacheUpdate = new Date();
        
        if (contentCache) {
            this.templateCache = new Map([...this.templateCache, ...contentCache]);
            this.manageCacheSize();
        }
        
        // Save to localStorage
        this.saveCacheToStorage();
        
        console.log('Template cache updated');
    }

    /**
     * Get cache statistics
     * @returns {Object} Cache statistics
     */
    getCacheStats() {
        const storageUsed = this.getStorageUsage();
        
        return {
            structureCached: !!this.structureCache,
            structureCacheAge: this.lastCacheUpdate ? new Date() - this.lastCacheUpdate : null,
            contentCacheSize: this.templateCache.size,
            maxCacheSize: this.maxCacheSize,
            cacheTimeout: this.cacheTimeout,
            storageUsed: storageUsed,
            cacheHitRate: this.calculateCacheHitRate()
        };
    }

    /**
     * Calculate storage usage for template cache
     * @returns {Object} Storage usage information
     */
    getStorageUsage() {
        try {
            const cached = localStorage.getItem(this.localStorageKey);
            const sizeInBytes = cached ? new Blob([cached]).size : 0;
            const sizeInKB = Math.round(sizeInBytes / 1024 * 100) / 100;
            
            return {
                bytes: sizeInBytes,
                kilobytes: sizeInKB,
                megabytes: Math.round(sizeInKB / 1024 * 100) / 100
            };
        } catch (error) {
            return { bytes: 0, kilobytes: 0, megabytes: 0 };
        }
    }

    /**
     * Calculate cache hit rate (simplified)
     * @returns {number} Cache hit rate percentage
     */
    calculateCacheHitRate() {
        // This is a simplified implementation
        // In a real scenario, you'd track hits and misses
        return this.templateCache.size > 0 ? 85 : 0; // Placeholder
    }

    /**
     * Warm up cache with commonly used templates
     */
    async warmUpCache() {
        console.log('Warming up template cache...');
        
        try {
            // First ensure we have the structure
            await this.scanTemplateDirectory();
            
            // Then preload common templates
            await this.preloadTemplates();
            
            console.log('Cache warm-up completed');
        } catch (error) {
            console.warn('Cache warm-up failed:', error);
        }
    }

    /**
     * Handle errors gracefully and provide fallback behavior
     * @param {Error} error - Error object
     * @param {string} context - Context where error occurred
     */
    handleError(error, context) {
        console.error(`Template Discovery Service error in ${context}:`, error);
        
        // Emit custom event for error handling
        const errorEvent = new CustomEvent('templateDiscoveryError', {
            detail: { error, context }
        });
        document.dispatchEvent(errorEvent);
    }
}

// Export for use in other modules
window.TemplateDiscoveryService = TemplateDiscoveryService;