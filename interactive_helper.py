"""
Helper methods for the interactive selector.
"""

from typing import List
from rich.text import Text
from parameters import Parameter


def highlight_parameters(command: str, parameters: List[Parameter], base_style: str = "white") -> Text:
    """Highlight parameters in a command string"""
    if not parameters:
        return Text(command, style=base_style)
    
    result = Text()
    last_end = 0
    
    for param in parameters:
        highlight_start = param.start_pos
        highlight_end = param.end_pos
        # Do NOT include surrounding quotes in visual highlight; show only inner value
        if highlight_start > last_end:
            result.append(command[last_end:highlight_start], style=base_style)
        param_style = "bold yellow" if base_style == "bold green" else "yellow"
        result.append(command[highlight_start:highlight_end], style=param_style)
        last_end = highlight_end
    
    # Add remaining text after the last parameter
    if last_end < len(command):
        result.append(command[last_end:], style=base_style)
    
    return result
