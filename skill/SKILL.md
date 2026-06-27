---
name: graphify-auto
description: "One command to make any project's graphify graph cheap and current. Use when the user types /graphify-auto, or asks to set up / refresh / sync a graphify graph for a project. Builds the graph FREE (AST-only, no LLM) if it doesn't exist, or refreshes it free if it does — then the query-nudge gets Claude to actually query it. Maximizes realized token savings at ~0 cost."
---

# /graphify-auto

One command that makes any project's knowledge graph **cheap to build, current,
and actually used**. For any project you point it at:

- **No graph yet?** Builds it **free** — AST-only, no LLM call (`graphify extract`
  with backend keys stripped). Community names are placeholders (cosmetic);
  queries work fully. Build cost ~0 → net token-positive from the very first query.
- **Graph exists?** Refreshes it **free** (incremental AST update) + tracks what
  changed.

Why free build matters: an LLM-backed build can cost ~150–360k tokens, so it only
pays back after ~70 navigation queries. A **free** build pays back on query #1.

The savings only become real if the graph is queried instead of grepped — that's
the job of the installed `graphify-query-nudge` hook, which reminds Claude to
`graphify query` on codebase questions inside a graphed project.

## Usage

```
/graphify-auto              # build-if-missing (free) or refresh (free) the current dir
/graphify-auto <path>       # same, for a specific project
/graphify-auto status       # show stale files + naming freshness, change nothing
/graphify-auto all          # refresh every built graph under the current dir (free)
/graphify-auto name         # also re-run community naming (costs tokens; needs a backend)
```

## What to do when invoked

Engine: `~/.graphify-auto/policy_engine.py`. Assume `graphify` is on PATH
(`export PATH="$HOME/.local/bin:$PATH"`).

1. **Resolve the target.** Use the given path, else cwd. (For `status`, walk up to
   the nearest `graphify-out/graph.json`.)

2. **`status`** → run only this, report, stop:
   ```
   python3 ~/.graphify-auto/policy_engine.py status <root>
   ```

3. **`all`** → find and free-refresh every graph under cwd:
   ```
   find . -type d -name graphify-out -prune 2>/dev/null | while read d; do
     python3 ~/.graphify-auto/policy_engine.py ensure "$(dirname "$d")"
   done
   ```

4. **Default (build-or-refresh, FREE):**
   ```
   python3 ~/.graphify-auto/policy_engine.py ensure <root>
   ```
   - `"action":"built-free"` → first build, ~0 tokens.
   - `"action":"refreshed-free"` → incremental update, ~0 tokens.
   Report which happened, file/change counts, and that it cost 0 tokens.

5. **`name` only** (opt-in, costs tokens, needs a backend): after `ensure`, run
   `python3 ~/.graphify-auto/policy_engine.py run-naming <root>`. If no backend,
   say it was skipped — names are cosmetic; queries don't need them.

6. **Close the loop.** Remind the user (once) that for codebase questions they
   should let Claude **query the graph** (`graphify query "..."`) rather than grep
   — that's where the ~10–40× token savings actually land. The query-nudge hook
   does this automatically inside graphed projects.

## Rules
- Builds and refreshes are **always free** — backend keys are stripped so no LLM
  is ever called by this skill. Naming is the only paid step and is opt-in.
- Be selective about *which* projects to graph: big, long-lived, navigation-heavy
  repos pay off; throwaway / edit-only projects rarely do (free build helps, but
  if you never query it, even a free graph isn't worth maintaining).
