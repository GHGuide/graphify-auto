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
| `skill/SKILL.md` | the `/graphify-auto` skill — on-demand smart refresh | working |
| `policy/policy_engine.py` | Token-free planner: staleness + naming gate | working |
| `install.sh` | installs skill + engine | working |
| `hooks/*.sh` | optional always-on mode (refresh on every edit) | working |
| `FINDINGS.md` | Measured token-cost map of graphify (corrects the design) | — |
| `RESEARCH.md` | Literature grounding (IVM + query-driven extraction) | — |

Primary model is **skill-invoked**: nothing fires automatically — you run
`/graphify-auto` when you want a project refreshed. The policy engine is a
**working, token-free planner**: staleness via content-hash diff, query→file
mapping from `source_file` nodes (verified on a real 10k-node graph, <0.1s), and
`decide_naming` — the gate for the only paid step. Per-file `merge-graphs` splice
was **removed** after testing showed it namespaces ids and drops labels
(FINDINGS.md).

## Install

1. `uv tool install graphifyy` (the graphify CLI)
2. `bash install.sh` — installs the engine + the `/graphify-auto` skill.
3. Build a graph once (costs tokens): `/graphify <path>`.
4. Refresh it anytime (free): `/graphify-auto <path>`.

```
/graphify-auto              # smart-refresh current dir's graph
/graphify-auto status       # show stale files + naming freshness
/graphify-auto name         # also re-name communities (costs tokens; needs backend)
```

**Always-on mode (optional):** to refresh on every Claude edit instead of on
demand, install `hooks/*.sh` to `~/.claude/hooks/` and register them in
`settings.json` (PostToolUse `Edit|Write|MultiEdit` → `graphify-auto-update.sh`,
Stop → `graphify-flush.sh`). `install.sh` prints the exact lines.

## Limits (read before believing the marketing)

- Skill model is **on-demand** — you must run `/graphify-auto`. (Always-on hooks
  exist but see external-edit caveat below.)
- Refresh covers **code structure** (AST). That's free and keeps queries
  accurate. Community **names** only refresh via `name` + a backend.
- Convenience over capability: `graphify --watch` catches external-editor edits
  too; this only sees graphs you point it at.
- Keeping a graph query-fresh is already ~0 tokens in graphify — so the headline
  win is convenience, not token savings (FINDINGS.md is honest about this).

## License

Match graphify's license. Credit: built on top of
[safishamsi/graphify](https://github.com/safishamsi/graphify).
