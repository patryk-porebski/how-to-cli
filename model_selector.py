"""Interactive model selector with arrow key navigation"""

import sys
import tty
import termios
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

from logger import get_logger

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class ModelSelector:
    """Interactive model selector with keyboard navigation"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = get_logger(self.__class__.__name__)
        self.selected_index = 0
        
    def select_model(self, models: List[Dict[str, Any]], current_model: str = None) -> Optional[str]:
        """
        Interactive model selection
        Returns: selected model ID or None if cancelled
        """
        if not models:
            return None
            
        if len(models) == 1:
            # Auto-select single model
            return models[0].get('id')
        
        # Find current model index if set
        if current_model:
            for i, model in enumerate(models):
                if model.get('id') == current_model:
                    self.selected_index = i
                    break
        
        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        
        try:
            while True:
                # Clear terminal properly
                import os
                os.system('clear')
                
                self._display_models(models, current_model)
                self._display_help()
                
                # Get user input
                key = self._get_key()
                
                # Handle navigation
                if key == '\x1b' or key == '\x03' or key == 'q':  # Escape, Ctrl+C, or q
                    return None
                elif key == '\x1b[A' or key == 'k':  # Up arrow or k
                    self.selected_index = max(0, self.selected_index - 1)
                elif key == '\x1b[B' or key == 'j':  # Down arrow or j
                    self.selected_index = min(len(models) - 1, self.selected_index + 1)
                elif key == '\r':  # Enter
                    return models[self.selected_index].get('id')
                elif key.isdigit():
                    # Number selection
                    num = int(key) - 1
                    if 0 <= num < min(len(models), 9):  # Limit to first 9 models for number selection
                        return models[num].get('id')
                elif key == 'c' and CLIPBOARD_AVAILABLE:
                    # Copy model ID to clipboard
                    model_id = models[self.selected_index].get('id')
                    pyperclip.copy(model_id)
                    self.console.print(f"[green]Copied {model_id} to clipboard[/green]")
                    return None
                    
        finally:
            # Show cursor
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
    
    def _display_models(self, models: List[Dict[str, Any]], current_model: str = None):
        """Display the list of models with highlighting"""
        title = f"Select a model ({len(models)} available):"
        
        # Create model list display
        model_lines = []
        for i, model in enumerate(models):
            model_id = model.get('id', 'Unknown')
            model_name = model.get('name', 'No name')
            description = model.get('description', '')
            
            # Truncate long descriptions
            if description and len(description) > 80:
                description = description[:77] + "..."
            
            # Format the line
            if i == self.selected_index:
                # Selected item
                arrow = "❯"
                if model_id == current_model:
                    prefix = f"[green]{arrow} {i+1}. {model_id}[/green] [bold](current)[/bold]"
                else:
                    prefix = f"[cyan]{arrow} {i+1}. {model_id}[/cyan]"
                name_part = f" [bold]({model_name})[/bold]"
                desc_part = f"\n    [dim]{description}[/dim]" if description else ""
            else:
                # Unselected item
                if model_id == current_model:
                    prefix = f"  [green]{i+1}. {model_id}[/green] [bold](current)[/bold]"
                else:
                    prefix = f"  [dim]{i+1}. {model_id}[/dim]"
                name_part = f" [dim]({model_name})[/dim]"
                desc_part = f"\n    [dim]{description}[/dim]" if description and i == self.selected_index else ""
            
            model_lines.append(f"{prefix}{name_part}{desc_part}")
        
        # Display in a panel
        content = "\n".join(model_lines)
        panel = Panel(
            content,
            title=title,
            expand=False,
            border_style="blue"
        )
        self.console.print(panel)
    
    def _display_help(self):
        """Display help text for navigation"""
        help_items = [
            "[dim]↑↓[/dim] or [dim]j/k[/dim] navigate",
            "[dim]Enter[/dim] or [dim]1-9[/dim] select",
            "[dim]c[/dim] copy to clipboard" if CLIPBOARD_AVAILABLE else None,
            "[dim]q[/dim] or [dim]Esc[/dim] quit"
        ]
        
        # Filter out None items
        help_items = [item for item in help_items if item is not None]
        help_text = "  ".join(help_items)
        
        self.console.print(f"\n{help_text}")
    
    def _get_key(self):
        """Get a single keypress from the user"""
        if sys.platform == 'win32':
            import msvcrt
            return msvcrt.getch().decode('utf-8')
        else:
            # Unix/Linux/macOS
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                
                # Handle escape sequences (arrow keys)
                if ch == '\x1b':
                    ch += sys.stdin.read(2)
                    
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
