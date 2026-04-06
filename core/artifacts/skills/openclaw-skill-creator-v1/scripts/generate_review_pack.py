#!/usr/bin/env python3
"""Generate a baseline-vs-with-skill review pack skeleton."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from file_rules import apply_invocation_line
from skill_manifest import normalize_profile_name


PLACEHOLDER_PATTERN = re.compile(r"__([A-Z_]+)__")
NAME_RE = re.compile(r"^[a-z0-9-]+$")
RAW_FILES = [
    "assistant.txt",
    "command.txt",
    "prompt.txt",
    "response.json",
    "run-summary.json",
    "stdout.txt",
]
ACCEPTED_CASE_SET_FORMAT = "openclaw-accepted-case-set-v1"
PACK_SELECTION_POLICY_FORMAT = "openclaw-pack-selection-policy-v1"
PACK_SELECTION_MANIFEST_FORMAT = "openclaw-pack-selection-manifest-v1"
PACK_SELECTION_TRACE_FORMAT = "openclaw-pack-selection-trace-v1"
PACK_SELECTION_ALLOWED_ROLES = {"primary", "supporting", "excluded"}


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def template_root() -> Path:
    return package_root() / "templates" / "eval-pack"


def accepted_case_set_root() -> Path:
    return package_root() / "accepted-case-sets"


def definition_root() -> Path:
    return package_root() / "definitions"


def pack_selection_policy_path() -> Path:
    return definition_root() / "pack-selection-policy-v1.json"


def pack_selection_manifest_contract_path() -> Path:
    return definition_root() / "pack-selection-manifest-contract.json"


def pack_selection_trace_contract_path() -> Path:
    return definition_root() / "pack-selection-trace-contract.json"


def render_text(text: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return values[match.group(1)]

    return PLACEHOLDER_PATTERN.sub(replace, text)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(apply_invocation_line(path, content), encoding="utf-8")


def require_valid_name(name: str, label: str) -> None:
    if not NAME_RE.match(name):
        raise SystemExit(f"{label} must be lowercase hyphen-case")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {path}: {exc}") from exc


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_case_header_text(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    saw_header = False
    for line in content.splitlines():
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


def replace_structured_header(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}: .*$", re.MULTILINE)
    replacement = f"{key}: {value}"
    if not pattern.search(content):
        raise SystemExit(f"accepted case file is missing required header: {key}")
    return pattern.sub(replacement, content, count=1)


def load_accepted_case_set(case_set_id: str) -> tuple[Path, dict[str, object]]:
    manifest_path = accepted_case_set_root() / case_set_id / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"accepted case set manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"accepted case set manifest is not valid JSON: {manifest_path}: {exc}") from exc
    if manifest.get("format") != ACCEPTED_CASE_SET_FORMAT:
        raise SystemExit(
            f"accepted case set manifest has unsupported format: {manifest.get('format')!r}; "
            f"expected {ACCEPTED_CASE_SET_FORMAT!r}"
        )
    return manifest_path, manifest


def resolve_accepted_case_specs(
    manifest_path: Path,
    manifest: dict[str, object],
    requested_case_ids: list[str],
    skill_name: str,
    baseline_profile: str,
    trial_profile: str,
    declared_capabilities: list[str],
) -> list[dict[str, str]]:
    manifest_skill = manifest.get("skill_name")
    if manifest_skill != skill_name:
        raise SystemExit(
            f"accepted case set skill mismatch: manifest targets {manifest_skill!r}, "
            f"but --skill-name was {skill_name!r}"
        )
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("accepted case set manifest must define a non-empty cases list")

    case_map: dict[str, dict[str, object]] = {}
    ordered_case_ids: list[str] = []
    for item in cases:
        if not isinstance(item, dict):
            raise SystemExit("accepted case set cases entries must be objects")
        case_id = item.get("case_id")
        rel_path = item.get("path")
        if not isinstance(case_id, str) or not isinstance(rel_path, str):
            raise SystemExit("accepted case set case entries must include string case_id and path")
        require_valid_name(case_id, "accepted case set case id")
        case_map[case_id] = item
        ordered_case_ids.append(case_id)

    selected_case_ids = requested_case_ids or ordered_case_ids
    specs: list[dict[str, str]] = []
    for case_id in selected_case_ids:
        if case_id not in case_map:
            raise SystemExit(f"case id {case_id!r} is not present in accepted case set {manifest_path.parent.name!r}")
        source_path = manifest_path.parent / str(case_map[case_id]["path"])
        if not source_path.is_file():
            raise SystemExit(f"accepted case file not found: {source_path}")
        content = source_path.read_text(encoding="utf-8")
        content = replace_structured_header(content, "case_id", case_id)
        content = replace_structured_header(content, "target_skill", skill_name)
        content = replace_structured_header(content, "baseline_profile", baseline_profile)
        content = replace_structured_header(content, "trial_profile", trial_profile)
        content = replace_structured_header(content, "declared_capabilities", ", ".join(declared_capabilities))
        specs.append(
            {
                "case_id": case_id,
                "case_text": content,
                "case_source_type": "accepted-case-set",
                "case_source_ref": f"{manifest_path}:{source_path.relative_to(manifest_path.parent)}",
            }
        )
    return specs


def resolve_source_case_specs(
    case_files: list[str],
    skill_name: str,
    baseline_profile: str,
    trial_profile: str,
    declared_capabilities: list[str],
) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    seen_case_ids: set[str] = set()
    for raw_path in case_files:
        source_path = Path(raw_path).resolve()
        if not source_path.is_file():
            raise SystemExit(f"source case file not found: {source_path}")
        content = source_path.read_text(encoding="utf-8")
        header = parse_case_header_text(content)
        case_id = header.get("case_id", source_path.stem)
        require_valid_name(case_id, "source case id")
        if case_id in seen_case_ids:
            raise SystemExit(f"duplicate case id from --case-file inputs: {case_id}")
        seen_case_ids.add(case_id)
        content = replace_structured_header(content, "case_id", case_id)
        content = replace_structured_header(content, "target_skill", skill_name)
        content = replace_structured_header(content, "baseline_profile", baseline_profile)
        content = replace_structured_header(content, "trial_profile", trial_profile)
        content = replace_structured_header(content, "declared_capabilities", ", ".join(declared_capabilities))
        specs.append(
            {
                "case_id": case_id,
                "case_text": content,
                "case_source_type": "source-case-file",
                "case_source_ref": str(source_path),
            }
        )
    return specs


def create_case_and_review(
    run_root: Path,
    skill_name: str,
    case_id: str,
    baseline_profile: str,
    trial_profile: str,
    declared_capabilities: list[str],
    case_text_override: str | None = None,
    case_source_type: str = "template",
    case_source_ref: str = "template:case-template.md.tmpl",
) -> dict[str, object]:
    values = {
        "CASE_ID": case_id,
        "TARGET_SKILL": skill_name,
        "BASELINE_PROFILE": baseline_profile,
        "TRIAL_PROFILE": trial_profile,
        "DECLARED_CAPABILITIES": ", ".join(declared_capabilities),
        "BASELINE_RAW_DIR": str(run_root / "raw" / case_id / "baseline"),
        "WITH_SKILL_RAW_DIR": str(run_root / "raw" / case_id / "with-skill"),
        "BASELINE_RUN_SUMMARY": str(run_root / "raw" / case_id / "baseline" / "run-summary.json"),
        "WITH_SKILL_RUN_SUMMARY": str(run_root / "raw" / case_id / "with-skill" / "run-summary.json"),
    }
    case_text = case_text_override or render_text((template_root() / "case-template.md.tmpl").read_text(encoding="utf-8"), values)
    review_text = render_text((template_root() / "review-template.md.tmpl").read_text(encoding="utf-8"), values)

    case_path = run_root / "cases" / f"{case_id}.md"
    review_path = run_root / "results" / f"{case_id}-review.md"
    write_text(case_path, case_text)
    write_text(review_path, review_text)

    baseline_raw = run_root / "raw" / case_id / "baseline"
    with_skill_raw = run_root / "raw" / case_id / "with-skill"
    baseline_raw.mkdir(parents=True, exist_ok=True)
    with_skill_raw.mkdir(parents=True, exist_ok=True)
    return {
        "case_id": case_id,
        "case_path": str(case_path),
        "review_path": str(review_path),
        "baseline_raw_dir": str(baseline_raw),
        "with_skill_raw_dir": str(with_skill_raw),
        "expected_raw_files": RAW_FILES,
        "baseline_profile": baseline_profile,
        "trial_profile": trial_profile,
        "declared_capabilities": declared_capabilities,
        "case_source_type": case_source_type,
        "case_source_ref": case_source_ref,
    }


def infer_plan_source(args: argparse.Namespace, accepted_case_manifest_path: Path | None) -> str:
    if accepted_case_manifest_path is not None:
        return "accepted-case-set"
    if args.case_file:
        return "source-case-files"
    return "template-case-ids"


def infer_pack_mode(args: argparse.Namespace, accepted_case_manifest_path: Path | None) -> str:
    if args.pack_mode:
        return args.pack_mode
    if accepted_case_manifest_path is not None:
        return "accepted_case_regeneration"
    return "manual_case_selection"


def parse_selection_artifact_spec(spec: str) -> tuple[str, Path]:
    role, separator, raw_path = spec.partition(":")
    if separator != ":" or role not in PACK_SELECTION_ALLOWED_ROLES or not raw_path.strip():
        raise SystemExit("--selection-artifact must use ROLE:/absolute/or/relative/path with role in primary|supporting|excluded")
    return role, Path(raw_path.strip()).expanduser().resolve()


def parse_case_selection_specs(values: list[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for raw in values:
        case_id, separator, remainder = raw.partition("|")
        selection_class, separator_two, reason = remainder.partition("|")
        if separator != "|" or separator_two != "|" or not case_id.strip() or not selection_class.strip() or not reason.strip():
            raise SystemExit("--case-selection must use case_id|selection_class|reason")
        case_id = case_id.strip()
        require_valid_name(case_id, "case selection case id")
        result[case_id] = {
            "selection_class": selection_class.strip(),
            "selection_reason": reason.strip(),
        }
    return result


def parse_rejected_case_specs(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        case_id, separator, reason = raw.partition("|")
        if separator != "|" or not case_id.strip() or not reason.strip():
            raise SystemExit("--rejected-case must use case_id|reason")
        case_id = case_id.strip()
        require_valid_name(case_id, "rejected case id")
        result[case_id] = reason.strip()
    return result


def classify_selection_artifact(path: Path, run_root: Path) -> str:
    name = path.name
    parts = set(path.parts)
    if name == "manifest.json" and "accepted-case-sets" in parts:
        return "accepted_case_manifest"
    if name == "review-pack-manifest.json":
        return "review_pack_manifest"
    if name == "trial-plan.json":
        return "trial_plan_manifest"
    if name == "matrix-run-manifest.json":
        return "matrix_run_manifest"
    if name == "RESULT-MATRIX.md":
        return "result_matrix"
    if name == "REPEATED-SIGNAL.md":
        return "repeated_signal"
    if name.startswith("READINESS"):
        return "readiness_artifact"
    if name == "VERDICT.md":
        return "verdict_artifact"
    if name == "REPORT.md":
        return "report_artifact"
    if name.endswith("-review.md"):
        return "review_artifact"
    if path.parent.name == "cases" and name.endswith(".md"):
        if path.is_relative_to(run_root):
            return "case_file"
        return "source_case_file"
    if name in RAW_FILES:
        return "raw_output"
    if name == "case-template.md.tmpl":
        return "template_scaffold"
    return "reference_document"


def artifact_currentness(path: Path, run_root: Path) -> str:
    if path.is_relative_to(run_root):
        return "current_run"
    if "accepted-case-sets" in path.parts:
        return "registry"
    if "runs" in path.parts:
        return "historical_run"
    return "reference"


def role_for_artifact(requested_role: str, admissibility: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if requested_role == "excluded":
        return "excluded", warnings
    if requested_role == "primary" and admissibility != "primary":
        warnings.append(f"primary role downgraded to supporting by policy admissibility={admissibility}")
        return "supporting", warnings
    return requested_role, warnings


def build_source_artifact_record(
    *,
    path: Path,
    requested_role: str,
    policy: dict[str, Any],
    run_root: Path,
    selected_case_ids: set[str],
    skill_name: str,
) -> tuple[dict[str, Any], list[str]]:
    artifact_kind = classify_selection_artifact(path, run_root)
    artifact_policy = policy["artifact_kinds"].get(artifact_kind, policy["artifact_kinds"]["reference_document"])
    resolved_role, warnings = role_for_artifact(requested_role, str(artifact_policy["admissibility"]))
    currentness = artifact_currentness(path, run_root)
    path_text = str(path)
    exact_case_match = any(case_id and case_id in path_text for case_id in selected_case_ids)
    selected_skill_match = skill_name in path_text
    weight = int(artifact_policy["base_weight"])
    modifiers = policy["weight_modifiers"]
    weight += int(modifiers.get(currentness, 0))
    if exact_case_match:
        weight += int(modifiers.get("exact_case_match", 0))
    if selected_skill_match:
        weight += int(modifiers.get("selected_skill_match", 0))
    if artifact_policy.get("contamination_risk") == "high":
        weight += int(modifiers.get("contamination_risk_high_penalty", 0))
    return (
        {
            "path": path_text,
            "exists": path.exists(),
            "artifact_kind": artifact_kind,
            "requested_role": requested_role,
            "resolved_role": resolved_role,
            "policy_admissibility": artifact_policy["admissibility"],
            "raw_or_derived": artifact_policy["raw_or_derived"],
            "currentness": currentness,
            "exact_case_match": exact_case_match,
            "selected_skill_match": selected_skill_match,
            "contamination_risk": artifact_policy["contamination_risk"],
            "relative_weight": weight,
        },
        warnings,
    )


def selection_flags(selection_class: str) -> dict[str, bool]:
    normalized = selection_class.lower().replace("_", "-")
    return {
        "manual_carry_forward": "carry-forward" in normalized,
        "disputed_carry_forward": "disputed" in normalized and "carry-forward" in normalized,
        "adjacent_addition": "adjacent" in normalized,
        "fresh_addition": "fresh" in normalized,
        "repeated_signal": "repeated" in normalized,
    }


def validate_contract_fields(document: dict[str, Any], contract_path: Path, key_name: str) -> None:
    contract = load_json(contract_path)
    missing = [key for key in contract[key_name] if key not in document]
    if missing:
        raise SystemExit(f"{document.get('format', 'document')} missing required keys: {', '.join(missing)}")


def build_pack_selection_assets(
    *,
    run_root: Path,
    skill_name: str,
    created: list[dict[str, Any]],
    args: argparse.Namespace,
    accepted_case_manifest_path: Path | None,
    accepted_case_set: str | None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    policy = load_json(pack_selection_policy_path())
    if policy.get("version") != PACK_SELECTION_POLICY_FORMAT:
        raise SystemExit(f"unsupported pack selection policy format: {policy.get('version')!r}")

    plan_source = infer_plan_source(args, accepted_case_manifest_path)
    pack_mode = infer_pack_mode(args, accepted_case_manifest_path)
    if pack_mode not in policy["allowed_pack_modes"]:
        raise SystemExit(f"unsupported --pack-mode: {pack_mode!r}")

    selection_specs = parse_case_selection_specs(args.case_selection)
    rejected_cases = parse_rejected_case_specs(args.rejected_case)
    selected_case_ids = {str(item["case_id"]) for item in created}

    source_specs: list[tuple[str, Path]] = []
    seen_source_specs: set[tuple[str, str]] = set()

    def add_source_spec(role: str, source_path: Path) -> None:
        key = (role, str(source_path))
        if key not in seen_source_specs:
            seen_source_specs.add(key)
            source_specs.append((role, source_path))

    if accepted_case_manifest_path is not None:
        add_source_spec("primary", accepted_case_manifest_path.resolve())
    elif args.case_file:
        for raw_path in args.case_file:
            add_source_spec("primary", Path(raw_path).expanduser().resolve())
    else:
        add_source_spec("supporting", template_root() / "case-template.md.tmpl")

    for raw_spec in args.selection_artifact:
        role, source_path = parse_selection_artifact_spec(raw_spec)
        add_source_spec(role, source_path)

    warnings: list[str] = []
    source_artifacts: list[dict[str, Any]] = []
    for requested_role, path in source_specs:
        artifact_record, artifact_warnings = build_source_artifact_record(
            path=path,
            requested_role=requested_role,
            policy=policy,
            run_root=run_root,
            selected_case_ids=selected_case_ids,
            skill_name=skill_name,
        )
        source_artifacts.append(artifact_record)
        warnings.extend(f"{path}: {warning}" for warning in artifact_warnings)

    candidate_case_ids = set(args.candidate_case_id) | selected_case_ids | set(rejected_cases)
    if not candidate_case_ids:
        candidate_case_ids = selected_case_ids
    if set(args.candidate_case_id):
        for case_id in args.candidate_case_id:
            require_valid_name(case_id, "candidate case id")

    selected_case_map = {str(item["case_id"]): item for item in created}
    selected_cases: list[dict[str, Any]] = []
    candidate_cases: list[dict[str, Any]] = []
    modifiers = policy["weight_modifiers"]

    default_confidence = "high" if accepted_case_manifest_path is not None else "medium"
    if not args.selection_artifact and not args.case_selection and not args.rejected_case and accepted_case_manifest_path is None:
        default_confidence = "low"
        warnings.append("selection trace has no explicit historical source artifacts beyond pack input sources")

    if candidate_case_ids == selected_case_ids:
        warnings.append("candidate case universe was not wider than the selected case set")

    for case_id in sorted(candidate_case_ids):
        selected = case_id in selected_case_map
        selection_entry = selection_specs.get(case_id, {})
        if selected:
            created_item = selected_case_map[case_id]
            selection_class = selection_entry.get("selection_class")
            if not selection_class:
                if accepted_case_manifest_path is not None:
                    selection_class = "accepted-case-set"
                elif created_item.get("case_source_type") == "source-case-file":
                    selection_class = "manual-source-case-file"
                else:
                    selection_class = "manual-template-case-id"
            selection_reason = selection_entry.get("selection_reason")
            if not selection_reason:
                if accepted_case_manifest_path is not None:
                    selection_reason = "selected from the accepted case-set registry for regeneration"
                elif created_item.get("case_source_type") == "source-case-file":
                    selection_reason = "selected from explicit source case-file input"
                else:
                    selection_reason = "selected from explicit case-id input"
            flags = selection_flags(selection_class)
            related_artifacts = [
                item
                for item in source_artifacts
                if item["resolved_role"] != "excluded"
                and (item["exact_case_match"] or item["selected_skill_match"] or item["resolved_role"] == "primary")
            ]
            selection_weight = max((int(item["relative_weight"]) for item in related_artifacts), default=40)
            if flags["manual_carry_forward"]:
                selection_weight += int(modifiers.get("carry_forward", 0))
            if flags["disputed_carry_forward"]:
                selection_weight += int(modifiers.get("disputed", 0))
            if flags["adjacent_addition"]:
                selection_weight += int(modifiers.get("adjacent", 0))
            if flags["fresh_addition"]:
                selection_weight += int(modifiers.get("fresh", 0))
            if flags["repeated_signal"]:
                selection_weight += int(modifiers.get("repeated_signal", 0))
            selected_case_record = {
                "case_id": case_id,
                "case_path": created_item["case_path"],
                "review_path": created_item["review_path"],
                "case_source_type": created_item["case_source_type"],
                "case_source_ref": created_item["case_source_ref"],
                "selection_class": selection_class,
                "selection_reason": selection_reason,
                "selection_weight": selection_weight,
                "manual_carry_forward": flags["manual_carry_forward"],
                "disputed_carry_forward": flags["disputed_carry_forward"],
                "adjacent_addition": flags["adjacent_addition"],
                "fresh_addition": flags["fresh_addition"],
                "repeated_signal": flags["repeated_signal"],
                "source_artifact_count": len(related_artifacts),
                "source_artifact_refs": [item["path"] for item in related_artifacts],
            }
            selected_cases.append(selected_case_record)
            candidate_cases.append(
                {
                    "case_id": case_id,
                    "selected": True,
                    "case_path": created_item["case_path"],
                    "selection_class": selection_class,
                    "selection_reason": selection_reason,
                    "selection_weight": selection_weight,
                    "manual_carry_forward": flags["manual_carry_forward"],
                    "disputed_carry_forward": flags["disputed_carry_forward"],
                    "adjacent_addition": flags["adjacent_addition"],
                    "fresh_addition": flags["fresh_addition"],
                    "repeated_signal": flags["repeated_signal"],
                }
            )
        else:
            candidate_cases.append(
                {
                    "case_id": case_id,
                    "selected": False,
                    "case_path": None,
                    "selection_class": "rejected",
                    "selection_reason": rejected_cases.get(case_id, "not selected for this pack"),
                    "selection_weight": 0,
                    "manual_carry_forward": False,
                    "disputed_carry_forward": False,
                    "adjacent_addition": False,
                    "fresh_addition": False,
                    "repeated_signal": False,
                }
            )

    trace_path = run_root / "summaries" / "pack-selection-trace.json"
    manifest_path = run_root / "summaries" / "pack-selection-manifest.json"
    trace = {
        "format": PACK_SELECTION_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "run_root": str(run_root),
        "skill_name": skill_name,
        "pack_mode": pack_mode,
        "plan_source": plan_source,
        "selection_confidence": default_confidence,
        "selection_policy_path": str(pack_selection_policy_path()),
        "accepted_case_set": accepted_case_set,
        "accepted_case_manifest": str(accepted_case_manifest_path) if accepted_case_manifest_path else None,
        "candidate_cases": candidate_cases,
        "source_artifacts": source_artifacts,
        "warnings": warnings,
        "manual_inputs": {
            "case_ids": list(args.case_id),
            "case_files": [str(Path(item).expanduser().resolve()) for item in args.case_file],
            "candidate_case_ids": sorted(candidate_case_ids),
            "rejected_cases": rejected_cases,
            "case_selection": selection_specs,
            "selection_artifacts": [spec for spec in args.selection_artifact],
        },
    }
    manifest = {
        "format": PACK_SELECTION_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "run_root": str(run_root),
        "skill_name": skill_name,
        "pack_mode": pack_mode,
        "plan_source": plan_source,
        "selection_confidence": default_confidence,
        "selection_policy_path": str(pack_selection_policy_path()),
        "selection_trace_path": str(trace_path),
        "accepted_case_set": accepted_case_set,
        "accepted_case_manifest": str(accepted_case_manifest_path) if accepted_case_manifest_path else None,
        "candidate_case_count": len(candidate_cases),
        "selected_case_count": len(selected_cases),
        "rejected_case_count": sum(1 for item in candidate_cases if not item["selected"]),
        "selected_cases": selected_cases,
        "primary_source_artifact_count": sum(1 for item in source_artifacts if item["resolved_role"] == "primary"),
        "supporting_source_artifact_count": sum(1 for item in source_artifacts if item["resolved_role"] == "supporting"),
        "excluded_source_artifact_count": sum(1 for item in source_artifacts if item["resolved_role"] == "excluded"),
        "warnings": warnings,
    }
    validate_contract_fields(trace, pack_selection_trace_contract_path(), "required_top_level")
    for item in trace["candidate_cases"]:
        missing = [
            key
            for key in load_json(pack_selection_trace_contract_path())["required_candidate_case_keys"]
            if key not in item
        ]
        if missing:
            raise SystemExit(f"pack selection trace candidate case missing keys: {', '.join(missing)}")
    for item in trace["source_artifacts"]:
        missing = [
            key
            for key in load_json(pack_selection_trace_contract_path())["required_source_artifact_keys"]
            if key not in item
        ]
        if missing:
            raise SystemExit(f"pack selection trace source artifact missing keys: {', '.join(missing)}")
    validate_contract_fields(manifest, pack_selection_manifest_contract_path(), "required_top_level")
    for item in manifest["selected_cases"]:
        missing = [
            key
            for key in load_json(pack_selection_manifest_contract_path())["required_selected_case_keys"]
            if key not in item
        ]
        if missing:
            raise SystemExit(f"pack selection manifest selected case missing keys: {', '.join(missing)}")
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return trace, manifest, trace_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--skill-name", required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--case-file", action="append", default=[])
    parser.add_argument("--accepted-case-set")
    parser.add_argument("--baseline-profile")
    parser.add_argument("--trial-profile")
    parser.add_argument("--declared-capability", action="append", default=[])
    parser.add_argument("--inventory-manifest")
    parser.add_argument("--pack-mode")
    parser.add_argument("--selection-artifact", action="append", default=[])
    parser.add_argument("--candidate-case-id", action="append", default=[])
    parser.add_argument("--rejected-case", action="append", default=[])
    parser.add_argument("--case-selection", action="append", default=[])
    args = parser.parse_args()

    require_valid_name(args.skill_name, "skill name")
    run_root = Path(args.run_root)
    baseline_profile = args.baseline_profile or normalize_profile_name(args.skill_name, "baseline")
    trial_profile = args.trial_profile or normalize_profile_name(args.skill_name, "trial")
    accepted_case_manifest_path: Path | None = None
    accepted_case_manifest: dict[str, object] | None = None
    if args.accepted_case_set:
        accepted_case_manifest_path, accepted_case_manifest = load_accepted_case_set(args.accepted_case_set)
    accepted_case_capabilities = None
    if accepted_case_manifest and isinstance(accepted_case_manifest.get("declared_capabilities"), list):
        accepted_case_capabilities = accepted_case_manifest.get("declared_capabilities")
    declared_capabilities = args.declared_capability or accepted_case_capabilities or ["replace-with-primary-capability"]
    for rel in ["cases", "profiles", "raw", "results", "summaries"]:
        (run_root / rel).mkdir(parents=True, exist_ok=True)

    if not args.case_id and not args.case_file and accepted_case_manifest is None:
        raise SystemExit("at least one --case-id or --case-file is required unless --accepted-case-set is provided")

    case_specs: list[dict[str, str]]
    if accepted_case_manifest is not None and accepted_case_manifest_path is not None:
        case_specs = resolve_accepted_case_specs(
            accepted_case_manifest_path,
            accepted_case_manifest,
            args.case_id,
            args.skill_name,
            baseline_profile,
            trial_profile,
            declared_capabilities,
        )
    elif args.case_file:
        case_specs = resolve_source_case_specs(
            args.case_file,
            args.skill_name,
            baseline_profile,
            trial_profile,
            declared_capabilities,
        )
    else:
        case_specs = []
        for case_id in args.case_id:
            require_valid_name(case_id, "case id")
            case_specs.append(
                {
                    "case_id": case_id,
                    "case_text": "",
                    "case_source_type": "template",
                    "case_source_ref": str(template_root() / "case-template.md.tmpl"),
                }
            )

    created = []
    for case_spec in case_specs:
        created.append(
            create_case_and_review(
                run_root,
                args.skill_name,
                case_spec["case_id"],
                baseline_profile,
                trial_profile,
                declared_capabilities,
                case_text_override=case_spec["case_text"] or None,
                case_source_type=case_spec["case_source_type"],
                case_source_ref=case_spec["case_source_ref"],
            )
        )

    selection_trace, selection_manifest, selection_trace_path, selection_manifest_path = build_pack_selection_assets(
        run_root=run_root,
        skill_name=args.skill_name,
        created=created,
        args=args,
        accepted_case_manifest_path=accepted_case_manifest_path,
        accepted_case_set=args.accepted_case_set,
    )

    method_lines = [
        "# Review Pack Method",
        "",
        "- baseline profile first",
        "- with-skill profile second",
        "- one-skill-under-test isolation",
        "- no readiness verdict without completed reviews",
        "- invalidated evidence stays invalid until the harness fault is replaced with a clean rerun",
        "- keep raw outputs and matrix manifests alongside pair reviews so denial reasons stay machine-readable",
    ]
    if args.accepted_case_set:
        method_lines.append(f"- concrete case prompts sourced from accepted case set `{args.accepted_case_set}`")
    method_text = "\n".join(method_lines) + "\n"
    write_text(run_root / "METHOD.md", method_text)

    manifest = {
        "format": "openclaw-review-pack-v1",
        "run_root": str(run_root),
        "skill_name": args.skill_name,
        "pack_mode": selection_manifest["pack_mode"],
        "plan_source": selection_manifest["plan_source"],
        "selection_confidence": selection_manifest["selection_confidence"],
        "inventory_manifest": args.inventory_manifest,
        "accepted_case_set": args.accepted_case_set,
        "accepted_case_manifest": str(accepted_case_manifest_path) if accepted_case_manifest_path else None,
        "pack_selection_policy": str(pack_selection_policy_path()),
        "pack_selection_manifest": str(selection_manifest_path),
        "pack_selection_trace": str(selection_trace_path),
        "baseline_profile": baseline_profile,
        "trial_profile": trial_profile,
        "case_count": len(created),
        "cases": created,
        "required_raw_files": RAW_FILES,
        "readiness_inputs": {
            "results_dir": str(run_root / "results"),
            "review_pack_manifest": str(run_root / "summaries" / "review-pack-manifest.json"),
            "matrix_manifest": str(run_root / "summaries" / "matrix-run-manifest.json"),
            "trial_plan": str(run_root / "summaries" / "trial-plan.json"),
        },
        "invalidation_policy": [
            "non-zero harness returncode invalidates the affected case",
            "missing assistant text invalidates the affected case",
            "JSON parse errors in run-summary invalidates the affected case",
            "session ids longer than the configured limit invalidate the affected case",
        ],
    }
    (run_root / "summaries" / "review-pack-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    trial_plan = {
        "format": "openclaw-skill-trial-plan-v1",
        "run_root": str(run_root),
        "pack_mode": selection_manifest["pack_mode"],
        "plan_source": selection_manifest["plan_source"],
        "selection_confidence": selection_manifest["selection_confidence"],
        "inventory_manifest": args.inventory_manifest,
        "accepted_case_set": args.accepted_case_set,
        "accepted_case_manifest": str(accepted_case_manifest_path) if accepted_case_manifest_path else None,
        "pack_selection_policy": str(pack_selection_policy_path()),
        "pack_selection_manifest": str(selection_manifest_path),
        "pack_selection_trace": str(selection_trace_path),
        "comparison_modes": ["baseline", "with-skill"],
        "profiles": {
            "baseline": {"profile_name": baseline_profile, "role": "baseline"},
            "trial": {"profile_name": trial_profile, "role": "trial"},
        },
        "cases": [
            {
                "case_id": item["case_id"],
                "case_path": item["case_path"],
                "target_skill": args.skill_name,
                "baseline_profile": baseline_profile,
                "trial_profile": trial_profile,
                "expected_trigger": "yes",
                "declared_capabilities": declared_capabilities,
                "review_path": item["review_path"],
                "case_source_type": item["case_source_type"],
                "case_source_ref": item["case_source_ref"],
                "selection_class": next(
                    (
                        case_item["selection_class"]
                        for case_item in selection_manifest["selected_cases"]
                        if case_item["case_id"] == item["case_id"]
                    ),
                    "manual-template-case-id",
                ),
                "selection_reason": next(
                    (
                        case_item["selection_reason"]
                        for case_item in selection_manifest["selected_cases"]
                        if case_item["case_id"] == item["case_id"]
                    ),
                    "selected for this pack",
                ),
                "selection_weight": next(
                    (
                        case_item["selection_weight"]
                        for case_item in selection_manifest["selected_cases"]
                        if case_item["case_id"] == item["case_id"]
                    ),
                    0,
                ),
            }
            for item in created
        ],
        "runner_entrypoint": "/home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1/scripts/run_skill_trial_matrix.py",
        "legacy_runner_entrypoint": "/home/agent/agents/core/artifacts/skills/openclaw-skill-eval-harness-v1/scripts/run_managed_skills_matrix.py",
    }
    (run_root / "summaries" / "trial-plan.json").write_text(
        json.dumps(trial_plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
