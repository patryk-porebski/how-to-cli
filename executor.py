import subprocess
import os
import sys
import shlex
import re
from typing import List, Optional, Tuple
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table

from openrouter_client import Command
from logger import get_logger
from exceptions import CommandExecutionError, SafetyError
from constants import DANGEROUS_COMMANDS, SYSTEM_CRITICAL_PATHS, COMMAND_TIMEOUT

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class CommandExecutor:
    """Handles execution of commands with user confirmation and safety checks"""
    
    def __init__(self, console: Optional[Console] = None, require_confirmation: bool = True):
        self.console = console or Console()
        self.require_confirmation = require_confirmation
        self.execution_history = []
        self.logger = get_logger(self.__class__.__name__)
    
    def execute_commands(self, commands: List[Command], show_commands: bool = True) -> List[Tuple[Command, bool, str]]:
        """Execute a list of commands with user confirmation"""
        if not commands:
            self.console.print("[yellow]No commands to execute[/yellow]")
            return []
        
        # If multiple commands, let user select which ones to execute
        if len(commands) > 1:
            selected_commands = self._select_commands(commands)
            if not selected_commands:
                self.console.print("[yellow]No commands selected for execution[/yellow]")
                return []
        else:
            selected_commands = commands
        
        results = []
        
        for i, command in enumerate(selected_commands, 1):
            self.console.print(f"\n[bold blue]Command {i}/{len(selected_commands)}[/bold blue]")
            
            # Show command details
            self._display_command_details(command)
            
            # Check for dangerous commands
            if self._is_dangerous_command(command.command):
                self.console.print("[bold red]⚠️  WARNING: This command may be dangerous![/bold red]")
                if not Confirm.ask("Are you sure you want to proceed?", default=False):
                    results.append((command, False, "Skipped by user (dangerous command)"))
                    continue
            
            # Ask for confirmation if required
            if self.require_confirmation and command.requires_confirmation:
                choice = self._get_execution_choice(command)
                if choice == "skip":
                    self.logger.info(f"Command skipped by user: {command.command}")
                    results.append((command, False, "Skipped by user"))
                    continue
                elif choice == "edit":
                    original_command = command.command
                    command = self._edit_command(command)
                    self.logger.info(f"Command edited from '{original_command}' to '{command.command}'")
                elif choice == "copy":
                    self._copy_command(command)
                    self.logger.info(f"Command copied to clipboard: {command.command}")
                    results.append((command, False, "Command copied to clipboard"))
                    continue
            
            # Execute the command
            try:
                success, output = self._execute_single_command(command)
                results.append((command, success, output))
            except Exception as e:
                error_msg = f"Failed to execute command: {e}"
                self.logger.error(error_msg)
                results.append((command, False, error_msg))
            
            # Ask if user wants to continue if command failed
            if not success and i < len(selected_commands):
                if not Confirm.ask("Command failed. Continue with remaining commands?", default=False):
                    for remaining_cmd in selected_commands[i:]:
                        results.append((remaining_cmd, False, "Skipped due to previous failure"))
                    break
        
        self._display_execution_summary(results)
        return results
    
    def _display_commands_preview(self, commands: List[Command]):
        """Display preview of all commands before execution"""
        self.console.print("\n[bold green]Commands to execute:[/bold green]")
        
        for i, command in enumerate(commands, 1):
            panel_content = f"[bold cyan]{command.command}[/bold cyan]\n[dim]{command.description}[/dim]"
            self.console.print(Panel(panel_content, title=f"Command {i}", expand=False))
    
    def _display_command_details(self, command: Command):
        """Display details for a single command"""
        # Display command with syntax highlighting
        syntax = Syntax(command.command, "bash", theme="monokai", line_numbers=False)
        self.console.print(syntax)
        self.console.print(f"\n[dim]{command.description}[/dim]")
        
        if command.working_directory:
            self.console.print(f"[dim]Working directory: {command.working_directory}[/dim]")
    
    def _is_dangerous_command(self, command: str) -> bool:
        """Check if a command might be dangerous"""
        command_lower = command.lower()
        
        self.logger.debug(f"Checking if command is dangerous: {command}")
        
        # Check for dangerous command patterns
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command_lower:
                self.logger.warning(f"Dangerous command pattern detected: {dangerous} in {command}")
                return True
        
        # Check for system critical paths
        for critical_path in SYSTEM_CRITICAL_PATHS:
            if critical_path in command:
                self.logger.warning(f"System critical path detected: {critical_path} in {command}")
                return True
        
        # Check for redirections that might overwrite important files
        if any(redirect in command for redirect in ['>', '>>', '|']):
            if any(path in command for path in ['/etc/', '/bin/', '/sbin/', 'C:\\']):
                self.logger.warning(f"Dangerous redirection to system path detected in: {command}")
                return True
        
        # Additional safety checks
        if self._has_suspicious_patterns(command):
            return True
        
        return False
    
    def _has_suspicious_patterns(self, command: str) -> bool:
        """Check for additional suspicious patterns in commands"""
        suspicious_patterns = [
            r';\s*rm\s',  # Command chaining with rm
            r'&&\s*rm\s',  # Command chaining with rm
            r'\|\s*rm\s',  # Piping to rm
            r'>\s*/dev/',  # Writing to device files
            r'wget.*\|\s*sh',  # Downloading and executing
            r'curl.*\|\s*sh',  # Downloading and executing
            r'sudo\s+.*rm.*-rf',  # Sudo with recursive rm
            r'find.*-delete',  # Find with delete
            r'xargs.*rm',  # xargs with rm
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                self.logger.warning(f"Suspicious pattern detected: {pattern} in {command}")
                return True
        
        return False
    
    def _check_directory_permissions(self, directory: str) -> bool:
        """Check if directory exists and is accessible"""
        try:
            path = Path(directory)
            if not path.exists():
                self.logger.warning(f"Directory does not exist: {directory}")
                return False
            if not path.is_dir():
                self.logger.warning(f"Path is not a directory: {directory}")
                return False
            if not os.access(directory, os.R_OK | os.X_OK):
                self.logger.warning(f"Insufficient permissions for directory: {directory}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error checking directory permissions for {directory}: {e}")
            return False
    
    def _check_file_permissions_in_command(self, command: str) -> List[str]:
        """Check file permissions for commands that might modify files"""
        warnings = []
        
        # Extract potential file paths from command
        try:
            parts = shlex.split(command)
        except ValueError:
            # If command can't be parsed, skip detailed checks
            return warnings
        
        # Check for file modification commands
        if any(parts[0].endswith(cmd) for cmd in ['rm', 'mv', 'cp', 'chmod', 'chown']):
            for part in parts[1:]:
                if part.startswith('/') or part.startswith('./') or part.startswith('../'):
                    path = Path(part)
                    if path.exists():
                        if not os.access(str(path.parent), os.W_OK):
                            warnings.append(f"No write permission for directory: {path.parent}")
                        if path.is_file() and not os.access(str(path), os.W_OK):
                            warnings.append(f"No write permission for file: {path}")
        
        return warnings
    
    def _execute_single_command(self, command: Command) -> Tuple[bool, str]:
        """Execute a single command and return success status and output"""
        try:
            self.console.print(f"[dim]Executing: {command.command}[/dim]")
            
            # Check file permissions before execution
            permission_warnings = self._check_file_permissions_in_command(command.command)
            for warning in permission_warnings:
                self.logger.warning(warning)
                self.console.print(f"[yellow]Warning: {warning}[/yellow]")
            
            # Change working directory if specified
            original_cwd = os.getcwd()
            if command.working_directory:
                if not self._check_directory_permissions(command.working_directory):
                    error_msg = f"Insufficient permissions for working directory: {command.working_directory}"
                    self.logger.error(error_msg)
                    return False, error_msg
                try:
                    os.chdir(command.working_directory)
                except FileNotFoundError:
                    return False, f"Working directory not found: {command.working_directory}"
                except PermissionError:
                    return False, f"Permission denied accessing working directory: {command.working_directory}"
            
            # Execute the command
            result = subprocess.run(
                command.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT
            )
            
            # Restore original working directory
            if command.working_directory:
                try:
                    os.chdir(original_cwd)
                except OSError as e:
                    self.logger.error(f"Failed to restore working directory to {original_cwd}: {e}")
                    raise CommandExecutionError(f"Failed to restore working directory: {e}")
            
            # Store in history
            self.execution_history.append({
                'command': command.command,
                'success': result.returncode == 0,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            })
            
            # Display output
            if result.stdout:
                self.console.print("[green]Output:[/green]")
                self.console.print(result.stdout)
            
            if result.stderr:
                self.console.print("[red]Error output:[/red]")
                self.console.print(result.stderr)
            
            if result.returncode == 0:
                self.console.print("[green]✓ Command executed successfully[/green]")
                return True, result.stdout
            else:
                self.console.print(f"[red]✗ Command failed with exit code {result.returncode}[/red]")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {COMMAND_TIMEOUT} seconds"
            self.logger.error(f"Command timeout: {command.command}")
            self.console.print(f"[red]✗ {error_msg}[/red]")
            return False, error_msg
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with exit code {e.returncode}: {e}"
            self.logger.error(f"Command failed: {command.command} - {error_msg}")
            self.console.print(f"[red]✗ {error_msg}[/red]")
            return False, error_msg
        except OSError as e:
            error_msg = f"OS error executing command: {e}"
            self.logger.error(f"OS error: {command.command} - {error_msg}")
            self.console.print(f"[red]✗ {error_msg}[/red]")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error executing command: {e}"
            self.logger.error(f"Unexpected error: {command.command} - {error_msg}")
            self.console.print(f"[red]✗ {error_msg}[/red]")
            return False, error_msg
        finally:
            # Ensure we're back in the original directory
            if command.working_directory:
                try:
                    os.chdir(original_cwd)
                except OSError as e:
                    self.logger.error(f"Failed to restore working directory in finally block: {e}")
    
    def _display_execution_summary(self, results: List[Tuple[Command, bool, str]]):
        """Display summary of command execution results"""
        if not results:
            return
        
        successful = sum(1 for _, success, _ in results if success)
        total = len(results)
        
        self.console.print(f"\n[bold]Execution Summary:[/bold]")
        self.console.print(f"[green]✓ Successful: {successful}[/green]")
        self.console.print(f"[red]✗ Failed/Skipped: {total - successful}[/red]")
        self.console.print(f"[blue]Total: {total}[/blue]")
        
        # Show failed commands
        failed_commands = [(cmd, output) for cmd, success, output in results if not success]
        if failed_commands:
            self.console.print("\n[red]Failed/Skipped commands:[/red]")
            for cmd, output in failed_commands:
                self.console.print(f"  • {cmd.command}: {output}")
    
    def get_execution_history(self) -> List[dict]:
        """Get history of executed commands"""
        return self.execution_history.copy()
    
    def clear_history(self):
        """Clear execution history"""
        self.execution_history.clear()
    
    def _select_commands(self, commands: List[Command]) -> List[Command]:
        """Let user select which commands to execute"""
        self.console.print("\n[bold green]Available commands:[/bold green]")
        
        # Display commands in a table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Command", style="green")
        table.add_column("Description", style="yellow")
        
        for i, cmd in enumerate(commands, 1):
            table.add_row(str(i), cmd.command[:50] + "..." if len(cmd.command) > 50 else cmd.command, 
                         cmd.description[:60] + "..." if len(cmd.description) > 60 else cmd.description)
        
        self.console.print(table)
        
        self.console.print("\n[bold]Options:[/bold]")
        self.console.print("• Enter numbers (e.g., '1,3' or '1-3'): Select specific commands")
        self.console.print("• 'all': Select all commands")
        self.console.print("• 'none' or just Enter: Skip all")
        
        while True:
            try:
                selection = Prompt.ask("\nWhich commands do you want to execute?", default="all")
                
                if selection.lower() in ['none', '']:
                    return []
                elif selection.lower() == 'all':
                    return commands
                else:
                    # Parse number selection
                    selected_indices = self._parse_selection(selection, len(commands))
                    return [commands[i-1] for i in selected_indices]
                    
            except (ValueError, IndexError) as e:
                self.console.print(f"[red]Invalid selection: {e}. Please try again.[/red]")
    
    def _parse_selection(self, selection: str, max_num: int) -> List[int]:
        """Parse user selection string into list of indices"""
        indices = []
        
        for part in selection.split(','):
            part = part.strip()
            if '-' in part:
                # Range selection like "1-3"
                start, end = map(int, part.split('-'))
                indices.extend(range(start, end + 1))
            else:
                # Single number
                indices.append(int(part))
        
        # Validate indices
        for idx in indices:
            if idx < 1 or idx > max_num:
                raise ValueError(f"Index {idx} is out of range (1-{max_num})")
        
        return sorted(set(indices))  # Remove duplicates and sort
    
    def _get_execution_choice(self, command: Command) -> str:
        """Get user choice for command execution"""
        options = "[E]xecute, [S]kip"
        if CLIPBOARD_AVAILABLE:
            options += ", [C]opy"
        options += ", [M]odify"
        
        while True:
            choice = Prompt.ask(f"{options}?", choices=["e", "execute", "s", "skip", "c", "copy", "m", "modify"], 
                              default="e", show_choices=False).lower()
            
            if choice in ["e", "execute"]:
                return "execute"
            elif choice in ["s", "skip"]:
                return "skip"
            elif choice in ["c", "copy"] and CLIPBOARD_AVAILABLE:
                return "copy"
            elif choice in ["m", "modify"]:
                return "edit"
            else:
                self.console.print("[red]Invalid choice. Please try again.[/red]")
    
    def _edit_command(self, command: Command) -> Command:
        """Allow user to edit a command"""
        self.console.print(f"\n[yellow]Current command:[/yellow] {command.command}")
        
        new_command = Prompt.ask("Enter modified command", default=command.command)
        new_description = Prompt.ask("Enter new description (optional)", default=command.description)
        
        return Command(
            command=new_command,
            description=new_description,
            working_directory=command.working_directory,
            requires_confirmation=command.requires_confirmation
        )
    
    def _copy_command(self, command: Command):
        """Copy command to clipboard"""
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(command.command)
                self.console.print("[green]✓ Command copied to clipboard[/green]")
            except Exception as e:
                self.console.print(f"[red]Failed to copy to clipboard: {e}[/red]")
        else:
            self.console.print("[yellow]Clipboard functionality not available (install pyperclip)[/yellow]")
            self.console.print(f"[cyan]Command to copy:[/cyan] {command.command}")
