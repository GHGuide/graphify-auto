# Empirical findings (2026-06-25)

Measured against graphify (the installed CLI), not assumed. These correct the
original design and define what "smart" can actually mean here.

## Token-cost map of the graphify pipeline

| Step | Command | Token cost | Backend required |
|---|---|---|---|
| AST extraction | `extract`, `update` | **0** | no |
| Community detection (Leiden) | part of `cluster-only` | **0** | no |
| Community **naming** | `cluster-only` "label" phase | **LLM tokens** | yes (else `Community N`) |
| Query | `query` | **0** | no |

Evidence:
- `graphify extract .` on a `.py` file with **no API key** → "AST extraction… 2 nodes,
  1 edges". Code extraction is free.
- `graphify cluster-only .` with no key → "no LLM backend configured; keeping
  Community N placeholders… Done". Clustering free; only naming needs an LLM.
- `graphify query "widget render"` on an unnamed graph → full BFS traversal with
  nodes, edges, `src`/`loc`. **Queries do not need named communities.**

## Consequence: keeping a graph query-fresh is already free

`graphify update` is AST-only. The auto-update hook already runs it and already
spends **0 tokens**. So:

- **Trigger A (query-time scoped per-file re-extraction) saves nothing** — there
  are no per-query tokens, and per-file code extraction is free anyway.
- The only thing that goes stale for free-updates is **community names** (and the
  god-node summaries derived from them), which are cosmetic for querying.

## `merge-graphs` cannot splice a re-extraction back in

Tested merging two graph.json files:
- Node ids get **namespaced** by source dir: `A` → `tmp::A` (cross-repo union design).
- A node attribute was **dropped**: merged `B` came back with `label: []`.

So `execute_scoped_refresh` via `merge-graphs` would create duplicate, label-less
nodes in the main graph. **Removed.** Re-extracting code is free and whole-graph
(`graphify update`) is already correct — there is nothing to splice.

## What "smart" actually reduces to

Gate the one paid step — **community naming**:
- Never name per edit (the hook never does — good).
- Re-name lazily, only when: a backend is configured **and** community structure
  changed materially **and** the named report/viz is about to be used.
- With no backend (current machine): naming is a clean no-op; placeholders stay;
  queries unaffected; **0 tokens** — already optimal.

Net: the headline "smart semantic processing that maximises token savings" is
real but **small** — graphify is already ~free to keep query-fresh. graphify-auto's
durable value is (1) zero-setup free auto-refresh, (2) not wasting tokens re-naming
communities on every edit.
