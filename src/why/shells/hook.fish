if set -q WHY_HOOK_LOADED
    exit 0
end
set -g WHY_HOOK_LOADED 1

function _why_preexec --on-event fish_preexec
    set -g WHY_LAST_CMD $argv[1]
    set -g WHY_LAST_PWD $PWD
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
    WHY_SUPPRESS=1 command why _hook \
        --cmd "$WHY_LAST_CMD" \
        --cwd "$WHY_LAST_PWD" \
        --code $code </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log"
    set -e WHY_LAST_CMD
end
