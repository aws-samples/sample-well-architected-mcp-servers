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
        
        // Debug: Log the base URL and current location
        console.log('TemplateDiscoveryService initialized');
        console.log('Base URL:', this.baseUrl);
        console.log('Current location:', window.location.href);
        console.log('Current pathname:', window.location.pathname);
        
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
            
            // Try to load from index.json first
            try {
                console.log('Attempting to load from index.json...');
                const structure = await this.loadFromIndex();
                console.log('Index.json loaded successfully:', structure);
                
                if (structure && Object.keys(structure).length > 0) {
                    this.structureCache = structure;
                    this.lastCacheUpdate = new Date();
                    this.saveCacheToStorage();
                    console.log('Template structure loaded from index.json:', structure);
                    return structure;
                } else {
                    console.warn('Index.json loaded but structure is empty');
                }
            } catch (indexError) {
                console.warn('Failed to load from index.json, falling back to directory scanning:', indexError.message);
                console.error('Index loading error details:', indexError);
            }

            // Fallback to dynamic directory scanning method
            const structure = {};
            
            // Try to discover categories dynamically by scanning the base directory
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
     * Load template structure from index.json file
     * @returns {Promise<Object>} Template structure from index file
     */
    async loadFromIndex() {
        try {
            console.log('Loading template structure from index.json...');
            const indexUrl = `${this.baseUrl}index.json`;
            console.log('Full index URL:', indexUrl);
            console.log('Attempting to fetch:', indexUrl);
            
            const response = await fetch(indexUrl);
            console.log('Fetch response:', response.status, response.statusText);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText} - URL: ${indexUrl}`);
            }

            const indexData = await response.json();
            console.log('Raw index.json data:', indexData);
            
            if (!indexData.categories) {
                throw new Error('Invalid index.json format: missing categories');
            }

            const structure = {};
            
            // Process each category from the index
            for (const [categoryKey, categoryData] of Object.entries(indexData.categories)) {
                console.log(`Processing category from index: ${categoryKey}`, categoryData);
                const templates = [];
                
                // Process main category templates
                if (categoryData.templates && categoryData.templates.length > 0) {
                    for (const templateInfo of categoryData.templates) {
                        console.log(`Processing main template: ${templateInfo.name}`, templateInfo);
                        
                        const templatePath = templateInfo.path ? 
                            `${this.baseUrl}${templateInfo.path}/${templateInfo.filename}` :
                            `${this.baseUrl}${categoryKey}/${templateInfo.filename}`;
                        
                        templates.push({
                            name: templateInfo.name,
                            displayName: templateInfo.displayName || templateInfo.name,
                            filename: templateInfo.filename,
                            path: templatePath,
                            category: categoryKey,
                            subcategory: null,
                            description: templateInfo.description,
                            lastModified: templateInfo.lastModified ? new Date(templateInfo.lastModified) : null
                        });
                    }
                }
                
                // Process subcategories if they exist
                if (categoryData.subcategories) {
                    for (const [subCategoryKey, subCategoryData] of Object.entries(categoryData.subcategories)) {
                        console.log(`Processing subcategory: ${categoryKey}/${subCategoryKey}`, subCategoryData);
                        
                        if (subCategoryData.templates && subCategoryData.templates.length > 0) {
                            for (const templateInfo of subCategoryData.templates) {
                                console.log(`Processing subcategory template: ${templateInfo.name}`, templateInfo);
                                
                                const templatePath = templateInfo.path ? 
                                    `${this.baseUrl}${templateInfo.path}/${templateInfo.filename}` :
                                    `${this.baseUrl}${categoryKey}/${subCategoryKey}/${templateInfo.filename}`;
                                
                                templates.push({
                                    name: templateInfo.name,
                                    displayName: templateInfo.displayName || templateInfo.name,
                                    filename: templateInfo.filename,
                                    path: templatePath,
                                    category: categoryKey,
                                    subcategory: subCategoryKey,
                                    description: templateInfo.description,
                                    lastModified: templateInfo.lastModified ? new Date(templateInfo.lastModified) : null
                                });
                            }
                        }
                    }
                }
                
                if (templates.length > 0) {
                    structure[categoryKey] = templates;
                    console.log(`Added ${templates.length} templates to category: ${categoryKey}`);
                }
            }

            console.log(`Loaded ${Object.keys(structure).length} categories from index.json`);
            return structure;

        } catch (error) {
            console.error('Error loading from index.json:', error);
            throw error;
        }
    }

    /**
     * Scan category directory recursively for subcategories (max 2 levels)
     * @param {string} categoryPath - Path to category directory
     * @returns {Promise<Object>} Category structure with subcategories
     */
    async scanCategoryWithSubcategories(categoryPath) {
        const categoryName = categoryPath.split('/').pop();
        const structure = {
            name: categoryName,
            templates: [],
            subcategories: {}
        };

        try {
            // First, try to scan for direct templates in the category
            const directTemplates = await this.scanCategoryDirectory(categoryName);
            structure.templates = directTemplates;

            // Then, try to detect subcategories by attempting to access known subdirectories
            const potentialSubcategories = [
                'Auto Scaling Groups',
                'ECS Rightsizing', 
                'Savings Plans',
                'Network',
                'Identity',
                'Storage',
                'Compute'
            ];

            for (const subcategoryName of potentialSubcategories) {
                try {
                    const subcategoryPath = `${categoryPath}/${subcategoryName}/`;
                    const isDirectory = await this.isTemplateDirectory(subcategoryPath);
                    
                    if (isDirectory) {
                        const subcategoryTemplates = await this.scanSubcategoryDirectory(categoryPath, subcategoryName);
                        if (subcategoryTemplates.length > 0) {
                            structure.subcategories[subcategoryName] = {
                                name: subcategoryName,
                                templates: subcategoryTemplates
                            };
                            console.log(`Found subcategory: ${categoryName}/${subcategoryName} with ${subcategoryTemplates.length} templates`);
                        } else {
                            console.log(`Skipping empty subcategory: ${categoryName}/${subcategoryName}`);
                        }
                    }
                } catch (error) {
                    // Subcategory doesn't exist or isn't accessible, continue
                    console.debug(`Subcategory ${categoryName}/${subcategoryName} not found:`, error.message);
                }
            }

            return structure;

        } catch (error) {
            console.error(`Error scanning category with subcategories: ${categoryPath}`, error);
            throw error;
        }
    }

    /**
     * Check if a path is a directory containing .md files
     * @param {string} path - Path to check
     * @returns {Promise<boolean>} True if directory with templates
     */
    async isTemplateDirectory(path) {
        try {
            // Try to access a common template file to see if directory exists
            const testFiles = ['index.md', 'README.md', 'template.md'];
            
            for (const testFile of testFiles) {
                try {
                    const response = await fetch(`${path}${testFile}`, { method: 'HEAD' });
                    if (response.ok) {
                        return true;
                    }
                } catch (error) {
                    // File doesn't exist, try next
                    continue;
                }
            }

            // If no test files found, try to access the directory itself
            // This is a heuristic - if we can access any .md file, assume it's a template directory
            const response = await fetch(path, { method: 'HEAD' });
            return response.ok;

        } catch (error) {
            console.debug(`Directory check failed for ${path}:`, error.message);
            return false;
        }
    }

    /**
     * Scan a subcategory directory for template files
     * @param {string} categoryPath - Parent category path
     * @param {string} subcategoryName - Subcategory name
     * @returns {Promise<Array>} Array of template objects
     */
    async scanSubcategoryDirectory(categoryPath, subcategoryName) {
        const templates = [];
        const subcategoryPath = `${categoryPath}/${subcategoryName}/`;

        // Common template patterns to check
        const templatePatterns = [
            `${subcategoryName} - Quick Start.md`,
            `${subcategoryName} - Analysis.md`,
            `${subcategoryName} - Optimization.md`,
            `${subcategoryName} - Best Practices.md`,
            `${subcategoryName} - Assessment.md`
        ];

        // Also check for files that might be in the subcategory based on index.json
        const knownSubcategoryFiles = {
            'Auto Scaling Groups': [
                'Auto Scaling Group Optimization.md',
                'Auto Scaling Groups - Cost Analysis.md',
                'Auto Scaling Groups - Rightsizing Recommendations.md',
                'Auto Scaling Groups - Spot Instance Opportunities.md'
            ],
            'ECS Rightsizing': [
                'EC2 Instance Rightsizing Analysis.md',
                'EC2 Rightsizing - Quick Wins.md',
                'EC2 Rightsizing - Top Opportunities.md',
                'EC2 Rightsizing - Underutilized Instances.md'
            ],
            'Savings Plans': [
                'Scan for saving plans options.md',
                'Reserved Instances - Purchase Recommendations.md',
                'Savings Plans - Compute Recommendations.md',
                'Savings Plans - Current Utilization.md'
            ]
        };

        const filesToCheck = knownSubcategoryFiles[subcategoryName] || templatePatterns;

        for (const templateFile of filesToCheck) {
            try {
                const response = await fetch(`${subcategoryPath}${templateFile}`, { method: 'HEAD' });
                if (response.ok) {
                    templates.push({
                        name: templateFile.replace('.md', ''),
                        displayName: templateFile.replace('.md', ''),
                        filename: templateFile,
                        path: `${subcategoryPath}${templateFile}`,
                        category: categoryPath.split('/').pop(),
                        subcategory: subcategoryName,
                        lastModified: response.headers.get('last-modified') ? 
                            new Date(response.headers.get('last-modified')) : null
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
     * Get templates organized by category and subcategory
     * @returns {Promise<Object>} Hierarchical template structure
     */
    async getHierarchicalStructure() {
        try {
            // First try to load from index.json which already supports hierarchical structure
            const indexStructure = await this.loadFromIndex();
            
            // Convert to hierarchical format
            const hierarchical = {};
            
            for (const [categoryName, templates] of Object.entries(indexStructure)) {
                hierarchical[categoryName] = {
                    name: categoryName,
                    templates: templates.filter(t => !t.subcategory),
                    subcategories: {}
                };
                
                // Group templates by subcategory
                const subcategoryGroups = {};
                templates.filter(t => t.subcategory).forEach(template => {
                    if (!subcategoryGroups[template.subcategory]) {
                        subcategoryGroups[template.subcategory] = [];
                    }
                    subcategoryGroups[template.subcategory].push(template);
                });
                
                // Add subcategories to structure
                for (const [subcategoryName, subcategoryTemplates] of Object.entries(subcategoryGroups)) {
                    hierarchical[categoryName].subcategories[subcategoryName] = {
                        name: subcategoryName,
                        templates: subcategoryTemplates
                    };
                }
            }
            
            return hierarchical;
            
        } catch (error) {
            console.error('Error getting hierarchical structure:', error);
            
            // Fallback to scanning directories
            const structure = {};
            const knownCategories = ['Security', 'Cost Optimization', 'Performance', 'Reliability', 'Operational Excellence'];
            
            for (const category of knownCategories) {
                try {
                    const categoryStructure = await this.scanCategoryWithSubcategories(category);
                    if (categoryStructure.templates.length > 0 || Object.keys(categoryStructure.subcategories).length > 0) {
                        structure[category] = categoryStructure;
                    }
                } catch (error) {
                    console.warn(`Failed to scan category ${category}:`, error.message);
                }
            }
            
            return structure;
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

        // Since we can't directly list directory contents from the browser,
        // we'll rely on the index.json file or return empty array for fallback
        console.warn(`Cannot dynamically scan category directory: ${category}`);
        console.warn('Browser security prevents directory listing. Use index.json for template discovery.');

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
     * Force refresh templates by clearing all caches and reloading
     * @returns {Promise<Object>} Fresh template structure
     */
    async forceRefresh() {
        console.log('🔄 Force refreshing templates...');
        
        // Clear all caches
        this.invalidateCache('force_refresh');
        
        // Force reload from server
        const freshStructure = await this.scanTemplateDirectory();
        
        console.log('✅ Templates force refreshed successfully');
        return freshStructure;
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
     * Add a new template to the index (for future backend integration)
     * @param {string} category - Category name
     * @param {Object} templateInfo - Template information
     * @returns {Promise<boolean>} Success status
     */
    async addTemplateToIndex(category, templateInfo) {
        try {
            console.log(`Adding template to index: ${category}/${templateInfo.name}`);
            
            // This would typically be handled by a backend API
            // For now, we'll just invalidate the cache to force a refresh
            this.invalidateCache('new_template_added');
            
            // Emit event for UI updates
            const event = new CustomEvent('templateAdded', {
                detail: { category, templateInfo }
            });
            document.dispatchEvent(event);
            
            return true;
        } catch (error) {
            console.error('Error adding template to index:', error);
            return false;
        }
    }

    /**
     * Refresh index from server (for future backend integration)
     * @returns {Promise<Object>} Updated template structure
     */
    async refreshIndex() {
        try {
            console.log('Refreshing template index from server...');
            
            // Force reload from index.json
            this.invalidateCache('manual_refresh');
            const structure = await this.loadFromIndex();
            
            // Emit refresh event
            const event = new CustomEvent('templateIndexRefreshed', {
                detail: { structure }
            });
            document.dispatchEvent(event);
            
            return structure;
        } catch (error) {
            console.error('Error refreshing index:', error);
            throw error;
        }
    }

    /**
     * Get index metadata
     * @returns {Promise<Object>} Index metadata
     */
    async getIndexMetadata() {
        try {
            const indexUrl = `${this.baseUrl}index.json`;
            const response = await fetch(indexUrl);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const indexData = await response.json();
            
            return {
                version: indexData.version,
                lastUpdated: indexData.lastUpdated,
                categoryCount: Object.keys(indexData.categories || {}).length,
                totalTemplates: Object.values(indexData.categories || {})
                    .reduce((total, category) => total + (category.templates?.length || 0), 0)
            };
        } catch (error) {
            console.error('Error getting index metadata:', error);
            return null;
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