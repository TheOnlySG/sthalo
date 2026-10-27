#!/usr/bin/env bash
# Fast tracked-file secret scan for CI. This complements provider-side scanning;
# it is intentionally conservative and does not inspect untracked local files.
set -euo pipefail

cd "$(dirname "$0")/.."

fail=0

tracked_envs="$(git ls-files | grep -E '(^|/)\.env($|\.)' | grep -vE '\.env\.example$' || true)"
if [[ -n "$tracked_envs" ]]; then
  echo "Tracked environment files are not allowed:" >&2
  echo "$tracked_envs" >&2
  fail=1
fi

patterns=(
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
  'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'
  'sk-[A-Za-z0-9]{20,}'
  'SUPABASE_SERVICE_ROLE_KEY=[^r<]'
  'SUPABASE_SECRET_KEY=[^r<]'
)

for pattern in "${patterns[@]}"; do
  matches="$(
    git grep -nIE -e "$pattern" -- . ':(exclude)*.lock' \
      ':(exclude)scripts/check_secrets.sh' || true
  )"
  if [[ -n "$matches" ]]; then
    echo "Potential secret matched /$pattern/:" >&2
    echo "$matches" >&2
    fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "No tracked secrets matched the fast scan patterns."
