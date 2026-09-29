---
name: repo_navigation
description: >-
  Find definitions, callers and callees for a Python symbol in the checkout at
  /workspace, using the ast module only. Use when a bug report names a function,
  class or traceback frame, or when you need to know who calls something or what
  something calls. Indexes async def, which the released code graph does not.
---

# Repository navigation

## Why this exists

The competition ships `get_code_neighbors`, `get_code_subgraph` and
`search_similar_code`, which read a prebuilt code graph and embedding index. In
the downloadable dataset the per-task `graphs/` and `embeddings/` files are
**absent for all 129 tasks** — they were hard links, and a ZIP cannot store a
hard link, so only one name per commit group survived. The three tools therefore
return nothing.

The graph builder also enumerates `def` and `class` but not `async def`, so
0 of 45,593 async functions in the corpus are nodes — and all four source repos
are async-heavy.

This skill ignores the release entirely and parses the checkout that is already
in `/workspace`. It is exact rather than semantic, and it sees `async def`.

## Usage

Run with `run_skill_script`, passing `args`:

```bash
# How much is in here at all, and does this script work?
run_skill_script(repo_navigation/scripts/find_symbols.py, args=["summary"])

# Where is it defined?
run_skill_script(repo_navigation/scripts/find_symbols.py,
                 args=["defs", "--query", "get"])

# What calls it, and what does it call?
run_skill_script(repo_navigation/scripts/find_symbols.py,
                 args=["calls", "--query", "get"])

# Everything at once, machine-readable — use this when you need to post-process
run_skill_script(repo_navigation/scripts/find_symbols.py,
                 args=["json", "--query", "get"])
```

Add `--root /workspace` if the working directory is not already the checkout. Add
`--show-body` to `defs` to print the source of each match.

`summary` takes no `--query` and is the fastest way to confirm the checkout is
unpacked and visible.

## Reading the output

- `defs` — `file:line`, then `kind` and the fully qualified `id`. A qualified id
  like `fastapi.routing.APIRoute.get_route` tells you the class as well as the
  method, which is often the point.
- `refs` — every site that *mentions* the name, whether it defines it or calls
  it. This is the "who is involved" view.
- `calls` — for a definition, the names it refers to from an outer scope:
  imports, module globals, other functions. Local variables and names that
  appear only in type annotations are filtered out, as are builtins, so the
  output is navigation targets rather than noise.
- `json` — all of the above with absolute file paths and line numbers, for
  further processing.

## Limits — read before you trust it

- **Name-based, not semantic.** It finds a symbol you can name. It will not
  find "the function that handles HEAD requests" unless you search for a string
  from the handler. For behaviour, `grep -rn` is still the right tool.
- **Static only.** References are syntactic. A call reached through
  `getattr`, a registry, or a dynamically built name is invisible. The same is
  true of the released graph, so this is not a downgrade.
- **No cross-file resolution.** `defs` reports a match on the name wherever it
  occurs. It does not confirm that the caller's import reaches that definition.
  Read the import when it matters.
- **Skips unparseable files.** Anything that fails `ast.parse` — unusual syntax
  for the running interpreter, or a file with a deliberate syntax error — is
  silently absent from the index. If `summary` shows far fewer symbols than the
  repository should have, that is why.
- **Python only.** These four repos are Python, so this is complete coverage
  here, but it would not be for a mixed tree.

## When to fall back to `run_command`

- Searching for a string, not a symbol: `grep -rn --include='*.py' "pattern" /workspace`
- When a line was introduced: `git log -S "pattern" --oneline`
- Who last touched a line: `git blame -L <start>,<end> <file>`
- Why the code is that way: `git log -p -- <file>`

`git log -S` is underused and often answers "is this a regression, and when was
it introduced" faster than any static analysis.
