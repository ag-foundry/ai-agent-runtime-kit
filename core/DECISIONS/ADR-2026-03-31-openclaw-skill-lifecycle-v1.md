# ADR-2026-03-31-openclaw-skill-lifecycle-v1

Status: accepted
Date: 2026-03-31
Topic: core

## Decision

Adopt an OpenClaw Skill Lifecycle v1 that is:
- additive to the current Phase 1 runtime
- split into portable core, managed OpenClaw profile, and lifecycle-complete readiness
- eval-aware before packaging-aware

Implement in this cleanup checkpoint:
- revised portability research
- tightened architecture spec
- corrected managed-skill audit matrix
- improved canonical template skill
- improved eval harness skeleton
- deterministic OpenClaw-profile validation helper
- exact rollback backups for edited artifacts

Do not implement in this cleanup checkpoint:
- managed-skill runtime rewrites
- managed-skill prose rewrites that are not supported by current disk state
- eval execution
- packaging or registration changes
- bridge replacement

## Context

Phase 1 is already working.
Confirmed behavior includes:
- retrieval read-path
- vault read-path
- controlled vault write
- routing policy
- gateway / Telegram / local voice path

Re-audit of the current managed skills showed two important corrections:
1. the current `SKILL.md` files already use absolute bridge paths
2. the current `SKILL.md` files already include structured `metadata.openclaw.*`

Therefore the cleanup target is not "fix the live skills first".
The cleanup target is:
- make the documentation accurate
- make the standard explicit
- make the template and eval skeleton trustworthy

## Rationale

This decision preserves the live memory-vault path while removing ambiguity from the lifecycle documents.

Why this approach:
1. It does not invent drift that is not on disk.
2. It avoids unnecessary edits to working Phase 1 skills.
3. It keeps portable canon and OpenClaw-specific profile rules separate.
4. It makes eval readiness the next real gate.
5. It improves rollback quality by storing exact pre-edit backups.

## Consequences

### Positive
- clearer authoring standard
- better separation between portable patterns and OpenClaw-only rules
- stronger template artifact
- safer eval harness skeleton
- more honest checkpoint about current managed skill state

### Negative
- packaging remains intentionally secondary
- loader behavior around metadata is still documented by convention rather than by runtime enforcement
- real confidence in trigger precision still depends on a later eval phase

## Non-goals

This ADR does not:
- replace the current memory bridges
- change allowed write areas
- auto-enable new meta-skills in production
- claim eval success
- claim any git commit or release event

## Verification

```bash
python3 /home/agent/.nvm/versions/node/v24.14.1/lib/node_modules/openclaw/skills/skill-creator/scripts/quick_validate.py /home/agent/.openclaw/skills/server-memory-retrieval
python3 /home/agent/.nvm/versions/node/v24.14.1/lib/node_modules/openclaw/skills/skill-creator/scripts/quick_validate.py /home/agent/.openclaw/skills/server-memory-routing
python3 /home/agent/.nvm/versions/node/v24.14.1/lib/node_modules/openclaw/skills/skill-creator/scripts/quick_validate.py /home/agent/.openclaw/skills/server-vault-read
python3 /home/agent/.nvm/versions/node/v24.14.1/lib/node_modules/openclaw/skills/skill-creator/scripts/quick_validate.py /home/agent/.openclaw/skills/server-vault-write
python3 /home/agent/.nvm/versions/node/v24.14.1/lib/node_modules/openclaw/skills/skill-creator/scripts/quick_validate.py /home/agent/agents/core/artifacts/skills/openclaw-skill-template-v1
python3 /home/agent/agents/core/artifacts/skills/openclaw-skill-template-v1/scripts/validate_openclaw_skill.py /home/agent/agents/core/artifacts/skills/openclaw-skill-template-v1
bash /home/agent/agents/core/artifacts/skills/openclaw-skill-template-v1/scripts/check_skill_tree.sh /home/agent/agents/core/artifacts/skills/openclaw-skill-template-v1
bash /home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1/scripts/check_eval_tree.sh /home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1
python3 /home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1/scripts/aggregate_reviews.py /home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1/examples/results
```

## Rollback

Restore from:

`/home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup`

```bash
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/research/2026-03-31-claude-skill-creator-portability-research.md /home/agent/agents/core/artifacts/research/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/architecture/2026-03-31-openclaw-skill-lifecycle-v1.md /home/agent/agents/core/artifacts/architecture/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/architecture/2026-03-31-openclaw-skill-audit-matrix-v1.md /home/agent/agents/core/artifacts/architecture/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/decisions/ADR-2026-03-31-openclaw-skill-lifecycle-v1.md /home/agent/agents/core/DECISIONS/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/core/LOG.md /home/agent/agents/core/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/core/TODO.md /home/agent/agents/core/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/core/index.md /home/agent/agents/core/memory/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/core/facts.md /home/agent/agents/core/memory/
cp /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/core/lessons.md /home/agent/agents/core/memory/
rm -f /home/agent/agents/core/memory/context.md
rm -rf /home/agent/agents/core/artifacts/skills/openclaw-skill-template-v1
rm -rf /home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1
cp -R /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/skills/openclaw-skill-template-v1 /home/agent/agents/core/artifacts/skills/
cp -R /home/agent/agents/core/runs/2026-03-31-openclaw-skill-lifecycle-cleanup-v2/backup/skills/openclaw-skill-eval-harness-v1 /home/agent/agents/core/artifacts/skills/
```
