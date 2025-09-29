"""Tests for configuration management"""

import pytest
import os
import tempfile
import yaml
from pathlib import Path

from config import Config
from exceptions import ConfigurationError


class TestConfig:
    """Test cases for Config class"""
    
    def test_default_config_creation(self):
        """Test that default config is created properly"""
        config = Config.__new__(Config)  # Create without calling __init__
        config.config = Config.DEFAULT_CONFIG.copy()
        
        assert config.config['openrouter']['model'] == 'openai/gpt-4'
        assert config.config['execution']['require_confirmation'] is True
        assert config.config['output']['verbose'] is False
    
    def test_config_file_loading(self, temp_config_file):
        """Test loading config from file"""
        config = Config(temp_config_file)
        
        assert config.get('openrouter.api_key') == 'test_key'
        assert config.get('openrouter.model') == 'test_model'
        assert config.get('execution.require_confirmation') is False
    
    def test_config_get_with_dot_notation(self, temp_config_file):
        """Test getting config values with dot notation"""
        config = Config(temp_config_file)
        
        assert config.get('openrouter.api_key') == 'test_key'
        assert config.get('nonexistent.key', 'default') == 'default'
        assert config.get('openrouter.nonexistent', 'default') == 'default'
    
    def test_config_update_from_cli(self, temp_config_file):
        """Test updating config from CLI arguments"""
        config = Config(temp_config_file)
        
        config.update_from_cli(**{
            'openrouter.model': 'new_model',
            'execution.timeout': 60,
            'new_section.new_key': 'new_value'
        })
        
        assert config.get('openrouter.model') == 'new_model'
        assert config.get('execution.timeout') == 60
        assert config.get('new_section.new_key') == 'new_value'
    
    def test_config_save_and_load(self):
        """Test saving and loading config"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create config and modify it
            config = Config(temp_path)
            config.update_from_cli(**{'openrouter.api_key': 'saved_key'})
            config.save()
            
            # Load it again and verify
            config2 = Config(temp_path)
            assert config2.get('openrouter.api_key') == 'saved_key'
            
        finally:
            os.unlink(temp_path)
    
    def test_invalid_config_file_handling(self):
        """Test handling of invalid config files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            # Should raise ConfigurationError for invalid YAML
            with pytest.raises(Exception):  # ConfigurationError or other YAML error
                config = Config(temp_path)
            
        finally:
            os.unlink(temp_path)
    
    def test_default_config_path(self):
        """Test default config path generation"""
        config = Config.__new__(Config)
        path = config._get_default_config_path()
        
        assert path.endswith('config.yaml')
        assert '.config/how' in path
    
    def test_merge_config(self):
        """Test config merging logic"""
        config = Config.__new__(Config)
        base = {'a': {'b': 1, 'c': 2}, 'd': 3}
        override = {'a': {'b': 10}, 'e': 4}
        
        config._merge_config(base, override)
        
        assert base == {'a': {'b': 10, 'c': 2}, 'd': 3, 'e': 4}
