# RUNNER_V2_STATE_MODEL

## Purpose
This document defines the internal runner-side state model for `project-research-run`
when targeting `project-research v2`.

It exists to make runner refactor deterministic and safe.

The runner should build one coherent internal state first, then derive all output artifacts from it.

The state model must support **two execution modes**:

- `chatgpt_codex`
- `openai_api`

These modes must share the same internal research structure.
Only the model access layer / execution path may differ.

---

## Main design rule

The runner must not generate each artifact independently from scratch.

Instead it should:

1. collect local context
2. classify the project
3. choose mode
4. choose execution mode
5. derive research targets
6. derive query sets
7. derive risk seeds
8. derive starting approach
9. evaluate quality gates
10. build one internal state object
11. render artifacts from that state

---

## Internal state object

The internal state object should contain at least:

- `topic`
- `initial_prompt`
- `project_type`
- `detected_classes`
- `class_scores`
- `mode`
- `mode_reason`
- `execution_mode`
- `execution_mode_reason`
- `model_access_layer`
- `human_in_loop`
- `requires_api_key`
- `supports_background_automation`
- `memory_first`
- `local_memory_summary`
- `search_targets`
- `source_priority`
- `query_sets`
- `risk_seeds`
- `starting_approach`
- `anti_patterns`
- `open_questions`
- `sources`
- `findings`
- `provenance_entries`
- `quality_gates_result`
- `artifact_dir`
- `precheck_log`
- `runner_version`
- `skill_name`
- `skill_version`
- `started_at`
- `finished_at`
- `status`

---

## Field groups

## 1. Identity fields
These identify the run and must stay stable across all artifacts.

- `topic`
- `initial_prompt`
- `artifact_dir`
- `runner_version`
- `skill_name`
- `skill_version`
- `started_at`
- `finished_at`
- `status`

---

## 2. Classification fields
These are derived early and shape the rest of the run.

- `project_type`
- `detected_classes`
- `class_scores`
- `mode`
- `mode_reason`

---

## 3. Execution fields
These define how the model is being accessed.

- `execution_mode`
- `execution_mode_reason`
- `model_access_layer`
- `human_in_loop`
- `requires_api_key`
- `supports_background_automation`

### Expected semantics

#### Mode: `chatgpt_codex`
- `execution_mode = "chatgpt_codex"`
- `model_access_layer = "interactive_chatgpt_or_codex"`
- `human_in_loop = true`
- `requires_api_key = false`
- `supports_background_automation = false`

#### Mode: `openai_api`
- `execution_mode = "openai_api"`
- `model_access_layer = "server_side_openai_api"`
- `human_in_loop = false` or `true` depending on workflow
- `requires_api_key = true`
- `supports_background_automation = true`

Rules:
- execution fields must stay internally consistent
- execution fields must match `context.json` and `run_manifest.json`
- execution mode must not change artifact structure

---

## 4. Local-context fields
These are produced before external search planning.

- `memory_first`
- `local_memory_summary`
- `precheck_log`

Rules:
- local memory summary must prefer signal over boilerplate
- if local signal is weak, that must be stated honestly

---

## 5. Research-planning fields
These define how the bounded research stage is planned.

- `search_targets`
- `source_priority`
- `query_sets`
- `risk_seeds`
- `starting_approach`
- `anti_patterns`
- `open_questions`

Rules:
- every search target must have query sets
- starting approach must be planning-relevant, not generic filler
- anti-patterns must be explicit

---

## 6. Gathered-source fields
These hold structured source information.

- `sources`

Each source should support:
- `kind`
- `title`
- `url`
- `why_relevant`
- `confidence`
- `source_bucket`
- `notes`

Rules:
- `sources` may be empty in planning-only mode
- empty sources must not be disguised as completed research

---

## 7. Finding fields
These support downstream automation and project-init.

- `findings`

Each finding should support:
- `id`
- `kind`
- `statement`
- `confidence`
- `provenance`

Rules:
- findings must be concise
- findings must be atomic
- inferred findings must say they are inferred

---

## 8. Provenance fields
These provide traceability.

- `provenance_entries`

Each provenance entry should support:
- `ref`
- `origin_type`
- `path_or_url`
- `label`
- `used_for`

Rules:
- findings must be traceable to provenance entries
- provenance must stay compact

---

## 9. Quality fields
These capture gate evaluation and final health of the run.

- `quality_gates_result`

Suggested structure:
- `passed_gates`
- `failed_gates`
- `warnings`
- `notes`

Rules:
- required v2 gates must always be evaluated
- warnings may exist without full failure
- fake success is forbidden

---

## Derivation map

## Derived directly from input or environment
- `topic`
- `initial_prompt`
- `started_at`
- `runner_version`
- `skill_name`
- `skill_version`

## Derived from precheck and local context
- `memory_first`
- `local_memory_summary`
- `precheck_log`

## Derived from classification step
- `project_type`
- `detected_classes`
- `class_scores`
- `mode`
- `mode_reason`

## Derived from execution selection step
- `execution_mode`
- `execution_mode_reason`
- `model_access_layer`
- `human_in_loop`
- `requires_api_key`
- `supports_background_automation`

## Derived from planning step
- `search_targets`
- `source_priority`
- `query_sets`
- `risk_seeds`
- `starting_approach`
- `anti_patterns`
- `open_questions`

## Derived from research fill step
- `sources`
- `findings`
- `provenance_entries`

## Derived from quality evaluation step
- `quality_gates_result`
- `status`

## Derived at finalization step
- `artifact_dir`
- `finished_at`

---

## Artifact rendering map

## context.json
Should contain the full or near-full internal state snapshot used for rendering.

Must include:
- identity fields
- classification fields
- execution fields
- local-context fields
- planning fields
- artifact references

## sources.json
Should contain:
- identity subset
- classification subset
- execution subset
- planning subset
- source list
- local memory summary
- artifact references

## findings.jsonl
Should be rendered from:
- `findings`

## provenance.json
Should be rendered from:
- `topic`
- `artifact_dir`
- `provenance_entries`

## quality_report.json
Should be rendered from:
- `topic`
- `mode`
- `status`
- `quality_gates_result`

## run_manifest.json
Should contain:
- identity subset
- classification subset
- execution subset
- artifact list
- quality gate summary
- final status

## RESEARCH.md
Should be rendered from the same state object, not assembled independently.

---

## Consistency rule

The following values must remain consistent across the state object and rendered artifacts:

- `topic`
- `project_type`
- `mode`
- `mode_reason`
- `artifact_dir`
- `execution_mode`
- `execution_mode_reason`
- `model_access_layer`
- `human_in_loop`
- `requires_api_key`
- `supports_background_automation`

If these diverge, validator/eval may treat the run as contract-broken.

---

## Migration rule

The state model must support this evolution path:

1. start in `chatgpt_codex`
2. validate artifacts and quality gates
3. later run in `openai_api`
4. preserve the same state structure
5. preserve the same artifact contract
6. preserve the same validator/eval/regression surface

That migration path is the default design target.