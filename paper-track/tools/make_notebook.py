"""
Generate notebooks/cgr_pipeline.ipynb - a fully self-contained notebook with
cgr.py embedded, so it can be published as a public Kaggle Notebook without any
external dependency.

    python tools/make_notebook.py

The CELLS list is the single source of truth. The `<<CGR>>` placeholder is
replaced at build time with cgr.py's source minus its CLI guard (in a notebook
`__name__` is already `"__main__"`, so the guard would fire on import).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_RAW = (ROOT / "cgr.py").read_text(encoding="utf-8")
_MARKER = '\nif __name__ == "__main__":'
CGR = _RAW.split(_MARKER)[0] if _MARKER in _RAW else _RAW
assert "def main(" in _RAW, "cgr.py lost its CLI entry point"
assert '"""' not in CGR.split('"""')[0], "unexpected module docstring shape"

OUT = ROOT / "notebooks" / "cgr_pipeline.ipynb"

MD = "markdown"
CODE = "code"

CGR_CELL = "<<CGR>>"


def md(text: str) -> dict:
    return {"cell_type": MD, "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": CODE,
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip("\n").splitlines(keepends=True),
    }


CELLS = [
    md(
        """
# cgr - Code Graph Repair for the Gemma 4 Developer Agent corpus

Repairs and re-indexes the competition's `graphs/` + `embeddings/` release, then
measures what the shipped defects cost an agent.

* **Defect 1 - hard-link loss.** `graphs/` and `embeddings/` ship 256 files each
  (129 task-named hard-linked to 127 commit-named). ZIP cannot store hard links,
  so exactly one name per commit group survives the download and the rest arrive
  0 bytes. The harness enables the code-intelligence tools only when those files
  exceed 100 bytes, so `get_code_neighbors`, `get_code_subgraph` and
  `search_similar_code` silently switch off.
* **Defect 2 - no `async` nodes.** Graph generation enumerates `def` and `class`
  but not `async def`, so asynchronous functions are absent from the node set
  and are unreachable by all three graph tools.

Everything runs on CPU. No LLM inference, no GPU, no network after download.

**How to run.** On Kaggle, attach the `gemma-4-developer-agent` competition data as
an input and *Run All*; the read-only input is staged into `/kaggle/working`
automatically. On Colab, upload your `kaggle.json` and make sure ~50 GB is free.
`results.json` is written to the working directory at the end.

The tool is embedded in the cell below, so this notebook is standalone.
"""
    ),
    md("## 0. Environment"),
    code(
        """
import json, os, shutil, subprocess, sys, textwrap, time
from pathlib import Path

print("python", sys.version.split()[0])
try:
    import numpy
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "numpy"], check=True)
    import numpy
print("numpy", numpy.__version__)

# Kaggle Notebooks save /kaggle/working as output; Colab uses /content. Kaggle
# runs as root, so /content could be created there too - check Kaggle first.
if Path("/kaggle/working").is_dir():
    WORK = Path("/kaggle/working")
elif Path("/content").is_dir():
    WORK = Path("/content")
else:
    WORK = Path.home() / "cgr_work"
WORK.mkdir(parents=True, exist_ok=True)
print("work dir:", WORK)
print(f"free disk: {shutil.disk_usage(WORK).free / 1e9:.1f} GB")
"""
    ),
    CGR_CELL,
    code(
        """
# cgr is now defined in this namespace - no import needed.
print("cgr ready:", GRAPH_MIN_BYTES, "byte tool gate,", EMBED_DIM, "d embeddings")
print("entry points:", ", ".join(
    n for n in ("census", "repair", "audit", "reindex", "retrieval_eval", "apply_repaired")
    if n in globals()))
"""
    ),
    md("## 1. Acquire the corpus\n\nTried in order: an already-attached dataset, then the Kaggle CLI."),
    code(
        """
COMP = "gemma-4-developer-agent"

