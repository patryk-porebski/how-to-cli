"""Tests for OpenRouter client"""

import pytest
import responses
import json
from unittest.mock import patch, Mock

from openrouter_client import OpenRouterClient, Command
from exceptions import APIError


class TestOpenRouterClient:
    """Test cases for OpenRouterClient class"""
    
    def test_client_initialization(self):
        """Test client initialization"""
        client = OpenRouterClient(
            api_key="test_key",
            model="test_model",
            max_tokens=500
        )
        
        assert client.api_key == "test_key"
        assert client.model == "test_model"
        assert client.max_tokens == 500
    
    def test_client_initialization_without_api_key(self):
        """Test that client raises error without API key"""
        with pytest.raises(ValueError, match="OpenRouter API key is required"):
            OpenRouterClient(api_key="")
    
    def test_create_headers(self):
        """Test header creation"""
        client = OpenRouterClient(api_key="test_key")
        headers = client._create_headers()
        
        assert headers["Authorization"] == "Bearer test_key"
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers
    
    def test_system_prompt_creation(self):
        """Test system prompt creation"""
        client = OpenRouterClient(api_key="test_key")
        prompt = client._create_system_prompt()
        
        assert "command" in prompt
        assert "description" in prompt
        assert "macOS/Linux compatible commands" in prompt
        assert "STRICT JSON" in prompt
    
    @responses.activate
    def test_successful_api_call(self):
        """Test successful API call and command parsing"""
        # Mock API response
        mock_response = {
            "choices": [{
                "message": {
                    "content": "COMMAND: ls -la\nDESC: List files with details"
                }
            }]
        }
        
        responses.add(
            responses.POST,
            "https://openrouter.ai/api/v1/chat/completions",
            json=mock_response,
            status=200
        )
        
        client = OpenRouterClient(api_key="test_key")
        
        with patch('builtins.print'):  # Suppress debug prints
            commands = client.ask_for_commands("list files")
        
        assert len(commands) == 1
        assert commands[0].command == "ls -la"
        assert commands[0].description == "List files with details"
    
    @responses.activate
    def test_api_error_handling(self):
        """Test API error handling"""
        responses.add(
            responses.POST,
            "https://openrouter.ai/api/v1/chat/completions",
            json={"error": "Invalid API key"},
            status=401
        )
        
        client = OpenRouterClient(api_key="invalid_key")
        
        with patch('builtins.print'):  # Suppress debug prints
            with pytest.raises(Exception, match="API request failed"):
                client.ask_for_commands("test query")
    
    @responses.activate
    def test_empty_response_handling(self):
        """Test handling of empty API responses"""
        mock_response = {"choices": []}
        
        responses.add(
            responses.POST,
            "https://openrouter.ai/api/v1/chat/completions",
            json=mock_response,
            status=200
        )
        
        client = OpenRouterClient(api_key="test_key")
        
        with patch('builtins.print'):  # Suppress debug prints
            with pytest.raises(Exception, match="No response from API"):
                client.ask_for_commands("test query")
    
    def test_command_parsing(self):
        """Test command parsing from various formats"""
        client = OpenRouterClient(api_key="test_key")
        
        # Test standard format
        content1 = "COMMAND: echo hello\nDESC: Print hello"
        with patch('builtins.print'):
            commands1 = client._parse_commands(content1)
        
        assert len(commands1) == 1
        assert commands1[0].command == "echo hello"
        assert commands1[0].description == "Print hello"
        
        # Test multiple commands
        content2 = "COMMAND: ls\nDESC: List files\nCOMMAND: pwd\nDESC: Print directory"
        with patch('builtins.print'):
            commands2 = client._parse_commands(content2)
        
        assert len(commands2) == 2
        assert commands2[0].command == "ls"
        assert commands2[1].command == "pwd"
    
    def test_fallback_parsing(self):
        """Test fallback command parsing"""
        client = OpenRouterClient(api_key="test_key", debug=False)
        
        # Content with shell prompt format that should be detected
        content = "$ ls -la\n$ echo hello"
        
        commands = client._fallback_command_parsing(content)
        
        # Should extract recognizable commands
        command_texts = [cmd.command for cmd in commands]
        assert any("ls" in cmd for cmd in command_texts)
    
    def test_context_in_request(self):
        """Test that context is included in API request"""
        client = OpenRouterClient(api_key="test_key")
        
        with patch.object(client, '_create_headers', return_value={}):
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "COMMAND: ls\nDESC: list"}}]
                }
                mock_post.return_value = mock_response
                
                with patch('builtins.print'):  # Suppress debug prints
                    client.ask_for_commands("test query", context="test context")
                
                # Check that request was made with context
                args, kwargs = mock_post.call_args
                payload = kwargs['json']
                messages = payload['messages']
                
                # Should have system, context, and user messages
                assert len(messages) == 3
                assert any("test context" in msg['content'] for msg in messages)
