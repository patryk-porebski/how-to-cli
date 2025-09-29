"""Real-time output streaming for command execution"""

import subprocess
import threading
import queue
import time
from typing import Iterator, Optional, Callable
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel

from logger import get_logger


class StreamingExecutor:
    """Executes commands with real-time output streaming"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = get_logger(self.__class__.__name__)
    
    def execute_with_streaming(self, command: str, working_directory: Optional[str] = None,
                             timeout: Optional[int] = None) -> tuple[bool, str, str]:
        """
        Execute command with real-time output streaming
        
        Returns:
            tuple of (success, stdout, stderr)
        """
        
        try:
            self.logger.debug(f"Starting streaming execution: {command}")
            
            # Create process
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                cwd=working_directory
            )
            
            # Queues for output
            stdout_queue = queue.Queue()
            stderr_queue = queue.Queue()
            
            # Threads for reading output
            stdout_thread = threading.Thread(
                target=self._read_output,
                args=(process.stdout, stdout_queue, "stdout")
            )
            stderr_thread = threading.Thread(
                target=self._read_output,
                args=(process.stderr, stderr_queue, "stderr")
            )
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Display output in real-time
            stdout_lines = []
            stderr_lines = []
            
            with Live(self._create_output_panel("", ""), refresh_per_second=10, console=self.console) as live:
                start_time = time.time()
                
                while process.poll() is None:
                    # Check for timeout
                    if timeout and (time.time() - start_time) > timeout:
                        process.terminate()
                        process.wait(timeout=5)
                        raise subprocess.TimeoutExpired(command, timeout)
                    
                    # Read available output
                    self._read_queued_output(stdout_queue, stdout_lines)
                    self._read_queued_output(stderr_queue, stderr_lines)
                    
                    # Update display
                    live.update(self._create_output_panel(
                        '\n'.join(stdout_lines[-20:]),  # Show last 20 lines
                        '\n'.join(stderr_lines[-20:])
                    ))
                    
                    time.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
                # Read any remaining output
                self._read_queued_output(stdout_queue, stdout_lines)
                self._read_queued_output(stderr_queue, stderr_lines)
                
                # Final update
                live.update(self._create_output_panel(
                    '\n'.join(stdout_lines[-20:]),
                    '\n'.join(stderr_lines[-20:])
                ))
            
            # Wait for process to complete
            return_code = process.returncode
            
            # Join threads
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            # Combine output
            full_stdout = '\n'.join(stdout_lines)
            full_stderr = '\n'.join(stderr_lines)
            
            success = return_code == 0
            self.logger.debug(f"Command completed with return code {return_code}")
            
            return success, full_stdout, full_stderr
            
        except subprocess.TimeoutExpired as e:
            self.logger.warning(f"Command timed out: {command}")
            return False, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            self.logger.error(f"Error in streaming execution: {e}")
            return False, "", str(e)
    
    def _read_output(self, pipe, output_queue: queue.Queue, stream_name: str):
        """Read output from pipe and put in queue"""
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    output_queue.put(line.rstrip('\n\r'))
            pipe.close()
        except Exception as e:
            self.logger.debug(f"Error reading {stream_name}: {e}")
    
    def _read_queued_output(self, output_queue: queue.Queue, lines: list):
        """Read all available lines from queue"""
        try:
            while True:
                line = output_queue.get_nowait()
                lines.append(line)
        except queue.Empty:
            pass
    
    def _create_output_panel(self, stdout: str, stderr: str) -> Panel:
        """Create output panel for display"""
        content = Text()
        
        if stdout:
            content.append("📤 Output:\n", style="bold green")
            content.append(stdout[-1000:], style="white")  # Limit display length
            content.append("\n\n")
        
        if stderr:
            content.append("⚠️  Errors:\n", style="bold red")
            content.append(stderr[-1000:], style="red")
        
        if not stdout and not stderr:
            content.append("⏳ Waiting for output...", style="dim")
        
        return Panel(
            content,
            title="🖥️  Command Output",
            border_style="blue"
        )


class ProgressIndicator:
    """Shows progress for long-running operations"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = get_logger(self.__class__.__name__)
    
    def show_progress(self, operation_name: str, progress_callback: Callable[[], bool]):
        """
        Show progress indicator while operation runs
        
        Args:
            operation_name: Name of the operation
            progress_callback: Function that returns True when operation is complete
        """
        
        spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        spinner_index = 0
        
        with Live(console=self.console, refresh_per_second=10) as live:
            while not progress_callback():
                char = spinner_chars[spinner_index % len(spinner_chars)]
                spinner_index += 1
                
                text = Text()
                text.append(f"{char} ", style="cyan")
                text.append(operation_name, style="white")
                
                live.update(Panel(text, border_style="cyan"))
                time.sleep(0.1)
    
    def show_with_steps(self, steps: list, step_callback: Callable[[int], bool]):
        """
        Show progress with numbered steps
        
        Args:
            steps: List of step descriptions
            step_callback: Function called with step index, returns True when step is complete
        """
        
        with Live(console=self.console, refresh_per_second=10) as live:
            for i, step in enumerate(steps):
                # Show current step as in progress
                text = Text()
                text.append(f"Step {i+1}/{len(steps)}: ", style="bold cyan")
                text.append(step, style="white")
                text.append(" ⏳", style="yellow")
                
                live.update(Panel(text, border_style="cyan"))
                
                # Wait for step completion
                while not step_callback(i):
                    time.sleep(0.1)
                
                # Show step as completed
                text = Text()
                text.append(f"Step {i+1}/{len(steps)}: ", style="bold cyan")
                text.append(step, style="white")
                text.append(" ✅", style="green")
                
                live.update(Panel(text, border_style="green"))
                time.sleep(0.5)  # Brief pause to show completion
