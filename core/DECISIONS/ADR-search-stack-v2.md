# ADR: Search Stack v2 for project-research

## Status
Accepted

## Date
2026-03-16

## Context

The current `project-research-run` now supports:
- `manual_curated` default backend
- optional live `searxng` retrieval
- artifact-level search metadata in `context.json` and `sources.json`
- validated source/provenance linkage

However, raw external retrieval quality is still below the desired level.
The main issue is not only search access, but retrieval policy and evidence selection quality.

A practical failure case was observed with AGH (AdGuard Home) installation on router:
- install source repo was known
- the needed configuration guidance already existed in the repository README
- the assistant did not prioritize exact-repo documentation first
- time was wasted on generic reasoning and external detours

This shows that the retrieval system must become repository-aware and documentation-aware.

## Decision

We adopt a six-layer search architecture for `project-research`:

1. Query fan-out / query planning
2. Candidate cleaning / source normalization
3. Fetch + extraction
4. Local hybrid retrieval index
5. Rerank
6. Answer synthesis with source policy

Additionally, we adopt a hard rule:

### Repo-docs-first rule
If a specific repository, install script, or project source is known, retrieval must prioritize exact repository documentation before broad web search.

Priority order:

1. `README*`
2. `docs/`
3. `examples/`
4. install/setup/configuration files
5. `docker-compose*`, `.env.example`, sample configs
6. release notes / changelog
7. exact repo issues / discussions
8. only then generic external search

## Consequences

### Positive
- fewer wasted loops after installation
- better post-install configuration guidance
- less generic advice
- better relevance for GitHub-centered tasks
- closer behavior to high-quality research assistants

### Trade-offs
- more retrieval logic
- more metadata handling
- more complexity in source ranking
- need to track source origin and repo affinity explicitly

## Initial implementation order

### Layer 1
Add query planning with exact-repo and install-context awareness.

### Layer 2
Add source normalization, domain quality filters, and exact-repo prioritization.

### Layer 3
Add fetch + content extraction from selected pages.

### Layer 4
Add local hybrid retrieval store for extracted documents.

### Layer 5
Add rerank over extracted candidates.

### Layer 6
Add final synthesis rules with mandatory official-doc / repo-doc / issue-source balance.

## Required repository-aware behaviors

If the task mentions a known repo or exact install source, the system must explicitly try to extract:

- install steps
- post-install steps
- first-run steps
- config file location
- default URL / port / path
- UI setup steps
- environment variables
- sample configs
- known issues from exact repo

## Non-goals

- no blind trust in generic search snippets
- no skipping repo docs when repo identity is already known
- no forum-first behavior when exact docs are available
