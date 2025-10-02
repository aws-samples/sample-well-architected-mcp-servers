/**
 * Template Selector Component
 * Manages template selection UI and integration with chat input
 */
class TemplateSelector {
    constructor() {
        this.discoveryService = new TemplateDiscoveryService();
        this.dropdownGenerator = new TemplateDropdownGenerator();
        this.templateProcessor = new TemplateProcessor();
        this.container = null;
        this.chatInput = null;
        this.isInitialized = false;
        this.currentTemplate = null;
        this.onSelectionChangeCallback = null;
        
        // Bind methods
        this.handleTemplateSelection = this.handleTemplateSelection.bind(this);
        this.handleRefreshRequest = this.handleRefreshRequest.bind(this);
        this.handleError = this.handleError.bind(this);
    }

    /**
     * Initialize the template selector
     * @param {HTMLElement} container - Container element for template selector
     * @param {HTMLInputElement} chatInput - Chat input element
     */
    async initialize(container, chatInput) {
        if (this.isInitialized) {
            console.warn('TemplateSelector already initialized');
            return;
        }

        console.log('Initializing TemplateSelector...');
        
        this.container = container;
        this.chatInput = chatInput;

        try {
            // Set up event listeners
            this.setupEventListeners();
            
            // Render the template selector UI
            await this.renderTemplateSelector();
            
            // Warm up cache
            await this.discoveryService.warmUpCache();
            
            this.isInitialized = true;
            console.log('TemplateSelector initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize TemplateSelector:', error);
            this.handleError(error, 'initialization');
        }
    }

    /**
     * Render the complete template selector interface
     */
    async renderTemplateSelector() {
        if (!this.container) {
            throw new Error('Container not set for TemplateSelector');
        }

        try {
            console.log('Rendering template selector...');
            
            // Show loading state
            this.showLoadingState();
            
            // Discover templates
            const templateStructure = await this.discoveryService.scanTemplateDirectory();
            
            // Generate dropdowns
            const dropdownsContainer = this.dropdownGenerator.generateDropdowns(templateStructure);
            
            // Clear container and add new content
            this.container.innerHTML = '';
            this.container.appendChild(dropdownsContainer);
            
            // Add CSS if not already added
            this.ensureStylesLoaded();
            
            console.log('Template selector rendered successfully');
            
        } catch (error) {
            console.error('Error rendering template selector:', error);
            this.showErrorState(error.message);
        }
    }

    /**
     * Set up event listeners for template system
     */
    setupEventListeners() {
        // Template selection events
        this.dropdownGenerator.onTemplateSelected(this.handleTemplateSelection);
        
        // Document-level events
        document.addEventListener('templateSelected', this.handleTemplateSelection);
        document.addEventListener('templateSelectionCleared', this.handleSelectionCleared.bind(this));
        document.addEventListener('templateRefreshRequested', this.handleRefreshRequest);
        document.addEventListener('templateDiscoveryError', this.handleError);
        
        // Chat input events
        if (this.chatInput) {
            this.chatInput.addEventListener('input', this.handleChatInputChange.bind(this));
            this.chatInput.addEventListener('focus', this.handleChatInputFocus.bind(this));
        }
    }

    /**
     * Handle template selection
     * @param {Object|CustomEvent} templateInfo - Template information or event
     */
    async handleTemplateSelection(templateInfo) {
        try {
            // Handle both direct calls and events
            const template = templateInfo.detail || templateInfo;
            
            if (!template || !template.path) {
                console.warn('Invalid template selection:', template);
                return;
            }

            console.log('Handling template selection:', template);
            
            // Show loading state
            this.showTemplateLoadingState(template);
            
            // Load template content
            const rawContent = await this.discoveryService.loadTemplateContent(template.path);
            
            // Process template placeholders
            const processedContent = await this.templateProcessor.processTemplate(rawContent);
            
            // Populate chat input
            this.populateChatInput(processedContent);
            
            // Store current template
            this.currentTemplate = template;
            
            // Hide loading state
            this.hideTemplateLoadingState();
            
            // Trigger callback
            if (this.onSelectionChangeCallback) {
                this.onSelectionChangeCallback(template);
            }
            
            // Focus chat input
            if (this.chatInput) {
                this.chatInput.focus();
                // Move cursor to end
                this.chatInput.setSelectionRange(this.chatInput.value.length, this.chatInput.value.length);
            }
            
        } catch (error) {
            console.error('Error handling template selection:', error);
            this.hideTemplateLoadingState();
            this.showTemplateError(error.message);
        }
    }

