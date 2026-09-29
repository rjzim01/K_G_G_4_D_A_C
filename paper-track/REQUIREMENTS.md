https://www.kaggle.com/competitions/gemma-4-developer-agent-paper

# Google — The Gemma 4 Developer Agent **Paper Track**

Source: <https://www.kaggle.com/competitions/gemma-4-developer-agent-paper>
Retrieved: 2026-09-27 · Host: Google DeepMind · License: Apache 2.0

---

## 1. What this track is

There are **two** active competitions:

| Competition | Slug | What you submit |
|---|---|---|
| Featured (main) | `gemma-4-developer-agent` | `submission.zip` agent config — scored by bugs fixed |
| **Paper Track (this one)** | `gemma-4-developer-agent-paper` | A **Kaggle Writeup** research paper |

- The main leaderboard ranks by **bugs fixed**. The Paper Track instead asks you to **contribute research advancing the state of the art in agentic software engineering**.
- **Participation in the main competition is NOT required** to submit to the Paper Track (though joining both is encouraged).
- Winning papers are highlighted at a **Google-hosted event** (e.g. a NeurIPS expo workshop) and awarded prizes.
- Research must be **original and unpublished**. Related prior work may be included/cited.

### Topic suggestions (not exhaustive)
- **Tuning & Optimization** — parameter-efficient fine-tuning (PEFT/LoRA) and RL approaches to improve SWE-agent capability.
- **Code Comprehension** — novel techniques for code-graph generation, parsing, and embedding for deep repository comprehension.
- **Tasks & Benchmarks** — new tasks, evaluation datasets, or resources targeting code structure, graphs, and structured code generation.
- **Graph Reasoning** — methods/architectures for LLM reasoning over large-scale graphs.

Submissions **leveraging the released code-graph and embedding dataset are highly encouraged** (not required).

---

## 2. Timeline

| Date | Event |
|---|---|
| **Sept 22, 2026** | Start date |
| **Nov 12, 2026, 11:59 PM UTC** | **Final Submission Deadline** (papers) |

Draft/unsent Writeups are not eligible. Organizers reserve the right to change dates.

### Related main-competition dates (if you also enter the featured track)
| Date | Event |
|---|---|
| Sept 23, 2026 | Start date |
| Nov 12, 2026 (optional) | Deadline to submit Research Paper |
| Nov 25, 2026 | Entry Deadline + Team Merger Deadline |
| Dec 2, 2026 | Final Submission Deadline |

---

## 3. Evaluation — 5 criteria, 0–5 each, averaged

Eligibility: you must **join the competition** and **submit a Writeup**.

| Criterion | Question asked |
|---|---|
| **Novelty** | Does the work provide new insights, deepen understanding, or highlight important properties of existing methods? |
| **Quality** | How general/universal is the approach beyond the competition? Does it translate to similar problems? How well does it generalize? |
| **Relevance** | Is there significance and/or potential impact on software engineering and agentic learning? |
| **Verifiability** | Is there sufficient information to understand how the innovation works; how data was obtained, analyzed, interpreted? |
| **Clarity** | Is the paper clearly presented and written? |

- Final score = **average of the five** (0 = lowest, 5 = highest).
- Rubric feedback is **not** shared.
- **Ties** → earliest-entered paper wins. Disqualified winner → next-highest score.

---

## 4. Submission requirements

A valid submission is a **Kaggle Writeup** acting as the research-paper report. It must include:

1. **Title and subtitle**
2. **Abstract**
3. **Introduction**
4. **Description of the research — including methods and experiments**
5. **Related works and citations**

### Scope & limits
- **3,000 words maximum.** (Scope: original, unpublished research.)
- **Non-archival** — submitting here does not block submission to other conferences/venues.

### Optional assets
- **Public Notebook** — code should be submitted as a *public* notebook in the **Project Links** field. Must be publicly accessible, no login/paywall. A private Kaggle Notebook is auto-published after the deadline.
- **Public Project Link** — instead of (or in addition to) the Writeup, an **arXiv-ready LaTeX/Word PDF** of the paper, publicly accessible, no login/paywall.
- Media Gallery / cover image.
- ⚠️ Any private Kaggle Resource attached to a public Writeup is **automatically made public after the deadline**.

### Mechanism
Click **"New Writeup"** on the competition page → save → a **"Submit"** button appears top-right. One Writeup per team, but it can be un-submitted, edited, and re-submitted. Submit before the deadline; drafts don't count.

---

## 5. Prizes — $35,000 total

| Award | Amount | Criteria |
|---|---|---|
| **Overall Best Paper** | **$15,000** | Highest average score across the 5 criteria |
| **Best New Resource** | **$10,000** | A new **dataset / tool / software**. E.g. a dataset from the provided embeddings usable for evaluation or fine-tuning; a library that clusters code by behavior; a dashboard for exploring structurally-similar GitHub repos. (Contrasted with an *empirical* paper that generates new knowledge.) |
| **Best New Application** | **$10,000** | A novel **use-case** (e.g. using code-graphs to write TPU kernels). Creative use of code-graphs and/or the provided embeddings for previously-unexplored use-cases; may include new eval datasets for entirely novel tasks or application to existing benchmarks. |

Top submissions highlighted at a **Google-hosted expo during NeurIPS 2026**. A paper may compete across categories; the overall award is the single highest score.

---

## 6. Rules highlights

- **Sponsor:** Google LLC, 1600 Amphitheatre Parkway, Mountain View, CA 94043
- **Max team size:** 5. Team merges allowed (by team leader) until the Team Merger Deadline, subject to the daily-submission cap.
- **Submission limits:** max **5 submissions/day**; up to **2 Final Submissions** selected for judging.
- **Identity verification required** to compete.
- **Winner license:** winning submission + source code licensed under an **OSI-approved license**. Data access/use: **Apache 2.0** (commercial or non-commercial use permitted, incl. academic research).
- **Data security:** don't redistribute Competition Data to non-participants; notify Kaggle of any unauthorized access.
- **Submission size limit:** 20,480 MB (20 GB) per submission.

