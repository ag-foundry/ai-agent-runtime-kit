#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path("/home/agent/agents/_shared/skills/project-research-v2-draft")

errors: list[str] = []
warnings: list[str] = []


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def add_error(msg: str) -> None:
    errors.append(msg)


def add_warning(msg: str) -> None:
    warnings.append(msg)


def require_exists(path: Path) -> None:
    if not path.exists():
        add_error(f"missing: {path}")


def load_json(path: Path):
    try:
        return json.loads(read_text(path))
    except Exception as e:
        add_error(f"invalid json: {path} :: {e}")
        return None


def check_required_files() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "SKILL.md",
        ROOT / "skill.json",
        ROOT / "references" / "VALIDATOR_REQUIREMENTS.md",
        ROOT / "policies" / "source_policy.md",
        ROOT / "policies" / "budget_policy.md",
        ROOT / "policies" / "quality_policy.md",
        ROOT / "policies" / "maintenance_hooks.md",
        ROOT / "evals" / "classification_cases.yaml",
        ROOT / "evals" / "source_quality_cases.yaml",
        ROOT / "evals" / "mixed_project_cases.yaml",
        ROOT / "evals" / "empty_memory_cases.yaml",
        ROOT / "schemas" / "context.schema.json",
        ROOT / "schemas" / "source.schema.json",
        ROOT / "schemas" / "finding.schema.json",
        ROOT / "schemas" / "research_report.schema.json",
        ROOT / "schemas" / "run_manifest.schema.json",
    ]
    for path in required:
        require_exists(path)


