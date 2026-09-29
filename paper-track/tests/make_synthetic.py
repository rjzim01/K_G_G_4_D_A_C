"""
Build a synthetic replica of the Gemma 4 Developer Agent corpus that reproduces
the two reported defects, then run cgr.py against it.

This exists so the tool can be validated without the 22 GB gated download.
It is NOT part of the paper - it is a test harness.

    python tests/make_synthetic.py /tmp/cgr_synth
    python tests/make_synthetic.py /tmp/cgr_synth --kaggle-layout   # lost aliases absent, not 0 bytes
    python cgr.py report --root /tmp/cgr_synth/data --out /tmp/cgr_synth/results.json
"""

from __future__ import annotations

import json
import random
import shutil
import sys
import tarfile
from pathlib import Path

import numpy as np

DIM = 256
RNG = random.Random(0xC0DE)
NRN = np.random.default_rng(0xC0DE)

REPOS = [
    ("fastapi/fastapi", "fastapi"),
    ("Textualize/rich", "rich"),
    ("psf/requests", "requests"),
    ("encode/httpx", "httpx"),
]

# 129 dev tasks over 127 distinct commits: two commit pairs are shared, which
# is what produces the mislabelled-survivor case. Pairs are same-repo, exactly
# as observed in the real corpus (requests_6589/6629, rich_3882/3894).
TASKS = []
for i in range(129):
    repo, short = REPOS[i % 4]
    sha = f"{i:040x}"[:40]
    TASKS.append({"instance_id": f"{short}_{1000 + i}", "repo": repo, "base_commit": sha})
# indices 4 and 8 are both fastapi; 5 and 9 are both rich
TASKS[4]["base_commit"] = TASKS[8]["base_commit"]
TASKS[5]["base_commit"] = TASKS[9]["base_commit"]


def module_source(mod: str, n_sync: int, n_async: int, n_cls: int) -> str:
    lines = [f"# {mod}", "import asyncio", ""]
    names = []
    for c in range(n_cls):
        cn = f"Cls{c}"
        names.append((f"{mod}.{cn}", "class", False))
        names.append((f"{mod}.{cn}.sync_{c}", "sync_function", False))  # methods ARE in the real graph
        lines += [f"class {cn}:", f"    def sync_{c}(self):", f"        return {c}", ""]
        if c % 2 == 0:
            lines += [f"    async def aio_{c}(self):", f"        await asyncio.sleep(0)", ""]
            names.append((f"{mod}.{cn}.aio_{c}", "async_function", True))
    for s in range(n_sync):
        names.append((f"{mod}.func_{s}", "sync_function", False))
        lines += [f"def func_{s}(x):", f"    return x + {s}", ""]
    for a in range(n_async):
        names.append((f"{mod}.aio_{a}", "async_function", True))
        lines += [f"async def aio_{a}(x):", "    await asyncio.sleep(0)", f"    return x", ""]
    return "\n".join(lines) + "\n", names


