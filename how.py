#!/usr/bin/env python3
"""
How - CLI tool for asking LLMs to generate and execute terminal commands
"""
import sys
import os
import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.traceback import install
from pathlib import Path

from config import Config
from openrouter_client import OpenRouterClient
from executor import CommandExecutor
from logger import setup_logger, get_logger
from exceptions import ConfigurationError, APIError, CommandExecutionError
from constants import APP_NAME, APP_VERSION, APP_DESCRIPTION
from security import APIKeyManager
from history import CommandHistory, HistoryEntry
from session import SessionManager
from cache import QueryCache
from streaming import StreamingExecutor
from background import JobManager, JobStatus
from interactive import InteractiveSelector, MinimalExecutor
from model_selector import ModelSelector

def _get_query_with_history(history_manager=None):
    """Get query from user with arrow key history navigation"""
    import readline
    import sys
    
    # Configure readline for better history behavior
    readline.parse_and_bind('tab: complete')
    readline.parse_and_bind('set editing-mode emacs')
    
    # Load query history
    if history_manager:
        try:
            entries = history_manager.search(limit=50)
            # Get unique queries only, in reverse chronological order
            seen_queries = set()
            query_history = []
            for entry in entries:
                if entry.query not in seen_queries:
                    query_history.append(entry.query)
                    seen_queries.add(entry.query)
            
            # Set up readline history (add in chronological order for proper navigation)
            readline.clear_history()
            for query in query_history:  # Add in chronological order (oldest to newest)
                readline.add_history(query)
                
        except Exception as e:
            # If history loading fails, continue without it
            pass
    
    try:
        # Use ANSI escape codes for dimmed prompt - this works in real terminals
        dimmed_prompt = "\033[2mWhat do you want to accomplish?\033[0m "
        return input(dimmed_prompt)
    except (EOFError, KeyboardInterrupt):
        print()  # New line after Ctrl+C
        return ""

# Install rich traceback handler
install(show_locals=True)

console = Console()
logger = setup_logger('how_cli')


@click.group(invoke_without_command=True)
@click.option('--config', '-c', help='Configuration file path')
@click.option('--api-key', help='OpenRouter API key')
@click.option('--model', help='LLM model to use')
@click.option('--max-tokens', type=int, help='Maximum tokens for LLM response')
@click.option('--temperature', type=float, help='Temperature for LLM response')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation before executing commands')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--streaming', is_flag=True, help='Enable real-time output streaming')
@click.option('--parallel', is_flag=True, help='Enable parallel command execution')
@click.option('--cache/--no-cache', default=True, help='Enable/disable response caching')
@click.option('--dry-run', is_flag=True, help='Show commands but do not execute them')
@click.pass_context
def cli(ctx, config, api_key, model, max_tokens, temperature, no_confirm, verbose, dry_run, debug, streaming, parallel, cache):
    """How - Ask LLMs for terminal commands and execute them safely"""
    
    # Ensure that ctx.obj exists and is a dict
    ctx.ensure_object(dict)
    
    # Setup logging level based on options
    log_level = 'DEBUG' if debug else ('INFO' if verbose else 'WARNING')
    global logger
    logger = setup_logger('how_cli', level=log_level)
    
    # Load configuration
    try:
        cfg = Config(config)
        
        # Validate model if provided via CLI
        if model:
            try:
                # Use API key from config or CLI
                test_api_key = api_key or cfg.get('openrouter.api_key')
                if test_api_key:
                    validation_client = OpenRouterClient(
                        api_key=test_api_key,
                        base_url=cfg.get('openrouter.base_url'),
                        model=cfg.get('openrouter.model'),
                        debug=debug
                    )
                    
                    if not validation_client.validate_model(model):
                        logger.warning(f"Model '{model}' not found in available models")
                        console.print(f"[yellow]Warning: Model '{model}' not found in available models[/yellow]")
                        console.print("[yellow]Use 'how models' to see available models[/yellow]")
                else:
                    logger.warning("No API key available for model validation")
            except Exception as e:
                logger.warning(f"Could not validate model {model}: {e}")
        
        # Update config with CLI options
        cfg.update_from_cli(
            **{k: v for k, v in {
                'openrouter.api_key': api_key,
                'openrouter.model': model,
                'openrouter.max_tokens': max_tokens,
                'openrouter.temperature': temperature,
                'execution.require_confirmation': not no_confirm,
                'output.verbose': verbose
            }.items() if v is not None}
        )
        
        ctx.obj['config'] = cfg
        ctx.obj['dry_run'] = dry_run
        ctx.obj['debug'] = debug
        ctx.obj['streaming'] = streaming
        ctx.obj['parallel'] = parallel
        ctx.obj['cache'] = cache
        
        # Initialize components
        ctx.obj['api_key_manager'] = APIKeyManager()
        ctx.obj['history'] = CommandHistory()
        ctx.obj['session_manager'] = SessionManager()
        ctx.obj['query_cache'] = QueryCache() if cache else None
        ctx.obj['job_manager'] = JobManager() if parallel else None
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {e}")
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)
    
    # If no subcommand, run the main to command
    if ctx.invoked_subcommand is None:
        ctx.invoke(to)


