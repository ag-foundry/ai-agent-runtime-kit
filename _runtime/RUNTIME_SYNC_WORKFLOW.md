# Runtime Sync Workflow

## Purpose

This document defines the short operational workflow for runtime changes in the AI-agent server project.

It answers four questions:

1. What to run after changing runtime files.
2. In what order to run checks.
3. What counts as ready for commit.
4. What blocks commit.

This is a guardrail workflow, not a lock-in mechanism.

---

## Scope

This workflow applies when the live runtime in:

`/home/agent/bin`

has been changed and the canonical repo copy in:

`/home/agent/agents/_runtime/canonical`

must be updated.

Live execution remains in `/home/agent/bin`.

The repo stores the verified canonical copy and compact runtime metadata.

---

## Operational Model

The current safe model is:

`/home/agent/bin -> /home/agent/agents/_runtime/canonical -> git`

Meaning:

1. Edit and test in live runtime.
2. Sync verified protected runtime into canonical repo copy.
3. Refresh compact manifest metadata.
4. Refresh compact registry metadata.
5. Review commit readiness.
6. Commit only after checks pass.

This is a guardrail workflow, not a lock-in mechanism.

---

## Short Checklist

Use this checklist after any runtime change.

- [ ] Runtime file change completed in `/home/agent/bin`
- [ ] Relevant syntax checks passed
- [ ] Relevant smoke or regression checks passed when needed
- [ ] Protected runtime synced into canonical copy
- [ ] Compact runtime manifest built or refreshed
- [ ] Manifest status shows `MANIFEST_STATUS=IN_SYNC`
- [ ] Compact runtime registry built or refreshed
- [ ] Registry status shows `REGISTRY_STATUS=HEALTHY`
- [ ] Readiness review completed without `BLOCK`
- [ ] Git diff reviewed
- [ ] Only intended files changed
- [ ] Commit message reflects the real change

Do not commit if any box above is still false.

---

## Standard Order of Operations

### Option A — Explicit step-by-step

### Step 1 — Edit live runtime

Make changes only in:

`/home/agent/bin`

Do not edit `_runtime/canonical/bin` directly as the primary working path.

---

### Step 2 — Run local validation

Run validation appropriate to the changed file type.

Typical examples:

- shell: `bash -n`
- python: `python3 -m py_compile`
- project-specific smoke checks
- project-specific regression checks

Validation must be relevant, not ceremonial.

If the change affects execution flow, run smoke or regression, not only syntax checks.

---

### Step 3 — Sync protected runtime

Run:

`/home/agent/agents/_runtime/tools/sync-protected-runtime.sh`

Expected result:

`HASH_OK`

A failed sync blocks commit.

---

### Step 4 — Build compact runtime manifest

Run:

`python3 /home/agent/agents/_runtime/tools/build-runtime-manifest.py`

Expected result:

- compact manifest written or refreshed at:

`/home/agent/agents/_runtime/canonical/meta/runtime-manifest.json`

- protected file count summarized
- file presence summarized
- per-file parity summarized

Expected healthy signals:

- `MANIFEST_OK`
- `MANIFEST_STATUS=IN_SYNC`

A failed manifest build blocks commit.

---

### Step 5 — Build compact runtime registry

Run:

`python3 /home/agent/agents/_runtime/tools/build-runtime-registry.py`

Expected result:

- compact registry written or refreshed at:

`/home/agent/agents/_runtime/runtime-registry.json`

- required docs presence summarized
- required tools presence summarized
- tool executability summarized where applicable
- manifest health summarized for governance use
- structural runtime governance health summarized

Expected healthy signals:

- `REGISTRY_OK`
- `REGISTRY_STATUS=HEALTHY`

A failed registry build blocks commit.

---

### Step 6 — Confirm runtime status when explicit parity confirmation is needed

Run:

`/home/agent/agents/_runtime/tools/status-protected-runtime.sh`

Expected result:

`STATUS=IN_SYNC`

Meaning:

- live protected runtime and canonical repo copy match
- no unresolved drift remains in protected files

If status returns `DRIFT` or `BROKEN`, do not commit.

Note:

The readiness helper already includes a protected runtime status review.
Run the explicit status tool when you want an additional direct parity check.

---

### Step 7 — Run commit readiness review

Run:

`/home/agent/agents/_runtime/tools/runtime-commit-readiness.sh`

Expected results include:

- `COMMIT_READINESS=READY`
- `COMMIT_READINESS=REVIEW`
- `COMMIT_READINESS=BLOCK`

Do not commit when the result is `BLOCK`.

---

### Step 8 — Review git state

Review:

- changed files
- unintended modifications
- whether the change belongs in repo
- whether raw operational dumps were introduced by mistake

Only curated and intentional changes should remain staged for commit.

---

### Step 9 — Commit and push

Commit only when all previous steps are green.

Then push normally.

---

### Option B — Short wrapper flow

After file-specific validation is complete, run:

`/home/agent/agents/_runtime/tools/runtime-sync-flow.sh`

This wrapper runs:

1. protected runtime sync
2. compact manifest build
3. compact registry build
4. commit-readiness review

It does **not** replace:

- `bash -n`
- `python3 -m py_compile`
- smoke checks
- regression checks

