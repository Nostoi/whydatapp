# why-cli shell hook for zsh.
WHY_HOOK_VERSION=3
if [[ -n $WHY_HOOK_LOADED ]]; then
  return
fi
WHY_HOOK_LOADED=1

# The `2>>"$HOME/.why/hook.log"` redirects below are expanded by the shell *before*
# the command runs, so a missing directory prints to the terminal and `|| true`
# cannot suppress it. Create it once at load rather than on every prompt.
[[ -d "$HOME/.why" ]] || mkdir -p "$HOME/.why" 2>/dev/null

autoload -Uz add-zsh-hook 2>/dev/null

# Ring buffer: newline-separated base64-encoded commands, capped at 10.
WHY_HISTORY=""
_WHY_HISTORY_LIMIT=10
_WHY_PROMPT_TAG="[why rec] "

# NOTE: do not name a local `status` here — in zsh it is a read-only alias for $?
# and the assignment aborts the whole function (and the rest of precmd with it).
_why_update_prompt() {
  local _why_status _why_base
  _why_status=$(WHY_SUPPRESS=1 command why follow status --porcelain 2>/dev/null || printf 'inactive')
  # Derive the base from the *current* PROMPT, not a load-time snapshot, so that
  # themes which recompute PROMPT each draw (starship, p10k, git status) keep working.
  _why_base="${PROMPT#"$_WHY_PROMPT_TAG"}"
  if [[ "$_why_status" == "active" ]]; then
    PROMPT="${_WHY_PROMPT_TAG}${_why_base}"
  else
    PROMPT="$_why_base"
  fi
}

_why_preexec() {
  WHY_LAST_CMD="$1"
  WHY_LAST_PWD="$PWD"

  # Append to ring buffer (base64-encode to survive newlines/special chars).
  local encoded
  encoded=$(printf '%s' "$1" | base64 | tr -d '\n')
  if [[ -z $WHY_HISTORY ]]; then
    WHY_HISTORY="$encoded"
  else
    WHY_HISTORY="${WHY_HISTORY}"$'\n'"${encoded}"
  fi
  # Trim to last _WHY_HISTORY_LIMIT lines.
  local count
  count=$(printf '%s\n' "$WHY_HISTORY" | wc -l | tr -d ' ')
  if (( count > _WHY_HISTORY_LIMIT )); then
    WHY_HISTORY=$(printf '%s\n' "$WHY_HISTORY" | tail -n $_WHY_HISTORY_LIMIT)
  fi
}

_why_precmd() {
  local code=$?
  _why_update_prompt
  if [[ -z $WHY_LAST_CMD ]]; then
    return
  fi
  if [[ -n $WHY_SUPPRESS ]]; then
    WHY_LAST_CMD=
    return
  fi

  WHY_SUPPRESS=1 command why _record \
    --cmd "$WHY_LAST_CMD" \
    --cwd "$WHY_LAST_PWD" \
    --code $code \
    --shell zsh \
    >/dev/null 2>>"$HOME/.why/hook.log" || true

  if [[ $code -ne 0 ]]; then
    WHY_LAST_CMD=
    return
  fi

  # Decode ring buffer into newline-separated plain commands for --history.
  local history_plain=""
  if [[ -n $WHY_HISTORY ]]; then
    history_plain=$(printf '%s\n' "$WHY_HISTORY" | while IFS= read -r enc; do
      printf '%s\n' "$enc" | base64 --decode 2>/dev/null
      printf '\x1E'  # record separator between commands
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

if typeset -f add-zsh-hook >/dev/null 2>&1; then
  add-zsh-hook preexec _why_preexec
  add-zsh-hook precmd  _why_precmd
fi