@cli.command()
@click.argument('query', nargs=-1, required=False)
@click.option('--context', default=None, help='Additional context for the query')
@click.pass_context
def to(ctx, query, context):
    """Ask LLM for commands to accomplish a task"""
    config = ctx.obj['config']
    dry_run = ctx.obj['dry_run']
    debug = ctx.obj.get('debug', False)
    streaming = ctx.obj.get('streaming', False)
    parallel = ctx.obj.get('parallel', False)
    use_cache = ctx.obj.get('cache', True)
    
    # Get component instances
    api_key_manager = ctx.obj['api_key_manager']
    history = ctx.obj['history']
    session_manager = ctx.obj['session_manager']
    query_cache = ctx.obj.get('query_cache')
    job_manager = ctx.obj.get('job_manager')
    
    # Get query from user if not provided
    if not query:
        # Prompt with history navigation
        query_text = _get_query_with_history(ctx.obj.get('history'))
    else:
        query_text = ' '.join(query)
    
    if not query_text.strip():
        console.print("[yellow]No query provided[/yellow]")
        return
    
    try:
        # Get API key using secure manager
        api_key = api_key_manager.get_api_key(config.get('openrouter.api_key'))
        if not api_key:
            api_key = api_key_manager.prompt_for_api_key()
            if not api_key:
                logger.error("No API key provided")
                console.print("[red]API key is required to use How CLI[/red]")
                sys.exit(1)
        
        client = OpenRouterClient(
            api_key=api_key,
            base_url=config.get('openrouter.base_url'),
            model=config.get('openrouter.model'),
            max_tokens=config.get('openrouter.max_tokens'),
            temperature=config.get('openrouter.temperature'),
            debug=debug
        )
        
        # Show what we're asking
        console.print(Panel(f"[bold cyan]Query:[/bold cyan] {query_text}", expand=False))
        if context:
            console.print(Panel(f"[bold cyan]Context:[/bold cyan] {context}", expand=False))
        
        # Check cache first
        commands = None
        if use_cache and query_cache:
            commands = query_cache.get(query_text, context, config.get('openrouter.model'))
            if commands:
                console.print("[dim]✓ Found cached response[/dim]")
        
        # Get commands from LLM if not cached
        if not commands:
            console.print("\n[yellow]Asking LLM for commands...[/yellow]")
            logger.info(f"Requesting commands for query: {query_text}")
            commands = client.ask_for_commands(query_text, context)
            
            # Cache the response
            if use_cache and query_cache and commands:
                query_cache.put(query_text, context, config.get('openrouter.model'), commands)
        
        if not commands:
            logger.warning("No commands generated by LLM")
            console.print("[red]No commands generated by LLM[/red]")
            return
        
        # Initialize executor (streaming or regular)
        if streaming:
            executor = StreamingExecutor(console=console)
        else:
            executor = CommandExecutor(
                console=console,
                require_confirmation=config.get('execution.require_confirmation')
            )
        
        if dry_run:
            console.print("\n[yellow]DRY RUN MODE - Commands will not be executed[/yellow]")
            # Use clean list display for dry run preview
            console.print("\\nCommands that would be executed:", style="bold green")
            for i, command in enumerate(commands, 1):
                console.print(f"{i}. ", style="cyan", end="")
                console.print(command.command, style="bold")
                console.print(f"    {command.description}", style="dim")
                if i < len(commands):
                    console.print()
        else:
            # Use interactive selector for command selection and execution
            selector = InteractiveSelector(console=console)
            minimal_executor = MinimalExecutor(console=console)
            
            # Command selection loop - allows return to command list from parameter mode
            while True:
                # Let user select command and action
                result = selector.select_command(commands)
                
                if not result:
                    # User cancelled (Esc, Ctrl+C, q) - exit program
                    return
                
                selected_command, action = result
                success = False
                output = ""
                
                if action == 'execute':
                    # Execute the command and EXIT
                    success = minimal_executor.execute_command(selected_command)
                    output = "Command executed" if success else "Command failed"
                    break  # Exit the loop and program
                    
                elif action == 'copy':
                    # Copy to clipboard and EXIT
                    success = minimal_executor.copy_command(selected_command)
                    output = "Copied to clipboard" if success else "Copy failed"
                    break  # Exit the loop and program
                    
                elif action == 'edit':
                    # Edit the command
                    edited_command = minimal_executor.edit_command(selected_command)
                    if edited_command:
                        # Always execute the command after editing (even if unchanged)
                        success = minimal_executor.execute_command(edited_command)
                        output = "Command executed" if success else "Command failed"
                        break  # Exit the loop and program
                        
                elif action == 'parameters':
                    # Customize parameters; pass LLM-provided parameters when available
                    from parameters import ParameterCustomizer
                    preset_params = getattr(selected_command, 'parameters', None) or []
                    customizer = ParameterCustomizer(console, llm_client=client, user_task=query_text, preset_parameters=preset_params)
                    # If the selected command already has parameters from LLM, pre-seed detection by merging
                    if getattr(selected_command, 'parameters', None):
                        # Build a synthetic display by marking spans if provided
                        # ParameterCustomizer will still run heuristic detection; LLM params are merged inside
                        pass
                    customized_command = customizer.customize_command(selected_command.command)
                    if customized_command:
                        # Create new command with customized version
                        from openrouter_client import Command
                        custom_cmd = Command(
                            command=customized_command,
                            description=selected_command.description,
                            working_directory=selected_command.working_directory
                        )
                        success = minimal_executor.execute_command(custom_cmd)
                        break  # Exit the loop and program
                    else:
                        # User cancelled editing - continue loop to show command list again
                        continue
                
                # Add to history
                history_entry = HistoryEntry(
                    query=query_text,
                    command=selected_command.command,
                    description=selected_command.description,
                    success=success,
                    output=output,
                    working_directory=selected_command.working_directory or ""
                )
                history.add_entry(history_entry)
            
            # ALWAYS EXIT - No continuation, no questions, nothing!
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except APIError as e:
        logger.error(f"API error: {e}")
        console.print(f"[red]API Error: {e}[/red]")
        sys.exit(1)
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Configuration Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        if config.get('output.verbose') or debug:
            console.print_exception()
        sys.exit(1)
    finally:
        # Cleanup background jobs if needed
        if ctx.obj.get('job_manager'):
            ctx.obj['job_manager'].stop_workers()


