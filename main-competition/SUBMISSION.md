# What to zip, and how to verify it

**Short version: zip the *contents* of `submission/`, not the folder itself.**

```
main-competition/submission/agent.yaml     <- this file is the submission
```

`agent.yaml` must sit at the **root of the archive**. If you zip the folder, you get
`submission/agent.yaml` one level down, and the loader will not find your root agent. This is the
single most common way a submission fails before it is even read.

## The ten files, and where they must land

Run from `main-competition/`, this is the exact archive structure:

```
agent.yaml                                  root agent config      REQUIRED
eval_config.yaml                            per-task time limits   optional
configs/sampling.yaml                       decoding params       optional
prompts/system.md                           strategy              optional
sub_agents/locator.yaml                     search sub-agent      optional
sub_agents/patcher.yaml                     verify sub-agent      optional
skills/repo_navigation/SKILL.md             skill manifest        optional
skills/repo_navigation/scripts/find_symbols.py                   optional
skills/repo_navigation/resources/repo_notes.md                    optional
adapters/README.md                          (empty, no LoRA)      optional
```

Note there is **no `submission/` prefix** on any of these. Current size is ~17 KB, so the 20 GB cap
is nowhere near binding.

## Three ways to build it

### 1. The build script (recommended)

```bash
cd K_G_G_4_DeveloperAgent/main-competition
python3 tools/build_submission.py --zip --strict
```

Writes `submission.zip` next to the folder. `--strict` turns warnings into errors. This also checks
the things a manual zip cannot: `agent.yaml` at the root, no `!include` escaping the submission
root, no symlinks, an `SKILL.md` with a `name:` field for every skill, every `run_skill_script`
path resolving, and Python that compiles.

The script is gitignored output — `submission.zip` is a build artifact and is deliberately not
tracked. Regenerate it any time; never edit it directly.

### 2. Command line, no dependencies

```bash
cd K_G_G_4_DeveloperAgent/main-competition/submission
zip -r -D ../submission.zip . -x '*.pyc' -x '*__pycache__*' -x '.DS_Store'
```

The trailing `.` is the important part — it archives the current directory's contents, so paths
start at `agent.yaml`. Note you `cd` *into* `submission/` first; zipping `submission/` from the
parent puts a directory level in the way.

`-D` skips bare directory entries. Without it you get a valid archive with 18 entries instead of
10 (the extra 8 are just `skills/`, `adapters/`, and friends). Harmless in most readers, but the
build script omits them, so `-D` keeps the two methods byte-comparable.

### 3. GUI

Select all ten files/folders inside `submission/`, right-click → *Compress* → *zip*. Make sure you
selected the **contents**, not `submission` itself. After it finishes, open the zip and confirm
`agent.yaml` is at the top level with no enclosing folder.

## Verify before you upload

```bash
python3 -c "
import zipfile
z = zipfile.ZipFile('submission.zip')
names = sorted(z.namelist())
print('\n'.join(names))
print()
assert z.testzip() is None, 'corrupt archive'
assert 'agent.yaml' in names, 'FAIL: agent.yaml is not at the archive root'
print('OK -', len(names), 'files, agent.yaml at root')
"
```

You want to see this shape:

```
adapters/README.md
agent.yaml
configs/sampling.yaml
eval_config.yaml
prompts/system.md
skills/repo_navigation/SKILL.md
skills/repo_navigation/resources/repo_notes.md
skills/repo_navigation/scripts/find_symbols.py
sub_agents/locator.yaml
sub_agents/patcher.yaml
```

## What must never be in the archive

- **A `submission/` top-level directory** — breaks root discovery.
- **`__pycache__/`, `*.pyc`, `.DS_Store`, `*.ipynb_checkpoints/`** — junk, and `find_symbols.py`
  will try to parse whatever `.py` files it finds in the sandbox.
- **Any `../` path.** `!include` resolves relative to the file containing the tag and may not
  traverse outside the submission root, so a config referencing `../../paper-track/...` fails at
  load. Everything a config needs is already inside the folder.
- **The corpus, graphs, embeddings, snapshots, or a LoRA checkpoint.** The dataset is supplied by
  the harness; the submission is config plus scripts only.
- **Symlinks.** A ZIP cannot store them faithfully, and the loader rejects them.

## Also read before uploading

**[`SCHEMA-NOTES.md`](SCHEMA-NOTES.md)** — written without the dataset, so the *concepts* in the
YAML are right but some *field names* are inferred. Reconcile against `sample_submission/agent.yaml`
and `HARNESS_README.md` from the competition download. The first validating run will likely produce
schema errors, and each one is a rename rather than a redesign.

Zipping is the last step, not the next one. A structurally perfect archive with wrong field names
still scores zero.
