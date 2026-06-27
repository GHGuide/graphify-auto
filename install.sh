#!/usr/bin/env bash
# graphify-auto installer. Sets up the full loop, all free, all automatic:
#   1. query-nudge (UserPromptSubmit) -> makes Claude QUERY the graph (the savings)
#   2. auto-update (PostToolUse)       -> smart free refresh on code edits
#   3. flush (Stop)                    -> one full free refresh per turn
#   4. /graphify-auto skill            -> build-free / refresh-free any project on demand
#   5. policy engine                   -> staleness + cheap-build + naming gate
# Idempotent. Spends 0 tokens. Never auto-builds (build a graph once with /graphify).

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$HOME/.graphify-auto"
SKILL_DIR="$HOME/.claude/skills/graphify-auto"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$ENGINE_DIR" "$SKILL_DIR" "$HOOKS_DIR"

install -m 0644 "$SRC/policy/policy_engine.py"        "$ENGINE_DIR/policy_engine.py"
install -m 0644 "$SRC/skill/SKILL.md"                 "$SKILL_DIR/SKILL.md"
install -m 0755 "$SRC/hooks/graphify-query-nudge.sh"  "$HOOKS_DIR/graphify-query-nudge.sh"
install -m 0755 "$SRC/hooks/graphify-auto-update.sh"  "$HOOKS_DIR/graphify-auto-update.sh"
install -m 0755 "$SRC/hooks/graphify-flush.sh"        "$HOOKS_DIR/graphify-flush.sh"

# Register all three hooks (idempotent, backs up settings first).
python3 - "$SETTINGS" "$HOOKS_DIR" <<'PY'
import json, os, sys, shutil
settings, hooks_dir = sys.argv[1], sys.argv[2]
if not os.path.exists(settings):
    json.dump({}, open(settings, 'w'))
shutil.copy2(settings, settings + '.bak-graphifyauto')
d = json.load(open(settings))
h = d.setdefault('hooks', {})

def ensure(event, cmd, matcher=None):
    arr = h.setdefault(event, [])
    if any(cmd in hh.get('command','') for e in arr for hh in e.get('hooks', [])):
        return False
    entry = {"hooks": [{"type": "command", "command": cmd, "async": True, "timeout": 30}]}
    if matcher:
        entry["matcher"] = matcher
    arr.append(entry)
    return True

n = ensure("UserPromptSubmit", f"{hooks_dir}/graphify-query-nudge.sh")
u = ensure("PostToolUse",      f"{hooks_dir}/graphify-auto-update.sh", "Edit|Write|MultiEdit")
f = ensure("Stop",             f"{hooks_dir}/graphify-flush.sh")
json.dump(d, open(settings, 'w'), indent=2)
print(f"hooks registered (new: nudge={n}, auto-update={u}, flush={f})")
PY

echo
echo "Installed + registered (all free, all automatic):"
echo "  query-nudge   UserPromptSubmit   -> reminds Claude to query the graph"
echo "  auto-update   PostToolUse        -> smart free refresh on code edits"
echo "  flush         Stop               -> full free refresh once per turn"
echo "  /graphify-auto skill + engine"
echo
echo "Next: build a graph once (cheap):  /graphify-auto <project>   (free for code repos)"
echo "Then just work — it stays current automatically, and Claude queries it."
