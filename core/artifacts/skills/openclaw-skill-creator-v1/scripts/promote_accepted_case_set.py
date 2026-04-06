#!/usr/bin/env python3
"""Promote a proven trial contour into the package accepted-case registry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from evaluate_readiness import (
    analyze_matrix_manifest,
    evaluate_group,
    gates_path,
    load_expected_cases,
    parse_review,
)
from file_rules import apply_invocation_line


ACCEPTED_CASE_SET_FORMAT = "openclaw-accepted-case-set-v1"
ALLOWED_STATUS_VALUES = {"accepted", "candidate", "superseded"}


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def accepted_case_set_root() -> Path:
    return package_root() / "accepted-case-sets"


def contract_path() -> Path:
    return package_root() / "definitions" / "accepted-case-set-contract.json"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(apply_invocation_line(path, content), encoding="utf-8")


def load_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {path}: {exc}") from exc


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def unique_strings(values) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered


def evaluate_run_root(run_root: Path, target_skill: str) -> dict[str, object]:
    gates = load_json(gates_path())
    results_dir = run_root / "results"
    matrix_manifest = run_root / "summaries" / "matrix-run-manifest.json"
    manifest_evidence: dict[str, dict[str, object]] = {}
    if matrix_manifest.exists():
        manifest_evidence = analyze_matrix_manifest(matrix_manifest, gates)
    expected_case_ids, _warnings = load_expected_cases(results_dir, run_root)

    reviews = []
    for path in sorted(results_dir.glob("*.md")):
        fields = parse_review(path)
        if fields.get("target_skill") == target_skill:
            reviews.append(fields)
    if not reviews:
        raise SystemExit(f"no review files for target skill {target_skill!r} found under {results_dir}")
    return evaluate_group(
        target_skill,
        reviews,
        gates,
        {fields.get("case_id", "") for fields in reviews if fields.get("case_id")} or expected_case_ids,
        manifest_evidence,
    )


def validate_manifest(manifest: dict[str, object]) -> None:
    contract = load_json(contract_path())
    missing = [key for key in contract["required_top_level"] if key not in manifest]
    if missing:
        raise SystemExit(f"accepted case-set manifest missing required keys: {', '.join(missing)}")
    status = manifest.get("status")
    if status not in contract["allowed_status_values"]:
        raise SystemExit(f"accepted case-set manifest has unsupported status: {status!r}")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("accepted case-set manifest must contain a non-empty cases list")
    for item in cases:
        if not isinstance(item, dict):
            raise SystemExit("accepted case-set cases entries must be objects")
        missing_case_keys = [key for key in contract["required_case_keys"] if key not in item]
        if missing_case_keys:
            raise SystemExit(f"accepted case-set case entry missing keys: {', '.join(missing_case_keys)}")
    promotion = manifest.get("promotion")
    if not isinstance(promotion, dict):
        raise SystemExit("accepted case-set manifest promotion field must be an object")
    missing_promotion_keys = [key for key in contract["required_promotion_keys"] if key not in promotion]
    if missing_promotion_keys:
        raise SystemExit(f"accepted case-set manifest promotion object missing keys: {', '.join(missing_promotion_keys)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--case-set-id", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--accepted-on")
    parser.add_argument("--status", default="accepted")
    parser.add_argument("--evidence-run-root", action="append", default=[])
    parser.add_argument("--registry-root")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.status not in ALLOWED_STATUS_VALUES:
        raise SystemExit(f"--status must be one of: {', '.join(sorted(ALLOWED_STATUS_VALUES))}")

    run_root = Path(args.run_root)
    trial_plan_path = run_root / "summaries" / "trial-plan.json"
    review_pack_manifest_path = run_root / "summaries" / "review-pack-manifest.json"
    if not trial_plan_path.is_file():
        raise SystemExit(f"trial plan missing: {trial_plan_path}")
    if not review_pack_manifest_path.is_file():
        raise SystemExit(f"review-pack manifest missing: {review_pack_manifest_path}")

    trial_plan = load_json(trial_plan_path)
    review_pack = load_json(review_pack_manifest_path)
    cases = trial_plan.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("trial-plan.json must contain at least one case")

    target_skills = unique_strings(item.get("target_skill", "") for item in cases)
    if len(target_skills) != 1:
        raise SystemExit(f"promotion currently requires exactly one target skill per run root, got: {target_skills}")
    skill_name = target_skills[0]

    declared_capabilities = unique_strings(
        capability
        for item in cases
        for capability in (item.get("declared_capabilities") or [])
    )
    if not declared_capabilities:
        declared_capabilities = unique_strings(review_pack.get("declared_capabilities") or [])
    source_pack_selection_policy = trial_plan.get("pack_selection_policy") or review_pack.get("pack_selection_policy")
    source_pack_selection_manifest = trial_plan.get("pack_selection_manifest") or review_pack.get("pack_selection_manifest")
    source_pack_selection_trace = trial_plan.get("pack_selection_trace") or review_pack.get("pack_selection_trace")
    source_global_managed_policy_registry = trial_plan.get("global_managed_policy_registry") or review_pack.get("global_managed_policy_registry")
    source_global_managed_launch_manifest = trial_plan.get("global_managed_launch_manifest") or review_pack.get("global_managed_launch_manifest")
    source_global_managed_launch_trace = trial_plan.get("global_managed_launch_trace") or review_pack.get("global_managed_launch_trace")
    source_global_managed_memory_fabric = trial_plan.get("global_managed_memory_fabric") or review_pack.get("global_managed_memory_fabric")
    source_global_managed_memory_selection = trial_plan.get("global_managed_memory_selection") or review_pack.get("global_managed_memory_selection")
    source_global_managed_default_path_enforced = trial_plan.get("global_managed_default_path_enforced")
    if source_global_managed_default_path_enforced is None:
        source_global_managed_default_path_enforced = review_pack.get("global_managed_default_path_enforced")
    source_global_managed_override = trial_plan.get("global_managed_override")
    if source_global_managed_override is None:
        source_global_managed_override = review_pack.get("global_managed_override")
    source_global_managed_invocation_mode = trial_plan.get("global_managed_invocation_mode")
    if source_global_managed_invocation_mode is None:
        source_global_managed_invocation_mode = review_pack.get("global_managed_invocation_mode")

    readiness_snapshot = evaluate_run_root(run_root, skill_name)
    registry_root = Path(args.registry_root) if args.registry_root else accepted_case_set_root()
    target_root = registry_root / args.case_set_id
    if target_root.exists() and not args.force:
        raise SystemExit(f"target case-set directory already exists: {target_root}; pass --force to overwrite")

    cases_root = target_root / "cases"
    cases_root.mkdir(parents=True, exist_ok=True)

    promoted_cases: list[dict[str, object]] = []
    for item in cases:
        case_id = str(item["case_id"])
        source_case_path = Path(str(item["case_path"]))
        if not source_case_path.is_file():
            raise SystemExit(f"source case file missing: {source_case_path}")
        target_case_path = cases_root / f"{case_id}.md"
        write_text(target_case_path, source_case_path.read_text(encoding="utf-8"))
        promoted_cases.append(
            {
                "case_id": case_id,
                "path": str(target_case_path.relative_to(target_root)),
                "expected_trigger": item.get("expected_trigger", "yes"),
                "declared_capabilities": item.get("declared_capabilities", []),
                "source_case_path": str(source_case_path),
                "source_review_path": str(item.get("review_path", "")),
            }
        )

    manifest = {
        "format": ACCEPTED_CASE_SET_FORMAT,
        "case_set_id": args.case_set_id,
        "skill_name": skill_name,
        "status": args.status,
        "accepted_on": args.accepted_on or datetime.now().date().isoformat(),
        "description": args.description,
        "declared_capabilities": declared_capabilities,
        "comparison_modes": trial_plan.get("comparison_modes", ["baseline", "with-skill"]),
        "profiles": trial_plan.get("profiles", {}),
        "inventory_manifest": trial_plan.get("inventory_manifest"),
        "source_run_root": str(run_root),
        "evidence_run_roots": unique_strings([run_root, *args.evidence_run_root]),
        "source_pack_selection_policy": source_pack_selection_policy,
        "source_pack_selection_manifest": source_pack_selection_manifest,
        "source_pack_selection_trace": source_pack_selection_trace,
        "source_global_managed_policy_registry": source_global_managed_policy_registry,
        "source_global_managed_launch_manifest": source_global_managed_launch_manifest,
        "source_global_managed_launch_trace": source_global_managed_launch_trace,
        "source_global_managed_memory_fabric": source_global_managed_memory_fabric,
        "source_global_managed_memory_selection": source_global_managed_memory_selection,
        "source_global_managed_default_path_enforced": source_global_managed_default_path_enforced,
        "source_global_managed_override": source_global_managed_override,
        "source_global_managed_invocation_mode": source_global_managed_invocation_mode,
        "cases": promoted_cases,
        "promotion": {
            "promoted_at": now_utc_iso(),
            "promotion_script": str(Path(__file__).resolve()),
            "readiness_snapshot": readiness_snapshot,
            "source_pack_selection_policy": source_pack_selection_policy,
            "source_pack_selection_manifest": source_pack_selection_manifest,
            "source_pack_selection_trace": source_pack_selection_trace,
            "source_global_managed_policy_registry": source_global_managed_policy_registry,
            "source_global_managed_launch_manifest": source_global_managed_launch_manifest,
            "source_global_managed_launch_trace": source_global_managed_launch_trace,
            "source_global_managed_memory_fabric": source_global_managed_memory_fabric,
            "source_global_managed_memory_selection": source_global_managed_memory_selection,
            "source_global_managed_default_path_enforced": source_global_managed_default_path_enforced,
            "source_global_managed_override": source_global_managed_override,
            "source_global_managed_invocation_mode": source_global_managed_invocation_mode,
        },
    }
    validate_manifest(manifest)
    (target_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
