# AI Agent Contour Public Distribution

This repository is the clean public distribution of the AI-agent server contour.

It is intended for installation, reconstruction, and reuse on another server without exposing the owner’s private topics, personal memory, or local operational debris.

## What This System Is

This project provides a managed AI-agent server contour with:

- a Codex-first human frontdoor
- a server-side AI meta-launcher
- a canonical managed backend path
- a governed runtime mirror
- a policy registry
- a machine-readable memory fabric
- research and current-state routing
- optional MCP/tool integration surfaces
- topic bootstrap and migration support

## What Problem It Solves

It gives one governed entry contour for substantial AI work on a server so the operator does not need to remember workflow classes, manual launcher chains, or separate memory/research/tool paths.

## What This Public Repo Includes

- `_runtime/` canonical runtime representation and sync tools
- `_shared/` shared rules, templates, and research skills
- `core/` generic managed-contour logic and governance source
- `mcp/` optional generic MCP connector candidate surface
- public installation and reconstruction docs

## What This Public Repo Does Not Include

- personal or project-specific operational topics
- private memory/history
- secrets, credentials, tokens, or private auth material
- bulky run traces and local-only dumps
- unrelated future projects

## Human Entry Model

- Primary frontdoor: Codex chat
- Codex substantial-work preflight helper: `/home/agent/bin/codex-frontdoor-preflight`
- Compatibility or automation entrypoint: `/home/agent/bin/agent-exec`

## Start Here

- Installation: `INSTALL.md`
- Reconstruction: `RECONSTRUCT.md`
- Operator modes: `OPERATOR-MODES.md`
- Core steering: `core/PROJECT-STEERING.md`
