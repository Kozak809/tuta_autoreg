"""
Core configuration management for automation accounts.

Provides centralized logic for resolving configuration paths and loading
JSON-based account settings, ensuring consistency across different automation
scripts and apps.
"""
import os
import json

def get_config_manager():
    """Returns the central configuration manager instance."""
    return ConfigManager()

class ConfigManager:
    @staticmethod
    def resolve_path(config_path):
        """
        Resolves the absolute path for an account configuration file.
        Searches common locations relative to the project root.
        Returns the loaded JSON data and the absolute path.
        """
        if not config_path:
            return None, None
            
        # Standardize project root discovery
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        possible_paths = [
            config_path, 
            os.path.join(root_dir, config_path),
            os.path.join(root_dir, "apps", "tuta", config_path)
        ]
        
        for cp in possible_paths:
            if os.path.exists(cp):
                try:
                    with open(cp, "r", encoding="utf-8") as f:
                        return json.load(f), cp
                except (json.JSONDecodeError, IOError):
                    continue
        return None, None
