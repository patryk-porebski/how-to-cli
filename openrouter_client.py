import requests
import json
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from logger import get_logger
from exceptions import APIError, ParseError
from constants import (
    DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE,
    API_TIMEOUT, SHELL_PROMPT_PATTERNS, COMMON_COMMAND_PREFIXES, GITHUB_URL, APP_NAME
)


@dataclass
class Command:
    """Represents a command to be executed"""
    command: str
    description: str
    working_directory: Optional[str] = None
    requires_confirmation: bool = True
    parameters: Optional[List[Dict[str, Any]]] = None  # LLM-extracted parameters (optional)


class OpenRouterClient:
    """Client for interacting with OpenRouter API"""
    
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, 
                 model: str = DEFAULT_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS, 
                 temperature: float = DEFAULT_TEMPERATURE, debug: bool = False):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.debug = debug
        self.logger = get_logger(self.__class__.__name__)
        
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
    
    def _make_api_request_with_retry(self, url: str, payload: Dict[str, Any], max_retries: int = 3) -> requests.Response:
        """Make API request with retry logic"""
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Making API request (attempt {attempt + 1}/{max_retries})")
                response = requests.post(
                    url,
                    headers=self._create_headers(),
                    json=payload,
                    timeout=API_TIMEOUT
                )
                return response
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    self.logger.error(f"API request timed out after {max_retries} attempts")
                    raise APIError(f"API request timed out after {API_TIMEOUT} seconds")
                self.logger.warning(f"API request timeout on attempt {attempt + 1}, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
            except requests.exceptions.ConnectionError as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Connection error after {max_retries} attempts: {e}")
                    raise APIError(f"Connection error: {e}")
                self.logger.warning(f"Connection error on attempt {attempt + 1}, retrying...")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request exception: {e}")
                raise APIError(f"Request error: {e}")
        
        raise APIError("Max retries exceeded")
    
    def _create_headers(self) -> Dict[str, str]:
        """Create headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": GITHUB_URL,
            "X-Title": APP_NAME
        }
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for command generation with parameters.

        Prefer strict JSON output. If JSON is not followed, legacy parsing will be used as a fallback.
        """
        return (
            "You generate shell commands with concise descriptions and user-facing parameters.\n"
            "Return STRICT JSON only, no extra text, using this schema: {\n"
            "  \"commands\": [{\n"
            "    \"command\": string,\n"
            "    \"description\": string,\n"
            "    \"parameters\": [{\n"
            "      \"name\": string,\n"
            "      \"role\": string,\n"
            "      \"description\": string,\n"
            "      \"spanStart\": integer|null,\n"
            "      \"spanEnd\": integer|null,\n"
            "      \"suggestions\": string[]\n"
            "    }]\n"
            "  }...]\n"
            "}\n"
            "Rules:\n"
            "- spanStart/spanEnd are 0-based indices into the command string if applicable.\n"
            "- Provide 1-5 helpful suggestions per parameter.\n"
            "- Keep description under 10 words.\n"
            "- macOS/Linux compatible commands.\n"
            "- NO text outside the JSON."
        )

    def ask_for_parameters(self, user_task: str, command: str) -> List[Dict[str, Any]]:
        """Use the LLM to extract user-facing parameters from a command.

        Returns a list of dicts with keys:
          - name: str
          - role: str (e.g., input, output, frame, time, option)
          - description: str
          - spanStart: int | null (index in command)
          - spanEnd: int | null (index in command, exclusive)
          - suggestions: List[str]
        """
        system_prompt = (
            "You extract customizable parameters from shell commands.\n"
            "Return ONLY strict JSON with the following schema: {\n"
            "  \"parameters\": [{\n"
            "    \"name\": string,\n"
            "    \"role\": string,\n"
            "    \"description\": string,\n"
            "    \"spanStart\": integer|null,\n"
            "    \"spanEnd\": integer|null,\n"
            "    \"suggestions\": string[]\n"
            "  }...]\n"
            "}\n"
            "Rules:\n"
            "- Use spanStart/spanEnd as 0-based indices into the provided command string when possible.\n"
            "- Prefer meaningful names (e.g., Input video, Frame number, Output image).\n"
            "- Include 1-5 useful suggestions per parameter.\n"
            "- Do NOT include any text before or after the JSON."
        )

        user_message = (
            f"Task: {user_task}\n"
            f"Command: {command}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": min(512, self.max_tokens),
            "temperature": min(0.4, self.temperature or 0.4),
        }

        response = self._make_api_request_with_retry(
            f"{self.base_url}/chat/completions",
            payload
        )
        if response.status_code != 200:
            raise APIError(f"Parameter extraction failed: {response.status_code} - {response.text}")
        result = response.json()
        if not result.get('choices'):
            return []
        content = result['choices'][0]['message']['content']
        try:
            data = json.loads(content)
            params = data.get('parameters', []) or []
            # Basic validation
            cleaned: List[Dict[str, Any]] = []
            for p in params:
                name = (p.get('name') or '').strip()
                if not name:
                    continue
                cleaned.append({
                    'name': name,
                    'role': (p.get('role') or '').strip() or 'option',
                    'description': (p.get('description') or '').strip(),
                    'spanStart': p.get('spanStart'),
                    'spanEnd': p.get('spanEnd'),
                    'suggestions': p.get('suggestions') or []
                })
            return cleaned
        except Exception:
            # If model returned non-JSON, do not fail hard
            return []
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from OpenRouter API"""
        try:
            self.logger.debug("Fetching available models from OpenRouter")
            response = requests.get(
                f"{self.base_url}/models",
                headers=self._create_headers(),
                timeout=API_TIMEOUT
            )
            
            if response.status_code != 200:
                error_msg = f"Failed to fetch models: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                raise APIError(error_msg)
            
            result = response.json()
            if self.debug:
                self.logger.debug(f"Models API response: {json.dumps(result, indent=2)}")
            
            models = result.get('data', [])
            self.logger.info(f"Retrieved {len(models)} available models")
            return models
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching models: {e}")
            raise APIError(f"Network error fetching models: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response for models: {e}")
            raise APIError(f"Invalid JSON response for models: {e}")
        except APIError:
            raise  # Re-raise API errors as-is
        except Exception as e:
            self.logger.error(f"Unexpected error fetching models: {e}")
            raise APIError(f"Error fetching models: {e}")

    def validate_model(self, model_id: str) -> bool:
        """Validate if a model ID is available"""
        try:
            models = self.get_available_models()
            available_ids = [m.get('id') for m in models if m.get('id')]
            return model_id in available_ids
        except Exception as e:
            self.logger.warning(f"Could not validate model {model_id}: {e}")
            return True  # Assume valid if we can't check

    def ask_for_commands(self, user_query: str, context: Optional[str] = None) -> List[Command]:
        """Ask LLM for commands based on user query"""
        try:
            system_prompt = self._create_system_prompt()
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            if context:
                messages.append({"role": "user", "content": f"Context: {context}"})
            
            messages.append({"role": "user", "content": user_query})
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            if self.debug:
                self.logger.debug(f"API Request:")
                self.logger.debug(f"  URL: {self.base_url}/chat/completions")
                self.logger.debug(f"  Model: {self.model}")
                self.logger.debug(f"  Messages: {len(messages)} messages")
                self.logger.debug(f"  User query: {repr(user_query)}")
                self.logger.debug(f"  Max tokens: {self.max_tokens}")
                self.logger.debug(f"  Temperature: {self.temperature}")
            
            response = self._make_api_request_with_retry(
                f"{self.base_url}/chat/completions",
                payload
            )
            
            if self.debug:
                self.logger.debug(f"Response status: {response.status_code}")
                self.logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                error_msg = f"API request failed: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                if self.debug:
                    self.logger.debug(f"Error response body: {response.text}")
                raise APIError(error_msg)
            
            result = response.json()
            if self.debug:
                self.logger.debug(f"Full API response: {json.dumps(result, indent=2)}")
            
            if 'choices' not in result or not result['choices']:
                error_msg = "No response from API"
                self.logger.error(error_msg)
                raise APIError(error_msg)
            
            content = result['choices'][0]['message']['content']
            if self.debug:
                self.logger.debug(f"Extracted content: {repr(content)}")
            # Prefer JSON parsing with parameters
            parsed = self._parse_commands_json(content)
            if parsed:
                return parsed
            # Fallback to legacy parsing
            return self._parse_commands(content)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error: {e}")
            raise APIError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            raise APIError(f"Invalid JSON response: {e}")
        except APIError:
            raise  # Re-raise API errors as-is
        except Exception as e:
            self.logger.error(f"Unexpected error getting commands: {e}")
            raise APIError(f"Error getting commands: {e}")
    
    def _parse_commands(self, content: str) -> List[Command]:
        """Parse commands from LLM response"""
        if self.debug:
            self.logger.debug(f"Raw LLM response:\n{repr(content)}")
            self.logger.debug("=" * 60)
        
        commands = []
        lines = content.strip().split('\n')
        
        current_command = None
        current_description = None
        
        for line in lines:
            line = line.strip()
            if self.debug:
                self.logger.debug(f"Processing line: {repr(line)}")
            
            if line.startswith('COMMAND:'):
                if self.debug:
                    self.logger.debug("Found COMMAND line")
                # Save previous command if exists
                if current_command:
                    commands.append(Command(
                        command=current_command,
                        description=current_description or "No description provided",
                        parameters=None
                    ))
                
                # Start new command
                current_command = line[8:].strip()  # Remove 'COMMAND: '
                current_description = None
                if self.debug:
                    self.logger.debug(f"Extracted command: {repr(current_command)}")
                
            elif line.startswith('DESC:'):
                if self.debug:
                    self.logger.debug("Found DESC line")
                current_description = line[5:].strip()  # Remove 'DESC: '
                if self.debug:
                    self.logger.debug(f"Extracted description: {repr(current_description)}")
        
        # Add the last command
        if current_command:
            commands.append(Command(
                command=current_command,
                description=current_description or "No description provided",
                parameters=None
            ))
            if self.debug:
                self.logger.debug(f"Added final command: {current_command}")
        
        if self.debug:
            self.logger.debug(f"Found {len(commands)} commands via COMMAND: parsing")
        
        # Fallback: if no COMMAND: format found, try to extract commands differently
        if not commands:
            if self.debug:
                self.logger.debug("No commands found, trying fallback parsing...")
            commands = self._fallback_command_parsing(content)
        
        self.logger.info(f"Parsed {len(commands)} commands from LLM response")
        if self.debug:
            for i, cmd in enumerate(commands):
                self.logger.debug(f"  {i+1}. {cmd.command} - {cmd.description}")
        
        return commands

    def _parse_commands_json(self, content: str) -> List[Command]:
        """Try to parse strict JSON of commands with parameters."""
        try:
            data = json.loads(content)
        except Exception:
            return []
        items = data.get('commands') if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        commands: List[Command] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cmd_str = item.get('command')
            desc = item.get('description') or "No description provided"
            params = item.get('parameters') if isinstance(item.get('parameters'), list) else None
            if not cmd_str or not isinstance(cmd_str, str):
                continue
            commands.append(Command(command=cmd_str, description=desc, parameters=params))
        return commands
    
    def _fallback_command_parsing(self, content: str) -> List[Command]:
        """Fallback method to extract commands from free-form text"""
        if self.debug:
            self.logger.debug("Using fallback parsing...")
        commands = []
        
        # Split content into potential command blocks
        lines = content.strip().split('\n')
        if self.debug:
            self.logger.debug(f"Fallback processing {len(lines)} lines")
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if self.debug:
                self.logger.debug(f"Fallback line {line_num}: {repr(line)}")
            
            if not line:
                if self.debug:
                    self.logger.debug("Skipping empty line")
                continue
            
            # Skip explanatory text and markdown
            if any(line.startswith(marker) for marker in ['#', '*', '-', 'Here', 'To', 'You can', 'This will']):
                if self.debug:
                    self.logger.debug("Skipping explanatory line")
                continue
            
            # Look for shell prompt patterns
            for pattern_num, pattern in enumerate(SHELL_PROMPT_PATTERNS):
                match = re.match(pattern, line)
                if match:
                    cmd = match.group(1).strip()
                    if self.debug:
                        self.logger.debug(f"Pattern {pattern_num} matched, extracted: {repr(cmd)}")
                    # Filter out obvious non-commands
                    if (cmd and 
                        len(cmd.split()) > 0 and 
                        not cmd.lower().startswith(('note:', 'tip:', 'warning:', 'example:')) and
                        any(cmd.startswith(common) for common in COMMON_COMMAND_PREFIXES) or 
                        '/' in cmd or '--' in cmd or '-' in cmd):
                        if self.debug:
                            self.logger.debug(f"Command passed filters, adding: {cmd}")
                        commands.append(Command(
                            command=cmd,
                            description="Auto-detected command"
                        ))
                    else:
                        if self.debug:
                            self.logger.debug(f"Command failed filters: {cmd}")
                    break
        
        # If still no commands found, try to extract anything that looks like a command
        if not commands:
            if self.debug:
                self.logger.debug("No commands found in patterns, trying backticks...")
            for line in lines:
                line = line.strip()
                # Look for backtick-enclosed commands
                backtick_match = re.search(r'`([^`]+)`', line)
                if backtick_match:
                    cmd = backtick_match.group(1).strip()
                    if self.debug:
                        self.logger.debug(f"Found backtick command: {repr(cmd)}")
                    # Check if it's a known command prefix
                    if any(cmd.startswith(common) for common in COMMON_COMMAND_PREFIXES[:10]):  # Use first 10 most common
                        commands.append(Command(
                            command=cmd,
                            description="Command found in backticks"
                        ))
        
        if self.debug:
            self.logger.debug(f"Fallback parsing found {len(commands)} commands")
        return commands