---

## 7. Judges

Elan Markowitz (MLE, Google) is listed as judge, with citation to: Elan Markowitz, Bryan Perozzi, Benedek Rózemberczki, Glenn Cameron, Hadi Hemmati, Yuchen Li, Michael Galkin, Majid Farhadi, Ryan Holbrook, Ashley Oldacre.

---

## 8. Context: the main competition (what you'd be writing about)

- **Task:** post-train Gemma 4 into autonomous SWE agents that navigate large repos and draft fixes for real bug-fix / feature-request issues.
- **Metric:** PASS/FAIL per issue (SWE-Bench style) — patch applied to the repo snapshot, validation tests run via pytest. Score = % of patched repos passing.
- **Time budget:** **12 hours** total for all tasks, including sandbox setup, excluding validation time. Optional per-task limits in `eval_config.yaml`.
- **Model:** only `gemma-4-31b-it-qat-w4a16-ct` is supported, for every agent and subagent. Optional PEFT **LoRA** adapters (`.safetensors`) in `adapters/<name>/`, referenceable per-agent via `adapter: <name>`.
- **Submission layout:**
  ```
  submission.zip
  ├── agent.yaml            # REQUIRED root agent config
  ├── configs/sampling.yaml # optional, via !include
  ├── prompts/system.md     # optional, via !include
  ├── sub_agents/*.yaml     # optional sub-agents / AgentTool
  ├── adapters/<name>/      # optional LoRA (adapter_config.json + adapter_model.safetensors)
  └── skills/<name>/        # optional ADK skills (SKILL.md, scripts/, resources/)
  ```
- **Config language:** Google **ADK Agent Config** spec, with sandboxing restrictions. `!include` resolves relative to the file containing the tag. No path traversal outside the submission root (no `../`, no symlinks). Only harness-provided tools or custom subagents via `agent_tool` are callable. `run_skill_script` executes inside the persistent Docker sandbox and debits the central time budget.
- **Harness tools:** `run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`, `write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`.
- **Prizes:** $100,000 total → competition $65,000 (1st $37k, 2nd $18k, 3rd $10k) + optional paper award $35,000.

### Dataset (gated)
- 129 public dev tasks, ~120 hidden test tasks; repos: `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`.
- Contents: `tasks.jsonl` (incl. reference `patch` + `test_patch`), `snapshots/*.tgz` (129 git trees frozen at `base_commit`), `graphs/*.json` (256 NetworkX AST call/dependency graphs backing the graph tools), `embeddings/*.npz` (256 × float32 256-dim node vectors, backs `search_similar_code`), `wheels/` (124 prebuilt wheels mounted read-only at `/wheels/` for offline `pip`), `docker/`, `sandbox/setup.py`, `sample_submission/`, **`HARNESS_README.md`** (in-depth guide to `swegemma`, `adk-submission`, `adk-eval-core`, two-container sandbox lifecycle, tool signatures, context compaction, local CLI eval), `submission.parquet` (output: `id`, `prediction`).
- Curation pipeline: commit/PR mining (logic + tests) → issue linking & prompt extraction → filtering/de-noising → **fail-to-pass** baseline verification + **pass-to-pass** solution verification → frontier-model near-completion check on the test set.
- Total 22.42 GB, 524 files, Apache 2.0. **Requires signing in and accepting the competition rules.**

---

## 9. Local files in this repo

This project covers **both** competitions, split into one folder each - see
[`../README.md`](../README.md) for the map. Files for this paper track:

```
REQUIREMENTS.md                          ← this file
docs/paper-track-overview.md             ← scraped Overview (Description/Timeline/Evaluation/Submission/Prizes/Judges)
docs/paper-track-rules.md                ← scraped Rules
paper/paper_template.md                  ← the writeup, with {{tokens}} for every number
paper/paper.md                           ← paper_template.md rendered from a real results.json
paper/submission-checklist.md            ← what must be ticked before submitting
paper/cgr_ieee_latex_*.md, *.pdf         ← IEEE LaTeX build of the same paper
cgr.py                                   ← the tool this paper is about
notebooks/cgr_pipeline.ipynb             ← standalone notebook, submitted as a public Project Link
tools/fill_results.py                    ← results.json + template -> paper.md
tools/make_notebook.py                   ← cgr.py -> cgr_pipeline.ipynb
tests/make_synthetic.py                  ← fixture corpus, for validating cgr without the 22 GB download
results.json                             ← real 129-task run; the source of every number in the paper
../references/gemma4-tech-report.pdf     ← Gemma 4 Technical Report (arXiv:2607.02770v2)
```

Files for the featured competition:

```
../main-competition/docs/main-competition-overview.md  ← scraped Overview
../main-competition/docs/main-competition-data.md      ← scraped Data tab (dataset schema)
```

### Still to fetch manually (Kaggle auth required)
Nothing on the paper track is downloadable — it has no data, only the Writeup form. If you also enter the featured competition, you'll need to:
1. Sign in at kaggle.com and **accept the competition rules**.
2. Install the CLI: `pip install kaggle`, then place credentials at `~/.kaggle/kaggle.json`.
3. `kaggle competitions download -c gemma-4-developer-agent` (22.42 GB) to get the dataset incl. `HARNESS_README.md` and `sample_submission/`.
4. Accept the Gemma 4 license to pull the model: `gemma-4-31b-it-qat-w4a16-ct`.