@cli.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    config = ctx.obj['config']
    
    # Hide sensitive information
    display_config = config.config.copy()
    if 'openrouter' in display_config and 'api_key' in display_config['openrouter']:
        api_key = display_config['openrouter']['api_key']
        if api_key:
            display_config['openrouter']['api_key'] = f"{api_key[:8]}..." if len(api_key) > 8 else "***"
    
    import yaml
    config_text = yaml.dump(display_config, default_flow_style=False, indent=2)
    
    console.print(Panel(
        config_text,
        title=f"Configuration ({config.config_file})",
        expand=False
    ))


@cli.command()
@click.pass_context
def config_init(ctx):
    """Initialize default configuration file"""
    config = ctx.obj['config']
    config_path = config.create_default_config()
    console.print(f"[green]Created default configuration at: {config_path}[/green]")
    console.print("Edit this file to customize your settings.")


@cli.command()
@click.option('--key', required=True, help='Configuration key (use dot notation, e.g., openrouter.model)')
@click.option('--value', required=True, help='Configuration value')
@click.pass_context
def config_set(ctx, key, value):
    """Set a configuration value"""
    config = ctx.obj['config']
    
    # Validate model if setting openrouter.model
    if key == 'openrouter.model':
        try:
            api_key = config.get('openrouter.api_key')
            if api_key:
                client = OpenRouterClient(
                    api_key=api_key,
                    base_url=config.get('openrouter.base_url'),
                    model=config.get('openrouter.model'),
                    debug=ctx.obj.get('debug', False)
                )
                
                console.print(f"[yellow]Validating model: {value}[/yellow]")
                if not client.validate_model(value):
                    console.print(f"[red]Warning: Model '{value}' not found in available models[/red]")
                    console.print("[yellow]Use 'how models' to see available models or 'how select-model' for interactive selection[/yellow]")
                    if not click.confirm("Continue anyway?"):
                        return
                else:
                    console.print(f"[green]✓ Model '{value}' is available[/green]")
            else:
                console.print("[yellow]No API key configured - skipping model validation[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Could not validate model: {e}[/yellow]")
    
    # Try to convert value to appropriate type
    if value.lower() in ('true', 'false'):
        value = value.lower() == 'true'
    elif value.isdigit():
        value = int(value)
    elif '.' in value and value.replace('.', '').isdigit():
        value = float(value)
    
    config.update_from_cli(**{key: value})
    config.save()
    console.print(f"[green]Set {key} = {value}[/green]")