def check_skill_md() -> None:
    path = ROOT / "SKILL.md"
    if not path.exists():
        return

    text = read_text(path)

    if not text.startswith("---\n"):
        add_error("SKILL.md: missing YAML front matter at top")

    required_phrases = [
        "# project-research v2 draft",
        "## Goal",
        "## Main output contract",
        "## Use this skill when",
        "## Do not use this skill when",
        "## Core policy",
        "## Research modes",
        "## Required quality rules",
        "## Success criteria",
        "## Planned companion files",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            add_error(f"SKILL.md: missing section phrase: {phrase}")

    for item in ["run_manifest.json", "findings.jsonl", "provenance.json", "quality_report.json"]:
        if item not in text:
            add_error(f"SKILL.md: missing {item} in output contract")


def check_skill_json() -> None:
    path = ROOT / "skill.json"
    if not path.exists():
        return

    data = load_json(path)
    if data is None:
        return

    required_keys = [
        "name",
        "version",
        "status",
        "entry_policy",
        "description",
        "triggers",
        "modes",
        "required_outputs",
        "required_schemas",
        "quality_gates",
        "future_flows",
    ]
    for key in required_keys:
        if key not in data:
            add_error(f"skill.json: missing key: {key}")

    if data.get("name") != "project-research":
        add_error("skill.json: name must be project-research")

    status = data.get("status")
    if status not in {"draft", "active", "deprecated"}:
        add_error("skill.json: status must be one of draft|active|deprecated")

    if data.get("entry_policy") != "SKILL.md":
        add_error("skill.json: entry_policy must be SKILL.md")

    triggers = data.get("triggers", {})
    if "use_when" not in triggers:
        add_error("skill.json: triggers.use_when missing")
    if "avoid_when" not in triggers:
        add_error("skill.json: triggers.avoid_when missing")

    modes = data.get("modes", {})
    for mode_name in ["none", "quick", "deep"]:
        if mode_name not in modes:
            add_error(f"skill.json: modes.{mode_name} missing")

    expected_outputs = {
        "RESEARCH.md",
        "sources.json",
        "run_manifest.json",
        "findings.jsonl",
        "provenance.json",
        "quality_report.json",
    }
    missing_outputs = expected_outputs - set(data.get("required_outputs", []))
    for item in sorted(missing_outputs):
        add_error(f"skill.json: required_outputs missing: {item}")

    for rel in data.get("required_schemas", []):
        require_exists(ROOT / rel)

    expected_gates = {
        "search_targets_have_query_sets",
        "no_memory_boilerplate_dominance",
        "starting_approach_not_generic",
        "anti_patterns_present",
        "provenance_present_for_findings",
    }
    missing_gates = expected_gates - set(data.get("quality_gates", []))
    for gate in sorted(missing_gates):
        add_error(f"skill.json: quality_gates missing: {gate}")

    for flow in ["watchtower", "housekeeper", "project-init"]:
        if flow not in set(data.get("future_flows", [])):
            add_error(f"skill.json: future_flows missing: {flow}")


def check_schema_files() -> None:
    for path in sorted((ROOT / "schemas").glob("*.json")):
        data = load_json(path)
        if data is None:
            continue
        if data.get("type") != "object":
            add_error(f"{path.name}: top-level type must be object")
        if "properties" not in data:
            add_error(f"{path.name}: missing properties")
        if "required" not in data:
            add_error(f"{path.name}: missing required")
        if "$schema" not in data:
            add_warning(f"{path.name}: missing $schema")
        if "title" not in data:
            add_warning(f"{path.name}: missing title")


def check_policy_files() -> None:
    for path in [
        ROOT / "policies" / "source_policy.md",
        ROOT / "policies" / "budget_policy.md",
        ROOT / "policies" / "quality_policy.md",
        ROOT / "policies" / "maintenance_hooks.md",
    ]:
        if path.exists() and len(read_text(path).strip()) < 40:
            add_error(f"{path.name}: suspiciously short")


def check_eval_files() -> None:
    for path in sorted((ROOT / "evals").glob("*")):
        if not path.is_file():
            continue
        text = read_text(path)
        if "cases:" not in text:
            add_warning(f"{path.name}: does not contain 'cases:' marker")

    classification = ROOT / "evals" / "classification_cases.yaml"
    if classification.exists():
        text = read_text(classification)
        if "expected_project_type" not in text:
            add_error("classification_cases.yaml: missing expected_project_type")
        if "expected_classes" not in text:
            add_error("classification_cases.yaml: missing expected_classes")


def check_banned_legacy_markers() -> None:
    banned = [
        "xmltv",
        "epg ",
        "django-only",
        "nextjs-only",
        "python-only",
        "youtube-only",
        "telegram-only",
    ]
    skip_files = {
        ROOT / "scripts" / "validate_skill.py",
        ROOT / "references" / "VALIDATOR_REQUIREMENTS.md",
    }

    collected = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p in skip_files:
            continue
        collected.append(read_text(p).lower())

    text_all = "\n".join(collected)
    for marker in banned:
        if marker in text_all:
            add_error(f"legacy/project-specific marker found: {marker}")


def check_script_presence() -> None:
    scripts_dir = ROOT / "scripts"
    if not scripts_dir.exists():
        add_error("scripts directory missing")
        return
    if not (scripts_dir / "validate_skill.py").exists():
        add_error("scripts/validate_skill.py missing")


def check_contract_intent() -> None:
    skill_md = ROOT / "SKILL.md"
    skill_json_path = ROOT / "skill.json"
    if not skill_md.exists() or not skill_json_path.exists():
        return

    text = read_text(skill_md).lower()
    data = load_json(skill_json_path)
    if data is None:
        return

    if "structured artifacts" not in text:
        add_warning("SKILL.md: structured-artifacts intent is not stated strongly")

    if len(data.get("required_schemas", [])) < 5:
        add_warning("skill.json: fewer than 5 required schemas declared")

    if len(data.get("quality_gates", [])) < 5:
        add_warning("skill.json: fewer than 5 quality gates declared")


def main() -> int:
    if not ROOT.exists():
        print(f"ROOT NOT FOUND: {ROOT}")
        return 2

    check_required_files()
    check_script_presence()
    check_skill_md()
    check_skill_json()
    check_schema_files()
    check_policy_files()
    check_eval_files()
    check_banned_legacy_markers()
    check_contract_intent()

    if errors:
        print("VALIDATION FAILED")
        for item in errors:
            print(f"- ERROR: {item}")
        if warnings:
            print()
            print("WARNINGS")
            for item in warnings:
                print(f"- WARN: {item}")
        return 1

    print("VALIDATION OK")
    print(f"root: {ROOT}")

    if warnings:
        print()
        print("WARNINGS")
        for item in warnings:
            print(f"- WARN: {item}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
