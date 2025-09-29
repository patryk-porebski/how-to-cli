#compdef how

# Zsh completion for How CLI

_how() {
    local context state state_descr line
    typeset -A opt_args

    _arguments -C \
        '--help[Show help message]' \
        '(-c --config)'{-c,--config}'[Configuration file path]:config file:_files -g "*.yaml"' \
        '--api-key[OpenRouter API key]:api key:' \
        '--model[LLM model to use]:model:(openai/gpt-4 openai/gpt-3.5-turbo anthropic/claude-3-sonnet anthropic/claude-3-haiku meta-llama/llama-2-70b-chat)' \
        '--max-tokens[Maximum tokens]:max tokens:(100 500 1000 2000 4000)' \
        '--temperature[Temperature]:temperature:(0.0 0.1 0.3 0.5 0.7 1.0)' \
        '--no-confirm[Skip confirmation]' \
        '(-v --verbose)'{-v,--verbose}'[Verbose output]' \
        '--debug[Enable debug logging]' \
        '--dry-run[Show commands without executing]' \
        '1: :_how_subcommands' \
        '*:: :->subcommand_args' && return 0

    case $state in
        subcommand_args)
            case $line[1] in
                to)
                    _arguments \
                        '--context[Additional context]:context:' \
                        '*:query:'
                    ;;
                config-set)
                    _arguments \
                        '--key[Configuration key]:key:(openrouter.api_key openrouter.model openrouter.max_tokens openrouter.temperature execution.require_confirmation output.verbose)' \
                        '--value[Configuration value]:value:'
                    ;;
                history)
                    _arguments \
                        '--search[Search term]:search term:' \
                        '--limit[Result limit]:limit:(10 25 50 100)' \
                        '--successful-only[Show only successful commands]' \
                        '--export[Export to file]:export file:_files' \
                        '--clear[Clear history]' \
                        '--stats[Show statistics]'
                    ;;
                sessions)
                    _arguments \
                        '--list[List sessions]' \
                        '--create[Create session]:session name:' \
                        '--load[Load session]:session id:' \
                        '--delete[Delete session]:session id:' \
                        '--save[Save current session]:session id:'
                    ;;
                cache)
                    _arguments \
                        '--stats[Show cache statistics]' \
                        '--clear[Clear all cache]' \
                        '--clear-expired[Clear expired cache entries]'
                    ;;
                background)
                    _arguments \
                        '--list[List background jobs]' \
                        '--status[Show job status]:job id:' \
                        '--cancel[Cancel job]:job id:' \
                        '--stats[Show job statistics]'
                    ;;
            esac
            ;;
    esac
}

_how_subcommands() {
    local -a subcommands
    subcommands=(
        'to:Ask LLM for commands to accomplish a task'
        'config-show:Show current configuration'
        'config-init:Initialize default configuration file'
        'config-set:Set a configuration value'
        'test-api:Test OpenRouter API connection'
        'version:Show version information'
        'history:Manage command execution history'
        'sessions:Manage command sessions'
        'cache:Manage response cache'
        'background:Manage background jobs'
    )
    _describe 'subcommands' subcommands
}

_how "$@"
