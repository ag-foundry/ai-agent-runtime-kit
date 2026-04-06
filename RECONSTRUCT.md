# Reconstruct

## Purpose

Use this repo to reconstruct the generic AI-agent contour on a clean or recovered server without importing the owner’s private operational topics.

## Reconstruction Outline

1. Clone the public repo to `/home/agent/agents`.
2. Sync `_runtime/canonical` into `/home/agent/bin`.
3. Verify the shared rule layer and core steering documents.
4. Confirm the managed launchers, policy registry, and memory-fabric definitions exist.
5. Recreate optional external dependencies only if needed:
   - Codex environment
   - MCP servers
   - graph/vector helper services
   - research/search backends

## Recovery Boundaries

This public repo is enough to rebuild the generic contour, but it is not the owner’s full recovery source.

It intentionally excludes:

- personal topic history
- private memory and vault material
- private operational traces
- private connector/auth state

## When To Use The Private Canonical Repo Instead

Use the private canonical repo when the goal is:

- full owner recovery
- restoration of private topic history
- recovery of internal artifacts or decision lineage
- exact continuity with the original working server
