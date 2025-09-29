# How To CLI Tool

Ask LLMs how to do anything with terminal commands. A powerful CLI tool that leverages LLMs via OpenRouter to generate and execute terminal commands safely. Ask the AI what you want to accomplish, and it will provide an interactive interface to select, customize, and execute commands with smart parameter detection and safety checks.

## Features

- 🤖 **LLM-Powered**: Uses OpenRouter API to access various LLMs (GPT-4, Claude, etc.)
- ⌨️ **Interactive Interface**: Arrow key navigation and keyboard shortcuts for smooth workflow
- 🎯 **Smart Parameter Detection**: Automatically detects and highlights customizable parameters in commands
- ✨ **Parameter Customization**: Tab through parameters, paste clipboard content, get file suggestions
- 🔒 **Safety First**: Built-in safety checks for dangerous commands with clear warnings
- 📝 **Clean Output**: Minimal, focused interface with clear execution markers
- ⚙️ **Configurable**: Flexible configuration via YAML file and CLI options
- 🔄 **Multi-Command Support**: Generate and execute multiple commands in sequence
- 📋 **Clipboard Integration**: Copy commands or paste content directly into parameters
- 🧪 **Dry Run Mode**: Preview commands without executing them
- 📊 **Execution History**: Track command execution results with search and statistics

## Installation

1. Clone or download the project files
2. Run the setup script:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

## Quick Start

