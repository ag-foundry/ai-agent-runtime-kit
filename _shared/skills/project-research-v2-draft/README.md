 # project-research-v2-draft

`project-research-v2-draft` is a research-and-validation skill bundle for structured project discovery, artifact generation, provenance capture, quality gating, and regression checks.

The bundle is designed to support **two execution modes** with a **shared artifact contract**:

- `chatgpt_codex` — interactive human-in-the-loop workflow using ChatGPT Pro / Codex, without requiring a dedicated OpenAI API backend
- `openai_api` — server-side workflow using OpenAI API for automation, orchestration, and background execution

These modes must share:
- artifact structure
- schemas
- provenance model
- quality gates
- validator logic
- eval logic
- regression logic

Only the **model access layer / execution path** may differ.

---

## Current status

The current bundle already has a working validated research pipeline:

- `project-research-run`
- `validate-project-research-run`
- `project-research-eval`
- `project-research-regress`
- `project-research-regress-full`

The current runtime baseline is built around:
- artifact bundle completeness
- validator correctness
- eval coverage
- full regression safety

The next architecture steps must preserve this working baseline.

---

## Design goal

The project must support this migration path:

1. start in `chatgpt_codex`
2. generate artifacts locally
3. validate and regress the outputs
4. later add `openai_api` execution
5. keep the same contracts, evals, and regression surface

This means the project must **not** be split into two separate stacks.

---

## Shared contracts

The following contracts are shared across both execution modes:

- `context.json`
- `findings.jsonl`
- `provenance.json`
- `quality_report.json`
- `run_manifest.json`
- `sources.json`
- `RESEARCH.md`

Validators and evals must treat these outputs identically regardless of execution mode.

---

## Bundle structure

### Core docs
- `SKILL.md`
- `skill.json`
- `README.md`

### Policies
- `policies/source_policy.md`
- `policies/budget_policy.md`
- `policies/quality_policy.md`
- `policies/maintenance_hooks.md`
- `policies/execution_modes.md`

### Schemas
- `schemas/context.schema.json`
- `schemas/finding.schema.json`
- `schemas/source.schema.json`
- `schemas/run_manifest.schema.json`
- `schemas/research_report.schema.json`

### Evals
- `evals/classification_cases.yaml`
- `evals/source_quality_cases.yaml`
- `evals/mixed_project_cases.yaml`
- `evals/empty_memory_cases.yaml`
- `evals/runner_eval_cases.yaml`

### References
- `references/RUNNER_V2_ARTIFACT_CONTRACT.md`
- `references/RUNNER_V2_STATE_MODEL.md`
- `references/RUNNER_V2_REFACTOR_PLAN.md`
- `references/VALIDATOR_REQUIREMENTS.md`

### Scripts
- `scripts/validate_skill.py`

---

## Execution modes

### Mode: `chatgpt_codex`
Use when:
- the user is driving work manually
- ChatGPT / Codex is the primary execution interface
- artifact production is local and interactive
- no API key should be mandatory
- background server automation is not required

Expected semantics:
- `execution_mode = "chatgpt_codex"`
- `model_access_layer = "interactive_chatgpt_or_codex"`
- `human_in_loop = true`
- `requires_api_key = false`
- `supports_background_automation = false`

### Mode: `openai_api`
Use when:
- the server or workflow engine must call the model directly
- jobs run through scripts, orchestration, queues, webhooks, or schedulers
- API billing and credentials are acceptable
- background automation is required

Expected semantics:
- `execution_mode = "openai_api"`
- `model_access_layer = "server_side_openai_api"`
- `human_in_loop = true/false` depending on workflow
- `requires_api_key = true`
- `supports_background_automation = true`

---

## Research prompt standard

Research prompts must be dual-mode-safe.

### Canonical prompt pattern
A correct research prompt should say, in substance:

- support both `chatgpt_codex` and `openai_api`
- keep artifacts / provenance / evals / validator shared
- isolate only the execution layer
- allow migration from `chatgpt_codex` to `openai_api` without redesigning the project

Avoid prompts that force API-only assumptions unless the task explicitly requires API-only implementation.

---

## Validation and regression

### Skill bundle validation
- `python3 scripts/validate_skill.py`

### Runtime validation
- `validate-project-research-run <topic> latest`

### Eval surface
- `project-research-eval all`

### Full regression
- `project-research-regress-full`

The bundle is considered healthy only when:
- artifact bundle is complete
- validator passes
- eval cases pass
- full regression passes

---

## Current architectural rule

Use:
- shared research core
- shared quality contracts
- shared eval surface
- shared regression surface
- mode-specific execution adapters

Do not:
- fork the bundle by mode
- make OpenAI API mandatory for all project work
- duplicate validators/evals by mode without necessity

---

## Practical meaning

For this project, `chatgpt_codex` is a **first-class execution mode**, not a temporary workaround.

`openai_api` is an **optional upgrade path** for server-driven automation.

The bundle must remain productive in `chatgpt_codex` mode even if API mode is not enabled yet.
