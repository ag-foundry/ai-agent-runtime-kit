# Core Project Steering

Status: durable-steering-layer
Updated: 2026-04-06
Scope: `/home/agent/agents/core`

This is the main long-form steering document for the `core` topic.

It consolidates confirmed findings from:

- `/home/agent/agents/core/artifacts/audit/curated/2026-04-03-full-architecture-audit-v1.md`
- `/home/agent/agents/core/artifacts/audit/curated/2026-04-03-truth-model-normalization-and-rule-precedence-v1.md`

It does not replace live source files, scripts, or accepted manifests.
It must not be used to upgrade a derived status artifact into canonical truth.

## Project purpose

The `core` topic exists to operate and improve the long-lived server AI orchestration stack without losing grounded execution, reproducibility, or reuse.

This includes:

- governed runtime entrypoints
- retrieval-backed current-state answers
- research-backed background synthesis
- topic memory and durable decisions
- controlled vault integration
- reusable creator/eval/promotion tooling for OpenClaw skills

## Current confirmed status

The following are confirmed and working:

- live runtime execution remains rooted in `/home/agent/bin`
- `/home/agent/agents/_runtime` is the governed repo mirror for the protected runtime surface
- retrieval and vault read/write bridges are real working paths
- the creator / eval / accepted-case-set / promotion-gate / provenance line exists and remains additive
- a global managed launcher, policy registry, and memory-fabric definition now exist at `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/scripts/launch_managed_workflow.py`, `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/definitions/global-managed-policy-registry-v1.json`, and `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/definitions/global-managed-memory-fabric-v1.json`, making the canonical managed path the default standard for managed eval, historical review, current-run review, compare, clean rerun, promotion-preview, new-topic bootstrap, and controlled topic migration while keeping compatibility paths explicit
- the server now has one human-facing natural-language managed entrypoint at `/home/agent/bin/agent-exec`, backed by `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/scripts/launch_ai_meta_workflow.py`; it classifies intent, resolves topic/run/case scope, selects a managed or research-aware backend path, lifts machine-readable memory, and leaves `ai-meta-launch-*` traces instead of relying on remembered workflow-class selection
- Codex chat is now bound into the same server-wide contour through a real preflight contract instead of docs-only intent: `/home/agent/bin/codex-frontdoor-preflight` drives the same meta-launcher in `--frontdoor-source codex_chat --preflight-only` mode, emits `codex-frontdoor-contract.json` plus manifest/trace/memory selection, routes structured work to canonical backends, keeps open-ended substantial work in the current Codex conversation, and traces MCP/tool plus skill decisions explicitly
- global memory is now wired as a managed fabric instead of an implicit pile: topic memory, shared memory, steering docs, run artifacts, accepted caveats, do-not-reopen registry, runtime registry/manifest, retrieval/research latest artifacts, OpenClaw workspace notes, per-request memory snapshots, and best-effort graph recall can all be selected by workflow policy with contamination-sensitive exclusions for clean reruns
- research is now part of the same managed server contour through the meta-launcher: research requests route to `/home/agent/bin/project-research-run` as a traceable managed mode with policy-registry and memory-fabric grounding, while current-state requests route to `/home/agent/bin/openclaw-retrieval-bridge`
- all non-system topic roots under `/home/agent/agents/*` now either have managed defaults in place or were created through the managed bootstrap path; `_shared` and `_runtime` stay intentional system roots outside topic migration
- the current strongest proven skill contour is still the `server-vault-write` line, with promotion evidence that remains honest about human judgment
- prompt-contained contract skills have now been validated as useful diagnostic surfaces but weak default proof surfaces, because both `ledger-evidence-audit` and `promotion-readiness-auditor` tended toward baseline parity
- the first net-new usefulness-proven result is now the file-state / bundle-state skill `promotion-bundle-admission-guard`, which reached `usable now` on a real bundle-path surface
- a cleaner second `promotion-bundle-admission-guard` bundle-state pass removed the earlier baseline timeout caveat, but baseline completed the same bundle-state judgment and the result fell back to weak delta, so class-level reproducibility is not yet proven
- `runtime-governance-remediation-guard` is now an accepted managed skill line on the canonical managed evaluation path: `generate_review_pack.py` -> `pack-selection-trace.json` / `pack-selection-manifest.json` -> `run_skill_trial_matrix.py` -> completed review -> `evaluate_readiness.py` -> promotion-preview or deliberate adoption
- the accepted non-blocking caveat for that line is explicit: `runtime-governance-remediation-guard-validation-proof-gate` remains an accepted weak boundary residue, and a single-case `evaluate_readiness.py` result may still say `not yet ready` under the unchanged single-case policy without reopening line-level acceptance
- experiment-intelligence layer `v1` now exists at `/home/agent/agents/core/artifacts/experiment-intelligence/skill-creator-history-v1`, where a single registry normalizes the current skill-creator / usefulness / delta / runtime-governance corpus and keeps pending placeholder review packs out of the active registry until they are completed
- research-brain `v2` now exists at `/home/agent/agents/core/runtime/research-brain-v2` with a derived decision root at `/home/agent/agents/core/artifacts/research-brain/skill-creator-history-v2`, where task intake classification, bounded search-depth selection, execution-class routing, exhausted-line enforcement, next-step portfolio generation, and post-run writeback planning are layered on top of experiment-intelligence `v1` plus durable steering and memory
- the current corpus now shows two paused lines, not one more immediate rerun queue: prompt-contained net-new candidates are locally exhausted for this cycle, and the repeated bundle-state portability follow-ups after the first win are locally exhausted for proving family-level delta inside the same proof class

