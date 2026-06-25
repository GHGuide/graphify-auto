#!/usr/bin/env python3
"""
graphify-auto policy engine (SKELETON).

Decides when a *semantic* (token-costing) rebuild is worth it. The structural
(AST) layer is free and handled by the shell hooks; nothing here gates that.

State lives under <project>/graphify-out/:
  .semantic_stale.json   - files whose content changed since last LLM extraction
  cost.json              - graphify's cost tracker (extended with query stats)

Nothing in this file spends tokens. The only token cost is the actual
`graphify` re-extraction call, which the `decide_*` functions return as a
*plan* for the caller to execute. This keeps the policy pure and testable.

Integration points still owed by graphify are marked `# TODO(graphify)`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# --- tunables ---------------------------------------------------------------

WEIGHTS = {"struct": 1, "logic": 3, "prose": 5, "noop": 0}
DEBT_THRESHOLD = 25          # background refresh only above this
IDLE_MINUTES = 10            # viz regen after this much quiet
CHEAP_BACKEND_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".c", ".cpp", ".h"}
PROSE_EXT = {".md", ".mdx", ".txt", ".rst", ".adoc"}

# Heuristics for classifying a unified diff (token-free, regex only).
_SIG_RE = re.compile(r"^[+-]\s*(def |class |func |fn |function |import |from |export )")
_BODY_RE = re.compile(r"^[+-]")
_WS_RE = re.compile(r"^[+-]\s*$")


# --- state ------------------------------------------------------------------

def _stale_path(project: Path) -> Path:
    return project / "graphify-out" / ".semantic_stale.json"


def load_stale(project: Path) -> set[str]:
    p = _stale_path(project)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_stale(project: Path, stale: Iterable[str]) -> None:
    p = _stale_path(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(set(stale)), ensure_ascii=False), encoding="utf-8")


# --- classification ---------------------------------------------------------

def classify_diff(path: str, diff: str | None) -> str:
    """Return one of: struct | logic | prose | noop. No tokens."""
    ext = Path(path).suffix.lower()
    if ext in PROSE_EXT:
        return "prose"
    if diff is None:
        # No diff available: assume body-logic change for code, prose otherwise.
        return "logic" if ext in CODE_EXT else "prose"
    changed = [ln for ln in diff.splitlines() if _BODY_RE.match(ln) and not ln.startswith(("+++", "---"))]
    if not changed:
        return "noop"
    if all(_WS_RE.match(ln) for ln in changed):
        return "noop"
    if any(_SIG_RE.match(ln) for ln in changed):
        return "struct"     # AST will catch signature/import changes for free
    return "logic"


def debt(project: Path, classes: dict[str, str]) -> int:
    """classes: {file_path: class}. Sum of weights over current stale set."""
    return sum(WEIGHTS.get(c, 0) for c in classes.values())


# --- decisions (return PLANS, never execute) --------------------------------

@dataclass
class Plan:
    ast_refresh: bool = False
    regen_viz: bool = False
    semantic_files: list[str] = field(default_factory=list)  # files to LLM re-extract
    reason: str = ""

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


def cheap_backend_available() -> bool:
    return any(os.environ.get(k) for k in CHEAP_BACKEND_ENV)


def decide_on_edit(project: Path, changed: dict[str, str | None]) -> Plan:
    """
    changed: {file_path: unified_diff_or_None}. Called from the edit hook.
    Always plans a free AST refresh; updates the stale set; only plans a
    background semantic rebuild when debt is high AND tokens are cheap.
    """
    classes = {f: classify_diff(f, d) for f, d in changed.items()}
    stale = load_stale(project)
    for f, c in classes.items():
        if c in ("logic", "prose"):     # AST can't capture these
            stale.add(f)
    save_stale(project, stale)

    plan = Plan(ast_refresh=True, reason="structural refresh (free)")
    score = debt(project, {f: c for f, c in classes.items() if f in stale})
    if score >= DEBT_THRESHOLD and cheap_backend_available():
        plan.semantic_files = sorted(stale)
        plan.reason = f"debt {score} >= {DEBT_THRESHOLD} and cheap backend -> background semantic rebuild"
    return plan


def decide_on_query(project: Path, candidate_files: Iterable[str]) -> Plan:
    """
    candidate_files: source files behind the nodes a query would traverse.
    # TODO(graphify): expose this mapping from `graphify query`.
    Re-extract ONLY the queried files that are stale, then answer.
    """
    stale = load_stale(project)
    dirty = sorted(set(candidate_files) & stale)
    if not dirty:
        return Plan(reason="query region already fresh — no tokens spent")
    return Plan(semantic_files=dirty,
                reason=f"scoped refresh of {len(dirty)} queried+stale file(s)")


def clear_refreshed(project: Path, files: Iterable[str]) -> None:
    """Call after a successful semantic re-extract to drop files from stale set."""
    save_stale(project, load_stale(project) - set(files))


# --- CLI (for the hooks / skill to call) ------------------------------------

def _main() -> int:
    ap = argparse.ArgumentParser(description="graphify-auto update policy")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("on-edit", help="plan after an edit")
    e.add_argument("project")
    e.add_argument("--file", action="append", default=[], help="changed file (repeatable)")

    q = sub.add_parser("on-query", help="plan before answering a query")
    q.add_argument("project")
    q.add_argument("--candidate", action="append", default=[], help="candidate source file (repeatable)")

    s = sub.add_parser("status", help="show stale set + debt")
    s.add_argument("project")

    args = ap.parse_args()
    project = Path(args.project).resolve()

    if args.cmd == "on-edit":
        print(decide_on_edit(project, {f: None for f in args.file}).to_json())
    elif args.cmd == "on-query":
        print(decide_on_query(project, args.candidate).to_json())
    elif args.cmd == "status":
        stale = load_stale(project)
        print(json.dumps({"stale_files": sorted(stale), "count": len(stale)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
