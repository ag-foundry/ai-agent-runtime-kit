#!/usr/bin/env python3
# Во имя Отца и Сына и Святаго Духа. Аминь.
"""Build a universal skill inventory manifest from skill roots and explicit skill dirs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skill_manifest import discover_skill_dirs, load_skill_frontmatter
from validate_skill_lifecycle import validate_skill


def classify_schema_status(errors: list[str]) -> str:
    return "creator-compatible" if not errors else "legacy-or-incomplete"


def build_entry(skill_dir: Path) -> dict[str, object]:
    errors, warnings = validate_skill(skill_dir)
    frontmatter, _content = load_skill_frontmatter(skill_dir)
    metadata = frontmatter.get("metadata") if isinstance(frontmatter.get("metadata"), dict) else {}
    openclaw = metadata.get("openclaw") if isinstance(metadata.get("openclaw"), dict) else {}
    capabilities = openclaw.get("capabilities") if isinstance(openclaw.get("capabilities"), dict) else {}
    lifecycle = openclaw.get("lifecycle") if isinstance(openclaw.get("lifecycle"), dict) else {}
    profile = openclaw.get("profile") if isinstance(openclaw.get("profile"), dict) else {}

    return {
        "skill_name": frontmatter.get("name", skill_dir.name),
        "skill_dir": str(skill_dir),
        "skill_file": str(skill_dir / "SKILL.md"),
        "description": frontmatter.get("description", ""),
        "invocation": openclaw.get("invocation"),
        "maturity": openclaw.get("maturity"),
        "schema_state": classify_schema_status(errors),
        "creator_compatible": not errors,
        "creator_schema_errors": errors,
        "creator_schema_warnings": warnings,
        "portability": profile.get("portability"),
        "lifecycle_stage": lifecycle.get("stage"),
        "readiness": lifecycle.get("readiness"),
        "trial_method": ((capabilities.get("evidence") or {}).get("trial_method") if isinstance(capabilities, dict) else None),
        "primary_capabilities": capabilities.get("primary", []) if isinstance(capabilities, dict) else [],
        "secondary_capabilities": capabilities.get("secondary", []) if isinstance(capabilities, dict) else [],
        "interfaces": capabilities.get("surfaces", {}) if isinstance(capabilities, dict) else {},
        "compatibility": openclaw.get("compatibility", {}),
        "boundaries": openclaw.get("boundaries", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", action="append", default=[])
    parser.add_argument("--skill-dir", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()

    skills_roots = [Path(path) for path in (args.skills_root or ["/home/agent/.openclaw/skills"])]
    explicit_skill_dirs = [Path(path) for path in args.skill_dir]
    skill_dirs = discover_skill_dirs(skills_roots, explicit_skill_dirs)

    manifest = {
        "format": "openclaw-skill-inventory-v1",
        "skills_root_inputs": [str(path) for path in skills_roots],
        "skill_dir_inputs": [str(path) for path in explicit_skill_dirs],
        "skill_count": len(skill_dirs),
        "skills": [build_entry(skill_dir) for skill_dir in skill_dirs],
    }
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
