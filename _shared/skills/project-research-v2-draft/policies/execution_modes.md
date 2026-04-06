# Execution Modes — Dual-Mode Contract

## Purpose

`project-research-v2-draft` must support **two execution modes** without changing the artifact contract:

1. **`chatgpt_codex`**
   - User works through ChatGPT Pro / Codex.
   - Human-in-the-loop workflow.
   - No mandatory OpenAI API backend.
   - Good for interactive research, terminal-driven work, VS Code, manual review, and semi-automated pipelines.

2. **`openai_api`**
   - Server-side or tool-side workflow via OpenAI API.
   - Intended for automation, scheduled runs, webhooks, orchestration graphs, and machine-triggered execution.
   - Requires API credentials and API billing.
   - Recommended OpenAI integration path: Responses API.

These modes must be treated as **different model access layers**, not different research products.

---

## Core Rule

The following must remain **shared across both modes**:

- artifact structure
- context contract
- findings contract
- provenance contract
- quality gates
- validator behavior
- eval behavior
- regression behavior
- memory-first policy
- topic workspace layout

Only the **model access layer** may differ.

---

## Canonical Fields

Every future context / manifest evolution should be compatible with these fields:

### Context-level execution fields
- `execution_mode`
- `execution_mode_reason`
- `model_access_layer`
- `human_in_loop`
- `requires_api_key`
- `supports_background_automation`

### Recommended semantics

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

---

## Research Prompt Policy

All future research prompts must be written in a **dual-mode-safe** way.

### Bad prompt style
Prompts that assume only one backend, for example:
- “build only around OpenAI Responses API”
- “the system must require API keys”
- “the architecture assumes server-side model calls only”

### Good prompt style
Prompts that explicitly preserve both execution modes.

### Canonical universal research prompt template

> Research a production-ready AI-agent server/workflow architecture that supports two execution modes:
> 1) `chatgpt_codex` — human-in-the-loop workflow using ChatGPT Pro / Codex without requiring a dedicated OpenAI API backend,
> 2) `openai_api` — server-side workflow using OpenAI API for automation and orchestration.
>
> Keep artifact contracts, validation, provenance, memory, evals, and quality gates shared across both modes.
> Isolate only the model access layer and execution-path differences.
> Prefer architectures that can start in `chatgpt_codex` mode and later upgrade to `openai_api` mode without rewriting the research/validation stack.

---

## Architectural Rule

The project should be designed as:

- **Shared core**
  - project classification
  - memory-first precheck
  - search targets
  - source selection
  - findings
  - provenance
  - quality gates
  - evals
  - regression

- **Mode-specific adapter layer**
  - `chatgpt_codex` adapter
  - `openai_api` adapter

This means:
- do **not** fork the whole project into two separate systems
- do **not** duplicate validator/eval logic by mode unless strictly necessary
- do **not** make API usage mandatory for the entire project

---

## Practical Meaning for This Project

### `chatgpt_codex` mode
Use this mode when:
- user is driving the work manually
- work happens in ChatGPT + Codex + terminal + VS Code
- artifacts are still generated locally
- review and approval happen manually
- server automation is optional or absent

### `openai_api` mode
Use this mode when:
- the server must call models by itself
- jobs run from scripts, queues, agents, n8n, LangGraph, schedulers, or webhooks
- API keys and usage metering are acceptable
- background execution is needed

---

## File-Level Impact

This contract must be reflected in the following files:

- `README.md`
- `SKILL.md`
- `skill.json`
- `evals/runner_eval_cases.yaml`
- `references/RUNNER_V2_ARTIFACT_CONTRACT.md`
- `references/RUNNER_V2_STATE_MODEL.md`
- `policies/quality_policy.md`
- `project-research-run` runtime behavior

---

## Migration Rule

The project must always be able to evolve in this order:

1. start in `chatgpt_codex`
2. validate artifacts / eval / regressions
3. later add `openai_api`
4. keep the same artifact and quality contracts
5. avoid redoing the whole project when switching model access strategy

That migration path is the default design target.

---

## Decision Summary

**Truth for this project:**
- ChatGPT Pro / Codex mode is a first-class mode, not a temporary hack.
- OpenAI API mode is an optional upgrade path, not a mandatory prerequisite.
- The project is dual-mode by design.