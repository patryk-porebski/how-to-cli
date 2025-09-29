# Fish completion for How CLI

# Main command completion
complete -c how -f

# Global options
complete -c how -s h -l help -d "Show help message"
complete -c how -s c -l config -d "Configuration file path" -r -F
complete -c how -l api-key -d "OpenRouter API key" -r
complete -c how -l model -d "LLM model to use" -r -xa "openai/gpt-4 openai/gpt-3.5-turbo anthropic/claude-3-sonnet anthropic/claude-3-haiku meta-llama/llama-2-70b-chat"
complete -c how -l max-tokens -d "Maximum tokens" -r -xa "100 500 1000 2000 4000"
complete -c how -l temperature -d "Temperature" -r -xa "0.0 0.1 0.3 0.5 0.7 1.0"
complete -c how -l no-confirm -d "Skip confirmation"
complete -c how -s v -l verbose -d "Verbose output"
complete -c how -l debug -d "Enable debug logging"
complete -c how -l dry-run -d "Show commands without executing"

# Subcommands
complete -c how -n "__fish_use_subcommand" -xa "to" -d "Ask LLM for commands"
complete -c how -n "__fish_use_subcommand" -xa "config-show" -d "Show current configuration"
complete -c how -n "__fish_use_subcommand" -xa "config-init" -d "Initialize default configuration"
complete -c how -n "__fish_use_subcommand" -xa "config-set" -d "Set configuration value"
complete -c how -n "__fish_use_subcommand" -xa "test-api" -d "Test OpenRouter API connection"
complete -c how -n "__fish_use_subcommand" -xa "version" -d "Show version information"
complete -c how -n "__fish_use_subcommand" -xa "history" -d "Manage command history"
complete -c how -n "__fish_use_subcommand" -xa "sessions" -d "Manage command sessions"
complete -c how -n "__fish_use_subcommand" -xa "cache" -d "Manage response cache"
complete -c how -n "__fish_use_subcommand" -xa "background" -d "Manage background jobs"

# Subcommand options
complete -c how -n "__fish_seen_subcommand_from to" -l context -d "Additional context" -r

complete -c how -n "__fish_seen_subcommand_from config-set" -l key -d "Configuration key" -r -xa "openrouter.api_key openrouter.model openrouter.max_tokens openrouter.temperature execution.require_confirmation output.verbose"
complete -c how -n "__fish_seen_subcommand_from config-set" -l value -d "Configuration value" -r

complete -c how -n "__fish_seen_subcommand_from history" -l search -d "Search term" -r
complete -c how -n "__fish_seen_subcommand_from history" -l limit -d "Result limit" -r -xa "10 25 50 100"
complete -c how -n "__fish_seen_subcommand_from history" -l successful-only -d "Show only successful commands"
complete -c how -n "__fish_seen_subcommand_from history" -l export -d "Export to file" -r -F
complete -c how -n "__fish_seen_subcommand_from history" -l clear -d "Clear history"
complete -c how -n "__fish_seen_subcommand_from history" -l stats -d "Show statistics"

complete -c how -n "__fish_seen_subcommand_from sessions" -l list -d "List sessions"
complete -c how -n "__fish_seen_subcommand_from sessions" -l create -d "Create session" -r
complete -c how -n "__fish_seen_subcommand_from sessions" -l load -d "Load session" -r
complete -c how -n "__fish_seen_subcommand_from sessions" -l delete -d "Delete session" -r
complete -c how -n "__fish_seen_subcommand_from sessions" -l save -d "Save current session" -r

complete -c how -n "__fish_seen_subcommand_from cache" -l stats -d "Show cache statistics"
complete -c how -n "__fish_seen_subcommand_from cache" -l clear -d "Clear all cache"
complete -c how -n "__fish_seen_subcommand_from cache" -l clear-expired -d "Clear expired cache entries"

complete -c how -n "__fish_seen_subcommand_from background" -l list -d "List background jobs"
complete -c how -n "__fish_seen_subcommand_from background" -l status -d "Show job status" -r
complete -c how -n "__fish_seen_subcommand_from background" -l cancel -d "Cancel job" -r
complete -c how -n "__fish_seen_subcommand_from background" -l stats -d "Show job statistics"
