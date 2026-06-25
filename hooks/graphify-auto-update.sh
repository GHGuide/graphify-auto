#!/usr/bin/env bash
# graphify-auto-update.sh
# PostToolUse hook (Edit|Write|MultiEdit).
# After Claude edits a file, if that file lives inside a project that already
# has a built graphify graph (graphify-out/graph.json), refresh the graph
# incrementally: `graphify update` is AST-only, no LLM, free, changed-files-only.
#
# Rules:
#   - Only UPDATES existing graphs. Never auto-builds (building costs tokens;
#     run `/graphify .` once per project by hand).
#   - Debounced (90s per project) so rapid multi-file edits don't stack rebuilds.
#   - Fully detached + non-blocking so the edit is never slowed down.
#   - Silent no-op when the edited file isn't inside a graphified project.

set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

# graphify must be installed; otherwise do nothing.
command -v graphify >/dev/null 2>&1 || exit 0

# Read the hook payload from stdin and pull out the edited file path.
payload="$(cat)"
file="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null || true)"
[ -n "$file" ] || exit 0

dir="$(dirname "$file")"
[ -d "$dir" ] || exit 0

# Walk up to find the nearest ancestor holding graphify-out/graph.json.
root=""
cur="$dir"
while [ -n "$cur" ] && [ "$cur" != "/" ]; do
  if [ -f "$cur/graphify-out/graph.json" ]; then
    root="$cur"
    break
  fi
  cur="$(dirname "$cur")"
done
[ -n "$root" ] || exit 0   # not inside any built graph -> nothing to update

# Record this project as "dirty" so the Stop-hook flush refreshes it at the end
# of the turn. This guarantees trailing edits are captured even when the
# debounce below skips the final edit of a burst.
dirty="$HOME/.claude/hooks/.graphify_dirty"
grep -qxF "$root" "$dirty" 2>/dev/null || echo "$root" >> "$dirty"

# Debounce: skip if this project was refreshed less than 90s ago.
stamp="$root/graphify-out/.last_auto_update"
now="$(date +%s)"
if [ -f "$stamp" ]; then
  last="$(cat "$stamp" 2>/dev/null || echo 0)"
  [ "$last" -gt 0 ] 2>/dev/null || last=0
  if [ "$(( now - last ))" -lt 90 ]; then
    exit 0
  fi
fi
echo "$now" > "$stamp"

# Refresh in the background, fully detached. AST-only, no API cost.
log="$root/graphify-out/.auto_update.log"
( cd "$root" && nohup graphify update . >"$log" 2>&1 & ) >/dev/null 2>&1

exit 0
