/**
 * Template Dropdown Generator
 * Dynamically creates dropdown UI elements based on discovered template structure
 */
class TemplateDropdownGenerator {
    constructor() {
        this.dropdowns = new Map();
        this.eventHandlers = new Map();
        this.selectedTemplate = null;
        this.onSelectionCallback = null;
    }

    /**
     * Generate dropdown elements for all template categories
     * @param {Object} templateStructure - Template structure organized by category
     * @returns {HTMLElement} Container element with all dropdowns
     */
    generateDropdowns(templateStructure) {
        console.log('Generating template dropdowns...', templateStructure);

        // Create main container
        const container = document.createElement('div');
        container.className = 'template-dropdowns-container';
        container.innerHTML = `
            <div class="template-selector-header">
                <span class="template-selector-title">📋 Quick Templates</span>
                <div class="template-header-controls">
                    <input type="text" class="template-search-input" placeholder="Search templates..." />
                    <button class="template-refresh-btn" title="Refresh Templates">🔄</button>
                </div>
            </div>
            <div class="template-dropdowns-wrapper"></div>
        `;

        const wrapper = container.querySelector('.template-dropdowns-wrapper');
        const refreshBtn = container.querySelector('.template-refresh-btn');
        const searchInput = container.querySelector('.template-search-input');

        // Add refresh button handler
        refreshBtn.addEventListener('click', () => {
            this.handleRefreshClick();
        });

        // Add search functionality
        searchInput.addEventListener('input', (e) => {
            this.handleTemplateSearch(e.target.value, templateStructure);
        });

        // Add keyboard shortcuts
        searchInput.addEventListener('keydown', (e) => {
            this.handleSearchKeyboard(e);
        });

        // Generate dropdown for each category
        Object.entries(templateStructure).forEach(([category, templates]) => {
            if (templates && templates.length > 0) {
                const dropdown = this.createCategoryDropdown(category, templates);
                wrapper.appendChild(dropdown);
                this.dropdowns.set(category, dropdown);
            }
        });

        // Add "No templates" message if no categories found
        if (Object.keys(templateStructure).length === 0) {
            wrapper.innerHTML = `
                <div class="no-templates-message">
                    <span>📁 No templates found</span>
                    <small>Add .md files to the prompt-templates folder</small>
                </div>
            `;
        }

        return container;
    }

    /**
     * Create a dropdown for a specific category
     * @param {string} category - Category name
     * @param {Array} templates - Array of template objects
     * @returns {HTMLElement} Dropdown element
     */
    createCategoryDropdown(category, templates) {
        const dropdownContainer = document.createElement('div');
        dropdownContainer.className = 'template-dropdown-container';
        
        const categoryId = this.sanitizeId(category);
        
        dropdownContainer.innerHTML = `
            <div class="template-dropdown-group">
                <label for="template-select-${categoryId}" class="template-dropdown-label">
                    ${this.getCategoryIcon(category)} ${category}
                </label>
                <select id="template-select-${categoryId}" class="template-dropdown-select">
                    <option value="">Select a template...</option>
                </select>
            </div>
        `;

        const select = dropdownContainer.querySelector('.template-dropdown-select');
        this.populateDropdown(select, category, templates);
        this.attachDropdownHandlers(select, category);

        return dropdownContainer;
    }

    /**
     * Populate a dropdown with template options
     * @param {HTMLSelectElement} select - Select element to populate
     * @param {string} category - Category name
     * @param {Array} templates - Array of template objects
     */
    populateDropdown(select, category, templates) {
        // Clear existing options except the first one
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        // Add template options
        templates.forEach(template => {
            const option = document.createElement('option');
            option.value = template.name;
            option.textContent = template.displayName;
            option.dataset.templatePath = template.path;
            option.dataset.category = category;
            option.title = `Preview: ${template.displayName}`;
            select.appendChild(option);
        });

        console.log(`Populated ${category} dropdown with ${templates.length} templates`);
    }