def pip_install(pkg):
    for extra in ([], ["--break-system-packages"]):
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg, *extra], check=True)
            return
        except subprocess.CalledProcessError:
            continue
    raise SystemExit(f"could not pip install {pkg}")

def find_attached():
    for base in ("/kaggle/input", "/content"):
        b = Path(base)
        if not b.is_dir():
            continue
        for p in b.rglob("tasks.jsonl"):
            if p.parent.joinpath("graphs").is_dir():
                return p.parent
    return None

def via_cli():
    cred = Path.home() / ".kaggle" / "kaggle.json"
    if not cred.exists() and not (WORK / "kaggle.json").exists():
        raise SystemExit(
            "No attached dataset and no ~/.kaggle/kaggle.json.\\n"
            "Either add the competition as a notebook input, or upload your "
            f"kaggle.json to {WORK}/ and re-run this cell."
        )
    if not shutil.which("kaggle"):
        pip_install("kaggle")
    # The release is ~22.4 GB compressed and ~45 GB once unpacked.
    free = shutil.disk_usage(WORK).free / 1e9
    if free < 50:
        print(f"WARNING: {free:.1f} GB free, need ~50 GB. In Colab pick a larger disk "
              "under Runtime > Change runtime type.")
    zip_path = WORK / f"{COMP}.zip"
    if not zip_path.exists():
        subprocess.run(["kaggle", "competitions", "download", "-c", COMP, "-p", str(WORK)], check=True)
    dest = WORK / "corpus"
    print("extracting ~22 GB, this takes a while ...")
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    for p in dest.rglob("tasks.jsonl"):
        if p.parent.joinpath("graphs").is_dir():
            return p.parent
    raise SystemExit("tasks.jsonl not found after extraction")

def find_snapshots(root):
    # Normally snapshots/ sits next to tasks.jsonl; otherwise search the input tree.
    if (root / "snapshots").is_dir():
        return root / "snapshots"
    for base in (root.parent, root.parent.parent, Path("/kaggle/input")):
        if base.is_dir():
            for p in base.rglob("snapshots"):
                if p.is_dir() and any(p.glob("*.tgz")):
                    return p
    return None

def ensure_writable(root):
    # cgr repairs in place, but /kaggle/input is read-only. Stage a fresh
    # writable copy of the parts cgr mutates (tasks.jsonl, graphs/, embeddings/)
    # and link the large, read-only snapshots/ instead of copying them.
    probe = root / ".cgr_write_probe"
    try:
        probe.write_text("x")
        probe.unlink()
        return root
    except OSError:
        pass
    dest = WORK / "corpus_rw"
    if dest.exists():
        shutil.rmtree(dest)  # always start from the released state
    dest.mkdir(parents=True)
    # copyfile, not copy2/copytree: those carry over the read-only file mode
    shutil.copyfile(root / "tasks.jsonl", dest / "tasks.jsonl")
    for sub in ("graphs", "embeddings"):
        if (root / sub).is_dir():
            (dest / sub).mkdir()
            for f in (root / sub).iterdir():
                if f.is_file():
                    shutil.copyfile(f, dest / sub / f.name)
    snaps = find_snapshots(root)
    if snaps:
        (dest / "snapshots").symlink_to(snaps, target_is_directory=True)
        print("snapshots:", snaps)
    else:
        print("WARNING: no snapshots/ directory with .tgz files found; the audit will score nothing")
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file() and not f.is_symlink())
    print(f"input is read-only: staged a writable copy at {dest} ({size / 1e9:.2f} GB)")
    return dest

ROOT_DATA = ensure_writable(find_attached() or via_cli())
print("corpus root:", ROOT_DATA)
print("entries:", sorted(p.name for p in ROOT_DATA.iterdir())[:12])
"""
    ),
    md("## 2. Census - quantify the hard-link loss **before** touching anything"),
    code(
        """
