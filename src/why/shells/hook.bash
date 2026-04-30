# why-cli shell hook for bash.
if [[ -n "$WHY_HOOK_LOADED" ]]; then
  return 0 2>/dev/null || exit 0
fi
WHY_HOOK_LOADED=1

_why_preexec_bash() {
  if [[ -n "$COMP_LINE" ]]; then return; fi
  if [[ "$BASH_COMMAND" == "_why_precmd_bash" ]]; then return; fi
  WHY_LAST_CMD="$BASH_COMMAND"
  WHY_LAST_PWD="$PWD"
}

_why_precmd_bash() {
  local code=$?
  if [[ -z "$WHY_LAST_CMD" ]]; then return; fi
  if [[ $code -ne 0 ]]; then WHY_LAST_CMD=; return; fi
  if [[ -n "$WHY_SUPPRESS" ]]; then WHY_LAST_CMD=; return; fi
  WHY_SUPPRESS=1 command why _hook \
    --cmd "$WHY_LAST_CMD" \
    --cwd "$WHY_LAST_PWD" \
    --code $code </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log" || true
  WHY_LAST_CMD=
}

trap '_why_preexec_bash' DEBUG
PROMPT_COMMAND="_why_precmd_bash;${PROMPT_COMMAND}"
