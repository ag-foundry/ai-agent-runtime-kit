# source_policy

## Purpose

This policy defines how `project-research-run` should gather and prioritize sources.

The system must remain:

- memory-first
- planning-oriented
- bounded by mode
- provenance-aware
- compatible with both execution modes:
  - `chatgpt_codex`
  - `openai_api`

External search must enrich local context, not replace it.

---

## Retrieval order

The default retrieval order is:

1. local topic memory
2. local project artifacts
3. authoritative external sources
4. maintained implementations
5. issue/discussion/problem sources
6. forums only if needed

This means:
- local context is always checked first
- external retrieval is used to fill gaps, validate assumptions, and surface fresh implementation knowledge

---

## Source priority

### Priority 1 — Authoritative sources
Use first when available:

- official documentation
- vendor documentation
- standards
- specifications
- official release notes
- official migration guides

These should dominate tool choice and architecture decisions where possible.

---

### Priority 2 — Maintained implementations
Use to understand real-world structure and current practice:

- active repositories
- maintained examples
- implementation templates
- integration examples
- deployment examples

Prefer repositories that show:
- recent activity
- non-trivial usage
- installation clarity
- issue/discussion evidence of real use

---

### Priority 3 — Recurring issue patterns
Use to identify practical breakage and edge cases:

- GitHub issues
- GitHub discussions
- issue trackers
- troubleshooting threads
- known limitations
- migration pain points

These sources are important for:
- risk discovery
- failure pattern mapping
- anti-pattern detection
- rollout planning

---

### Priority 4 — Strong technical articles
Use when they add real explanatory value:

- deep implementation writeups
- architecture walkthroughs
- migration notes
- comparative technical analyses

They are secondary to authoritative docs and maintained implementations.

---

### Priority 5 — Forums only if needed
Use selectively:

- Reddit
- Stack Overflow
- community forums
- niche boards
- user reports

Forums are useful for:
- symptom discovery
- workarounds
- hidden incompatibilities
- operational pain points

Forums must not be treated as the highest-trust source.

---

## Search buckets

The runner should think in research buckets rather than undifferentiated search.

### Required default buckets
- `official_docs`
- `similar_solutions`
- `recurring_risks`

### Optional buckets depending on project type
- `active_repositories`
- `issue_patterns`
- `platform_choices`
- `structure_patterns`
- `data_models`
- `dashboard_patterns`
- `kpi_patterns`
- `business_workflows`
- `integration_patterns`
- `deployment_patterns`

Each bucket should map to explicit query sets.

---

## Search backend policy

The search layer may use different backends, but the research contract must remain stable.

### Allowed search backend examples
- `searxng`
- `brave_api`
- `perplexity_search_api`
- `manual_curated`
- future search adapters

### Rule
Search backend choice must not change:
- artifact structure
- provenance discipline
- validator behavior
- eval behavior
- regression behavior

Only retrieval mechanics may differ.

---

## SearXNG policy

When `searxng` is used:

- use it as a search discovery layer
- do not treat raw result rank as final truth
- fetch and inspect selected pages before using them as findings
- prefer deduplicated and bucket-balanced candidate selection
- prefer trusted domains when task sensitivity is high

SearXNG is a search adapter, not a research conclusion engine.

---

## External retrieval rules

When using external search:

- prefer 1–2 authoritative sources before many secondary sources
- prefer 2–3 strong implementation examples over large noisy lists
- prefer fresh problem evidence when tooling is fast-moving
- do not inflate source counts for appearance
- do not pretend shallow retrieval is deep research

---

## Forum usage rules

Forums may be used when:

- authoritative docs are incomplete
- practical breakage matters
- migration pain points matter
- troubleshooting patterns are needed
- there is evidence that docs and reality diverge

Forums should mainly contribute to:
- risk sections
- issue-pattern findings
- anti-pattern sections
- workaround notes

They should rarely dominate architecture recommendations.

---

## Repository usage rules

Repositories should be evaluated by:

- maintenance activity
- recency
- install clarity
- issue/discussion quality
- evidence of real-world usage
- structural similarity to the target problem

Do not treat every GitHub repo as a valid “solution candidate”.

---

## Source recording rules

Every selected source should capture:

- what it is
- why it matters
- which bucket it belongs to
- how much confidence it deserves
- whether it is authoritative, implementation-oriented, or issue-oriented

The system must distinguish clearly between:
- authoritative sources
- implementation sources
- issue/problem sources
- illustrative/community sources

---

## Minimum bounded retrieval guidance

### Mode: `none`
- no external sources required
- planning may remain local-only

### Mode: `quick`
Target:
- 1–2 authoritative sources
- 2–3 strong implementation candidates
- 1–3 recurring risk/problem signals

### Mode: `deep`
Target:
- broader bucket coverage
- more explicit comparison
- more problem evidence
- stronger provenance density

The exact counts may vary, but bounded research must remain compact and purposeful.

---

## Quality expectations

A good source mix should usually show:

- at least one authoritative anchor when available
- at least one real implementation signal when implementation matters
- at least one issue/risk signal when failure risk matters
- no forum-only architecture recommendation unless unavoidable

---

## Anti-patterns

Do not:

- rely only on forums when official docs exist
- rely only on official docs when real-world breakage is central
- collect many weak sources instead of a few strong ones
- treat search ranking as proof of quality
- treat raw retrieval as finished research
- let one noisy bucket dominate all findings

---

## Practical meaning for this project

For this project, the intended research pattern is:

1. memory first
2. detect missing information
3. search externally by bucket
4. fetch selected sources
5. derive findings with provenance
6. write compact planning-oriented artifacts
7. only then hand off to coding / planning / orchestration

This policy must remain compatible with:
- current `chatgpt_codex` usage
- future `openai_api` automation
- future `searxng` integration
- shared validator/eval/regression logic