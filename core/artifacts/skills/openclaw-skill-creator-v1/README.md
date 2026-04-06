# OpenClaw Skill Creator v1

This package is now a creator-driven lifecycle system for creator-compatible OpenClaw skills.

It no longer assumes that only the current four managed skills matter.

The active architecture is:

- manifest-driven
- schema-driven
- capability-aware
- domain-agnostic by contract
- backward-compatible with the current managed skills where practical

It still stays honest about scope:

- not an installed runtime skill
- not a claim of Claude Code parity
- not a broad rollout signal
- not automatic runtime registration

The lifecycle now reasons about skills through:

- declared metadata in `SKILL.md`
- creator schema compliance
- capability declarations
- file-tree compliance
- profile manifests
- review-pack manifests
- trial-plan manifests
- readiness evidence and invalidation state

## Executable now

- `scripts/create_skill_scaffold.py`
  Creates a creator-compatible starter skill tree from bundled templates and capability metadata inputs.
- `scripts/check_required_tree.py`
  Checks the required file tree for a creator-compatible skill.
- `scripts/validate_skill_lifecycle.py`
  Validates frontmatter, lifecycle metadata, capability declarations, and anti-patterns.
- `scripts/build_skill_inventory.py`
  Builds a manifest-driven inventory from live skills, creator-generated skills, or mixed roots.
- `scripts/generate_managed_profile.py`
  Generates baseline or trial profile roots from inventory or discovered skills.
- `scripts/generate_review_pack.py`
  Creates a review pack plus `trial-plan.json` for universal baseline-vs-trial execution, either from placeholder templates or from an accepted concrete case set.
- `scripts/promote_accepted_case_set.py`
  Promotes a proven run root into the package accepted-case registry so future generator-derived reruns can rebuild the same concrete contour without copying from an older run root.
- `scripts/check_eval_harness_compatibility.py`
  Verifies creator outputs against either the universal runner contract or the legacy fixed path.
- `scripts/evaluate_readiness.py`
  Applies deterministic readiness gates and reports pending or invalidated evidence explicitly.
- `scripts/build_rollback_pack.py`
  Creates a rollback pack for selected files before edits.

## Universal contract

The universal path relies on:

- `definitions/skill-metadata-contract.json`
  creator schema for lifecycle and capability metadata
- `definitions/trial-plan-contract.json`
  machine-readable contract for harness execution
- `definitions/accepted-case-set-contract.json`
  machine-readable contract for accepted concrete case-set manifests
- inventory manifests from `scripts/build_skill_inventory.py`
- profile manifests from `scripts/generate_managed_profile.py`
- review-pack manifests and `summaries/trial-plan.json` from `scripts/generate_review_pack.py`
- accepted concrete case sets under `accepted-case-sets/` when a contour must be regenerated without copying case files from an older run root

This path is intentionally domain-agnostic.

It is meant to support arbitrary future skills such as research, finance, legal, media, data, scientific, or unknown future classes without hardcoding those domains into the lifecycle system.

## Legacy vs universal paths

- Universal path:
  `build_skill_inventory.py` -> `generate_managed_profile.py` -> `generate_review_pack.py` -> `run_skill_trial_matrix.py`
- Legacy path:
  `run_managed_skills_matrix.py` still preserves the fixed four-skill map for backward compatibility
- Migration path:
  `build_skill_inventory.py` explicitly marks live skills as `creator_compatible: false` when they still lack the stricter creator schema

## Canonical managed default path

For accepted or adoption-ready managed lines, the canonical default path is:

- `launch_managed_workflow.py`
- `build_skill_inventory.py`
- `generate_managed_profile.py`
- `generate_review_pack.py`
- `summaries/pack-selection-trace.json`
- `summaries/pack-selection-manifest.json`
- `summaries/trial-plan.json`
- `run_skill_trial_matrix.py`
- completed review files
- `evaluate_readiness.py`
- promotion-preview or deliberate adoption/promotion as a separate governance step

This is the default managed path.

`run_managed_skills_matrix.py` remains a compatibility wrapper, not the preferred canonical route when a creator-generated `trial-plan.json` already exists.

## Global managed launcher

Use `scripts/launch_managed_workflow.py` as the default user-facing entrypoint for managed workflows.

It adds:

- one explicit launcher trace
- one global policy-registry reference
- one machine-readable memory-fabric definition plus per-launch memory selection
- automatic canonical path selection for managed eval
- explicit override discipline for compatibility or legacy paths
- new-topic bootstrap hooks through generated `AGENTS.md`, `README.md`, and `managed-defaults.json`
- controlled topic migration so older topic roots can gain managed defaults without losing their local docs

The launcher now covers:

- `canonical_managed_eval`
- `historical_review`
- `current_run_review`
- `compare_runs`
- `clean_rerun`
- `promotion_preview`
- `topic_bootstrap`
- `topic_migration`

Direct component scripts remain supported, but they are no longer the preferred remembered manual chain for normal managed work.
When a component surface is invoked directly outside the launcher-managed path, downstream matrix manifests now record that as compatibility/direct mode instead of leaving the bypass silent.

