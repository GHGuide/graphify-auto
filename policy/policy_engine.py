#!/usr/bin/env python3
"""
graphify-auto policy engine.

Decides when a *semantic* (token-costing) rebuild is worth it, and which files
to refresh. The structural (AST) layer is free and handled by the shell hooks;
nothing here gates that.

Design is grounded in two literatures (see RESEARCH.md):
  * Incremental View Maintenance — react to deltas, never recompute from scratch
    (Kairo 2025; Partial Update, ICDE 2018; Stateful Differential Operators 2026).
    -> we track a per-file stale set and refresh only deltas.
  * Query-driven on-demand extraction — extract precisely where a query needs it,
    guided by information gaps (AgenticOCR 2026; CAVIA 2025).
    -> Trigger A re-extracts only the files behind a query's candidate nodes.

Token-cost discipline: nothing in this module spends tokens. `scan_stale` only
hashes files; `candidates_for_query` only reads graph.json. The expensive
re-extraction is returned as a *Plan* for the caller to execute (and is gated).

graphify graph.json is NetworkX node-link JSON:
  nodes[] = {id, label, norm_label, source_file, source_location, file_type, ...}
  links[] = {source, target, ...}   # source/target are node ids
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# --- tunables ---------------------------------------------------------------

WEIGHTS = {"struct": 1, "logic": 3, "prose": 5, "noop": 0}
DEBT_THRESHOLD = 25            # background (Trigger B) refresh only above this
QUERY_TOP_K = 12               # candidate seed nodes per query
EXPAND_HOPS = 1                # neighbourhood expansion around seeds
CHEAP_BACKEND_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
            ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".php", ".swift", ".kt"}
PROSE_EXT = {".md", ".mdx", ".txt", ".rst", ".adoc", ".org"}

_STOP = {"the", "a", "an", "of", "to", "in", "is", "and", "or", "how", "what",
         "does", "do", "where", "which", "this", "that", "for", "with", "on",
         "are", "be", "it", "use", "used", "using", "into", "from", "via"}

_SIG_RE = re.compile(r"^[+-]\s*(def |class |func |fn |function |import |from |export |type |interface |struct )")
_BODY_RE = re.compile(r"^[+-]")
_WS_RE = re.compile(r"^[+-]\s*$")


# --- paths / io -------------------------------------------------------------

def _out(project: Path) -> Path:
    return project / "graphify-out"

def _graph_path(project: Path) -> Path:
    return _out(project) / "graph.json"

def _stale_path(project: Path) -> Path:
    return _out(project) / ".semantic_stale.json"

def _hash_path(project: Path) -> Path:
    return _out(project) / ".semantic_hashes.json"


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def load_stale(project: Path) -> set[str]:
    return set(_read_json(_stale_path(project), []))

def save_stale(project: Path, stale: Iterable[str]) -> None:
    p = _stale_path(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(set(stale)), ensure_ascii=False), encoding="utf-8")


# --- staleness via content hashing (no tokens) ------------------------------

def _file_hash(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def graph_source_files(project: Path) -> set[str]:
    """All source files referenced by graph nodes (relative paths as stored)."""
    g = _read_json(_graph_path(project), {})
    out = set()
    for n in g.get("nodes", []):
        sf = n.get("source_file")
        if sf:
            out.add(sf)
    return out


def scan_stale(project: Path) -> dict:
    """
    Hash every source file in the graph, diff against the stored hashes, and add
    changed/new files to the stale set. Pure IVM delta detection — no LLM.
    Returns a small report dict.
    """
    baseline = not _hash_path(project).exists()   # first scan: graph already reflects these files
    prev = _read_json(_hash_path(project), {})
    cur: dict[str, str] = {}
    changed: list[str] = []
    for rel in sorted(graph_source_files(project)):
        h = _file_hash(project / rel)
        if h is None:
            continue                      # deleted/unreadable -> skip (AST pass handles removal)
        cur[rel] = h
        if not baseline and prev.get(rel) != h:
            changed.append(rel)

    stale = load_stale(project)
    stale.update(changed)
    save_stale(project, stale)
    _hash_path(project).write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    return {"scanned": len(cur), "changed": len(changed), "baseline": baseline,
            "stale_total": len(stale), "changed_files": changed[:50]}


# --- change classification (no tokens) --------------------------------------

def classify(path: str, diff: str | None = None) -> str:
    """struct | logic | prose | noop. AST already captures 'struct' for free."""
    ext = Path(path).suffix.lower()
    if ext in PROSE_EXT:
        return "prose"
    if diff is None:
        return "logic" if ext in CODE_EXT else "prose"
    lines = [ln for ln in diff.splitlines()
             if _BODY_RE.match(ln) and not ln.startswith(("+++", "---"))]
    if not lines or all(_WS_RE.match(ln) for ln in lines):
        return "noop"
    if any(_SIG_RE.match(ln) for ln in lines):
        return "struct"
    return "logic"


def debt(project: Path) -> int:
    """Weighted churn over the current stale set (file ext as a cheap proxy)."""
    return sum(WEIGHTS[classify(f)] for f in load_stale(project))


# --- query -> candidate files (no tokens) -----------------------------------

def _tokens(q: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", q.lower()) if len(t) > 2 and t not in _STOP]


def candidates_for_query(project: Path, query: str,
                         top_k: int = QUERY_TOP_K, hops: int = EXPAND_HOPS) -> set[str]:
    """
    Source files behind the nodes a query would most likely traverse. Seeds by
    term overlap on node labels, expands `hops` over `links`, returns source_file
    of the selected nodes. Mirrors graphify's own traversal closely enough to
    bound what a scoped refresh must touch, without invoking the LLM.
    """
    g = _read_json(_graph_path(project), {})
    nodes = g.get("nodes", [])
    if not nodes:
        return set()
    by_id = {n.get("id"): n for n in nodes}
    toks = _tokens(query)
    if not toks:
        return set()

    def score(n) -> int:
        hay = f"{n.get('norm_label','')} {n.get('label','')} {n.get('source_file','')}".lower()
        return sum(1 for t in toks if t in hay)

    scored = sorted(((score(n), n.get("id")) for n in nodes), reverse=True)
    seeds = [nid for s, nid in scored if s > 0][:top_k]
    selected = set(seeds)

    if hops > 0 and seeds:
        adj: dict[str, set[str]] = {}
        for ln in g.get("links", []):
            s, t = ln.get("source"), ln.get("target")
            if s is None or t is None:
                continue
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)
        frontier = set(seeds)
        for _ in range(hops):
            nxt = set()
            for nid in frontier:
                nxt |= adj.get(nid, set())
            selected |= nxt
            frontier = nxt

    files = set()
    for nid in selected:
        n = by_id.get(nid)
        if n and n.get("source_file"):
            files.add(n["source_file"])
    return files


# --- decisions (return PLANS, never execute) --------------------------------

@dataclass
class Plan:
    ast_refresh: bool = False
    regen_viz: bool = False
    semantic_files: list[str] = field(default_factory=list)
    reason: str = ""
    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


def cheap_backend_available() -> bool:
    return any(os.environ.get(k) for k in CHEAP_BACKEND_ENV)


def decide_on_edit(project: Path) -> Plan:
    """Edit hook: free AST refresh always; background semantic only if debt high
    AND a cheap backend is configured (else defer to query-time, Trigger A)."""
    rep = scan_stale(project)
    plan = Plan(ast_refresh=True, reason="structural refresh (free)")
    score = debt(project)
    if score >= DEBT_THRESHOLD and cheap_backend_available():
        plan.semantic_files = sorted(load_stale(project))
        plan.reason = (f"debt {score} >= {DEBT_THRESHOLD} and cheap backend "
                       f"-> background scoped semantic rebuild ({rep['changed']} changed)")
    return plan


def decide_on_query(project: Path, query: str) -> Plan:
    """Trigger A: re-extract only the queried-and-stale files, then answer."""
    cand = candidates_for_query(project, query)
    dirty = sorted(cand & load_stale(project))
    if not dirty:
        return Plan(reason=f"query region fresh ({len(cand)} candidate files, 0 stale) — 0 tokens")
    return Plan(semantic_files=dirty,
                reason=f"scoped refresh of {len(dirty)}/{len(cand)} queried files (query-driven)")


def clear_refreshed(project: Path, files: Iterable[str]) -> None:
    save_stale(project, load_stale(project) - set(files))


# --- ensure: build-cheap-or-refresh (the /graphify-auto core) ---------------
# Guarantees a queryable graph for `project` at ~0 tokens:
#   - no graph yet  -> FREE AST build (graphify extract + cluster), backend env
#     stripped so no LLM is ever called (community names stay "Community N";
#     cosmetic — queries work fine). Build cost ~0 => net-positive from query #1.
#   - graph exists  -> FREE AST update (changed files only) + stale bookkeeping.
# Never spends Claude tokens. Naming (the only paid step) stays opt-in elsewhere.

_BACKEND_KEYS = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY")

def _free_env() -> dict:
    import os
    env = {k: v for k, v in os.environ.items() if k not in _BACKEND_KEYS}
    env["PATH"] = os.path.expanduser("~/.local/bin") + ":" + env.get("PATH", "")
    env["GRAPHIFY_NO_LLM"] = "1"   # belt-and-suspenders if graphify honors it
    return env

def ensure_cheap(project: Path) -> dict:
    import subprocess
    if not project.is_dir():
        return {"status": "error", "why": f"path not found: {project}"}
    env = _free_env()
    def run(args):
        try:
            return subprocess.run(["graphify", *args], cwd=str(project), env=env,
                                  capture_output=True, text=True)
        except FileNotFoundError:
            return None   # graphify not on PATH
    _GFAIL = {"status": "error", "why": "graphify CLI not found on PATH"}
    if not _graph_path(project).exists():
        r = run(["extract", "."])
        if r is None:
            return _GFAIL
        if r.returncode != 0:
            err = (r.stderr or "")
            # Non-code corpora (docs/papers/images) intrinsically need an LLM to
            # extract — can't AST-parse a PDF/image. Report cleanly, don't crash.
            if "no LLM API key" in err or "need semantic extraction" in err:
                return {"status": "needs_backend", "action": "skipped", "tokens": 0,
                        "why": "this corpus has docs/papers/images that require an LLM "
                               "to build; code-only projects build free. Set a backend "
                               "key (e.g. GEMINI_API_KEY) and use /graphify, or graph a "
                               "code-only subset."}
            return {"status": "error", "stage": "extract", "stderr": err[-400:]}
        run(["cluster-only", "."])          # free; placeholder names, keeps query happy
        rep = scan_stale(project)           # baseline hashes
        n = len(graph_source_files(project))
        return {"status": "ok", "action": "built-free", "files": n,
                "tokens": 0, "note": "AST-only build, no LLM"}
    r = run(["update", "."])
    if r is None:
        return _GFAIL
    if r.returncode != 0:
        return {"status": "error", "stage": "update", "stderr": r.stderr[-400:]}
    rep = scan_stale(project)
    return {"status": "ok", "action": "refreshed-free",
            "changed": rep.get("changed", 0), "tokens": 0}


# --- the one paid step: community naming (see FINDINGS.md) ------------------
# graphify keeps a graph QUERY-fresh for free (AST `update`). The only step that
# costs LLM tokens is community *naming* (`cluster-only` with a backend). It is
# global (not per-file) and cosmetic for querying. So the smart move is to gate
# WHEN to re-name, never to re-extract per file. Per-file splice via merge-graphs
# was removed: it namespaces ids and drops labels (FINDINGS.md).

NAME_STRUCT_DELTA = 0.05      # re-name only if >5% of nodes changed since last naming

def _sig_path(project: Path) -> Path:
    return _out(project) / ".name_signature.json"

def _structure_signature(project: Path) -> dict:
    g = _read_json(_graph_path(project), {})
    return {"nodes": len(g.get("nodes", [])), "links": len(g.get("links", []))}

def names_stale(project: Path) -> bool:
    """True if community structure drifted materially since names were last set."""
    last = _read_json(_sig_path(project), None)
    if last is None:
        return True                      # never named
    cur = _structure_signature(project)
    base = max(1, last.get("nodes", 0))
    return abs(cur["nodes"] - last.get("nodes", 0)) / base > NAME_STRUCT_DELTA


def decide_naming(project: Path, context: str = "manual") -> Plan:
    """
    Gate the only token-costing step. Worth re-naming only when ALL hold:
      - a backend is configured (else naming is a no-op, 0 tokens), AND
      - names are materially stale, AND
      - context is one where named labels are about to matter
        (idle | preview | session-end | manual), never on a hot per-edit path.
    """
    if not cheap_backend_available():
        return Plan(reason="no backend -> naming is a free no-op; placeholders fine for queries")
    if context == "edit":
        return Plan(reason="hot edit path -> defer naming (cosmetic, costs tokens)")
    if not names_stale(project):
        return Plan(reason="community structure ~unchanged since last naming -> skip")
    return Plan(regen_viz=True, reason=f"names stale and context={context} -> re-name (cluster-only)")


def run_naming(project: Path) -> dict:  # pragma: no cover - spends tokens iff backend set
    """Execute the paid step. Safe no-op (0 tokens) when no backend; records sig."""
    import subprocess
    r = subprocess.run(["graphify", "cluster-only", str(project)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"status": "error", "stderr": r.stderr[-400:]}
    _sig_path(project).write_text(json.dumps(_structure_signature(project)), encoding="utf-8")
    return {"status": "ok", "named": cheap_backend_available()}


# --- CLI --------------------------------------------------------------------

def _main() -> int:
    ap = argparse.ArgumentParser(description="graphify-auto update policy (token-free planner)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ensure", help="build-free-if-missing or refresh-free; ~0 tokens")
    p.add_argument("project")

    p = sub.add_parser("scan-stale", help="hash source files, update stale set")
    p.add_argument("project")

    p = sub.add_parser("on-edit", help="plan after an edit batch")
    p.add_argument("project")

    p = sub.add_parser("decide-naming", help="gate the only paid step (community naming)")
    p.add_argument("project")
    p.add_argument("--context", default="manual",
                   choices=["edit", "idle", "preview", "session-end", "manual"])

    p = sub.add_parser("run-naming", help="execute community naming (opt-in; costs tokens iff backend)")
    p.add_argument("project")

    p = sub.add_parser("candidates", help="source files a query would touch (utility)")
    p.add_argument("project")
    p.add_argument("query")

    p = sub.add_parser("status", help="show stale set, debt, naming freshness")
    p.add_argument("project")

    args = ap.parse_args()
    project = Path(args.project).resolve()

    if args.cmd == "ensure":
        print(json.dumps(ensure_cheap(project), ensure_ascii=False))
    elif args.cmd == "scan-stale":
        print(json.dumps(scan_stale(project), ensure_ascii=False))
    elif args.cmd == "on-edit":
        print(decide_on_edit(project).to_json())
    elif args.cmd == "decide-naming":
        print(decide_naming(project, args.context).to_json())
    elif args.cmd == "run-naming":
        print(json.dumps(run_naming(project), ensure_ascii=False))
    elif args.cmd == "candidates":
        print(json.dumps(sorted(candidates_for_query(project, args.query)), ensure_ascii=False))
    elif args.cmd == "status":
        print(json.dumps({"stale": sorted(load_stale(project)), "debt": debt(project),
                          "cheap_backend": cheap_backend_available(),
                          "names_stale": names_stale(project)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
