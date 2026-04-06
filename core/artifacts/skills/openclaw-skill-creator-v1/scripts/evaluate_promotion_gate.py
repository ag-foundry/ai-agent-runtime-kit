#!/usr/bin/env python3
"""Evaluate whether an accepted-case-set contour clears the additive promotion gate."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from promote_accepted_case_set import evaluate_run_root, validate_manifest as validate_case_set_manifest


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def contract_path() -> Path:
    return package_root() / "definitions" / "promotion-checklist-contract.json"


def provenance_contract_path() -> Path:
    return package_root() / "definitions" / "promotion-provenance-report-contract.json"


def load_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {path}: {exc}") from exc


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require_non_empty_string(value: object, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise SystemExit(f"{label} must be a non-empty string")
    return text


def ensure_string_list(values: object, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise SystemExit(f"{label} must be a non-empty list")
    result = [require_non_empty_string(value, f"{label} entry") for value in values]
    return result


def validate_provenance_report(report: dict[str, object]) -> None:
    contract = load_json(provenance_contract_path())
    missing = [key for key in contract["required_top_level"] if key not in report]
    if missing:
        raise SystemExit(f"provenance report missing required keys: {', '.join(missing)}")
    if report.get("format") != contract["version"]:
        raise SystemExit(
            f"provenance report format must be {contract['version']!r}, got {report.get('format')!r}"
        )

    for collection_name, required_keys in (
        ("path_level_contexts", contract["required_path_context_keys"]),
        ("required_file_anchors", contract["required_file_anchor_keys"]),
        ("supporting_file_anchors", contract["required_file_anchor_keys"]),
    ):
        collection = report.get(collection_name)
        if not isinstance(collection, list):
            raise SystemExit(f"{collection_name} must be a list")
        for item in collection:
            if not isinstance(item, dict):
                raise SystemExit(f"{collection_name} entries must be objects")
            missing_keys = [key for key in required_keys if key not in item]
            if missing_keys:
                raise SystemExit(f"{collection_name} entry missing keys: {', '.join(missing_keys)}")


def validate_checklist(checklist: dict[str, object]) -> None:
    contract = load_json(contract_path())
    missing = [key for key in contract["required_top_level"] if key not in checklist]
    if missing:
        raise SystemExit(f"promotion checklist missing required keys: {', '.join(missing)}")
    if checklist.get("format") != contract["version"]:
        raise SystemExit(
            f"promotion checklist format must be {contract['version']!r}, got {checklist.get('format')!r}"
        )

    require_non_empty_string(checklist.get("case_set_id"), "case_set_id")
    require_non_empty_string(checklist.get("skill_name"), "skill_name")
    require_non_empty_string(checklist.get("registry_manifest_path"), "registry_manifest_path")
    require_non_empty_string(checklist.get("source_run_root"), "source_run_root")

    requirements = checklist.get("machine_requirements")
    if not isinstance(requirements, dict):
        raise SystemExit("machine_requirements must be an object")
    missing_requirements = [key for key in contract["required_machine_requirement_keys"] if key not in requirements]
    if missing_requirements:
        raise SystemExit(
            "machine_requirements missing required keys: " + ", ".join(missing_requirements)
        )
    if requirements["required_registry_status"] not in contract["allowed_registry_status_values"]:
        raise SystemExit(
            f"required_registry_status must be one of: {', '.join(contract['allowed_registry_status_values'])}"
        )
    if requirements["required_readiness_verdict"] not in contract["allowed_readiness_verdicts"]:
        raise SystemExit(
            f"required_readiness_verdict must be one of: {', '.join(contract['allowed_readiness_verdicts'])}"
        )
    for key in ("minimum_completed_reviews", "minimum_meaningful_delta_count"):
        if not isinstance(requirements[key], int) or requirements[key] < 0:
            raise SystemExit(f"machine_requirements.{key} must be an integer >= 0")
    for key in (
        "require_zero_pending_reviews",
        "require_zero_invalidated_reviews",
        "require_compatibility_ok",
        "require_reproducible_case_regeneration",
        "require_complete_provenance",
        "require_rollback_pack",
    ):
        if not isinstance(requirements[key], bool):
            raise SystemExit(f"machine_requirements.{key} must be a boolean")

    reproducibility = checklist.get("reproducibility")
    if not isinstance(reproducibility, dict):
        raise SystemExit("reproducibility must be an object")
    missing_repro = [key for key in contract["required_reproducibility_keys"] if key not in reproducibility]
    if missing_repro:
        raise SystemExit("reproducibility missing required keys: " + ", ".join(missing_repro))
    require_non_empty_string(reproducibility["regen_run_root"], "reproducibility.regen_run_root")
    if reproducibility["expected_case_source_type"] not in contract["allowed_case_source_types"]:
        raise SystemExit(
            "reproducibility.expected_case_source_type must be one of: "
            + ", ".join(contract["allowed_case_source_types"])
        )

    compatibility = checklist.get("compatibility")
    if not isinstance(compatibility, dict):
        raise SystemExit("compatibility must be an object")
    missing_compatibility = [key for key in contract["required_compatibility_keys"] if key not in compatibility]
    if missing_compatibility:
        raise SystemExit("compatibility missing required keys: " + ", ".join(missing_compatibility))
    require_non_empty_string(compatibility["harness_runner"], "compatibility.harness_runner")

    rollback = checklist.get("rollback")
    if not isinstance(rollback, dict):
        raise SystemExit("rollback must be an object")
    missing_rollback = [key for key in contract["required_rollback_keys"] if key not in rollback]
    if missing_rollback:
        raise SystemExit("rollback missing required keys: " + ", ".join(missing_rollback))
    require_non_empty_string(rollback["rollback_pack_manifest"], "rollback.rollback_pack_manifest")
    ensure_string_list(rollback["required_restore_sources"], "rollback.required_restore_sources")
    ensure_string_list(rollback["rollback_commands"], "rollback.rollback_commands")

    human_review = checklist.get("human_review")
    if not isinstance(human_review, dict):
        raise SystemExit("human_review must be an object")
    missing_human_review = [key for key in contract["required_human_review_keys"] if key not in human_review]
    if missing_human_review:
        raise SystemExit("human_review missing required keys: " + ", ".join(missing_human_review))
    if not isinstance(human_review["required"], bool):
        raise SystemExit("human_review.required must be a boolean")
    if not isinstance(human_review["checks"], list):
        raise SystemExit("human_review.checks must be a list")
    for item in human_review["checks"]:
        if not isinstance(item, dict):
            raise SystemExit("human_review checks entries must be objects")
        missing_human_check_keys = [key for key in contract["required_human_check_keys"] if key not in item]
        if missing_human_check_keys:
            raise SystemExit("human_review check missing keys: " + ", ".join(missing_human_check_keys))

    provenance = checklist.get("provenance")
    if provenance is not None:
        if not isinstance(provenance, dict):
            raise SystemExit("provenance must be an object when provided")
        missing_provenance_keys = [key for key in contract["required_provenance_keys"] if key not in provenance]
        if missing_provenance_keys:
            raise SystemExit("provenance missing required keys: " + ", ".join(missing_provenance_keys))
        require_non_empty_string(provenance["report_path"], "provenance.report_path")
        for key in ("minimum_path_level_contexts", "minimum_required_file_anchors"):
            if not isinstance(provenance[key], int) or provenance[key] < 0:
                raise SystemExit(f"provenance.{key} must be an integer >= 0")
        ensure_string_list(provenance["required_anchor_roles"], "provenance.required_anchor_roles")


def run_json_command(args: list[str]) -> tuple[int, dict[str, object] | None, str, str]:
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    stdout = completed.stdout.strip()
    parsed = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return completed.returncode, parsed, completed.stdout, completed.stderr


def build_result(criterion: str, kind: str, passed: bool | None, details: str, evidence: object = None) -> dict[str, object]:
    result: dict[str, object] = {
        "criterion": criterion,
        "kind": kind,
        "passed": passed,
        "details": details,
    }
    if evidence is not None:
        result["evidence"] = evidence
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checklist", required=True)
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    checklist_path = Path(args.checklist).resolve()
    checklist = load_json(checklist_path)
    validate_checklist(checklist)

    case_set_id = str(checklist["case_set_id"])
    skill_name = str(checklist["skill_name"])
    registry_manifest_path = Path(str(checklist["registry_manifest_path"])).resolve()
    source_run_root = Path(str(checklist["source_run_root"])).resolve()
    requirements = checklist["machine_requirements"]
    reproducibility = checklist["reproducibility"]
    compatibility = checklist["compatibility"]
    rollback = checklist["rollback"]
    human_review = checklist["human_review"]
    provenance = checklist.get("provenance")

    registry_manifest = load_json(registry_manifest_path)
    validate_case_set_manifest(registry_manifest)

    criteria: list[dict[str, object]] = []
    required_registry_status = str(requirements["required_registry_status"])
    actual_registry_status = str(registry_manifest.get("status", ""))
    criteria.append(
        build_result(
            "contour_status_matches_requirement",
            "machine-checkable",
            actual_registry_status == required_registry_status,
            f"registry manifest status is {actual_registry_status!r}; required {required_registry_status!r}",
        )
    )

    registry_case_set_id = str(registry_manifest.get("case_set_id", ""))
    registry_skill_name = str(registry_manifest.get("skill_name", ""))
    criteria.append(
        build_result(
            "registry_identity_matches_checklist",
            "machine-checkable",
            registry_case_set_id == case_set_id and registry_skill_name == skill_name,
            f"manifest case_set_id={registry_case_set_id!r}, skill_name={registry_skill_name!r}",
        )
    )

    manifest_source_run_root = Path(str(registry_manifest.get("source_run_root", ""))).resolve()
    criteria.append(
        build_result(
            "source_run_root_matches_registry_manifest",
            "machine-checkable",
            manifest_source_run_root == source_run_root,
            f"registry manifest source_run_root={manifest_source_run_root}",
        )
    )

    embedded_readiness = registry_manifest.get("promotion", {}).get("readiness_snapshot", {})
    live_readiness = evaluate_run_root(source_run_root, skill_name)
    criteria.append(
        build_result(
            "readiness_snapshot_matches_live_source_run",
            "machine-checkable",
            embedded_readiness == live_readiness,
            "embedded readiness snapshot matches a fresh evaluation of source_run_root",
            evidence={"embedded": embedded_readiness, "live": live_readiness},
        )
    )

    reviewed = int(live_readiness["reviewed"])
    criteria.append(
        build_result(
            "completed_reviews_threshold",
            "machine-checkable",
            reviewed >= int(requirements["minimum_completed_reviews"]),
            f"reviewed={reviewed}, minimum_required={requirements['minimum_completed_reviews']}",
        )
    )

    pending_case_ids = list(live_readiness["pending_case_ids"])
    criteria.append(
        build_result(
            "no_pending_reviews",
            "machine-checkable",
            (not requirements["require_zero_pending_reviews"]) or not pending_case_ids,
            f"pending_case_ids={pending_case_ids}",
        )
    )

    invalidated_case_ids = list(live_readiness["invalidated_case_ids"])
    criteria.append(
        build_result(
            "no_invalidated_evidence",
            "machine-checkable",
            (not requirements["require_zero_invalidated_reviews"]) or not invalidated_case_ids,
            f"invalidated_case_ids={invalidated_case_ids}",
            evidence=live_readiness.get("invalidated_reasons", {}),
        )
    )

    criteria.append(
        build_result(
            "readiness_verdict_requirement",
            "machine-checkable",
            live_readiness["verdict"] == requirements["required_readiness_verdict"],
            f"verdict={live_readiness['verdict']!r}, required={requirements['required_readiness_verdict']!r}",
        )
    )

    meaningful_delta_count = int(live_readiness["meaningful_delta_count"])
    criteria.append(
        build_result(
            "meaningful_delta_threshold",
            "machine-checkable",
            meaningful_delta_count >= int(requirements["minimum_meaningful_delta_count"]),
            f"meaningful_delta_count={meaningful_delta_count}, minimum_required={requirements['minimum_meaningful_delta_count']}",
        )
    )

    provenance_ok = True
    provenance_details: list[str] = []
    if not registry_manifest_path.is_file():
        provenance_ok = False
        provenance_details.append(f"missing registry manifest: {registry_manifest_path}")
    if not source_run_root.is_dir():
        provenance_ok = False
        provenance_details.append(f"missing source_run_root: {source_run_root}")
    promotion_script = Path(str(registry_manifest.get("promotion", {}).get("promotion_script", "")))
    if not promotion_script.is_file():
        provenance_ok = False
        provenance_details.append(f"missing promotion_script: {promotion_script}")
    evidence_run_roots = registry_manifest.get("evidence_run_roots", [])
    if not isinstance(evidence_run_roots, list) or not evidence_run_roots:
        provenance_ok = False
        provenance_details.append("evidence_run_roots is empty")
    else:
        for raw_path in evidence_run_roots:
            path = Path(str(raw_path))
            if not path.exists():
                provenance_ok = False
                provenance_details.append(f"missing evidence_run_root: {path}")

    cases = registry_manifest.get("cases", [])
    if not isinstance(cases, list) or not cases:
        provenance_ok = False
        provenance_details.append("registry manifest cases list is empty")
    else:
        for item in cases:
            if not isinstance(item, dict):
                provenance_ok = False
                provenance_details.append("registry manifest has non-object case entry")
                continue
            rel_path = Path(str(item.get("path", "")))
            accepted_case_path = registry_manifest_path.parent / rel_path
            source_case_path = Path(str(item.get("source_case_path", "")))
            source_review_path = Path(str(item.get("source_review_path", "")))
            if not accepted_case_path.is_file():
                provenance_ok = False
                provenance_details.append(f"missing accepted case file: {accepted_case_path}")
            if not source_case_path.is_file():
                provenance_ok = False
                provenance_details.append(f"missing source_case_path: {source_case_path}")
            if not source_review_path.is_file():
                provenance_ok = False
                provenance_details.append(f"missing source_review_path: {source_review_path}")
    criteria.append(
        build_result(
            "provenance_complete",
            "machine-checkable",
            (not requirements["require_complete_provenance"]) or provenance_ok,
            "; ".join(provenance_details) if provenance_details else "all declared provenance paths exist",
        )
    )

    if provenance is not None:
        provenance_report_path = Path(str(provenance["report_path"])).resolve()
        provenance_report = load_json(provenance_report_path)
        validate_provenance_report(provenance_report)
        criteria.append(
            build_result(
                "selective_provenance_report_identity",
                "machine-checkable",
                provenance_report.get("case_set_id") == case_set_id
                and provenance_report.get("skill_name") == skill_name
                and str(provenance_report.get("registry_manifest_path")) == str(registry_manifest_path)
                and str(provenance_report.get("source_run_root")) == str(source_run_root),
                f"provenance report path={provenance_report_path}",
            )
        )

        path_level_contexts = provenance_report.get("path_level_contexts", [])
        required_file_anchors = provenance_report.get("required_file_anchors", [])
        supporting_file_anchors = provenance_report.get("supporting_file_anchors", [])
        criteria.append(
            build_result(
                "path_level_contexts_declared",
                "machine-checkable",
                isinstance(path_level_contexts, list)
                and len(path_level_contexts) >= int(provenance["minimum_path_level_contexts"]),
                f"path_level_context_count={len(path_level_contexts)}, minimum_required={provenance['minimum_path_level_contexts']}",
                evidence=path_level_contexts,
            )
        )
        path_level_paths_exist = all(Path(str(item.get("path", ""))).exists() for item in path_level_contexts if isinstance(item, dict))
        criteria.append(
            build_result(
                "path_level_context_paths_exist",
                "machine-checkable",
                path_level_paths_exist,
                "all declared path-level context paths exist" if path_level_paths_exist else "one or more path-level context paths are missing",
            )
        )

        required_anchor_roles = sorted(set(ensure_string_list(provenance["required_anchor_roles"], "provenance.required_anchor_roles")))
        anchor_roles_present = sorted(
            {
                str(item.get("role"))
                for item in required_file_anchors
                if isinstance(item, dict) and item.get("role")
            }
        )
        criteria.append(
            build_result(
                "required_file_anchor_count",
                "machine-checkable",
                isinstance(required_file_anchors, list)
                and len(required_file_anchors) >= int(provenance["minimum_required_file_anchors"]),
                f"required_file_anchor_count={len(required_file_anchors)}, minimum_required={provenance['minimum_required_file_anchors']}",
            )
        )
        criteria.append(
            build_result(
                "required_anchor_roles_present",
                "machine-checkable",
                set(required_anchor_roles).issubset(set(anchor_roles_present)),
                f"required_roles={required_anchor_roles}, present_roles={anchor_roles_present}",
            )
        )
        required_anchor_paths_exist = all(
            Path(str(item.get("path", ""))).is_file()
            and (Path(str(item["backup_path"])).exists() if item.get("backup_path") else True)
            for item in required_file_anchors
            if isinstance(item, dict)
        )
        criteria.append(
            build_result(
                "required_file_anchors_exist",
                "machine-checkable",
                required_anchor_paths_exist,
                "all required file-level provenance anchors exist" if required_anchor_paths_exist else "one or more required file-level provenance anchors are missing",
                evidence={
                    "required_file_anchor_count": len(required_file_anchors),
                    "supporting_file_anchor_count": len(supporting_file_anchors),
                },
            )
        )

    regen_run_root = Path(str(reproducibility["regen_run_root"])).resolve()
    if regen_run_root.exists():
        if not args.force:
            raise SystemExit(f"regen_run_root already exists: {regen_run_root}; pass --force to replace it")
        shutil.rmtree(regen_run_root)

    profiles = registry_manifest.get("profiles", {})
    baseline_profile = profiles.get("baseline", {}).get("profile_name", "")
    trial_profile = profiles.get("trial", {}).get("profile_name", "")
    generate_args = [
        sys.executable,
        str(package_root() / "scripts" / "generate_review_pack.py"),
        "--run-root",
        str(regen_run_root),
        "--skill-name",
        skill_name,
        "--baseline-profile",
        str(baseline_profile),
        "--trial-profile",
        str(trial_profile),
        "--accepted-case-set",
        case_set_id,
    ]
    inventory_manifest = registry_manifest.get("inventory_manifest")
    if inventory_manifest:
        generate_args.extend(["--inventory-manifest", str(inventory_manifest)])
    generate_returncode, generate_json, generate_stdout, generate_stderr = run_json_command(generate_args)
    regen_manifest_path = regen_run_root / "summaries" / "review-pack-manifest.json"
    regen_trial_plan_path = regen_run_root / "summaries" / "trial-plan.json"
    regen_manifest = load_json(regen_manifest_path) if regen_manifest_path.is_file() else {}
    regen_trial_plan = load_json(regen_trial_plan_path) if regen_trial_plan_path.is_file() else {}
    criteria.append(
        build_result(
            "accepted_case_set_regeneration",
            "machine-checkable",
            (
                (not requirements["require_reproducible_case_regeneration"])
                or (
                    generate_returncode == 0
                    and regen_manifest.get("accepted_case_set") == case_set_id
                    and regen_trial_plan.get("accepted_case_set") == case_set_id
                )
            ),
            f"generate_review_pack exit_code={generate_returncode}",
            evidence={
                "command": generate_args,
                "stdout": generate_json if generate_json is not None else generate_stdout.strip(),
                "stderr": generate_stderr.strip(),
            },
        )
    )

    expected_case_ids = sorted(str(item["case_id"]) for item in cases if isinstance(item, dict) and item.get("case_id"))
    regenerated_case_ids = sorted(
        str(item.get("case_id"))
        for item in regen_trial_plan.get("cases", [])
        if isinstance(item, dict) and item.get("case_id")
    )
    regenerated_case_source_types = sorted(
        {str(item.get("case_source_type")) for item in regen_trial_plan.get("cases", []) if isinstance(item, dict)}
    )
    criteria.append(
        build_result(
            "regenerated_case_ids_match_registry",
            "machine-checkable",
            regenerated_case_ids == expected_case_ids,
            f"regenerated_case_ids={regenerated_case_ids}, expected_case_ids={expected_case_ids}",
        )
    )
    criteria.append(
        build_result(
            "regenerated_case_source_type_matches_expectation",
            "machine-checkable",
            regenerated_case_source_types == [str(reproducibility["expected_case_source_type"])],
            f"regenerated_case_source_types={regenerated_case_source_types}",
        )
    )

    compatibility_args = [
        sys.executable,
        str(package_root() / "scripts" / "check_eval_harness_compatibility.py"),
        "--run-root",
        str(regen_run_root),
        "--harness-runner",
        str(compatibility["harness_runner"]),
    ]
    compatibility_returncode, compatibility_json, compatibility_stdout, compatibility_stderr = run_json_command(
        compatibility_args
    )
    compatibility_ok = compatibility_returncode == 0 and isinstance(compatibility_json, dict) and bool(
        compatibility_json.get("ok")
    )
    criteria.append(
        build_result(
            "compatibility_check",
            "machine-checkable",
            (not requirements["require_compatibility_ok"]) or compatibility_ok,
            f"check_eval_harness_compatibility exit_code={compatibility_returncode}",
            evidence={
                "command": compatibility_args,
                "stdout": compatibility_json if compatibility_json is not None else compatibility_stdout.strip(),
                "stderr": compatibility_stderr.strip(),
            },
        )
    )

    rollback_pack_manifest_path = Path(str(rollback["rollback_pack_manifest"])).resolve()
    rollback_pack_manifest = load_json(rollback_pack_manifest_path)
    copied_items = rollback_pack_manifest.get("copied", [])
    copied_sources = sorted(
        str(item.get("source"))
        for item in copied_items
        if isinstance(item, dict) and item.get("source")
    )
    required_restore_sources = sorted(ensure_string_list(rollback["required_restore_sources"], "rollback.required_restore_sources"))
    rollback_pack_ok = rollback_pack_manifest_path.is_file() and set(required_restore_sources).issubset(set(copied_sources))
    criteria.append(
        build_result(
            "rollback_pack_available",
            "machine-checkable",
            (not requirements["require_rollback_pack"]) or rollback_pack_ok,
            f"rollback_pack_manifest={rollback_pack_manifest_path}",
            evidence={
                "required_restore_sources": required_restore_sources,
                "copied_sources": copied_sources,
            },
        )
    )
    rollback_commands = ensure_string_list(rollback["rollback_commands"], "rollback.rollback_commands")
    criteria.append(
        build_result(
            "rollback_commands_declared",
            "machine-checkable",
            bool(rollback_commands),
            f"rollback command count={len(rollback_commands)}",
            evidence=rollback_commands,
        )
    )

    for item in human_review["checks"]:
        criteria.append(
            build_result(
                str(item["check_id"]),
                "human-review-required",
                None,
                str(item["summary"]),
            )
        )

    machine_results = [item for item in criteria if item["kind"] == "machine-checkable"]
    human_results = [item for item in criteria if item["kind"] == "human-review-required"]
    machine_passed = all(bool(item["passed"]) for item in machine_results)
    if machine_passed and human_review["required"]:
        eligibility_verdict = "eligible pending human judgment"
    elif machine_passed:
        eligibility_verdict = "eligible"
    else:
        eligibility_verdict = "not eligible"

    report = {
        "format": "openclaw-promotion-eligibility-report-v1",
        "generated_at": now_utc_iso(),
        "checklist_path": str(checklist_path),
        "case_set_id": case_set_id,
        "skill_name": skill_name,
        "registry_manifest_path": str(registry_manifest_path),
        "source_run_root": str(source_run_root),
        "eligibility_verdict": eligibility_verdict,
        "machine_gate_passed": machine_passed,
        "auto_promotion_approved": machine_passed and not human_review["required"],
        "human_judgment_required": bool(human_review["required"]),
        "machine_check_count": len(machine_results),
        "human_check_count": len(human_results),
        "criteria": criteria,
    }

    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if machine_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
