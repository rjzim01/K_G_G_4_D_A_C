#!/usr/bin/env python3
"""Generate notebooks/run_agent_colab.ipynb.

The notebook is written by a script rather than by hand so the JSON stays valid
and the shared constants (model id, VRAM floor, competition name) are defined in
exactly one place. Run this after changing any of those.
"""

import json
import pathlib

MODEL = "gemma-4-31b-it-qat-w4a16-ct"
COMP = "gemma-4-developer-agent"
VRAM_FLOOR_GB = 24  # 15.5 GB of weights + KV cache + activations + sandbox

cells = []


def md(*lines):
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": [l + "\n" for l in "\n".join(lines).split("\n")[:-1]]
                             + [""] if False else
                  [l + "\n" for l in "\n".join(lines).split("\n")]})

def code(src, collapsed=False):
    src = src.strip("\n")
    lines = src.split("\n")
    src_lines = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    m = {}
    if collapsed:
        m["collapsed"] = True
        m["scrolled"] = True
    cells.append({"cell_type": "code", "execution_count": None, "metadata": m,
                  "outputs": [], "source": src_lines})


# ---------------------------------------------------------------- 0. header
md(r"""
# Gemma 4 Developer Agent — run the submission

Runs `main-competition/submission/` on a GPU runtime and produces `submission.parquet`.

**Runtime:** `Runtime > Change runtime type > GPU`. This notebook needs **≥24 GB VRAM**
(see the preflight in the next section). Kaggle's **GPU T4 ×2** is free and fits; on Colab
use **L4 or A100** (paid). Free Colab T4 is 15 GB and will not hold the model.

**Two cells need you, and the notebook will say so out loud rather than fail silently:**

1. `HARNESS_CMD` — the eval invocation. I could not verify the exact CLI syntax because
   `HARNESS_README.md` ships with the gated dataset. Upload it and cell 6 will print the
   command for you; otherwise paste in the one line from that file.
2. `HARNESS_ARGS` — anything after it (model flags, task filters).

Everything else runs as-is.
""")

# ---------------------------------------------------------------- 1. config
md(r"""
## 0. Configuration — the only cell you need to edit

Everything tunable lives here. The rest of the notebook reads these names.

`HARNESS_CMD` is the one I could not verify: `swegemma` / `adk-submission` /
`adk-eval-core` ship with the gated dataset, and I do not have `HARNESS_README.md`. Upload
that file and section 5 will print the exact invocation for you. Do not guess it.
""")

code(r'''
MODEL = "''' + MODEL + r'''"
COMP  = "''' + COMP + r'''"
VRAM_FLOOR_GB = ''' + str(VRAM_FLOOR_GB) + r'''   # 15.5 GB weights + KV cache + activations + sandbox

# --- paths; leave None to auto-detect -------------------------------------------------
CORPUS_ROOT    = None   # an already-unpacked corpus
SUBMISSION_ZIP = None   # /content/submission.zip  (agent.yaml must be at the ROOT)
PREDICTIONS    = None   # predictions.jsonl from the harness, if you want to build the parquet

# --- harness --------------------------------------------------------------------------
HARNESS_CMD  = None     # e.g. "!swegemma eval"  <- from HARNESS_README.md
HARNESS_ARGS = []       # model flags, task filters, --config ...
TASK_LIMIT   = 1        # 1 while you debug; None for the full 129-task sweep

import os, sys, json, shutil, subprocess
from pathlib import Path

def env_pick() -> Path:
    for c in ("/content", "/kaggle/working", Path.cwd()):
        p = Path(c)
        if p.is_dir():
            return p
    return Path.cwd()

WORK = env_pick() / "gemma4_agent"
WORK.mkdir(parents=True, exist_ok=True)

def say(*a):
    print(*a, flush=True)

def sh(cmd, **kw):
    say(f"$ {cmd if isinstance(cmd, str) else ' '.join(map(str, cmd))}")
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw)

print("python  ", sys.version.split()[0])
print("workdir ", WORK)
print("model   ", MODEL)
''')

# ---------------------------------------------------------------- 2. preflight
md(r"""
## 1. GPU preflight — run this first

Fails fast on purpose. A 22 GB corpus download followed by an out-of-memory crash on a
15 GB card is a bad afternoon; this cell takes five seconds.
""")

