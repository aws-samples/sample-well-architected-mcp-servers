#!/usr/bin/env node

/**
 * Template Index Updater
 * 
 * This script helps maintain the index.json file by scanning the prompt-templates
 * directory and automatically updating the index with new templates.
 * 
 * Usage:
 *   node update-index.js
 *   node update-index.js --scan-only  (just show what would be updated)
 */

const fs = require('fs');
const path = require('path');

class TemplateIndexUpdater {
    constructor() {
        this.baseDir = __dirname;
        this.indexPath = path.join(this.baseDir, 'index.json');
    }

    /**
     * Scan directories and update index.json
     */
    async updateIndex(scanOnly = false) {
        try {
            console.log('🔍 Scanning prompt-templates directory...');
            
            // Load existing index
            let existingIndex = {};
            if (fs.existsSync(this.indexPath)) {
                existingIndex = JSON.parse(fs.readFileSync(this.indexPath, 'utf8'));
            }

            // Scan directories
            const scannedStructure = await this.scanDirectories();
            
            // Merge with existing index
            const updatedIndex = this.mergeIndexes(existingIndex, scannedStructure);
            
            if (scanOnly) {
                console.log('📋 Scan results (no changes made):');
                console.log(JSON.stringify(updatedIndex, null, 2));
                return;
            }

            // Write updated index
            fs.writeFileSync(this.indexPath, JSON.stringify(updatedIndex, null, 2));
            
            console.log('✅ Index updated successfully!');
            console.log(`📊 Categories: ${Object.keys(updatedIndex.categories).length}`);
            
            let totalTemplates = 0;
            let totalSubcategories = 0;
            
            for (const [categoryName, categoryData] of Object.entries(updatedIndex.categories)) {
                totalTemplates += categoryData.templates?.length || 0;
                
                if (categoryData.subcategories) {
                    const subCatCount = Object.keys(categoryData.subcategories).length;
                    totalSubcategories += subCatCount;
                    
                    for (const subCategoryData of Object.values(categoryData.subcategories)) {
                        totalTemplates += subCategoryData.templates?.length || 0;
                    }
                    
                    console.log(`  📁 ${categoryName}: ${categoryData.templates?.length || 0} templates, ${subCatCount} subcategories`);
                } else {
                    console.log(`  📁 ${categoryName}: ${categoryData.templates?.length || 0} templates`);
                }
            }
            
            console.log(`📄 Total templates: ${totalTemplates}`);
            if (totalSubcategories > 0) {
                console.log(`📂 Total subcategories: ${totalSubcategories}`);
            }

        } catch (error) {
            console.error('❌ Error updating index:', error);
            process.exit(1);
        }
    }

    /**
     * Scan directories for templates (recursive)
     */
    async scanDirectories() {
        const categories = {};
        
        // Recursively scan all directories
        await this.scanDirectoryRecursive(this.baseDir, '', categories);

        return {
            version: "1.0.0",
            lastUpdated: new Date().toISOString(),
            categories
        };
    }

    /**
     * Recursively scan directory for templates
     */
    async scanDirectoryRecursive(currentPath, relativePath, categories) {
        const items = fs.readdirSync(currentPath, { withFileTypes: true });
        
        // First, collect all .md files in current directory
        const mdFiles = items
            .filter(item => item.isFile() && item.name.endsWith('.md'))
            .map(item => item.name);

        // If we have .md files, create/update category
        if (mdFiles.length > 0) {
            const categoryKey = relativePath || 'Root';
            const templates = [];

            for (const file of mdFiles) {
                const filePath = path.join(currentPath, file);
                const stats = fs.statSync(filePath);
                
                const templateName = file.replace('.md', '');
                
                templates.push({
                    name: templateName,
                    displayName: this.generateDisplayName(templateName),
                    filename: file,
                    path: relativePath, // Store the relative path for nested templates
                    description: await this.extractDescription(filePath),
                    lastModified: stats.mtime.toISOString()
                });
            }

            // Create category structure for nested paths
            if (relativePath) {
                const pathParts = relativePath.split('/');
                const mainCategory = pathParts[0];
                const subCategory = pathParts.slice(1).join('/');

                if (!categories[mainCategory]) {
                    categories[mainCategory] = {
                        displayName: mainCategory,
                        description: this.generateCategoryDescription(mainCategory),
                        templates: [],
                        subcategories: {}
                    };
                }

                if (subCategory) {
                    // This is a nested template - add to subcategory
                    if (!categories[mainCategory].subcategories[subCategory]) {
                        categories[mainCategory].subcategories[subCategory] = {
                            displayName: subCategory,
                            description: this.generateCategoryDescription(subCategory),
                            templates: []
                        };
                    }
                    categories[mainCategory].subcategories[subCategory].templates.push(...templates);
                } else {
                    // This is a top-level template in the main category
                    categories[mainCategory].templates.push(...templates);
                }
            } else {
                // Root level templates (shouldn't happen in our structure, but handle it)
                if (!categories['Root']) {
                    categories['Root'] = {
                        displayName: 'Root Templates',
                        description: 'Root level templates',
                        templates: []
                    };
                }
                categories['Root'].templates.push(...templates);
            }
        }

        // Then, recursively scan subdirectories
        const directories = items
            .filter(item => item.isDirectory() && !item.name.startsWith('.'))
            .map(item => item.name);

        for (const dirName of directories) {
            const dirPath = path.join(currentPath, dirName);
            const newRelativePath = relativePath ? `${relativePath}/${dirName}` : dirName;
            
            await this.scanDirectoryRecursive(dirPath, newRelativePath, categories);
        }

        // Sort templates in each category and subcategory
        for (const category of Object.values(categories)) {
            if (category.templates) {
                category.templates.sort((a, b) => a.displayName.localeCompare(b.displayName));
            }
            if (category.subcategories) {
                for (const subcategory of Object.values(category.subcategories)) {
                    if (subcategory.templates) {
                        subcategory.templates.sort((a, b) => a.displayName.localeCompare(b.displayName));
                    }
                }
            }
        }
    }

