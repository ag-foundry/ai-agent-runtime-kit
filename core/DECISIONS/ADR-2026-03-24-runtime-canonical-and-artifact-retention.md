# ADR-2026-03-24: Runtime Canonical Copy and Artifact Retention Policy

## Status

Accepted

## Date

2026-03-24

## Context

The live project runtime currently operates from:

`/home/agent/bin`

This server-side runtime is real, active, and already validated by smoke checks and full regression.

At the same time, the repository did not fully reflect the real server state. The project needed a safer governance model for:

- runtime source-of-truth
- repository hygiene
- auditability
- rollback-safe cleanup
- future extensibility without architectural lock-in

A dependency-aware hygiene pass was completed on 2026-03-24.

Verified outcomes:

- the live contour was identified and syntax-checked
- support and guarded layers were identified
- archive candidates were identified
- archive candidates were moved to quarantine in a controlled test
- live smoke checks still passed after quarantine
- full regression still passed after quarantine
- rollback restored the original `/home/agent/bin` layout
- a canonical repo copy of the protected working set was created and hash-verified

## Decision

### 1. Live execution path stays in `/home/agent/bin`

The live execution path remains:

`/home/agent/bin`

This is the current operational runtime and must not be silently replaced by repo paths.

### 2. Repo canonical runtime is stored in `_runtime/canonical`

The repository stores a canonical copy of the protected working set under:

`/home/agent/agents/_runtime/canonical`

This canonical copy is a verified source-of-truth snapshot, not the active execution path.

### 3. Current safe workflow is `bin -> canonical -> git`

The current approved workflow is:

1. develop and test changes in `/home/agent/bin`
2. run pre-checks and post-checks
3. run live smoke checks
4. run full regression when needed
5. copy the protected working set to `_runtime/canonical`
6. verify hash parity
7. only then stage and commit repo changes

### 4. Archive handling is quarantine-first

Historical files, backups, patch helpers, and bootstrap tails must not be deleted first.

The required pattern is:

- identify candidates
- quarantine them
- keep rollback available
- run verification
- only then decide on longer-term archive or deletion policy

### 5. Raw artifact policy

The repository should prefer compact, high-signal artifacts over raw dumps.

#### Commit candidates
High-signal, low-noise artifacts may be committed when they support governance or reproducibility.

Examples:
- `_runtime/canonical/**`
- `_runtime/README.md`
- `_runtime/.gitignore`
- selected audit summaries
- selected compact hygiene manifests
- future compact inventory manifests

#### Local-only by default
Raw operational dumps should remain local unless there is a specific reason to preserve them in git.

Examples:
- large raw inventory snapshots
- duplicate inventory runs
- raw external reference scans
- quarantine tarballs
- moved-file lists used only for one-time staging
- bulky transient hygiene traces

### 6. Guardrails, not lock-in

The rules in this ADR are intended to protect the system without reducing future options.

This ADR does **not** mean that the project is permanently restricted to the current structure.

In particular, it does not forbid future evolution toward:

- better sync tooling
- formal deployment flows
- modular runtime packaging
- stronger registries and manifests
- improved archive management
- future separation between development, canonical, and deployed runtime layers

The current model is a safe normalization step, not a permanent ceiling.

## Consequences

### Positive
- the live runtime remains stable
- the repo now has a canonical verified runtime copy
- cleanup becomes safer and reversible
- future governance can build on verified structure instead of ad hoc file piles
- the project gains control without forcing premature deployment redesign

### Negative
- there is still some duplication between `/home/agent/bin` and `_runtime/canonical`
- sync is still manual and policy-driven
- some raw artifacts remain outside a fully normalized retention model
- `core/LOG.md` still needs an English checkpoint update

## Follow-up actions

1. keep `_runtime/canonical` as the current repo canonical layer
2. update `core/LOG.md` with the 2026-03-24 runtime hygiene checkpoint
3. define which compact hygiene artifacts deserve repo retention
4. define which compact inventory artifacts deserve repo retention
5. leave raw inventory and raw quarantine artifacts local-only unless explicitly needed
6. later define a repeatable sync and archive workflow without changing the live runtime path