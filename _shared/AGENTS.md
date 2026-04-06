# Shared Project Rules

Status: durable-shared-layer
Updated: 2026-04-06
Scope: `/home/agent/agents`

This file is the shared repo rule layer.

Higher-precedence agent-wide communication and safety rules live in `/home/agent/.codex/AGENTS.md`.
Topic-specific direction belongs in the active topic `AGENTS.md` and, where present, its steering document.

## Global language policy

- Always answer the user in Russian by default across all tasks and repositories, even if the task prompt, requested output contract, section titles, examples, field names, repository context, filenames, or code are in English.
- Do not switch to English merely because the prompt, template, headings, labels, or requested response format is written in English.
- Keep all user-facing explanations, summaries, verdicts, pass/fail labels, next steps, clarifying questions, and final answer blocks in Russian by default.
- If a requested output format uses English headings or labels, convert the user-facing response to Russian while preserving technical literals as needed.
- Switch to another language only if the user explicitly asks for it.
- Keep filenames, paths, commands, code, JSON/YAML keys, commit messages, and technical artifact contents in the project's original language when appropriate.
- Do not translate filenames, paths, commands, code, JSON/YAML keys, or other technical file contents solely to match the response language.

## Shared workflow

- Work from a topic directory under `/home/agent/agents/<topic>/`.
- Before a major phase, a new control-plane layer, or a cross-topic change, read the active topic `AGENTS.md` and its steering document if one exists.
- Keep verification commands and rollback commands with the work they describe.
- Preserve rollback paths for any non-trivial change.
- After each major phase, run a short writeback classification across `LOG.md`, `TODO.md`, `memory/index.md`, `memory/facts.md`, `memory/lessons.md`, topic steering, topic `AGENTS.md`, or keep the result in `artifacts/` and `runs/` only.
- Routine minimum after a major phase: record the checkpoint in `LOG.md`, update the next required step or blocker in `TODO.md`, and add a durable pointer in `memory/index.md` when a primary artifact or rollback pack was created.

## Codex frontdoor binding

- This file is also the live Codex operator layer because `/home/agent/.codex/AGENTS.md` points here; treat the rules below as active inside Codex chat, not as documentation only.
- Keep ordinary casual dialogue local inside the current Codex chat when no substantial work is needed.
- Before substantial work in Codex chat, run `/home/agent/bin/codex-frontdoor-preflight` with the user’s natural-language request.
- Treat substantial work as the default for multi-step analysis, code changes, review/current/compare/clean-rerun/eval/promotion/bootstrap/migration requests, research/search work, and server/router/receiver/vpn operational work.
- Use the resulting `codex-frontdoor-contract.json`, `ai-meta-launch-manifest.json`, `ai-meta-launch-trace.json`, and managed memory selection as the routing contract for the rest of the task.
- If the frontdoor contract selects `managed_backend`, `current_state_backend`, or `research_backend`, follow that backend path unless an explicit override is justified.
- If the frontdoor contract selects `codex_chat_local`, stay in the current Codex conversation and execute the work here using the selected memory/tool/skill decisions instead of spawning a parallel Codex mode by default.
- If the contract cannot be produced because the platform/runtime is unavailable, say so briefly, continue with the strongest grounded fallback, and keep the limitation explicit in the trace or final report.
- Direct component invocation, positional compatibility mode, and legacy runners remain compatibility or override paths, not the default Codex-frontdoor route.

## Truth model

- `canonical`: maintained source-of-record artifacts such as live repo rules, topic steering, ADRs, source files, scripts, manifests, contracts, and other accepted project records.
- `derived`: status summaries, retrieval answers, research snapshots, generated verification artifacts, promotion reports, rollback packs, and vault notes.
- `ephemeral`: scratch outputs, `/tmp/*`, temporary registries, and isolated one-off workspaces.
- Do not promote a derived artifact to canonical truth unless a deliberate follow-up phase makes that change explicit.

## Truth hierarchy discipline

- Prefer the freshest grounded layer for current operational status.
- Prefer validated research artifacts for older background and source-backed synthesis.
- Treat vault notes as human-readable support, not canonical project truth.
- Treat generated runs, reports, and checklists as evidence or orientation, not as source of truth by default.

## Anti-bloat discipline

- Keep the control plane lighter than the execution plane.
- Do not add a new registry, checklist, report, or steering file unless it reduces repeated manual work or protects a live path.
- When a lighter marker or derived artifact is sufficient, do not create another durable governance layer.
