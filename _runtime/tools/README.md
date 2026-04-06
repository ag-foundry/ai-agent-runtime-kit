# Runtime Tools

## Purpose

This directory contains helper scripts for maintaining the protected runtime relationship between:

- live runtime: `/home/agent/bin`
- canonical repository copy: `/home/agent/agents/_runtime/canonical`

These tools support the current safe workflow:

`/home/agent/bin -> _runtime/canonical -> git`

They are operational guardrails, not architectural lock-in.

---

## Tools

### `sync-protected-runtime.sh`

Path:

`/home/agent/agents/_runtime/tools/sync-protected-runtime.sh`

Purpose:

- copy the protected working set from `/home/agent/bin` into `_runtime/canonical/bin`
- refresh canonical hash manifests
- verify parity between live protected files and canonical protected files

Use this after:

- updating protected runtime files in `/home/agent/bin`
- validating changed files
- running relevant smoke or regression checks when needed

Expected success signal:

`HASH_OK`

---

### `status-protected-runtime.sh`

Path:

`/home/agent/agents/_runtime/tools/status-protected-runtime.sh`

Purpose:

- check whether the protected working set in `/home/agent/bin` matches `_runtime/canonical/bin`
- show whether canonical runtime state is aligned with the live verified runtime

Possible results:

- `STATUS=IN_SYNC`
- `STATUS=DRIFT`
- `STATUS=BROKEN`

Use this before staging runtime-related repository changes when you need an explicit parity check.

Expected healthy result:

`STATUS=IN_SYNC`

---

### `build-runtime-manifest.py`

Path:

`/home/agent/agents/_runtime/tools/build-runtime-manifest.py`

Purpose:

- build a compact machine-readable manifest for the protected runtime set
- write or refresh:

`/home/agent/agents/_runtime/canonical/meta/runtime-manifest.json`

- summarize parity, missing files, and per-file hashes
- provide a stable manifest layer for registry, inventory, and governance work

Expected result lines:

- `MANIFEST_OK`
- `MANIFEST_STATUS=IN_SYNC` or `MANIFEST_STATUS=DRIFT`

Important behavior:

- the manifest builder is idempotent
- it does not rewrite the manifest file when only volatile timestamp noise would change
- it should not create unnecessary git churn when runtime state is unchanged

Use this after sync and before registry/readiness review.

---

### `build-runtime-registry.py`

Path:

`/home/agent/agents/_runtime/tools/build-runtime-registry.py`

Purpose:

- build a compact machine-readable registry for the protected runtime layer
- write or refresh:

`/home/agent/agents/_runtime/runtime-registry.json`

- summarize whether required runtime docs are present
- summarize whether required runtime tools are present
- verify executability of runtime tools where applicable
- summarize manifest health from a governance point of view
- provide one compact registry layer for runtime status and governance checks

Expected healthy result lines:

- `REGISTRY_OK`
- `REGISTRY_STATUS=HEALTHY`

Important behavior:

- the registry builder is part of the protected runtime control plane
- it should be rebuilt after manifest refresh, before readiness or governance review
- it should describe the current governed runtime layer, not an aspirational one

Use this after manifest build and before readiness/governance review.

---

### `runtime-commit-readiness.sh`

Path:

`/home/agent/agents/_runtime/tools/runtime-commit-readiness.sh`

Purpose:

- run the protected runtime status check
- summarize current git working tree state
- show whether the repo is ready for a runtime-related commit
- highlight blockers or review conditions before commit

Possible readiness results:

- `COMMIT_READINESS=READY`
- `COMMIT_READINESS=REVIEW`
- `COMMIT_READINESS=BLOCK`

Typical behavior:

- `READY` means canonical runtime is in sync and the repo has intended changes with no extra review blockers
- `REVIEW` means canonical runtime is in sync, but untracked files or other review items still need attention
- `BLOCK` means commit should not proceed yet

Typical blocker examples:

- status tool failed
- runtime is not in sync
- there are no repo changes to commit

---

### `runtime-sync-flow.sh`

Path:

`/home/agent/agents/_runtime/tools/runtime-sync-flow.sh`

Purpose:

- run protected runtime sync
- build or refresh the compact runtime manifest
- build or refresh the compact runtime registry
- immediately run commit-readiness review
- provide one short wrapper flow after file-specific validation is already done

Flow results:

- `FLOW_RESULT=OK`
- `FLOW_RESULT=BLOCK`

Important rule:

This wrapper does **not** replace:

- `bash -n`
- `python3 -m py_compile`
- smoke checks
- regression checks

Run file-specific validation first. Then run the wrapper.

Typical behavior:

- `FLOW_RESULT=OK` means sync succeeded, manifest build succeeded, registry build succeeded, and readiness helper completed without hard blockers
- `FLOW_RESULT=BLOCK` means the flow must stop and blockers must be fixed first

Current wrapper path:

`validate -> sync -> manifest -> registry -> readiness`

---

### `runtime-governance-status.sh`

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

Possible governance results:

- `GOVERNANCE_STATUS=HEALTHY`
- `GOVERNANCE_STATUS=REVIEW`
- `GOVERNANCE_STATUS=BLOCK`

Typical behavior:

- `HEALTHY` means protected runtime is in sync, manifest is present and healthy, registry is present and healthy, required docs are present, and the repo is clean
- `REVIEW` means the governance layer is structurally healthy, but git state still needs review
- `BLOCK` means runtime sync, manifest, registry, or required docs are not in an acceptable state

This helper reads the runtime registry layer.

Use this when you want one short operational status view of the whole runtime governance layer.

---

### `runtime-governance-flow.sh`

Path:

`/home/agent/agents/_runtime/tools/runtime-governance-flow.sh`

