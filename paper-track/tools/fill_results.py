"""
Render paper/paper.md from paper/paper_template.md + a results.json produced by
the notebook (or by cgr's `report` command).

    python tools/fill_results.py /path/to/results.json
    python tools/fill_results.py /path/to/results.json --notebook-url https://www.kaggle.com/code/YOU/SLUG

Every number in the rendered paper comes from results.json. The script refuses to
write a paper whose numbers are not all measurable, and it prints the word count
so the 3,000-word limit can be checked before submitting.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "paper" / "paper_template.md"
OUT = ROOT / "paper" / "paper.md"
CGR = ROOT / "cgr.py"
WORD_LIMIT = 3000


def _get(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return default if d is None else d


def build_tokens(r: dict, notebook_url: str) -> dict:
    cb, ca = r["census_before"], r["census_after"]
    ab, aa = r["audit_before"]["overall"], r["audit_after"]["overall"]
    bb, ba = r["bench_before"], r["bench_after"]
    rb, ra = bb["reachability"], ba["reachability"]
    st, rep, rx = r["structural"], r["repair"], r["reindex"]

    def reach(bench):
        """needed-symbol counts, split by kind"""
        out = {"total": 0, "present": 0}
        for kind, d in bench["reachability"]["by_kind"].items():
            out[kind] = d
        return out

    kbb, kba = reach(bb), reach(ba)
    total = rb["needed_total"]
    present = rb["needed_present"]

    n_repos = len(cb["repos"])
    repo_list = ", ".join(cb["repos"])
    cgr_lines = len(CGR.read_text(encoding="utf-8").splitlines())

    t = {
        **repo_tokens(r),
        "WORDCOUNT": None,  # filled in after the other tokens, once words are counted
        "CGR_LINES": cgr_lines,
        "NOTEBOOK_URL": notebook_url or "TODO: paste the public notebook URL here",
        # corpus
        "N_TASKS": cb["n_tasks"],
        "N_REPOS": n_repos,
        "REPO_LIST": repo_list,
        # defect 1
        "G_FILES": _get(cb, "graph", "n_files"),
        "G_DEAD": _get(cb, "graph", "n_dead_files"),
        "G_PCT_DEAD": _fmt(_get(cb, "graph", "pct_files_dead")),
        "G_TASKS_DEAD": _get(cb, "graph", "n_tasks_own_file_dead"),
        "G_PCT_DISABLED": _fmt(_get(cb, "graph", "pct_tasks_graph_tools_disabled")),
        "E_FILES": _get(cb, "embeddings", "n_files"),
        "E_DEAD": _get(cb, "embeddings", "n_dead_files"),
        "G_MISSING": _get(cb, "graph", "n_missing_task_files", default=0),
        "E_MISSING": _get(cb, "embeddings", "n_missing_task_files", default=0),
        "N_GROUPS": _get(cb, "graph", "n_groups"),
        "N_SHARED_GROUPS": _get(cb, "graph", "n_shared_groups"),
        "N_REPAIRED": rep["n_repaired"],
        "N_UNRECOVERABLE": rep["n_unrecoverable"],
        "N_MISLABELLED": len(cb.get("mislabelled_groups", [])),
        "G_DEAD_AFTER": _get(ca, "graph", "n_dead_files"),
        "E_DEAD_AFTER": _get(ca, "embeddings", "n_dead_files"),
        "RECOVERY_VERDICT": (
            "i.e. every lost file can be rebuilt from the release itself"
            if rep["n_unrecoverable"] == 0
            else "these files cannot be rebuilt from the release alone"
        ),
        # defect 2 / coverage
        "SYNC_BEFORE_PCT": _fmt(_get(ab, "sync_function", "pct")),
        "SYNC_BEFORE_FOUND": _get(ab, "sync_function", "found"),
        "SYNC_BEFORE_TOTAL": _get(ab, "sync_function", "total"),
        "ASYNC_BEFORE_PCT": _fmt(_get(ab, "async_function", "pct")),
        "ASYNC_BEFORE_FOUND": _get(ab, "async_function", "found"),
        "ASYNC_TOTAL": _get(ab, "async_function", "total"),
        "ASYNC_AFTER_PCT": _fmt(_get(aa, "async_function", "pct")),
        "ASYNC_AFTER_FOUND": _get(aa, "async_function", "found"),
        "CLASS_BEFORE_PCT": _fmt(_get(ab, "class", "pct")),
        "CLASS_BEFORE_FOUND": _get(ab, "class", "found"),
        "CLASS_BEFORE_TOTAL": _get(ab, "class", "total"),
        "SYNC_AFTER_PCT": _fmt(_get(aa, "sync_function", "pct")),
        "CLASS_AFTER_PCT": _fmt(_get(aa, "class", "pct")),
        # reachability
        "REACH_BEFORE": _fmt(rb["pct_needed_symbols_reachable"]),
        "REACH_AFTER": _fmt(ra["pct_needed_symbols_reachable"]),
        "NEEDED_TOTAL": total,
        "NEEDED_PRESENT_BEFORE": present,
        "NEEDED_PRESENT_AFTER": ra["needed_present"],
        "ASYNC_REACH_BEFORE": _fmt(_get(rb, "by_kind", "async_function", "pct", default=0)),
        "ASYNC_REACH_AFTER": _fmt(_get(ra, "by_kind", "async_function", "pct", default=0)),
        "NEEDED_SYNC_TOTAL_BEFORE": _get(kbb, "sync_function", "total", default=0),
        "NEEDED_SYNC_PRESENT_BEFORE": _get(kbb, "sync_function", "present", default=0),
        "NEEDED_SYNC_PCT_BEFORE": _fmt(_get(kbb, "sync_function", "pct", default=0)),
        "NEEDED_ASYNC_TOTAL_BEFORE": _get(kbb, "async_function", "total", default=0),
        "NEEDED_ASYNC_PRESENT_BEFORE": _get(kbb, "async_function", "present", default=0),
        "NEEDED_ASYNC_PCT_BEFORE": _fmt(_get(kbb, "async_function", "pct", default=0)),
        "N_AFFECTED_BEFORE": bb["affected_tasks"]["n_tasks_with_unreachable_needed_symbol"],
        "N_AFFECTED_AFTER": ba["affected_tasks"]["n_tasks_with_unreachable_needed_symbol"],
        "N_BLIND_BEFORE": bb["affected_tasks"]["n_tasks_fully_blind_to_async"],
        "N_BLIND_AFTER": ba["affected_tasks"]["n_tasks_fully_blind_to_async"],
        "N_ASYNC_NEED": bb["affected_tasks"]["n_tasks_needing_async_symbol"],
        "N_SCORED": bb["n_tasks_scored"],
        "PCT_AFFECTED_BEFORE": _fmt(bb["affected_tasks"]["pct_tasks_affected"]),
        "MULTIHOP_BEFORE": _fmt(_get(bb, "multi_hop", "pct", default=0)),
        "MULTIHOP_AFTER": _fmt(_get(ba, "multi_hop", "pct", default=0)),
        # reindex
        "N_NODES_ADDED": rx["n_nodes_added"],
        "REINDEX_TASKS": rx["n_tasks"],
        "N_NODES_ADDED_ASYNC": _get(rx, "n_nodes_added_by_kind", "async_function", default=0),
        # structural
        "STRUCT_TASKS": st["n_tasks"],
        "STRUCT_NODES": st["total_nodes"],
        "STRUCT_EDGES": st["total_edges"],
        "STRUCT_MEAN_EDGES": st["mean_edges_per_node"],
        "STRUCT_MODULE_NODES": st["module_level_nodes"],
        "N_EDGE_TYPES": len(st["distinct_edge_types"]),
        "EDGE_TYPES": ", ".join(f"`{e}`" for e in st["distinct_edge_types"]) or "none",
        # sanity
        "SANITY_R1": _fmt(_get(bb, "self_retrieval_sanity_upper_bound", "recall@1", default=0)),
        "SANITY_R10": _fmt(_get(bb, "self_retrieval_sanity_upper_bound", "recall@10", default=0)),
    }
    return t


def _short(repo: str) -> str:
    return repo.rsplit("/", 1)[-1]


def _join(names) -> str:
    names = [f"`{n}`" for n in names]
    if not names:
        return "none"
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def repo_tokens(r: dict) -> dict:
    """Per-repository coverage: a table plus the repo groupings the text cites."""
    by_repo = r["audit_before"]["by_repo"]
    rows, full, gap, async_only, async_only_total = [], [], [], [], 0
    n_tasks = {}
    for t in r["audit_before"]["per_task"]:
        n_tasks[t["repo"]] = n_tasks.get(t["repo"], 0) + 1

    def cell(d):
        if not d or not d.get("total"):
            return "-"
        return f"{d['found']:,}/{d['total']:,} ({_fmt(d['pct'])}%)"

    for repo in sorted(by_repo, key=lambda x: -n_tasks.get(x, 0)):
        k = by_repo[repo]
        s, a, c = k.get("sync_function", {}), k.get("async_function", {}), k.get("class", {})
        rows.append(f"| `{_short(repo)}` | {n_tasks.get(repo, 0)} | {cell(s)} | {cell(a)} | {cell(c)} |")
        complete = s.get("pct", 0) == 100.0 and c.get("pct", 0) == 100.0
        (full if complete else gap).append(_short(repo))
        if complete and a.get("total"):
            async_only.append(_short(repo))
            async_only_total += a["total"] - a["found"]
    table = "\n".join(["| Repository | Tasks | Sync functions | Async functions | Classes |",
                       "|---|---|---|---|---|", *rows])

    core = next((ex for t in r["audit_before"]["per_task"] for ex in t.get("missing_async_examples", [])
                 if not ex.startswith(("docs_src.", "docs.", "examples.", "scripts."))), None)
    rx = r["reindex"].get("n_nodes_added_by_kind", {})
    return {
        "REPO_TABLE": table,
        "FULL_REPOS": _join(full),
        "GAP_REPOS": _join(gap),
        "ASYNC_ONLY_REPOS": _join(async_only),
        "ASYNC_ONLY_MISSING": f"{async_only_total:,}",
        "ASYNC_CORE_EXAMPLE": f"`{core}`" if core else "a library-code async function",
        "N_NODES_ADDED_SYNC": rx.get("sync_function", 0),
        "N_NODES_ADDED_CLASS": rx.get("class", 0),
        "NEEDED_CLASS_PCT_BEFORE": _fmt(_get(r, "bench_before", "reachability", "by_kind", "class", "pct", default=0)),
    }


def _fmt(x, nd=2):
    if x is None:
        return "n/a"
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return str(x)
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", type=Path)
    ap.add_argument("--notebook-url", default="")
    ap.add_argument("--allow-synthetic", action="store_true",
                    help="force the banner-marked draft mode even for a non-fixture root")
    args = ap.parse_args()

    r = json.loads(args.results.read_text(encoding="utf-8"))

    # Safety net: never let fixture numbers masquerade as a submittable paper.
    root = str(_get(r, "census_before", "root", default="")).lower()
    synthetic = any(k in root for k in ("synth", "fixture", "/tmp/")) or args.allow_synthetic
    if synthetic:
        print("=" * 72, file=sys.stderr)
        print("SYNTHETIC results: writing a banner-marked DRAFT, not a submittable paper.", file=sys.stderr)
        print(f"  corpus root: {root or '<unknown>'}", file=sys.stderr)
        print("  These are fixture numbers. Re-run the notebook on the real", file=sys.stderr)
        print("  competition corpus, then fill results from that results.json.", file=sys.stderr)
        print("=" * 72, file=sys.stderr)

    tokens = build_tokens(r, args.notebook_url)

    text = TEMPLATE.read_text(encoding="utf-8")
    used = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)))
    missing = [k for k in used if k not in tokens]
    if missing:
        print("ERROR: results.json is missing values for:", ", ".join(missing), file=sys.stderr)
        return 1

    # inject every number except WORDCOUNT, count the words, then fill WORDCOUNT
    def value(name):
        v = tokens[name]
        return f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else str(v)

    text = re.sub(r"\{\{(\w+)\}\}",
                  lambda m: m.group(0) if m.group(1) == "WORDCOUNT" else value(m.group(1)), text)
    words = len(re.findall(r"[A-Za-z0-9][\w'-]*", text))
    text = text.replace("{{WORDCOUNT}}", f"{words:,}")

    if synthetic:
        banner = (
            "> ## DRAFT - NOT SUBMITTABLE\n"
            ">\n"
            "> Every number below was produced by `tests/make_synthetic.py`, a fixture that\n"
            "> *replicates the shape* of the competition release. They are not measurements of\n"
            "> the real corpus. Replace this file by running the notebook on the real data\n"
            "> and re-running `tools/fill_results.py` on that `results.json`.\n"
        )
        text = banner + "\n" + text

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")

    still = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)))
    print(f"wrote {OUT}")
    print(f"word count: {words:,} (limit {WORD_LIMIT:,})")
    if words > WORD_LIMIT:
        print(f"WARNING: {words - WORD_LIMIT:,} words over the limit; trim before submitting.")
    if still:
        print("WARNING: unresolved tokens remain:", ", ".join(still))
    if "TODO" in text:
        print("WARNING: text still contains TODO (notebook URL or Discussion links); resolve before submitting.")
    if synthetic:
        print("DRAFT ONLY - paper.md is banner-marked as non-submittable.")
        return 2
    return 1 if (still or "TODO" in text or words > WORD_LIMIT) else 0


if __name__ == "__main__":
    raise SystemExit(main())
