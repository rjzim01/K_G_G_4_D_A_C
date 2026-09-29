\documentclass[conference,a4paper]{IEEEtran}
\IEEEoverridecommandlockouts
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage[hyphens]{url}
\usepackage{tikz}
\usetikzlibrary{shapes.geometric, arrows.meta, positioning, fit, backgrounds}
\newcommand{\todo}[1]{\textcolor{red}{\textbf{TODO:} #1}}
\begin{document}

\title{Code Graph Repair: Restoring Silently Disabled Code-Intelligence Tools in the Gemma~4 Developer Agent Corpus}

% Uncomment and fill in if the venue asks for authors:
% \author{\IEEEauthorblockN{Your Name}
% \IEEEauthorblockA{\textit{Affiliation} \\
% City, Country \\
% email@example.com}}

\maketitle

\begin{abstract}
The Gemma 4 Developer Agent competition ships a 22.4\,GB code-intelligence corpus that participant agents use through three tools: \texttt{get\_code\_neighbors}, \texttt{get\_code\_subgraph} and \texttt{search\_similar\_code}. We audited that release and found two defects that degrade it without any error, warning, or log line. First, the dataset describes its per-task graphs and embeddings as hard links to shared commit-level files, but the distributed data keeps only one name per commit: all 129 task-named graph files and 129 task-named embedding files are absent, so 100\% of tasks have no graph or embedding file under their own name. Second, the graph builder omits \texttt{async def}: 0 of 45,593 AST-extracted async functions are graph nodes. We present \emph{cgr}, a CPU-only, single-file tool whose only dependency is NumPy. It reconstructs every lost file from its commit group and verifies it by SHA-256, and re-indexes each graph with schema-compatible nodes for missing symbols. Because each task's reference patch is known, cgr also supplies the missing evaluation for this corpus: it maps each patch to the symbols it edits and measures whether those symbols are reachable in the graph the agent sees. Applying cgr raises needed-symbol reachability from 90.08\% to 100\% and async reachability from 0\% to 100\%, and reduces the tasks fully blind to the asynchronous code their fix edits from 16 to 0. cgr is released under Apache 2.0 as a notebook-embeddable resource that needs no LLM inference and no GPU.
\end{abstract}

\begin{IEEEkeywords}
Code Graphs, Software Engineering Agents, Benchmark Integrity, Dataset Repair, Code Retrieval, Reproducibility
\end{IEEEkeywords}

\section{Introduction}

The Gemma 4 Developer Agent competition \cite{kaggle2026gemma4} provides 129 software-engineering tasks drawn from four Python repositories. An agent must fix a defect in a checkout at a pinned commit, in the style of SWE-bench \cite{jimenez2024swebench}. Each task ships with a code graph, an embedding index for semantic search, and a reference patch. The graph and the index are how the benchmark's code-intelligence tools see the repository. If they are silently incomplete, the benchmark measures the agent's ability to succeed with a partially deleted toolbelt, unevenly across tasks. This paper documents two such failures, quantifies their effect, and ships a repair.

\textbf{Defect 1 -- lost task-named files.} The dataset description states that the 129 task-named files \texttt{<instance\_id>.json} are hard-linked to commit-named files \texttt{<repo>\_<base\_commit>.json}. In the data as distributed on Kaggle, \texttt{graphs/} holds 127 files that form 127 commit groups, and every task-named alias is gone: 129 graph and 129 embedding files are absent. A packaging step that does not preserve hard links produces exactly this. The content survives under the commit name, so nothing is lost, but all 129 tasks find no file under their own name.

\textbf{Defect 2 -- missing asynchronous nodes.} Against an independent abstract syntax tree (AST) reference set, the graphs contain 0 of 45,593 async functions, in library code (for example \texttt{ahttpx.\allowbreak\_client.\allowbreak Client.\allowbreak request}) as well as in documentation examples. An extraction rule that matches \texttt{FunctionDef} but not \texttt{AsyncFunctionDef} produces exactly this, and every tool that traverses the graph inherits the omission.

\textbf{The evaluation gap.} The competition ships no measurement of either defect, and nothing connects the per-task reference patches to the graphs. cgr fills this gap: it turns a packaging complaint into a measurable, per-task quantity.

\textbf{Contributions.} (1) A reproducible audit of the released corpus that quantifies both defects, per task and per repository; (2) cgr, a 1,207-line, single-file tool that reconstructs every lost artifact from its commit group, verifies it by content hash, and re-indexes missing symbols into the released schema; (3) a per-task reachability benchmark built from the reference patches, which measures the fraction of symbols a task's fix edits that the task's own graph contains: 90.08\% before repair and 100\% after; and (4) a public notebook that runs the whole pipeline on CPU and emits a single \texttt{results.json}, from which every number in this paper is generated.

\section{Related Work}

Representing programs as graphs over syntactic and semantic relations is well established \cite{allamanis2018graphs}. Repository-level code graphs are now a common substrate for large language model (LLM) software-engineering agents, used to navigate and localise code in RepoGraph \cite{ouyang2025repograph}, CodexGraph \cite{liu2025codexgraph} and LocAgent \cite{chen2025locagent}. These works build better graphs. cgr asks a prior question: is a graph that has \emph{already shipped} usable? It answers with each task's reference patch as ground truth.

Embedding-based code retrieval, as benchmarked by CodeSearchNet \cite{husain2019codesearchnet}, is the model for \texttt{search\_similar\_code}. cgr recovers the embedding files (Defect 1) but does not re-embed, because the released embedder is not part of the dataset (Section~\ref{sec:limitations}).

Datasheets \cite{gebru2021datasheets}, Data Cards \cite{pushkarna2022datacards} and the survey of Paullada et al.~\cite{paullada2021data} argue that datasets need documented provenance and known failure modes. cgr is an executable counterpart for a code-intelligence release, where the failure is a filesystem feature that the distribution format silently drops.

Participants independently reported missing graph files and missing async nodes in the competition Discussion \todo{link the Discussion threads}. Those reports come without a repair, a per-task measurement, or a reusable tool. We reproduced both defects independently; the reports motivate this work but are not its contribution.

\section{Method}

cgr is a single Python file whose only third-party dependency is NumPy, used to read the \texttt{.npz} embeddings. It exposes a library API and a command-line interface, and runs as the four-stage pipeline shown in Fig.~\ref{fig:pipeline}.

\begin{figure}[htbp]
\centering
\resizebox{\columnwidth}{!}{%
\begin{tikzpicture}[
    node distance=0.5cm and 0.35cm,
    box/.style={rectangle, draw, rounded corners, minimum height=0.8cm, minimum width=1.5cm, align=center, font=\footnotesize},
    mainbox/.style={box, fill=blue!15},
    databox/.style={box, fill=green!15},
    outputbox/.style={box, fill=orange!15},
    arrow/.style={-{Stealth[scale=0.7]}, thick}
]
\node[databox] (in) {Released\\corpus};
\node[mainbox, right=of in] (cen) {1. Census\\(read-only)};
\node[mainbox, right=of cen] (rep) {2. Repair\\(SHA-256)};
\node[mainbox, right=of rep] (aud) {3. Audit\\(AST)};
\node[mainbox, right=of aud] (rx) {4. Re-index};
\node[databox, below=of aud] (snap) {Source\\snapshots};
\node[databox, below=of rep] (patch) {Reference\\patches};
\node[outputbox, below=of rx] (out) {Reachability\\benchmark +\\\texttt{results.json}};
\draw[arrow] (in) -- (cen);
\draw[arrow] (cen) -- (rep);
\draw[arrow] (rep) -- (aud);
\draw[arrow] (aud) -- (rx);
\draw[arrow] (snap) -- (aud);
\draw[arrow] (rx) -- (out);
\draw[arrow] (patch) -- (snap);
\end{tikzpicture}%
}
\caption{The cgr pipeline. Census and repair restore the lost per-task files; audit and re-index restore the missing symbols; the reachability benchmark maps each reference patch onto the pre-patch snapshot and is run before and after repair.}
\label{fig:pipeline}
\end{figure}

\subsection{Census}

For each artifact kind (\texttt{graphs}, \texttt{embeddings}), cgr groups files by (repository, base commit). Every task's own \texttt{<instance\_id>} file is an expected member of its group. A member is \emph{lost} when it is absent or at most 100 bytes, the size below which the harness disables the code tools. This stage is read-only and runs before anything touches the data.

\subsection{Repair}

For each group, cgr takes the surviving member as the true content, copies it to every lost member's path, and verifies each copy by SHA-256. Copying from the survivor rather than re-cloning the repository costs $O(\text{bytes})$ and makes repair a pure function of the release. Groups with no survivor are reported as unrecoverable, never fabricated.

\subsection{Audit}

Independently of the release, cgr parses each task's source snapshot with Python's \texttt{ast} module and enumerates a reference symbol set $R$: module-level functions (\texttt{def} and \texttt{async def}), classes, and the methods defined directly in those classes, excluding test files. With $N$ the set of graph node identifiers, the coverage of symbol kind $k$ is
\begin{equation}
\text{cov}_k = \frac{|R_k \cap N|}{|R_k|},
\end{equation}
reported per kind, per repository and per task. Because $R$ and $N$ come from different sources, a disagreement points to the graph builder rather than the data.

\subsection{Re-index}

For each graph, cgr adds a node for every symbol in $R \setminus N$. Each node carries the released schema's three fields: an \texttt{id} in the dataset's fully qualified \texttt{module.Class.symbol} convention, so the graph tools resolve it unchanged, a matching \texttt{name}, and the symbol's source \texttt{text} at the base commit. cgr does not synthesise vectors or guess edges (Section~\ref{sec:limitations}).

\subsection{Reachability Benchmark}

Coverage is an intermediate quantity; what matters is whether the symbols a task is \emph{about} are reachable. For each task, cgr maps every removed or replaced line of the reference patch, and every insertion point, onto the pre-patch snapshot the agent sees. The enclosing function, method, or class (for edits in a class body outside any method) is a \emph{needed symbol}; test files are ignored. With $S$ the set of needed symbols over all scored tasks, needed-symbol reachability is
\begin{equation}
\text{reach} = \frac{|S \cap N|}{|S|}.
\end{equation}
A symbol that is not a node can never be returned by any of the three tools, so this is a hard ceiling on what they can deliver. cgr also reports \emph{affected tasks} (at least one unreachable needed symbol), tasks \emph{fully blind to async} (they need async symbols and their graph contains none of them), \emph{multi-hop connectivity} (the fraction of present needed symbols within two undirected edge hops of another node, which is what \texttt{get\_code\_neighbors} can reach by walking), and a \emph{self-retrieval sanity check} (recall@$k$ when each target's own released vector is the query, which checks the embedding loader and is not a retrieval benchmark).

\section{Experimental Setup}

All experiments run on the competition corpus as mounted in a Kaggle Notebook (\texttt{gemma-4-developer-agent}: 129 tasks from \texttt{Textualize/rich}, \texttt{encode/httpx}, \texttt{fastapi/fastapi} and \texttt{psf/requests}), using the notebook published with this submission. cgr requires Python 3.9+ and NumPy and runs on CPU; no model is loaded. The configuration is the default: a 100-byte threshold and 2-hop connectivity. Every number in Section~\ref{sec:results} is generated from the \texttt{results.json} the notebook writes; none was typed by hand.

\section{Results}
\label{sec:results}

Table~\ref{tab:summary} summarises the effect of cgr on the corpus.

\begin{table}[htbp]
\caption{Effect of cgr on the released corpus}
\label{tab:summary}
\centering
\begin{tabular}{lrr}
\toprule
\textbf{Metric} & \textbf{Before} & \textbf{After} \\
\midrule
Tasks without their own graph file & 129 & 0 \\
Async node coverage & 0.00\% & 100.00\% \\
Needed-symbol reachability & 90.08\% & 100.00\% \\
\quad async needed symbols & 0/44 & 44/44 \\
Tasks with an unreachable needed symbol & 16 & 0 \\
Tasks fully blind to async & 16 & 0 \\
Needed symbols within 2 hops & 79.10\% & 71.26\% \\
\bottomrule
\end{tabular}
\end{table}

\subsection{Defect 1: Lost Task-Named Files}

\texttt{graphs/} holds 127 commit-named files in 127 groups, and all 129 task-named graph files and 129 task-named embedding files are absent, leaving 100\% of tasks without their own files. Repair restores 258 files with 0 unrecoverable groups, i.e.\ every lost file can be rebuilt from the release itself. Afterwards no graph or embedding file is lost.

\subsection{Defect 2: Missing Async Nodes}

Table~\ref{tab:coverage} gives node coverage against the AST reference set before re-indexing.

\begin{table*}[htbp]
\caption{Graph node coverage by repository (found/total), before re-indexing}
\label{tab:coverage}
\centering
\begin{tabular}{lrlll}
\toprule
\textbf{Repository} & \textbf{Tasks} & \textbf{Sync functions} & \textbf{Async functions} & \textbf{Classes} \\
\midrule
\texttt{fastapi} & 67 & 23,448/43,524 (53.87\%) & 0/45,495 (0.00\%) & 11,392/36,376 (31.32\%) \\
\texttt{rich} & 48 & 43,585/43,585 (100.00\%) & -- & 9,110/9,110 (100.00\%) \\
\texttt{requests} & 13 & 3,090/3,090 (100.00\%) & -- & 598/598 (100.00\%) \\
\texttt{httpx} & 1 & 520/520 (100.00\%) & 0/98 (0.00\%) & 75/75 (100.00\%) \\
\bottomrule
\end{tabular}
\end{table*}

Async coverage is 0\% wherever async code exists. The clearest case is \texttt{httpx}: sync and class coverage is complete, yet all 98 async functions are missing, which isolates the omission to \texttt{async def}. Sync and class coverage is also complete in \texttt{rich} and \texttt{requests}. The one repository with gaps beyond async is \texttt{fastapi}, where many synchronous functions and classes are also absent. We did not attribute that gap to a cause; the benchmark below shows that it lies mostly outside the code the tasks edit. Re-indexing adds 90,653 nodes across 68 tasks (45,593 async, 20,076 sync and 24,984 classes) and raises coverage to 100\% for all three kinds.

\subsection{The Cost to Tasks}

The reference patches of the 121 scored tasks (8 tasks edit no attributable symbol) edit 494 needed symbols, of which 445 (90.08\%) are nodes in the released graphs. By kind, 99.23\% of synchronous and 96.72\% of class needed symbols are present, against 0 of 44 async ones. The non-async gap therefore barely touches the tasks, while the async gap removes every async symbol a fix needs. Of the 121 tasks, 16 (13.22\%) have at least one unreachable needed symbol; these are exactly the 16 tasks that need an async symbol, and all 16 are fully blind to async. After cgr, needed-symbol reachability is 100\% (494/494), and affected and fully blind tasks both fall from 16 to 0.

\subsection{Edge Structure}

Across the 129 task graphs the release holds 461,336 nodes and 460,018 edges (0.997 per node), all of type \texttt{calls}. Of the present needed symbols, 79.10\% are within two hops of another node before repair and 71.26\% after, because re-indexed nodes carry no edges. The headline numbers measure node presence, but this bounds how much of the repair \texttt{get\_code\_neighbors} can exploit, and synthesising \texttt{calls} edges is the natural next step.

\subsection{Sanity Check}

Querying the released embeddings with each target's own vector gives recall@1 = recall@10 = 1.00, so the embedding reader is correct where the data survived.

\section{Limitations}
\label{sec:limitations}

\textbf{cgr repairs; it does not reconstruct.} Repair copies the surviving member of a commit group; a group with no survivor cannot be helped and is reported.

\textbf{No vectors or edges for new nodes.} Re-indexed nodes are found by \texttt{get\_code\_subgraph} and by name, but \texttt{search\_similar\_code} cannot surface them until a host supplies the embedder, which the dataset does not include, and \texttt{get\_code\_neighbors} cannot walk to them. The 100\% async coverage is a \emph{node} coverage figure.

\textbf{The \texttt{fastapi} gap is unexplained.} We measured it and showed its small effect on tasks, but did not determine whether it reflects a deliberate scope choice by the graph builder or a second bug. Re-indexing fills it regardless, which a host may or may not want.

\textbf{Needed-symbol extraction is heuristic.} It attributes each edited line to the enclosing top-level function, method or class; module-level edits are not attributed. It indicates where an agent must look, not what it must read.

\textbf{The benchmark is oracle-based.} It uses the reference patch, which an agent does not have. It measures the corpus's fitness, not agent behaviour; we ran no agent.

\section{Conclusion}

As distributed, the Gemma 4 Developer Agent corpus has no task-named graph or embedding file for any of its 129 tasks and represents none of its 45,593 async functions, silently switching off or blinding the code-intelligence tools. cgr restores 258 files and closes the async gap, raising needed-symbol reachability from 90.08\% to 100\% and cutting fully blind tasks from 16 to 0, on CPU, in one file, with no inference. A code-intelligence release should ship a coverage assertion alongside its artifacts: cgr's audit is under a hundred lines and would have caught both defects before the competition. We release the tool, the notebook and a machine-generated \texttt{results.json} so that these claims can be re-derived rather than trusted. This work is original and has not been published elsewhere.

\section*{Data and Code Availability}

This paper is a submission to the Google -- The Gemma 4 Developer Agent Paper Track \cite{kaggle2026paper} (Best New Resource category). The notebook that produces every number is public at \todo{paste the public notebook URL}. \texttt{cgr.py} is embedded in that notebook and available standalone in the accompanying repository under the Apache 2.0 licence, together with \texttt{results.json}.

\begin{thebibliography}{00}
\bibitem{kaggle2026gemma4} E. Markowitz, B. Perozzi, B. R\'{o}zemberczki, G. Cameron, H. Hemmati, Y. Li, M. Galkin, M. Farhadi, R. Holbrook, and A. Oldacre, ``Google -- The Gemma 4 Developer Agent Competition,'' Kaggle, 2026. [Online]. Available: \url{https://www.kaggle.com/competitions/gemma-4-developer-agent}
\bibitem{kaggle2026paper} E. Markowitz, B. Perozzi, B. R\'{o}zemberczki, G. Cameron, H. Hemmati, Y. Li, M. Galkin, M. Farhadi, R. Holbrook, and A. Oldacre, ``Google -- The Gemma 4 Developer Agent Paper Track,'' Kaggle, 2026. [Online]. Available: \url{https://www.kaggle.com/competitions/gemma-4-developer-agent-paper}
\bibitem{jimenez2024swebench} C. E. Jimenez \textit{et al.}, ``SWE-bench: Can language models resolve real-world GitHub issues?'' in \textit{Proc. ICLR}, 2024.
\bibitem{allamanis2018graphs} M. Allamanis, M. Brockschmidt, and M. Khademi, ``Learning to represent programs with graphs,'' in \textit{Proc. ICLR}, 2018.
\bibitem{ouyang2025repograph} S. Ouyang \textit{et al.}, ``RepoGraph: Enhancing AI software engineering with repository-level code graph,'' in \textit{Proc. ICLR}, 2025.
\bibitem{liu2025codexgraph} X. Liu \textit{et al.}, ``CodexGraph: Bridging large language models and code repositories via code graph databases,'' in \textit{Proc. NAACL}, 2025.
\bibitem{chen2025locagent} Z. Chen \textit{et al.}, ``LocAgent: Graph-guided LLM agents for code localization,'' in \textit{Proc. ACL}, 2025.
\bibitem{husain2019codesearchnet} H. Husain, H.-H. Wu, T. Gazit, M. Allamanis, and M. Brockschmidt, ``CodeSearchNet challenge: Evaluating the state of semantic code search,'' arXiv:1909.09436, 2019.
\bibitem{gebru2021datasheets} T. Gebru \textit{et al.}, ``Datasheets for datasets,'' \textit{Communications of the ACM}, vol. 64, no. 12, pp. 86--92, 2021.
\bibitem{pushkarna2022datacards} M. Pushkarna, A. Zaldivar, and O. Kjartansson, ``Data Cards: Purposeful and transparent dataset documentation for responsible AI,'' in \textit{Proc. ACM FAccT}, 2022.
\bibitem{paullada2021data} A. Paullada, I. D. Raji, E. M. Bender, E. Denton, and A. Hanna, ``Data and its (dis)contents: A survey of dataset development and use in machine learning research,'' \textit{Patterns}, vol. 2, no. 11, 2021.
\end{thebibliography}

\end{document}
