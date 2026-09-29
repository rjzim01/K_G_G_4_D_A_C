#!/usr/bin/env python3
"""Symbol and reference search over a Python checkout, using only the standard library.

This exists because the three code-intelligence harness tools
(``get_code_neighbors``, ``get_code_subgraph``, ``search_similar_code``) read
the released ``graphs/`` and ``embeddings/`` index, and in the downloadable ZIP
those per-task files are absent -- the per-task names were hard links to shared
commit-level files, and a ZIP cannot store a hard link, so only one name per
commit group survived. The result is that the tools silently return nothing.
This script does not read the release at all: it parses the checkout in
``/workspace`` directly, so it works whether or not the corpus has been
repaired. See ``../SKILL.md``.

Two properties worth knowing:

* ``async def`` is indexed. The released graph builder enumerates ``def`` and
  ``class`` but not ``async def``, so 0 of 45,593 async functions in the corpus
  are nodes. All four source repos are async-heavy, so this is most of what the
  missing index was hiding.
* It is exact, not semantic. ``search_similar_code`` finds *similar* code by
  embedding; this finds *identical names and real static references*. For
  locating a defect in a known repo that is the more useful of the two.

Usage::

    find_symbols.py defs  --query name_substring   # where is it defined
    find_symbols.py refs  --query name_substring   # who calls/imports it
    find_symbols.py calls --query name_substring   # what does it call
    find_symbols.py json  --query name_substring   # machine-readable, all of the above

Run it with no arguments to index the checkout and print a summary, which is a
cheap way to confirm it can see the tree at all.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_ROOTS = (".",)
_BUILTINS = frozenset(dir(builtins))
SKIP_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
        ".ruff_cache", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
        "build", "dist", ".eggs", "site-packages", ".hypothesis",
    }
)


def _dotted(node: ast.AST) -> str:
    """Render a dotted attribute/name chain, e.g. ``a.b.c``; '' otherwise."""
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    else:
        return ""
    return ".".join(reversed(parts))


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # very old Python, or an odd node
        return "<expr>"


class Symbol:
    """One definition site, and the reference edges leaving it."""

    __slots__ = ("id", "name", "kind", "file", "line", "end_line", "text", "calls", "bases")

    def __init__(self, sid, name, kind, file, line, end_line, text, calls, bases):
        self.id = sid
        self.name = name
        self.kind = kind
        self.file = file
        self.line = line
        self.end_line = end_line
        self.text = text
        self.calls = calls
        self.bases = bases

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "file": self.file,
            "line": self.line,
            "end_line": self.end_line,
            "calls": self.calls,
            "bases": self.bases,
        }


class NodeVisitor(ast.NodeVisitor):
    """Collect module/class/function symbols, including ``async def``."""

    def __init__(self, rel_path: str, source: str, symbols: List[Symbol]) -> None:
        self.rel = rel_path
        self.lines = source.splitlines()
        self.symbols = symbols
        self.stack: List[str] = []

    # -- helpers ---------------------------------------------------------
    def _qualified(self, name: str) -> str:
        return ".".join(self.stack + [name])

    def _span_text(self, node: ast.AST) -> str:
        try:
            start = node.lineno - 1
            return "\n".join(self.lines[start : node.end_lineno])
        except Exception:
            return ""

    def _references(self, node: ast.AST) -> List[str]:
        """Names this definition refers to that live in an *outer* scope.

        Local variables, loop targets and names appearing only inside a type
        annotation are excluded -- they are not navigation targets and they
        swamp the output. What is left is imports, module globals and calls to
        other functions, which is what a get_code_neighbors substitute owes you.
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return []

        bound: set = set()

        class Bound(ast.NodeVisitor):
            def _bind(inner, t: ast.AST) -> None:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        bound.add(n.id)

            def visit_arg(inner, a: ast.arg) -> None:
                bound.add(a.arg)

            def visit_Assign(inner, a: ast.Assign) -> None:
                for t in a.targets:
                    inner._bind(t)
                inner.generic_visit(a)

            def visit_AnnAssign(inner, a: ast.AnnAssign) -> None:
                inner._bind(a.target)
                if a.value is not None:
                    inner.visit(a.value)

            def visit_AugAssign(inner, a: ast.AugAssign) -> None:
                inner._bind(a.target)
                inner.generic_visit(a)

            def visit_For(inner, f: ast.For) -> None:
                inner._bind(f.target)
                inner.generic_visit(f)

            visit_AsyncFor = visit_For

            def visit_comprehension(inner, c: ast.comprehension) -> None:
                inner._bind(c.target)
                inner.generic_visit(c)

            def visit_withitem(inner, w: ast.withitem) -> None:
                if w.optional_vars is not None:
                    inner._bind(w.optional_vars)
                inner.generic_visit(w)

            def visit_ExceptHandler(inner, h: ast.ExceptHandler) -> None:
                if h.name:
                    bound.add(h.name)
                inner.generic_visit(h)

            def visit_NamedExpr(inner, nw: ast.NamedExpr) -> None:
                inner._bind(nw.target)
                inner.generic_visit(nw)

            def visit_FunctionDef(inner, f: ast.FunctionDef) -> None:
                bound.add(f.name)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(inner, c: ast.ClassDef) -> None:
                bound.add(c.name)

        found: List[str] = []

        class Refs(ast.NodeVisitor):
            """Collect loads only, and never descend into a type annotation."""

            def _body(inner, body) -> None:
                for stmt in body:
                    inner.visit(stmt)

            def visit_Call(inner, c: ast.Call) -> None:
                d = _dotted(c.func)
                if d:
                    found.append(d)
                for a in c.args:
                    inner.visit(a)
                for k in c.keywords:
                    inner.visit(k.value)

            def visit_Attribute(inner, a: ast.Attribute) -> None:
                d = _dotted(a)
                if d:
                    found.append(d)
                inner.generic_visit(a)

            def visit_Name(inner, n: ast.Name) -> None:
                if isinstance(n.ctx, ast.Load):
                    found.append(n.id)

            def visit_AnnAssign(inner, a: ast.AnnAssign) -> None:
                if a.value is not None:
                    inner.visit(a.value)

            def visit_arg(inner, a: ast.arg) -> None:
                if a.annotation is None:
                    found.append(a.arg)

            def _skip_annotations(inner, fn) -> None:
                for d in fn.decorator_list:
                    inner.visit(d)
                for default in fn.args.defaults:
                    inner.visit(default)
                for d in fn.args.kw_defaults:
                    if d is not None:
                        inner.visit(d)
                inner._body(fn.body)

            def visit_FunctionDef(inner, f: ast.FunctionDef) -> None:
                inner._skip_annotations(f)
                bound.add(f.name)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(inner, c: ast.ClassDef) -> None:
                for b in c.bases:
                    inner.visit(b)
                for k in c.keywords:
                    inner.visit(k.value)
                inner._body(c.body)
                bound.add(c.name)

        try:
            Bound().generic_visit(node)
            Refs()._body(node.body)
        except Exception:
            return found

        out: List[str] = []
        seen = set()
        for r in found:
            leaf = r.rsplit(".", 1)[-1]
            if r in seen or leaf in bound or r in ("self", "cls", "super"):
                continue
            # a builtin is never a navigation target
            if leaf in _BUILTINS and "." not in r:
                continue
            seen.add(r)
            out.append(r)
        return out

    # -- visitors --------------------------------------------------------
    def _add(self, node: ast.AST, name: str, kind: str) -> None:
        calls = [r for r in self._references(node) if r != name]
        bases: List[str] = []
        if isinstance(node, ast.ClassDef):
            bases = [_dotted(b) for b in node.bases if _dotted(b)]

        self.symbols.append(
            Symbol(
                self._qualified(name),
                name,
                kind,
                self.rel,
                getattr(node, "lineno", 0),
                getattr(node, "end_lineno", 0) or 0,
                self._span_text(node),
                calls,
                bases,
            )
        )
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Module(self, node: ast.Module) -> None:
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add(child, child.name, "async def" if isinstance(child, ast.AsyncFunctionDef) else "def")
            elif isinstance(child, ast.ClassDef):
                self._add(child, child.name, "class")
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                continue
            else:
                self.generic_visit(child)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node, node.name, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node, node.name, "def")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add(node, node.name, "async def")


