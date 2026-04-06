# Implementation Plan

## Step 1: minimum viable creator

- create the package structure
- ship the canonical scaffold templates
- ship deterministic tree and lifecycle validation
- ship one-skill-under-test profile generation
- ship review-pack generation
- ship readiness gates and rollback-pack generation

Success condition:

- a new candidate managed skill can be scaffolded, validated, isolated for eval, and judged with deterministic readiness rules

## Step 2: hardening

- integrate the creator outputs more tightly with the existing eval harness
- add stronger warning coverage for weak trigger descriptions and platform-copy anti-patterns
- add packaging checks for richer managed-skill metadata conventions
- tighten readiness reports and invalidation handling

Success condition:

- creator outputs reduce manual review load and make invalid evidence harder to misread

## Step 3: wider managed-skill adoption support

- add richer semantic scoring and redundancy analysis against workspace bootstrap context
- add optional dashboards and reporting
- add v2 schema and lifecycle features once real adoption pressure justifies them

Success condition:

- the creator supports broader managed-skill rollout without relaxing evidence discipline
