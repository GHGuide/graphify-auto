#!/usr/bin/env bash
# graphify-auto-update.sh  (PostToolUse: Edit|Write|MultiEdit)
# Smart automatic refresh. Fires only when an update is actually worth doing:
#
#   WHEN (smart gating):
#     - the edited file is CODE (AST update only handles code; skip docs/json/etc)
#     - it lives inside a project that already has a built graph
#     - not within the 90s debounce window (coalesce edit bursts)
#
#   HOW (cheap + no disk churn):
#     - light incremental update: `graphify update . --no-cluster`
#       (re-extracts only changed code files; skips clustering + graph.html, so
#        rapid editing never regenerates the heavy HTML — that's what fills disks)
#     - marks the project dirty so the Stop flush does ONE full refresh per turn
#
# AST update is free (no LLM) => zero Claude tokens. Never auto-builds.

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
command -v graphify >/dev/null 2>&1 || exit 0
command -v jq       >/dev/null 2>&1 || exit 0

payload="$(cat)"
file="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null || true)"
[ -n "$file" ] || exit 0

# Smart gate 1: only react to CODE edits (AST update can't use anything else).
case "$file" in
  *.py|*.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.go|*.rs|*.java|*.rb|*.c|*.cc|*.cpp|\
  *.h|*.hpp|*.cs|*.php|*.swift|*.kt|*.scala|*.m|*.mm) : ;;
  *) exit 0 ;;
esac

dir="$(dirname "$file")"; [ -d "$dir" ] || exit 0

# Smart gate 2: must be inside a built graph (never auto-build).
root=""; cur="$dir"
while [ -n "$cur" ] && [ "$cur" != "/" ]; do
  if [ -f "$cur/graphify-out/graph.json" ]; then root="$cur"; break; fi
  cur="$(dirname "$cur")"
done
[ -n "$root" ] || exit 0

# Mark dirty -> Stop flush does one full refresh per turn.
dirty="$HOME/.claude/hooks/.graphify_dirty"
grep -qxF "$root" "$dirty" 2>/dev/null || echo "$root" >> "$dirty"

# Smart gate 3: debounce (90s) so a burst of edits doesn't stack rebuilds.
stamp="$root/graphify-out/.last_auto_update"
now="$(date +%s)"
if [ -f "$stamp" ]; then
  last="$(cat "$stamp" 2>/dev/null || echo 0)"; [ "$last" -gt 0 ] 2>/dev/null || last=0
  if [ "$(( now - last ))" -lt 90 ]; then exit 0; fi
fi
echo "$now" > "$stamp"

# Light, detached, free: structure only, no clustering/html (deferred to flush).
log="$root/graphify-out/.auto_update.log"
( cd "$root" && nohup graphify update . --no-cluster >"$log" 2>&1 & ) >/dev/null 2>&1
exit 0
