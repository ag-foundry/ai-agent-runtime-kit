<!-- Во имя Отца и Сына и Святаго Духа. Аминь. -->

# Core Topic Rules

Status: durable-topic-layer
Updated: 2026-04-03

Read `/home/agent/agents/core/PROJECT-STEERING.md` before major work on architecture, runtime, retrieval, research, memory, vault integration, skills, or governance.

This file is the short topic rule layer.
Long-form topic steering lives in `/home/agent/agents/core/PROJECT-STEERING.md`.

## Core rules

- Do not confuse derived layers with canonical truth.
- For current operational status, prefer `/home/agent/agents/core/artifacts/retrieval-execution/latest/ANSWER.md` over `project-state/latest.*` and older status summaries.
- Vault notes are derived human-readable recall, not canonical project truth.
- Keep new governance layers additive, minimal, and justified by repeated payoff.
- Do not break the working runtime, retrieval/vault bridges, or creator/eval/promotion path while doing control-plane work.
- When validating net-new skill usefulness, prefer file-state or bundle-state surfaces over prompt-contained contract prompts whenever the skill can inspect real artifacts by path.
- Before closing a major phase, run the writeback classification from `/home/agent/agents/core/PROJECT-STEERING.md` and promote only what became durable.
- After reading this file and the steering document, use `TODO.md`, `LOG.md`, `DECISIONS/`, and selected memory files as local execution context.

<!-- managed-default-hook -->
## Managed default path
- Server AI entrypoint: `/home/agent/bin/agent-exec`
- Codex chat preflight helper: `/home/agent/bin/codex-frontdoor-preflight`
- Managed backend launcher: `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/scripts/launch_managed_workflow.py`
- Global managed policy registry: `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/definitions/global-managed-policy-registry-v1.json`
- Global memory fabric: `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/definitions/global-managed-memory-fabric-v1.json`
- In Codex chat, substantial work should start with the preflight helper so frontdoor routing and trace are created before execution.
- Compatibility and direct script paths are exception modes, not the default route.
