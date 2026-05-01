if set -q WHY_HOOK_LOADED
    exit 0
end
set -g WHY_HOOK_LOADED 1

# Ring buffer: list of base64-encoded commands, capped at 10.
set -g WHY_HISTORY
set -g _WHY_HISTORY_LIMIT 10

function _why_preexec --on-event fish_preexec
    set -g WHY_LAST_CMD $argv[1]
    set -g WHY_LAST_PWD $PWD

    set -l encoded (printf '%s' $argv[1] | base64 | tr -d '\n')
    set -g WHY_HISTORY $WHY_HISTORY $encoded
    if test (count $WHY_HISTORY) -gt $_WHY_HISTORY_LIMIT
        set -g WHY_HISTORY $WHY_HISTORY[(math (count $WHY_HISTORY) - $_WHY_HISTORY_LIMIT + 1)..-1]
    end
end

function _why_postexec --on-event fish_postexec
    set -l code $status
    if test -z "$WHY_LAST_CMD"
        return
    end
    if test $code -ne 0
        set -e WHY_LAST_CMD
        return
    end
    if set -q WHY_SUPPRESS
        set -e WHY_LAST_CMD
        return
    end

    set -l history_plain ""
    for enc in $WHY_HISTORY
        set history_plain $history_plain(printf '%s\n' $enc | base64 --decode 2>/dev/null)(printf '\x1E')
    end

    WHY_SUPPRESS=1 command why _hook \
        --cmd "$WHY_LAST_CMD" \
        --cwd "$WHY_LAST_PWD" \
        --code $code \
        --history "$history_plain" \
        </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log"
    set -e WHY_LAST_CMD
end