Purpose:

- provide one top-level governance wrapper for the runtime layer
- support two modes:
  - `status` — run only the governance status snapshot
  - `refresh` — refresh canonical runtime state, rebuild compact manifest, rebuild compact registry, then run governance status snapshot

Flow results:

- `GOVERNANCE_FLOW=OK`
- `GOVERNANCE_FLOW=BLOCK`

Important rule:

In `refresh` mode this wrapper does **not** replace:

- `bash -n`
- `python3 -m py_compile`
- smoke checks
- regression checks

Run file-specific validation first. Then use refresh mode.

Refresh mode is governance-oriented, not commit-readiness-oriented.

Typical behavior:

- `status` mode gives one short governance snapshot
- `refresh` mode gives a top-level flow:
  `validate -> sync -> manifest -> registry -> governance snapshot`
- `GOVERNANCE_FLOW=BLOCK` means sync, manifest, registry, or governance blockers still need to be fixed

---

## Standard Paths

### Standard runtime path

`validate -> sync -> manifest -> registry -> readiness -> review git -> commit/push`

### Standard governance refresh path

`validate -> sync -> manifest -> registry -> governance snapshot`

---

## Recommended Order After Runtime Changes

### Option A — explicit step-by-step

After changing protected runtime files in `/home/agent/bin`, use this order:

1. validate the changed runtime file
2. run smoke or regression when the change affects execution behavior
3. run `sync-protected-runtime.sh`
4. run `build-runtime-manifest.py`
5. run `build-runtime-registry.py`
6. run `status-protected-runtime.sh` when explicit parity confirmation is needed
7. run `runtime-commit-readiness.sh`
8. review git diff and git status
9. commit and push only when the result is acceptable

### Option B — short wrapper flow

After file-specific validation is complete:

1. run `runtime-sync-flow.sh`
2. review git diff and git status
3. commit and push only when the result is acceptable

### Option C — governance snapshot

When you want one short high-level status check for the whole runtime governance layer:

1. run `runtime-governance-status.sh`
2. inspect `GOVERNANCE_STATUS`
3. fix blockers or review git state if needed

### Option D — top-level governance flow

When you want one top-level wrapper:

1. use `runtime-governance-flow.sh status` for status-only
2. use `runtime-governance-flow.sh refresh` after file-specific validation
3. inspect `GOVERNANCE_FLOW` and downstream signals
4. review git state before commit

For the short checklist and commit criteria, see:

`/home/agent/agents/_runtime/RUNTIME_SYNC_WORKFLOW.md`

---

## Quick Practical Sequences

### Explicit sequence

    bash -n /home/agent/bin/<changed-shell-file>
    python3 -m py_compile /home/agent/bin/<changed-python-file>
    /home/agent/agents/_runtime/tools/sync-protected-runtime.sh
    python3 /home/agent/agents/_runtime/tools/build-runtime-manifest.py
    python3 /home/agent/agents/_runtime/tools/build-runtime-registry.py
    /home/agent/agents/_runtime/tools/status-protected-runtime.sh
    /home/agent/agents/_runtime/tools/runtime-commit-readiness.sh

### Wrapper sequence

    bash -n /home/agent/bin/<changed-shell-file>
    python3 -m py_compile /home/agent/bin/<changed-python-file>
    /home/agent/agents/_runtime/tools/runtime-sync-flow.sh

### Governance snapshot

    /home/agent/agents/_runtime/tools/runtime-governance-status.sh

### Top-level governance flow

    /home/agent/agents/_runtime/tools/runtime-governance-flow.sh status
    /home/agent/agents/_runtime/tools/runtime-governance-flow.sh refresh

Run only the validation steps that are relevant to the changed file type.

---

## Interpretation Guide

### Good state

A healthy runtime-related commit path usually looks like this:

- sync tool returns `HASH_OK`
- manifest builder returns `MANIFEST_OK`
- manifest builder returns `MANIFEST_STATUS=IN_SYNC`
- registry builder returns `REGISTRY_OK`
- registry builder returns `REGISTRY_STATUS=HEALTHY`
- status tool returns `STATUS=IN_SYNC` when run explicitly
- readiness helper returns `COMMIT_READINESS=READY` or a clearly understood `REVIEW`
- wrapper returns `FLOW_RESULT=OK` when used
- governance helper returns `GOVERNANCE_STATUS=HEALTHY` when the repo is clean
- governance flow returns `GOVERNANCE_FLOW=OK`
- git contains only intended changes

### Do not commit when

- `MANIFEST_STATUS` is not `IN_SYNC`
- `REGISTRY_STATUS` is not `HEALTHY`
- `STATUS` is not `IN_SYNC`
- readiness helper returns `BLOCK`
- wrapper returns `FLOW_RESULT=BLOCK`
- governance helper returns `GOVERNANCE_STATUS=BLOCK`
- governance flow returns `GOVERNANCE_FLOW=BLOCK`
- raw operational dumps are included by mistake
- unrelated temporary repair files are mixed into the commit
- canonical copy does not reflect the verified live runtime

---

## Working Rule

Do not treat `_runtime/canonical/bin` as the primary editing path.

Primary editing and execution remain in:

`/home/agent/bin`

The repository stores the verified canonical copy and compact metadata about it.

---

## Design Rule

These tools support the current safe workflow, but they do not define a permanent architectural lock-in.

Future work may replace or extend them with:

- stronger sync tooling
- richer manifests
- richer registries
- stronger wrapper flows
- deployment-aware workflows
- more formal runtime packaging

The rule is:

- use guardrails to prevent breakage
- keep the workflow understandable
- keep code truth and docs truth aligned
- prefer small verified improvements over clever drift