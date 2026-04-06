# OpenClaw Skill Creator v1 Capability Matrix

| Capability area | Status in this package | Executable now | Artifact |
| --- | --- | --- | --- |
| canonical scaffold generation | implemented | yes | `scripts/create_skill_scaffold.py`, `templates/managed-skill/` |
| portable-core vs OpenClaw-profile separation | implemented | yes | `templates/managed-skill/SKILL.md.tmpl`, `references/portability-core-vs-profile.md.tmpl` |
| deterministic validation | implemented | yes | `scripts/check_required_tree.py`, `scripts/validate_skill_lifecycle.py` |
| required file-tree checks | implemented | yes | `definitions/required-skill-tree.json` |
| schema-defined lifecycle metadata contract | implemented | yes | `definitions/skill-metadata-contract.json` |
| manifest-driven skill inventory | implemented | yes | `scripts/build_skill_inventory.py` |
| capability-aware metadata validation | implemented | yes | `scripts/validate_skill_lifecycle.py`, `definitions/skill-metadata-contract.json` |
| isolated profile generation for arbitrary creator-compatible skills | implemented | yes | `scripts/generate_managed_profile.py` |
| baseline plus trial profile generation | implemented | yes | `scripts/generate_managed_profile.py` |
| universal trial-plan generation | implemented | yes | `scripts/generate_review_pack.py`, `definitions/trial-plan-contract.json` |
| readiness gates | implemented | yes | `definitions/readiness-gates.json`, `scripts/evaluate_readiness.py` |
| review-pack generation | implemented | yes | `scripts/generate_review_pack.py`, `templates/eval-pack/` |
| accepted concrete case-set regeneration | implemented | yes | `accepted-case-sets/`, `scripts/generate_review_pack.py` |
| accepted concrete case-set promotion from proven run roots | implemented | yes | `scripts/promote_accepted_case_set.py`, `definitions/accepted-case-set-contract.json` |
| creator-to-harness compatibility checks | implemented | yes | `scripts/check_eval_harness_compatibility.py` |
| universal harness execution path | implemented | yes | `openclaw-skill-eval-harness-v1/scripts/run_skill_trial_matrix.py` |
| legacy fixed-path compatibility | implemented | yes | `openclaw-skill-eval-harness-v1/scripts/run_managed_skills_matrix.py` |
| invalidation-aware readiness reporting | implemented | yes | `definitions/readiness-gates.json`, `scripts/evaluate_readiness.py` |
| compatibility inventory for legacy live skills | implemented | yes | `scripts/build_skill_inventory.py` |
| eval aggregation safety | partially implemented | partly | readiness now surfaces invalidated evidence and denial reasons, but still does not replace the existing Prompt 2 aggregator |
| rollback-pack generation | implemented | yes | `scripts/build_rollback_pack.py` |
| anti-pattern warnings | implemented | yes | `scripts/validate_skill_lifecycle.py` |
| “do not copy literally” guidance | implemented | yes | `templates/managed-skill/references/do-not-copy-literally.md.tmpl` |
| invocation-line rule for generated commentable files | implemented | yes | `scripts/file_rules.py`, scaffold and review-pack generators |
| arbitrary domain-specific logic | intentionally avoided | yes | contract stays domain-agnostic; future domains fit through metadata and capabilities |
| automatic eval execution from creator package alone | partially implemented | partly | creator emits universal trial plans; harness executes them through the shared universal runner |
| semantic answer-quality scoring | deferred | no | requires v2 work |
| automatic runtime registration | out of scope | no | intentionally excluded from v1 |
