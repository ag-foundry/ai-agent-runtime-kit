# RUNNER_V2_REFACTOR_PLAN

## Purpose
This document defines the safe implementation plan for refactoring
`project-research-run` from the current v1/v3 planning shape
to the `project-research v2` contract.

The goal is to keep the runner working during transition,
while gradually moving it to the new structured artifact model.

---

## Refactor principles

1. Do not rewrite everything at once.
2. Keep the shell entrypoint for now.
3. Preserve current working behavior where possible.
4. Introduce new artifacts in a controlled order.
5. Make internal state coherent before richer research fill.
6. Prefer safe incremental steps over clever rewrites.

---

## Current status before refactor

Already available:
- `project-research-v2-draft/SKILL.md`
- `project-research-v2-draft/skill.json`
- `schemas/`
- `policies/`
- `evals/`
- `RUNNER_V2_ARTIFACT_CONTRACT.md`
- `RUNNER_V2_STATE_MODEL.md`
- validated `validate_skill.py`

Current runner status:
- current `project-research-run` can already produce:
  - `RESEARCH.md`
  - `sources.json`
  - `context.json`
  - `precheck.txt`
- current runner does not yet produce:
  - `run_manifest.json`
  - `findings.jsonl`
  - `provenance.json`
  - `quality_report.json`

---

## Refactor target

The refactored runner must:

1. build one internal state snapshot
2. write coherent structured artifacts
3. render `RESEARCH.md` from the same state
4. remain honest when research fill is shallow
5. stay compatible with bounded `none|quick|deep` behavior

---

## Refactor phases

## Phase 1 — State-first stabilization
Goal:
- keep current logic
- formalize internal state shape
- improve consistency of existing outputs

Tasks:
- ensure `context.json` becomes the canonical state snapshot
- ensure `sources.json` is derived from state, not assembled ad hoc
- ensure `RESEARCH.md` reflects state-derived values
- keep `precheck.txt` as existing diagnostic artifact

Deliverable:
- runner still works
- `context.json` is coherent and complete enough for future artifact generation

---

## Phase 2 — Add missing required artifacts
Goal:
- start emitting full v2 minimum artifact set

Tasks:
- add `run_manifest.json`
- add `findings.jsonl`
- add `provenance.json`
- add `quality_report.json`

Rules:
- keep contents minimal but valid
- do not fake deep research
- provenance may initially point mostly to local memory and local files
- findings may initially be derived from planning outputs only

Deliverable:
- runner emits all required v2 artifacts

---

## Phase 3 — Quality gate enforcement
Goal:
- make runner evaluate and record v2 gates explicitly

Required gates:
- `search_targets_have_query_sets`
- `no_memory_boilerplate_dominance`
- `starting_approach_not_generic`
- `anti_patterns_present`
- `provenance_present_for_findings`

Tasks:
- compute pass/fail per gate
- write gate results into `quality_report.json`
- reflect summary in `run_manifest.json`
- downgrade run status to `warning` when needed

Deliverable:
- quality is no longer implicit; it is recorded

---

## Phase 4 — Improve findings and provenance
Goal:
- make downstream automation possible

Tasks:
- define stable finding IDs
- ensure one JSON object per line in `findings.jsonl`
- ensure each finding has provenance
- add compact provenance entries with `used_for`

Deliverable:
- future `project-init` can consume findings and provenance safely

---

## Phase 5 — Real quick-research fill
Goal:
- move from planning-only stub toward real bounded research value

Tasks:
- collect 2–3 similar solutions
- collect 1–2 authoritative sources
- collect 3–5 recurring risks
- enrich `sources`
- enrich `findings`
- keep output bounded and compact

Deliverable:
- runner becomes genuinely useful as a research stage,
  not just as a planning skeleton

---

## Phase 6 — Eval and trace integration
Goal:
- make refactor testable and observable

Tasks:
- add runner test prompts
- compare artifacts against contract
- prepare trace points for later observability
- prepare quality regression checks

Deliverable:
- runner changes become measurable, not opinion-based

---

## Safe implementation order

The implementation order should be:

1. preserve current runner file as baseline
2. inspect current output shape
3. update runner to produce richer `context.json`
4. add `quality_report.json`
5. add `run_manifest.json`
6. add `findings.jsonl`
7. add `provenance.json`
8. re-render `RESEARCH.md` from unified state
9. test on mixed prompt
10. compare results with contract docs

This order minimizes breakage.

---

## First concrete coding step

The first real code step should **not** be full runner rewrite.

Instead:
- create a new generator/updater script for `project-research-run`
- preserve the old runner as rollback point
- teach the runner to emit:
  - `quality_report.json`
  - `run_manifest.json`
first, because they are easiest and most structural

Only after that add:
- `findings.jsonl`
- `provenance.json`

---

## Rollback strategy

If refactor breaks behavior:
- keep the prior `project-research-run` as backup
- compare artifact differences
- restore old runner immediately
- fix incrementally

No destructive migration should occur in this phase.

---

## Definition of done for first runner refactor

The first runner refactor is done if:

- runner still starts and completes successfully
- `context.json` is coherent
- `sources.json` matches state
- `RESEARCH.md` matches state
- `quality_report.json` exists
- `run_manifest.json` exists
- output directory and `latest` symlink still work
- mixed prompt test still completes without fake claims

---

## Not yet included in this refactor

This stage does not yet include:
- full external research harvesting
- background mode execution
- weekly watchtower flow
- housekeeper flow
- project-init generation
- automatic self-modification

These come later.

---

## Immediate next action after this document

After accepting this refactor plan:

1. create a safe runner-updater script
2. back up current `project-research-run`
3. upgrade runner to emit:
   - `quality_report.json`
   - `run_manifest.json`
4. test on the existing mixed prompt
5. inspect outputs
6. only then continue