## Accepted managed line note

`runtime-governance-remediation-guard` is now the accepted managed line for this canonical path.

Known non-blocking caveat:

- `runtime-governance-remediation-guard-validation-proof-gate` remains an accepted weak boundary residue
- a one-case `evaluate_readiness.py` run on that exact boundary pack may still return `not yet ready` under the unchanged single-case policy
- this does not reopen line-level acceptance or justify returning to ad hoc pack assembly

## Scaffolding or partial layers

- semantic diffing of baseline vs trial outputs is still limited
- human review remains required for readiness
- legacy live skills are not yet fully migrated to the stricter creator schema
- runtime registration remains intentionally out of scope
- graph/helper and vector/semantic connectors are declared in the memory fabric but still not callable directly from the local launcher runtime

## Quick start

Create a new creator-compatible scaffold:

```bash
python3 scripts/create_skill_scaffold.py \
  --output-dir /tmp/my-skill \
  --skill-name my-skill \
  --description "Creator-compatible skill for X. Use when Y." \
  --primary-capability evidence-summarization
```

Build an inventory:

```bash
python3 scripts/build_skill_inventory.py \
  --skills-root /home/agent/.openclaw/skills \
  --skill-dir /tmp/my-skill
```

Validate lifecycle shape:

```bash
python3 scripts/check_required_tree.py --root /tmp/my-skill
python3 scripts/validate_skill_lifecycle.py --root /tmp/my-skill
```

Create isolated baseline and trial profiles:

```bash
python3 scripts/generate_managed_profile.py \
  --profile-name my-skill-baseline \
  --baseline \
  --managed-skill my-skill \
  --inventory-manifest /tmp/skill-inventory.json

python3 scripts/generate_managed_profile.py \
  --profile-name my-skill-trial \
  --enable-skill my-skill \
  --managed-skill my-skill \
  --inventory-manifest /tmp/skill-inventory.json
```

Generate a universal review pack:

```bash
python3 scripts/generate_review_pack.py \
  --run-root /tmp/my-skill-trial-pack \
  --skill-name my-skill \
  --baseline-profile my-skill-baseline \
  --trial-profile my-skill-trial \
  --case-id smoke-case
```

Regenerate a concrete accepted case set without copying from an older run root:

```bash
python3 scripts/generate_review_pack.py \
  --run-root /tmp/server-vault-write-pack \
  --skill-name server-vault-write \
  --baseline-profile skill-migration-delta-strict-baseline-vault-write \
  --trial-profile skill-migration-delta-strict-with-server-vault-write \
  --accepted-case-set server-vault-write-policy-delta-two-case-v1
```

Promote a proven contour into the package accepted-case registry:

```bash
python3 scripts/promote_accepted_case_set.py \
  --run-root /tmp/server-vault-write-pack \
  --case-set-id server-vault-write-policy-delta-two-case-v1 \
  --description "Accepted two-case contour for server-vault-write ambiguity and raw-policy deltas." \
  --force
```

Evaluate the additive promotion gate for an accepted contour:

```bash
python3 scripts/evaluate_promotion_gate.py \
  --checklist accepted-case-sets/server-vault-write-policy-delta-two-case-v1/promotion-checklist.json \
  --output /tmp/server-vault-write-promotion-gate-report.json \
  --force
```

Build a selective file-level provenance report for an accepted contour:

```bash
python3 scripts/build_selective_promotion_provenance.py \
  --checklist accepted-case-sets/server-vault-write-policy-delta-two-case-v1/promotion-checklist.json \
  --output accepted-case-sets/server-vault-write-policy-delta-two-case-v1/promotion-provenance.json \
  --force
```

Check creator-to-harness compatibility:

```bash
python3 scripts/check_eval_harness_compatibility.py \
  --run-root /tmp/my-skill-trial-pack \
  --profile-manifest /tmp/my-skill-baseline-manifest.json \
  --profile-manifest /tmp/my-skill-trial-manifest.json
```

Apply readiness gates to completed reviews:

```bash
python3 scripts/evaluate_readiness.py --run-root /tmp/my-skill-trial-pack
```

## Package map

- `lifecycle-spec.md` - universalized v1 lifecycle target
- `capability-matrix.md` - what is implemented, partial, deferred, or out of scope
- `scope-boundary.md` - in / out / deferred boundary
- `implementation-plan.md` - staged expansion path
- `definitions/` - creator schema, required tree, trial-plan, and readiness definitions
- `templates/` - canonical scaffold and review-pack templates
- `accepted-case-sets/` - accepted concrete case assets that can be regenerated through the creator path
- `scripts/` - deterministic entrypoints

## Invocation-line rule

New text files generated by this package add a commented invocation line based on `Во имя Отца и Сына и Святаго Духа. Аминь.` only when the target format safely supports comments.

- Markdown files get an HTML comment, except frontmatter-based `SKILL.md`, which gets a YAML comment inside the frontmatter block.
- Python, shell, YAML, and similar commentable text files use `# ...` when they are generated by the package.
- JSON and other machine-readable formats without safe comments remain unchanged.
