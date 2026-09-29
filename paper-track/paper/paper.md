# cgr: Code Graph Repair for the Gemma 4 Developer Agent Corpus

### Restoring the Code-Intelligence Tools for 129 of 129 Tasks in a Release That Silently Disabled Them

**Category:** Best New Resource · **Track:** Google - The Gemma 4 Developer Agent Paper Track · **Words:** 2,593

---

## Abstract

The Gemma 4 Developer Agent competition ships a 22.4 GB code-intelligence corpus that participant agents
use through three tools: `get_code_neighbors`, `get_code_subgraph` and `search_similar_code`. We audited
that release and found two defects that degrade it without any error, warning, or log line. First, the
dataset describes its per-task graphs and embeddings as **hard links** to shared commit-level files, but
the distributed data keeps only one name per commit: all **129** task-named graph files and
129 task-named embedding files are absent, so **100.00%** of tasks have no graph or
embedding file under their own name. Second, the graph builder omits `async def`: **0
of 45,593** AST-extracted async functions are graph nodes. We present **cgr**, a CPU-only,
single-file tool whose only dependency is numpy. It (a) reconstructs every lost file from its commit group
and verifies it by SHA-256, and (b) re-indexes each graph with schema-compatible nodes for missing symbols.
Because each task's reference patch is known, cgr also supplies the missing evaluation for this corpus: it
maps each patch to the symbols it edits and measures whether those symbols are reachable in the graph the
agent sees. Applying cgr raises needed-symbol reachability from 90.08% to **100.00%**
and async reachability from 0.00% to **100.00%**, and reduces the tasks
fully blind to the asynchronous code their fix edits from 16 to 0. cgr is
released under Apache 2.0 as a notebook-embeddable resource with no LLM inference and no GPU.

## 1. Introduction

The competition provides 129 software-engineering tasks drawn from 4 Python
repositories. An agent must fix a defect in a checkout at a pinned commit, in the style of SWE-bench
(Jimenez et al., 2024). Each task ships with a code graph, an embedding index for semantic search, and a
reference patch. The graph and the index are how the benchmark's code-intelligence tools see the
repository. If they are silently incomplete, the benchmark measures the agent's ability to succeed with a
partially deleted toolbelt, unevenly across tasks. This paper documents two such failures, quantifies
their effect, and ships a repair.

**Defect 1 - lost task-named files.** The dataset description states that the 129 task-named
files `<instance_id>.json` are hard-linked to commit-named files `<repo>_<base_commit>.json`. In the data
as distributed on Kaggle, `graphs/` holds 127 files that form 127 commit groups, and every
task-named alias is gone: 129 graph and 129 embedding files are absent. A packaging
step that does not preserve hard links
produces exactly this. The content survives under the commit name, so nothing is lost, but
**129 of 129** tasks (100.00%) find no file under their own name.

**Defect 2 - missing asynchronous nodes.** Against an independent AST reference set, the graphs contain
0.00% of async functions (0 of 45,593), in library code (for
example `ahttpx._client.Client.request`) as well as in documentation examples. An extraction rule that matches
`FunctionDef` but not `AsyncFunctionDef` produces exactly this, and every tool that traverses the graph
inherits the omission.

**The evaluation gap.** The competition ships no measurement of either defect, and nothing connects the
per-task reference patches to the graphs. cgr fills this gap: it turns a packaging complaint into a
measurable, per-task quantity.

**Contributions.**

1. A reproducible audit of the released corpus that quantifies both defects, per task and per repository.
2. **cgr**, a 1,207-line, single-file tool that reconstructs every lost artifact from its commit
   group, verifies it by content hash, and re-indexes missing symbols into the released schema.
3. **A per-task reachability benchmark** built from the reference patches: the fraction of symbols a
   task's fix edits that the task's own graph contains, 90.08% before repair and
   100.00% after.
