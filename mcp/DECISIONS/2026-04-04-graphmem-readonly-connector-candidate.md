# ADR: graphmem-readonly connector candidate

Status: accepted-candidate
Date: 2026-04-04
Topic: mcp

## Context

- `research-brain-v2` cross-topic smoke for `mcp` recommended one explicit connector candidate from a real need.
- The same steering explicitly blocked a broad MCP framework and multiple parallel connector lines.
- `openclaw-retrieval-bridge` and `openclaw-vault-read-bridge` already work as public bridges, so they are weak first candidates.
- `openclaw-vault-write-bridge` is higher risk and not suitable for the first MCP connector line.
- The local stack already exposes `Neo4j` on `127.0.0.1:7687`.
- Existing runtime entrypoints already show a safe auth-discovery pattern:
  - `agent-exec` reads `NEO4J_AUTH` from `docker inspect ai-neo4j`
  - `graphmem-recall` provides a read-only recall path
  - `graphmem stats` provides bounded health visibility

## Decision

Choose `graphmem-readonly` as the first explicit MCP connector candidate.

This candidate is intentionally narrow:

- read-only only
- topic-local only
- no new framework
- no arbitrary Cypher
- no write path

## Rights

Allowed for the candidate:

- `graphmem stats`
- `graphmem-recall <query>`
- ephemeral auth discovery from `docker inspect ai-neo4j`

Not allowed for the candidate:

- `graphmem init`
- `graphmem ingest`
- arbitrary `graphmem query`
- any vault write path
- any broad registry or manager for multiple MCP servers

## Shortlist

Allow now:

- `graphmem-readonly`

Conditional later:

- `memory-readonly-qdrant`
- `searxng-readonly-search`

Deny now:

- `openclaw-retrieval-bridge`
- `openclaw-vault-read-bridge`
- `openclaw-vault-write-bridge`
- `graphmem-full-cypher`
- `github-admin`

## Why this candidate first

- It solves a real local gap without duplicating an existing public bridge.
- It fits the least-privilege MCP profile required by the topic rules.
- It can be smoke-tested with read-only commands and ephemeral credentials.
- It stays within `mcp` bounds and does not reopen broad memory work.

## Minimal implementation contour

If the next step is explicitly approved later, implement only this:

1. One topic-local `graphmem-readonly` MCP wrapper.
2. One tool for graph stats.
3. One tool for graph recall by query string.
4. Ephemeral `NEO4J_AUTH` discovery from `docker inspect ai-neo4j`.
5. No arbitrary Cypher input.
6. Fail closed if auth discovery or the Neo4j container is unavailable.

## Safe smoke test

Use:

- `/home/agent/agents/mcp/artifacts/2026-04-04-mcp-explicit-connector-candidate-v1/safe_smoke.sh`

Expected behavior:

- no writes
- no persisted secrets
- output files stored only under `mcp/artifacts`

## Risks and mitigations

- Risk: accidental drift into arbitrary database access.
  - Mitigation: do not expose raw Cypher or `graphmem query`.
- Risk: secret persistence.
  - Mitigation: export auth only for the child process and do not write it to artifacts.
- Risk: scope creep into a general MCP framework.
  - Mitigation: keep a single connector candidate and a single smoke path.

## Rollback

- rollback manifest: `/home/agent/agents/mcp/runs/2026-04-04-mcp-explicit-connector-candidate-v1/rollback-pack/manifest.json`
- rollback command: `bash /home/agent/agents/mcp/runs/2026-04-04-mcp-explicit-connector-candidate-v1/rollback-pack/rollback.sh`