@cli.command()
@click.pass_context
def version(ctx):
    """Show version information"""
    console.print(f"[bold blue]{APP_NAME}[/bold blue]")
    console.print(f"Version: {APP_VERSION}")
    console.print(f"Description: {APP_DESCRIPTION}")
    
    # Show additional info
    api_key_manager = APIKeyManager()
    storage_info = api_key_manager.get_storage_info()
    
    console.print(f"\n[bold]Security Features:[/bold]")
    console.print(f"Keyring available: {'✓' if storage_info['keyring_available'] else '✗'}")
    console.print(f"Stored API key: {'✓' if storage_info['has_stored_key'] else '✗'}")
    console.print(f"Environment variable: {storage_info['environment_variable']}")


@cli.command()
@click.pass_context
def test_api(ctx):
    """Test OpenRouter API connection"""
    config = ctx.obj['config']
    
    try:
        api_key = config.get('openrouter.api_key')
        if not api_key:
            api_key = click.prompt("Enter your OpenRouter API key", hide_input=True)
        
        client = OpenRouterClient(
            api_key=api_key,
            base_url=config.get('openrouter.base_url'),
            model=config.get('openrouter.model'),
            max_tokens=100,
            temperature=0.1,
            debug=False
        )
        
        console.print("[yellow]Testing API connection...[/yellow]")
        commands = client.ask_for_commands("echo 'hello world'")
        
        if commands:
            console.print("[green]✓ API connection successful![/green]")
            console.print(f"Model: {config.get('openrouter.model')}")
            console.print(f"Generated {len(commands)} command(s)")
        else:
            console.print("[red]✗ API connection failed - no commands returned[/red]")
            
    except Exception as e:
        console.print(f"[red]✗ API connection failed: {e}[/red]")


@cli.command()
@click.option('--provider', help='Filter models by provider (e.g., anthropic, openai)')
@click.option('--search', help='Search models by name or description')
@click.option('--limit', type=int, default=50, help='Maximum number of models to show')
@click.pass_context
def models(ctx, provider, search, limit):
    """List available OpenRouter models"""
    config = ctx.obj['config']
    
    try:
        api_key = config.get('openrouter.api_key')
        if not api_key:
            api_key = click.prompt("Enter your OpenRouter API key", hide_input=True)
        
        client = OpenRouterClient(
            api_key=api_key,
            base_url=config.get('openrouter.base_url'),
            model=config.get('openrouter.model'),
            debug=ctx.obj.get('debug', False)
        )
        
        console.print("[yellow]Fetching available models...[/yellow]")
        models_list = client.get_available_models()
        
        if not models_list:
            console.print("[red]No models found[/red]")
            return
        
        # Filter models
        filtered_models = models_list
        
        if provider:
            filtered_models = [m for m in filtered_models 
                             if m.get('id', '').lower().startswith(provider.lower())]
        
        if search:
            search_lower = search.lower()
            filtered_models = [m for m in filtered_models 
                             if search_lower in m.get('id', '').lower() or 
                                search_lower in m.get('name', '').lower()]
        
        # Limit results
        if limit and len(filtered_models) > limit:
            filtered_models = filtered_models[:limit]
            console.print(f"[dim]Showing first {limit} models (use --limit to show more)[/dim]")
        
        if not filtered_models:
            console.print("[yellow]No models match the specified filters[/yellow]")
            return
        
        # Display models in a table format
        console.print(f"\n[bold blue]Available Models ({len(filtered_models)} found):[/bold blue]\n")
        
        current_model = config.get('openrouter.model')
        
        for model in filtered_models:
            model_id = model.get('id', 'Unknown')
            model_name = model.get('name', 'No name')
            description = model.get('description', 'No description')
            
            # Highlight current model
            if model_id == current_model:
                console.print(f"[green]➤ {model_id}[/green] [bold]({model_name})[/bold]")
            else:
                console.print(f"  [cyan]{model_id}[/cyan] [dim]({model_name})[/dim]")
            
            # Show description if available and not too long
            if description and len(description) < 100:
                console.print(f"    [dim]{description}[/dim]")
            
            console.print()
        
        # Show usage tip
        console.print("[dim]Use 'how config-set --key openrouter.model --value MODEL_ID' to set a model[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error fetching models: {e}[/red]")


