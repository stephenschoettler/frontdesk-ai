import os
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages system prompt templates stored in the templates/ directory."""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = templates_dir
        self._templates_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def _load_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load all template files from the templates directory."""
        if self._templates_cache is not None:
            return self._templates_cache

        templates = {}

        if not os.path.exists(self.templates_dir):
            logger.warning(f"Templates directory {self.templates_dir} does not exist")
            return templates

        for filename in os.listdir(self.templates_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.templates_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)

                        # Validate required fields
                        if 'name' not in template_data or 'system_prompt' not in template_data:
                            logger.warning(f"Template {filename} missing required fields")
                            continue

                        # Use filename without extension as key
                        template_key = filename[:-5]  # Remove .json
                        templates[template_key] = template_data

                        logger.info(f"Loaded template: {template_data['name']}")

                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Error loading template {filename}: {e}")

        self._templates_cache = templates
        return templates

    def get_template(self, template_key: str) -> Optional[Dict[str, Any]]:
        """Get a specific template by key."""
        templates = self._load_templates()
        return templates.get(template_key)

    def get_all_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get all available templates."""
        return self._load_templates()

    def get_template_list(self) -> List[Dict[str, Any]]:
        """Get a list of templates with basic info for UI display."""
        templates = self._load_templates()
        return [
            {
                'key': key,
                'name': data['name'],
                'description': data.get('description', '')
            }
            for key, data in templates.items()
        ]

    def get_system_prompt(self, template_key: str) -> Optional[str]:
        """Get just the system prompt text for a template."""
        template = self.get_template(template_key)
        return template['system_prompt'] if template else None

    def invalidate_cache(self):
        """Clear the template cache to force reload."""
        self._templates_cache = None


# Global instance
template_manager = TemplateManager()