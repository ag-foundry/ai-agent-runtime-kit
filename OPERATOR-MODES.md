# Operator Modes

## Required Core Runtime Pieces

- Linux server
- Bash
- Python 3
- repository checkout
- writable runtime bin directory
- runtime sync flow under `_runtime/tools/`

## Primary Human Entry

When Codex is available, the primary human entry path is:

- `codex-frontdoor-preflight`

This is the chat-oriented helper for substantial work that should route through the managed stack.

## Required Compatibility CLI

For automation, fallback operation, or environments without Codex chat, the required CLI entrypoint is:

- `agent-exec`

## Optional Operator Workflows

- VS Code
- Codex extension or Codex environment
- Obsidian
- MCP servers and connector integrations
- graph/vector helper services

## Practical Rule

Use Codex plus `codex-frontdoor-preflight` when you want the primary human workflow.
Use `agent-exec` when you need compatibility, automation, or non-chat entry.
