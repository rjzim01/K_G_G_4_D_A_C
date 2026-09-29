# Paper track — `gemma-4-developer-agent-paper`

[Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)
· rules, rubric and prizes in [`REQUIREMENTS.md`](REQUIREMENTS.md) · index of both tracks in
[`../README.md`](../README.md).

**What you submit:** a Kaggle Writeup of max 3,000 words describing original, unpublished research on
agentic software engineering. Start 22 Sept 2026, deadline **12 Nov 2026, 23:59 UTC**. The Writeup
must carry a title, abstract, introduction, methods and experiments, and related work with citations;
code goes in the Project Links field as a public notebook.

**What this folder holds:** the paper being written, and `cgr`, the tool the paper is about — the
"Best New Resource" contribution, whose notebook is the public link that submission requires.

```
paper-track/
├── REQUIREMENTS.md   the track's rules, evaluation rubric, prizes, timeline
├── docs/             scraped Overview and Rules pages
├── paper/            the submission: paper.md (rendered), paper_template.md (tokens),
│                     cgr_ieee_latex_*.md + gemma_4_*.pdf (IEEE LaTeX build), submission-checklist.md
├── cgr.py            the tool — single file, numpy only
├── notebooks/        cgr_pipeline.ipynb, generated from cgr.py, submitted as a Project Link
├── tools/            make_notebook.py (cgr.py -> notebook), fill_results.py (results.json -> paper.md)
├── tests/            make_synthetic.py, a fixture corpus so cgr can be validated without the 22 GB download
└── results.json      a real 129-task run; every number in paper.md is substituted from it
```

Work through it in this order: run the notebook on the real corpus → get `results.json` →
`tools/fill_results.py` renders `paper/paper.md` → work the checklist in
`paper/submission-checklist.md`. Everything below documents the tool itself.

---

# cgr - Code Graph Repair

**A resource for the [Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent).**

`cgr` audits, repairs and re-indexes the competition's released code-intelligence corpus, and measures
what the shipped defects cost a participant agent. CPU-only, one file, only needs numpy, no LLM inference.

Research writeup: [`paper/paper_template.md`](paper/paper_template.md) (numbers auto-filled from
`results.json`).

---

## What it does

The release ships `graphs/` and `embeddings/` for every task. Two defects degrade them:

| # | Defect | Consequence |
|---|--------|-------------|
| 1 | Per-task graphs are **hard links** to shared commit-level graphs. ZIP cannot store hard links, so one name per commit group survives and the rest arrive **0 bytes** (local unzip) or are **absent** (the mounted Kaggle input). | The three code tools (`get_code_neighbors`, `get_code_subgraph`, `search_similar_code`) are gated on files exceeding 100 bytes, so they silently switch off. |
| 2 | The graph builder enumerates `def` and `class` but **not `async def`**. | Async functions are absent from the node set and unreachable by every graph tool. |

`cgr` provides:

- **`census`** - read-only inventory. Counts dead files, resolves the commit-group structure, reports how
  many tasks lose their own `instance_id` file.
- **`repair`** - rebuilds every lost artifact by copying from the one verified survivor in its commit
  group, then checks the result by SHA-256.
- **`audit`** - parses each task's source with `ast` and reports node coverage against that independent
  reference set, per kind / repo / task. Read-only.
- **`reindex`** - adds schema-compatible nodes (`id`, `name`, source `text`) for every symbol the audit
  found missing - on the released corpus, overwhelmingly async functions.
- **`retrieval_eval`** - the evaluation the release is missing. Uses each task's reference patch to work
  out which symbols that task is actually *about*, then reports the fraction of those symbols that the
  graph the agent sees can reach.

Plus `unpack` and `apply` helpers.

## Install

Python 3.9+ and numpy (preinstalled on Kaggle and Colab; otherwise `pip install numpy`).

```bash
git clone <this repo> && cd cgr
python3 cgr.py --help
```

## Use

```bash
CORPUS=/path/to/gemma-4-developer-agent   # the directory containing tasks.jsonl, graphs/, embeddings/

python3 cgr.py census  --root "$CORPUS"              # read-only: quantify the damage
python3 cgr.py repair  --root "$CORPUS" --dry-run    # read-only: preview the repair
python3 cgr.py repair  --root "$CORPUS"              # write
python3 cgr.py audit   --root "$CORPUS"              # read-only: node coverage
python3 cgr.py reindex --root "$CORPUS" --out-dir repaired
python3 cgr.py apply   --root "$CORPUS" --out-dir repaired
python3 cgr.py bench   --root "$CORPUS"
```

`audit`, `bench` and `reindex` skip tasks whose graph is still a dead 0-byte file, so run `repair` first.

`report` runs the whole pipeline and writes `results.json` in the canonical schema - the same one the
notebook emits, so the two produce interchangeable files.

> **`report` mutates the corpus in place.** It repairs, re-indexes and applies. Run it on a copy if you
> want to keep the damaged original for comparison. The notebook has the same property by design: it has
> to measure "before" and "after" on the same corpus, so it captures "before" first and prints it.