    /**
     * Attach event handlers to a dropdown
     * @param {HTMLSelectElement} select - Select element
     * @param {string} category - Category name
     */
    attachDropdownHandlers(select, category) {
        const changeHandler = (event) => {
            this.handleTemplateSelection(event, category);
        };

        const keydownHandler = (event) => {
            this.handleKeyboardNavigation(event, category);
        };

        const focusHandler = (event) => {
            event.target.dataset.keyboardFocused = 'true';
        };

        const blurHandler = (event) => {
            event.target.dataset.keyboardFocused = 'false';
            this.hideTemplatePreview();
        };

        const mouseoverHandler = (event) => {
            if (event.target.tagName === 'OPTION' && event.target.value) {
                this.showTemplatePreview(event.target, category);
            }
        };

        const mouseoutHandler = (event) => {
            this.hideTemplatePreview();
        };

        // Attach all event listeners
        select.addEventListener('change', changeHandler);
        select.addEventListener('keydown', keydownHandler);
        select.addEventListener('focus', focusHandler);
        select.addEventListener('blur', blurHandler);
        select.addEventListener('mouseover', mouseoverHandler);
        select.addEventListener('mouseout', mouseoutHandler);

        // Store handlers for cleanup
        this.eventHandlers.set(select, {
            change: changeHandler,
            keydown: keydownHandler,
            focus: focusHandler,
            blur: blurHandler,
            mouseover: mouseoverHandler,
            mouseout: mouseoutHandler
        });

        // Add ARIA attributes for accessibility
        select.setAttribute('aria-label', `Select ${category} template`);
        select.setAttribute('role', 'combobox');
        select.setAttribute('aria-expanded', 'false');
    }

    /**
     * Handle keyboard navigation for dropdowns
     * @param {KeyboardEvent} event - Keyboard event
     * @param {string} category - Category name
     */
    handleKeyboardNavigation(event, category) {
        const select = event.target;
        
        switch (event.key) {
            case 'Enter':
                event.preventDefault();
                this.handleTemplateSelection(event, category);
                break;
                
            case 'Escape':
                event.preventDefault();
                this.clearSelection();
                select.blur();
                break;
                
            case 'ArrowDown':
            case 'ArrowUp':
                // Let default behavior handle option navigation
                // Update ARIA expanded state
                select.setAttribute('aria-expanded', 'true');
                break;
                
            case 'Tab':
                // Close dropdown when tabbing away
                select.setAttribute('aria-expanded', 'false');
                break;
        }
    }

    /**
     * Handle template selection from dropdown
     * @param {Event} event - Selection event
     * @param {string} category - Category name
     */
    handleTemplateSelection(event, category) {
        const select = event.target;
        const selectedOption = select.options[select.selectedIndex];
        
        if (!selectedOption || !selectedOption.value) {
            this.clearSelection();
            return;
        }

        const templateInfo = {
            name: selectedOption.value,
            displayName: selectedOption.textContent,
            path: selectedOption.dataset.templatePath,
            category: category
        };

        console.log('Template selected:', templateInfo);

        // Clear other dropdowns
        this.clearOtherSelections(select);

        // Store selection
        this.selectedTemplate = templateInfo;

        // Add to recently used
        this.addToRecentlyUsed(templateInfo);

        // Add visual feedback
        this.addSelectionFeedback(select, templateInfo);

        // Trigger callback
        if (this.onSelectionCallback) {
            this.onSelectionCallback(templateInfo);
        }

        // Emit custom event
        const event_custom = new CustomEvent('templateSelected', {
            detail: templateInfo
        });
        document.dispatchEvent(event_custom);
    }

    /**
     * Clear selection from other dropdowns
     * @param {HTMLSelectElement} currentSelect - Currently selected dropdown
     */
    clearOtherSelections(currentSelect) {
        this.dropdowns.forEach((dropdown) => {
            const select = dropdown.querySelector('.template-dropdown-select');
            if (select && select !== currentSelect) {
                select.selectedIndex = 0;
                this.removeSelectionFeedback(select);
            }
        });
    }

