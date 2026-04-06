# Operator Modes

## Mandatory

- Linux server runtime
- Bash
- Python 3
- repository checkout at `/home/agent/agents`
- runtime sync into `/home/agent/bin`

## Primary Human Mode

- Codex chat is the primary human frontdoor
- substantial work should start with `/home/agent/bin/codex-frontdoor-preflight`

## Compatibility Mode

- `/home/agent/bin/agent-exec` remains available for automation or compatibility workflows
- direct component calls are not the default operator model

## Optional

- VS Code: optional editor/operator shell
- Codex extension or Codex environment: optional but recommended for the primary frontdoor experience
- Obsidian: optional human-readable note tooling
- MCP servers/connectors: optional, selected by policy when available
- graph/vector helper layers: optional and availability-dependent
