---
name: project-research
description: >
  Run a memory-first, bounded research stage before planning a new or materially changed project.
  Use for software, websites, analytics, automation, infrastructure, business-process, documentation,
  and mixed projects when you need a compact RESEARCH.md plus a short, prioritized source list.
  Do not use for tiny local edits, routine follow-up work, or tasks already well-covered by project memory.
---

# project-research

## Goal
Produce a compact, useful `RESEARCH.md` that improves the next step (`PROJECT_PLAN.md`)
without turning research into a token-heavy web crawl.

## Use this skill when
- the task is a new project or a materially new project direction;
- there is an external platform, API, protocol, format, tool, workflow, or market context to understand;
- it is helpful to inspect a few similar solutions before planning;
- you need a disciplined pre-plan research step.

## Do not use this skill when
- the task is a tiny local edit;
- the topic is already well covered by local memory and prior artifacts;
- you only need to continue an already planned implementation with no meaningful scope change.

## Core policy
1. **Memory first.**
   Check local memory and existing artifacts before any external search.
2. **Bounded research.**
   Default to `quick`, not `deep`.
3. **Two-stage search.**
   First metadata pass, then focused extraction.
4. **Planning handoff.**
   The output must help create `PROJECT_PLAN.md`, not replace it.

## Decision flow
1. Identify the topic / project scope.
2. Run local precheck:
   - project `README.md`, `LOG.md`, `TODO.md`, `DECISIONS/`, `artifacts/`
   - `memory search <topic>` when available
   - existing related topics if relevant
3. Classify the task:
   - software
   - website
   - analytics
   - automation
   - infrastructure
   - business
   - content
   - documentation
   - mixed
4. Choose mode:
   - `none`  → local memory is enough
   - `quick` → default
   - `deep`  → only for ambiguity, high risk, or weak signal from quick mode
5. Build outputs:
   - `RESEARCH.md`
   - `sources.json`

## Research modes
### none
Use only local memory and existing artifacts.

### quick (default)
Limits:
- metadata candidates: up to 6
- deeply inspected sources: up to 3
- similar solutions in final summary: 2–3
- official sources: 1–2
- recurring risks/patterns: 3–5
- target summary length: about 500–800 words

### deep
Use only if quick mode is insufficient.
Limits:
- metadata candidates: up to 10
- deeply inspected sources: up to 6
- similar solutions in final summary: 4–6
- official sources: 2–4
- recurring risks/patterns: 5–10
- target summary length: up to about 1400 words

## Source priority
1. official docs / vendor docs / standards / platform rules
2. active repositories / maintained solutions
3. recurring issue patterns / discussions
4. strong technical articles
5. forums only if needed

## Metadata pass
During metadata pass, inspect only:
- title / name
- short description
- recency / activity
- applicability to the task
- signs of maturity

## Focused extraction
Only extract:
- architecture / structure
- key tools / stack / platforms
- constraints
- recurring risks
- practical ideas worth reusing
- anti-patterns to avoid

## Required output shape
The final `RESEARCH.md` must answer:
1. What type of project is this?
2. What existing local context already helps?
3. Are there a few strong external reference points?
4. What risks or patterns repeat?
5. What starting approach is most reasonable?
6. What should be avoided?

## Success criteria
The skill is successful if it:
- stays bounded;
- reuses local memory first;
- produces a compact, prioritized output;
- improves planning quality;
- avoids unnecessary external search.

## Bundled helpers
- `scripts/precheck_memory.sh` — lightweight local-memory precheck helper
- `scripts/render_research_stub.py` — scaffold `RESEARCH.md` / `sources.json` from templates
- `scripts/validate_skill.py` — validate this skill bundle
- `references/policy.md` — full policy
- `references/checklist.md` — quick audit checklist
- `assets/RESEARCH.md.tpl` — output template
- `assets/sources.json.tpl` — machine-readable source template
- `evals/trigger_queries.md` — trigger / non-trigger test set
