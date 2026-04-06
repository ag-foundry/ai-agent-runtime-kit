# Scope Boundary

## In v1

- canonical creator-compatible skill scaffold generation
- portable core vs OpenClaw profile separation
- deterministic tree checks and lifecycle validation
- manifest-driven skill inventory
- capability-aware lifecycle metadata
- baseline and trial profile generation for arbitrary creator-compatible skills
- universal review-pack and trial-plan generation
- eval-harness compatibility checks
- universal runner support through the shared harness
- deterministic readiness verdicts from completed reviews
- rollback-pack generation
- anti-pattern warnings
- explicit “do not copy literally” guidance for Anthropic/Codex-specific patterns
- invocation-line comments for newly generated commentable text files

## Explicitly out of scope for v1

- claiming Claude Code parity
- automatic skill installation into the live runtime
- automatic enablement of a new managed skill in production
- broad environment audit
- networked or service-level changes
- automatic mutation of the accepted Prompt 2 evidence pack
- pretending that all live legacy skills already satisfy the new creator schema

## Deferred to v2

- richer end-to-end execution packaging inside the creator package itself
- richer semantic diffing of baseline vs with-skill behavior
- stronger schema linting for cross-file lifecycle references beyond the current creator metadata contract
- multi-skill interaction packs and cross-skill scoring
- redundancy analysis against workspace bootstrap context
- richer dashboards and report generation