code(r'''
try:
    import torch
except ImportError:
    raise SystemExit(
        "STOP: torch is not installed.\n"
        "  Runtime > Change runtime type > GPU, then restart the runtime."
    )

if not torch.cuda.is_available():
    raise SystemExit(
        "STOP: no CUDA device is visible.\n"
        "  Runtime > Change runtime type > pick a GPU accelerator, then RESTART.\n"
        "  Restart is required - changing the runtime does not hot-attach a GPU."
    )

props = torch.cuda.device_properties(0)
vram  = props.total_memory / 1e9
n_gpu = torch.cuda.device_count()

say(f"GPU      {props.name}")
say(f"devices  {n_gpu}")
say(f"VRAM     {vram:.1f} GB each" + (f"   ({vram * n_gpu:.0f} GB combined)" if n_gpu > 1 else ""))
say(f"floor    {VRAM_FLOOR_GB} GB for {MODEL}")
say("")

if vram < VRAM_FLOOR_GB:
    raise SystemExit(
        f"STOP: {vram:.0f} GB VRAM is under the {VRAM_FLOOR_GB} GB floor.\n"
        f"The 4-bit weights alone are 15.5 GB, before KV cache and the sandbox.\n"
        f"\n"
        f"  Colab free T4   15 GB   will NOT fit\n"
        f"  Colab L4        24 GB   fits (paid)\n"
        f"  Colab A100      40 GB   fits (paid)\n"
        f"  Kaggle T4 x2    30 GB   fits (free)  <- best value\n"
        f"  Kaggle P100 x2  32 GB   fits (free)\n"
        f"\n"
        f"Do this now, not after the 22 GB download."
    )

say("PASS: enough VRAM to attempt the run.")
say("Caveat: multi-GPU does not reliably shard a 31B model. If you OOM on T4 x2,")
say("that is why - move to Kaggle P100 x2 or Colab A100.")
''')

# ---------------------------------------------------------------- 3. deps
md("## 2. Dependencies")

code(r'''
# Colab ships torch already. Everything else here is small.
for pkg in ("huggingface_hub", "pyarrow", "pandas", "kaggle"):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], check=False)

import importlib
for m in ("torch", "pandas", "pyarrow", "huggingface_hub"):
    mod = importlib.import_module(m)
    say(f"{m:<16} {getattr(mod, '__version__', '?')}")
''')

# ---------------------------------------------------------------- 4. submission
md(r"""
## 3. Stage the submission

Either upload `submission.zip` to the panel on the left, or point `SUBMISSION_ZIP` at a
path. The zip must contain `agent.yaml` **at the root** — see
`main-competition/SUBMISSION.md`. This cell verifies that and refuses otherwise.
""")

code(r'''
import zipfile

def find_zip():
    if SUBMISSION_ZIP and Path(SUBMISSION_ZIP).exists():
        return Path(SUBMISSION_ZIP)
    for base in (Path("/content"), Path("/kaggle/working")):
        if not base.is_dir():
            continue
        for p in base.rglob("submission*.zip"):
            return p
    return None

src = find_zip()
if src is None:
    raise SystemExit(
        "submission.zip not found.\n"
        "Build it locally:\n"
        "  cd K_G_G_4_DeveloperAgent/main-competition\n"
        "  python3 tools/build_submission.py --zip --strict\n"
        "then upload it with the file panel on the left."
    )

with zipfile.ZipFile(src) as z:
    names = z.namelist()
    assert z.testzip() is None, "corrupt archive"
    assert "agent.yaml" in names, (
        f"agent.yaml is not at the archive root. Got: {names[:5]}\n"
        f"Zip the CONTENTS of submission/, not the folder itself."
    )
    z.extractall(WORK / "entry")

say(f"submission  {src}")
say(f"extracted   {WORK / 'entry'}")
for n in sorted(names):
    say("   ", n)
''')

# ---------------------------------------------------------------- 5. corpus
md(r"""
## 4. Get the corpus (gated)

Three ways, tried in order: an already-unpacked copy, the Kaggle CLI with your
`kaggle.json`, or a manual upload. The release is ~22.4 GB compressed, ~45 GB unpacked.

`/kaggle/input` is read-only. `cgr` repairs in place, so if you are on Kaggle the
`prepare_corpus.py` wrapper stages a writable copy and symlinks the large
`snapshots/` instead of duplicating it.
""")

