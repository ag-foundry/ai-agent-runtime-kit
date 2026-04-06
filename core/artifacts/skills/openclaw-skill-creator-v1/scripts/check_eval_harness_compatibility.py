#!/usr/bin/env python3
"""Check whether creator outputs align with universal or legacy eval-harness runners."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skill_manifest import load_trial_contract


REQUIRED_DIRS = ["cases", "profiles", "raw", "results", "summaries"]
LEGACY_REQUIRED_CASE_FIELDS = ["case_id", "target_skill", "expected_trigger"]
UNIVERSAL_REQUIRED_CASE_FIELDS = ["case_id", "target_skill", "expected_trigger", "baseline_profile", "trial_profile"]


def parse_case_header(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    saw_header = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped and not saw_header:
            continue
        if not stripped:
            break
        if stripped.startswith("<!--"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
        saw_header = True
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument(
        "--harness-runner",
        default="/home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1/scripts/run_skill_trial_matrix.py",
    )
    parser.add_argument("--profile-manifest", action="append", default=[])
    args = parser.parse_args()

    run_root = Path(args.run_root)
    runner_path = Path(args.harness_runner)
    trial_contract = load_trial_contract()
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_DIRS:
        if not (run_root / rel).is_dir():
            errors.append(f"missing required run-root dir: {rel}")

    if not runner_path.exists():
        errors.append(f"harness runner missing: {runner_path}")
        result = {"ok": False, "errors": errors, "warnings": warnings}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    is_legacy_runner = runner_path.name == "run_managed_skills_matrix.py"
    review_pack_manifest_path = run_root / "summaries" / "review-pack-manifest.json"
    review_pack_manifest = None
    if review_pack_manifest_path.exists():
        review_pack_manifest = json.loads(review_pack_manifest_path.read_text(encoding="utf-8"))
    else:
        warnings.append(f"review-pack manifest missing: {review_pack_manifest_path}")

    trial_plan_path = run_root / "summaries" / "trial-plan.json"
    trial_plan = None
    if trial_plan_path.exists():
        trial_plan = json.loads(trial_plan_path.read_text(encoding="utf-8"))
    elif not is_legacy_runner:
        errors.append(f"universal trial plan missing: {trial_plan_path}")

    cases = []
    required_case_fields = UNIVERSAL_REQUIRED_CASE_FIELDS if (trial_plan is not None or not is_legacy_runner) else LEGACY_REQUIRED_CASE_FIELDS
    for case_path in sorted((run_root / "cases").glob("*.md")):
        header = parse_case_header(case_path)
        cases.append({"path": str(case_path), "header": header})
        for field in required_case_fields:
            if not header.get(field):
                errors.append(f"{case_path.name} missing case header field: {field}")
        case_id = header.get("case_id", case_path.stem)
        expected_review = run_root / "results" / f"{case_id}-review.md"
        if not expected_review.exists():
            errors.append(f"missing pair-review file for case: {case_id}")
        for mode in ["baseline", "with-skill"]:
            expected_raw_dir = run_root / "raw" / case_id / mode
            if not expected_raw_dir.is_dir():
                errors.append(f"missing raw dir for {case_id}: {expected_raw_dir}")

    if review_pack_manifest is not None and review_pack_manifest.get("case_count") != len(cases):
        errors.append("review-pack case_count does not match the number of case files")

    manifests = {}
    for raw_path in args.profile_manifest:
        manifest_path = Path(raw_path)
        if not manifest_path.exists():
            errors.append(f"profile manifest missing: {manifest_path}")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests[manifest.get("profile_name", manifest_path.name)] = manifest

    baseline_profiles: set[str] = set()
    trial_profiles: dict[str, str] = {}
    if trial_plan is not None:
        if trial_plan.get("format") != trial_contract["version"]:
            errors.append("trial-plan format does not match the universal contract")
        missing_top_level = [key for key in trial_contract["required_top_level"] if key not in trial_plan]
        if missing_top_level:
            errors.append(f"trial-plan missing top-level keys: {', '.join(missing_top_level)}")
        if sorted(trial_plan.get("comparison_modes", [])) != sorted(trial_contract["required_comparison_modes"]):
            errors.append("trial-plan comparison_modes do not match the expected universal contract")
        for case in trial_plan.get("cases", []):
            for key in trial_contract["required_case_keys"]:
                if not case.get(key):
                    errors.append(f"trial-plan case missing key: {key}")
            baseline_profiles.add(case.get("baseline_profile", ""))
            trial_profiles[case.get("target_skill", "")] = case.get("trial_profile", "")
    else:
        for item in cases:
            header = item["header"]
            baseline_profiles.add(header.get("baseline_profile", ""))
            trial_profiles[header.get("target_skill", "")] = header.get("trial_profile", "")

    if manifests:
        for profile_name in sorted(name for name in baseline_profiles if name):
            baseline_manifest = manifests.get(profile_name)
            if baseline_manifest is None:
                errors.append(f"missing baseline profile manifest for {profile_name}")
                continue
            if baseline_manifest.get("profile_mode") != "baseline":
                errors.append(f"{profile_name} profile manifest must declare profile_mode=baseline")
            if baseline_manifest.get("enabled_skills") not in ([], None):
                errors.append(f"{profile_name} profile manifest must not enable managed skills")

        for skill_name, profile_name in sorted(trial_profiles.items()):
            if not skill_name or not profile_name:
                continue
            manifest = manifests.get(profile_name)
            if manifest is None:
                errors.append(f"missing trial profile manifest for {profile_name}")
                continue
            enabled_skills = manifest.get("enabled_skills") or []
            if enabled_skills != [skill_name]:
                errors.append(f"{profile_name} must enable exactly [{skill_name}]")
            if manifest.get("profile_mode") != "with-skill":
                errors.append(f"{profile_name} profile manifest must declare profile_mode=with-skill")

    result = {
        "ok": not errors,
        "run_root": str(run_root),
        "harness_runner": str(runner_path),
        "runner_mode": "legacy-fixed-path" if is_legacy_runner else "universal-manifest-driven",
        "case_count": len(cases),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
