# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Utilities for working with prompt templates."""

import os
import re
from typing import Any, Dict, List, Optional

from loguru import logger

# Cache for prompt templates
_prompt_templates = {}
_is_initialized = False


def load_prompt_templates(file_path: str = "PROMPT_TEMPLATE.md") -> Dict[str, Dict[str, Any]]:
    """Load prompt templates from a markdown file.

    Args:
        file_path: Path to the markdown file containing prompt templates

    Returns:
        Dictionary mapping template names to template content and metadata
    """
    global _prompt_templates, _is_initialized

    if _is_initialized:
        return _prompt_templates

    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Prompt template file not found: {file_path}")
            return {}

        # Read the file content
        with open(file_path, "r") as f:
            content = f.read()

        # Parse the markdown content to extract templates
        # First, split by level 2 headers (## )
        sections = re.split(r"(?m)^## ", content)

        # The first section is the introduction, skip it
        if sections and not sections[0].startswith("## "):
            sections = sections[1:]

        # Process each section
        for section in sections:
            if not section.strip():
                continue

            # Extract the section title (template name)
            lines = section.split("\n")
            title = lines[0].strip()

            # Convert title to a template name (lowercase, underscores)
            template_name = title.lower().replace(" ", "_")

            # Extract the template content (between triple backticks)
            template_content = ""
            description = ""
            in_code_block = False
            desc_lines = []

            for line in lines[1:]:
                if line.strip() == "```":
                    in_code_block = not in_code_block
                    continue

                if in_code_block:
                    template_content += line + "\n"
                elif line.strip() and not in_code_block:
                    desc_lines.append(line.strip())

            # Join description lines
            if desc_lines:
                description = " ".join(desc_lines)

            # Store the template
            _prompt_templates[template_name] = {
                "name": template_name,
                "title": title,
                "content": template_content.strip(),
                "description": description,
            }

        # Special handling for the workflow example section
        workflow_section = None
        for section in content.split("## "):
            if section.startswith("Example Workflow"):
                workflow_section = section
                break

        if workflow_section:
            _prompt_templates["workflow_example"] = {
                "name": "workflow_example",
                "title": "Example Workflow",
                "content": workflow_section.split("Example Workflow")[1].strip(),
                "description": "Recommended workflow for a comprehensive security assessment",
            }

        _is_initialized = True
        logger.info(f"Loaded {len(_prompt_templates)} prompt templates from {file_path}")
        return _prompt_templates

    except Exception as e:
        logger.error(f"Error loading prompt templates: {e}")
        return {}


def get_prompt_template(template_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific prompt template by name.

    Args:
        template_name: Name of the template to retrieve

    Returns:
        Template dictionary or None if not found
    """
    global _prompt_templates, _is_initialized

    if not _is_initialized:
        load_prompt_templates()

    return _prompt_templates.get(template_name)


def get_all_template_names() -> List[str]:
    """Get a list of all available template names.

    Returns:
        List of template names
    """
    global _prompt_templates, _is_initialized

    if not _is_initialized:
        load_prompt_templates()

    return list(_prompt_templates.keys())


def get_template_metadata() -> List[Dict[str, str]]:
    """Get metadata for all available templates.

    Returns:
        List of dictionaries with template metadata
    """
    global _prompt_templates, _is_initialized

    if not _is_initialized:
        load_prompt_templates()

    return [
        {
            "name": template["name"],
            "title": template["title"],
            "description": template["description"],
        }
        for template in _prompt_templates.values()
    ]