    /**
     * Merge existing index with scanned structure
     */
    mergeIndexes(existing, scanned) {
        const merged = {
            version: scanned.version,
            lastUpdated: scanned.lastUpdated,
            categories: {}
        };

        // Start with scanned categories
        for (const [categoryName, categoryData] of Object.entries(scanned.categories)) {
            merged.categories[categoryName] = { ...categoryData };
            
            // If category exists in existing index, preserve custom descriptions
            if (existing.categories && existing.categories[categoryName]) {
                const existingCategory = existing.categories[categoryName];
                
                // Preserve custom category description
                if (existingCategory.description && 
                    existingCategory.description !== this.generateCategoryDescription(categoryName)) {
                    merged.categories[categoryName].description = existingCategory.description;
                }

                // Preserve custom template descriptions for main category templates
                if (merged.categories[categoryName].templates) {
                    for (const template of merged.categories[categoryName].templates) {
                        const existingTemplate = existingCategory.templates?.find(t => t.name === template.name);
                        if (existingTemplate && existingTemplate.description && 
                            existingTemplate.description !== template.description) {
                            template.description = existingTemplate.description;
                        }
                    }
                }

                // Preserve custom descriptions for subcategories and their templates
                if (merged.categories[categoryName].subcategories && existingCategory.subcategories) {
                    for (const [subCategoryName, subCategoryData] of Object.entries(merged.categories[categoryName].subcategories)) {
                        const existingSubCategory = existingCategory.subcategories[subCategoryName];
                        
                        if (existingSubCategory) {
                            // Preserve custom subcategory description
                            if (existingSubCategory.description && 
                                existingSubCategory.description !== this.generateCategoryDescription(subCategoryName)) {
                                subCategoryData.description = existingSubCategory.description;
                            }

                            // Preserve custom template descriptions in subcategory
                            if (subCategoryData.templates) {
                                for (const template of subCategoryData.templates) {
                                    const existingTemplate = existingSubCategory.templates?.find(t => t.name === template.name);
                                    if (existingTemplate && existingTemplate.description && 
                                        existingTemplate.description !== template.description) {
                                        template.description = existingTemplate.description;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        return merged;
    }

    /**
     * Generate display name from template name
     */
    generateDisplayName(templateName) {
        return templateName
            .split(/[-_\s]+/)
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    /**
     * Generate category description
     */
    generateCategoryDescription(categoryName) {
        const descriptions = {
            'Security': 'AWS security assessment and compliance templates',
            'Cost Optimization': 'AWS cost optimization and savings analysis templates',
            'Performance': 'AWS performance optimization and monitoring templates',
            'Reliability': 'AWS reliability and resilience assessment templates',
            'Operational Excellence': 'AWS operational excellence and best practices templates'
        };

        return descriptions[categoryName] || `${categoryName} analysis and assessment templates`;
    }

    /**
     * Extract description from template file
     */
    async extractDescription(filePath) {
        try {
            const content = fs.readFileSync(filePath, 'utf8');
            
            // Look for description in various formats
            const lines = content.split('\n').slice(0, 10); // Check first 10 lines
            
            for (const line of lines) {
                const trimmed = line.trim();
                
                // Look for description patterns
                if (trimmed.startsWith('Description:') || trimmed.startsWith('## Description')) {
                    return trimmed.replace(/^(Description:|## Description)\s*/, '');
                }
                
                // Look for first paragraph after title
                if (trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('---') && trimmed.length > 20) {
                    return trimmed.length > 100 ? trimmed.substring(0, 97) + '...' : trimmed;
                }
            }
            
            // Fallback: generate from filename
            const filename = path.basename(filePath, '.md');
            return `${this.generateDisplayName(filename)} analysis and recommendations`;
            
        } catch (error) {
            console.warn(`Could not extract description from ${filePath}:`, error.message);
            return 'Template analysis and recommendations';
        }
    }
}

// CLI execution
if (require.main === module) {
    const scanOnly = process.argv.includes('--scan-only');
    const updater = new TemplateIndexUpdater();
    updater.updateIndex(scanOnly);
}

module.exports = TemplateIndexUpdater;