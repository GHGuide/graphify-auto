---
name: graphify-auto
description: "On-demand smart refresh of a graphify knowledge graph. Use when the user types /graphify-auto, or asks to refresh/update/sync a graphify graph after edits without rebuilding from scratch. Runs the free AST update, tracks which files went stale, and gates the only token-costing step (community naming). Does NOT build graphs — use /graphify for that."
---

# /graphify-auto

On-demand, token-aware refresh for an already-built graphify graph. Replaces the
old always-on edit hooks: nothing fires automatically — you run this when you
want the current project's graph brought up to date.

Why it's cheap: `graphify update` (AST) is free; only community **naming** costs
LLM tokens, so naming is opt-in. See the graphify-auto repo for FINDINGS/STRATEGY.

## Usage

```
/graphify-auto              # smart-refresh the current directory's graph
/graphify-auto <path>       # refresh the graph at <path>
/graphify-auto status       # show stale files + naming freshness, change nothing
/graphify-auto name         # also re-run community naming (costs tokens; needs a backend)
```

## What to do when invoked

Engine lives at `~/.graphify-auto/policy_engine.py` (installed by graphify-auto).
All paths below assume `graphify` is on PATH (`export PATH="$HOME/.local/bin:$PATH"`).

1. **Resolve the project root.** From the given path (or cwd), walk up to the
   nearest ancestor containing `graphify-out/graph.json`.
   - If none found: tell the user this folder has no graph yet and to run
     `/graphify <path>` once first. **Do not build** — building costs tokens.

2. **`status` subcommand** → run only this, then report, stop:
   ```
   python3 ~/.graphify-auto/policy_engine.py status <root>
   ```

3. **Default / `name` refresh:**
   ```
   # free AST refresh (no tokens)
   ( cd <root> && graphify update . )
   # bookkeeping: which files changed since last refresh
   python3 ~/.graphify-auto/policy_engine.py scan-stale <root>
   # gate the paid step
   python3 ~/.graphify-auto/policy_engine.py decide-naming <root> --context manual
   ```

4. **Naming (only if user said `name`, or `GRAPHIFY_AUTO_NAME=1`):** if
   `decide-naming` returned `"regen_viz": true` AND a backend key is set
   (`GOOGLE_API_KEY`/`GEMINI_API_KEY`), run:
   ```
   python3 ~/.graphify-auto/policy_engine.py run-naming <root>
   ```
   Otherwise tell the user naming was skipped and why (no backend / not stale).

5. **Report** compactly: project root, nodes/links count, files refreshed,
   stale set, naming decision, and tokens spent (0 unless naming actually ran).

## Rules
- Never auto-build a graph. Only refresh existing ones.
- Naming is the only token-costing action — never run it without `name` or the
  env opt-in.
- Keep it to the resolved project; do not touch other graphs.