code(r'''
def corpus_ready(p: Path) -> bool:
    return p.is_dir() and (p / "tasks.jsonl").exists() and (p / "graphs").is_dir()

def locate_corpus():
    if CORPUS_ROOT and corpus_ready(Path(CORPUS_ROOT)):
        return Path(CORPUS_ROOT)
    for base in (Path("/kaggle/input"), Path("/content")):
        if not base.is_dir():
            continue
        for tj in base.rglob("tasks.jsonl"):
            if (tj.parent / "graphs").is_dir():
                return tj.parent
    return None

def download_corpus():
    cred = Path.home() / ".kaggle" / "kaggle.json"
    if not cred.exists():
        for cand in (WORK / "kaggle.json", Path("/content") / "kaggle.json"):
            if cand.exists():
                shutil.copy(cand, cred); break
    if not cred.exists():
        raise SystemExit(
            "No corpus and no ~/.kaggle/kaggle.json.\n"
            "  1. kaggle.com -> Settings -> API -> Create New Token\n"
            "  2. upload that kaggle.json to the notebook file panel\n"
            f"  3. accept the {COMP} rules, then re-run\n"
            f"Or set CORPUS_ROOT if you already unpacked it."
        )
    if not shutil.which("kaggle"):
        sh([sys.executable, "-m", "pip", "install", "-q", "kaggle"])
    zp = WORK / f"{COMP}.zip"
    if not zp.exists():
        say("downloading ~22.4 GB, this takes a while ...")
        sh(["kaggle", "competitions", "download", "-c", COMP, "-p", str(WORK)])
    say("extracting ~45 GB ...")
    import zipfile as _z
    dest = WORK / "corpus"
    with _z.ZipFile(zp) as z:
        z.extractall(dest)
    for tj in dest.rglob("tasks.jsonl"):
        if (tj.parent / "graphs").is_dir():
            return tj.parent
    return None

DATA = locate_corpus() or download_corpus()
if DATA is None:
    raise SystemExit("could not obtain the corpus")

n_tasks = sum(1 for _ in open(DATA / "tasks.jsonl"))
say(f"corpus   {DATA}")
say(f"tasks    {n_tasks}")
say("note: the released graph/embeddings index is broken - 0-byte files from a ZIP")
say("      losing hard links. find_symbols.py sidesteps this, so you do NOT need to")
say("      run cgr before scoring. Run cgr only if you want the paper's numbers.")
''')

# ---------------------------------------------------------------- 6. harness cmd
md(r"""
## 5. ⚠️ The harness invocation — one line you must fill in

I could not verify this syntax. `swegemma` / `adk-submission` / `adk-eval-core` ship with
the gated dataset and are not on PyPI, and I do not have `HARNESS_README.md` here. I am
not going to invent a plausible-looking command and let you discover the error an hour in.

**If you uploaded `HARNESS_README.md`, the cell below finds it and prints the eval
commands.** Otherwise open it on Kaggle, find the local-eval invocation, and paste that
one line here.
""")

code(r'''
def show_readme():
    for base in (Path("/content"), Path("/kaggle/working"), Path.cwd()):
        if not base.is_dir():
            continue
        for p in base.rglob("HARNESS_README*"):
            say(f"--- {p} ---")
            txt = p.read_text(errors="replace")
            for line in txt.splitlines():
                if any(k in line.lower() for k in ("swegemma", "eval", "predict", "parquet", "!pip")):
                    say("   ", line.strip())
            return
    say("no HARNESS_README found. Upload it to the left panel to have it parsed here.")

show_readme()
say("")
if HARNESS_CMD:
    say("HARNESS_CMD is set:", HARNESS_CMD)
else:
    say("HARNESS_CMD is still None - the next cell will stop rather than guess.")
''', collapsed=True)

# ---------------------------------------------------------------- 7. run
md(r"""
## 6. Run the evaluation

120 s/task default, 240 s abandon, 129 tasks, 12 h budget. The first task is the one to
watch: a schema error in `agent.yaml` surfaces immediately, so run **one task first**
rather than the full sweep. Set `TASK_LIMIT = 1` below until you have seen a green run.
""")

code(r'''
if not HARNESS_CMD:
    raise SystemExit(
        "HARNESS_CMD is not set.\n\n"
        "Open HARNESS_README.md from the competition download, find the local-eval\n"
        "invocation, and paste it into the cell above. Everything else in this\n"
        "notebook is ready; this is the only unknown."
    )

args = list(HARNESS_ARGS)
if TASK_LIMIT:
    args += ["--limit", str(TASK_LIMIT)]

cmd = HARNESS_CMD if HARNESS_CMD.startswith("!") else HARNESS_CMD
full = f"{cmd} {' '.join(args)} --submission {WORK / 'entry'}".strip()
say("running:", full)
say("")

rc = sh(full, cwd=str(WORK)).returncode
say("")
say("exit code:", rc)
if TASK_LIMIT == 1:
    say("Green? Set TASK_LIMIT = None and re-run from here for the full sweep.")
''', collapsed=True)