The main current risk is not execution failure.
The main current risk is control-plane bloat:

- duplicated or stale derived truth being mistaken for canonical truth
- too many retained runs, backups, and generated trees competing for attention
- extra governance layers being added faster than they protect live execution or reuse

## What is already strong and must not be broken

These working paths should be preserved unless there is clear evidence for change:

- the live public execution path in `/home/agent/bin`
- the governed runtime bridge in `/home/agent/agents/_runtime`
- retrieval and vault bridges used by OpenClaw
- the creator/eval/promotion path for accepted-case-set work
- the additive promotion-gate and selective provenance layers
- the global managed launcher, policy registry, and memory-fabric layer that make the canonical managed path the default standard instead of a remembered manual chain
- the server-wide AI meta-launcher layer that makes natural-language managed work the default human entry instead of one more script the operator has to remember
- the canonical managed path for accepted skill lines:
  `launch_managed_workflow.py` -> `generate_review_pack.py` -> `pack-selection-trace.json` / `pack-selection-manifest.json` -> `run_skill_trial_matrix.py` -> completed reviews -> `evaluate_readiness.py` -> promotion-preview or deliberate adoption

Do not break these paths in the name of architectural cleanliness alone.

## Runtime-Governance Accepted Baseline

For `runtime-governance-remediation-guard`, the settled baseline is now:

- status: `accepted managed skill line`
- default path: the canonical managed path above, not legacy/ad hoc assembly
- accepted caveat: `runtime-governance-remediation-guard-validation-proof-gate` remains a visible weak boundary residue, but not a blocker for line-level acceptance

Do not reopen these themes without a new blocker:

- contamination from old derived artifacts on disputed reruns
- repo-root leakage in case-facing execution
- trustworthiness of enforced projection
- prose-only upstream pack selection on the canonical path
- the claim that the accepted status is overturned merely because a one-case readiness pack still returns `not yet ready`

## Global AI Meta-Launcher Baseline

The settled server-wide baseline is now:

- default human entrypoint: `/home/agent/bin/agent-exec`
- default Codex-chat binding helper: `/home/agent/bin/codex-frontdoor-preflight`
- compatibility bootstrap alias: `/home/agent/bin/agent-topic`
- backend policy/trace launcher: `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/scripts/launch_ai_meta_workflow.py`
- canonical managed backend: `/home/agent/agents/core/artifacts/skills/openclaw-skill-creator-v1/scripts/launch_managed_workflow.py`
- default server behavior: natural-language request -> hybrid AI plus deterministic routing -> managed memory selection -> canonical backend or research/current-state backend or Codex-local post-preflight execution -> explicit trace
- universal hardening result: readiness-only review is now a first-class managed route, research/search are confirmed launcher-routable and memory-aware, compatibility topic mode preserves intent routing, and all real non-system topic roots now carry refreshed managed defaults including `server_ai_entrypoint=/home/agent/bin/agent-exec`

