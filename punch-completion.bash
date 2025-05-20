# punch bash completion with 'add' category and task completion

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
    local catname
    if [[ -f "$config_file" ]]; then
        while IFS= read -r line; do
            # Match YAML category name (indented two spaces, ends with colon)
            if [[ "$line" =~ ^[[:space:]]{2}([A-Za-z0-9\ \-_]+):[[:space:]]*$ ]]; then
                catname="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ short:[[:space:]]*([A-Za-z0-9_]+) ]]; then
                shorts="$shorts ${BASH_REMATCH[1]}"
                short_to_full[${BASH_REMATCH[1]}]="$catname"
            fi
        done < "$config_file"
    fi

    local subcommands="start report export login submit add"
    local opts_report="-f --from -t --to"
    local opts_export="-f --from -t --to --format -o --output"
    local opts_submit="-f --from -t --to -n --dry-run --headed"
    local opts_global="-v --version"

    # Subcommand completion
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$subcommands $opts_global" -- "$cur") )
        return 0
    fi

    # Option completion for subcommands
    case "${COMP_WORDS[1]}" in
        report)
            COMPREPLY=( $(compgen -W "$opts_report" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -W "$opts_export" -- "$cur") )
            return 0
            ;;
        submit)
            COMPREPLY=( $(compgen -W "$opts_submit" -- "$cur") )
            return 0
            ;;
        add)
            COMP_WORDBREAKS=${COMP_WORDBREAKS//:/}

            if [[ ${COMP_CWORD} -eq 2 ]]; then
                # Complete category shorts with colon
                COMPREPLY=( $(compgen -S: -W "$shorts" -- "$cur") )
                return 0

            elif [[ ${COMP_CWORD} -eq 3 && "${COMP_WORDS[2]}" == *: ]]; then
                # Complete tasks for the selected category
                local short="${COMP_WORDS[2]%:}"
                local fullcat="${short_to_full[$short]}"
                if [[ -f "$tasks_file" && -n "$fullcat" ]]; then
                    local tasks
                    # Read tasks (field 3) for this category (field 2) from tasks_file
                    mapfile -t tasks < <(
                        awk -F'|' -v cat="$fullcat" '
                            { gsub(/^[ \t]+|[ \t]+$/, "", $2); 
                              gsub(/^[ \t]+|[ \t]+$/, "", $3); }
                            $2 == cat && $3 != "" { print $3 }
                        ' "$tasks_file" | sort -u
                    )
                    # If we found any tasks, build the reply list
                    if ((${#tasks[@]})); then
                        if [[ -z "$cur" ]]; then
                            COMPREPLY=( "${tasks[@]}" )
                        else
                            # Ensure we split only on newline, then compgen on $cur
                            local IFS=$'\n'
                            COMPREPLY=( $(compgen -W "$(printf '%s\n' "${tasks[@]}")" -- "$cur") )
                        fi
                    else
                        COMPREPLY=()
                    fi
                    return 0
                fi
            fi
            ;;
    esac

    # Fallback: complete nothing
    COMPREPLY=()
}
complete -F _punch_complete punch.py punch