c0 = census(ROOT_DATA)
print(json.dumps(c0, indent=2)[:3500])
"""
    ),
    md("## 3. Repair - rebuild every commit group from its one surviving copy"),
    code(
        """
rep = repair(ROOT_DATA)
c1 = census(ROOT_DATA)
g0, g1 = c0["graph"], c1["graph"]

print(f"repaired {rep['n_repaired']} files, unrecoverable {rep['n_unrecoverable']}")
print(f"0-byte files on disk                       {g0['n_dead_files']:>4d} -> {g1['n_dead_files']}")
print(f"task files absent altogether               {g0['n_missing_task_files']:>4d} -> {g1['n_missing_task_files']}")
print(f"tasks whose OWN file is 0 bytes or absent {g0['n_tasks_own_file_dead']:>4d} -> "
      f"{g1['n_tasks_own_file_dead']}  of {g1['n_tasks']}")
print(f"graph tools disabled by a naive check      "
      f"{g0['pct_tasks_graph_tools_disabled']:>4.1f}% -> {g1['pct_tasks_graph_tools_disabled']}%")
"""
    ),
    md("## 4. Coverage and cost audit **before** re-indexing"),
    code(
        """
t0 = time.time()
audit_before = audit(ROOT_DATA)
bench_before = retrieval_eval(ROOT_DATA, k_values=(1, 5, 10))
print(f"audit + bench on the released corpus: {time.time() - t0:.0f}s")
print("audited", audit_before["n_tasks_audited"], "tasks; skipped:", audit_before["skip_reasons"])
print("bench scored", bench_before["n_tasks_scored"], "tasks; skipped:", bench_before["skip_reasons"])
if not audit_before["n_tasks_audited"]:
    raise SystemExit("No task could be audited - see the skip reasons above and the first skipped "
                     f"tasks: {list(audit_before['skipped'].items())[:3]}")
print("\\nnode coverage vs. the AST reference set:")
print(json.dumps(audit_before["overall"], indent=2))
print("\\nreachability of the symbols the reference patches need:")
print(json.dumps(bench_before["reachability"]["by_kind"], indent=2))
print("\\naffected tasks:")
print(json.dumps(bench_before["affected_tasks"], indent=2))
"""
    ),
    md(
        """
## 5. Re-index - add the missing `async` nodes

New nodes are structurally complete and schema-compatible (`id` / `name` /
`text`). They ship **without vectors**: the released embedder is not part of the
dataset, so `search_similar_code` can only surface them once the host supplies
an embedder. `get_code_neighbors` and `get_code_subgraph` work immediately,
because those read the graph rather than the vectors.
"""
    ),
    code(
        """
REPAIRED = WORK / "repaired"
reindex_result = reindex(ROOT_DATA, REPAIRED)
print(json.dumps({k: v for k, v in reindex_result.items() if k != "per_task"}, indent=2))
if reindex_result["per_task"]:
    print("examples:", reindex_result["per_task"][0]["examples"][:3])

inst = apply_repaired(ROOT_DATA, REPAIRED)
print(f"installed {inst['n_installed']} corrected graphs ({inst['n_changed']} changed)")
"""
    ),
    md("## 6. Coverage and cost audit **after** re-indexing"),
    code(
        """
audit_after = audit(ROOT_DATA)
bench_after = retrieval_eval(ROOT_DATA, k_values=(1, 5, 10))

def row(label, a, b, pct=False):
    f = (lambda x: f"{x:.2f}%") if pct else (lambda x: str(x))
    print(f"{label:<44s} {f(a):>10s} {f(b):>12s}")

print(f"{'metric':<44s} {'BEFORE':>10s} {'AFTER':>12s}")
print("-" * 69)
for k in ("sync_function", "async_function", "class"):
    row(f"node coverage: {k}", audit_before["overall"][k]["pct"],
        audit_after["overall"][k]["pct"], pct=True)
row("needed-symbol reachability",
    bench_before["reachability"]["pct_needed_symbols_reachable"],
    bench_after["reachability"]["pct_needed_symbols_reachable"], pct=True)