    /**
     * Handle selection cleared event
     */
    handleSelectionCleared() {
        console.log('Template selection cleared');
        this.currentTemplate = null;
        
        if (this.onSelectionChangeCallback) {
            this.onSelectionChangeCallback(null);
        }
    }

    /**
     * Handle refresh request
     */
    async handleRefreshRequest() {
        try {
            console.log('Handling template refresh request...');
            
            // Refresh templates
            const templateStructure = await this.discoveryService.refreshTemplates();
            
            // Update dropdowns
            this.dropdownGenerator.updateDropdowns(templateStructure);
            
            console.log('Template refresh completed');
            
        } catch (error) {
            console.error('Error refreshing templates:', error);
            this.handleError(error, 'refresh');
        }
    }

    /**
     * Handle chat input changes
     * @param {Event} event - Input event
     */
    handleChatInputChange(event) {
        // If user starts typing and has a template selected, clear the selection
        if (this.currentTemplate && event.target.value !== this.currentTemplate.content) {
            // Only clear if the content has significantly changed
            const originalLength = this.currentTemplate.content?.length || 0;
            const currentLength = event.target.value.length;
            
            // Clear selection if content is significantly different
            if (Math.abs(originalLength - currentLength) > 50) {
                this.clearSelection();
            }
        }
    }

    /**
     * Handle chat input focus
     */
    handleChatInputFocus() {
        // Could add template suggestions or other focus-related behavior
    }

    /**
     * Populate chat input with template content
     * @param {string} content - Template content
     */
    populateChatInput(content) {
        if (!this.chatInput) {
            console.warn('Chat input not available for population');
            return;
        }

        console.log('Populating chat input with template content');
        
        // Set the content
        this.chatInput.value = content;
        
        // Store original content for comparison
        if (this.currentTemplate) {
            this.currentTemplate.content = content;
        }
        
        // Trigger input event to notify other components
        const inputEvent = new Event('input', { bubbles: true });
        this.chatInput.dispatchEvent(inputEvent);
        
        // Add visual feedback
        this.addChatInputFeedback();
    }

    /**
     * Add visual feedback to chat input when template is loaded
     */
    addChatInputFeedback() {
        if (!this.chatInput) return;
        
        this.chatInput.classList.add('template-populated');
        
        // Remove feedback after a short delay
        setTimeout(() => {
            if (this.chatInput) {
                this.chatInput.classList.remove('template-populated');
            }
        }, 2000);
    }

    /**
     * Clear template selection
     */
    clearSelection() {
        console.log('Clearing template selection');
        
        this.currentTemplate = null;
        this.dropdownGenerator.clearSelection();
        
        if (this.onSelectionChangeCallback) {
            this.onSelectionChangeCallback(null);
        }
    }

