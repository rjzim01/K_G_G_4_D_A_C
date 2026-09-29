# Main competition — `gemma-4-developer-agent`

[Google - The Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent)

Post-train Gemma 4 into an autonomous SWE agent. Ranked by **bugs fixed**, not by a paper.

- **Start:** 23 Sept 2026 · **Entry + team merge:** 25 Nov 2026 · **Final submission:** 2 Dec 2026
- **Prizes:** $100,000 total — $65,000 competition ($37k / $18k / $10k) plus an optional $35,000
  paper award (that is the [paper track](../paper-track/))
- **Team size:** max 5. Submission cap: 5/day, 20 GB per submission.
- **Identity verification required** to compete.

Full rules and dataset detail live in
[`../paper-track/REQUIREMENTS.md`](../paper-track/REQUIREMENTS.md) §8, and the scraped pages are in
`docs/`.

## The task

129 public dev tasks (plus ~120 hidden test tasks) drawn from `fastapi/fastapi`, `Textualize/rich`,
`psf/requests` and `encode/httpx`. Each task is a defect to locate and fix in a checkout frozen at a
pinned commit.

- **Metric:** PASS/FAIL per issue, SWE-bench style — apply your patch, run the validation tests with
  pytest. Score is the percentage of patched repos that pass.
- **Time budget:** 12 hours total across all tasks, including sandbox setup, excluding validation.
  Per-task limits are optional via `eval_config.yaml`.
- **Model:** only `gemma-4-31b-it-qat-w4a16-ct`, for the agent and every subagent. Optional PEFT
  LoRA adapters in `adapters/<name>/`, referenceable per agent with `adapter: <name>`.

## Submission layout

```
submission.zip
├── agent.yaml            # REQUIRED root agent config
├── eval_config.yaml      # optional per-task time limits
├── configs/sampling.yaml # optional, pulled in with !include
├── prompts/system.md     # optional, pulled in with !include
├── sub_agents/*.yaml     # optional sub-agents / AgentTool
├── adapters/<name>/      # optional LoRA (adapter_config.json + adapter_model.safetensors)
└── skills/<name>/        # optional ADK skills (SKILL.md, scripts/, resources/)
```

Config is the Google **ADK Agent Config** spec, with sandboxing restrictions: `!include` resolves
relative to the file containing the tag, no path traversal outside the submission root (no `../`, no
symlinks), and only harness-provided tools or custom subagents declared via `agent_tool` are
callable. `run_skill_script` executes inside the persistent Docker sandbox and debits the central
time budget.

Output is `submission.parquet` with columns `id` and `prediction`.

## What is here — the submission

**[`SUBMISSION.md`](SUBMISSION.md) is the step-by-step: which folder to zip, how to build the
archive, and how to verify it before uploading.**

`submission/` is a working scaffold, staged so it can be zipped directly.

```
submission/
├── agent.yaml                        root `coder` agent: tools, two sub-agents
├── eval_config.yaml                  300 s/task default, 240 s abandon, per-repo overrides
├── configs/sampling.yaml             low temperature; stop on the diff fence
├── prompts/system.md                 the strategy: reproduce, minimal fix, verify, submit
├── sub_agents/locator.yaml           read-only search — keeps grep output out of the root context
├── sub_agents/patcher.yaml           read-only verification — baseline, apply, re-run, verdict
├── skills/repo_navigation/
│   ├── SKILL.md
│   ├── scripts/find_symbols.py       AST symbol/ref search — stdlib only, indexes `async def`
│   └── resources/repo_notes.md       what the four source repos look like
└── adapters/README.md                deliberately empty — see below
```

**The design decision that matters.** The submission does *not* depend on `cgr` having been run.
`find_symbols.py` parses the checkout in `/workspace` with `ast` instead of reading the released
graph, so navigation works on the corpus exactly as downloaded. It is also *more* reliable than the
graph tools would be: it indexes `async def`, which the released builder omits entirely (0 of 45,593
async functions are nodes). The system prompt tells the agent to probe the three graph tools once
and then fall back, so you find out whether the defect is present rather than assuming it.