    /**
     * Add visual feedback for selected template
     * @param {HTMLSelectElement} select - Select element
     * @param {Object} templateInfo - Selected template information
     */
    addSelectionFeedback(select, templateInfo) {
        select.classList.add('template-selected');
        
        // Add selected indicator
        const container = select.closest('.template-dropdown-container');
        let indicator = container.querySelector('.template-selected-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'template-selected-indicator';
            container.appendChild(indicator);
        }
        
        indicator.innerHTML = `
            <span class="selected-template-name">✓ ${templateInfo.displayName}</span>
            <button class="clear-selection-btn" title="Clear selection">×</button>
        `;

        // Add clear button handler
        const clearBtn = indicator.querySelector('.clear-selection-btn');
        clearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.clearSelection();
        });
    }

    /**
     * Remove visual feedback for template selection
     * @param {HTMLSelectElement} select - Select element
     */
    removeSelectionFeedback(select) {
        select.classList.remove('template-selected');
        
        const container = select.closest('.template-dropdown-container');
        const indicator = container.querySelector('.template-selected-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    /**
     * Clear all template selections
     */
    clearSelection() {
        console.log('Clearing template selection');
        
        this.selectedTemplate = null;
        
        this.dropdowns.forEach((dropdown) => {
            const select = dropdown.querySelector('.template-dropdown-select');
            if (select) {
                select.selectedIndex = 0;
                this.removeSelectionFeedback(select);
            }
        });

        // Emit clear event
        const event = new CustomEvent('templateSelectionCleared');
        document.dispatchEvent(event);
    }

    /**
     * Get icon for category
     * @param {string} category - Category name
     * @returns {string} Icon emoji
     */
    getCategoryIcon(category) {
        const icons = {
            'Security': '🛡️',
            'Cost Optimization': '💰',
            'Performance': '⚡',
            'Reliability': '🔧',
            'Operational Excellence': '⚙️',
            'Monitoring': '📊',
            'Compliance': '📋',
            'Disaster Recovery': '🔄'
        };
        return icons[category] || '📄';
    }

    /**
     * Sanitize category name for use as HTML ID
     * @param {string} category - Category name
     * @returns {string} Sanitized ID
     */
    sanitizeId(category) {
        return category.toLowerCase().replace(/[^a-z0-9]/g, '-');
    }

    /**
     * Handle refresh button click
     */
    handleRefreshClick() {
        console.log('Refreshing templates...');
        
        // Emit refresh event
        const event = new CustomEvent('templateRefreshRequested');
        document.dispatchEvent(event);
        
        // Add visual feedback
        const refreshBtn = document.querySelector('.template-refresh-btn');
        if (refreshBtn) {
            refreshBtn.classList.add('refreshing');
            refreshBtn.textContent = '⏳';
            
            setTimeout(() => {
                refreshBtn.classList.remove('refreshing');
                refreshBtn.textContent = '🔄';
            }, 1000);
        }
    }

    /**
     * Update dropdowns with new template structure
     * @param {Object} templateStructure - New template structure
     */
    updateDropdowns(templateStructure) {
        console.log('Updating template dropdowns...');
        
        // Clear existing dropdowns
        this.dropdowns.clear();
        
        // Find the wrapper and regenerate
        const wrapper = document.querySelector('.template-dropdowns-wrapper');
        if (wrapper) {
            wrapper.innerHTML = '';
            
            // Generate new dropdowns
            Object.entries(templateStructure).forEach(([category, templates]) => {
                if (templates && templates.length > 0) {
                    const dropdown = this.createCategoryDropdown(category, templates);
                    wrapper.appendChild(dropdown);
                    this.dropdowns.set(category, dropdown);
                }
            });
            
            // Handle empty state
            if (Object.keys(templateStructure).length === 0) {
                wrapper.innerHTML = `
                    <div class="no-templates-message">
                        <span>📁 No templates found</span>
                        <small>Add .md files to the prompt-templates folder</small>
                    </div>
                `;
            }
        }
    }

    /**
     * Set callback for template selection
     * @param {Function} callback - Callback function
     */
    onTemplateSelected(callback) {
        this.onSelectionCallback = callback;
    }

    /**
     * Get currently selected template
     * @returns {Object|null} Selected template info or null
     */
    getSelectedTemplate() {
        return this.selectedTemplate;
    }

    /**
     * Add loading state to dropdown
     * @param {HTMLSelectElement} select - Select element
     */
    addLoadingState(select) {
        select.classList.add('template-loading');
        select.disabled = true;
        
        const container = select.closest('.template-dropdown-container');
        let loadingMsg = container.querySelector('.template-loading-message');
        
        if (!loadingMsg) {
            loadingMsg = document.createElement('div');
            loadingMsg.className = 'template-loading-message';
            loadingMsg.textContent = 'Loading template...';
            container.appendChild(loadingMsg);
        }
    }

    /**
     * Remove loading state from dropdown
     * @param {HTMLSelectElement} select - Select element
     */
    removeLoadingState(select) {
        select.classList.remove('template-loading');
        select.disabled = false;
        
        const container = select.closest('.template-dropdown-container');
        const loadingMsg = container.querySelector('.template-loading-message');
        if (loadingMsg) {
            loadingMsg.remove();
        }
    }

    /**
     * Add error state to dropdown
     * @param {HTMLSelectElement} select - Select element
     * @param {string} errorMessage - Error message to display
     */
    addErrorState(select, errorMessage) {
        select.classList.add('template-error');
        
        const container = select.closest('.template-dropdown-container');
        let errorMsg = container.querySelector('.template-error-message');
        
        if (!errorMsg) {
            errorMsg = document.createElement('div');
            errorMsg.className = 'template-error-message';
            container.appendChild(errorMsg);
        }
        
        errorMsg.textContent = errorMessage;
        
        // Auto-remove error after 5 seconds
        setTimeout(() => {
            this.removeErrorState(select);
        }, 5000);
    }

    /**
     * Remove error state from dropdown
     * @param {HTMLSelectElement} select - Select element
     */
    removeErrorState(select) {
        select.classList.remove('template-error');
        
        const container = select.closest('.template-dropdown-container');
        const errorMsg = container.querySelector('.template-error-message');
        if (errorMsg) {
            errorMsg.remove();
        }
    }

    /**
     * Show template preview
     * @param {HTMLOptionElement} option - Option element being hovered
     * @param {string} category - Category name
     */
    async showTemplatePreview(option, category) {
        try {
            const templatePath = option.dataset.templatePath;
            const templateName = option.textContent;
            
            if (!templatePath) return;

            // Create or update preview tooltip
            let preview = document.getElementById('template-preview-tooltip');
            if (!preview) {
                preview = document.createElement('div');
                preview.id = 'template-preview-tooltip';
                preview.className = 'template-preview-tooltip';
                document.body.appendChild(preview);
            }

            // Show loading state
            preview.innerHTML = `
                <div class="template-preview-header">
                    <strong>${templateName}</strong>
                    <span class="template-preview-category">${category}</span>
                </div>
                <div class="template-preview-content">
                    <div class="template-preview-loading">
                        <div class="template-preview-spinner"></div>
                        Loading preview...
                    </div>
                </div>
            `;

            // Position tooltip
            this.positionPreviewTooltip(preview, option);
            preview.style.display = 'block';

            // Load template content (use a simple fetch for preview)
            try {
                const response = await fetch(templatePath);
                if (response.ok) {
                    const content = await response.text();
                    const previewContent = this.generatePreviewContent(content);
                    
                    preview.innerHTML = `
                        <div class="template-preview-header">
                            <strong>${templateName}</strong>
                            <span class="template-preview-category">${category}</span>
                        </div>
                        <div class="template-preview-content">
                            ${previewContent}
                        </div>
                        <div class="template-preview-footer">
                            <small>Click to select this template</small>
                        </div>
                    `;
                } else {
                    throw new Error('Failed to load template');
                }
            } catch (error) {
                preview.innerHTML = `
                    <div class="template-preview-header">
                        <strong>${templateName}</strong>
                        <span class="template-preview-category">${category}</span>
                    </div>
                    <div class="template-preview-content">
                        <div class="template-preview-error">
                            ⚠️ Preview unavailable
                        </div>
                    </div>
                `;
            }

        } catch (error) {
            console.warn('Error showing template preview:', error);
        }
    }

    /**
     * Hide template preview
     */
    hideTemplatePreview() {
        const preview = document.getElementById('template-preview-tooltip');
        if (preview) {
            preview.style.display = 'none';
        }
    }

    /**
     * Position preview tooltip relative to option
     * @param {HTMLElement} tooltip - Tooltip element
     * @param {HTMLElement} option - Option element
     */
    positionPreviewTooltip(tooltip, option) {
        const select = option.closest('select');
        if (!select) return;

        const rect = select.getBoundingClientRect();
        const scrollY = window.pageYOffset || document.documentElement.scrollTop;
        const scrollX = window.pageXOffset || document.documentElement.scrollLeft;

        // Position to the right of the dropdown
        tooltip.style.position = 'absolute';
        tooltip.style.left = (rect.right + scrollX + 10) + 'px';
        tooltip.style.top = (rect.top + scrollY) + 'px';
        tooltip.style.zIndex = '10001';

        // Adjust if tooltip would go off screen
        setTimeout(() => {
            const tooltipRect = tooltip.getBoundingClientRect();
            if (tooltipRect.right > window.innerWidth) {
                // Position to the left instead
                tooltip.style.left = (rect.left + scrollX - tooltipRect.width - 10) + 'px';
            }
            if (tooltipRect.bottom > window.innerHeight) {
                // Position higher
                tooltip.style.top = (rect.bottom + scrollY - tooltipRect.height) + 'px';
            }
        }, 0);
    }

    /**
     * Generate preview content from template
     * @param {string} content - Template content
     * @returns {string} Preview HTML
     */
    generatePreviewContent(content) {
        // Extract first few lines and key sections
        const lines = content.split('\n');
        const preview = [];
        let lineCount = 0;
        const maxLines = 8;

        for (const line of lines) {
            if (lineCount >= maxLines) break;
            
            const trimmed = line.trim();
            if (trimmed) {
                if (trimmed.startsWith('#')) {
                    // Header
                    const level = (trimmed.match(/^#+/) || [''])[0].length;
                    const text = trimmed.replace(/^#+\s*/, '');
                    preview.push(`<div class="preview-header preview-h${level}">${text}</div>`);
                } else if (trimmed.startsWith('-') || trimmed.startsWith('*')) {
                    // List item
                    const text = trimmed.replace(/^[-*]\s*/, '');
                    preview.push(`<div class="preview-list-item">• ${text}</div>`);
                } else if (trimmed.includes('{{') && trimmed.includes('}}')) {
                    // Placeholder line
                    preview.push(`<div class="preview-placeholder">${trimmed}</div>`);
                } else {
                    // Regular text
                    preview.push(`<div class="preview-text">${trimmed}</div>`);
                }
                lineCount++;
            }
        }

        if (lines.length > maxLines) {
            preview.push('<div class="preview-more">...</div>');
        }

        return preview.join('');
    }

    /**
     * Handle template search
     * @param {string} searchTerm - Search term
     * @param {Object} templateStructure - Full template structure
     */
    handleTemplateSearch(searchTerm, templateStructure) {
        const term = searchTerm.toLowerCase().trim();
        
        if (!term) {
            // Show all templates
            this.updateDropdowns(templateStructure);
            return;
        }

        // Filter templates based on search term
        const filteredStructure = {};
        
        Object.entries(templateStructure).forEach(([category, templates]) => {
            const filteredTemplates = templates.filter(template => 
                template.name.toLowerCase().includes(term) ||
                template.displayName.toLowerCase().includes(term) ||
                category.toLowerCase().includes(term)
            );
            
            if (filteredTemplates.length > 0) {
                filteredStructure[category] = filteredTemplates;
            }
        });

        // Update dropdowns with filtered results
        this.updateDropdowns(filteredStructure);
        
        // Highlight search results
        this.highlightSearchResults(term);
    }

    /**
     * Handle keyboard shortcuts in search
     * @param {KeyboardEvent} event - Keyboard event
     */
    handleSearchKeyboard(event) {
        switch (event.key) {
            case 'Escape':
                event.target.value = '';
                event.target.blur();
                // Reset to show all templates
                this.handleTemplateSearch('', this.originalTemplateStructure || {});
                break;
                
            case 'ArrowDown':
                event.preventDefault();
                this.focusFirstDropdown();
                break;
                
            case 'Enter':
                event.preventDefault();
                this.selectFirstSearchResult();
                break;
        }
    }

    /**
     * Focus the first dropdown
     */
    focusFirstDropdown() {
        const firstDropdown = document.querySelector('.template-dropdown-select');
        if (firstDropdown) {
            firstDropdown.focus();
        }
    }

    /**
     * Select the first search result
     */
    selectFirstSearchResult() {
        const firstDropdown = document.querySelector('.template-dropdown-select');
        if (firstDropdown && firstDropdown.options.length > 1) {
            firstDropdown.selectedIndex = 1; // Skip "Select a template..." option
            firstDropdown.dispatchEvent(new Event('change'));
        }
    }

    /**
     * Highlight search results
     * @param {string} searchTerm - Search term to highlight
     */
    highlightSearchResults(searchTerm) {
        if (!searchTerm) return;
        
        const dropdowns = document.querySelectorAll('.template-dropdown-select');
        dropdowns.forEach(select => {
            Array.from(select.options).forEach(option => {
                if (option.value && option.textContent.toLowerCase().includes(searchTerm.toLowerCase())) {
                    option.classList.add('search-highlighted');
                } else {
                    option.classList.remove('search-highlighted');
                }
            });
        });
    }

    /**
     * Store recently used templates
     * @param {Object} template - Template that was used
     */
    addToRecentlyUsed(template) {
        const storageKey = 'coa_recent_templates';
        let recent = [];
        
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) {
                recent = JSON.parse(stored);
            }
        } catch (error) {
            console.warn('Failed to load recent templates:', error);
        }
        
        // Remove if already exists
        recent = recent.filter(t => t.name !== template.name || t.category !== template.category);
        
        // Add to beginning
        recent.unshift({
            name: template.name,
            displayName: template.displayName,
            category: template.category,
            path: template.path,
            lastUsed: Date.now()
        });
        
        // Keep only last 5
        recent = recent.slice(0, 5);
        
        try {
            localStorage.setItem(storageKey, JSON.stringify(recent));
        } catch (error) {
            console.warn('Failed to save recent templates:', error);
        }
    }

    /**
     * Get recently used templates
     * @returns {Array} Recently used templates
     */
    getRecentlyUsed() {
        const storageKey = 'coa_recent_templates';
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) {
                const recent = JSON.parse(stored);
                // Filter out templates older than 7 days
                const weekAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
                return recent.filter(t => t.lastUsed > weekAgo);
            }
        } catch (error) {
            console.warn('Failed to load recent templates:', error);
        }
        return [];
    }

    /**
     * Add recently used section to dropdowns
     * @param {Object} templateStructure - Template structure
     * @returns {Object} Enhanced template structure with recent templates
     */
    addRecentlyUsedSection(templateStructure) {
        const recent = this.getRecentlyUsed();
        if (recent.length === 0) {
            return templateStructure;
        }

        const enhanced = { ...templateStructure };
        enhanced['📌 Recently Used'] = recent;
        
        return enhanced;
    }

    /**
     * Get dropdown statistics
     * @returns {Object} Statistics about dropdowns
     */
    getStats() {
        const totalDropdowns = this.dropdowns.size;
        let totalTemplates = 0;
        
        this.dropdowns.forEach((dropdown) => {
            const select = dropdown.querySelector('.template-dropdown-select');
            if (select) {
                // Subtract 1 for the "Select a template..." option
                totalTemplates += Math.max(0, select.options.length - 1);
            }
        });
        
        return {
            totalCategories: totalDropdowns,
            totalTemplates: totalTemplates,
            hasSelection: !!this.selectedTemplate,
            selectedCategory: this.selectedTemplate?.category || null,
            selectedTemplate: this.selectedTemplate?.name || null
        };
    }

    /**
     * Cleanup event handlers
     */
    destroy() {
        this.eventHandlers.forEach((handlers, element) => {
            if (typeof handlers === 'object') {
                // New format with multiple handlers
                Object.entries(handlers).forEach(([eventType, handler]) => {
                    element.removeEventListener(eventType, handler);
                });
            } else {
                // Legacy format with single handler
                element.removeEventListener('change', handlers);
            }
        });
        this.eventHandlers.clear();
        this.dropdowns.clear();
        this.selectedTemplate = null;
        this.onSelectionCallback = null;
    }
}

// Export for use in other modules
window.TemplateDropdownGenerator = TemplateDropdownGenerator;