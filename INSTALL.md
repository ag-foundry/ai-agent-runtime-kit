# Install

## Intended Baseline

- Linux server with Bash and Python 3.11+
- `git`, `python3`, and standard shell utilities
- writable `/home/agent/agents` and `/home/agent/bin`

## Clone And Place

1. Clone this public repo to `/home/agent/agents`.
2. Review `_runtime/canonical` and `_runtime/tools`.
3. Sync the governed runtime into `/home/agent/bin` with `_runtime/tools/runtime-sync-flow.sh`.

## Minimal Bootstrap

1. Read `_shared/README.md`.
2. Read `core/README.md`.
3. Confirm the frontdoor scripts exist in `/home/agent/bin` after runtime sync:
   - `codex-frontdoor-preflight`
   - `agent-exec`
4. Confirm the core managed launcher paths resolve inside `core/artifacts/skills/openclaw-skill-creator-v1/scripts/`.

## Minimal Validation

1. Run `bash -n` against the runtime shell entrypoints you plan to use.
2. Run `python3 -m py_compile` on the main Python launcher/runtime scripts.
3. Run `_runtime/tools/runtime-sync-flow.sh`.
4. Run one harmless frontdoor preflight request and inspect the produced contract/trace.

## Optional Operator Tooling

- VS Code with Codex: optional but recommended for the primary human frontdoor
- Obsidian: optional for human-readable note workflows
- external connectors and MCP servers: optional and capability-dependent

## Honest Limits

This public baseline still assumes the canonical path layout `/home/agent/agents` and `/home/agent/bin`.
Relocating the tree requires a deliberate path-rewrite pass.
