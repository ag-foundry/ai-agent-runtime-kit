# Reconstruct

## Purpose

Use this repository to rebuild the public, reusable AI-agent runtime kit on another Linux server without importing the maintainer's private operational topics.

## Reconstruction Outline

```bash
export AGENT_REPO_ROOT="${AGENT_REPO_ROOT:-/home/agent/agents}"
export AGENT_BIN_DIR="${AGENT_BIN_DIR:-/home/agent/bin}"

git clone https://github.com/ag-foundry/ai-agent-runtime-kit.git "$AGENT_REPO_ROOT"
cd "$AGENT_REPO_ROOT"
bash _runtime/tools/runtime-sync-flow.sh
```

Then verify:

- `_shared/README.md`
- `core/README.md`
- `OPERATOR-MODES.md`
- `_runtime/RUNTIME_SYNC_WORKFLOW.md`

## Recovery Boundary

This public repo is enough to reconstruct the reusable runtime kit.
It is not the maintainer's full private recovery source.

## Intentionally Excluded

- personal topic history
- private memory and vault material
- private operational traces
- private auth material
- internal-only recovery lineage

## When The Private Canonical Repo Is Still Needed

Use the private canonical repo when the goal is full owner recovery or restoration of internal historical continuity.
