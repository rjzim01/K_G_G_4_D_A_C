#!/usr/bin/env python3
"""Prepare the competition corpus for local agent development.

Wraps the paper track's ``cgr`` so you do not have to remember the flag order,
and so the read-only-input case is handled for you. Two jobs:

1. **Repair the code-intelligence corpus.** The downloadable ZIP loses every
   per-task ``graphs/`` and ``embeddings/`` file, so the three graph tools return
   nothing. ``cgr repair`` rebuilds them. Optional, but without it you are
   developing an agent against three dead tools and will not know it.

2. **Report whether the fix worked**, as ``results.json`` -- the same schema the
   paper track's notebook writes, so the two are interchangeable.

Where it runs:

- **Kaggle / Colab** — the normal case. ``/kaggle/input`` is read-only, so this
  stages a writable copy of the working subset into ``/kaggle/working`` (or
  ``/content``) before repairing.
- **This machine** — fine for repair and for measuring. 12 cores and no GPU is
  plenty for ``cgr``, which is CPU-only and numpy-only. It is *not* enough to
  serve ``gemma-4-31b-it-qat-w4a16-ct``; see the note printed at the end.

Usage::

    python3 tools/prepare_corpus.py --root /path/to/corpus
    python3 tools/prepare_corpus.py --root /path/to/corpus --staging /kaggle/working/corpus_rw
    python3 tools/prepare_corpus.py --root /path/to/corpus --limit 10   # smoke run
    python3 tools/prepare_corpus.py --download                            # Kaggle CLI download
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
CGR = HERE.parent.parent / "paper-track" / "cgr.py"

# cgr needs these; snapshots/ is only read for the audit, and links instead of
# copying so a 22 GB corpus does not become 44 GB.
STAGE_DIRS = ("graphs", "embeddings")
STAGE_FILES = ("tasks.jsonl",)
LINK_DIRS = ("snapshots", "wheels")


def die(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def run_cgr(args: List[str]) -> None:
    cmd = [sys.executable, str(CGR), *args]
    print(f"$ {' '.join(cmd[1:])}\n", flush=True)
    proc = subprocess.run(cmd)
    if proc.returncode not in (0,):
        die(f"cgr {' '.join(args)} failed with exit {proc.returncode}")


def is_readonly(path: Path) -> bool:
    return not os.access(path, os.W_OK)


def stage(src: Path, dst: Path) -> Path:
    """Copy the working subset to a writable location, linking the read-only rest."""
    dst.mkdir(parents=True, exist_ok=True)
    for name in STAGE_FILES:
        s = src / name
        if s.is_file():
            shutil.copy2(s, dst / name)
            print(f"  copied   {name}")
    for name in STAGE_DIRS:
        s = src / name
        if not s.is_dir():
            continue
        d = dst / name
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(s, d)
        print(f"  copied   {name}/ ({sum(f.stat().st_size for f in d.rglob('*') if f.is_file()) // 1024**2} MiB)")
    for name in LINK_DIRS:
        s = src / name
        if s.is_dir() and not (dst / name).exists():
            try:
                os.symlink(s.resolve(), dst / name)
                print(f"  linked   {name}/ (read-only, not copied)")
            except OSError:
                print(f"  ! could not link {name}/; audit will skip it")
    return dst


def download(dest: Path) -> Path:
    if shutil.which("kaggle") is None:
        die("kaggle CLI not found; pip install kaggle, then put credentials at ~/.kaggle/kaggle.json")
    dest.mkdir(parents=True, exist_ok=True)
    print("downloading 22.42 GB -- this is the slow part\n", flush=True)
    proc = subprocess.run(
        ["kaggle", "competitions", "download", "-c", "gemma-4-developer-agent", "-p", str(dest)]
    )
    if proc.returncode != 0:
        die(f"download failed with exit {proc.returncode}; have you accepted the competition rules?")
    zips = sorted(dest.glob("*.zip"))
    if not zips:
        die("download reported success but no .zip appeared")
    out = dest / "corpus"
    out.mkdir(exist_ok=True)
    print(f"unpacking {zips[0].name} ...")
    run_cgr(["unpack", "--zip", str(zips[0]), "--root", str(out)])
    return out


def summarize(results_path: Path) -> None:
    """Print the before/after comparison, which is the whole point of the run."""
    if not results_path.is_file():
        print("no results.json written", file=sys.stderr)
        return
    d = json.loads(results_path.read_text())
    corpus = d.get("corpus", {})
    W = 66

    def line(label: str, before, after, fmt="{}") -> None:
        try:
            b = fmt.format(before)
            a = fmt.format(after)
        except (TypeError, ValueError):
            return
        mark = "" if b == a else "   <-- changed"
        print(f"{label:<34} {b:>12} -> {a:<12}{mark}")

    print("\n" + "=" * W)
    print(f"corpus: {corpus.get('n_tasks', '?')} tasks, "
          f"{', '.join(corpus.get('repos') or [])}")
    print("=" * W)

    cb, ca = d.get("census_before", {}), d.get("census_after", {})
    for kind in ("graph", "embeddings"):
        g, h = cb.get(kind, {}), ca.get(kind, {})
        if g or h:
            print(f"\n{kind}/")
            line("  tasks with tools disabled (pct)",
                 g.get("pct_tasks_graph_tools_disabled", "?"),
                 h.get("pct_tasks_graph_tools_disabled", "?"), "{:.1f}")
            line("  dead files", g.get("n_dead_files", "?"), h.get("n_dead_files", "?"))
            line("  missing task-named files",
                 g.get("n_missing_task_files", "?"), h.get("n_missing_task_files", "?"))

    rep = d.get("repair", {})
    if rep:
        print(f"\nrepair: {rep.get('n_repaired', 0)} file(s) rebuilt, "
              f"{rep.get('n_unrecoverable', 0)} unrecoverable, "
              f"{rep.get('already_ok', 0)} already intact")

    ab, aa = d.get("audit_before", {}), d.get("audit_after", {})
    if ab or aa:
        print("\nnode coverage (AST symbols the agent can reach)")
        for kind in ("sync_function", "async_function", "class"):
            b = (ab.get("overall") or {}).get(kind, {})
            a = (aa.get("overall") or {}).get(kind, {})
            if b or a:
                line(f"  {kind}",
                     f"{b.get('pct', '?')}%", f"{a.get('pct', '?')}%", "{}")

    bb, ba = d.get("bench_before", {}), d.get("bench_after", {})
    if bb or ba:
        print("\nretrieval reachability of the symbols each task is about")
        line("  needed symbols reachable",
             (bb.get("reachability") or {}).get("pct_needed_symbols_reachable", "?"),
             (ba.get("reachability") or {}).get("pct_needed_symbols_reachable", "?"),
             "{:.1f}")

    ri = d.get("reindex", {})
    if ri.get("n_nodes_added"):
        print(f"\nreindex: +{ri['n_nodes_added']} nodes {ri.get('n_nodes_added_by_kind', {})}")
    st = d.get("structural", {})
    if st:
        print(f"graph: {st.get('total_nodes', '?')} nodes, {st.get('total_edges', '?')} edges "
              f"({st.get('mean_edges_per_node', 0):.3f} edges/node), "
              f"edge types {st.get('distinct_edge_types', [])}")
    print("=" * W)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="corpus root containing tasks.jsonl")
    ap.add_argument("--staging", help="writable staging dir (needed if --root is read-only)")
    ap.add_argument("--out", help="where to write results.json")
    ap.add_argument("--limit", type=int, help="only the first N tasks (smoke run)")
    ap.add_argument("--download", action="store_true", help="kaggle competitions download first")
    ap.add_argument("--skip-repair", action="store_true", help="measure only, change nothing")
    ap.add_argument("--stepwise", action="store_true",
                    help="run each cgr subcommand separately for debugging (does the work twice)")
    args = ap.parse_args(argv)

    if not CGR.is_file():
        die(f"cgr not found at {CGR}")
    if not (shutil.which(sys.executable) or True):
        die("no python")

    if args.download:
        if not args.root:
            args.root = str(download(Path.cwd() / "downloads"))
    if not args.root:
        ap.error("--root is required (or use --download)")

    root = Path(args.root).resolve()
    if not (root / "tasks.jsonl").is_file():
        die(f"no tasks.jsonl under {root}; is this the corpus root?")

    work = root
    if args.staging:
        work = Path(args.staging).resolve()
    elif is_readonly(root):
        die(
            f"{root} is not writable. Pass --staging <dir> (on Kaggle use "
            "/kaggle/working/corpus_rw) so the repair has somewhere to write."
        )

    if work != root:
        print(f"staging read-only corpus {root} -> {work}\n")
        work = stage(root, work)
    elif not args.skip_repair:
        print("WARNING: repairing in place. Keep a copy if you want the damaged original.\n")

    out = Path(args.out).resolve() if args.out else work / "results.json"
    limit = ["--limit", str(args.limit)] if args.limit else []

    # `report` already runs census -> repair -> audit -> bench -> reindex ->
    # install and emits every section, so running the steps individually first
    # would do the expensive pass twice. Stepwise is for debugging only.
    if args.stepwise:
        if not args.skip_repair:
            run_cgr(["repair", "--root", str(work), *limit])
        run_cgr(["audit", "--root", str(work), *limit])
        run_cgr(["reindex", "--root", str(work), "--out-dir", str(work / "repaired"), *limit])
        run_cgr(["apply", "--root", str(work), "--out-dir", str(work / "repaired")])
    elif args.skip_repair:
        run_cgr(["census", "--root", str(work), "--out", str(out)])
    run_cgr(["report", "--root", str(work), "--out", str(out), *limit])

    summarize(out)
    print(f"\nresults: {out}")
    print(
        "\nnote: this repairs the corpus, but serving gemma-4-31b-it-qat-w4a16-ct needs a GPU.\n"
        "For a real end-to-end run use Kaggle (GPU on) or Colab; cgr itself is CPU-only and\n"
        "runs fine here."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
