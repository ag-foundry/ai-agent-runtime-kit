# Runtime Canonical Layer

## Purpose

This directory stores the canonical repository copy of the protected live runtime used by the AI-agent server project.

It exists to solve a specific operational problem:

- the live runtime must remain executable and editable on the server
- the repository must still reflect the verified operational state
- raw operational clutter must not become the default repository state
- compact runtime metadata should be available without depending on raw ad hoc inspection
- governance status should be visible through one short operational snapshot
- a top-level governance wrapper should be available for short operational control

This layer provides a controlled bridge between the live runtime and git.

---

## Current Operational Model

Live runtime remains here:

`/home/agent/bin`

Canonical repository copy lives here:

`/home/agent/agents/_runtime/canonical`

Current safe workflow:

`/home/agent/bin -> _runtime/canonical -> git`

Meaning:

1. changes are made and validated in the live runtime
2. verified protected files are synced into the canonical repository copy
3. compact manifest metadata is refreshed
4. compact registry metadata is refreshed
5. commit readiness is checked
6. governance state can be reviewed in one short snapshot
7. a top-level governance wrapper can refresh canonical runtime state, rebuild compact manifest and compact registry, and run governance review
8. only then are changes committed to git

This is a guardrail workflow, not a lock-in mechanism.

---

## Directory Layout

- `canonical/` — canonical repository copy of protected runtime files
- `canonical/bin/` — synced protected runtime files
- `canonical/meta/` — protected set manifests, hashes, and compact runtime metadata
- `tools/` — operational sync, manifest, registry, readiness, governance, and wrapper tools

---

## Working Rule

Do not use `_runtime/canonical/bin` as the primary editing location.

Primary editing and execution remain in:

`/home/agent/bin`

The canonical copy is refreshed from the verified live runtime.

---

## Required Workflow

After changing protected runtime files in `/home/agent/bin`, follow the runtime sync workflow documented here:

`/home/agent/agents/_runtime/RUNTIME_SYNC_WORKFLOW.md`

That file is the short operational checklist for:

- what to run after runtime changes
- what order to use
- what counts as commit readiness
- what blocks commit

---

## Compact Manifest Layer

The canonical runtime layer also includes compact machine-readable metadata:

`/home/agent/agents/_runtime/canonical/meta/runtime-manifest.json`

This manifest is built by:

`/home/agent/agents/_runtime/tools/build-runtime-manifest.py`

The manifest summarizes:

- protected file count
- live file presence
- canonical file presence
- per-file hashes
- parity between live and canonical protected files
- compact sync status for registry and governance work

Important behavior:

- the manifest builder is idempotent
- it does not rewrite the manifest file for timestamp-only noise
- it should not introduce unnecessary git churn when runtime state is unchanged

Expected healthy result:

- `MANIFEST_OK`
- `MANIFEST_STATUS=IN_SYNC`

---

## Compact Registry Layer

The canonical runtime layer also includes compact machine-readable metadata:

`/home/agent/agents/_runtime/runtime-registry.json`

This registry is built by:

`/home/agent/agents/_runtime/tools/build-runtime-registry.py`

The registry summarizes:

- required runtime docs presence
- required runtime tools presence
- required tool executability where applicable
- manifest health for governance use
- structural runtime governance health

Important behavior:

- the registry builder is part of the protected runtime control plane
- it is rebuilt after manifest refresh
- it is used by governance-aware status checks
- it should describe the current governed runtime layer, not an aspirational one

Expected healthy result:

- `REGISTRY_OK`
- `REGISTRY_STATUS=HEALTHY`

---

## Tools

### Sync Tool

Path:

`/home/agent/agents/_runtime/tools/sync-protected-runtime.sh`

Purpose:

- copy the protected working set from live runtime into canonical copy
- refresh hashes
- verify parity between live and canonical protected files

Expected success signal:

`HASH_OK`

### Status Tool

Path:

`/home/agent/agents/_runtime/tools/status-protected-runtime.sh`

Purpose:

- detect drift between live protected runtime and canonical repository copy
- show whether canonical state is aligned with live verified state

Expected healthy signal:

`STATUS=IN_SYNC`

### Manifest Builder

Path:

`/home/agent/agents/_runtime/tools/build-runtime-manifest.py`

Purpose:

- build or refresh compact runtime metadata in `canonical/meta/runtime-manifest.json`
- summarize file presence, hashes, and parity state
- provide a compact manifest layer for registry and governance work

Expected healthy signals:

- `MANIFEST_OK`
- `MANIFEST_STATUS=IN_SYNC`

### Registry Builder

Path:

`/home/agent/agents/_runtime/tools/build-runtime-registry.py`

Purpose:

- build or refresh compact runtime metadata in `_runtime/runtime-registry.json`
- summarize required docs presence
- summarize required tools presence
- verify tool executability where applicable
- summarize manifest health for governance use
- provide a compact registry layer for status and governance checks

Expected healthy signals:

- `REGISTRY_OK`
- `REGISTRY_STATUS=HEALTHY`

### Readiness Helper

Path:

`/home/agent/agents/_runtime/tools/runtime-commit-readiness.sh`

Purpose:

- run protected runtime status review
- summarize current git working tree state
- show whether the repo is ready for a runtime-related commit
- highlight blockers or review conditions before commit

Expected outputs include:

- `COMMIT_READINESS=READY`
- `COMMIT_READINESS=REVIEW`
- `COMMIT_READINESS=BLOCK`

### Runtime Sync Flow

Path:

`/home/agent/agents/_runtime/tools/runtime-sync-flow.sh`

Purpose:

