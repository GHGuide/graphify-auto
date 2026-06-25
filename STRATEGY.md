# Update strategy

How graphify-auto decides when to refresh a graph, and why that maximises token
savings. The design rests on one fact:

> **`graphify update` is AST-only. No LLM. Zero Claude tokens.**
> Semantic re-extraction (re-reading changed content with an LLM) is the *only*
> step that costs tokens.

So the strategy is not "be clever about updating." It's "run the free thing
always, run the paid thing only when it pays off."

## Three layers, three cost profiles

| Layer | Mechanism | Cost | Policy |
|---|---|---|---|
| **Structural** | `graphify update` (AST) | 0 tokens | Always — on every edit/turn |
| **Visualisation** | `graph.html`, clustering, report | 0 tokens, but CPU + disk | Throttle — out of hot path |
| **Semantic** | LLM re-extraction of changed files | **tokens** | Lazy — only when queried, scoped, budget-biased |

Naive "always update" is correct for the structural layer and *wrong* for the
other two: it burns disk (viz) and tokens (semantic) for freshness nobody asked
for. The whole value of this engine is splitting these apart.

## Layer 0 — Structural: always (free)

PostToolUse hook → debounced `graphify update`. Stop hook → flush per turn.
Already implemented in `hooks/`. Nothing to decide; it's free.

## Layer 1 — Visualisation: out of the hot path

`graph.html` + clustering + community labelling are cheap in tokens but heavy in
CPU/disk, and regenerating them on every edit is what fills disks.

Regenerate viz **only** on:
- idle (no edits for `IDLE_MINUTES`), or
- just before `graph.html` is opened, or
- session end.

In the hot path, run structural update with viz suppressed (`--no-viz` where the
CLI supports it).

## Layer 2 — Semantic: the smart core

This is the only layer where "when to update" affects token cost. Two pieces of
cheap (token-free) state per project:

- **stale-file set** — files whose *content* changed since their last semantic
  extraction. Derived from graphify's per-file hash cache, no LLM.
- **semantic debt** — a weighted churn score over the stale set.

### Classifying a change (token-free)

For each changed file, estimate what AST already captured vs what only an LLM
would catch:

| Change kind | AST captures it? | Debt weight |
|---|---|---|
| New / renamed / removed symbol, import edge | yes | `LOW` |
| Same signatures, changed body logic | partially | `MED` |
| Docs / markdown / comments / prose | no — semantic only | `HIGH` |
| Whitespace / formatting only | n/a | `0` |

`debt(project) = Σ weight(file)` over the stale set. Cheap regex + AST diff; no
tokens spent to compute it.

### Trigger A — query-time scoped refresh (primary)

This is the mechanism that makes the savings claim true.

```
on graphify query Q:
    candidates = nodes graphify would traverse for Q
    files      = source files behind those candidates
    dirty      = files ∩ stale_set
    if dirty:
        re-extract ONLY `dirty` (LLM)        # scoped — bounded token cost
        merge into graph, clear them from stale_set
    answer Q from the now-fresh subgraph
```

You pay semantic tokens **only** for the files a real question touches, **only**
at the moment it's asked. Never pre-pay; never stale where it matters. Regions
nobody queries are never semantically refreshed and cost nothing.

### Trigger B — background refresh (opportunistic, gated)

If `debt > THRESHOLD` *and* a cheap backend is configured (`GEMINI_API_KEY` /
`GOOGLE_API_KEY`): run a scoped semantic rebuild of the stale set in the
background. If the only backend is the host Claude session (the user's own
tokens): **do not** pre-spend — defer entirely to Trigger A.

So the willingness to pre-refresh scales with how cheap the tokens are.

## Self-tuning: spend where queries happen

Track per project in `graphify-out/cost.json`:
- `query_count`
- `tokens_saved_per_query` (from `graphify benchmark`)
- `tokens_spent_on_rebuilds`

Use the ratio to bias Trigger B:
- High query rate → keep aggressively fresh (refresh pays back fast).
- Near-zero queries → let the graph go stale; spend nothing maintaining a graph
  nobody reads.

Refresh budget flows toward graphs that actually save tokens.

## One-line claim (true version)

> Structural refresh is free, so it's continuous. Semantic refresh costs tokens,
> so it's lazy, scoped to what you query, and biased toward graphs you use.

## Integration points needed from graphify

- **Scoped semantic re-extract** of an explicit file list (cache is per-file-hash,
  so feasible; may need a CLI flag or a targeted `extract` call).
- **Query candidate → source file** mapping exposed from `graphify query`
  (to compute `files` in Trigger A).
- **Viz-suppressed update** in the hot path (`update --no-viz` or equivalent).

If these land upstream, query-time scoped refresh could be a native graphify
feature rather than glue.

## Honest limits

- File classification is heuristic — a body-logic change that flips meaning may be
  scored `MED` and under-refreshed. Degrades to the answer you'd get today.
- Query→file mapping is only as good as the graph's existing edges.
- Background refresh (Trigger B) trades a chance of wasted tokens for freshness;
  it's gated behind a cheap backend precisely to bound that risk.