@cli.command()
@click.option('--provider', help='Filter models by provider (e.g., anthropic, openai)')
@click.option('--search', help='Search models by name or description')
@click.pass_context
def select_model(ctx, provider, search):
    """Interactively select and set a model with arrow key navigation"""
    config = ctx.obj['config']
    
    try:
        api_key = config.get('openrouter.api_key')
        if not api_key:
            api_key = click.prompt("Enter your OpenRouter API key", hide_input=True)
        
        client = OpenRouterClient(
            api_key=api_key,
            base_url=config.get('openrouter.base_url'),
            model=config.get('openrouter.model'),
            debug=ctx.obj.get('debug', False)
        )
        
        console.print("[yellow]Fetching available models...[/yellow]")
        models_list = client.get_available_models()
        
        if not models_list:
            console.print("[red]No models found[/red]")
            return
        
        # Filter models
        filtered_models = models_list
        
        if provider:
            filtered_models = [m for m in filtered_models 
                             if m.get('id', '').lower().startswith(provider.lower())]
        
        if search:
            search_lower = search.lower()
            filtered_models = [m for m in filtered_models 
                             if search_lower in m.get('id', '').lower() or 
                                search_lower in m.get('name', '').lower()]
        
        if not filtered_models:
            console.print("[yellow]No models match the specified filters[/yellow]")
            return
        
        # Sort models by provider and name for better organization
        filtered_models.sort(key=lambda x: (x.get('id', '').split('/')[0], x.get('id', '')))
        
        # Use interactive selector
        selector = ModelSelector(console)
        current_model = config.get('openrouter.model')
        selected_model = selector.select_model(filtered_models, current_model)
        
        if selected_model:
            # Update configuration
            config.update_from_cli(**{'openrouter.model': selected_model})
            config.save()
            console.print(f"[green]✓ Model set to: {selected_model}[/green]")
            
            # Test the new model
            console.print("[yellow]Testing new model...[/yellow]")
            try:
                test_client = OpenRouterClient(
                    api_key=api_key,
                    base_url=config.get('openrouter.base_url'),
                    model=selected_model,
                    max_tokens=100,
                    temperature=0.1,
                    debug=False
                )
                commands = test_client.ask_for_commands("echo 'test'")
                if commands:
                    console.print("[green]✓ Model test successful![/green]")
                else:
                    console.print("[yellow]⚠ Model test returned no commands[/yellow]")
            except Exception as e:
                console.print(f"[red]✗ Model test failed: {e}[/red]")
        else:
            console.print("[yellow]Model selection cancelled[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error selecting model: {e}[/red]")


@cli.command()
@click.option('--search', help='Search term for filtering history')
@click.option('--limit', type=int, default=25, help='Number of entries to show')
@click.option('--successful-only', is_flag=True, help='Show only successful commands')
@click.option('--export', help='Export history to JSON file')
@click.option('--stats', is_flag=True, help='Show history statistics')
@click.pass_context
def history(ctx, search, limit, successful_only, export, stats):
    """Manage command execution history"""
    history_manager = ctx.obj['history']
    
    if stats:
        stats_data = history_manager.get_stats()
        console.print("\\n[bold]History Statistics:[/bold]")
        console.print(f"Total commands: {stats_data.get('total_commands', 0)}")
        console.print(f"Successful commands: {stats_data.get('successful_commands', 0)}")
        console.print(f"Success rate: {stats_data.get('success_rate', 0):.1f}%")
        console.print(f"Average execution time: {stats_data.get('average_execution_time', 0):.2f}s")
        return
    
    if export:
        history_manager.export_to_json(export)
        console.print(f"[green]History exported to {export}[/green]")
        return
    
    # Show recent history
    entries = history_manager.search(search, limit, successful_only)
    
    if not entries:
        console.print("[yellow]No history entries found[/yellow]")
        return
    
    # Display history in clean list format
    console.print("\\n[bold blue]❯[/bold blue] Recent command history:")
    console.print()
    
    for i, entry in enumerate(entries, 1):
        status = "✓" if entry.success else "✗"
        status_style = "green" if entry.success else "red"
        time_str = entry.timestamp[:16].replace('T', ' ')
        
        # Command line with status
        console.print(f"[dim]{i}.[/dim] [{status_style}]{status}[/{status_style}] [bold]{entry.command}[/bold]")
        
        # Query and time on dimmed line
        query_display = entry.query[:50] + "..." if len(entry.query) > 50 else entry.query
        console.print(f"    [dim]Query: {query_display} • {time_str}[/dim]")
        
        if i < len(entries):
            console.print()


if __name__ == '__main__':
    cli()