Do not reopen these themes without a new blocker:

- the claim that users should keep selecting `workflow-class` manually for ordinary managed work
- the claim that direct component invocation is still a silent normal route
- the claim that research must stay outside the global managed contour
- the claim that compatibility topic mode must stay a general-analysis-only fallback

## Canonical / derived / ephemeral policy

### Canonical

Treat the following as canonical within their scope:

- `/home/agent/.codex/AGENTS.md` for agent-wide communication and safety policy
- `/home/agent/agents/_shared/AGENTS.md` for shared repo rules
- `/home/agent/agents/core/AGENTS.md` and this file for core-topic steering
- live source files, scripts, contracts, manifests, and accepted registries under `/home/agent/agents`
- ADRs, `TODO.md`, and `LOG.md` as the maintained record of intent, accepted direction, and topic history
- the governed runtime metadata under `/home/agent/agents/_runtime`

### Derived

Treat the following as derived unless a later phase deliberately promotes them:

- `/home/agent/agents/core/artifacts/project-state/latest.*`
- `/home/agent/agents/core/artifacts/research/latest`
- `/home/agent/agents/core/RESEARCH.md`
- `/home/agent/agents/core/artifacts/retrieval-execution/latest/ANSWER.md`
- `/home/agent/agents/core/artifacts/experiment-intelligence/skill-creator-history-v1/*`
- vault status notes under `/home/agent/vaults/main/OpenClaw/`
- generated verification trees under `runs/*/generated`
- promotion reports, provenance reports, and rollback packs

Derived artifacts may be preferred for specific questions, but they do not become source-of-record by default.

### Ephemeral

Treat the following as ephemeral:

- `/tmp/*`
- scratch verification outputs
- temporary registries
- isolated one-off workspaces created only for a run

Ephemeral artifacts must not be referenced as durable truth after their immediate task ends.

## Practical precedence model

Precedence here is scope-based and question-based.

### 1. Agent-wide communication, safety, and execution policy

Use this order:

1. `/home/agent/.codex/AGENTS.md`
2. `/home/agent/agents/_shared/AGENTS.md`
3. `/home/agent/agents/core/AGENTS.md`

This governs language, safety, approval boundaries, secrets policy, and top-level truth discipline.

### 2. Core topic repo work

When the work changes files under `/home/agent/agents/core`, use this order:

1. `/home/agent/agents/core/AGENTS.md`
2. `/home/agent/agents/core/PROJECT-STEERING.md`
3. `/home/agent/agents/core/TODO.md`, `/home/agent/agents/core/LOG.md`, `/home/agent/agents/core/DECISIONS/`, and selected memory files
4. `/home/agent/agents/_shared/AGENTS.md`

This keeps long-form topic steering local to the topic instead of duplicated into shared rules.

### 3. OpenClaw workspace routing

For OpenClaw routing only, use this order:

1. `/home/agent/.openclaw/workspace/TOOLS.md`
2. `/home/agent/.openclaw/workspace/MEMORY.md`

These files may route lookup or bridge choice.
They do not authorize writes, weaken higher-precedence safety rules, or upgrade derived layers to canonical truth.

### 4. Current operational status questions

Use this order:

1. `/home/agent/agents/core/artifacts/retrieval-execution/latest/ANSWER.md`
2. `/home/agent/agents/core/artifacts/project-state/latest.*`
3. `/home/agent/agents/core/artifacts/research/latest`
4. vault status notes

Meaning:

- retrieval is the preferred current-state answer layer
- `project-state/latest.*` is orientation only
- research may be valid but older background
- vault notes are human-readable recall only

### 5. Research and older background questions

Use this order:

1. `/home/agent/agents/core/artifacts/research/latest`
2. older validated research artifacts
3. retrieval answers only as current-state contrast
4. vault notes only as supporting recall

### 6. Note-content questions

If the user asks about the content of a vault note, the vault note wins for that question.
That does not promote the note to canonical project truth outside the note-reading scope.

### 7. Write actions

Use this order:

1. agent-wide and shared safety rules
2. topic rules and this steering document for repo work
3. OpenClaw write-routing rules only after the higher layers allow the action

Routing may choose the correct bridge.
Routing does not create permission by itself.