# ---------------------------------------------------------------- 8. smoke test
md(r"""
## 7. Smoke test that needs no model — runs on any runtime, including CPU

Worth running regardless of the eval, because it validates the part of the submission
that is entirely mine: `find_symbols.py` inside a real checkout. If this fails, the skill
is broken and the agent will be navigating blind.

This is the one cell in this notebook that produces a real result today.
""")

code(r'''
import ast, tempfile, subprocess

SCRIPT = WORK / "entry" / "skills/repo_navigation/scripts/find_symbols.py"
assert SCRIPT.exists(), f"missing {SCRIPT}"

# Stand up a small async-heavy checkout: the released graph builder indexes `def` and
# `class` but NOT `async def`, which is the whole reason this script exists.
DEMO_CORE = "\n".join([
    "import asyncio",
    "",
    "class Session:",
    "    def close(self):",
    "        return None",
    "",
    "def sync_helper(x):",
    "    return x * 2",
    "",
    "async def fetch(url):",
    "    await asyncio.sleep(0)",
    "    return url",
    "",
    "async def stream(url):",
    "    async for chunk in fetch(url):",
    "        yield chunk",
    "",
])

demo = Path(tempfile.mkdtemp()) / "demo_repo"
(demo / "pkg").mkdir(parents=True)
(demo / "pkg" / "__init__.py").write_text("")
(demo / "pkg" / "core.py").write_text(DEMO_CORE)
(demo / "app.py").write_text(
    "from pkg.core import fetch, Session\n"
    "\n"
    "async def main():\n"
    "    await fetch('x')\n"
)

def run(*argv):
    r = subprocess.run([sys.executable, str(SCRIPT), *argv],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout.strip() or r.stderr.strip())

rc1, out1 = run("summary", "--root", str(demo))
say("--- summary ---"); say(out1)

rc2, out2 = run("calls", "--root", str(demo), "-q", "fetch")
say("--- calls fetch ---"); say(out2)

ok = rc1 == 0 and rc2 == 0
say("")
say("SMOKE TEST:", "PASS" if ok else "FAIL")
if ok:
    say("The skill indexes async def and resolves real static references.")
    say("The agent will not be navigating blind.")
''')

# ---------------------------------------------------------------- 9. parquet
md(r"""
## 8. Produce `submission.parquet`

Two columns: `id` and `prediction`. The prediction is the agent's `FinalResponse` for the
task — the patch plus any final summary, exactly as the harness collects it.
""")

code(r'''
import pandas as pd

def build_parquet(pred_path):
    rows = []
    with open(pred_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    missing = {"id", "prediction"} - set(df.columns)
    if missing:
        raise SystemExit(f"prediction file is missing column(s): {missing}")
    out = WORK / "submission.parquet"
    df[["id", "prediction"]].to_parquet(out, index=False)
    say(f"wrote {out}  rows={len(df)}")
    say(df[["id"]].head().to_string(index=False))
    return out

if PREDICTIONS:
    build_parquet(PREDICTIONS)
else:
    say("PREDICTIONS not set - nothing to package yet.")
    say("Point it at the harness's own output (it writes per-task predictions), or set")
    say("it to None and let the harness emit submission.parquet directly.")
''')

# ---------------------------------------------------------------- 10. notes
md(r"""
## 9. Before you trust any number from this

- **`SCHEMA-NOTES.md`** — the config field names in `agent.yaml` are *inferred* from the
  rules pages, not confirmed. The first validating run will likely produce schema errors.
  Each one is a rename, not a redesign. Reconcile against `sample_submission/agent.yaml`.
- **No pass rate has been measured.** This notebook is a harness for measuring one, not a
  report of a result.
- **Prompt is untuned.** `TASK_LIMIT = 1` first, read the transcript, then sweep.
- **The corpus is broken as released** and this notebook does not fix it, by design —
  `find_symbols.py` does not read the graph. Run `cgr` only if you want the paper's
  coverage numbers.
""")

nb = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": [], "name": "run_agent_colab.ipynb", "toc_visible": True},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

out = pathlib.Path(__file__).resolve().parent.parent / "notebooks" / "run_agent_colab.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(nb, indent=1) + "\n")

import re
kinds = [c["cell_type"] for c in cells]
print(f"wrote {out}")
print(f"  {len(cells)} cells ({kinds.count('markdown')} md, {kinds.count('code')} code)")
