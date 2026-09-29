# Submission checklist

Paper Track: **Google Gemma 4 Developer Agent** - Writeup / Best New Resource.
Deadline: **12 Nov 2026, 23:59 UTC.**

Nothing here is done until the boxes are ticked against the *real* corpus.

## Blocking - cannot be done locally

- [ ] Accept the main competition's rules (required to download `gemma-4-developer-agent`).
- [ ] Get Kaggle API credentials (`~/.kaggle/kaggle.json`).
- [ ] Run `notebooks/cgr_pipeline.ipynb` on the **real** corpus. Kaggle: attach the competition data
      and Run All (the read-only input is staged automatically). Colab: needs `kaggle.json` and ~50 GB.
- [ ] Download the resulting `results.json` from the run.

## Then, locally

- [ ] `python3 tools/fill_results.py <real results.json> --notebook-url <public notebook URL>`
      exits 0 and prints no `WARNING`.
- [ ] `grep -n 'TODO\|{{\|DRAFT' paper/paper.md` returns nothing.
- [ ] Open `paper/paper.md` and read the numbers. Confirm each is plausible for the real corpus and that
      none of them are still the fixture values. The synthetic fixture produced these signatures:
      129 tasks, 4 repos (fastapi, rich, requests, httpx), 50.39% dead files, 0% async coverage,
      18 fully-blind tasks, 1 edge type (`calls`), 0 module nodes, instance ids `<repo>_1000`..`<repo>_1128`.
      **The real corpus has real instance ids and repos; if you see the ones above, the run used the fixture.**
- [ ] Word count is under 3,000 (the script prints it).
- [ ] Open `HARNESS_README.md` on the competition Data tab and confirm the code tools are gated on
      graph/embedding files larger than 100 bytes - the paper states this as fact.
- [ ] Re-read Section 5 against the raw `results.json`. Every claim must trace to a field.
- [ ] Re-read Section 6 and make sure the limitations still describe what the real run showed -
      especially the vector-backfill and edge-sparsity caveats, which may change if the real graphs
      are denser than the fixture's.

## Verify the research is still novel

- [ ] Re-scan the Paper Track **Discussion** and **Writeup** tabs for new posts since the audit.
- [ ] Re-scan main-competition **Discussion** for a host response about the 0-byte files or the async
      nodes. If the host shipped a fix, the paper must say so and re-baseline against it.
- [ ] Confirm nobody has published this repair plus this reachability metric. If they have, narrow the
      claim to what is still new and say plainly what is prior.

## Publish the resource

- [ ] Push the notebook to a **public** Kaggle Notebook (the competition requires a public project link).
- [ ] Record the notebook URL and pass it as `--notebook-url`.
- [ ] Publish `cgr.py` under Apache 2.0 in a public repo, and put that link in the paper's
      Project Links.
- [x] `LICENSE` (Apache 2.0) is in the repo root.
- [ ] Confirm the notebook runs from a clean kernel with no local files, since that is how a judge will
      run it.

## Writeup requirements

- [ ] Title and subtitle present.
- [ ] Abstract present.
- [ ] Methods and experiments both present (this paper has a Method section and a Results section).
- [ ] Related work present with real citations - open each entry in the References section and confirm
      authors / venue / year: Allamanis 2018, Chen 2025 (LocAgent), Gebru 2021, Husain 2019,
      Jimenez 2024, Liu 2025 (CodexGraph), Ouyang 2025 (RepoGraph), Paullada 2021, Pushkarna 2022.
- [ ] Replace `TODO: link the Discussion threads` in Section 2 with the actual Discussion post URLs.
- [ ] Paper Track and main competition citations present, verbatim (including "Rózemberczki").
- [ ] Stated as original and not previously published.
- [ ] Under 3,000 words.
- [ ] Team size is 1 and within the cap (max 5).

## Honesty gate

- [ ] The paper does not claim to have run the main competition's agent. It audits the corpus only.
- [ ] The reachability benchmark is described as oracle-based (it uses reference patches) and not as an
      agent-behaviour result.
- [ ] The self-retrieval sanity check is labelled an upper bound by construction, not a retrieval
      benchmark.
- [ ] Any claim inherited from the Discussion thread is attributed to participants, not presented as
      this paper's own discovery.
- [ ] The two defects are reproduced independently, not cited from the forum.

## Final

- [ ] Read the rendered `paper/paper.md` top to bottom once as a reviewer would.
- [ ] Submit.
