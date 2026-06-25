# Research grounding

The smart-update design is not invented from scratch — it maps onto two
established literatures. Found via Semantic Scholar / arXiv (free APIs).
Semantic Scholar anonymous rate limit (~1 rps) capped the search; the themes
below were the load-bearing hits.

## 1. Incremental View Maintenance (IVM)

> *Maintain a derived result by reacting to input deltas, never recomputing from
> scratch.*

- **Kairo: Incremental View Maintenance for Scalable Virtual Switch Caching**
  (SIGCOMM 2025) — recasts cache maintenance as IVM: "efficient top-down updates
  that react only to rule changes rather than recomputing from scratch."
- **Partial Update: Efficient Materialized View Maintenance in a Distributed
  Graph Database** (ICDE 2018) — IVM applied to a *graph* view specifically.
- **Stateful Differential Operators for Incremental Computing** (PACMPL 2026) —
  formalises operators that "map input changes to output changes" with internal
  state to "selectively cache relevant information."

**How graphify-auto applies it:** a graph is a materialized view over source
files. We keep a per-file content-hash store; `scan_stale` computes the *delta*
(changed files) and adds only those to a stale set. We never recompute the whole
semantic graph — the AST layer already does delta refresh for free, and the
semantic layer is restricted to the delta too.

## 2. Query-driven / on-demand extraction

> *Extract precisely what a query needs, when it needs it — guided by
> information gaps, not eagerly.*

- **AgenticOCR: Parsing Only What You Need for Efficient RAG** (2026) — turns
  extraction "from a static, full-text process into a query-driven, on-demand
  extraction system… on-demand decompression precisely where needed."
- **CAVIA: Query-Aware … through Reasoning-Perception Loops** (ICASSP 2025) —
  "reasoning continuously guides visual extraction based on identified
  information gaps," vs. exhaustive processing.

**How graphify-auto applies it:** Trigger A. On a query we compute the candidate
nodes (term overlap + 1-hop over `links`), map them to `source_file`, intersect
with the stale set, and re-extract *only* those files before answering. Tokens
are spent precisely where a real question meets stale content — nowhere else.

## Synthesis → policy

| Principle | From | Mechanism in `policy_engine.py` |
|---|---|---|
| React to deltas, never recompute | IVM | `scan_stale` (content-hash diff) → stale set |
| Spend only where queried | query-driven extraction | `candidates_for_query` ∩ stale → `decide_on_query` |
| Cost-aware eagerness | (cost model) | background refresh gated on `cheap_backend_available()` |
| Spend where it pays back | (IVM cost-benefit) | per-project query-count bias (planned, cost.json) |

## Honest gaps

- No paper validates the *specific* heuristic (term-overlap + 1-hop) as a proxy
  for graphify's real traversal — it's an engineering approximation. Worst case:
  a stale file outside the candidate set is missed (same staleness you'd get
  today) or an extra fresh file is refreshed (bounded waste).
- The cost-benefit self-tuning (spend where queries happen) is motivated by IVM
  cost models but not yet implemented.