## Research, retrieval, execution, memory, and vault coordination model

The project should be treated as one connected system:

- `execution` lives in the public command surface under `/home/agent/bin`
- `_runtime` is the governed repo mirror for that public surface
- `retrieval` provides the preferred derived layer for current operational status
- `research` provides deeper source-backed background and older context
- `memory` provides continuity, decisions, checkpoints, and reuse hints inside the repo
- `vault` provides human-readable synced recall and curated note surfaces

Coordination rules:

- use retrieval first for current state
- use research for deeper background, not as automatic freshest truth
- use topic memory to preserve continuity and decision trace
- use vault notes for recall and human-readable summaries, not as canonical records
- treat vector and graph retrieval as accelerators, not as replacements for direct file truth

## Durable writeback and memory-promotion policy

After each major phase, run a short writeback classification before closing the phase.

Routine minimum:

- `LOG.md`: record the historical checkpoint with the main result plus verification and rollback pointers
- `TODO.md`: update the next required step or blocker
- `memory/index.md`: add durable pointers to the primary artifact and rollback pack when they matter for later recall

Promotion classes and destinations:

- `durable fact` -> `memory/facts.md`
  Use only for verified state, stable capabilities, accepted status changes, or other results expected to stay true across sessions.
- `durable lesson / anti-pattern` -> `memory/lessons.md`
  Use for reusable operating rules, anti-patterns, or generalizable mistakes revealed by the phase.
- `next-step / blocker` -> `TODO.md`
  Use for the next concrete requirement, unresolved decision, or blocked dependency.
- `historical checkpoint` -> `LOG.md`
  Use for what happened in this phase and where the evidence lives.
- `steering-level rule or direction` -> `PROJECT-STEERING.md`
  Use only when the phase changes topic direction, truth policy, coordination policy, or other durable guidance beyond one run.
- `AGENTS-level repeated rule` -> topic `AGENTS.md` or `/home/agent/agents/_shared/AGENTS.md`
  Use only when the rule is small, repeated, stable, and likely to matter in future phases. Keep it short.
- `artifact/run-only evidence` -> keep in `artifacts/` or `runs/` only
  Raw outputs, bulky reports, temporary diagnostics, and evidence bundles should usually stay non-promoted. Add only a pointer in `memory/index.md` when future recall is likely to matter.

Short decision surface:

1. What became a durable fact?
2. What became a durable lesson or anti-pattern?
3. What is the next required step or blocker?
4. What belongs only to `artifacts/` or `runs/`?
5. Did this phase change topic steering?
6. Did it reveal a small repeated rule worth promoting into `AGENTS.md`?

Human judgment remains required for:

- whether a candidate fact is stable enough for `memory/facts.md`
- whether a takeaway is general enough for `memory/lessons.md`
- whether a result is mature enough for steering or `AGENTS.md`
- whether an artifact deserves a durable pointer or should remain run-only

Do not promote everything.
The goal is to prevent important insight from being stranded in evidence, not to turn every run into durable memory.

## Git / GitHub strategy direction

Current direction is intentionally conservative.

Keep in git as durable project material:

- rules and steering files
- ADRs, contracts, source scripts, accepted manifests, and reusable templates
- governed runtime metadata
- creator/eval source packages and accepted-case-set source artifacts

Treat as derived-first and commit only when they materially help audit, reproducibility, or regression:

- generated run trees
- raw evaluation outputs
- rollback packs
- status snapshots
- promotion and provenance reports

Current guidance:

- manual checkpoints are enough for now
- do not build a custom GitHub control plane in this phase
- if GitHub automation later becomes useful, prefer existing GitHub tooling or integrations over bespoke repo logic

## MCP and external-tool-first principle

Prefer an existing public command, bridge, or mature integration before adding custom glue.

Use MCP or external integrations only when:

- the need is explicit
- the boundary is clear
- the integration can be smoke-tested safely

Do not build a new MCP framework or a broad external-tool orchestration layer yet.

## Skills line: confirmed and unfinished

Confirmed:

