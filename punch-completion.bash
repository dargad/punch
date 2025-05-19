# punch.py bash completion with task name completion

_punch_complete()
{
    local cur prev words cword
    _init_completion || return

    # Paths
    local config_file="${XDG_CONFIG_HOME:-$HOME/.config}/punch/punch.yaml"
    local tasks_file="${XDG_DATA_HOME:-$HOME/.local/share}/punch/tasks.txt"

    # Extract short categories and mapping to full names
    local shorts
    local -A short_to_full
    if [[ -f "$config_file" ]]; then
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]*([A-Za-z0-9\ \-_]+):[[:space:]]*$ ]]; then
                catname="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ short:\ ([^[:space:]]+) ]]; then
                shorts="$shorts ${BASH_REMATCH[1]}"
                short_to_full[${BASH_REMATCH[1]}]="$catname"
            fi
        done < "$config_file"
    fi

    local subcommands="new report export login submit"
    local opts_report="-f --from -t --to"
    local opts_export="-f --from -t --to --format -o --output"
    local opts_submit="-f --from -t --to -n --dry-run --headed"
    local opts_global="-v --version"

    # If first arg is not a subcommand, suggest quick task entry
    if [[ ${COMP_CWORD} -eq 1 && ! " $subcommands " =~ " ${cur} " ]]; then
        COMPREPLY=( $(compgen -W "$shorts" -- "$cur") )
        return 0
    fi

    # Subcommand completion
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$subcommands $opts_global" -- "$cur") )
        return 0
    fi

    # Option completion for subcommands
    case "${COMP_WORDS[1]}" in
        report)
            COMPREPLY=( $(compgen -W "$opts_report" -- "$cur") )
            ;;
        export)
            COMPREPLY=( $(compgen -W "$opts_export" -- "$cur") )
            ;;
        submit)
            COMPREPLY=( $(compgen -W "$opts_submit" -- "$cur") )
            ;;
        *)
            ;;
    esac

    # Quick task entry: <short-category> : <task name> [: notes]
    # Detect if we are after "<short> :"
    if [[ ${COMP_CWORD} -ge 3 ]]; then
        local prev_short="${COMP_WORDS[1]}"
        local prev_colon="${COMP_WORDS[2]}"
        if [[ " $shorts " =~ " $prev_short " && "$prev_colon" == ":" ]]; then
            # Find full category name
            local fullcat="${short_to_full[$prev_short]}"
            # Extract tasks for this category from tasks.txt
            if [[ -f "$tasks_file" && -n "$fullcat" ]]; then
                local tasks
                tasks=$(awk -F'|' -v cat="$fullcat" '{gsub(/^ +| +$/,"",$0); if ($2 == cat) print $3}' "$tasks_file" | sort -u)
                COMPREPLY=( $(compgen -W "$tasks" -- "$cur") )
                return 0
            fi
        fi
    fi

    # If after "<short> :", complete nothing (so user can type a new task)
    if [[ ${COMP_CWORD} -eq 3 && "${COMP_WORDS[2]}" == ":" ]]; then
        COMPREPLY=()
        return 0
    fi
}
complete -F _punch_complete punch
