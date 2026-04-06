# ADR-2026-03-27: Integration Blueprint Slice After Project-State Bootstrap

## Status

Accepted

## Date

2026-03-27

## Context

The project has now closed two important groundwork slices.

First closed slice:

- runtime governance
- manifest layer
- registry layer
- registry-aware runtime documentation alignment

Second closed slice:

- project-state layer bootstrap
- protected runtime helper `project-state-refresh`
- compact current snapshot in:
  - `core/artifacts/project-state/latest.json`
  - `core/artifacts/project-state/latest.md`

Current verified repo baseline:

- branch: `main`
- head: `8c256df`

This means the project now has:

- a governed runtime layer
- a compact runtime manifest
- a compact runtime registry
- runtime sync and governance wrappers
- a compact current-state layer for the `core` topic

However, the project still lacks one explicit architecture document that connects the major subsystems into one implementation order.

The missing layer is not another runtime helper.

The missing layer is a compact integration blueprint that answers:

- what the main subsystems are
- what role each subsystem plays
- which files or services are source of truth
- how data should move between layers
- what should be implemented first
- what should explicitly wait until later
- where Obsidian and OpenClaw fit into the real system

Without this blueprint, future work risks becoming locally correct but globally fragmented.

---

## Decision

The next macro-slice after project-state bootstrap will be:

- `integration blueprint slice`

This slice will define the first compact cross-layer architecture map for the AI-agent server.

It will cover these layers together:

- runtime governance
- memory stack
- vector memory
- graph memory
- unified search / retrieval
- Obsidian vault
- OpenClaw orchestration / UI layer

This slice is primarily architectural and documentary.

It should clarify implementation order and source-of-truth rules before broader build-out continues.

---

## Scope of the Integration Blueprint Slice

The blueprint must produce one compact architecture artifact that defines:

1. the major system layers
2. the purpose of each layer
3. inputs and outputs between layers
4. current source-of-truth paths
5. boundaries between operational state, memory state, and knowledge state
6. the intended place of Obsidian
7. the intended place of OpenClaw
8. the recommended implementation order for future work

This slice is not for implementing all integrations immediately.

It is for making the next phase structurally coherent.

---

## Required Layers to Describe

### 1. Runtime Governance Layer

This layer governs the live runtime and its canonical repository copy.

It already includes:

- protected runtime set
- runtime manifest
- runtime registry
- sync flow
- governance status
- governance refresh flow

This layer is the operational execution control plane.

### 2. Project-State Layer

This layer gives compact current operational orientation for the `core` topic.

It already includes:

- current snapshot json
- current snapshot md
- protected helper `project-state-refresh`

This layer is the orientation plane, not the implementation plane.

### 3. Memory Layer

This includes:

- topic memory
- long-term memory conventions
- memory snapshot logic
- human working context

This layer stores curated working memory and project continuity.

### 4. Vector Memory Layer

This includes embedding-oriented retrieval and semantic lookup.

This layer is intended for semantic recall and evidence retrieval.

### 5. Graph Memory Layer

This includes structured relationships, entities, and linked facts.

This layer is intended for relationship-aware recall and topology of knowledge.

### 6. Unified Search / Retrieval Layer

This layer should combine:

- local memory
- vector retrieval
- graph recall
- repo/docs-first retrieval
- external retrieval when appropriate

This is the retrieval orchestration plane.

### 7. Obsidian Vault Layer

Obsidian is not treated as an unrelated notes folder.

It should be positioned as a governed knowledge surface that can interact with:

- curated notes
- memory material
- research outputs
- retrieval inputs

This layer must not silently conflict with project memory truth.

### 8. OpenClaw Layer

OpenClaw is not treated as a random extra service.

It should be positioned as the future orchestration and interaction layer that sits above:

- runtime
- memory
- retrieval
- research workflows
- possibly dashboard or control UI paths

This is the likely human-facing orchestration layer.

---

## Source-of-Truth Rule for the Blueprint

The blueprint must explicitly distinguish between:

- execution truth
- decision truth
- operational orientation truth
- memory truth
- retrieval truth
- knowledge-vault truth

The intended hierarchy remains:

1. implementation files and live system state
2. governed canonical runtime files
3. ADR decisions
4. TODO / LOG / context
5. project-state latest snapshot
6. retrieval and knowledge layers
7. UI / orchestration layers above them

Obsidian and OpenClaw must fit into this hierarchy without blurring it.

---

## Deliverables for This Slice

The slice should produce at least:

1. this ADR
2. one compact blueprint artifact
3. one clear recommended implementation order for the next major slices

Recommended artifact target:

- `core/artifacts/architecture/latest-integration-blueprint.md`

Optional later historical snapshots may follow, but the first target should stay compact.

---

## What This Slice Must Not Do

This slice must not yet become:

- a broad refactor of runtime
- an Obsidian installation sprint
- an OpenClaw installation sprint
- a premature UI build
- a large orchestration implementation
- a mass rewrite of memory tooling

This slice defines the map before the next road is built.

---

## Immediate Next Step

The next concrete step after this ADR is:

- create `core/artifacts/architecture/latest-integration-blueprint.md`

That artifact should define:

- layer map
- cross-layer data flow
- source-of-truth map
- recommended implementation order
- deferred items that should wait

---

## Consequences

### Positive consequences

- future work gets one shared architecture map
- runtime, memory, search, Obsidian, and OpenClaw are positioned in one system
- implementation order becomes clearer
- fewer local optimizations will conflict with global design

### Trade-offs

- one more maintained architecture artifact exists
- some future ideas will be deferred instead of immediately implemented
- the blueprint can become stale if later work diverges from it

This trade-off is acceptable because the artifact is compact and meant to guide sequence.

---

## Rollback

If this slice proves unhelpful, rollback is simple:

- stop treating the blueprint as active guidance
- keep the ADR as decision history
- continue from runtime/project-state truth

Rollback cost is low.

---

## Decision Summary

After project-state bootstrap, the next major slice is:

- integration blueprint

Its purpose is to connect:

- runtime governance
- project-state
- memory
- vector memory
- graph memory
- unified retrieval
- Obsidian
- OpenClaw

into one coherent architecture and one practical implementation order.

The next file to create after this ADR is:

- `core/artifacts/architecture/latest-integration-blueprint.md`