4. A public notebook that runs the whole pipeline on CPU and emits a single `results.json`, from which
   every number in this paper is generated.

## 2. Related Work

**Graphs of code for learning and agents.** Representing programs as graphs over syntactic and semantic
relations is well established (Allamanis et al., 2018). Repository-level code graphs are now a common
substrate for LLM software-engineering agents, used to navigate and localise code in RepoGraph (Ouyang et
al., 2025), CodexGraph (Liu et al., 2025) and LocAgent (Chen et al., 2025). These works build better
graphs. cgr asks a prior question: is a graph that has *already shipped* usable? It answers with the
task's reference patch as ground truth.

**Code search.** Embedding-based code retrieval, as benchmarked by CodeSearchNet (Husain et al., 2019), is
the model for `search_similar_code`. cgr recovers the embedding files (Defect 1) but does not re-embed,
because the released embedder is not part of the dataset (Section 6).

**Dataset documentation.** Datasheets (Gebru et al., 2021), Data Cards (Pushkarna et al., 2022) and the
survey of Paullada et al. (2021) argue that datasets need documented provenance and known failure modes.
cgr is an executable counterpart for a code-intelligence release, where the failure is a filesystem
feature that the distribution format silently drops.

**Prior reports.** Participants independently reported missing graph files and missing async nodes in
the competition Discussion (TODO: link the Discussion threads). Those reports come without a repair, a
per-task measurement, or a reusable tool. We reproduced both defects independently; the reports motivate
this work but are not its contribution.

## 3. Method

cgr is a single Python file whose only third-party dependency is numpy, used to read the `.npz`
embeddings. It exposes a library API and a CLI, and runs as a four-stage pipeline.

**Stage 1 - Census.** For each artifact kind (`graphs`, `embeddings`), cgr groups files by (repository,
base commit). Every task's own `<instance_id>` file is an expected member of its group. A member is
**lost** when it is absent or at most 100 bytes, the size below which the harness disables the code
tools. This stage is read-only and runs before anything touches the data.

**Stage 2 - Repair.** For each group, cgr takes the surviving member as the true content, copies it to
every lost member's path, and verifies each copy by SHA-256. Copying from the survivor rather than
re-cloning the repository costs O(bytes) and makes repair a pure function of the release. Groups with no
survivor are reported as unrecoverable, never fabricated.

**Stage 3 - Audit.** Independently of the release, cgr parses each task's source snapshot with Python's
`ast` module and enumerates a reference symbol set: module-level functions (`def` and `async def`),
classes, and the methods defined directly in those classes, excluding test files. It intersects that set
with the graph's node ids and reports coverage per kind, per repository and per task. Because the two sets
come from different sources, a disagreement points to the graph builder rather than the data.

**Stage 4 - Re-index.** For each graph, cgr adds a node for every reference symbol the audit found
missing. Each node carries the released schema's three fields: an `id` in the dataset's fully qualified
`module.Class.symbol` convention, so the graph tools resolve it unchanged, a matching `name`, and the
symbol's source `text` at the base commit. cgr does **not** synthesise vectors or guess edges (Section 6).

**The reachability benchmark.** Coverage is an intermediate quantity; what matters is whether the symbols
a task is *about* are reachable. For each task, cgr maps every removed or replaced line of the reference
patch, and every insertion point, onto the pre-patch snapshot the agent sees. The enclosing function,
method, or class (for edits in a class body outside any method) is a **needed symbol**; test files are
ignored. cgr reports:

* **needed-symbol reachability**: the fraction of needed symbols present as graph nodes. A symbol that is
  not a node can never be returned by any of the three tools, so this is a hard ceiling on what they can
  deliver. It is the primary number, broken down by kind;
* **affected tasks**: tasks with at least one unreachable needed symbol, and tasks that need async symbols
  but whose graph contains none of them (*fully blind to async*);
* **multi-hop connectivity**: of the present needed symbols, the fraction within two undirected edge hops
  of another node, which is what `get_code_neighbors` can reach by walking;
