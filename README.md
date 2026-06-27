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
| `hooks/graphify-query-nudge.sh` | **the savings.** Reminds Claude to query the graph (not grep) when you ask a codebase question in a graphed project | working |
| `skill/SKILL.md` | the `/graphify-auto` skill — on-demand free refresh | working |
| `policy/policy_engine.py` | Token-free planner: staleness + naming gate | working |
| `install.sh` | installs nudge + skill + engine | working |
| `hooks/graphify-auto-update.sh`, `graphify-flush.sh` | optional always-on refresh (on every edit) | working |
| `FINDINGS.md` | Measured token-cost map of graphify (corrects the design) | — |
| `RESEARCH.md` | Literature grounding (IVM + query-driven extraction) | — |

### The insight that drives this
A fresh graph **saves nothing on its own.** Measured it: across 4 of my repos the graph
*could* cut 77–98% of tokens per question — but realized savings were **~0**, because in
practice Claude (and I) just grep/read files and never query the graph. A graph nobody
queries is pure cost.

So the savings chain has three links, and only the first two were ever built:
1. graph exists  →  `/graphify`
2. graph stays fresh  →  `/graphify-auto` (free)
3. **questions actually go through the graph**  →  `graphify-query-nudge.sh` ← this is the fix

The nudge is the cheap, proactive reminder that closes link 3. Without it, 1 and 2 are theatre.

### The economics fix: build free
Link 1 used to cost **~150–360k tokens** (an LLM-backed build), so the graph only
paid back after **~70 navigation queries** — which almost never happens. But that
cost was optional: `graphify` builds **AST-only with no LLM** for code corpora, and
the graph is still fully queryable (community names are just `Community N`
placeholders — cosmetic).

`/graphify-auto` now builds that way by default: it **strips backend keys** before
building, so the build is guaranteed **~0 tokens**. Break-even drops from ~70
queries to **1**. Every navigation query after that is pure profit.

| | LLM build (old) | Free AST build (now) |
|---|---|---|
| Build cost | ~150–360k | **~0** |
| Break-even | ~70 queries | **1 query** |
| Queryable | yes | yes |
| Community names | pretty | `Community N` (cosmetic) |

So `/graphify-auto <project>` = build-free-if-missing **or** refresh-free, for any
project, at ~0 tokens. (Docs/papers/image corpora can't be AST-parsed and still
need a backend — it says so cleanly instead of failing.)

### When it's actually worth graphing a project
- **Worth it:** big, long-lived, navigation-heavy repos you ask many "how does X
  work / where is Y" questions about.
- **Skip it:** throwaway / hackathon / edit-only projects. Even a free build isn't
  worth maintaining if you never query it — and editing code doesn't use the graph.

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
