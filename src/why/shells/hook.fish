set -g WHY_HOOK_VERSION 3
if set -q WHY_HOOK_LOADED
    exit 0
end
set -g WHY_HOOK_LOADED 1

# See hook.zsh: the hook.log redirects are expanded before the command runs, so a
# missing directory would print to the terminal unsuppressably.
test -d "$HOME/.why"; or mkdir -p "$HOME/.why" 2>/dev/null

# Ring buffer: list of base64-encoded commands, capped at 10.
set -g WHY_HISTORY
set -g _WHY_HISTORY_LIMIT 10

if functions -q fish_prompt; and not functions -q _why_original_fish_prompt
    functions -c fish_prompt _why_original_fish_prompt
    function fish_prompt
        # NOTE: do not name this `status` — $status is read-only in fish, as it is
        # in zsh, where the same mistake silently disabled the entire hook.
        set -l _why_status (WHY_SUPPRESS=1 command why follow status --porcelain 2>/dev/null; or echo inactive)
        if test "$_why_status" = active
            printf '[why rec] '
        end
        _why_original_fish_prompt
    end
end

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
    if set -q WHY_SUPPRESS
        set -e WHY_LAST_CMD
        return
    end

    WHY_SUPPRESS=1 command why _record \
        --cmd "$WHY_LAST_CMD" \
        --cwd "$WHY_LAST_PWD" \
        --code $code \
        --shell fish \
        >/dev/null 2>>"$HOME/.why/hook.log"; or true

    if test $code -ne 0
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
        </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log"; or true
    set -e WHY_LAST_CMD
end