As a library:

```python
from cgr import census, repair, audit, reindex, apply_repaired, retrieval_eval, load_tasks

print(census("corpus")["graph"]["pct_tasks_graph_tools_disabled"])
```

## Run it on Kaggle / Colab

[`notebooks/cgr_pipeline.ipynb`](notebooks/cgr_pipeline.ipynb) is **self-contained** - `cgr.py` is embedded
verbatim, so there is nothing to clone and no dependency to resolve. It finds the corpus from an attached
dataset or falls back to the Kaggle CLI, runs the full pipeline, and writes `results.json` into the work
directory.

**Kaggle (recommended).** Accept the rules for `gemma-4-developer-agent`, create a notebook from
`cgr_pipeline.ipynb`, add the competition data as an input, and *Run All*. `/kaggle/input` is read-only,
so the notebook copies `tasks.jsonl`, `graphs/` and `embeddings/` into `/kaggle/working/corpus_rw` (and
links `snapshots/`) before repairing. Download `results.json` from the output.

**Colab.** Upload your `kaggle.json` to `/content`, make sure **~50 GB** is free (the archive is ~22.4 GB
and is unpacked in place), and run all cells. `results.json` is written to `/content`.

Regenerate the notebook after editing `cgr.py`:

```bash
python3 tools/make_notebook.py
```

## Fill in the paper

```bash
python3 tools/fill_results.py /path/to/real/results.json \
    --notebook-url https://www.kaggle.com/code/YOUR_USER/YOUR_NOTEBOOK
```

Writes `paper/paper.md` with every number substituted and a word count. Budget is 3,000 words; the
current writeup lands around 2,700.

`fill_results.py` never writes a clean paper from the synthetic fixture corpus: given fixture results it
writes a banner-marked draft and exits with status 2. With real results it exits 1 if a token is
unresolved, a `TODO` remains (notebook URL, Discussion links), or the paper is over 3,000 words.

## Test

```bash
rm -rf /tmp/cgr_synth
python3 tests/make_synthetic.py /tmp/cgr_synth/data   # fixture that replicates the release's shape
# add --kaggle-layout to make the lost aliases absent instead of 0 bytes, as on the Kaggle input
python3 cgr.py report --root /tmp/cgr_synth/data --out /tmp/cgr_synth/results.json
```

To confirm the notebook and the CLI agree, run each on its *own* fresh copy of the fixture (a second
`report` on the same directory would see an already-repaired corpus and legitimately report different
"before" numbers):

```bash
python3 tests/make_synthetic.py /tmp/cA/data && python3 tests/make_synthetic.py /tmp/cB/data
python3 cgr.py report --root /tmp/cA/data --out /tmp/cA/cli.json   # then run the notebook on /tmp/cB
```

The fixture reproduces the commit-group structure, the 0-byte files, the missing async nodes and
async-target patches. It exists to prove the tool is correct, **not** to produce paper numbers.

## What cgr does not do

- It does not invent embeddings. Re-indexed nodes are structurally valid and reachable by the graph
  tools, but carry no vector, so `search_similar_code` cannot surface them until a host supplies the
  embedder (which is not part of the released dataset).
- It does not synthesise `calls` edges. The release ships a single edge type with very low density; cgr
  reports this rather than guessing.
- It does not re-clone repositories. Repair is a pure function of the release itself.

## Licence

Apache 2.0. See [`../LICENSE`](../LICENSE).

## Citation

> Elan Markowitz, Bryan Perozzi, Benedek Rózemberczki, Glenn Cameron, Hadi Hemmati, Yuchen Li,
> Michael Galkin, Majid Farhadi, Ryan Holbrook, and Ashley Oldacre. Google - The Gemma 4 Developer Agent
> Competition. https://www.kaggle.com/competitions/gemma-4-developer-agent, 2026. Kaggle.


-------------------------------------------------------------------------------------------------------------------------------------------
Steps on Kaggle

1. Join the main competition (gemma-4-developer-agent) and accept its rules. Without that, you can't attach its data.
2. Go to Code → New Notebook → File → Import Notebook and upload notebooks/cgr_pipeline.ipynb.
3. In the right panel, choose Add Input → Competitions → gemma-4-developer-agent.
4. Set Accelerator: None (CPU is enough). Internet can stay off.
5. Click Run All. When it finishes, download results.json from the Output tab (/kaggle/working/results.json).
6. Bring that file back here and we'll run fill_results.py.

One thing to check

To publish the notebook, you use Save Version → Save & Run All, and Kaggle keeps everything in /kaggle/working as output. That output is
capped at about 20 GB. The notebook's staged copy of the data also sits there; it prints its size ("staged a writable copy … (X GB)"). If
that copy is large, saving the version could fail.

I can add a final cell that deletes the staged copy after results.json is written, so only the small results are kept. That's about two
lines. Want me to add it?
-------------------------------------------------------------------------------------------------------------------------------------------