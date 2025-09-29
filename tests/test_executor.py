"""Tests for command executor"""

import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock

from executor import CommandExecutor
from openrouter_client import Command
from exceptions import CommandExecutionError, SafetyError


class TestCommandExecutor:
    """Test cases for CommandExecutor class"""
    
    def test_executor_initialization(self, mock_console):
        """Test executor initialization"""
        executor = CommandExecutor(console=mock_console, require_confirmation=False)
        
        assert executor.console == mock_console
        assert executor.require_confirmation is False
        assert executor.execution_history == []
    
    def test_dangerous_command_detection(self, command_executor):
        """Test detection of dangerous commands"""
        
        # Test dangerous commands
        dangerous_commands = [
            "rm -rf /",
            "sudo rm -rf /home",
            "chmod 777 /etc/passwd",
            "dd if=/dev/zero of=/dev/sda",
            "format C:",
        ]
        
        for cmd in dangerous_commands:
            assert command_executor._is_dangerous_command(cmd), f"Should detect '{cmd}' as dangerous"
        
        # Test safe commands
        safe_commands = [
            "ls -la",
            "echo hello",
            "pwd",
            "cat file.txt",
            "mkdir test_dir"
        ]
        
        for cmd in safe_commands:
            assert not command_executor._is_dangerous_command(cmd), f"Should not detect '{cmd}' as dangerous"
    
    def test_system_critical_path_detection(self, command_executor):
        """Test detection of system critical paths"""
        
        critical_commands = [
            "ls /etc/passwd",
            "cat /bin/bash",
            "rm C:\\Windows\\system32\\file.dll"
        ]
        
        for cmd in critical_commands:
            assert command_executor._is_dangerous_command(cmd), f"Should detect '{cmd}' as dangerous (critical path)"
    
    def test_empty_commands_list(self, command_executor):
        """Test handling of empty commands list"""
        result = command_executor.execute_commands([])
        
        assert result == []
        command_executor.console.print.assert_called_with("[yellow]No commands to execute[/yellow]")
    
    @patch('subprocess.run')
    def test_successful_command_execution(self, mock_run, command_executor):
        """Test successful command execution"""
        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        command = Command(
            command="echo hello",
            description="Test command",
            requires_confirmation=False
        )
        
        success, output = command_executor._execute_single_command(command)
        
        assert success is True
        assert output == "command output"
        assert len(command_executor.execution_history) == 1
        assert command_executor.execution_history[0]['success'] is True
    
    @patch('subprocess.run')
    def test_failed_command_execution(self, mock_run, command_executor):
        """Test failed command execution"""
        # Mock failed subprocess result
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command error"
        mock_run.return_value = mock_result
        
        command = Command(
            command="false",  # Command that always fails
            description="Test failing command",
            requires_confirmation=False
        )
        
        success, output = command_executor._execute_single_command(command)
        
        assert success is False
        assert output == "command error"
        assert len(command_executor.execution_history) == 1
        assert command_executor.execution_history[0]['success'] is False
    
    @patch('subprocess.run')
    def test_command_timeout(self, mock_run, command_executor):
        """Test command timeout handling"""
        mock_run.side_effect = subprocess.TimeoutExpired("test_cmd", 30)
        
        command = Command(
            command="sleep 60",
            description="Long running command",
            requires_confirmation=False
        )
        
        success, output = command_executor._execute_single_command(command)
        
        assert success is False
        assert "timed out" in output
    
    @patch('executor.Path')
    @patch('os.access')
    @patch('os.chdir')
    @patch('os.getcwd')
    @patch('subprocess.run')
    def test_working_directory_change(self, mock_run, mock_getcwd, mock_chdir, mock_access, mock_path, command_executor):
        """Test working directory change during execution"""
        mock_getcwd.return_value = "/original/dir"
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Mock path operations for permission checking
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        mock_path.return_value = mock_path_instance
        mock_access.return_value = True
        
        command = Command(
            command="ls",
            description="List files",
            working_directory="/test/dir",
            requires_confirmation=False
        )
        
        command_executor._execute_single_command(command)
        
        # Should change to working directory and back
        mock_chdir.assert_any_call("/test/dir")
        mock_chdir.assert_any_call("/original/dir")
    
    @patch('executor.Path')
    @patch('os.access')
    def test_nonexistent_working_directory(self, mock_access, mock_path, command_executor):
        """Test handling of nonexistent working directory"""
        # Mock path to not exist
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance
        
        command = Command(
            command="ls",
            description="List files",
            working_directory="/nonexistent/dir",
            requires_confirmation=False
        )
        
        success, output = command_executor._execute_single_command(command)
        
        assert success is False
        assert "Insufficient permissions" in output
    
    def test_selection_parsing(self, command_executor):
        """Test command selection parsing"""
        
        # Test single number
        indices = command_executor._parse_selection("1", 5)
        assert indices == [1]
        
        # Test range
        indices = command_executor._parse_selection("1-3", 5)
        assert indices == [1, 2, 3]
        
        # Test comma-separated
        indices = command_executor._parse_selection("1,3,5", 5)
        assert indices == [1, 3, 5]
        
        # Test mixed
        indices = command_executor._parse_selection("1,3-4", 5)
        assert indices == [1, 3, 4]
        
        # Test invalid range
        with pytest.raises(ValueError):
            command_executor._parse_selection("1-10", 5)
    
    def test_execution_history_management(self, command_executor):
        """Test execution history management"""
        
        # Initially empty
        assert command_executor.get_execution_history() == []
        
        # Add some mock history
        command_executor.execution_history = [
            {'command': 'ls', 'success': True},
            {'command': 'pwd', 'success': True}
        ]
        
        history = command_executor.get_execution_history()
        assert len(history) == 2
        assert history[0]['command'] == 'ls'
        
        # Clear history
        command_executor.clear_history()
        assert command_executor.get_execution_history() == []
    
    def test_command_display(self, command_executor):
        """Test command display functionality"""
        commands = [
            Command("ls -la", "List files", requires_confirmation=False),
            Command("pwd", "Print directory", requires_confirmation=False)
        ]
        
        # Should not raise exception
        command_executor._display_commands_preview(commands)
        command_executor._display_command_details(commands[0])
        
        # Check that console.print was called
        assert command_executor.console.print.called
    
    def test_execution_summary(self, command_executor, sample_commands):
        """Test execution summary display"""
        # Mock some results
        results = [
            (sample_commands[0], True, "success"),
            (sample_commands[1], False, "failed"),
            (sample_commands[2], False, "skipped")
        ]
        
        command_executor._display_execution_summary(results)
        
        # Should display summary
        assert command_executor.console.print.called