def build(root: Path, kaggle_layout: bool = False) -> None:
    if root.exists():
        shutil.rmtree(root)
    (root / "snapshots").mkdir(parents=True)
    (root / "graphs").mkdir(parents=True)
    (root / "embeddings").mkdir(parents=True)

    by_commit: dict[str, list[dict]] = {}
    for t in TASKS:
        by_commit.setdefault(t["base_commit"], []).append(t)

    tasks_rows = []
    for t in TASKS:
        short = t["repo"].rsplit("/", 1)[-1]
        n_cls, n_sync, n_async = 3 + (RNG.randrange(0, 3)), 6 + RNG.randrange(0, 6), 2 + RNG.randrange(0, 4)
        files = {}
        all_names: list[tuple[str, str, bool]] = []  # (node_id, kind, is_async)
        for m in range(2):
            src, names = module_source(f"{short}.mod{m}", n_sync, n_async, n_cls)
            files[f"{short}/mod{m}.py"] = src
            all_names.extend(names)
        # a test file that must be excluded from the audit
        files[f"{short}/test_mod.py"] = "def test_x():\n    pass\n"
        # a real repo root has packaging files alongside the package dir, so
        # that repo_dir resolves to the worktree root and not the package dir
        files["pyproject.toml"] = f'[project]\nname = "{short}"\n'
        all_names.append((f"{short}.mod0.unused", "sync_function", False))  # never in graph

        # ---- snapshot tarball
        snap = root / "snapshots" / f"{t['instance_id']}.tgz"
        with tarfile.open(snap, "w:gz") as tf:
            for rel, body in files.items():
                data = body.encode()
                info = tarfile.TarInfo(rel)
                info.size = len(data)
                tf.addfile(info, __import__("io").BytesIO(data))

        # ---- graph: drop every async node (the reported defect)
        nodes, kept = [], []
        for nid, kind, is_async in all_names:
            if nid.endswith(".unused"):
                continue
            if is_async:
                continue
            nodes.append({"id": nid, "name": nid, "text": f"def {nid.split('.')[-1]}(): pass"})
            kept.append(nid)
        # a couple of edges
        edges = [
            {"source": kept[0], "target": kept[1], "type": "calls", "key": 0},
            {"source": kept[2], "target": kept[0], "type": "calls", "key": 0},
        ]
        graph = {
            "directed": True,
            "multigraph": True,
            "graph": {"repo": t["repo"]},
            "nodes": nodes,
            "edges": edges,
        }
        gj = json.dumps(graph)

        # ---- embeddings keyed to the same (sync-only) node set
        npz_path = root / "embeddings" / f"{t['instance_id']}.npz"
        np.savez(npz_path, **{n: NRN.normal(size=DIM).astype(np.float32) for n in kept})

        # ---- a reference patch. ~15% of tasks edit an ASYNC body, mirroring
        #      the real corpus where 16/121 body-landing tasks do so.
        tgt = f"{short}/mod0.py"
        nlines = files[tgt].splitlines()
        #      Another ~20% edit a METHOD body, whose graph id is mod.Cls.method,
        #      so a patch->symbol mapper that drops the class name fails here.
        roll = RNG.random()
        edit_async = roll < 0.15 and any(l.startswith("async def") for l in nlines)
        if edit_async:
            ai = next(i for i, l in enumerate(nlines) if l.startswith("async def"))
            old = nlines[ai + 1]
            new = f"    await asyncio.sleep({RNG.randrange(0, 5)})  # patched"
            anchor = ai + 1
        elif roll < 0.35:
            mi = next(i for i, l in enumerate(nlines) if l.startswith("    def sync_0"))
            old = nlines[mi + 1]
            new = "        return -1  # patched"
            anchor = mi + 1
        else:
            si = next(i for i, l in enumerate(nlines) if l.startswith("def func_0"))
            old = nlines[si + 1]
            new = f"    return x + 999  # patched"
            anchor = si + 1
        nlines[anchor] = new
        patch = f"--- a/{tgt}\n+++ b/{tgt}\n@@ -{anchor+1},2 +{anchor+1},2 @@\n-{old}\n+{new}\n"

        tasks_rows.append(
            {
                "instance_id": t["instance_id"],
                "repo": t["repo"],
                "base_commit": t["base_commit"],
                "problem_statement": "synthetic",
                "hints_text": "",
                "patch": patch,
                "test_patch": "",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
        (root / "graphs" / f"{t['instance_id']}.json").write_text(gj)

    with (root / "tasks.jsonl").open("w", encoding="utf-8") as fh:
        for r in tasks_rows:
            fh.write(json.dumps(r) + "\n")

    # ---- reproduce the hard-link corruption.
    # First materialise the commit-named aliases that the real dataset carries
    # (129 task-named + 127 commit-named = 256), as exact copies.
    for sha, ts in by_commit.items():
        short = ts[0]["repo"].rsplit("/", 1)[-1]
        key = f"{short}_{sha}"
        src_iid = ts[0]["instance_id"]
        (root / "graphs" / f"{key}.json").write_bytes((root / "graphs" / f"{src_iid}.json").read_bytes())
        (root / "embeddings" / f"{key}.npz").write_bytes(
            (root / "embeddings" / f"{src_iid}.npz").read_bytes()
        )

    # Then keep exactly ONE name per commit group and zero the rest. In the
    # real corpus 127 of 129 task-named files are the dead ones, i.e. the
    # commit-named file is usually the survivor - so a per-task file check sees
    # ~98% of tasks as unusable. Reproduce that, with a couple of groups where
    # a task-named file survives instead (the shared-commit groups).
    blanked = 0
    for gidx, (sha, ts) in enumerate(sorted(by_commit.items())):
        short = ts[0]["repo"].rsplit("/", 1)[-1]
        key = f"{short}_{sha}"
        iids = [t["instance_id"] for t in ts]
        gnames = [f"{i}.json" for i in iids] + [f"{key}.json"]
        enames = [f"{i}.npz" for i in iids] + [f"{key}.npz"]
        # survivor position: the commit-named alias, except for a few groups
        keep = 0 if gidx % 63 == 0 else len(gnames) - 1
        for j, (gn, en) in enumerate(zip(gnames, enames)):
            if j == keep:
                continue
            (root / "graphs" / gn).write_bytes(b"")
            (root / "embeddings" / en).write_bytes(b"")
            blanked += 2
    # The mounted Kaggle input does not carry the lost aliases at all: the
    # release lists 524 files, fewer than 129 snapshots + 256 graphs + 256
    # embeddings. Reproduce that by deleting the 0-byte files instead.
    if kaggle_layout:
        for sub in ("graphs", "embeddings"):
            for f in (root / sub).iterdir():
                if f.stat().st_size == 0:
                    f.unlink()
    n_g = len(list((root / "graphs").iterdir()))
    n_e = len(list((root / "embeddings").iterdir()))
    print(f"synthetic corpus at {root}: {len(TASKS)} tasks, {n_g} graph + {n_e} embedding files, {blanked} zeroed")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(Path(args[0] if args else "/tmp/cgr_synth/data"), kaggle_layout="--kaggle-layout" in sys.argv)