* **a self-retrieval sanity check**: recall@k when each target's own released vector is the query, so
  recall@1 must be about 1.0. This checks the loader; it is **not** a retrieval benchmark.

## 4. Experimental Setup

All experiments run on the competition corpus as mounted in a Kaggle Notebook (`gemma-4-developer-agent`,
129 tasks, 4 repositories: Textualize/rich, encode/httpx, fastapi/fastapi, psf/requests), using the notebook published with this
submission. cgr requires Python 3.9+ and numpy and runs on CPU; no model is loaded. The configuration is
the default: a 100-byte threshold and 2-hop connectivity. Every number in Section 5 is generated from the
`results.json` the notebook writes; none was typed by hand.

## 5. Results

**Defect 1.** `graphs/` holds 127 commit-named files in 127 groups, and all
129 task-named graph files and 129 task-named embedding files are absent, leaving
100.00% of tasks without their own files. Repair restores 258 files with
0 unrecoverable groups (i.e. every lost file can be rebuilt from the release itself). Afterwards 0 graph and
0 embedding files are lost.

**Defect 2.** Table 1 gives node coverage against the AST reference set before re-indexing.

| Repository | Tasks | Sync functions | Async functions | Classes |
|---|---|---|---|---|
| `fastapi` | 67 | 23,448/43,524 (53.87%) | 0/45,495 (0.00%) | 11,392/36,376 (31.32%) |
| `rich` | 48 | 43,585/43,585 (100.00%) | - | 9,110/9,110 (100.00%) |
| `requests` | 13 | 3,090/3,090 (100.00%) | - | 598/598 (100.00%) |
| `httpx` | 1 | 520/520 (100.00%) | 0/98 (0.00%) | 75/75 (100.00%) |

*Table 1. Graph node coverage by repository (found/total), before re-indexing.*

Async coverage is 0.00% wherever async code exists. The clearest case is
`httpx`: sync and class coverage is complete, yet 98 async functions are
missing, which isolates the omission to `async def`. Sync and class coverage is complete in
`rich`, `requests` and `httpx`. The one repository with gaps beyond async is `fastapi`, where many synchronous
functions and classes are also absent. We did not attribute that gap to a cause. The benchmark below shows
it lies mostly outside the code the tasks edit. Re-indexing adds 90,653 nodes across
68 tasks (45,593 async, 20,076 sync, 24,984
classes) and raises coverage to 100.00% for async functions, 100.00% for sync
functions and 100.00% for classes.

**The cost to tasks.** The reference patches of the 121 scored tasks edit 494 needed
symbols, of which 445 (90.08%) are nodes in the released graphs. By kind,
99.23% of synchronous and 96.72% of class needed symbols are
present, against 0/44
(0.00%) async ones. So the non-async gap barely touches the tasks, while the async
gap removes every async symbol a fix needs. 16 of 121 tasks
(13.22%) have at least one unreachable needed symbol. 16 tasks need an
async symbol, and 16 of them are fully blind to async. After cgr, needed-symbol
reachability is **100.00%** (494/494), async reachability is
100.00%, affected tasks fall from 16 to 0, and fully
blind tasks from 16 to 0.

**Edge structure.** Across 129 task graphs the release holds 461,336 nodes and
460,018 edges (0.997 per node), all of type `calls`. Of the present needed
symbols, 79.10% are within two hops of another node before repair and 71.26%
after, because re-indexed nodes carry no edges. The headline numbers measure node presence, but this
bounds how much of the repair `get_code_neighbors` can exploit, and synthesising `calls` edges is the
natural next step.

**Sanity check.** Querying the released embeddings with each target's own vector gives recall@1 =
1.00 and recall@10 = 1.00: the embedding reader is correct where data survived.

## 6. Limitations

* **cgr repairs; it does not reconstruct.** Repair copies the surviving member of a commit group; a group
  with no survivor cannot be helped and is reported.
