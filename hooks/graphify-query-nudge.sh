#!/usr/bin/env bash
# graphify-query-nudge.sh
# UserPromptSubmit hook. The missing link that turns a fresh graph into real
# token savings: when you're working inside a project that HAS a graphify graph
# and you ask a codebase/architecture question, remind Claude to `graphify query`
# first instead of defaulting to Read/Grep (which costs ~10-40x more tokens).
#
# Why a hook (not the skill): the skill only runs when invoked. The whole problem
# is Claude doesn't THINK to query — so the nudge must fire proactively. This
# uses UserPromptSubmit additionalContext, the same injection path that reliably
# delivers context to the model.
#
# Low-noise by design:
#   - silent unless cwd is inside a built graph
#   - silent unless the prompt looks like a codebase question (keyword gate)
#   - flags staleness (via the policy engine) so Claude knows to refresh first

set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

payload="$(cat)"
command -v jq >/dev/null 2>&1 || exit 0

cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null)"
prompt="$(printf '%s' "$payload" | jq -r '.prompt // empty' 2>/dev/null)"
[ -n "$cwd" ] || cwd="$PWD"

# Walk up to the nearest project holding a built graph.
root=""; cur="$cwd"
while [ -n "$cur" ] && [ "$cur" != "/" ]; do
  if [ -f "$cur/graphify-out/graph.json" ]; then root="$cur"; break; fi
  cur="$(dirname "$cur")"
done
[ -n "$root" ] || exit 0   # not in a graphed project -> nothing to nudge

# Keyword gate: only nudge on codebase-ish questions, not edit-ops / chit-chat.
low="$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]')"
case "$low" in
  *how\ *|*what\ *|*where\ *|*why\ *|*explain*|*architect*|*\ find*|*which*|\
  *understand*|*flow*|*structure*|*depend*|*overview*|*trace*|*entry\ point*|\
  *call*|*relate*|*connect*|*module*|*component*|*where\ is*|*how\ does*) : ;;
  *) exit 0 ;;
esac

# Freshness check via the policy engine (optional).
fresh_note=""
ENG="$HOME/.graphify-auto/policy_engine.py"
if [ -f "$ENG" ]; then
  stale="$(python3 "$ENG" status "$root" 2>/dev/null \
    | python3 -c "import sys,json;print(len(json.load(sys.stdin).get('stale',[])))" 2>/dev/null || echo 0)"
  if [ "${stale:-0}" -gt 0 ] 2>/dev/null; then
    fresh_note=" NOTE: the graph may be stale ($stale changed file(s)); run /graphify-auto $root to refresh (free) before trusting it."
  fi
fi

proj="$(basename "$root")"
msg="This project ($proj) has a graphify knowledge graph at $root/graphify-out/. For codebase / architecture questions, query it FIRST: \`cd $root && graphify query \"<your question>\"\` — it returns the relevant subgraph for ~10-40x fewer tokens than reading files. Fall back to Grep/Read only if the graph doesn't answer.$fresh_note"

jq -nc --arg c "$msg" '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
exit 0
