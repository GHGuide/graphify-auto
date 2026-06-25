#!/usr/bin/env bash
# graphify-auto installer.
# Copies the hooks + policy engine into place and prints the settings.json
# snippet to enable them. Idempotent. Spends 0 tokens; never auto-builds graphs.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"
ENGINE_DIR="$HOME/.graphify-auto"

mkdir -p "$HOOKS_DIR" "$ENGINE_DIR"

install -m 0755 "$SRC/hooks/graphify-auto-update.sh" "$HOOKS_DIR/graphify-auto-update.sh"
install -m 0755 "$SRC/hooks/graphify-flush.sh"       "$HOOKS_DIR/graphify-flush.sh"
install -m 0644 "$SRC/policy/policy_engine.py"       "$ENGINE_DIR/policy_engine.py"

echo "Installed:"
echo "  $HOOKS_DIR/graphify-auto-update.sh"
echo "  $HOOKS_DIR/graphify-flush.sh"
echo "  $ENGINE_DIR/policy_engine.py"
echo
echo "Add this to ~/.claude/settings.json (hooks block):"
cat <<'JSON'
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "$HOME/.claude/hooks/graphify-auto-update.sh", "async": true }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "$HOME/.claude/hooks/graphify-flush.sh", "async": true }] }
    ]
  }
}
JSON
echo
echo "Then build each project once by hand:  graphify .   (or /graphify . in Claude Code)"
echo
echo "Optional: community-name auto-refresh costs LLM tokens and is OFF by default."
echo "Enable per-shell with a backend configured:"
echo "  export GRAPHIFY_AUTO_NAME=1   (and e.g. GOOGLE_API_KEY=...)"
