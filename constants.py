"""Constants used throughout the How CLI tool"""

# API Configuration
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.1
API_TIMEOUT = 30

# Command Execution
DANGEROUS_COMMANDS = [
    'rm', 'del', 'format', 'fdisk', 'mkfs', 'dd', 'chmod 777',
    'chown -R', 'sudo rm', 'sudo del', '> /dev/', 'curl', 'wget'
]

SYSTEM_CRITICAL_PATHS = [
    '/etc', '/bin', '/sbin', '/usr/bin', '/usr/sbin', '/boot',
    '/sys', '/proc', '/dev', 'C:\\Windows', 'C:\\Program Files'
]

# Command patterns for fallback parsing
SHELL_PROMPT_PATTERNS = [
    r'^\$\s*(.+)$',           # $ command
    r'^>\s*(.+)$',            # > command  
    r'^#\s*(.+)$',            # # command (as root)
    r'^sudo\s+(.+)$',         # sudo command
    r'^([a-zA-Z][a-zA-Z0-9_\-\.]*(?:\s+[^\n]*)?)$',  # Basic command pattern
]

COMMON_COMMAND_PREFIXES = [
    'ls', 'cd', 'mkdir', 'rm', 'cp', 'mv', 'chmod', 'chown', 'find', 'grep',
    'cat', 'less', 'tail', 'head', 'echo', 'touch', 'wget', 'curl', 'git',
    'npm', 'pip', 'apt', 'yum', 'brew', 'docker', 'sudo', 'ssh', 'scp',
    'ps', 'kill', 'killall', 'which', 'whereis', 'file', 'du', 'df',
    'tar', 'zip', 'unzip', 'gzip', 'gunzip', 'ln', 'history', 'alias',
    'ffmpeg', 'sox', 'python', 'node', 'java', 'gcc', 'make', 'cmake'
]

# Execution timeouts
COMMAND_TIMEOUT = 30
API_REQUEST_TIMEOUT = 30

# Configuration
CONFIG_DIR = ".config/how"
CONFIG_FILE = "config.yaml"

# Application metadata
APP_NAME = "How to CLI"
APP_VERSION = "0.0.3"
APP_DESCRIPTION = "Ask LLMs how to do anything with terminal commands"
GITHUB_URL = "https://github.com/patryk-porebski/how-to-cli"
