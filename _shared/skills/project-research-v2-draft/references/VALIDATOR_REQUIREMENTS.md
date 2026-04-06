# validator_requirements

The v2 validator must check:

- required files exist
- `SKILL.md` has front matter and mandatory sections
- `skill.json` exists and is parseable JSON
- all schema files listed in `skill.json` exist
- all required outputs are declared
- all quality gates are declared
- no banned project-specific legacy markers exist
- every target planned in `search_targets` must later be backed by `query_sets`
- future flows are declared but not mixed into core skill behavior
