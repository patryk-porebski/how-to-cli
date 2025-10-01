import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from logger import get_logger
from exceptions import ConfigurationError
from constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_MODEL, DEFAULT_BASE_URL, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE


class Config:
    """Configuration management for how CLI tool"""
    
    DEFAULT_CONFIG = {
        'openrouter': {
            'api_key': '',
            'base_url': DEFAULT_BASE_URL,
            'model': DEFAULT_MODEL,
            'max_tokens': DEFAULT_MAX_TOKENS,
            'temperature': DEFAULT_TEMPERATURE
        },
        'execution': {
            'require_confirmation': True,
            'show_commands_before_execution': True,
            'max_commands_per_request': 10,
            'timeout': 30
        },
        'output': {
            'verbose': False,
            'color': True,
            'format': 'rich'
        },
        'history': {
            'enabled': True,
            'write_to_shell_history': False,
            'shell_history_shells': ['bash', 'zsh']
        }
    }
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.config_file = config_file or self._get_default_config_path()
        self.config = self.DEFAULT_CONFIG.copy()
        self._load_config()
    
    def _get_default_config_path(self) -> str:
        """Get default config file path"""
        home = Path.home()
        config_dir = home / CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / CONFIG_FILE)
    
    def _load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                self.logger.debug(f"Loading config from {self.config_file}")
                with open(self.config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                self._merge_config(self.config, file_config)
                self.logger.info(f"Configuration loaded successfully from {self.config_file}")
            except yaml.YAMLError as e:
                self.logger.error(f"Invalid YAML in config file {self.config_file}: {e}")
                raise ConfigurationError(f"Invalid YAML in config file: {e}")
            except Exception as e:
                self.logger.warning(f"Could not load config file {self.config_file}: {e}")
        else:
            self.logger.debug(f"Config file {self.config_file} does not exist, using defaults")
    
    def _merge_config(self, base: Dict, override: Dict):
        """Recursively merge configuration dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def update_from_cli(self, **kwargs):
        """Update configuration from CLI arguments"""
        for key, value in kwargs.items():
            if value is not None:
                if '.' in key:
                    # Handle nested keys like 'openrouter.model'
                    keys = key.split('.')
                    current = self.config
                    for k in keys[:-1]:
                        if k not in current:
                            current[k] = {}
                        current = current[k]
                    current[keys[-1]] = value
                else:
                    self.config[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        current = self.config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current
    
    def save(self):
        """Save current configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            self.logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            self.logger.error(f"Could not save config file {self.config_file}: {e}")
            raise ConfigurationError(f"Could not save config file: {e}")
    
    def create_default_config(self):
        """Create default configuration file"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()
        return self.config_file