- run protected runtime sync
- build or refresh compact runtime manifest
- build or refresh compact runtime registry
- run commit-readiness review
- provide one short operational path after file-specific validation is already done

Expected outputs include:

- `FLOW_RESULT=OK`
- `FLOW_RESULT=BLOCK`

Important rule:

This wrapper does **not** replace file-specific validation such as:

- `bash -n`
- `python3 -m py_compile`
- smoke checks
- regression checks

Run those first. Then run the wrapper.

Current short wrapper path:

`validate -> sync -> manifest -> registry -> readiness`

### Governance Status Helper

Path:

`/home/agent/agents/_runtime/tools/runtime-governance-status.sh`

Purpose:

- provide one compact governance snapshot for the runtime layer
- check whether protected runtime is in sync
- check whether the compact runtime manifest exists and is healthy
- check whether the compact runtime registry exists and is healthy
- check whether the required governance docs are present
- summarize current git working tree state
- classify the overall governance state

Expected outputs include:

- `GOVERNANCE_STATUS=HEALTHY`
- `GOVERNANCE_STATUS=REVIEW`
- `GOVERNANCE_STATUS=BLOCK`

Use this helper when you want one short high-level status view of the runtime governance layer.

This helper reads the registry layer.

### Governance Flow Wrapper

Path:

`/home/agent/agents/_runtime/tools/runtime-governance-flow.sh`

Purpose:

- provide one top-level governance wrapper for the runtime layer
- support two modes:
  - `status` — run only the governance status snapshot
  - `refresh` — refresh canonical runtime state, rebuild compact manifest, rebuild compact registry, then run governance status snapshot

Expected outputs include:

- `GOVERNANCE_FLOW=OK`
- `GOVERNANCE_FLOW=BLOCK`

Important rule:

In `refresh` mode this wrapper does **not** replace file-specific validation such as:

- `bash -n`
- `python3 -m py_compile`
- smoke checks
- regression checks

Run those first. Then use refresh mode.

Refresh mode is governance-oriented, not commit-readiness-oriented.

Use this helper when you want one top-level operational control entry point for the runtime governance layer.

Current refresh path:

`validate -> sync -> manifest -> registry -> governance snapshot`

---

## Commit Readiness Baseline

A runtime-related commit is not ready unless all of the following are true:

- relevant runtime validation passed
- required smoke or regression checks passed when applicable
- sync tool completed successfully
- manifest builder completed successfully
- manifest status is `IN_SYNC`
- registry builder completed successfully
- registry status is `HEALTHY`
- status tool returns `STATUS=IN_SYNC` when explicitly used
- readiness helper does not block the commit
- git contains only intended changes
- raw operational dumps are not being committed accidentally

For the short checklist, use:

`/home/agent/agents/_runtime/RUNTIME_SYNC_WORKFLOW.md`

---

## Short Standard Path

The current short standard path is:

1. edit live runtime
2. run file-specific validation
3. run `runtime-sync-flow.sh`
4. review git diff and git status
5. commit
6. push

Expanded meaning:

`validate -> sync -> manifest -> registry -> readiness -> review git -> commit/push`

---

## Governance Snapshot Path

When you want one short high-level status check for the whole runtime governance layer:

1. run `runtime-governance-status.sh`
2. inspect `GOVERNANCE_STATUS`
3. fix blockers or review git state if needed

This path does not replace the normal runtime change workflow.

It gives a compact answer to:

- is protected runtime aligned
- is manifest healthy
- is registry healthy
- are required docs present
- is repo clean or not

---

## Top-Level Governance Flow Path

When you want one top-level governance wrapper:

1. use `runtime-governance-flow.sh status` for status-only
2. use `runtime-governance-flow.sh refresh` after file-specific validation
3. inspect `GOVERNANCE_FLOW` and downstream signals
4. review git state before commit

This path does not replace file-specific validation.

In refresh mode, it represents the short top-level operational flow:

`validate -> sync -> manifest -> registry -> governance snapshot`

---

## What This Layer Is Not

This layer does not:

- replace the live runtime
- force execution from the repository
- require immediate archive removal from `/home/agent/bin`
- prohibit future workflow evolution
- prohibit future modularization or runtime relocation if later justified

It is a current safe control layer.

---

## Current Governance Rule

Until superseded by a better verified workflow, the project rule is:

1. edit live runtime
2. validate
3. sync canonical copy
4. refresh compact manifest
5. refresh compact registry
6. confirm readiness
7. review git
8. commit

Governance snapshot rule:

1. run `runtime-governance-status.sh`
2. inspect `GOVERNANCE_STATUS`
3. resolve blockers or review git state when needed

Top-level governance flow rule:

1. use `runtime-governance-flow.sh status` for status-only
2. use `runtime-governance-flow.sh refresh` after validation
3. inspect `GOVERNANCE_FLOW`
4. resolve blockers or review git state when needed

---

## Related Materials

- `RUNTIME_SYNC_WORKFLOW.md`
- `canonical/meta/protected-working-set.txt`
- `canonical/meta/src-from-bin.sha256`
- `canonical/meta/canonical.sha256`
- `canonical/meta/runtime-manifest.json`
- `runtime-registry.json`
- `tools/sync-protected-runtime.sh`
- `tools/status-protected-runtime.sh`
- `tools/build-runtime-manifest.py`
- `tools/build-runtime-registry.py`
- `tools/runtime-commit-readiness.sh`
- `tools/runtime-sync-flow.sh`
- `tools/runtime-governance-status.sh`
- `tools/runtime-governance-flow.sh`
- `core/DECISIONS/ADR-2026-03-24-runtime-canonical-and-artifact-retention.md`