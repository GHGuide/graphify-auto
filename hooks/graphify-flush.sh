#!/usr/bin/env bash
# graphify-flush.sh  (Stop hook)
# Once per turn, do the FULL free refresh for every project edited this turn:
#   - `graphify update .`  -> incremental AST re-extract + clustering + report/html
#     (the heavy parts the per-edit hook deferred; runs at most once per turn)
#   - policy_engine scan-stale -> refresh the content-hash stale set so the
#     query-nudge's "may be stale" signal stays accurate
#
# Guarantees the graph is current + clustered before the next prompt. Bypasses
# the 90s debounce. AST-only => ZERO Claude tokens. Never auto-builds.

set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
command -v graphify >/dev/null 2>&1 || exit 0

dirty="$HOME/.claude/hooks/.graphify_dirty"
[ -f "$dirty" ] || exit 0

# Snapshot + clear so edits during the flush start a fresh batch.
roots="$(sort -u "$dirty" 2>/dev/null)"
: > "$dirty"
[ -n "$roots" ] || exit 0

ENG="$HOME/.graphify-auto/policy_engine.py"

while IFS= read -r root; do
  [ -n "$root" ] || continue
  [ -f "$root/graphify-out/graph.json" ] || continue
  date +%s > "$root/graphify-out/.last_auto_update" 2>/dev/null || true
  log="$root/graphify-out/.auto_update.log"
  # full update, then re-baseline (graph now reflects code -> drift back to 0);
  # detached so Stop returns fast.
  (
    cd "$root" && graphify update . >"$log" 2>&1
    [ -f "$ENG" ] && python3 "$ENG" mark-fresh "$root" >/dev/null 2>&1
  ) &
done <<EOF
$roots
EOF
exit 0
