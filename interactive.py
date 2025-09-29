"""Interactive command selector with arrow key navigation"""

import sys
import tty
import termios
from typing import List, Optional, Callable
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich.align import Align

from openrouter_client import Command
from logger import get_logger
from parameters import ParameterDetector, ParameterCustomizer
from interactive_helper import highlight_parameters

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class InteractiveSelector:
    """Interactive command selector with keyboard navigation"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = get_logger(self.__class__.__name__)
        self.selected_index = 0
        self.last_selected_index = 0  # Remember selection between commands
        self.parameter_detector = ParameterDetector()
        self.parameter_customizer = ParameterCustomizer(self.console)
        
    def select_command(self, commands: List[Command]) -> Optional[tuple]:
        """
        Interactive command selection
        Returns: (command, action) where action is 'execute', 'copy', or 'edit'
        """
        if not commands:
            return None
            
        if len(commands) == 1:
            # Auto-select single command but still allow user to choose action
            return self._show_single_command_actions(commands[0])
        
        # Smart selection persistence - start from last selected if valid
        if self.last_selected_index < len(commands):
            self.selected_index = self.last_selected_index
        else:
            self.selected_index = 0
        
        # Hide cursor
        import sys
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        
        try:
            while True:
                # Clear terminal properly
                import os
                os.system('clear')
                
                self._display_commands(commands)
                self._display_help()
                
                # Get user input
                key = self._get_key()
                
                # Handle navigation
                if key == '\x1b' or key == '\x03':  # Standalone Escape or Ctrl+C
                    return None
                elif key == '\x1b[A' or key == 'k':  # Up arrow or k
                    self.selected_index = max(0, self.selected_index - 1)
                elif key == '\x1b[B' or key == 'j':  # Down arrow or j
                    self.selected_index = min(len(commands) - 1, self.selected_index + 1)
                elif key == '\r':  # Enter - Check for parameters first
                    self.last_selected_index = self.selected_index  # Remember selection
                    selected_command = commands[self.selected_index]
                    
                    # Check if command has parameters
                    parameters = self.parameter_detector.detect_parameters(selected_command.command)
                    if parameters:
                        # Enter parameter editing mode
                        return selected_command, 'parameters'
                    else:
                        # Execute immediately if no parameters
                        return selected_command, 'execute'
                elif key.isdigit():
                    # Number selection - Check for parameters first
                    num = int(key) - 1
                    if 0 <= num < len(commands):
                        self.last_selected_index = num  # Remember selection
                        selected_command = commands[num]
                        
                        # Check if command has parameters
                        parameters = self.parameter_detector.detect_parameters(selected_command.command)
                        if parameters:
                            # Enter parameter editing mode
                            return selected_command, 'parameters'
                        else:
                            # Execute immediately if no parameters
                            return selected_command, 'execute'
                elif key == 'c':  # c for copy
                    return commands[self.selected_index], 'copy'
                elif key == 'm':  # m for modify
                    return commands[self.selected_index], 'edit'
                    
        finally:
            # Show cursor
            import sys
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
    
    def _display_commands(self, commands: List[Command]):
        """Display commands in a clean list format"""
        self.console.print()
        if len(commands) > 1:
            self.console.print("Select a command ", style="bold", end="")
            self.console.print(f"({len(commands)} available):", style="dim")
        else:
            self.console.print("Select a command:", style="bold")
        self.console.print()
        
        self._render_command_list(commands)
    
    def _render_command_list(self, commands: List[Command]):
        """Render the command list with parameter highlighting"""
        for i, command in enumerate(commands):
            is_selected = i == self.selected_index
            
            # Detect parameters for highlighting
            parameters = self.parameter_detector.detect_parameters(command.command)
            
            # Create the command display with parameter highlights
            if is_selected:
                # Highlighted selection
                prefix = Text("❯ ", style="bold green")
                number = Text(f"{i + 1}. ", style="bold cyan")
                command_text = highlight_parameters(command.command, parameters, "bold green")
            else:
                # Normal display
                prefix = Text("  ", style="dim")
                number = Text(f"{i + 1}. ", style="dim cyan")
                command_text = highlight_parameters(command.command, parameters, "white")
                
            # Combine all parts for command line
            full_line = Text()
            full_line.append_text(prefix)
            full_line.append_text(number)
            full_line.append_text(command_text)
            
            self.console.print(full_line)
            
            # Description on the next line
            desc_line = Text()
            desc_line.append("     ")  # Indent to align with command
            desc_line.append(command.description, style="dim green" if is_selected else "dim")
            self.console.print(desc_line)
            
            
            if i < len(commands) - 1:
                self.console.print()  # Space between commands
    
    # Removed complex _update_display - using simple console.clear() instead
    
    def _display_help(self):
        """Display help text"""
        self.console.print()
        help_items = [
            Text("↑↓", style="dim") + Text(" navigate", style="white"),
            Text("Enter/1-9", style="dim") + Text(" customize/execute", style="green"),
            Text("c", style="dim") + Text(" copy", style="blue"),
            Text("m", style="dim") + Text(" modify", style="yellow"),
            Text("Esc", style="dim") + Text(" quit", style="red")
        ]
        
        help_line = Text("  ")
        for i, item in enumerate(help_items):
            if i > 0:
                help_line.append("  ")
            help_line.append_text(item)
        self.console.print(help_line)
        self.console.print()
    
    def _show_single_command_actions(self, command: Command) -> Optional[tuple]:
        """Show actions for a single command"""
        self.console.print()
        self.console.print("Command ready:", style="bold")
        self.console.print()
        
        # Display the command prominently with parameter highlighting
        parameters = self.parameter_detector.detect_parameters(command.command)
        cmd_line = Text("  ")
        cmd_line.append_text(highlight_parameters(command.command, parameters, "bold green"))
        desc_text = Text(f"  {command.description}", style="dim")
        
        self.console.print(cmd_line)
        self.console.print(desc_text)
        self.console.print()
        
        # Show action options
        action_line = Text("  ")
        actions = [
            (Text("Enter", style="dim"), Text(" customize/execute", style="green")),
            (Text("c", style="dim"), Text(" copy", style="blue")),
            (Text("m", style="dim"), Text(" modify", style="yellow")),
            (Text("Esc", style="dim"), Text(" quit", style="red"))
        ]
        
        for i, (key, desc) in enumerate(actions):
            if i > 0:
                action_line.append("    ")
            action_line.append_text(key)
            action_line.append_text(desc)
        
        self.console.print(action_line)
        
        # Get user choice
        while True:
            key = self._get_key()
            
            if key == '\x1b' or key == '\x03':  # Standalone Escape or Ctrl+C
                return None
            elif key == '\r':  # Enter - customize if parameters exist (LLM or detected), else execute
                parameters = []
                try:
                    parameters = self.parameter_detector.detect_parameters(command.command)
                except Exception:
                    parameters = []
                # Prefer LLM-provided parameters if available on the command
                has_llm_params = bool(getattr(command, 'parameters', None))
                if has_llm_params or parameters:
                    return command, 'parameters'
                else:
                    return command, 'execute'
            elif key == 'c':
                return command, 'copy'
            elif key == 'm':
                return command, 'edit'
    
        
    
    def _get_key(self) -> str:
        """Get a single keypress from user with fallback for non-interactive terminals"""
        import sys
        
        # Check if running in a proper terminal
        if not sys.stdin.isatty():
            # Not a terminal, use simple input
            try:
                return input().strip()[:1] or '\r'
            except (EOFError, KeyboardInterrupt):
                return '\x1b'
        
        if sys.platform == 'win32':
            import msvcrt
            key = msvcrt.getch().decode('utf-8')
            if key == '\xe0':  # Arrow keys on Windows
                key2 = msvcrt.getch().decode('utf-8')
                if key2 == 'H':
                    return '\x1b[A'  # Up
                elif key2 == 'P':
                    return '\x1b[B'  # Down
            elif key == '\x1b':  # Escape key on Windows
                return '\x1b'
            return key
        else:
            # Unix/Linux/macOS
            try:
                import tty
                import termios
                
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    key = sys.stdin.read(1)
                    
                    # Handle arrow keys (escape sequences) vs standalone Escape
                    if key == '\x1b':
                        # Set stdin to non-blocking to check for more characters
                        import fcntl
                        import os
                        
                        # Save original flags
                        orig_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                        # Set non-blocking
                        fcntl.fcntl(fd, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)
                        
                        try:
                            # Try to read more characters
                            next_chars = sys.stdin.read(2)
                            if next_chars:
                                key += next_chars
                            # If no more chars, it's standalone escape
                        except (OSError, IOError):
                            # No more characters available - standalone escape
                            pass
                        finally:
                            # Restore original flags
                            fcntl.fcntl(fd, fcntl.F_SETFL, orig_fl)
                        
                    return key
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except (ImportError, OSError, termios.error):
                # Fallback for terminals that don't support raw mode
                self.console.print("[yellow]Arrow keys not supported in this terminal. Use j/k or numbers.[/yellow]")
                try:
                    return input().strip()[:1] or '\r'
                except (EOFError, KeyboardInterrupt):
                    return '\x1b'


class MinimalExecutor:
    """Minimal command executor with clean output"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = get_logger(self.__class__.__name__)
    
    def execute_command(self, command: Command) -> bool:
        """Execute command with minimal, clean output"""
        import subprocess
        import os
        
        try:
            # Clear command start marker
            self.console.print()
            self.console.print("❯", style="bold blue", end=" ")
            self.console.print(command.command, style="bold")
            
            if command.working_directory:
                self.console.print(f"  in {command.working_directory}", style="dim")
            
            # Subtle separator before output
            self.console.print("▶", style="dim")
            
            # Execute
            result = subprocess.run(
                command.command,
                shell=True,
                cwd=command.working_directory,
                text=True,
                capture_output=False  # Let output go directly to terminal
            )
            
            # Subtle command end marker
            if result.returncode == 0:
                self.console.print("◀", style="dim")
            else:
                self.console.print(f"◀ exit {result.returncode}", style="dim red")
            
            return result.returncode == 0
                
        except KeyboardInterrupt:
            self.console.print()
            self.console.print("Interrupted", style="yellow")
            return False
        except Exception as e:
            self.console.print()
            self.console.print(f"Error: {e}", style="red")
            return False
    
    def copy_command(self, command: Command) -> bool:
        """Copy command to clipboard"""
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(command.command)
                # Brief copy feedback - no waiting
                self.console.print()
                self.console.print("● Copied to clipboard:", style="green", end=" ")
                self.console.print(command.command, style="bold")
                return True
            except Exception as e:
                self.console.print(f"Copy failed: {e}", style="red")
                return False
        else:
            self.console.print("Clipboard unavailable", style="yellow")
            self.console.print(command.command, style="dim")
            return False
    
    def edit_command(self, command: Command) -> Optional[Command]:
        """Allow user to edit command with inline editing"""
        import readline
        
        self.console.print()
        self.console.print("Edit command:", style="bold")
        self.console.print()
        
        try:
            # Pre-fill the input with current command
            def pre_input_hook():
                readline.insert_text(command.command)
                readline.redisplay()
            
            # Set up readline to pre-fill the command
            readline.set_pre_input_hook(pre_input_hook)
            
            # Get edited command with pre-filled text
            self.console.print("Command:", style="dim", end=" ")
            new_command = input().strip()
            
            # Clear the hook
            readline.set_pre_input_hook(None)
            
            if new_command:
                if new_command != command.command:
                    # Create new command object
                    edited_command = Command(
                        command=new_command,
                        description=f"Modified: {command.description}",
                        working_directory=command.working_directory,
                        requires_confirmation=command.requires_confirmation
                    )
                    
                    self.console.print("Updated:", style="green", end=" ")
                    self.console.print(new_command, style="bold")
                    return edited_command
                else:
                    # Same command - still execute it
                    return command
            else:
                # Empty command - return original
                return command
                
        except KeyboardInterrupt:
            self.console.print()
            self.console.print("Cancelled", style="yellow")
            return command
        except ImportError:
            # Fallback if readline not available
            self.console.print(f"Current command: {command.command}", style="dim")
            self.console.print("New command:", style="dim", end=" ")
            new_command = input().strip()
            
            if new_command:
                if new_command != command.command:
                    edited_command = Command(
                        command=new_command,
                        description=f"Modified: {command.description}",
                        working_directory=command.working_directory,
                        requires_confirmation=command.requires_confirmation
                    )
                    return edited_command
                else:
                    # Same command - still execute it
                    return command
            else:
                # Empty command - return original
                return command