    /**
     * Show loading state
     */
    showLoadingState() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="template-loading-container">
                <div class="template-loading-spinner"></div>
                <span>Loading templates...</span>
            </div>
        `;
    }

    /**
     * Show template loading state
     * @param {Object} template - Template being loaded
     */
    showTemplateLoadingState(template) {
        // Add loading indicator to the specific dropdown
        const dropdowns = this.container.querySelectorAll('.template-dropdown-select');
        dropdowns.forEach(select => {
            if (select.value === template.name) {
                this.dropdownGenerator.addLoadingState(select);
            }
        });
    }

    /**
     * Hide template loading state
     */
    hideTemplateLoadingState() {
        const dropdowns = this.container.querySelectorAll('.template-dropdown-select');
        dropdowns.forEach(select => {
            this.dropdownGenerator.removeLoadingState(select);
        });
    }

    /**
     * Show error state
     * @param {string} errorMessage - Error message to display
     */
    showErrorState(errorMessage) {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="template-error-container">
                <div class="template-error-icon">⚠️</div>
                <div class="template-error-content">
                    <h4>Template System Error</h4>
                    <p>${errorMessage}</p>
                    <button class="template-retry-btn" onclick="window.templateSelector?.renderTemplateSelector()">
                        Retry
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Show template-specific error
     * @param {string} errorMessage - Error message
     */
    showTemplateError(errorMessage) {
        // Show error in the currently selected dropdown
        const dropdowns = this.container.querySelectorAll('.template-dropdown-select');
        dropdowns.forEach(select => {
            if (select.classList.contains('template-selected')) {
                this.dropdownGenerator.addErrorState(select, errorMessage);
            }
        });
    }

    /**
     * Ensure CSS styles are loaded
     */
    ensureStylesLoaded() {
        const existingLink = document.querySelector('link[href*="template-styles.css"]');
        if (!existingLink) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = './css/template-styles.css';
            document.head.appendChild(link);
        }
    }

    /**
     * Handle errors
     * @param {Error|CustomEvent} error - Error object or event
     * @param {string} context - Error context
     */
    handleError(error, context = 'unknown') {
        const errorObj = error.detail?.error || error;
        const errorContext = error.detail?.context || context;
        
        console.error(`TemplateSelector error in ${errorContext}:`, errorObj);
        
        // Show user-friendly error message
        const message = this.getUserFriendlyErrorMessage(errorObj, errorContext);
        
        if (errorContext === 'initialization') {
            this.showErrorState(message);
        } else {
            this.showTemplateError(message);
        }
    }

    /**
     * Get user-friendly error message
     * @param {Error} error - Error object
     * @param {string} context - Error context
     * @returns {string} User-friendly message
     */
    getUserFriendlyErrorMessage(error, context) {
        const messages = {
            'initialization': 'Failed to initialize template system. Please refresh the page.',
            'refresh': 'Failed to refresh templates. Please try again.',
            'loading': 'Failed to load template. Please try selecting another template.',
            'network': 'Network error. Please check your connection and try again.',
            'permission': 'Permission denied. Please check file permissions.',
            'not_found': 'Template not found. It may have been moved or deleted.'
        };
        
        // Try to match error type
        if (error.message?.includes('fetch')) {
            return messages.network;
        } else if (error.message?.includes('404')) {
            return messages.not_found;
        } else if (error.message?.includes('403')) {
            return messages.permission;
        }
        
        return messages[context] || 'An unexpected error occurred. Please try again.';
    }

    /**
     * Set callback for selection changes
     * @param {Function} callback - Callback function
     */
    onSelectionChange(callback) {
        this.onSelectionChangeCallback = callback;
    }

    /**
     * Get current template selection
     * @returns {Object|null} Current template or null
     */
    getCurrentTemplate() {
        return this.currentTemplate;
    }

    /**
     * Get template selector statistics
     * @returns {Object} Statistics
     */
    getStats() {
        return {
            initialized: this.isInitialized,
            hasCurrentTemplate: !!this.currentTemplate,
            currentTemplate: this.currentTemplate?.name || null,
            discoveryStats: this.discoveryService.getCacheStats(),
            dropdownStats: this.dropdownGenerator.getStats()
        };
    }

    /**
     * Destroy the template selector and cleanup
     */
    destroy() {
        console.log('Destroying TemplateSelector...');
        
        // Remove event listeners
        document.removeEventListener('templateSelected', this.handleTemplateSelection);
        document.removeEventListener('templateSelectionCleared', this.handleSelectionCleared);
        document.removeEventListener('templateRefreshRequested', this.handleRefreshRequest);
        document.removeEventListener('templateDiscoveryError', this.handleError);
        
        // Cleanup components
        this.dropdownGenerator.destroy();
        
        // Clear references
        this.container = null;
        this.chatInput = null;
        this.currentTemplate = null;
        this.onSelectionChangeCallback = null;
        this.isInitialized = false;
        
        console.log('TemplateSelector destroyed');
    }
}

// Export for use in other modules
window.TemplateSelector = TemplateSelector;