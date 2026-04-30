#!/usr/bin/env bash
# pre-commit hook: rebuild tailwind.css when templates change.
# Runs only if any staged file lives under src/why/web/templates/.
# Exits 0 when there's nothing to do; non-zero only on real build failure.

set -e

TEMPLATES_CHANGED=$(git diff --cached --name-only --diff-filter=ACMR | grep -E '^src/why/web/templates/' || true)
if [ -z "$TEMPLATES_CHANGED" ]; then
  exit 0
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "::error::pre-commit: npx not found, can't rebuild tailwind.css." >&2
  echo "Install Node (https://nodejs.org/) or skip with 'git commit --no-verify' (then rebuild before pushing)." >&2
  exit 1
fi

echo "pre-commit: templates changed → rebuilding src/why/web/static/css/tailwind.css"
npx --yes tailwindcss@3 \
  -i src/why/web/static/css/tailwind.src.css \
  -o src/why/web/static/css/tailwind.css \
  --minify >/dev/null

if ! grep -q '\.flex' src/why/web/static/css/tailwind.css; then
  echo "::error::pre-commit: rebuilt tailwind.css is missing utility classes — refusing to commit." >&2
  exit 1
fi

git add src/why/web/static/css/tailwind.css
echo "pre-commit: tailwind.css rebuilt and staged."
