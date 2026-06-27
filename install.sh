#!/usr/bin/env bash
# graphify-auto installer.
# Installs three things, in order of how much they matter:
#   1. query-nudge hook  -> the piece that makes the token savings REAL: when you
#      ask a codebase question inside a graphed project, it reminds Claude to
#      `graphify query` instead of grepping (a fresh graph nobody queries saves 0).
#   2. /graphify-auto skill -> on-demand free refresh (keeps the graph fresh).
#   3. policy engine -> staleness tracking + naming gate.
# Idempotent. Spends 0 tokens. Never auto-builds graphs.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$HOME/.graphify-auto"
SKILL_DIR="$HOME/.claude/skills/graphify-auto"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$ENGINE_DIR" "$SKILL_DIR" "$HOOKS_DIR"

install -m 0644 "$SRC/policy/policy_engine.py"     "$ENGINE_DIR/policy_engine.py"
install -m 0644 "$SRC/skill/SKILL.md"              "$SKILL_DIR/SKILL.md"
install -m 0755 "$SRC/hooks/graphify-query-nudge.sh" "$HOOKS_DIR/graphify-query-nudge.sh"

# Register the query-nudge as a UserPromptSubmit hook (idempotent, backs up first).
python3 - "$SETTINGS" "$HOOKS_DIR/graphify-query-nudge.sh" <<'PY'
import json, os, sys, shutil
settings, cmd = sys.argv[1], sys.argv[2]
if not os.path.exists(settings):
    json.dump({}, open(settings, 'w'))
shutil.copy2(settings, settings + '.bak-graphifyauto')
d = json.load(open(settings))
ups = d.setdefault('hooks', {}).setdefault('UserPromptSubmit', [])
if not any(cmd in hh.get('command','') for e in ups for hh in e.get('hooks', [])):
    ups.append({"hooks": [{"type": "command", "command": cmd, "timeout": 15}]})
    json.dump(d, open(settings, 'w'), indent=2)
    print("registered query-nudge (UserPromptSubmit)")
else:
    print("query-nudge already registered")
PY

echo
echo "Installed:"
echo "  $HOOKS_DIR/graphify-query-nudge.sh   <- nudges Claude to query the graph (the savings)"
echo "  $SKILL_DIR/SKILL.md                  <- /graphify-auto skill (free refresh)"
echo "  $ENGINE_DIR/policy_engine.py"
echo
echo "Use it:"
echo "  /graphify <path>        # build a graph once (costs tokens)"
echo "  /graphify-auto <path>   # refresh it anytime (free)"
echo "  ...then just ask codebase questions while working in that project — the"
echo "  nudge reminds Claude to query the graph (~10-40x fewer tokens than reading)."
echo
echo "Always-on refresh (optional): install hooks/graphify-auto-update.sh +"
echo "graphify-flush.sh and register PostToolUse/Stop to refresh on every edit."
