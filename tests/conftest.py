"""Pytest configuration and fixtures"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock

from config import Config
from openrouter_client import OpenRouterClient, Command
from executor import CommandExecutor


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
openrouter:
  api_key: test_key
  model: test_model
  max_tokens: 100
  temperature: 0.1
execution:
  require_confirmation: false
  timeout: 10
output:
  verbose: true
""")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    config = Mock()
    config.get.side_effect = lambda key, default=None: {
        'openrouter.api_key': 'test_api_key',
        'openrouter.model': 'test_model',
        'openrouter.max_tokens': 100,
        'openrouter.temperature': 0.1,
        'execution.require_confirmation': False,
        'execution.timeout': 10,
        'output.verbose': False
    }.get(key, default)
    return config


@pytest.fixture
def sample_commands():
    """Sample commands for testing"""
    return [
        Command(
            command="ls -la",
            description="List files with details",
            requires_confirmation=True
        ),
        Command(
            command="echo 'hello world'",
            description="Print hello world",
            requires_confirmation=False
        ),
        Command(
            command="rm -rf /",
            description="Dangerous command",
            requires_confirmation=True
        )
    ]


@pytest.fixture
def mock_console():
    """Mock rich console for testing"""
    return Mock()


@pytest.fixture
def command_executor(mock_console):
    """Command executor instance for testing"""
    return CommandExecutor(console=mock_console, require_confirmation=False)
