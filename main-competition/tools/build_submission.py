#!/usr/bin/env python3
"""Validate the submission layout and package it as submission.zip.

The rules are strict about what may be in the archive and what may be referenced
from inside it, and the failure modes are quiet: a path that escapes the
submission root is not an error at package time, it is a rejected submission.
So this checks the constraints that the Overview states, and refuses to build an
archive that violates them.

What it enforces, all from the published rules:

  - ``agent.yaml`` exists at the archive root.
  - ``!include`` paths resolve inside the submission root. Path traversal via
    ``../`` and symlinks are both disallowed by the rules; this rejects both.
  - Every file is a regular file, not a symlink.
  - The archive stays under the 20 GB submission cap.
  - Script referenced by a skill actually exists, and is not executable-bit
    dependent -- the sandbox may not preserve the bit.

Run::

    python3 tools/build_submission.py                  # validate, report, do not package
    python3 tools/build_submission.py --zip            # validate, then write submission.zip
    python3 tools/build_submission.py --zip --strict   # treat warnings as errors
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import List, Tuple

HERE = Path(__file__).resolve().parent
SUBMISSION = HERE.parent / "submission"
MAX_BYTES = 20 * 1024**3  # 20 GB per submission, per the rules
INCLUDE_RE = re.compile(r"!include\s+(\S+)")
SKIP_DIRS = {"__pycache__", ".git", ".ipynb_checkpoints", ".DS_Store"}


class Report:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.notes: List[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def render(self) -> str:
        out = []
        for label, items, tag in (
            ("error", self.errors, "x"),
            ("warn", self.warnings, "!"),
            ("note", self.notes, "-"),
        ):
            for it in items:
                out.append(f"  [{tag}] {label}: {it}")
        return "\n".join(out)


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn in SKIP_DIRS:
                continue
            yield Path(dirpath) / fn


def check_layout(root: Path, rep: Report) -> None:
    if not root.is_dir():
        rep.error(f"submission root missing: {root}")
        return

    agent = root / "agent.yaml"
    if not agent.is_file():
        rep.error("agent.yaml is required at the archive root")
    else:
        rep.note("agent.yaml present at root")

    files = list(iter_files(root))
    if not files:
        rep.error("submission root is empty")
        return

    total = 0
    symlinks = []
    for f in files:
        if f.is_symlink():
            symlinks.append(f.relative_to(root))
        else:
            total += f.stat().st_size

    for s in symlinks:
        rep.error(
            f"{s} is a symlink; the rules disallow symlinks, and they do not "
            "survive the zip round trip"
        )

    mb = total / 1024**2
    rep.note(f"{len(files)} files, {mb:.1f} MiB")
    if total > MAX_BYTES:
        rep.error(f"archive is {total / 1024**3:.2f} GB, over the 20 GB cap")

    # SKILL.md must be present for any skill directory to be loadable.
    for skill_dir in sorted(p for p in root.rglob("skills/*") if p.is_dir()):
        manifest = skill_dir / "SKILL.md"
        if not manifest.is_file():
            rep.error(f"{skill_dir.relative_to(root)} has no SKILL.md manifest")
        else:
            text = manifest.read_text(encoding="utf-8", errors="replace")
            if not text.startswith("---"):
                rep.error(
                    f"{manifest.relative_to(root)} does not open with YAML frontmatter; "
                    "the rules require `name: <skill-name>` in the manifest"
                )
            elif not re.search(r"^name:\s*\S+", text, re.M):
                rep.error(f"{manifest.relative_to(root)} frontmatter has no `name:` field")

    # Anything a skill or prompt points at must exist.
    skills_root = root / "skills"
    for md in sorted(root.rglob("SKILL.md")):
        if not skills_root.is_dir():
            rep.warn("no skills/ directory; the SKILL.md reference is dead")
            break


def strip_comments(text: str) -> str:
    """Drop whole-line and trailing ``#`` comments.

    Needed because the prose in these files talks *about* ``!include``, and a
    naive scan picks up ``!include that references it`` as a directive.
    """
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # A '#' only starts a comment outside quotes. These files are simple
        # enough that a quote-aware walk of the line is enough.
        in_s = in_d = False
        cut = None
        for i, ch in enumerate(line):
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == "#" and not in_s and not in_d:
                cut = i
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def check_includes(root: Path, rep: Report) -> None:
    for yml in sorted(list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))):
        rel = yml.relative_to(root)
        text = strip_comments(yml.read_text(encoding="utf-8", errors="replace"))
        for inc in INCLUDE_RE.findall(text):
            if ".." in inc or inc.startswith("/"):
                rep.error(
                    f"{rel} has `!include {inc}`; `!include` resolves relative to the "
                    "including file and may not escape the submission root"
                )
                continue
            target = (yml.parent / inc).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                rep.error(f"{rel} `!include {inc}` resolves outside the submission root")
                continue
            if not target.is_file():
                rep.error(f"{rel} `!include {inc}` does not exist")
            else:
                rep.note(f"{rel} !include {inc} -> ok")


def check_skill_scripts(root: Path, rep: Report) -> None:
    """Every ``run_skill_script(<path>)`` must point at a real file under skills/.

    This is the one reference class worth checking mechanically: the path is
    interpreted by the harness at run time, a typo is silent, and the file lives
    inside the submission at a predictable place. Prose references to paths in
    the *target* repos (fastapi/routing.py and friends) are deliberately not
    checked -- they are not ours to ship.
    """
    pattern = re.compile(r"run_skill_script\(\s*([\w./-]+\.py)")
    found_any = False
    for src in sorted(list(root.rglob("*.md")) + list(root.rglob("*.yaml"))):
        rel = src.relative_to(root)
        refs = set(
            pattern.findall(strip_comments(src.read_text(encoding="utf-8", errors="replace")))
        )
        for ref in sorted(refs):
            found_any = True
            skill_name = ref.split("/", 1)[0]
            candidate = root / "skills" / ref
            if not candidate.is_file():
                rep.error(
                    f"{rel} calls run_skill_script({ref!r}) but "
                    f"skills/{ref} does not exist in the submission"
                )
            elif not (root / "skills" / skill_name / "SKILL.md").is_file():
                rep.error(f"skills/{skill_name} is referenced but has no SKILL.md manifest")
    if found_any:
        rep.note("run_skill_script references resolved")


def check_scripts(root: Path, rep: Report) -> None:
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root)
        try:
            compile(py.read_text(encoding="utf-8", errors="replace"), str(rel), "exec")
        except SyntaxError as e:
            rep.error(f"{rel} does not parse: {e}")
        if not os.access(py, os.X_OK):
            rep.warn(
                f"{rel} is not executable; if the sandbox invokes it directly rather "
                "than via `python3`, it will fail with permission denied"
            )


def build_zip(root: Path, out: Path, rep: Report) -> None:
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in iter_files(root):
            zf.write(f, f.relative_to(root).as_posix())
    size = out.stat().st_size
    rep.note(f"wrote {out} ({size / 1024**2:.1f} MiB)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(SUBMISSION), help="submission staging directory")
    ap.add_argument("--zip", dest="do_zip", action="store_true", help="package submission.zip")
    ap.add_argument("--out", default=str(HERE.parent / "submission.zip"), help="output archive path")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    rep = Report()
    check_layout(root, rep)
    check_includes(root, rep)
    check_skill_scripts(root, rep)
    check_scripts(root, rep)

    inside = root.is_relative_to(Path.cwd())
    print(f"checking {root.relative_to(Path.cwd()) if inside else root}")
    body = rep.render()
    if body:
        print(body)
    print(f"\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")

    failed = bool(rep.errors) or (args.strict and bool(rep.warnings))
    if failed:
        print("not packaging")
        return 1

    if args.do_zip:
        build_zip(root, Path(args.out), rep)
        print(f"packaged -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
