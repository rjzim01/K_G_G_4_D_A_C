# Schema notes — what is verified and what is assumed

**Read this before submitting.** This submission was written without access to
the competition dataset. The `agent.yaml` schema, `sampling.yaml` keys and
`eval_config.yaml` keys are therefore reconstructed from the two scraped pages
in `docs/`, plus the public ADK Agent Config spec. The *concepts* are right; some
*field names* may not be.

The practical consequence: **the first run that validates will probably produce
schema errors, and that is expected.** Each one is a rename, not a redesign. Do
the reconciliation below once and the errors stop.

## Where the ground truth is

Three files in the dataset, none of which are in this repo:

| File | What it settles |
|---|---|
| `sample_submission/agent.yaml` | The authoritative root agent schema. Start here. |
| `HARNESS_README.md` | Tool call signatures, config language, local eval commands. 49 kB, in-depth. |
| `sample_submission/` (rest) | How sub-agents, skills and adapters are wired in practice. |

To get them:

```bash
kaggle competitions download -c gemma-4-developer-agent
# then look in sample_submission/ at the root of the extracted corpus
```

## Verified — stated in the published pages

These come from `docs/main-competition-overview.md`, which is a scrape of the
live Overview page. Safe to rely on.

- `agent.yaml` is **required at the archive root**.
- The config language follows the **Google ADK Agent Config** spec, plus
  sandboxing restrictions.
- `configs/sampling.yaml` — "generation parameters loaded via `!include`".
- `prompts/system.md` — "system instructions loaded via `!include`".
- `sub_agents/*.yaml` — "sub-agent or AgentTool YAML configurations".
- `adapters/<name>/` holds `adapter_config.json` + `adapter_model.safetensors`.
- `skills/<name>/` holds `SKILL.md`, `scripts/`, `resources/`. `SKILL.md` is a
  manifest with YAML frontmatter `name: <skill-name>`.
- `!include` resolves **relative to the file containing the tag**.
- Path traversal outside the submission root — `../` **and symlinks** — is
  disallowed.
- Only harness-provided tools, or custom subagents declared via `agent_tool`,
  are callable.
- `adapter: <adapter_name>` is referenceable on any `LlmAgent` in `agent.yaml`
  or `sub_agents/*.yaml`.
- `run_skill_script` runs in the persistent Docker sandbox and debits the
  central time budget; `load_skill_resource` reads skill knowledge files.
- `gemma-4-31b-it-qat-w4a16-ct` is the **only** permitted model, for every
  agent and subagent.
- `eval_config.yaml` may set per-task time limits. Shape not given.
- The nine harness tools and their signatures (see the table in the Overview).
- 12-hour total budget, 20 GB per submission, 5 submissions/day, team max 5.

## Assumed — inferred, not confirmed

Everything below is my reconstruction. Each is flagged in a comment at the point
of use.

| Assumption | Why I believe it | How to check |
|---|---|---|
| Agent-level keys `name`, `model`, `description`, `instruction`, `tools`, `sub_agents` | Mirrors ADK's Python `LlmAgent`. The Overview names `LlmAgent`, so the object model is ADK's. | `sample_submission/agent.yaml` |
| `instruction: !include prompts/system.md` | `instruction` is ADK's system-prompt field and `prompts/system.md` is documented as "system instructions". The pairing is inference. | same |
| `sub_agents: [{agent_tool: {config: path}}]` | `agent_tool` is named in the docs; the nesting and the `config:` key are invented. | `sample_submission/sub_agents/`, if any |
| `tools:` is a list of bare tool-name strings | The nine tools are named; whether the field takes strings, or objects with options, is unknown. | same |
| `configs/sampling.yaml` keys: `temperature`, `top_p`, `top_k`, `max_output_tokens`, `stop_sequences`, `presence_penalty`, `frequency_penalty` | Standard sampling vocabulary. "Generation parameters" is all the Overview says. | `HARNESS_README.md` |
| `eval_config.yaml` keys: `defaults.per_task_seconds`, `abandon_after_seconds`, `overrides` with glob patterns | Entirely invented. The docs confirm the file exists and may carry per-task limits, and nothing else. | `HARNESS_README.md` |
| Skills are auto-discovered from `skills/` | The docs never say a skill must be declared. If they must be, `agent.yaml` needs a reference I have not added. | `HARNESS_README.md` |
| A `SKILL.md` `description:` field exists for routing | The Overview only documents `name:`. I added `description:` because a router needs it. | `HARNESS_README.md` |
| `run_skill_script(<path>, args=[...])` call shape | The tool name is given, the argument convention is not. | `HARNESS_README.md` tool signatures |
| The graph-tool defect is still present at scoring time | True of the public ZIP. The private `rerun/` set may be assembled differently, and I have no way to check. | run the harness locally |

## Reconciliation order

Cheapest first, so the expensive work is not done on a config that will change:

1. **Open `sample_submission/agent.yaml`.** Diff its keys against
   `submission/agent.yaml`. Rename mine to match. This is the file that decides
   whether the submission loads at all.
2. **Grep `HARNESS_README.md` for the sampling and eval-config schemas.** If
   `sampling.yaml` uses different key names, either rename or **delete
   `configs/sampling.yaml` and the `!include` referencing it** — sampling is
   optional, and the base model defaults are a safe fallback. Do not ship a file
   you are unsure the harness will parse.
3. **Check whether skills need declaring in `agent.yaml`.** If they do, add the
   reference. This is the one omission that would leave the `repo_navigation`
   skill dead while the rest of the submission still loads.
4. **Run the local CLI eval** that `HARNESS_README.md` documents, on 2–3 tasks,
   before a full 129-task run. Confirm the agent reaches `edit_file` and
   `submit_patch`, and that `find_symbols.py` runs inside the sandbox.

`tools/build_submission.py` catches the *structural* mistakes — a missing
`agent.yaml`, an `!include` that escapes the root, a symlink, a missing
`SKILL.md` manifest, a `run_skill_script` path that does not exist, Python that
does not parse. It **cannot** catch a wrong field name, because it has no spec
to check against. That is exactly the gap this file describes.

## One thing that is a judgement call, not a schema issue

`agent.yaml` lists `get_code_neighbors`, `get_code_subgraph` and
`search_similar_code` in `tools:` even though they are expected to return
nothing. That is deliberate: the system prompt tells the agent to probe them
once per run and then fall back, which is how you *discover* whether the
defect is still there rather than assuming. Once a local eval confirms they are
dead, **remove them from the list** — an unavailable tool still costs a call and
context, and there is no upside to leaving a dead tool wired in.
