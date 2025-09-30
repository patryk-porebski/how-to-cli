"""
Smart parameter detection and customization for commands.
"""

import re
import os
import glob
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from rich.text import Text


@dataclass
class Parameter:
    """Represents a detected parameter in a command"""
    name: str  # Display name for the parameter
    original_value: str  # Original value in the command
    start_pos: int  # Start position in command string
    end_pos: int  # End position in command string
    param_type: str  # Type: 'file', 'path', 'placeholder', 'option'
    suggestions: List[str]  # Suggested values
    description: str  # Human-readable description


class ParameterDetector:
    """Detects and extracts parameters from commands"""
    
    def __init__(self):
        # File extension patterns are now built dynamically in _find_file_parameters
        
        # Common placeholder patterns
        self.placeholder_patterns = [
            r'\{[^}]+\}',           # {INPUT_FILE}, {OUTPUT_DIR}
            r'<[^>]+>',             # <filename>, <path>
            r'\[[^\]]+\]',          # [input], [output]
            r'\$\w+',               # $INPUT, $OUTPUT
        ]
        
        # File path patterns (likely to be customized)
        self.path_patterns = [
            r'(?:^|\s)(/[^\s]+)',              # Absolute paths
            r'(?:^|\s)(\.{1,2}/[^\s]+)',       # Relative paths
            r'(?:^|\s)([^\s]+/[^\s]*)',        # Directory-like paths
            r'(?:^|\s)(input|output|src|dest|source|destination)(?=\s|$)',  # Common words
        ]
        
        # Common option flags that imply parameters
        self.option_flags = {
            '-i': 'Input', '--input': 'Input', '--in': 'Input',
            '-o': 'Output', '--output': 'Output', '--out': 'Output',
            '--frame': 'Frame', '--frame-number': 'Frame', '-n': 'Frame',
            '--time': 'Time', '-ss': 'Start Time', '-to': 'End Time',
            '--fps': 'FPS', '--rate': 'FPS',
            '--width': 'Width', '--height': 'Height', '-s': 'Size'
        }
    
    def detect_parameters(self, command: str) -> List[Parameter]:
        """Detect all parameters in a command"""
        parameters = []
        
        # Find file extensions
        parameters.extend(self._find_file_parameters(command))
        
        # Find placeholders
        parameters.extend(self._find_placeholder_parameters(command))
        
        # Find potential file paths
        parameters.extend(self._find_path_parameters(command))
        
        # Find option-style parameters (e.g., -i input.mp4, --frame 123, --out=out.png)
        parameters.extend(self._find_option_parameters(command))
        
        # Find timecodes and standalone numeric parameters in common contexts
        parameters.extend(self._find_time_and_numeric_parameters(command))
        
        # Remove duplicates and overlaps
        parameters = self._deduplicate_parameters(parameters)
        
        # Sort by position
        parameters.sort(key=lambda p: p.start_pos)
        
        return parameters

    # Removed: quote handling now done at pattern level
    
    def _find_file_parameters(self, command: str) -> List[Parameter]:
        """Find file parameters by extension with proper quote handling"""
        parameters = []
        
        # Extension groups for building patterns
        ext_groups = [
            '(mp4|avi|mkv|mov|wmv|flv|webm|m4v)',  # Video
            '(mp3|wav|flac|aac|ogg|m4a)',          # Audio  
            '(jpg|jpeg|png|gif|bmp|svg|webp)',     # Image
            '(txt|md|doc|docx|pdf|rtf)',           # Document
            '(csv|json|xml|yaml|yml)',             # Data
            '(py|js|html|css|cpp|java|go)',        # Code
            '(tar|zip|gz|bz2|xz|7z)'              # Archive
        ]
        
        for ext_group in ext_groups:
            # Pattern 1: Quoted filenames "filename.ext" or 'filename.ext'
            quoted_pattern = f'["\']([^"\'\\s]+\\.{ext_group})["\']'
            for match in re.finditer(quoted_pattern, command, re.IGNORECASE):
                filename = match.group(1)  # Inner filename without quotes
                start_pos = match.start(1)  # Position of inner content
                end_pos = match.end(1)      # End of inner content
                
                ext = Path(filename).suffix.lower()
                param = Parameter(
                    name=f"File ({ext})",
                    original_value=filename,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    param_type='file',
                    suggestions=self._get_file_suggestions(filename),
                    description=f"{self._get_file_type(ext).title()} file ({ext})"
                )
                parameters.append(param)
            
            # Pattern 2: Unquoted filenames - explicitly avoid quoted content
            unquoted_pattern = f'(?<!["\'])\\b([^\\s"\']+\\.{ext_group})\\b(?!["\'])'
            for match in re.finditer(unquoted_pattern, command, re.IGNORECASE):
                filename = match.group(1)
                start_pos = match.start(1)
                end_pos = match.end(1)
                
                # Double-check: skip if overlaps with any existing parameter
                overlaps = any(
                    not (end_pos <= p.start_pos or start_pos >= p.end_pos)
                    for p in parameters
                )
                if overlaps:
                    continue
                
                ext = Path(filename).suffix.lower()
                param = Parameter(
                    name=f"File ({ext})",
                    original_value=filename,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    param_type='file',
                    suggestions=self._get_file_suggestions(filename),
                    description=f"{self._get_file_type(ext).title()} file ({ext})"
                )
                parameters.append(param)
        
        return parameters
    
    def _find_placeholder_parameters(self, command: str) -> List[Parameter]:
        """Find placeholder parameters like {INPUT}, <file>, [path]"""
        parameters = []
        
        for pattern in self.placeholder_patterns:
            for match in re.finditer(pattern, command):
                placeholder = match.group(0)
                
                # Extract the name from the placeholder
                name = re.sub(r'[{}<>\[\]$]', '', placeholder).replace('_', ' ').title()
                
                # Get suggestions based on the placeholder content
                suggestions = self._get_placeholder_suggestions(placeholder)
                
                param = Parameter(
                    name=name,
                    original_value=placeholder,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    param_type='placeholder',
                    suggestions=suggestions,
                    description=f"Parameter: {name}"
                )
                parameters.append(param)
        
        return parameters
    
    def _find_path_parameters(self, command: str) -> List[Parameter]:
        """Find potential file path parameters"""
        parameters = []
        
        # Look for common parameter words followed by paths
        path_keywords = r'\b(input|output|src|dest|source|destination|file|path|dir|directory)\b'
        
        # Find keyword + potential path combinations
        pattern = f'{path_keywords}\\s+([^\\s]+)'
        for match in re.finditer(pattern, command, re.IGNORECASE):
            keyword = match.group(1)
            # Get the captured path
            p_start = match.start(2)
            p_end = match.end(2)
            path_value = command[p_start:p_end]
            
            # Skip if it's already covered by file extension matching
            if any(ext_pattern in path_value.lower() for ext_pattern in ['.mp4', '.txt', '.jpg']):
                continue
            
            suggestions = self._get_path_suggestions(path_value)
            
            param = Parameter(
                name=keyword.title(),
                original_value=path_value,
                start_pos=p_start,
                end_pos=p_end,
                param_type='path',
                suggestions=suggestions,
                description=f"{keyword.title()} path"
            )
            parameters.append(param)
        
        return parameters

    def _find_option_parameters(self, command: str) -> List[Parameter]:
        """Find parameters provided via common CLI flags with robust quoting support."""
        parameters: List[Parameter] = []
        if not self.option_flags:
            return parameters
        # Build regex for flags
        import re as _re
        flags = sorted(self.option_flags.keys(), key=len, reverse=True)
        flag_alt = '|'.join(_re.escape(f) for f in flags)
        # --key=value
        pattern_eq = _re.compile(rf'(?P<flag>{flag_alt})=(?P<val>"[^"]+"|\'[^\']+\'|[^\s]+)')
        # --key value or -k value
        pattern_sp = _re.compile(rf'(?P<flag>{flag_alt})\s+(?P<val>"[^"]+"|\'[^\']+\'|[^\s]+)')
        
        for m in pattern_eq.finditer(command):
            flag = m.group('flag')
            name = self.option_flags.get(flag, flag.lstrip('-').replace('-', ' ').title())
            v_start, v_end = m.start('val'), m.end('val')
            value = command[v_start:v_end]
            parameters.append(Parameter(
                name=name,
                original_value=value,
                start_pos=v_start,
                end_pos=v_end,
                param_type='option',
                suggestions=self._suggest_for_option(name, value),
                description=f"{name} option"
            ))
        for m in pattern_sp.finditer(command):
            flag = m.group('flag')
            name = self.option_flags.get(flag, flag.lstrip('-').replace('-', ' ').title())
            v_start, v_end = m.start('val'), m.end('val')
            value = command[v_start:v_end]
            parameters.append(Parameter(
                name=name,
                original_value=value,
                start_pos=v_start,
                end_pos=v_end,
                param_type='option',
                suggestions=self._suggest_for_option(name, value),
                description=f"{name} option"
            ))
        return parameters
    
    def _find_time_and_numeric_parameters(self, command: str) -> List[Parameter]:
        """Find timecodes and numeric values likely to be tunable parameters"""
        parameters: List[Parameter] = []
        
        # Timecodes like 00:01:23 or 00:01:23.456
        for match in re.finditer(r'\b\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\b', command):
            value = match.group(0)
            param = Parameter(
                name='Time',
                original_value=value,
                start_pos=match.start(),
                end_pos=match.end(),
                param_type='option',
                suggestions=['00:00:01', '00:00:10', '00:01:00'],
                description='Time position'
            )
            parameters.append(param)
        
        # Frame numbers in common patterns (n=123, frame 123, --frame 123)
        for match in re.finditer(r'(?:\bframe\b\s*[=:]?\s*(\d+))|(?:\bn\s*=\s*(\d+))', command, re.IGNORECASE):
            value = next((g for g in match.groups() if g), None)
            if not value:
                continue
            param = Parameter(
                name='Frame',
                original_value=value,
                start_pos=match.start(),
                end_pos=match.start() + len(match.group(0)),
                param_type='option',
                suggestions=['1', '10', '100'],
                description='Frame number'
            )
            parameters.append(param)
        
        return parameters
    
    def _suggest_for_option(self, name: str, current_value: str) -> List[str]:
        """Provide simple suggestions based on option name"""
        suggestions: List[str] = []
        lower = name.lower()
        if 'input' in lower:
            suggestions = self._get_file_suggestions(current_value)
        elif 'output' in lower:
            suggestions = self._get_file_suggestions(current_value)
        elif lower in ['frame']:
            suggestions = ['1', '10', '100', current_value]
        elif 'time' in lower or 'start' in lower or 'end' in lower:
            suggestions = ['00:00:01', '00:00:10', '00:01:00']
        elif lower in ['fps', 'rate']:
            suggestions = ['24', '30', '60']
        elif lower in ['width', 'height']:
            suggestions = ['640', '720', '1080']
        elif lower == 'size':
            suggestions = ['1280x720', '1920x1080']
        return list(dict.fromkeys(suggestions))
    
    def _deduplicate_parameters(self, parameters: List[Parameter]) -> List[Parameter]:
        """Remove overlapping parameters, keeping the most specific ones"""
        if not parameters:
            return parameters
        
        # Sort by start position
        sorted_params = sorted(parameters, key=lambda p: p.start_pos)
        result = []
        
        for param in sorted_params:
            # Check if this parameter overlaps with any existing ones
            overlaps = False
            for existing in result:
                if (param.start_pos < existing.end_pos and param.end_pos > existing.start_pos):
                    overlaps = True
                    # Keep the more specific one (file > placeholder > path)
                    specificity = {'file': 3, 'placeholder': 2, 'path': 1}
                    if specificity.get(param.param_type, 0) > specificity.get(existing.param_type, 0):
                        result.remove(existing)
                        result.append(param)
                    break
            
            if not overlaps:
                result.append(param)
        
        return result
    
    def _get_file_suggestions(self, filename: str) -> List[str]:
        """Get file suggestions based on current directory"""
        suggestions = []
        
        try:
            # Get file extension
            ext = Path(filename).suffix
            
            # Find files with same extension in current directory
            pattern = f"*{ext}"
            matches = glob.glob(pattern)
            suggestions.extend(matches[:5])  # Limit to 5 suggestions
            
            # Add some common variations
            if ext.lower() in ['.mp4', '.avi', '.mkv']:
                suggestions.extend(['input.mp4', 'output.mp4', 'video.mp4'])
            elif ext.lower() in ['.txt', '.md']:
                suggestions.extend(['README.md', 'input.txt', 'output.txt'])
            
        except Exception:
            pass
        
        return list(set(suggestions))  # Remove duplicates
    
    def _get_placeholder_suggestions(self, placeholder: str) -> List[str]:
        """Get suggestions for placeholder parameters"""
        suggestions = []
        
        placeholder_lower = placeholder.lower()
        
        if any(word in placeholder_lower for word in ['input', 'source', 'src']):
            suggestions.extend(['input.txt', 'source.mp4', 'data.csv'])
        elif any(word in placeholder_lower for word in ['output', 'dest', 'destination']):
            suggestions.extend(['output.txt', 'result.mp4', 'processed.csv'])
        elif 'file' in placeholder_lower:
            suggestions.extend(['file.txt', 'document.pdf', 'data.json'])
        elif any(word in placeholder_lower for word in ['dir', 'directory', 'path']):
            suggestions.extend(['./', '../', '/tmp/', './output/'])
        
        return suggestions
    
    def _get_path_suggestions(self, path_value: str) -> List[str]:
        """Get suggestions for path parameters"""
        suggestions = []
        
        try:
            # If it looks like a directory, suggest directories
            if path_value.endswith('/') or 'dir' in path_value.lower():
                dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
                suggestions.extend(dirs[:5])
                suggestions.extend(['./', '../', '/tmp/'])
            else:
                # Suggest files
                files = [f for f in os.listdir('.') if os.path.isfile(f)]
                suggestions.extend(files[:5])
        
        except Exception:
            pass
        
        return suggestions
    
    def _get_file_type(self, ext: str) -> str:
        """Get file type category from extension"""
        ext = ext.lower()
        
        if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']:
            return 'video'
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
            return 'audio'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']:
            return 'image'
        elif ext in ['.txt', '.md', '.doc', '.docx', '.pdf', '.rtf']:
            return 'document'
        elif ext in ['.csv', '.json', '.xml', '.yaml', '.yml']:
            return 'data'
        elif ext in ['.py', '.js', '.html', '.css', '.cpp', '.java', '.go']:
            return 'code'
        elif ext in ['.tar', '.zip', '.gz', '.bz2', '.xz', '.7z']:
            return 'archive'
        else:
            return 'file'
    
    def enhance_file_suggestions(self, current_value: str) -> List[str]:
        """Get enhanced file suggestions including clipboard content"""
        suggestions = []
        
        try:
            # Try to get clipboard content
            import pyperclip
            clipboard_content = pyperclip.paste().strip()
            
            # If clipboard contains a file path, suggest it
            if clipboard_content and ('/' in clipboard_content or '.' in clipboard_content):
                if len(clipboard_content) < 200:  # Reasonable file path length
                    suggestions.append(f"📋 {clipboard_content}")
        except:
            pass
        
        # Add current directory files based on extension
        try:
            import os
            from pathlib import Path
            
            current_ext = Path(current_value).suffix.lower()
            if current_ext:
                # Find files with same extension
                files = [f for f in os.listdir('.') if f.lower().endswith(current_ext)]
                suggestions.extend(files[:3])
            
            # Add common directories
            dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
            suggestions.extend([f"{d}/" for d in dirs[:2]])
            
        except:
            pass
        
        return suggestions[:8]  # Limit to 8 suggestions


