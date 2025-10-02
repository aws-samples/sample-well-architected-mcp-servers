# Design Document

## Overview

This design implements a folder-based prompt template system for the Cloud Optimization Assistant frontend. The system automatically generates dropdown menus based on the directory structure in `prompt-templates/`, where each subfolder becomes a dropdown category and each Markdown file becomes a selectable template. This approach provides a scalable, maintainable solution that requires no code changes when adding new template categories.

## Architecture

### High-Level Architecture

```
Frontend (JavaScript)
├── Template Discovery Service
│   ├── Folder Scanner
│   ├── Template Loader
│   └── Cache Manager
├── UI Components
│   ├── Template Dropdown Generator
│   ├── Template Selector
│   └── Chat Input Integration
└── Template Processing
    ├── Markdown Parser
    ├── Content Validator
    └── Error Handler

Backend (FastAPI) - Optional Enhancement
├── Template API Endpoint
├── File System Monitor
└── Template Metadata Service
```

### Directory Structure

```
prompt-templates/
├── Security/
│   ├── Security Services.md
│   ├── Check Network Encryption.md
│   └── Storage Encryption Analysis.md
├── Cost Optimization/
│   ├── Scan for saving plans options.md
│   ├── Insights from Compute Optimizer.md
│   └── Reserved Instance Analysis.md
├── Performance/
│   ├── CloudWatch Metrics Review.md
│   └── Application Performance Analysis.md
└── Reliability/
    ├── Multi-AZ Configuration Check.md
    └── Backup Strategy Review.md
```

## Components and Interfaces

### 1. Template Discovery Service

**Purpose**: Automatically discover and load template structure from the file system.

**Key Methods**:
- `scanTemplateDirectory()`: Scans prompt-templates folder for subfolders and files
- `loadTemplateContent(path)`: Loads individual template Markdown content
- `getCachedTemplates()`: Returns cached template structure
- `refreshTemplates()`: Forces refresh of template cache

**Interface**:
```javascript
class TemplateDiscoveryService {
    async scanTemplateDirectory(): Promise<TemplateStructure>
    async loadTemplateContent(categoryPath: string, templateName: string): Promise<string>
    getCachedTemplates(): TemplateStructure | null
    refreshTemplates(): Promise<void>
}

interface TemplateStructure {
    [category: string]: TemplateFile[]
}

interface TemplateFile {
    name: string;
    displayName: string;
    path: string;
    lastModified?: Date;
}
```

### 2. Template Dropdown Generator

**Purpose**: Dynamically creates dropdown UI elements based on discovered template structure.

**Key Methods**:
- `generateDropdowns(templateStructure)`: Creates dropdown elements for each category
- `populateDropdown(category, templates)`: Populates individual dropdown with templates
- `attachEventHandlers()`: Attaches click and selection event handlers

**Interface**:
```javascript
class TemplateDropdownGenerator {
    generateDropdowns(templateStructure: TemplateStructure): HTMLElement[]
    populateDropdown(category: string, templates: TemplateFile[]): HTMLSelectElement
    attachEventHandlers(dropdowns: HTMLElement[]): void
    onTemplateSelected(callback: (category: string, template: TemplateFile) => void): void
}
```

### 3. Template Selector Component

**Purpose**: Manages template selection UI and integration with chat input.

**Key Methods**:
- `renderTemplateSelector()`: Renders the complete template selection interface
- `handleTemplateSelection()`: Processes template selection and loads content
- `populateChatInput()`: Populates chat input with selected template content
- `clearSelection()`: Resets template selection state

**Interface**:
```javascript
class TemplateSelector {
    renderTemplateSelector(container: HTMLElement): void
    handleTemplateSelection(category: string, template: TemplateFile): Promise<void>
    populateChatInput(content: string): void
    clearSelection(): void
    onSelectionChange(callback: (template: TemplateFile | null) => void): void
}
```

### 4. Backend Template API (Optional Enhancement)

**Purpose**: Provides server-side template management and metadata.

**Endpoints**:
- `GET /api/templates/structure`: Returns template directory structure
- `GET /api/templates/{category}/{template}`: Returns specific template content
- `GET /api/templates/metadata`: Returns template metadata and statistics

