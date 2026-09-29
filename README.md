# Google — The Gemma 4 Developer Agent

This directory holds work for **two different Kaggle competitions**. They are independent: you can
enter either, both, or neither. They are kept in separate folders so nothing from one track is
mistaken for a deliverable of the other.

| Folder | Competition | What you submit | Prize |
|---|---|---|---|
| [`main-competition/`](main-competition/) | [Google - The Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent) | `submission.zip` — an ADK agent config, scored by bugs fixed | $100,000 |
| [`paper-track/`](paper-track/) | [Google - The Gemma 4 Developer Agent Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper) | A **Kaggle Writeup** research paper, max 3,000 words | $35,000 |

Both deadlines: **12 Nov 2026, 23:59 UTC** (the main track's agent deadline is 2 Dec 2026).

## Layout

```
K_G_G_4_DeveloperAgent/
├── main-competition/                 ← gemma-4-developer-agent
│   ├── README.md                     track brief, submission layout, dataset facts
│   ├── SUBMISSION.md                 which folder to zip, how to build and verify the archive
│   ├── SCHEMA-NOTES.md               which config fields are verified vs. assumed
│   ├── submission/                   the entry: agent.yaml, prompts, sub-agents, skills
│   ├── notebooks/run_agent_colab.ipynb  GPU driver: preflight, stage, eval, package
│   ├── tools/                        build_submission.py, prepare_corpus.py, make_agent_notebook.py
│   └── docs/                         reference: Overview, Data tab
│
├── paper-track/                      ← gemma-4-developer-agent-paper
│   ├── README.md                     cgr: what it is, how to run it, how the paper is built
│   ├── REQUIREMENTS.md               the paper track's rules, rubric, prizes, timeline
│   ├── docs/                         scraped reference: Overview, Rules
│   ├── paper/                        the submission: paper.md, template, IEEE LaTeX, PDF, checklist
│   ├── cgr.py                        the research tool (the paper's contribution)
│   ├── notebooks/cgr_pipeline.ipynb  public notebook, submitted as a Project Link
│   ├── tools/                        make_notebook.py, fill_results.py
│   ├── tests/make_synthetic.py       fixture corpus, so cgr can be validated without the 22 GB download
│   └── results.json                  real 129-task run; every number in the paper comes from it
│
├── references/gemma4-tech-report.pdf Gemma 4 Technical Report (arXiv:2607.02770v2) — background for both
├── LICENSE                           Apache 2.0
└── .gitignore
```

## Which track uses what

- **The paper track uses the main track's dataset.** `cgr` audits and repairs the released
  code-intelligence corpus (129 tasks, `graphs/`, `embeddings/`, `snapshots/`), so it consumes the
  gated 22.4 GB download that only main-competition participants can fetch. That is why the tool
  lives under `paper-track/` — it is the paper's contribution (Best New Resource) — even though the
  data it repairs belongs to the main competition.
- **The main track's submission is in `main-competition/submission/`.** A root `coder` agent, two
  sub-agents, and a `repo_navigation` skill whose `find_symbols.py` re-derives symbol and call
  search from the source with `ast`. It deliberately does **not** depend on `cgr` having been run:
  the released graph tools return nothing on the corpus as downloaded, so the submission parses the
  checkout instead. Zip the *contents* of `submission/` so `agent.yaml` lands at the archive root —
  [`main-competition/SUBMISSION.md`](main-competition/SUBMISSION.md) has the commands and a
  verification snippet. Read
  [`main-competition/SCHEMA-NOTES.md`](main-competition/SCHEMA-NOTES.md) before submitting — the
  config field names are inferred from the rules pages, not confirmed against
  `sample_submission/agent.yaml`.
- **The data is gated.** Sign in, accept the rules of `gemma-4-developer-agent`, then
  `kaggle competitions download -c gemma-4-developer-agent`. Nothing in the paper track is
  downloadable — it has no data, only the Writeup form.
- **The agent needs a GPU.** `gemma-4-31b-it-qat-w4a16-ct` is a 31B model; run it on Kaggle with an
  accelerator or on Colab. Corpus repair and the paper's measurements are CPU-only and run anywhere.