class ParameterCustomizer:
    """Handles parameter customization UI"""
    
    def __init__(self, console, llm_client=None, user_task: Optional[str] = None, preset_parameters: Optional[List[Dict]] = None):
        self.console = console
        self.detector = ParameterDetector()
        self.llm_client = llm_client
        self.user_task = user_task or ""
        self.preset_parameters = preset_parameters or []
    
    def customize_command(self, command: str) -> Optional[str]:
        """Launch navigable parameter customization interface"""
        parameters = self.detector.detect_parameters(command)
        
        # Merge in preset parameters from LLM (if provided with the command)
        try:
            if self.preset_parameters:
                for p in self.preset_parameters:
                    start = p.get('spanStart')
                    end = p.get('spanEnd')
                    original_value = command[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(command) else (p.get('original_value') or p.get('name'))
                    parameters.append(Parameter(
                        name=(p.get('name') or 'Parameter'),
                        original_value=original_value,
                        start_pos=start if isinstance(start, int) else 0,
                        end_pos=end if isinstance(end, int) else 0,
                        param_type='option',
                        suggestions=p.get('suggestions') or [],
                        description=(p.get('description') or (p.get('role') or 'Parameter'))
                    ))
                parameters = self.detector._deduplicate_parameters(parameters)
                parameters.sort(key=lambda p: p.start_pos)
        except Exception:
            pass
        
        # Avoid a second LLM call here to keep Enter-to-customize fast.
        # Only if nothing at all was found and no preset parameters exist, fallback to LLM (best-effort).
        try:
            if not parameters and not self.preset_parameters and self.llm_client and self.user_task:
                llm_params = self.llm_client.ask_for_parameters(self.user_task, command)
                for p in llm_params:
                    start = p.get('spanStart')
                    end = p.get('spanEnd')
                    original_value = command[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(command) else p.get('name')
                    parameters.append(Parameter(
                        name=p.get('name') or 'Parameter',
                        original_value=original_value,
                        start_pos=start if isinstance(start, int) else 0,
                        end_pos=end if isinstance(end, int) else 0,
                        param_type='option',
                        suggestions=p.get('suggestions') or [],
                        description=p.get('description') or (p.get('role') or 'Parameter')
                    ))
                if parameters:
                    parameters = self.detector._deduplicate_parameters(parameters)
                    parameters.sort(key=lambda p: p.start_pos)
        except Exception:
            pass
        
        if not parameters:
            self.console.print("[yellow]No customizable parameters detected[/yellow]")
            input("Press Enter to continue...")
            return command
        
        # Enter parameter navigation mode
        return self._navigate_parameters(command, parameters)
    
    def _navigate_parameters(self, command: str, parameters: List[Parameter]) -> Optional[str]:
        """Navigate parameters with arrow keys like command selection"""
        selected_param_index = 0
        new_values = {}
        paste_buffer = None  # Holds paste content when detected
        
        # Hide cursor
        import sys
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        
        try:
            while True:
                # Clear terminal
                import os
                os.system('clear')
                
                # Show parameter selection interface
                self._display_parameter_interface(command, parameters, selected_param_index, new_values)
                
                # Get user input
                # Enable bracketed paste mode around key reads
                sys.stdout.write("\x1b[?2004h")  # Enable bracketed paste
                sys.stdout.flush()
                key = self._get_key()
                sys.stdout.write("\x1b[?2004l")  # Disable bracketed paste
                sys.stdout.flush()
                
                # Handle navigation
                if key in ['q', '\x1b', '\x03']:  # q, Esc, or Ctrl+C - go back
                    return None
                elif key == '\t':  # Tab - next parameter
                    selected_param_index = (selected_param_index + 1) % len(parameters)
                elif key == '\x1b[Z':  # Shift+Tab - previous parameter (hidden but functional)
                    selected_param_index = (selected_param_index - 1) % len(parameters)
                elif key == '\r':  # Enter - EXECUTE with current values
                    break
                elif key == 'c':  # c - copy customized command and EXIT
                    # Apply changes and copy to clipboard
                    final_command = self._apply_parameter_changes(command, parameters, new_values) if new_values else command
                    try:
                        import pyperclip
                        pyperclip.copy(final_command)
                        self.console.print(f"\n[green]✓ Copied:[/green] [cyan]{final_command}[/cyan]")
                    except ImportError:
                        self.console.print("\n[red]Error: pyperclip not available for clipboard operations[/red]")
                    finally:
                        import sys
                        sys.exit(0)
                elif key == 'v':  # v - paste clipboard into selected parameter
                    clipboard_content = self._get_clipboard_content()
                    if clipboard_content:
                        new_values[selected_param_index] = clipboard_content.strip()
                elif isinstance(key, tuple) and key and key[0] == '__PASTE__':
                    # key is ('__PASTE__', pasted_text)
                    pasted_text = key[1] if len(key) > 1 else ''
                    if pasted_text:
                        new_values[selected_param_index] = pasted_text
                elif key.isprintable() and len(key) == 1:
                    # Regular typing - enter edit mode with current value prefilled
                    current_param = parameters[selected_param_index]
                    if selected_param_index in new_values:
                        # Use the user's edited value
                        current_value_for_edit = new_values[selected_param_index]
                    else:
                        # Use the inner content from the original command (excluding quotes)
                        current_value_for_edit = current_param.original_value
                    new_value = self._edit_parameter_value(current_param, current_value_for_edit, key, full_command=command)
                    if new_value is not None:
                        if new_value != current_param.original_value:
                            new_values[selected_param_index] = new_value
                        elif selected_param_index in new_values:
                            # Remove if reverting to original
                            del new_values[selected_param_index]
                    
        finally:
            # Show cursor
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
        
        # Apply changes and return final command
        if new_values:
            return self._apply_parameter_changes(command, parameters, new_values)
        else:
            return command
    
    def _display_parameter_interface(self, command: str, parameters: List[Parameter], selected_index: int, new_values: dict):
        """Display streamlined command interface with tab navigation"""
        from rich.text import Text
        
        # Create the live command preview
        preview_command = self._build_live_command(command, parameters, new_values, selected_index)
        
        self.console.print(f"[bold cyan]Command:[/bold cyan]")
        self.console.print(preview_command)
        self.console.print()
        
        # Show help (simplified)
        help_items = [
            Text("Tab", style="dim") + Text(" next parameter", style="white"),
            Text("v/Cmd+V", style="dim") + Text(" paste clipboard", style="yellow"),
            Text("Type", style="dim") + Text(" edit", style="green"),
            Text("c", style="dim") + Text(" copy", style="blue"),
            Text("Enter", style="dim") + Text(" execute", style="cyan"),
            Text("Esc", style="dim") + Text(" back", style="red")
        ]
        
        help_line = Text("  ")
        for i, item in enumerate(help_items):
            if i > 0:
                help_line.append("  ")
            help_line.append_text(item)
        self.console.print(help_line)
    
    def _build_live_command(self, command: str, parameters: List[Parameter], new_values: dict, selected_index: int) -> Text:
        """Build live command preview with highlighting"""
        # Build the current command with all changes applied
        current_command = self._apply_parameter_changes(command, parameters, new_values) if new_values else command
        
        # Create highlighted version by rebuilding with colors
        result = Text()
        last_end = 0
        
        # Calculate actual positions in the modified command
        # We need to apply changes incrementally and track real positions
        working_params = []
        temp_command = command
        position_map = {}  # Maps parameter index to (start, end) in modified command
        
        # Sort parameters by original position (right to left for position stability)
        sorted_param_indices = sorted(range(len(parameters)), key=lambda i: parameters[i].start_pos)
        
        # Apply changes one by one and track positions
        for idx in sorted_param_indices:
            param = parameters[idx]
            current_value = new_values.get(idx, param.original_value)
            
            # Find where this parameter's original position maps to in temp_command
            # by calculating cumulative offset from all previous changes
            offset = 0
            for prev_idx in sorted_param_indices:
                if prev_idx >= idx:
                    break
                prev_param = parameters[prev_idx]
                prev_value = new_values.get(prev_idx, prev_param.original_value)
                if prev_param.start_pos < param.start_pos:
                    offset += len(prev_value) - len(prev_param.original_value)
            
            actual_start = param.start_pos + offset
            actual_end = actual_start + len(current_value)
            position_map[idx] = (actual_start, actual_end)
            working_params.append((idx, current_value, actual_start, actual_end))
        
        # Sort by actual position in modified command for rendering
        working_params.sort(key=lambda x: x[2])
        
        # Build the highlighted text
        for idx, current_value, start_pos, end_pos in working_params:
            # Add text before this parameter
            if start_pos > last_end:
                result.append(current_command[last_end:start_pos], style="white")
            
            # Add the parameter with appropriate highlighting
            if idx == selected_index:
                # Currently selected parameter - very prominent highlight
                if idx in new_values:
                    result.append(current_value, style="bold white on blue")
                else:
                    result.append(current_value, style="bold white on green") 
            else:
                # Other parameters - subtle highlight
                if idx in new_values:
                    result.append(current_value, style="yellow")
                else:
                    result.append(current_value, style="cyan")
            
            last_end = end_pos
        
        # Add remaining text after the last parameter
        if last_end < len(current_command):
            result.append(current_command[last_end:], style="white")
        
        return result
    
    def _edit_parameter_inline(self, param: Parameter, first_char: str) -> Optional[str]:
        """Edit a parameter inline with the first character already typed"""
        # Get enhanced suggestions
        enhanced_suggestions = self.detector.enhance_file_suggestions(param.original_value)
        all_suggestions = enhanced_suggestions + param.suggestions
        unique_suggestions = []
        seen = set()
        for suggestion in all_suggestions:
            if suggestion not in seen:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
        
        # Setup readline with suggestions
        import readline
        readline.clear_history()
        for suggestion in unique_suggestions[:10]:
            readline.add_history(suggestion.replace('📋 ', ''))
        
        try:
            # Show cursor and enable input mode
            import sys
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
            
            # Create minimal inline edit prompt
            self.console.print()
            self.console.print(f"[bold yellow]Edit {param.name}:[/bold yellow] ", end="")
            
            # Show suggestions inline if available
            if unique_suggestions:
                suggestion_text = " | ".join(unique_suggestions[:3])
                self.console.print(f"[dim]({suggestion_text})[/dim]")
                self.console.print("> ", end="")
            else:
                self.console.print()
                self.console.print("> ", end="")
            
            # Start with the first character typed
            readline.set_startup_hook(lambda: readline.insert_text(first_char))
            new_value = input().strip()
            readline.set_startup_hook()
            
            return new_value if new_value else param.original_value
            
        except (EOFError, KeyboardInterrupt):
            return None
        finally:
            # Hide cursor again
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
    
    def _edit_parameter_value(self, param: Parameter, prefill_value: str, first_char: str, full_command: Optional[str] = None) -> Optional[str]:
        """Edit a parameter with the input prefilled with its current value, then first_char appended."""
        # Setup readline with suggestions
        enhanced_suggestions = self.detector.enhance_file_suggestions(param.original_value)
        all_suggestions = enhanced_suggestions + param.suggestions
        unique_suggestions = []
        seen = set()
        for suggestion in all_suggestions:
            if suggestion not in seen:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
        
        import readline
        readline.clear_history()
        for suggestion in unique_suggestions[:10]:
            readline.add_history(suggestion.replace('📋 ', ''))
        
        # Show cursor and enable input mode
        import sys
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        
        try:
            self.console.print()
            self.console.print(f"[bold yellow]Edit {param.name}:[/bold yellow] ", end="")
            if unique_suggestions:
                suggestion_text = " | ".join(unique_suggestions[:3])
                self.console.print(f"[dim]({suggestion_text})[/dim]")
                self.console.print("> ", end="")
            else:
                self.console.print()
                self.console.print("> ", end="")
            
            # Ensure no pending keypress (like the triggering key) remains in buffer
            try:
                self._drain_buffer()
            except Exception:
                pass

            # Use pre_input_hook (more reliable than startup_hook) to prefill once
            def pre_input_hook():
                try:
                    # With corrected parameter detection, prefill_value should be clean
                    readline.insert_text(prefill_value)
                    readline.redisplay()
                finally:
                    # Remove hook immediately so it doesn't run twice
                    readline.set_pre_input_hook(None)
            readline.set_pre_input_hook(pre_input_hook)
            new_value = input().strip()
            
            return new_value if new_value else param.original_value
        except (EOFError, KeyboardInterrupt):
            return None
        finally:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()

    def _edit_parameter_with_paste_support(self, param: Parameter, first_char: str) -> Optional[str]:
        """Edit a parameter with better paste support"""
        import sys
        import select
        import termios
        import tty
        
        # Check if there's more input waiting (indicates paste operation)
        additional_input = ""
        if sys.stdin.isatty():
            try:
                # Check for more characters with a very short timeout
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    # Read any additional buffered input
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(fd)
                        # Read up to 1000 characters of buffered input
                        for _ in range(1000):
                            if select.select([sys.stdin], [], [], 0.001)[0]:
                                char = sys.stdin.read(1)
                                if char and char.isprintable():
                                    additional_input += char
                                else:
                                    break
                            else:
                                break
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except:
                pass
        
        # Combine first character with any additional pasted content
        initial_text = first_char + additional_input
        
        # Get enhanced suggestions
        enhanced_suggestions = self.detector.enhance_file_suggestions(param.original_value)
        all_suggestions = enhanced_suggestions + param.suggestions
        unique_suggestions = []
        seen = set()
        for suggestion in all_suggestions:
            if suggestion not in seen:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
        
        # Setup readline with suggestions
        import readline
        readline.clear_history()
        for suggestion in unique_suggestions[:10]:
            readline.add_history(suggestion.replace('📋 ', ''))
        
        try:
            # Show cursor and enable input mode
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
            
            # Create minimal inline edit prompt
            self.console.print()
            self.console.print(f"[bold yellow]Edit {param.name}:[/bold yellow] ", end="")
            
            # Show suggestions inline if available
            if unique_suggestions:
                suggestion_text = " | ".join(unique_suggestions[:3])
                self.console.print(f"[dim]({suggestion_text})[/dim]")
                self.console.print("> ", end="")
            else:
                self.console.print()
                self.console.print("> ", end="")
            
            # Pre-fill with the initial text (first char + any pasted content)
            if initial_text:
                readline.set_startup_hook(lambda: readline.insert_text(initial_text))
            
            new_value = input().strip()
            readline.set_startup_hook()
            
            return new_value if new_value else param.original_value
            
        except (EOFError, KeyboardInterrupt):
            return None
        finally:
            # Hide cursor again
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
    
    def _get_clipboard_content(self) -> Optional[str]:
        """Get clipboard content safely"""
        try:
            import pyperclip
            content = pyperclip.paste()
            return content if content else None
        except ImportError:
            return None

    # Removed: we keep parameter spans as inner-only for accurate editing
    
    def _drain_buffer(self):
        """Drain all remaining characters from input buffer (deterministic)"""
        import sys
        import select
        import termios
        import tty
        
        if not sys.stdin.isatty():
            return
        
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                # Read all available characters immediately
                while select.select([sys.stdin], [], [], 0)[0]:  # No timeout - immediate check
                    try:
                        sys.stdin.read(1)
                    except:
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except:
            pass
    
    def _get_key(self):
        """Get a single keypress, detecting paste operations (bracketed paste)"""
        import sys
        import tty
        import termios
        import select
        
        if not sys.stdin.isatty():
            return input()
        
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setraw(fd)
            
            key = sys.stdin.read(1)
            
            # Detect xterm bracketed paste: ESC [ 2 0 0 ~ ... ESC [ 2 0 1 ~
            if key == '\x1b':  # ESC
                # Peek next two to check for '[' '2'
                old_timeout = termios.tcgetattr(fd)
                try:
                    new_settings = old_timeout[:]
                    new_settings[6][termios.VMIN] = 0
                    new_settings[6][termios.VTIME] = 1  # 0.1s
                    termios.tcsetattr(fd, termios.TCSANOW, new_settings)
                    seq = sys.stdin.read(1)
                    if seq == '[':
                        seq += sys.stdin.read(1)
                        if seq.endswith('2'):
                            # Read remaining '00~'
                            seq += sys.stdin.read(3)
                            if seq == '[200~':
                                # Start of paste: read until ESC [ 2 0 1 ~
                                pasted = []
                                while True:
                                    ch = sys.stdin.read(1)
                                    if ch == '\x1b':
                                        # Possible end sequence
                                        maybe = sys.stdin.read(1)
                                        if maybe == '[':
                                            tail = sys.stdin.read(4)  # '201~'
                                            if tail == '201~':
                                                break
                                            else:
                                                # Not end, include and continue
                                                pasted.append('\x1b' + '[' + tail)
                                        else:
                                            pasted.append('\x1b' + maybe)
                                    else:
                                        pasted.append(ch)
                                return ('__PASTE__', ''.join(pasted))
                finally:
                    termios.tcsetattr(fd, termios.TCSANOW, old_timeout)
            
            # Handle escape sequences (arrow keys) if not paste
            if key == '\x1b':
                # Try to read more characters with very short timeout
                old_timeout = termios.tcgetattr(fd)
                try:
                    # Set very short timeout for detecting escape sequences
                    new_settings = old_timeout[:]
                    new_settings[6][termios.VMIN] = 0
                    new_settings[6][termios.VTIME] = 1  # 0.1 second timeout
                    termios.tcsetattr(fd, termios.TCSANOW, new_settings)
                    
                    next_chars = sys.stdin.read(2)
                    if len(next_chars) >= 2:
                        key += next_chars
                    else:
                        # Just Esc key by itself
                        return '\x1b'
                finally:
                    # Restore original settings
                    termios.tcsetattr(fd, termios.TCSANOW, old_timeout)
            
            # Check if more characters are immediately available (paste detection)
            elif key.isprintable():
                if select.select([sys.stdin], [], [], 0)[0]:
                    # More characters available - might be paste
                    all_chars = key
                    # Read all immediately available characters
                    while select.select([sys.stdin], [], [], 0)[0]:
                        try:
                            char = sys.stdin.read(1)
                            if char.isprintable():
                                all_chars += char
                            else:
                                break
                        except:
                            break
                    
                    # Check if this matches clipboard content
                    clipboard = self._get_clipboard_content()
                    if clipboard and all_chars == clipboard[:len(all_chars)] and len(all_chars) > 1:
                        return '__PASTE__'  # Special signal for paste
                    else:
                        # Not a paste or doesn't match - return first char only
                        # Put back the extra chars (this is tricky, so just return first char)
                        return key
            
            return key
            
        except (termios.error, OSError):
            return input()
        except KeyboardInterrupt:
            return '\x03'  # Return Ctrl+C
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except:
                pass
    
    def _apply_parameter_changes(self, command: str, parameters: List[Parameter], changes: Dict[int, str]) -> str:
        """Apply parameter changes to the command string"""
        # Apply changes from right to left to maintain positions
        modified_command = command
        
        for i in sorted(changes.keys(), reverse=True):
            param = parameters[i]
            new_value = changes[i]
            
            # Since parameter spans are inner-only (excluding quotes), 
            # we only replace the inner content, preserving existing quotes
            start, end = param.start_pos, param.end_pos
            
            # Replace the parameter in the command
            modified_command = (
                modified_command[:param.start_pos] + 
                new_value + 
                modified_command[param.end_pos:]
            )
        
        return modified_command