- the creator/eval/promotion path is real and script-backed
- accepted-case-set promotion is generalized beyond ad hoc single-skill handling
- promotion-gate and selective provenance are in place without breaking existing flow
- prompt-contained contract candidates were still worth running because they exposed the current parity boundary honestly
- generator `v1` is now usefulness-proven on one net-new bundle-state surface through `promotion-bundle-admission-guard`
- the current winning validation pattern is a file-state or bundle-state skill that inspects a real bundle root instead of reading a fully embedded contract from the prompt
- the clean second bundle-state validation pass was still useful because it removed the timeout-style caveat and showed the remaining blocker more clearly: reproducible class-level usefulness is not yet established even on the stronger bundle-state surface
- experiment-intelligence `v1` now provides the compact retrospective layer that the current skills corpus was missing: one registry, one pattern/blocker extraction layer, one next-step portfolio, and durable writeback pointers instead of scattered verdicts only in runs and artifacts

Still unfinished:

- broader managed-skill adoption is still a policy decision, not a rollout fact
- stronger semantic review signals are still needed beyond structural execution plus pair reviews
- the future policy for required versus supporting `assistant.txt` anchors is still open
- `server-vault-write-policy-delta-two-case-v1` remains honest about human judgment and is not auto-approved by script alone
- reproducible bundle-state usefulness is still unproven at the class level: the first `promotion-bundle-admission-guard` pass crossed the threshold, but the cleaner second pass completed fully for both modes and fell back to weak delta with `baseline_trigger_mismatch`
- the skills line is paused at this checkpoint: do not treat the current corpus as a signal to continue prompt-contained reruns or more bundle-state portability reruns by default

## Experiment intelligence layer

Use `/home/agent/agents/core/artifacts/experiment-intelligence/skill-creator-history-v1/experiment-registry-v1.json` as the current derived registry over the validated skill-creator corpus when the question is:

- what experiments have already been run
- which families are winning, parity-prone, or locally exhausted
- which blockers repeat across lines
- what the next recommended move should be before the skills line resumes

Do not treat the registry or retrospective report as canonical truth by themselves.
They are a derived coordination layer over completed evidence.
Promote only the stable conclusions into steering, `TODO.md`, and topic memory.

Human judgment remains required for promotion strength, semantic fit, and rollout decisions.

## Research brain v2 layer

Use `/home/agent/agents/core/artifacts/research-brain/skill-creator-history-v2/research-brain-state-v2.json` as the current derived intake/routing layer when the question is:

- what class of research task is being requested now
- how much local search depth is actually justified before acting
- which paused or locally exhausted lines must be blocked by default
- which repeated blockers and negative results must be carried forward before choosing another run
- what the compact next-step portfolio and post-run writeback plan should be

The builder under `/home/agent/agents/core/runtime/research-brain-v2/build_research_brain_v2.py` should stay explicit-command driven in `v2`.
Do not turn it into a daemon, a broad new framework, or an automatic experiment runner in this phase.

Do not treat the research-brain outputs as canonical truth by themselves.
They are a derived decision layer over experiment-intelligence `v1`, steering, memory, and validated artifacts.
Promote only the stable conclusions into steering, `TODO.md`, and topic memory.

## Cross-project memory and reuse priority

Before any broader governance expansion or wider skill-rollout claim, run a cross-project smoke test that checks:

- retrieval-backed current-state answers still win where they should
- topic memory improves continuity instead of splitting truth
- vault notes stay derived and supportive
- reuse works outside the current OpenClaw-only contour

This is a better next generalization test than adding another governance layer.

## What must not be built yet

Do not build these yet:

- a new heavyweight governance stack
- a custom GitHub control plane
- a broad MCP management framework
- broad managed-skill rollout claims
- bulk refreshes of stale derived layers as a substitute for clear truth policy

## Next major priorities

1. Keep this steering layer small and obey it instead of adding another layer.
2. Use research-brain `v2` plus experiment-intelligence `v1` before any new skill/usefulness rerun so search depth, execution class, and exhausted-line enforcement are explicit instead of implicit.
3. Validate research-brain `v2` on one non-skills local intake before any broader hook expansion or automation claims.
4. If the skills line resumes, prefer one hardened runtime-governance dry-run case where the decisive proof depends on dry-run-only machine outputs that baseline cannot reconstruct from direct file reads alone.
5. Run smoke-tested hygiene on backup-like files in `/home/agent/bin` without changing the public entrypoint surface.
6. Resolve the open skills-policy questions that still require human judgment.