**Interface**:
```python
@app.get("/api/templates/structure")
async def get_template_structure() -> Dict[str, List[TemplateInfo]]

@app.get("/api/templates/{category}/{template}")
async def get_template_content(category: str, template: str) -> TemplateContent

class TemplateInfo(BaseModel):
    name: str
    display_name: str
    path: str
    last_modified: Optional[datetime]
    size: Optional[int]

class TemplateContent(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]]
```

## Data Models

### Template Structure Model

```javascript
interface TemplateStructure {
    [category: string]: TemplateFile[]
}

interface TemplateFile {
    name: string;           // File name without extension
    displayName: string;    // Human-readable name for UI
    path: string;          // Full path to template file
    lastModified?: Date;   // File modification date
    size?: number;         // File size in bytes
    metadata?: TemplateMetadata;
}

interface TemplateMetadata {
    title?: string;
    description?: string;
    tags?: string[];
    compliance?: string[];
    estimatedDuration?: string;
}
```

### UI State Model

```javascript
interface TemplateUIState {
    selectedCategory: string | null;
    selectedTemplate: TemplateFile | null;
    dropdownsVisible: boolean;
    loadingTemplate: boolean;
    error: string | null;
}

interface TemplateCache {
    structure: TemplateStructure;
    lastUpdated: Date;
    contentCache: Map<string, string>;
}
```

## Error Handling

### Error Categories

1. **File System Errors**
   - Template directory not found
   - Template file not readable
   - Invalid file permissions

2. **Content Errors**
   - Malformed Markdown content
   - Empty template files
   - Invalid file encoding

3. **UI Errors**
   - Dropdown generation failures
   - Event handler attachment issues
   - Chat input integration problems

### Error Handling Strategy

```javascript
class TemplateErrorHandler {
    handleFileSystemError(error: Error, path: string): void {
        console.warn(`Template file system error at ${path}:`, error);
        // Continue operation without failing completely
        this.showUserNotification('Some templates may not be available');
    }

    handleContentError(error: Error, template: TemplateFile): void {
        console.warn(`Template content error for ${template.name}:`, error);
        // Load template as plain text fallback
        this.loadAsPlainText(template);
    }

    handleUIError(error: Error, component: string): void {
        console.error(`UI error in ${component}:`, error);
        // Graceful degradation to free-form input
        this.enableFreeFormMode();
    }
}
```

## Testing Strategy

### Unit Tests

1. **Template Discovery Service Tests**
   - Test folder scanning with various directory structures
   - Test template loading with different file types
   - Test caching behavior and cache invalidation
   - Test error handling for missing directories/files

2. **UI Component Tests**
   - Test dropdown generation with different template structures
   - Test template selection and chat input population
   - Test event handler attachment and cleanup
   - Test responsive behavior and accessibility

3. **Integration Tests**
   - Test complete template selection workflow
   - Test integration with existing chat functionality
   - Test error recovery and graceful degradation
   - Test performance with large numbers of templates

### Test Data Structure

```javascript
// Test template structure
const mockTemplateStructure = {
    "Security": [
        { name: "security-services", displayName: "Security Services", path: "Security/Security Services.md" },
        { name: "network-encryption", displayName: "Check Network Encryption", path: "Security/Check Network Encryption.md" }
    ],
    "Cost Optimization": [
        { name: "savings-plans", displayName: "Scan for saving plans options", path: "Cost Optimization/Scan for saving plans options.md" }
    ]
};
```

### Performance Considerations

1. **Template Caching**
   - Cache template structure in browser localStorage
   - Implement cache invalidation based on last modified dates
   - Lazy load template content only when selected

2. **UI Optimization**
   - Use document fragments for efficient DOM manipulation
   - Implement virtual scrolling for large template lists
   - Debounce template loading operations

3. **Memory Management**
   - Clear unused template content from memory
   - Implement LRU cache for frequently accessed templates
   - Monitor memory usage in browser developer tools

## Implementation Phases

### Phase 1: Core Template System
- Implement template discovery service
- Create basic dropdown UI components
- Integrate with existing chat input
- Add error handling and logging

### Phase 2: Enhanced UI Features
- Add template preview functionality
- Implement template search and filtering
- Add keyboard navigation support
- Enhance accessibility features

### Phase 3: Advanced Features
- Add template metadata support
- Implement template caching optimization
- Add backend API for template management
- Support for template versioning

### Phase 4: User Experience Enhancements
- Add template usage analytics
- Implement user preferences for template ordering
- Add template sharing and export features
- Support for custom user templates