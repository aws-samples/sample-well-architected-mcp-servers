/**
 * Template Processor
 * Handles template content processing including placeholder replacement
 */
class TemplateProcessor {
    constructor() {
        this.placeholderPattern = /\{\{([^}]+)\}\}/g;
        this.commonPlaceholders = {
            'account_id': () => this.getAwsAccountId(),
            'region': () => this.getAwsRegion(),
            'environment': () => this.getEnvironment(),
            'budget_range': () => this.getBudgetRange(),
            'compliance_framework': () => this.getComplianceFramework(),
            'criticality_level': () => this.getCriticalityLevel(),
            'workload_type': () => this.getWorkloadType(),
            'performance_sla': () => this.getPerformanceSla()
        };
    }

    /**
     * Process template content and replace placeholders
     * @param {string} content - Template content
     * @param {Object} customValues - Custom placeholder values
     * @returns {Promise<string>} Processed content
     */
    async processTemplate(content, customValues = {}) {
        if (!content) return content;

        console.log('Processing template content...');
        
        // Find all placeholders
        const placeholders = this.extractPlaceholders(content);
        
        if (placeholders.length === 0) {
            return content;
        }

        console.log('Found placeholders:', placeholders);
        
        // Get values for placeholders
        const values = await this.getPlaceholderValues(placeholders, customValues);
        
        // Replace placeholders with values
        let processedContent = content;
        for (const [placeholder, value] of Object.entries(values)) {
            const regex = new RegExp(`\\{\\{${placeholder}\\}\\}`, 'g');
            processedContent = processedContent.replace(regex, value);
        }
        
        return processedContent;
    }

    /**
     * Extract placeholders from template content
     * @param {string} content - Template content
     * @returns {Array<string>} Array of placeholder names
     */
    extractPlaceholders(content) {
        const placeholders = [];
        let match;
        
        while ((match = this.placeholderPattern.exec(content)) !== null) {
            const placeholder = match[1].trim();
            if (!placeholders.includes(placeholder)) {
                placeholders.push(placeholder);
            }
        }
        
        return placeholders;
    }

    /**
     * Get values for placeholders
     * @param {Array<string>} placeholders - Array of placeholder names
     * @param {Object} customValues - Custom values provided by user
     * @returns {Promise<Object>} Object with placeholder values
     */
    async getPlaceholderValues(placeholders, customValues = {}) {
        const values = {};
        
        for (const placeholder of placeholders) {
            // Check custom values first
            if (customValues[placeholder] !== undefined) {
                values[placeholder] = customValues[placeholder];
                continue;
            }
            
            // Check common placeholders
            if (this.commonPlaceholders[placeholder]) {
                try {
                    values[placeholder] = await this.commonPlaceholders[placeholder]();
                } catch (error) {
                    console.warn(`Failed to get value for placeholder ${placeholder}:`, error);
                    values[placeholder] = `{{${placeholder}}}`;
                }
                continue;
            }
            
            // Prompt user for unknown placeholders
            values[placeholder] = await this.promptForPlaceholder(placeholder);
        }
        
        return values;
    }

    /**
     * Prompt user for placeholder value
     * @param {string} placeholder - Placeholder name
     * @returns {Promise<string>} User-provided value
     */
    async promptForPlaceholder(placeholder) {
        return new Promise((resolve) => {
            const modal = this.createPlaceholderModal(placeholder, resolve);
            document.body.appendChild(modal);
        });
    }

    /**
     * Create modal for placeholder input
     * @param {string} placeholder - Placeholder name
     * @param {Function} resolve - Promise resolve function
     * @returns {HTMLElement} Modal element
     */
    createPlaceholderModal(placeholder, resolve) {
        const modal = document.createElement('div');
        modal.className = 'placeholder-modal-overlay';
        
        const displayName = this.getPlaceholderDisplayName(placeholder);
        const description = this.getPlaceholderDescription(placeholder);
        
        modal.innerHTML = `
            <div class="placeholder-modal">
                <div class="placeholder-modal-header">
                    <h3>Template Parameter Required</h3>
                    <button class="placeholder-modal-close" type="button">×</button>
                </div>
                <div class="placeholder-modal-body">
                    <label for="placeholder-input">${displayName}:</label>
                    <input type="text" id="placeholder-input" placeholder="Enter ${displayName.toLowerCase()}" />
                    <small class="placeholder-description">${description}</small>
                </div>
                <div class="placeholder-modal-footer">
                    <button class="placeholder-btn placeholder-btn-cancel" type="button">Skip</button>
                    <button class="placeholder-btn placeholder-btn-confirm" type="button">Confirm</button>
                </div>
            </div>
        `;
        
        // Add event handlers
        const input = modal.querySelector('#placeholder-input');
        const confirmBtn = modal.querySelector('.placeholder-btn-confirm');
        const cancelBtn = modal.querySelector('.placeholder-btn-cancel');
        const closeBtn = modal.querySelector('.placeholder-modal-close');
        
        const handleConfirm = () => {
            const value = input.value.trim() || `{{${placeholder}}}`;
            modal.remove();
            resolve(value);
        };
        
        const handleCancel = () => {
            modal.remove();
            resolve(`{{${placeholder}}}`);
        };
        
        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
        closeBtn.addEventListener('click', handleCancel);
        
        // Handle Enter key
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleConfirm();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                handleCancel();
            }
        });
        
        // Focus input after modal is added
        setTimeout(() => input.focus(), 100);
        
        return modal;
    }

    /**
     * Get display name for placeholder
     * @param {string} placeholder - Placeholder name
     * @returns {string} Display name
     */
    getPlaceholderDisplayName(placeholder) {
        const displayNames = {
            'account_id': 'AWS Account ID',
            'region': 'AWS Region',
            'environment': 'Environment Type',
            'budget_range': 'Monthly Budget Range',
            'compliance_framework': 'Compliance Framework',
            'criticality_level': 'Business Criticality Level',
            'workload_type': 'Workload Type',
            'performance_sla': 'Performance SLA Requirements'
        };
        
        return displayNames[placeholder] || placeholder.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    /**
     * Get description for placeholder
     * @param {string} placeholder - Placeholder name
     * @returns {string} Description
     */
    getPlaceholderDescription(placeholder) {
        const descriptions = {
            'account_id': 'Your 12-digit AWS Account ID (e.g., 123456789012)',
            'region': 'AWS region to analyze (e.g., us-east-1, eu-west-1)',
            'environment': 'Environment type (e.g., production, staging, development)',
            'budget_range': 'Monthly AWS spending range (e.g., $1000-5000)',
            'compliance_framework': 'Applicable compliance standards (e.g., SOC 2, PCI DSS, HIPAA)',
            'criticality_level': 'Business criticality (e.g., critical, high, medium, low)',
            'workload_type': 'Type of workload (e.g., web application, data processing, ML)',
            'performance_sla': 'Performance requirements (e.g., 99.9% uptime, <100ms latency)'
        };
        
        return descriptions[placeholder] || `Please provide a value for ${placeholder}`;
    }

    /**
     * Get AWS Account ID from UI or storage
     * @returns {string} AWS Account ID
     */
    getAwsAccountId() {
        const input = document.getElementById('awsAccountId');
        if (input && input.value.trim()) {
            return input.value.trim();
        }
        
        // Try to get from localStorage
        const stored = localStorage.getItem('aws_account_id');
        if (stored) {
            return stored;
        }
        
        return '{{account_id}}';
    }

    /**
     * Get AWS Region from configuration or default
     * @returns {string} AWS Region
     */
    getAwsRegion() {
        // Try to get from app config
        if (window.APP_CONFIG && window.APP_CONFIG.aws && window.APP_CONFIG.aws.region) {
            return window.APP_CONFIG.aws.region;
        }
        
        // Default to us-east-1
        return 'us-east-1';
    }

    /**
     * Get environment type
     * @returns {string} Environment type
     */
    getEnvironment() {
        // Try to detect from account ID or other indicators
        const accountId = this.getAwsAccountId();
        if (accountId && accountId !== '{{account_id}}') {
            // Simple heuristic - could be enhanced
            if (accountId.endsWith('001') || accountId.endsWith('000')) {
                return 'production';
            } else if (accountId.endsWith('002') || accountId.endsWith('999')) {
                return 'staging';
            }
        }
        
        return '{{environment}}';
    }

    /**
     * Get budget range
     * @returns {string} Budget range
     */
    getBudgetRange() {
        return '{{budget_range}}';
    }

    /**
     * Get compliance framework
     * @returns {string} Compliance framework
     */
    getComplianceFramework() {
        return '{{compliance_framework}}';
    }

    /**
     * Get criticality level
     * @returns {string} Criticality level
     */
    getCriticalityLevel() {
        return '{{criticality_level}}';
    }

    /**
     * Get workload type
     * @returns {string} Workload type
     */
    getWorkloadType() {
        return '{{workload_type}}';
    }

    /**
     * Get performance SLA
     * @returns {string} Performance SLA
     */
    getPerformanceSla() {
        return '{{performance_sla}}';
    }

    /**
     * Check if content has placeholders
     * @param {string} content - Content to check
     * @returns {boolean} True if content has placeholders
     */
    hasPlaceholders(content) {
        return this.placeholderPattern.test(content);
    }

    /**
     * Get placeholder modal styles
     * @returns {string} CSS styles
     */
    static getModalStyles() {
        return `
            .placeholder-modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                backdrop-filter: blur(4px);
            }
            
            .placeholder-modal {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
                max-width: 500px;
                width: 90%;
                max-height: 90vh;
                overflow: hidden;
            }
            
            .placeholder-modal-header {
                padding: 20px 24px 16px;
                border-bottom: 1px solid #e0e0e0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .placeholder-modal-header h3 {
                margin: 0;
                color: #232F3E;
                font-size: 18px;
            }
            
            .placeholder-modal-close {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #6c757d;
                padding: 0;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 6px;
            }
            
            .placeholder-modal-close:hover {
                background: rgba(220, 53, 69, 0.1);
                color: #dc3545;
            }
            
            .placeholder-modal-body {
                padding: 24px;
            }
            
            .placeholder-modal-body label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #232F3E;
            }
            
            .placeholder-modal-body input {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
                margin-bottom: 8px;
            }
            
            .placeholder-modal-body input:focus {
                outline: none;
                border-color: #FF9900;
                box-shadow: 0 0 0 3px rgba(255, 153, 0, 0.1);
            }
            
            .placeholder-description {
                color: #6c757d;
                font-size: 14px;
                line-height: 1.4;
            }
            
            .placeholder-modal-footer {
                padding: 16px 24px 24px;
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }
            
            .placeholder-btn {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .placeholder-btn-cancel {
                background: #f8f9fa;
                color: #6c757d;
                border: 1px solid #e0e0e0;
            }
            
            .placeholder-btn-cancel:hover {
                background: #e9ecef;
                color: #495057;
            }
            
            .placeholder-btn-confirm {
                background: linear-gradient(135deg, #FF9900 0%, #FF6600 100%);
                color: white;
            }
            
            .placeholder-btn-confirm:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(255, 153, 0, 0.3);
            }
        `;
    }
}

// Add modal styles to document
const modalStyles = document.createElement('style');
modalStyles.textContent = TemplateProcessor.getModalStyles();
document.head.appendChild(modalStyles);

// Export for use in other modules
window.TemplateProcessor = TemplateProcessor;