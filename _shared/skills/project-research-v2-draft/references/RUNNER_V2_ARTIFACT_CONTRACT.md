# RUNNER_V2_ARTIFACT_CONTRACT

## Purpose
This document defines the exact artifact contract that `project-research-run`
must follow when targeting `project-research v2`.

The goal is to keep the runner:

- memory-first
- bounded by mode
- planning-oriented
- schema-aligned
- explicit about provenance and quality gates
- compatible with **two execution modes**:
  - `chatgpt_codex`
  - `openai_api`

These execution modes must share the same artifact contract.
Only the model access layer may differ.

---

## Artifact set

A successful v2 run must produce these canonical artifacts inside:

`artifacts/research/<timestamp>/`

1. `context.json`
2. `RESEARCH.md`
3. `sources.json`
4. `run_manifest.json`
5. `findings.jsonl`
6. `provenance.json`
7. `quality_report.json`

Optional later artifacts may exist, but these seven are the required minimum.

---

## Artifact locations

Primary research artifacts must live under:

`artifacts/research/<timestamp>/`

The runner may also maintain:

- `artifacts/research/latest` → symlink to latest run

Canonical run data lives in the timestamped artifact directory.

The validator and eval layers must validate **artifact_dir-local files**, not topic-level convenience files.

---

## Shared dual-mode rule

All canonical artifacts must remain structurally compatible across both execution modes:

- `chatgpt_codex`
- `openai_api`

This means:

- artifact names stay the same
- validator logic stays shared
- eval logic stays shared
- regression logic stays shared
- provenance and quality gates stay shared

Execution-mode differences must be represented through fields, not through divergent artifact families.

---

## 1. context.json

## Role
Machine-readable run context used by downstream validation, eval, planning, and handoff.

## Required top-level fields
- `topic`
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
- `initial_prompt`
- `keywords`
- `search_targets`
- `source_priority`
- `query_sets`
- `risk_seeds`
- `starting_approach`
- `anti_patterns`
- `open_questions`
- `local_memory_summary`
- `artifact_dir`
- `precheck_log`

## Rules
- `execution_mode` must be one of:
  - `chatgpt_codex`
  - `openai_api`
- `memory_first` must reflect the actual runtime policy.
- `query_sets` must cover every value in `search_targets`.
- `starting_approach` must stay planning-oriented and non-generic.
- `artifact_dir` must match the actual timestamped run directory.

---

## 2. RESEARCH.md

## Role
Human-readable summary for planning handoff.

## Required sections
- Topic
- Project type
- Research mode
- Existing local context
- Search buckets
- Suggested search queries
- Similar solutions reviewed
- Official / authoritative sources
- Recurring risks / patterns
- Recommended starting approach
- What not to do
- Open questions

## Rules
- Must stay compact and planning-oriented.
- Must not pretend deeper research happened if it did not.
- Must reflect actual structured outputs, not invented extras.
- Must remain compatible with both execution modes.

---

## 3. sources.json

## Role
Structured planning-oriented representation of source strategy and gathered sources.

## Required top-level fields
- `topic`
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
- `initial_prompt`
- `keywords`
- `search_targets`
- `source_priority`
- `query_sets`
- `risk_seeds`
- `starting_approach`
- `local_memory_summary`
- `artifact_dir`
- `precheck_log`
- `artifact_refs`
- `sources`

## Rules
- Every value in `search_targets` must have a corresponding key in `query_sets`.
- `sources` may be empty in planning-only mode, but the file must not imply completed research.
- `local_memory_summary` must prefer signal over scaffolding boilerplate.
- `starting_approach` must be actionable.
- Dual-mode execution fields must remain internally consistent with `context.json` and `run_manifest.json`.

## Source object minimum shape
Each source entry should support:
- `kind`
- `title`
- `url`
- `why_relevant`
- `confidence`
- `source_bucket`
- `notes`

---

## 4. run_manifest.json

## Role
Execution manifest for the specific run.

## Required fields
- `skill_name`
- `skill_version`
- `topic`
- `mode`
- `mode_reason`
- `execution_mode`
- `execution_mode_reason`
- `model_access_layer`
- `human_in_loop`
- `requires_api_key`
- `supports_background_automation`
- `started_at`
- `finished_at`
- `runner_version`
- `initial_prompt`
- `project_type`
- `detected_classes`
- `artifact_dir`
- `artifacts`
- `quality_gates`
- `status`

## Allowed status values
- `ok`
- `warning`
- `failed`

## Rules
- `artifacts` must list the artifact files actually produced.
- `quality_gates` must reflect gates evaluated during the run.
- If a run fails partway, `status` must not be `ok`.
- Execution-mode fields must match the values recorded in `context.json`.

---

## 5. findings.jsonl

## Role
Line-delimited structured findings for downstream automation and planning.

## One JSON object per line

## Required fields per finding
- `id`
- `kind`
- `statement`
- `confidence`
- `provenance`

## Provenance object required fields
- `origin_type`
- `origin_ref`

## Allowed origin_type examples
- `local_memory`
- `local_file`
- `source`
- `inference`

## Rules
- Findings must be concise and atomic.
- One line = one finding.
- If a statement is inferred, provenance must say so explicitly.
- Findings must support future `project-init`.

---

## 6. provenance.json

## Role
Explicit mapping of references used by the run.

## Required top-level fields
- `topic`
- `artifact_dir`
- `entries`

## Entry minimum shape
- `ref`
- `origin_type`
- `path_or_url`
- `label`
- `used_for`

## Rules
- Every finding in `findings.jsonl` should be traceable to at least one provenance entry.
- Provenance may refer to local memory, local files, or external sources.
- Provenance should stay compact and audit-friendly.

---

## 7. quality_report.json

## Role
Machine-readable result of runner quality checks.

## Required top-level fields
- `topic`
- `mode`
- `status`
- `passed_gates`
- `failed_gates`
- `warnings`
- `notes`

## Required gate names in v2
- `search_targets_have_query_sets`
- `no_memory_boilerplate_dominance`
- `starting_approach_not_generic`
- `anti_patterns_present`
- `provenance_present_for_findings`

## Rules
- A fully clean run should have all required gates in `passed_gates`.
- If `sources` is empty and this is expected, report that as a note, not as fake success.
- Warnings are allowed without full failure, but they must be explicit.

---

## Runner behavior requirements

## Before writing artifacts
The runner must:
1. run local precheck
2. classify project
3. choose mode
4. choose execution mode
5. build search targets
6. build query sets
7. derive risk seeds
8. derive starting approach
9. evaluate quality gates
10. write artifacts

## Ordering rule
Structured artifacts should be internally coherent before `RESEARCH.md` is rendered.

Preferred order:
1. `context.json`
2. `sources.json`
3. `findings.jsonl`
4. `provenance.json`
5. `quality_report.json`
6. `run_manifest.json`
7. `RESEARCH.md`

---

## Consistency requirements

The runner output is valid only if all of the following remain consistent across artifacts:

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

The validator and eval layers may treat mismatches here as contract failures.

---

## Migration rule

The bundle must support this path without changing artifact families:

1. start in `chatgpt_codex`
2. validate artifacts and quality gates
3. later run in `openai_api`
4. preserve the same artifact contract
5. preserve the same validator/eval/regression surface

This migration path is the default design target.