1. **Get an OpenRouter API key** from [openrouter.ai](https://openrouter.ai)

2. **First run** - initialize configuration:

   ```bash
   python how.py config-init
   ```

3. **Ask for commands**:
   ```bash
   python how.py to "install nodejs on ubuntu"
   ```
   or simply:
   ```bash
   how to "install nodejs on ubuntu"
   ```

## Usage Examples

### Basic Usage

```bash
# Ask what you want to do
how to "find all python files larger than 1MB"

# Interactive mode with history navigation
how to
What do you want to accomplish? create a new git repository and make first commit
```

### With Options

```bash
# Use different model
how --model "anthropic/claude-3-sonnet" to "deploy docker container"

# Skip confirmations (be careful!)
how --no-confirm to "update all npm packages"

# Dry run mode (preview only)
how --dry-run to "clean up old log files"

# Add context
how to "optimize database" --context "PostgreSQL running on Ubuntu 20.04"
```

### Configuration Management

```bash
# Show current configuration
how config-show

# Set configuration values
how config-set --key "openrouter.model" --value "openai/gpt-4"
how config-set --key "execution.require_confirmation" --value "false"

# Test API connection
how test-api

# List available models
how models

# Filter models by provider
how models --provider anthropic

# Search models
how models --search "claude"

# Interactive model selection with arrow keys
how select-model

# Filter models in interactive selection
how select-model --provider openai

# View command history
how history

# Search history and show statistics
how history --search "git" --stats
```

## Interactive Navigation

The tool features a modern interactive interface with keyboard navigation:

### Command Selection

- **Arrow keys** or **j/k**: Navigate through commands
- **Enter** or **numbers (1-9)**: Select and customize/execute command
- **c**: Copy command to clipboard
- **m**: Modify command before execution
- **Esc**: Exit

### Parameter Customization

When a command has customizable parameters (highlighted in yellow), you can:

- **Tab**: Navigate between parameters
- **Type**: Edit the selected parameter value
- **v** or **Cmd+V**: Paste clipboard content into parameter
- **Enter**: Execute with current parameter values
- **c**: Copy customized command to clipboard
- **Esc**: Return to command selection

### Automatic Parameter Detection

The tool automatically detects various parameter types:

- **File paths**: `input.mp4`, `output.txt`, etc.
- **Placeholders**: `{INPUT}`, `<filename>`, `[path]`
- **Options**: `--input file.mp4`, `-o output.mp4`
- **Time codes**: `00:01:30`, frame numbers
- **Numeric values**: sizes, rates, dimensions

## Configuration

Configuration is stored in `~/.config/how/config.yaml`. You can customize:

### OpenRouter Settings

```yaml
openrouter:
  api_key: "your-api-key-here"
  base_url: "https://openrouter.ai/api/v1"
  model: "openai/gpt-4" # or anthropic/claude-3-sonnet, etc.
  max_tokens: 1000
  temperature: 0.1
```

### Execution Settings

```yaml
execution:
  require_confirmation: true
  show_commands_before_execution: true
  max_commands_per_request: 10
  timeout: 30
```

### Output Settings

```yaml
output:
  verbose: false
  color: true
  format: "rich"
```

## CLI Options

| Option               | Description                           |
| -------------------- | ------------------------------------- |
| `--config, -c`       | Custom configuration file path        |
| `--api-key`          | OpenRouter API key (overrides config) |
| `--model`            | LLM model to use                      |
| `--max-tokens`       | Maximum tokens for response           |
| `--temperature`      | Temperature for LLM (0.0-1.0)         |
| `--no-confirm`       | Skip confirmation prompts             |
| `--verbose, -v`      | Verbose output                        |
| `--debug`            | Enable debug logging                  |
| `--streaming`        | Enable real-time output streaming     |
| `--parallel`         | Enable parallel command execution     |
| `--cache/--no-cache` | Enable/disable response caching       |
| `--dry-run`          | Show commands without executing       |

## Available Commands

| Command        | Description                                        |
| -------------- | -------------------------------------------------- |
| `to [QUERY]`   | Ask LLM for commands (default if no command given) |
| `models`       | List available OpenRouter models                   |
| `select-model` | Interactively select and set a model               |
| `config-show`  | Display current configuration                      |
| `config-init`  | Create default configuration file                  |
| `config-set`   | Set a configuration value                          |
| `test-api`     | Test OpenRouter API connection                     |
| `history`      | View command execution history with search/stats   |
| `version`      | Show version information                           |

## Safety Features

The tool includes several safety mechanisms:

- **Dangerous Command Detection**: Warns about potentially harmful commands
- **System Path Protection**: Extra caution for system-critical directories
- **User Confirmation**: Optional confirmation for each command
- **Timeout Protection**: Commands timeout after 30 seconds
- **Execution History**: Track what was executed and results

### Dangerous Commands Detected

- File deletion commands (`rm`, `del`)
- System modification commands (`chmod 777`, `chown -R`)
- Disk operations (`format`, `fdisk`, `dd`)
- Network operations (`curl`, `wget` with redirects)

## Supported Models

Any model available on OpenRouter, including:

- `openai/gpt-4`
- `openai/gpt-3.5-turbo`
- `anthropic/claude-3-sonnet`
- `anthropic/claude-3-haiku`
- `meta-llama/llama-2-70b-chat`
- Many others...

## Example Sessions

### Installing Software

```bash
$ how to "install docker on ubuntu"

Select a command (2 available):

❯ 1. sudo apt update
     Update package lists to get latest package info

  2. sudo apt install docker.io -y
     Install Docker from Ubuntu repositories

  ↑↓ navigate  Enter/1-9 customize/execute  c copy  m modify  Esc quit

❯ sudo apt update
  in /home/user
▶
... (command output appears here)
◀
```

### File Operations with Parameter Customization

```bash
$ how to "compress video files"

Select a command:

❯ 1. ffmpeg -i input.mp4 -c:v libx264 -crf 23 output.mp4
     Compress video file with H.264 codec

  ↑↓ navigate  Enter/1-9 customize/execute  c copy  m modify  Esc quit

Command:
ffmpeg -i input.mp4 -c:v libx264 -crf 23 output.mp4

  Tab next parameter  v/Cmd+V paste clipboard  Type edit  c copy  Enter execute  Esc back

❯ ffmpeg -i input.mp4 -c:v libx264 -crf 23 compressed.mp4
  in /home/user/videos
▶
... (ffmpeg output appears here)
◀
```

### Command History

```bash
$ how history

❯ Recent command history:

1. ✓ git add .
   Query: create a git repository • 2024-01-15 14:30

2. ✓ git commit -m "Initial commit"
   Query: create a git repository • 2024-01-15 14:31

3. ✗ rm -rf node_modules
   Query: clean up project files • 2024-01-15 14:25

4. ✓ npm install
   Query: install dependencies • 2024-01-15 14:20
```

## Error Handling

The tool provides helpful error messages for common issues:

- Invalid API key
- Network connectivity problems
- Command execution failures
- Configuration errors

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source. Use it responsibly!
