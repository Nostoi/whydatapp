# why-cli shell hook for zsh.
if [[ -n $WHY_HOOK_LOADED ]]; then
  return
fi
WHY_HOOK_LOADED=1

autoload -Uz add-zsh-hook 2>/dev/null

_why_preexec() {
  WHY_LAST_CMD="$1"
  WHY_LAST_PWD="$PWD"
}

_why_precmd() {
  local code=$?
  if [[ -z $WHY_LAST_CMD ]]; then
    return
  fi
  if [[ $code -ne 0 ]]; then
    WHY_LAST_CMD=
    return
  fi
  if [[ -n $WHY_SUPPRESS ]]; then
    WHY_LAST_CMD=
    return
  fi
  WHY_SUPPRESS=1 command why _hook \
    --cmd "$WHY_LAST_CMD" \
    --cwd "$WHY_LAST_PWD" \
    --code $code </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log" || true
  WHY_LAST_CMD=
}

if typeset -f add-zsh-hook >/dev/null 2>&1; then
  add-zsh-hook preexec _why_preexec
  add-zsh-hook precmd  _why_precmd
fi
