#!/usr/bin/env python3
"""Validate a managed skill against the OpenClaw v1 lifecycle checks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from file_rules import INVOCATION_TEXT
from skill_manifest import load_metadata_contract, load_skill_frontmatter
NAME_RE = re.compile(r"^[a-z0-9-]+$")
GENERIC_DESCRIPTION_RE = re.compile(r"\b(managed skill|helper|tooling|workflow)\b", re.IGNORECASE)
PORTABILITY_LEAK_RE = re.compile(r"/home/agent|openclaw|agents/openai\.yaml|anthropic|claude code", re.IGNORECASE)


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def tree_spec_path() -> Path:
    return package_root() / "definitions" / "required-skill-tree.json"


def require_mapping(mapping: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be a mapping")
        return {}
    return value


def require_list(mapping: dict[str, Any], key: str, errors: list[str]) -> list[Any]:
    value = mapping.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    return value


def validate_tree(skill_dir: Path) -> tuple[list[str], list[str]]:
    spec = json.loads(tree_spec_path().read_text(encoding="utf-8"))
    errors = [f"missing required file: {path}" for path in spec.get("required_files", []) if not (skill_dir / path).exists()]
    warnings = [f"missing recommended dir: {path}" for path in spec.get("recommended_dirs", []) if not (skill_dir / path).exists()]
    return errors, warnings


def validate_skill(skill_dir: Path) -> tuple[list[str], list[str]]:
    contract = load_metadata_contract()
    enums = contract["enums"]
    capability_id_re = re.compile(contract["capability_id_pattern"])
    errors, warnings = validate_tree(skill_dir)
    frontmatter, content = load_skill_frontmatter(skill_dir)
    missing_top_level = [key for key in contract["top_level_required"] if key not in frontmatter]
    if missing_top_level:
        errors.append(f"missing top-level frontmatter keys: {', '.join(missing_top_level)}")
    unexpected = sorted(set(frontmatter.keys()) - set(contract["top_level_allowed"]))
    if unexpected:
        errors.append(f"unexpected top-level frontmatter keys: {', '.join(unexpected)}")

    name = frontmatter.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append("name must be a lowercase hyphen-case string")

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string")
    elif "use when" not in description.lower():
        warnings.append("description should say when the skill should trigger, preferably with 'Use when'")
    elif len(description.split()) < 10 or GENERIC_DESCRIPTION_RE.search(description):
        warnings.append("description may still be too generic; make the trigger and unique delta more explicit")
    if isinstance(description, str) and PORTABILITY_LEAK_RE.search(description):
        warnings.append("description appears to leak OpenClaw-only or provider-specific details into the portable core")

    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be a mapping")
        return errors, warnings

    openclaw = metadata.get("openclaw")
    if not isinstance(openclaw, dict):
        errors.append("metadata.openclaw must be a mapping")
        return errors, warnings

    if openclaw.get("invocation") not in set(enums["invocation"]):
        errors.append("metadata.openclaw.invocation has an unsupported value")
    if openclaw.get("maturity") not in set(enums["maturity"]):
        errors.append("metadata.openclaw.maturity has an unsupported value")

    profile = openclaw.get("profile")
    if not isinstance(profile, dict):
        warnings.append("metadata.openclaw.profile should describe the portable-core vs OpenClaw-only split")
    else:
        if profile.get("portability") not in set(enums["portability"]):
            warnings.append("metadata.openclaw.profile.portability should declare the portability split explicitly")
        portable_core_fields = profile.get("portable_core_fields")
        if portable_core_fields != ["name", "description"]:
            warnings.append("metadata.openclaw.profile.portable_core_fields should be ['name', 'description']")

    lifecycle = openclaw.get("lifecycle")
    if not isinstance(lifecycle, dict):
        warnings.append("metadata.openclaw.lifecycle should capture stage, readiness, and eval-harness intent")
    else:
        if lifecycle.get("stage") not in set(enums["lifecycle_stage"]):
            warnings.append("metadata.openclaw.lifecycle.stage should be one of: candidate, trial, accepted, retired")
        if lifecycle.get("readiness") not in set(enums["readiness"]):
            warnings.append(
                "metadata.openclaw.lifecycle.readiness should be one of: not-evaluated, review-pack-required, usable-with-caveats, usable-now, blocked"
            )
        if lifecycle.get("evidence") != "baseline-vs-with-skill":
            warnings.append("metadata.openclaw.lifecycle.evidence should be 'baseline-vs-with-skill'")
        if lifecycle.get("eval_harness") != "openclaw-skill-eval-harness-v1":
            warnings.append("metadata.openclaw.lifecycle.eval_harness should name the current shared harness")

    compatibility = require_mapping(openclaw, "compatibility", errors)
    runtime = require_list(compatibility, "runtime", errors) if compatibility else []
    require_list(compatibility, "os", errors) if compatibility else []
    requires = require_mapping(compatibility, "requires", errors) if compatibility else {}
    optional = require_mapping(compatibility, "optional", errors) if compatibility else {}

    if runtime and "openclaw" not in runtime:
        errors.append("metadata.openclaw.compatibility.runtime should include 'openclaw'")
    if requires:
        bins = requires.get("bins")
        if not isinstance(bins, list):
            errors.append("metadata.openclaw.compatibility.requires.bins must be a list")
    if optional:
        bins = optional.get("bins")
        if not isinstance(bins, list):
            errors.append("metadata.openclaw.compatibility.optional.bins must be a list")

    boundaries = require_mapping(openclaw, "boundaries", errors)
    if boundaries:
        if boundaries.get("bridge_mode") not in set(enums["bridge_mode"]):
            errors.append("metadata.openclaw.boundaries.bridge_mode has an unsupported value")
        if boundaries.get("writes") not in set(enums["write_mode"]):
            errors.append("metadata.openclaw.boundaries.writes has an unsupported value")
        if boundaries.get("network") not in set(enums["network_mode"]):
            errors.append("metadata.openclaw.boundaries.network has an unsupported value")

    capabilities = require_mapping(openclaw, "capabilities", errors)
    if capabilities:
        primary = require_list(capabilities, "primary", errors)
        secondary = require_list(capabilities, "secondary", errors)
        surfaces = require_mapping(capabilities, "surfaces", errors)
        evidence = require_mapping(capabilities, "evidence", errors)
        for value in primary + secondary:
            if not isinstance(value, str) or not capability_id_re.match(value):
                errors.append("metadata.openclaw.capabilities primary/secondary entries must be lowercase hyphen-case ids")
                break
        if not primary:
            warnings.append("metadata.openclaw.capabilities.primary should not be empty")
        if surfaces:
            require_list(surfaces, "inputs", errors)
            require_list(surfaces, "outputs", errors)
            require_list(surfaces, "artifacts", errors)
        if evidence:
            if evidence.get("trial_method") not in set(enums["trial_method"]):
                errors.append("metadata.openclaw.capabilities.evidence.trial_method has an unsupported value")
            require_list(evidence, "delta_signals", errors)
            require_list(evidence, "safety_focus", errors)

    line_count = len(content.splitlines())
    if line_count > 500:
        warnings.append(f"SKILL.md is long ({line_count} lines); consider moving detail into references/")

    lowered = content.lower()
    do_not_copy_ref = skill_dir / "references" / "do-not-copy-literally.md"
    if ("anthropic" in lowered or "claude code" in lowered) and not do_not_copy_ref.exists():
        warnings.append("Anthropic-specific references detected without a do-not-copy-literally note")
    if ("agents/openai.yaml" in lowered or "openai.yaml" in lowered) and not do_not_copy_ref.exists():
        warnings.append("Codex interface metadata reference detected without a do-not-copy-literally note")
    if "this is a managed openclaw skill scaffold generated by `openclaw-skill-creator-v1`" in lowered:
        warnings.append("SKILL.md still contains the scaffold placeholder sentence; replace it with real skill guidance")

    expected_invocation_files = [
        skill_dir / "SKILL.md",
        skill_dir / "references" / "portability-core-vs-profile.md",
        skill_dir / "references" / "do-not-copy-literally.md",
        skill_dir / "references" / "eval-plan.md",
    ]
    for path in expected_invocation_files:
        if path.exists() and INVOCATION_TEXT not in path.read_text(encoding="utf-8"):
            warnings.append(f"invocation-line comment missing from generated text file: {path.relative_to(skill_dir)}")

    portability_ref = skill_dir / "references" / "portability-core-vs-profile.md"
    if portability_ref.exists():
        portability_text = portability_ref.read_text(encoding="utf-8").lower()
        if "portable core" not in portability_text or "metadata.openclaw" not in portability_text:
            warnings.append("references/portability-core-vs-profile.md should explain portable core and metadata.openclaw separation")

    eval_plan_ref = skill_dir / "references" / "eval-plan.md"
    if eval_plan_ref.exists():
        eval_plan_text = eval_plan_ref.read_text(encoding="utf-8").lower()
        for needle, message in [
            ("baseline-vs-with-skill", "references/eval-plan.md should mention baseline-vs-with-skill"),
            ("raw outputs", "references/eval-plan.md should mention saved raw outputs"),
            ("readiness", "references/eval-plan.md should mention readiness gates"),
        ]:
            if needle not in eval_plan_text:
                warnings.append(message)

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root)
    try:
        errors, warnings = validate_skill(root)
    except Exception as exc:
        result = {"root": str(root), "ok": False, "errors": [str(exc)], "warnings": []}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    result = {
        "root": str(root),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