def iter_python_files(roots: Sequence[str]) -> Iterable[str]:
    seen = set()
    for root in roots:
        if os.path.isfile(root) and root.endswith(".py"):
            if root not in seen:
                seen.add(root)
                yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".egg"))
            for fn in sorted(filenames):
                if fn.endswith(".py"):
                    p = os.path.join(dirpath, fn)
                    if p not in seen:
                        seen.add(p)
                        yield p


def index(roots: Sequence[str]) -> List[Symbol]:
    symbols: List[Symbol] = []
    for path in iter_python_files(roots):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=path)
        except (SyntaxError, ValueError, RecursionError, OSError):
            continue
        NodeVisitor(path, source, symbols).visit(tree)
    return symbols


def _matches(sym: Symbol, query: str) -> bool:
    q = query.lower()
    return q in sym.name.lower() or q in sym.id.lower()


def cmd_defs(symbols: List[Symbol], args) -> int:
    hits = [s for s in symbols if _matches(s, args.query)]
    if not hits:
        print(f"no definition matching {args.query!r}")
        return 1
    for s in hits:
        print(f"{s.file}:{s.line}  {s.kind} {s.id}")
        if args.show_body:
            print(_indent(s.text))
    return 0


def cmd_refs(symbols: List[Symbol], args) -> int:
    """Who mentions this name: definitions plus every referencing site."""
    target = args.query.lower()
    rows: List[Tuple[str, str]] = []
    for s in symbols:
        if s.name.lower() == target or s.id.lower().endswith("." + target):
            rows.append((s.file, f"defines {s.kind} {s.id} (line {s.line})"))
        for ref in s.calls:
            if ref == target or ref.endswith("." + target):
                rows.append((s.file, f"referenced in {s.id} (line {s.line})"))
    if not rows:
        print(f"nothing references {args.query!r}")
        return 1
    for file, note in sorted(set(rows)):
        print(f"{file}  {note}")
    return 0


