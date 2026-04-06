# OpenClaw Skill Creator v1 Lifecycle Spec

This spec defines the universalized v1 lifecycle target for `openclaw-skill-creator-v1`.

It is based on three truths:

- Prompt 2 proved that real skill evidence exists
- Step 2 hardening made the lifecycle stricter and more honest
- turbo universalization must remove creator-side dependence on fixed skill names and fixed skill families

## Universal lifecycle contract

| Contract area | Requirement | Current delivery |
| --- | --- | --- |
| scaffold contract | Must create a repeatable creator-compatible skill starter tree with portable vs OpenClaw-specific separation | `scripts/create_skill_scaffold.py` plus `templates/managed-skill/` |
| metadata schema | Must define what lifecycle and capability metadata are allowed and required | `definitions/skill-metadata-contract.json` |
| deterministic validation | Must fail on missing required structure, invalid metadata, and incompatible lifecycle declarations | `scripts/check_required_tree.py` and `scripts/validate_skill_lifecycle.py` |
| inventory contract | Must discover arbitrary candidate skills from roots or explicit paths without name whitelists | `scripts/build_skill_inventory.py`, `scripts/skill_manifest.py` |
| profile contract | Must generate profile-local config and copied skills without touching the live runtime | `scripts/generate_managed_profile.py` |
| isolation rules | Must support baseline and trial profiles for arbitrary creator-compatible skills | `scripts/generate_managed_profile.py` manifest and validation |
| trial contract | Must emit a machine-readable trial plan that the harness can execute without fixed skill maps | `scripts/generate_review_pack.py`, `definitions/trial-plan-contract.json` |
| compatibility contract | Must verify that creator-generated packs and profile manifests match the selected harness runner mode | `scripts/check_eval_harness_compatibility.py` |
| readiness contract | Must convert completed reviews into deterministic verdicts with invalidation-aware reporting | `definitions/readiness-gates.json` and `scripts/evaluate_readiness.py` |
| legacy compatibility | Must preserve the old fixed-path runner only as an explicit backward-compatibility layer | `openclaw-skill-eval-harness-v1/scripts/run_managed_skills_matrix.py` |
| universal execution | Must support a generalized entrypoint that executes a `trial-plan.json` | `openclaw-skill-eval-harness-v1/scripts/run_skill_trial_matrix.py` |
| migration honesty | Must explicitly mark live legacy skills that do not yet satisfy the creator schema | `scripts/build_skill_inventory.py` |
| anti-pattern warnings | Must warn when a skill is too generic, too weakly scoped, or too underspecified for serious lifecycle use | `scripts/validate_skill_lifecycle.py` |
| invocation-line rule | Must add the invocation line only to new text files whose formats safely support comments | `scripts/file_rules.py` plus scaffold and review-pack generation |

## Deterministic readiness logic

`usable now` requires:

- at least one completed review
- valid evidence only
- baseline trigger recorded as `no`
- with-skill trigger recorded as `yes`
- no `fail` outcomes
- no `overtrigger` or `undertrigger`
- all outcomes are `pass`
- at least one `meaningful` delta signal

`usable with caveats` requires:

- at least one completed review
- valid evidence only
- baseline trigger recorded as `no`
- with-skill trigger recorded as `yes`
- no `fail` outcomes
- no `overtrigger` or `undertrigger`
- outcomes limited to `pass` or `partial`

`not yet ready` applies otherwise.

## Explicit honesty rules

- A generated scaffold is not a readiness claim.
- A validator pass is not an eval pass.
- A successful eval run is not enough for `usable now` by itself.
- A skill that adds no meaningful delta over baseline can still be real and still only be `usable with caveats`.
- Anthropic or Codex examples may inform design, but they must not be copied literally into OpenClaw assumptions.
- Invalidated harness evidence stays invalid until a clean rerun replaces it.

## Honest boundary

This package can now support creator-driven trials through the universal contract when the target skill satisfies the creator schema or is explicitly inventoried with truthful compatibility metadata.

It still does not mean:

- semantic quality is automatically proven
- rollout to production is automatically justified
- live legacy skills are all migrated already
- runtime registration should be automated
