# graphify-auto

Keep [graphify](https://github.com/safishamsi/graphify) knowledge graphs fresh
automatically while you work in Claude Code — without a persistent watcher
process and without git hooks.

> **Unofficial companion** to graphify. Not affiliated with the graphify project.
> graphify does the real work; this is glue + an update policy.

## The honest pitch

graphify's incremental update (`graphify update`) is **AST-only — it uses no LLM,
so it costs zero tokens**. That single fact drives everything here:

- **Structural refresh is free → so it's continuous.** Every time Claude edits a
  file inside a built graph, the graph's code structure is refreshed. No budget
  to manage, no decision to make.
- **Semantic refresh costs tokens → so it's lazy.** Re-reading changed docs/logic
  with an LLM is the only expensive part, so it happens *only when a query needs
  it*, scoped to the files that query touches, and biased toward graphs you
  actually use.

That's the whole "smart" claim. It is not an AI deciding when to update — it's the
observation that free things should run always and paid things should run only
when they pay off. See [STRATEGY.md](STRATEGY.md) for the full model.

## What's here

| Path | What it is | Status |
|---|---|---|
| `hooks/graphify-auto-update.sh` | PostToolUse hook: refresh graph on edit (free, AST) | working |
| `hooks/graphify-flush.sh` | Stop hook: flush edited projects at turn end | working |
| `policy/policy_engine.py` | Decides when a *semantic* (paid) rebuild is worth it | working planner |
| `RESEARCH.md` | Literature grounding (IVM + query-driven extraction) | — |

The two hooks are live and tested. The policy engine is a **working,
token-free planner**: staleness via content-hash diff, query→file mapping from
the graph's `source_file` nodes, and scoped `decide_on_query` plans — all tested
end-to-end and verified on a real 10k-node graph (query→files in <0.1s). The one
remaining piece is *executing* the paid re-extraction: `execute_scoped_refresh`
is experimental (default OFF) and would be cleaner with a first-class
`graphify reextract <files>` upstream.

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
