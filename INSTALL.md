# Install

## Prerequisites

- Linux server
- Bash
- Python 3.11 or newer
- `git`
- permission to write the repository checkout and the runtime bin directory

## Recommended Default Paths

The current runtime kit works best with:

- `AGENT_REPO_ROOT=/home/agent/agents`
- `AGENT_BIN_DIR=/home/agent/bin`

You can override those in the main runtime tools with environment variables, but the default layout is still the most fully supported path.

## Clean-Server Install

```bash
export AGENT_REPO_ROOT="${AGENT_REPO_ROOT:-/home/agent/agents}"
export AGENT_BIN_DIR="${AGENT_BIN_DIR:-/home/agent/bin}"

git clone https://github.com/ag-foundry/ai-agent-runtime-kit.git "$AGENT_REPO_ROOT"
cd "$AGENT_REPO_ROOT"
mkdir -p "$AGENT_BIN_DIR"
bash _runtime/tools/runtime-sync-flow.sh
```

## Alternative Install Paths

If you do not want to use the default host layout, set your own paths first:

```bash
export AGENT_REPO_ROOT="$HOME/ai-agent-runtime-kit"
export AGENT_BIN_DIR="$HOME/.local/bin"

git clone https://github.com/ag-foundry/ai-agent-runtime-kit.git "$AGENT_REPO_ROOT"
cd "$AGENT_REPO_ROOT"
mkdir -p "$AGENT_BIN_DIR"
bash _runtime/tools/runtime-sync-flow.sh
```

## First Successful Validation

Run:

```bash
export AGENT_REPO_ROOT="${AGENT_REPO_ROOT:-/home/agent/agents}"
export AGENT_BIN_DIR="${AGENT_BIN_DIR:-/home/agent/bin}"

"$AGENT_BIN_DIR/codex-frontdoor-preflight" --help
"$AGENT_BIN_DIR/agent-exec" --help
```

Expected checkpoints:

- `runtime-sync-flow.sh` ends with `FLOW_RESULT=OK`
- the manifest step reports `MANIFEST_STATUS=IN_SYNC`
- the registry step reports `REGISTRY_STATUS=HEALTHY`
- `codex-frontdoor-preflight --help` prints the preflight usage text
- `agent-exec --help` prints the managed-entry usage text
- generated runtime metadata stays local and should not be committed back to the public repo

## What To Read Next

1. `_shared/README.md`
2. `core/README.md`
3. `OPERATOR-MODES.md`

## Required Vs Optional Tooling

Required for the runtime kit:

- Bash
- Python
- the repository checkout
- the runtime sync flow

Optional operator tooling:

- Codex-capable environment for the primary chat frontdoor
- VS Code
- Obsidian
- MCP servers and external integrations

## Honest Limits

- the kit is installable and reusable now, but not yet fully path-agnostic
- the default layout remains the strongest supported deployment path
- some deeper helper scripts still assume the default layout even though the main runtime tools now accept `AGENT_REPO_ROOT` and `AGENT_BIN_DIR`