Run those first. Then run the wrapper.

After the wrapper:

1. review git diff and git status
2. commit

Current short wrapper path:

`validate -> sync -> manifest -> registry -> readiness`

---

### Option C — Governance snapshot

When you want one short high-level status check for the whole runtime governance layer, run:

`/home/agent/agents/_runtime/tools/runtime-governance-status.sh`

This helper is for a compact operational answer to questions like:

- is protected runtime aligned
- is manifest healthy
- is registry healthy
- are required docs present
- is repo clean or not

Expected outputs include:

- `GOVERNANCE_STATUS=HEALTHY`
- `GOVERNANCE_STATUS=REVIEW`
- `GOVERNANCE_STATUS=BLOCK`

Use this when you want status visibility, not a full runtime change flow.

---

### Option D — Top-level governance flow

When you want one top-level governance wrapper, use:

- `runtime-governance-flow.sh status` for status-only
- `runtime-governance-flow.sh refresh` after file-specific validation

In refresh mode, this wrapper runs the short governance-oriented path:

`validate -> sync -> manifest -> registry -> governance snapshot`

Expected outputs include:

- `GOVERNANCE_FLOW=OK`
- `GOVERNANCE_FLOW=BLOCK`

This wrapper does **not** replace:

- `bash -n`
- `python3 -m py_compile`
- smoke checks
- regression checks

Run validation first. Then use the wrapper.

---

## Minimal Practical Command Sequences

This is the short explicit sequence after a runtime change:

    bash -n /home/agent/bin/<changed-shell-file>
    python3 -m py_compile /home/agent/bin/<changed-python-file>
    /home/agent/agents/_runtime/tools/sync-protected-runtime.sh
    python3 /home/agent/agents/_runtime/tools/build-runtime-manifest.py
    python3 /home/agent/agents/_runtime/tools/build-runtime-registry.py
    /home/agent/agents/_runtime/tools/status-protected-runtime.sh
    /home/agent/agents/_runtime/tools/runtime-commit-readiness.sh
    cd /home/agent/agents && git status --short

This is the short wrapper sequence after file-specific validation:

    bash -n /home/agent/bin/<changed-shell-file>
    python3 -m py_compile /home/agent/bin/<changed-python-file>
    /home/agent/agents/_runtime/tools/runtime-sync-flow.sh
    cd /home/agent/agents && git status --short

This is the short governance snapshot sequence:

    /home/agent/agents/_runtime/tools/runtime-governance-status.sh

This is the short top-level governance flow sequence:

    /home/agent/agents/_runtime/tools/runtime-governance-flow.sh status
    /home/agent/agents/_runtime/tools/runtime-governance-flow.sh refresh

Use only the checks relevant to the changed file type.

Do not run fake checks just to satisfy the sequence.

---

## Examples

### Example A — Python runtime file changed

1. Edit `/home/agent/bin/some-runtime-file.py`
2. Run `python3 -m py_compile /home/agent/bin/some-runtime-file.py`
3. Run project-specific smoke or regression if execution path changed
4. Run `runtime-sync-flow.sh`
5. Review git diff
6. Commit
7. Push

### Example B — Shell runtime file changed

1. Edit `/home/agent/bin/some-script.sh`
2. Run `bash -n /home/agent/bin/some-script.sh`
3. Run smoke or regression if needed
4. Run `runtime-sync-flow.sh`
5. Review git diff
6. Commit
7. Push

### Example C — Governance refresh after runtime changes

1. Edit and validate the changed runtime file
2. Run `runtime-governance-flow.sh refresh`
3. Inspect `GOVERNANCE_FLOW`
4. Review git diff and git status
5. Commit only if downstream signals are healthy

---

## What Not To Do

Do not:

- treat `_runtime/canonical/bin` as the primary live editing path
- commit before sync, manifest refresh, registry refresh, and readiness review
- commit when manifest status is not `IN_SYNC`
- commit when registry status is not `HEALTHY`
- commit when wrapper returns `FLOW_RESULT=BLOCK`
- commit when governance status returns `GOVERNANCE_STATUS=BLOCK`
- commit when governance flow returns `GOVERNANCE_FLOW=BLOCK`
- commit raw audit, hygiene, or inventory dumps by default
- skip regression when execution logic changed materially
- mix unrelated cleanup into a runtime commit unless explicitly intended

---

## Current Project Rule

Until a future workflow supersedes this safely, the default runtime rule is:

1. change live runtime
2. validate
3. sync canonical copy
4. refresh compact manifest
5. refresh compact registry
6. confirm readiness
7. review git
8. commit
9. push

Short runtime form:

`validate -> sync -> manifest -> registry -> readiness -> review git -> commit/push`

Governance snapshot rule:

1. run `runtime-governance-status.sh`
2. inspect `GOVERNANCE_STATUS`
3. resolve blockers or review git state when needed

Top-level governance flow rule:

1. use `runtime-governance-flow.sh status` for status-only
2. use `runtime-governance-flow.sh refresh` after validation
3. inspect `GOVERNANCE_FLOW`
4. resolve blockers or review git state when needed

Short governance refresh form:

`validate -> sync -> manifest -> registry -> governance snapshot`