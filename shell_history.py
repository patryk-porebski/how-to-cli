"""Shell history integration for writing commands to shell history files"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from logger import get_logger


class ShellHistoryWriter:
    """Handles writing commands to shell history files"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.shell = self._detect_shell()
    
    def _detect_shell(self) -> str:
        """Detect the current shell"""
        shell = os.environ.get('SHELL', '')
        if 'zsh' in shell:
            return 'zsh'
        elif 'bash' in shell:
            return 'bash'
        elif 'fish' in shell:
            return 'fish'
        else:
            return 'sh'
    
    def write_to_history(self, command: str, shell: Optional[str] = None) -> bool:
        """Write a command to the shell history file"""
        shell = shell or self.shell
        
        try:
            if shell == 'zsh':
                return self._write_zsh_history(command)
            elif shell == 'bash':
                return self._write_bash_history(command)
            elif shell == 'fish':
                return self._write_fish_history(command)
            else:
                # Fallback to bash format for other shells
                return self._write_bash_history(command)
        except Exception as e:
            self.logger.error(f"Failed to write to shell history: {e}")
            return False
    
    def _write_zsh_history(self, command: str) -> bool:
        """Write to zsh history file"""
        history_file = Path.home() / '.zsh_history'
        
        try:
            # Zsh history format: ': timestamp:0;command'
            timestamp = int(datetime.now().timestamp())
            entry = f": {timestamp}:0;{command}\n"
            
            with open(history_file, 'a') as f:
                f.write(entry)
            
            self.logger.debug(f"Added command to zsh history: {command}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to write to zsh history: {e}")
            return False
    
    def _write_bash_history(self, command: str) -> bool:
        """Write to bash history file"""
        history_file = Path.home() / '.bash_history'
        
        try:
            # Bash history format: just the command
            with open(history_file, 'a') as f:
                f.write(f"{command}\n")
            
            self.logger.debug(f"Added command to bash history: {command}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to write to bash history: {e}")
            return False
    
    def _write_fish_history(self, command: str) -> bool:
        """Write to fish history file"""
        history_file = Path.home() / '.local/share/fish/fish_history'
        
        try:
            # Fish history format: YAML-like
            timestamp = int(datetime.now().timestamp())
            entry = f"- cmd: {command}\n  when: {timestamp}\n"
            
            # Ensure directory exists
            history_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(history_file, 'a') as f:
                f.write(entry)
            
            self.logger.debug(f"Added command to fish history: {command}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to write to fish history: {e}")
            return False
    
    def write_to_all_shells(self, command: str) -> dict:
        """Write command to all common shell history files"""
        results = {}
        
        for shell_type in ['bash', 'zsh', 'fish']:
            results[shell_type] = self.write_to_history(command, shell_type)
        
        return results
