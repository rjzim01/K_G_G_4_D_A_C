# adapters/

Intentionally empty. A PEFT LoRA adapter would go here as
`adapters/<adapter_name>/adapter_config.json` and
`adapters/<adapter_name>/adapter_model.safetensors`, referenced from a
`LlmAgent` with `adapter: <adapter_name>`.

## Nothing is here, and that is deliberate

No adapter is shipped. The base model is used for every agent, which the rules
require anyway — `gemma-4-31b-it-qat-w4a16-ct` is the only permitted variant, and
adapters are optional.

Adding one is not a drop-in change. It has to be trained against this harness:

- the exact tool set and the exact `ast`-indexed navigation path in
  `skills/repo_navigation/`, because an adapter trained against the released
  graph tools learns to rely on a data source that returns nothing;
- the tool-call format the harness parses, not a generic function-calling
  dataset;
- a held-out split of the 129 dev tasks, so "does fine-tuning help" is a
  measurement and not a hope.

A LoRA trained on generic Python instruction data will not beat the base model
here and costs you the submission-size budget to carry. This directory stays
empty until there is a trained artifact and a local eval that shows it wins.

## If you do train one

```text
adapters/main_lora/
├── adapter_config.json
└── adapter_model.safetensors
```

then reference it from `agent.yaml` with `adapter: main_lora`. The rules allow a
different adapter per agent — e.g. `main_lora` on the root coder agent and
`tool_lora` on the locator — but each one is still the same base model.

Check the size against the 20 GB per-submission cap before packaging.
