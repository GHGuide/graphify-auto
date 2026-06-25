# graphify-auto

Keep [graphify](https://github.com/safishamsi/graphify) knowledge graphs fresh
automatically while you work in Claude Code — without a persistent watcher
process and without git hooks.

> **Unofficial companion** to graphify. Not affiliated with the graphify project.
> graphify does the real work; this is glue + an update policy.

## The honest pitch

Measured, not assumed (see [FINDINGS.md](FINDINGS.md)): almost everything graphify
does to keep a graph **query-fresh costs zero tokens**.

- `graphify update` / `extract` (AST) — **free**, no backend.
- re-clustering — **free**.
- `query` — **free**, and works fine on an *unnamed* graph.
- community **naming** — the *only* LLM/token step, and it's cosmetic for querying.

So the design is small and honest:

- **Keep graphs query-fresh continuously** — it's free, so just run `graphify
  update` on every edit. (This is the whole win, and it already works.)
- **Gate the one paid step (naming).** Never re-name communities per edit. Re-name
  lazily, only when a backend is set *and* structure changed materially *and* the
  named report is about to be used. With no backend it's a clean no-op.

It is not an AI deciding when to update — it's the observation that graphify is
already ~free to keep fresh, so the job is mostly *not wasting* tokens on naming.
See [STRATEGY.md](STRATEGY.md) and [FINDINGS.md](FINDINGS.md).

## What's here

| Path | What it is | Status |
|---|---|---|
| `hooks/graphify-auto-update.sh` | PostToolUse hook: refresh graph on edit (free, AST) | working |
| `hooks/graphify-flush.sh` | Stop hook: flush edited projects at turn end | working |
| `policy/policy_engine.py` | Token-free planner: staleness + naming gate | working |
| `FINDINGS.md` | Measured token-cost map of graphify (corrects the design) | — |
| `RESEARCH.md` | Literature grounding (IVM + query-driven extraction) | — |

The two hooks are live and tested. The policy engine is a **working, token-free
planner**: staleness via content-hash diff, query→file mapping from `source_file`
nodes (verified on a real 10k-node graph, <0.1s), and `decide_naming` — the gate
for the only paid step. Per-file `merge-graphs` splice was **removed** after
testing showed it namespaces ids and drops labels (FINDINGS.md).

## Install (hooks only, today)

1. `uv tool install graphifyy` (the graphify CLI)
2. Copy `hooks/*.sh` to `~/.claude/hooks/` and `chmod +x` them.
3. Add to `~/.claude/settings.json`:

```json
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
```

4. Build each project once by hand: `/graphify .`. After that the hooks keep it fresh.

## Limits (read before believing the marketing)

- Fires only when **Claude Code** edits a file. External-editor edits are missed
  (use `graphify <path> --watch` for those).
- Free refresh covers **code structure only**. Doc/spec meaning needs a semantic
  rebuild — that's what the policy engine is for, and it's not built yet.
- Updates regenerate `graph.html` by default → disk churn. The policy engine
  moves viz regen out of the hot path; until then, watch `graphify-out/` size.

## License

Match graphify's license. Credit: built on top of
[safishamsi/graphify](https://github.com/safishamsi/graphify).