No LoRA adapter is shipped. Adapters are optional, the base model is mandatory either way, and an
adapter trained on generic Python instructions will not beat the base model on this harness. See
`submission/adapters/README.md`.

### Build and validate

**Zip the *contents* of `submission/`, not the folder — `agent.yaml` has to be at the archive root.**
Full instructions and a copy-paste verification snippet are in [`SUBMISSION.md`](SUBMISSION.md).

```bash
python3 tools/build_submission.py                  # check only
python3 tools/build_submission.py --zip            # check, then write submission.zip
python3 tools/build_submission.py --zip --strict   # warnings are errors too
```

`submission.zip` is generated on demand and is gitignored, so it is not in this repo. Re-run the
build whenever you change anything under `submission/`; never edit the archive directly.

It enforces the rules that are actually checkable: `agent.yaml` at the root, no `!include` that
escapes the submission root, no symlinks, the 20 GB cap, an `SKILL.md` manifest with a `name:` field
for every skill, every `run_skill_script` path resolving to a real file, and Python that compiles.

### Read this before submitting

**[`SCHEMA-NOTES.md`](SCHEMA-NOTES.md) records which fields are verified and which are assumed.**

This was written without the dataset, so the *concepts* in the configs are right but some *field
names* are inferred. Reconcile against `sample_submission/agent.yaml` and `HARNESS_README.md` from
the download — the first validating run will likely produce schema errors, and each is a rename.

## Repairing the corpus

`cgr` is a research tool, not a submission dependency. Repair the corpus if you want the three graph
tools to work, but the submission is built to not care:

```bash
python3 tools/prepare_corpus.py --root "$CORPUS"                  # repair + report
python3 tools/prepare_corpus.py --root "$CORPUS" --limit 10       # smoke run
python3 tools/prepare_corpus.py --root "$CORPUS" --skip-repair    # measure only
```

`prepare_corpus.py` wraps `cgr` so the flag order is not something to remember, and handles the
read-only-input case. On Kaggle, `/kaggle/input` cannot be written, so pass a staging dir:

```bash
python3 tools/prepare_corpus.py --root /kaggle/input/gemma-4-developer-agent \
                                --staging /kaggle/working/corpus_rw
```

It copies `graphs/`, `embeddings/` and `tasks.jsonl`, and symlinks `snapshots/` and `wheels/` rather
than copying them, so a 22 GB corpus does not become 44 GB. It writes `results.json` in the same
schema the paper track's notebook emits, and prints a before/after summary.

### Running the agent end to end

**Not on this machine, and not on free Colab either.** `gemma-4-31b-it-qat-w4a16-ct` is 31B
parameters; at 4-bit the weights alone are ~15.5 GB, before KV cache, activations, and the sandbox
image. This box has 14 GB RAM total and no GPU, so the model does not fit at all — that is a
physical limit, not a slow-run.

| Target | VRAM | Verdict |
|---|---|---|
| This machine | — | no GPU, 14 GB RAM |
| Colab, free T4 | 15 GB | **will not fit** — weights alone exceed it |
| Kaggle, GPU T4 ×2 | 30 GB | works, and is the cheapest realistic option |
| Colab Pro, A100 | 40 GB | works |

Budget for ~24 GB of VRAM as a floor. You also need the harness itself (`swegemma`,
`adk-submission`, `adk-eval-core`), which ships with the gated dataset rather than from PyPI.

`cgr` is a different matter — CPU-only, numpy-only, and `find_symbols.py` is pure stdlib — so
corpus repair, corpus measurement, submission validation, and symbol search all run fine right
here. See `SUBMISSION.md` and the table in the top-level README.

**[`notebooks/run_agent_colab.ipynb`](notebooks/run_agent_colab.ipynb) is the driver.** Generated
by `tools/make_agent_notebook.py` — edit the script, not the JSON, then re-run it:

```bash
python3 tools/make_agent_notebook.py
```