row("  async needed-symbol reachability",
    bench_before["reachability"]["by_kind"].get("async_function", {}).get("pct", 0),
    bench_after["reachability"]["by_kind"].get("async_function", {}).get("pct", 0), pct=True)
row("tasks with an unreachable needed symbol",
    bench_before["affected_tasks"]["n_tasks_with_unreachable_needed_symbol"],
    bench_after["affected_tasks"]["n_tasks_with_unreachable_needed_symbol"])
row("tasks fully blind to async",
    bench_before["affected_tasks"]["n_tasks_fully_blind_to_async"],
    bench_after["affected_tasks"]["n_tasks_fully_blind_to_async"])
"""
    ),
    md("## 7. Structural scan (secondary finding)\n\nEdge types, edge density and module-level node count of the graphs."),
    code(
        """
structural = structural_scan(ROOT_DATA)
print(json.dumps(structural, indent=2))
"""
    ),
    md("## 8. Emit `results.json`\n\nThe paper's numbers are read from this file. Attach it to the writeup's Project Links, or leave it in the notebook output."),
    code(
        """
# These are the same keys, in the same order, that `cgr.full_report()` returns -
# so `python cgr.py report` and this notebook produce interchangeable results.json.
results = {
    "tool": "cgr",
    "schema": 1,
    "corpus": {"n_tasks": c0["n_tasks"], "repos": c0["repos"]},
    "census_before": c0,
    "repair": rep,
    "census_after": c1,
    "audit_before": audit_before,
    "audit_after": audit_after,
    "bench_before": bench_before,
    "bench_after": bench_after,
    "reindex": {k: v for k, v in reindex_result.items() if k != "per_task"},
    "install": inst,
    "structural": structural,
}
out = WORK / "results.json"
out.write_text(json.dumps(results, indent=2, default=str))
print("wrote", out, f"({out.stat().st_size:,} bytes)")
print(json.dumps(results["reindex"], indent=2))
"""
    ),
    md(
        "## 9. Clean up\n\nOn Kaggle everything in `/kaggle/working` is saved as notebook output (capped at "
        "~20 GB), so drop the staged corpus copy and the re-indexed graphs and keep only `results.json`."
    ),
    code(
        """
# Only remove what ensure_writable() staged; a corpus you unpacked yourself is left alone.
if ROOT_DATA == WORK / "corpus_rw":
    for d in (ROOT_DATA, REPAIRED):
        shutil.rmtree(d, ignore_errors=True)
        print("removed", d)
print("kept:", sorted(p.name for p in WORK.iterdir()))
"""
    ),
    md(
        """
## Citation

> Elan Markowitz, Bryan Perozzi, Benedek Rózemberczki, Glenn Cameron, Hadi Hemmati,
> Yuchen Li, Michael Galkin, Majid Farhadi, Ryan Holbrook, and Ashley Oldacre.
> *Google - The Gemma 4 Developer Agent Competition.*
> https://www.kaggle.com/competitions/gemma-4-developer-agent, 2026. Kaggle.

## Licence

cgr is released under Apache 2.0, matching the competition dataset.
"""
    ),
]


def build() -> dict:
    cells = []
    for c in CELLS:
        if c is CGR_CELL or c == CGR_CELL:
            cell = code("# --- cgr.py (embedded verbatim; CLI guard removed) ---\n" + CGR)
        else:
            cell = dict(c)
        src = cell["source"]
        if src and not src[-1].endswith("\n"):
            src = src + ["\n"]
        cell["source"] = src
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


if __name__ == "__main__":
    compile(CGR, "cgr", "exec")  # fail loudly if the embed is broken
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nb = build()
    OUT.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    n_code = sum(1 for c in nb["cells"] if c["cell_type"] == CODE)
    print(f"wrote {OUT} ({n_code} code cells, {OUT.stat().st_size:,} bytes)")
