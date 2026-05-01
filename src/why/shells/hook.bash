# why-cli shell hook for bash.
if [[ -n "$WHY_HOOK_LOADED" ]]; then
  return 0 2>/dev/null || exit 0
fi
WHY_HOOK_LOADED=1

# Ring buffer: newline-separated base64-encoded commands, capped at 10.
WHY_HISTORY=""
_WHY_HISTORY_LIMIT=10

_why_preexec_bash() {
  if [[ -n "$COMP_LINE" ]]; then return; fi
  if [[ "$BASH_COMMAND" == "_why_precmd_bash" ]]; then return; fi
  WHY_LAST_CMD="$BASH_COMMAND"
  WHY_LAST_PWD="$PWD"

  local encoded
  encoded=$(printf '%s' "$BASH_COMMAND" | base64 | tr -d '\n')
  if [[ -z "$WHY_HISTORY" ]]; then
    WHY_HISTORY="$encoded"
  else
    WHY_HISTORY="${WHY_HISTORY}"$'\n'"${encoded}"
  fi
  local count
  count=$(printf '%s\n' "$WHY_HISTORY" | wc -l | tr -d ' ')
  if (( count > _WHY_HISTORY_LIMIT )); then
    WHY_HISTORY=$(printf '%s\n' "$WHY_HISTORY" | tail -n $_WHY_HISTORY_LIMIT)
  fi
}

_why_precmd_bash() {
  local code=$?
  if [[ -z "$WHY_LAST_CMD" ]]; then return; fi
  if [[ $code -ne 0 ]]; then WHY_LAST_CMD=; return; fi
  if [[ -n "$WHY_SUPPRESS" ]]; then WHY_LAST_CMD=; return; fi

  local history_plain=""
  if [[ -n "$WHY_HISTORY" ]]; then
    history_plain=$(printf '%s\n' "$WHY_HISTORY" | while IFS= read -r enc; do
      printf '%s\n' "$enc" | base64 --decode 2>/dev/null
      printf '\x1E'
    done)
  fi

  WHY_SUPPRESS=1 command why _hook \
    --cmd "$WHY_LAST_CMD" \
    --cwd "$WHY_LAST_PWD" \
    --code $code \
    --history "$history_plain" \
    </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log" || true
  WHY_LAST_CMD=
}

trap '_why_preexec_bash' DEBUG
PROMPT_COMMAND="_why_precmd_bash${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
