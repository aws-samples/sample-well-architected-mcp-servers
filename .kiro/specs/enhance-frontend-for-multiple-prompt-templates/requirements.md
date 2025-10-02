# Requirements Document

## Introduction

This feature enhances the Cloud Optimization Assistant (COA) frontend to support multiple prompt templates using a simple folder-based structure. The system will automatically generate dropdown menus based on subfolders in the `prompt-templates` directory, with each Markdown file representing a selectable template. This approach provides a scalable, maintainable way to organize and access prompt templates for different AWS assessment scenarios.

## Requirements

### Requirement 1

**User Story:** As a user, I want to select from organized prompt templates via dropdown menus, so that I can quickly access relevant assessment prompts without manual navigation.

#### Acceptance Criteria

1. WHEN the frontend loads THEN the system SHALL scan the `prompt-templates` folder for subfolders
2. WHEN subfolders are found THEN the system SHALL create a dropdown menu for each subfolder (e.g., "Security", "Cost Optimization")
3. WHEN a dropdown is opened THEN the system SHALL display all `.md` files in that subfolder as selectable options
4. WHEN a template is selected THEN the system SHALL load the Markdown file content and populate the chat input

### Requirement 2

**User Story:** As a system administrator, I want to add new template categories by creating folders, so that the system automatically recognizes and displays them without code changes.

#### Acceptance Criteria

1. WHEN a new subfolder is added to `prompt-templates` THEN the system SHALL automatically create a new dropdown menu with the folder name
2. WHEN `.md` files are added to any subfolder THEN the system SHALL automatically include them in the corresponding dropdown
3. WHEN the frontend is refreshed THEN the system SHALL reflect any folder structure changes
4. IF a subfolder is empty THEN the system SHALL still display the dropdown but show "No templates available"

### Requirement 3

**User Story:** As a security analyst, I want to access security-specific templates from a dedicated dropdown, so that I can quickly find relevant security assessment prompts.

#### Acceptance Criteria

1. WHEN the `prompt-templates/Security` folder exists THEN the system SHALL create a "Security" dropdown menu
2. WHEN the Security dropdown is opened THEN the system SHALL display templates like "Security Services.md" and "Check Network Encryption.md"
3. WHEN a security template is selected THEN the system SHALL load the template content into the chat input
4. WHEN the template is loaded THEN the system SHALL preserve the original Markdown formatting as plain text

### Requirement 4

**User Story:** As a cost optimization specialist, I want future cost optimization templates to be automatically available, so that new assessment types are immediately accessible.

#### Acceptance Criteria

1. WHEN a `prompt-templates/Cost Optimization` folder is created THEN the system SHALL automatically generate a "Cost Optimization" dropdown
2. WHEN cost templates like "Scan for saving plans options.md" are added THEN the system SHALL include them in the dropdown
3. WHEN new template categories are added THEN the system SHALL maintain existing functionality for all categories
4. IF template files are renamed or moved THEN the system SHALL reflect changes on next page load

### Requirement 5

**User Story:** As a user, I want the template selection interface to be intuitive and non-intrusive, so that I can choose to use templates or free-form input seamlessly.

#### Acceptance Criteria

1. WHEN the chat interface loads THEN the system SHALL display template dropdowns in a clear, accessible location
2. WHEN no template is selected THEN the system SHALL allow normal free-form chat input as currently implemented
3. WHEN a template is selected THEN the system SHALL populate the input field but allow further editing before submission
4. WHEN the user clears the input THEN the system SHALL return to normal free-form input mode

### Requirement 6

**User Story:** As a developer, I want the template system to handle errors gracefully, so that missing or malformed templates don't break the chat interface.

#### Acceptance Criteria

1. WHEN the `prompt-templates` folder doesn't exist THEN the system SHALL continue normal operation without template dropdowns
2. WHEN a template file cannot be loaded THEN the system SHALL show an error message and continue functioning
3. WHEN template files contain invalid content THEN the system SHALL load them as plain text
4. IF the template loading fails THEN the system SHALL log errors to the console for debugging