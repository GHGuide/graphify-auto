#!/usr/bin/env bash
# graphify-flush.sh
# Stop hook. At the end of each turn, refresh every graphify project that was
# edited during the turn (recorded in .graphify_dirty by graphify-auto-update.sh).
#
# Why: the PostToolUse debounce can skip the final edit of a burst. This flush
# runs once per turn, bypasses the debounce, and guarantees the graph is current
# before the next prompt. `graphify update` is AST-only => ZERO Claude tokens.

set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

command -v graphify >/dev/null 2>&1 || exit 0

dirty="$HOME/.claude/hooks/.graphify_dirty"
[ -f "$dirty" ] || exit 0

# Snapshot + clear so edits arriving during the flush start a fresh batch.
roots="$(sort -u "$dirty" 2>/dev/null)"
: > "$dirty"
[ -n "$roots" ] || exit 0

engine="$HOME/.graphify-auto/policy_engine.py"

while IFS= read -r root; do
  [ -n "$root" ] || continue
  [ -f "$root/graphify-out/graph.json" ] || continue
  date +%s > "$root/graphify-out/.last_auto_update" 2>/dev/null || true
  log="$root/graphify-out/.auto_update.log"
  # Free AST refresh, then optional engine bookkeeping. All backgrounded so the
  # turn never blocks. Chained (&&-style) so bookkeeping sees the refreshed graph.
  ( cd "$root" && {
      graphify update .
      if [ -f "$engine" ]; then
        python3 "$engine" scan-stale . >/dev/null 2>&1 || true
        # Community naming is the ONLY token-costing step -> opt-in only.
        if [ "${GRAPHIFY_AUTO_NAME:-0}" = "1" ]; then
          plan="$(python3 "$engine" decide-naming . --context session-end 2>/dev/null || true)"
          case "$plan" in
            *'"regen_viz": true'*) python3 "$engine" run-naming . >/dev/null 2>&1 || true ;;
          esac
        fi
      fi
    } >"$log" 2>&1 & ) >/dev/null 2>&1
done <<EOF
$roots
EOF

exit 0