def cmd_calls(symbols: List[Symbol], args) -> int:
    target = args.query.lower()
    out: List[str] = []
    for s in symbols:
        if s.name.lower() == target or s.id.lower().endswith("." + target):
            refs = [r for r in s.calls if r not in ("self", "cls")]
            out.append(f"{s.id}  ({s.file}:{s.line})\n" + "\n".join(f"    -> {r}" for r in refs))
    if not out:
        print(f"no definition matching {args.query!r}")
        return 1
    print("\n".join(out))
    return 0


def cmd_json(symbols: List[Symbol], args) -> int:
    q = args.query.lower()
    payload = {
        "query": args.query,
        "total_symbols": len(symbols),
        "definitions": [s.to_dict() for s in symbols if _matches(s, args.query)],
        "references": [
            {"file": s.file, "symbol": s.id, "line": s.line, "ref": r}
            for s in symbols
            for r in s.calls
            if q in r.lower()
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_summary(symbols: List[Symbol], args) -> int:
    kinds: Dict[str, int] = {}
    for s in symbols:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    files = len({s.file for s in symbols})
    print(f"indexed {len(symbols)} symbols across {files} files")
    for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {kind:>10}  {n}")
    return 0


def _indent(text: str, pad: str = "    ") -> str:
    return "\n".join(pad + line for line in text.splitlines())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AST symbol/reference search over a checkout. No third-party deps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Commands: defs, refs, calls, json, summary",
    )
    p.add_argument("command", choices=["defs", "refs", "calls", "json", "summary"])
    p.add_argument("--query", "-q", default="", help="symbol name or substring")
    p.add_argument(
        "--root",
        "-r",
        nargs="+",
        default=list(DEFAULT_ROOTS),
        help="files or directories to index (default: the current directory)",
    )
    p.add_argument("--show-body", action="store_true", help="with 'defs', print the source")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.exists(args.root[0]):
        print(f"no such path: {args.root[0]}", file=sys.stderr)
        return 2
    symbols = index(args.root)
    if not symbols:
        print(
            "indexed 0 symbols — the checkout is empty, unreadable, or not Python. "
            "Unpack snapshots/<instance_id>.tgz into /workspace first.",
            file=sys.stderr,
        )
        return 2
    if args.command == "summary":
        return cmd_summary(symbols, args)
    if not args.query:
        print("--query is required for this command", file=sys.stderr)
        return 2
    return {
        "defs": cmd_defs,
        "refs": cmd_refs,
        "calls": cmd_calls,
        "json": cmd_json,
    }[args.command](symbols, args)


if __name__ == "__main__":
    raise SystemExit(main())
