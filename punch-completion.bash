# punch bash completion with 'add' category and task completion

_punch_complete()
{
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Prefer Snap paths if they exist
    local snap_dir="$HOME/snap/punch/current"
    local config_file
    local tasks_file

    if [[ -f "$snap_dir/.config/punch/punch.yaml" ]]; then
        config_file="$snap_dir/.config/punch/punch.yaml"
    else
        config_file="${XDG_CONFIG_HOME:-$HOME/.config}/punch/punch.yaml"
    fi

    if [[ -f "$snap_dir/.local/share/punch/tasks.txt" ]]; then
        tasks_file="$snap_dir/.local/share/punch/tasks.txt"
    else
        tasks_file="${XDG_DATA_HOME:-$HOME/.local/share}/punch/tasks.txt"
    fi

    # Extract short categories and mapping to full names
    local shorts=""
    local -A short_to_full
    local catname
    if [[ -f "$config_file" ]]; then
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]{2}([A-Za-z0-9\ \-_]+):[[:space:]]*$ ]]; then
                catname="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ short:[[:space:]]*([A-Za-z0-9_]+) ]]; then
                shorts="$shorts ${BASH_REMATCH[1]}"
                short_to_full[${BASH_REMATCH[1]}]="$catname"
            fi
        done < "$config_file"
    fi

    local subcommands="start report export login submit add config help"
    local opts_start="-t --time"
    local opts_report="-f --from -t --to"
    local opts_export="-f --from -t --to --format -o --output"
    local opts_submit="-f --from -t --to -n --dry-run --headed -i --interactive --sleep"
    local opts_config="show edit path set get wizard"
    local opts_global="-v --verbose -V --version -h --help"

    # Subcommand completion
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$subcommands $opts_global" -- "$cur") )
        return 0
    fi

    case "${COMP_WORDS[1]}" in
        start)
            COMPREPLY=( $(compgen -W "$opts_start $opts_global" -- "$cur") )
            return 0
            ;;
        add)
            # punch add <category> :
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "$shorts" -- "$cur") )
                return 0
            elif [[ ${COMP_CWORD} -eq 3 ]]; then
                if [[ "$prev" == *: ]]; then
                    local short="${prev%:}"
                    local fullcat="${short_to_full[$short]}"
                    if [[ -f "$tasks_file" && -n "$fullcat" ]]; then
                        mapfile -t tasks < <(
                            awk -F'|' -v cat="$fullcat" '
                                { gsub(/^[ \t]+|[ \t]+$/, "", $2);
                                  gsub(/^[ \t]+|[ \t]+$/, "", $3); }
                                $2 == cat && $3 != "" { print $3 }
                            ' "$tasks_file" | sort -u
                        )
                        if ((${#tasks[@]})); then
                            local IFS=$'\n'
                            COMPREPLY=( $(compgen -W "$(printf '%s\n' "${tasks[@]}")" -- "$cur") )
                        else
                            COMPREPLY=()
                        fi
                        return 0
                    fi
                elif [[ "$cur" == ":" ]]; then
                    COMPREPLY=( ":" )
                    return 0
                else
                    COMPREPLY=( $(compgen -W ":" -- "$cur") )
                    return 0
                fi
            elif [[ ${COMP_CWORD} -eq 4 && "${COMP_WORDS[3]}" == ":" ]]; then
                local short="${COMP_WORDS[2]}"
                local fullcat="${short_to_full[$short]}"
                if [[ -f "$tasks_file" && -n "$fullcat" ]]; then
                    mapfile -t tasks < <(
                        awk -F'|' -v cat="$fullcat" '
                            { gsub(/^[ \t]+|[ \t]+$/, "", $2);
                              gsub(/^[ \t]+|[ \t]+$/, "", $3); }
                            $2 == cat && $3 != "" { print $3 }
                        ' "$tasks_file" | sort -u
                    )
                    if ((${#tasks[@]})); then
                        local IFS=$'\n'
                        COMPREPLY=( $(compgen -W "$(printf '%s\n' "${tasks[@]}")" -- "$cur") )
                    else
                        COMPREPLY=()
                    fi
                    return 0
                fi
            fi
            ;;
        report)
            COMPREPLY=( $(compgen -W "$opts_report $opts_global" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -W "$opts_export $opts_global" -- "$cur") )
            return 0
            ;;
        login)
            COMPREPLY=( $(compgen -W "$opts_global" -- "$cur") )
            return 0
            ;;
        submit)
            COMPREPLY=( $(compgen -W "$opts_submit $opts_global" -- "$cur") )
            return 0
            ;;
        config)
            # Complete config subcommands and options
            if [[ ${COMP_CWORD} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "$opts_config" -- "$cur") )
                return 0
            elif [[ ${COMP_CWORD} -eq 3 && "${COMP_WORDS[2]}" == "set" ]]; then
                COMPREPLY=( $(compgen -W "option" -- "$cur") )
                return 0
            elif [[ ${COMP_CWORD} -eq 3 && "${COMP_WORDS[2]}" == "get" ]]; then
                COMPREPLY=( $(compgen -W "option" -- "$cur") )
                return 0
            fi
            ;;
        help)
            COMPREPLY=( $(compgen -W "$opts_global" -- "$cur") )
            return 0
            ;;
    esac

    # Fallback: complete nothing
    COMPREPLY=()
}

# Do NOT remove ":" from COMP_WORDBREAKS!
complete -F _punch_complete punch.py punch