#!/bin/bash
# Bash completion for How CLI

_how_completion() {
    local cur prev words cword
    _init_completion || return

    case $prev in
        --config|-c)
            _filedir yaml
            return
            ;;
        --api-key)
            # Don't complete API keys
            return
            ;;
        --model)
            COMPREPLY=($(compgen -W "openai/gpt-4 openai/gpt-3.5-turbo anthropic/claude-3-sonnet anthropic/claude-3-haiku meta-llama/llama-2-70b-chat" -- "$cur"))
            return
            ;;
        --max-tokens)
            COMPREPLY=($(compgen -W "100 500 1000 2000 4000" -- "$cur"))
            return
            ;;
        --temperature)
            COMPREPLY=($(compgen -W "0.0 0.1 0.3 0.5 0.7 1.0" -- "$cur"))
            return
            ;;
    esac

    # Complete subcommands
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "to config-show config-init config-set test-api version history sessions cache background" -- "$cur"))
        return
    fi

    # Complete options
    case $cur in
        -*)
            COMPREPLY=($(compgen -W "--help --config --api-key --model --max-tokens --temperature --no-confirm --verbose --debug --dry-run" -- "$cur"))
            return
            ;;
    esac

    # Complete based on subcommand
    local subcommand=${words[1]}
    case $subcommand in
        config-set)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "--key --value" -- "$cur"))
            elif [[ $prev == "--key" ]]; then
                COMPREPLY=($(compgen -W "openrouter.api_key openrouter.model openrouter.max_tokens openrouter.temperature execution.require_confirmation output.verbose" -- "$cur"))
            fi
            ;;
        history)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "--search --limit --successful-only --export --clear --stats" -- "$cur"))
            fi
            ;;
        sessions)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "--list --create --load --delete --save" -- "$cur"))
            fi
            ;;
        cache)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "--stats --clear --clear-expired" -- "$cur"))
            fi
            ;;
        background)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "--list --status --cancel --stats" -- "$cur"))
            fi
            ;;
    esac
}

complete -F _how_completion how