* **No vectors or edges for new nodes.** Re-indexed nodes are found by `get_code_subgraph` and by name,
  but `search_similar_code` cannot surface them until a host supplies the embedder, which the dataset does
  not include, and `get_code_neighbors` cannot walk to them. The 100.00% async coverage is a
  *node* coverage figure.
* **The `fastapi` gap is unexplained.** We measured it and showed its small effect on tasks, but did
  not determine whether it reflects a deliberate scope choice by the graph builder or a second bug.
  Re-indexing fills it regardless, which a host may or may not want.
* **Needed-symbol extraction is heuristic.** It attributes each edited line to the enclosing top-level
  function, method or class; module-level edits are not attributed. It indicates where an agent must look,
  not a proof of what it must read.
* **The benchmark is oracle-based.** It uses the reference patch, which an agent does not have. It measures
  the corpus's fitness, not agent behaviour; we ran no agent.

## 7. Conclusion

As distributed, the Gemma 4 Developer Agent corpus has no task-named graph or embedding file for
100.00% of tasks and represents 0.00% of its async functions, silently
switching off or blinding the code-intelligence tools. cgr restores 258 files and closes the
async gap, raising needed-symbol reachability from 90.08% to 100.00% and cutting fully
blind tasks from 16 to 0, on CPU, in one file, with no inference. A
code-intelligence release should ship a coverage assertion alongside its artifacts: cgr's `audit` is under
a hundred lines and would have caught both defects before the competition. We release the tool, the
notebook and a machine-generated `results.json` so these claims can be re-derived rather than trusted.
This work is original and has not been published elsewhere.

## Project Links

* **Code (this notebook):** TODO: paste the public notebook URL here
* **Tool:** `cgr.py`, embedded in the notebook and available standalone in the accompanying repository
  (Apache 2.0).
* **Results:** `results.json`, written by the notebook's final cell.

## References

* Allamanis, M., Brockschmidt, M., and Khademi, M. Learning to Represent Programs with Graphs. ICLR, 2018.
* Chen, Z., et al. LocAgent: Graph-Guided LLM Agents for Code Localization. ACL, 2025.
* Gebru, T., et al. Datasheets for Datasets. Communications of the ACM 64(12), 2021.
* Husain, H., Wu, H.-H., Gazit, T., Allamanis, M., and Brockschmidt, M. CodeSearchNet Challenge:
  Evaluating the State of Semantic Code Search. arXiv:1909.09436, 2019.
* Jimenez, C. E., et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR, 2024.
* Liu, X., et al. CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph
  Databases. NAACL, 2025.
* Ouyang, S., et al. RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph.
  ICLR, 2025.
* Paullada, A., Raji, I. D., Bender, E. M., Denton, E., and Hanna, A. Data and its (dis)contents: A
  survey of dataset development and use in machine learning research. Patterns 2(11), 2021.
* Pushkarna, M., Zaldivar, A., and Kjartansson, O. Data Cards: Purposeful and Transparent Dataset
  Documentation for Responsible AI. FAccT, 2022.
* Elan Markowitz, Bryan Perozzi, Benedek Rózemberczki, Glenn Cameron, Hadi Hemmati, Yuchen Li, Michael
  Galkin, Majid Farhadi, Ryan Holbrook, and Ashley Oldacre. Google - The Gemma 4 Developer Agent Paper
  Track. https://www.kaggle.com/competitions/gemma-4-developer-agent-paper, 2026. Kaggle.
* Elan Markowitz, Bryan Perozzi, Benedek Rózemberczki, Glenn Cameron, Hadi Hemmati, Yuchen Li, Michael
  Galkin, Majid Farhadi, Ryan Holbrook, and Ashley Oldacre. Google - The Gemma 4 Developer Agent
  Competition. https://www.kaggle.com/competitions/gemma-4-developer-agent, 2026. Kaggle.
