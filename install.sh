#!/usr/bin/env bash
# graphify-auto installer.
# Installs the /graphify-auto skill + the policy engine. Idempotent.
# Skill-invoked model: nothing fires automatically — you run /graphify-auto when
# you want a project's graph refreshed. Spends 0 tokens; never auto-builds graphs.
#
# (Optional always-on hooks also ship under hooks/ — see "Always-on mode" below.)

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$HOME/.graphify-auto"
SKILL_DIR="$HOME/.claude/skills/graphify-auto"

mkdir -p "$ENGINE_DIR" "$SKILL_DIR"

install -m 0644 "$SRC/policy/policy_engine.py" "$ENGINE_DIR/policy_engine.py"
install -m 0644 "$SRC/skill/SKILL.md"          "$SKILL_DIR/SKILL.md"

echo "Installed:"
echo "  $ENGINE_DIR/policy_engine.py"
echo "  $SKILL_DIR/SKILL.md   (skill: /graphify-auto)"
echo
echo "Use it:"
echo "  /graphify <path>        # build a graph once (costs tokens)"
echo "  /graphify-auto <path>   # smart-refresh that graph anytime (free)"
echo "  /graphify-auto status   # show stale files + naming freshness"
echo "  /graphify-auto name     # also re-name communities (costs tokens; needs backend)"
echo
echo "Always-on mode (optional): to refresh on every Claude edit instead of"
echo "on /graphify-auto, install the hooks and register them in settings.json:"
echo "  install -m 0755 $SRC/hooks/*.sh $HOME/.claude/hooks/"
echo '  settings.json hooks: PostToolUse(Edit|Write|MultiEdit)->graphify-auto-update.sh, Stop->graphify-flush.sh'
