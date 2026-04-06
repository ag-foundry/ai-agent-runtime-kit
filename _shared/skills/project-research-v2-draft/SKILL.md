---
name: project-research
version: "2.0-draft"
description: >
  Run a memory-first, bounded research stage before planning a new or materially changed project.
  This v2 draft introduces a machine-readable contract, schema-defined artifacts, provenance,
  confidence and quality gates, while staying compact and planning-oriented across two execution modes:
  chatgpt_codex and openai_api.
---

# project-research v2 draft

## Goal
Produce a compact, high-signal research package that improves the next planning step
without turning research into uncontrolled crawling or bloated notes.

This skill must support **two execution modes** with the same artifact contract:

- `chatgpt_codex` — human-in-the-loop workflow via ChatGPT Pro / Codex, without requiring a dedicated OpenAI API backend
- `openai_api` — server-side workflow via OpenAI API for automation, orchestration, and background execution

These modes must differ only in the **model access layer**, not in the research artifact contract.

## Main output contract
The skill is considered successful only if it can support generation of:

- `RESEARCH.md`
- `sources.json`
- `run_manifest.json`
- `findings.jsonl`
- `provenance.json`
- `quality_report.json`
- `context.json`

## Use this skill when
- the task is a new project or materially new project direction;
- external platforms, APIs, protocols, formats, tools, workflows, regulations, or market context matter;
- a few strong reference points would improve planning;
- uncertainty is high enough that bounded research is justified.

## Do not use this skill when
- the task is a tiny local edit;
- the topic is already well covered by local memory and prior artifacts;
- you only need to continue implementation of an already approved plan without meaningful scope change.

## Core policy
1. **Memory first**  
   Check local memory, local artifacts, prior decisions, and topic files before external search.
2. **Bounded research**  
   Default to `quick`, not `deep`.
3. **Structured artifacts**  
   Important outputs must be schema-shaped, not ad-hoc prose.
4. **Provenance required**  
   Findings must be attributable to a source bucket or local memory.
5. **Planning handoff**  
   Research must improve `PROJECT_PLAN.md`, not replace it.
6. **Dual-mode compatibility**  
   Artifact shape, validator logic, eval logic, and quality gates must remain compatible with both `chatgpt_codex` and `openai_api`.

## Execution modes

### chatgpt_codex
Use when:
- the user is driving the work manually;
- ChatGPT / Codex is the primary execution interface;
- artifact production is local and interactive;
- no API key should be mandatory;
- background automation is not required.

Expected semantics:
- `execution_mode = "chatgpt_codex"`
- `model_access_layer = "interactive_chatgpt_or_codex"`
- `human_in_loop = true`
- `requires_api_key = false`
- `supports_background_automation = false`

### openai_api
Use when:
- the server or workflow engine must call the model directly;
- jobs run through scripts, orchestration, queues, webhooks, or schedulers;
- API billing and credentials are acceptable;
- background automation is required.

Expected semantics:
- `execution_mode = "openai_api"`
- `model_access_layer = "server_side_openai_api"`
- `human_in_loop = true/false` depending on workflow
- `requires_api_key = true`
- `supports_background_automation = true`

## Research modes

### none
Use only local memory and existing artifacts.

### quick
Default mode.  
Budget target:
- metadata candidates: up to 6
- deep inspections: up to 3
- similar solutions in summary: 2–3
- official sources: 1–2
- recurring risks: 3–5

### deep
Use only if quick mode is insufficient.  
Budget target:
- metadata candidates: up to 10
- deep inspections: up to 6
- similar solutions in summary: 4–6
- official sources: 2–4
- recurring risks: 5–10

## Required quality rules
- Every bucket in `search_targets` must have a corresponding `query_sets` entry.
- Boilerplate local memory must not dominate `local_memory_summary`.
- `sources.json` must not pretend to contain research if `sources` is empty.
- `starting_approach` must be specific enough to influence planning.
- Anti-patterns must be explicit.
- Execution-mode differences must not break artifact compatibility.
- Validators and evals must remain shared unless a mode-specific exception is explicitly documented.

## Research prompt standard
Research prompts must be **dual-mode-safe**.

A correct prompt must preserve both:
- `chatgpt_codex`
- `openai_api`

while keeping:
- artifact contracts shared
- provenance shared
- validator shared
- eval shared
- regression shared

Avoid prompts that force API-only assumptions unless the task is explicitly API-only.

## Success criteria
The skill is successful if it:
- stays bounded;
- uses local context first;
- produces structured artifacts;
- records provenance and confidence;
- improves the next planning step;
- avoids unnecessary expansion of scope;
- remains usable in both `chatgpt_codex` and `openai_api` modes.

## Planned companion files
- `skill.json`
- `schemas/*.json`
- `policies/*.md`
- `evals/*`
- `scripts/validate_skill.py`

## Design rule for this project
Start in `chatgpt_codex` if needed.
Upgrade later to `openai_api` if needed.
Do not redesign the whole research stack when changing model access strategy.