It is 20 cells: config (the only cell to edit), a VRAM preflight that refuses to continue on an
undersized GPU, submission staging with an `agent.yaml`-at-root assertion, corpus acquisition for
the gated download, the harness invocation, a model-free smoke test of `find_symbols.py`, and
packaging to `submission.parquet`. The smoke-test cell runs on any runtime, CPU included, and is
the one cell that produces a real result without a GPU.

The harness invocation (`HARNESS_CMD`) is deliberately left unset. `swegemma`, `adk-submission`,
and `adk-eval-core` ship with the gated dataset and are not on PyPI, so the exact CLI is not
verifiable from here. The notebook stops with instructions rather than guessing, and parses
`HARNESS_README.md` if you upload it.

## Harness tools

`run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`, `write_file`,
`get_code_neighbors`, `search_similar_code`, `get_code_subgraph`.

The last three read the released code graph and embedding index, and are **gated on files larger than
100 bytes** — see the caveat below. On the corpus as downloaded they return nothing, so the
submission ships an AST-based substitute rather than relying on them.

## Getting the data (gated)

1. Sign in at kaggle.com and accept the rules of `gemma-4-developer-agent`.
2. `pip install kaggle`, credentials at `~/.kaggle/kaggle.json`.
3. `kaggle competitions download -c gemma-4-developer-agent` — 22.42 GB, 524 files, Apache 2.0.
4. Accept the Gemma 4 license to pull `gemma-4-31b-it-qat-w4a16-ct`.

Contents: `tasks.jsonl` (reference `patch` + `test_patch`), `snapshots/*.tgz` (129 git trees frozen at
`base_commit`), `graphs/*.json` (256 NetworkX AST call/dependency graphs), `embeddings/*.npz`
(256 × float32 256-dim node vectors), `wheels/` (124 prebuilt wheels, mounted read-only at
`/wheels/`), `docker/`, `sandbox/setup.py`, `sample_submission/` and `HARNESS_README.md`.

## Known defect in the released corpus — `cgr` fixes it

`graphs/` and `embeddings/` ship per-task files that are **hard links** to shared commit-level files.
The downloadable ZIP cannot represent a hard link, so only one name per commit group survives: on the
mounted Kaggle input **all 129 task-named graph files and 129 task-named embedding files are absent**,
so 100% of tasks have no graph or embedding under their own name. Separately, the graph builder
enumerates `def` and `class` but not `async def`, so **0 of 45,593 async functions are nodes**.

Both defects silently disable `get_code_neighbors`, `get_code_subgraph` and `search_similar_code` for
the affected tasks, which means the leaderboard partly measures how well an agent works without its
code-intelligence tools.

The submission here is built to be **unaffected** — `skills/repo_navigation` re-derives the same
information from the source in `/workspace`. Repair the corpus anyway if you want those three tools
to work, because it is the only way to know whether they are dead at scoring time:

```bash
python3 tools/prepare_corpus.py --root "$CORPUS"   # repair + audit + reindex + report
```

`cgr` itself is documented in [`../paper-track/README.md`](../paper-track/README.md), and the
full run also works as a Kaggle notebook — see
[`../paper-track/README.md`](../paper-track/README.md#run-it-on-kaggle--colab).

## Reference pages in `docs/`

Scrapes of the two live competition pages, reformatted for reading. They are the source for
everything asserted in [`SCHEMA-NOTES.md`](SCHEMA-NOTES.md).

- [`docs/main-competition-overview.md`](docs/main-competition-overview.md) — Overview: rules,
  timeline, prizes, submission layout, harness tool signatures
- [`docs/main-competition-data.md`](docs/main-competition-data.md) — Data tab: dataset schema, file
  inventory, generation and verification pipeline

## Still missing

- **The dataset.** Nothing here has been run against the real 22.42 GB corpus — no local eval, no
  measured pass rate. The scaffold is unvalidated beyond structural checks.
- **Schema reconciliation.** See [`SCHEMA-NOTES.md`](SCHEMA-NOTES.md). The config field names are
  inferred, not confirmed.
- **A tuned prompt.** The strategy in `prompts/system.md` is reasoned, not measured. It needs a
  local eval over the 129 dev tasks to know whether it beats the base model.
- **Nothing trained.** No LoRA adapter, and the base model is used as-is.
