#!/usr/bin/env python3
"""Apply deterministic readiness gates to completed review files."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

CORE_ROOT = pathlib.Path(__file__).resolve().parents[4]
RUNTIME_ROOT = CORE_ROOT / "runtime"
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from context_router_policy_projector_v1.runtime import build_context_packet


KEY_RE = re.compile(r"^[a-z_]+$")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def package_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def gates_path() -> pathlib.Path:
    return package_root() / "definitions" / "readiness-gates.json"


def parse_review(path: pathlib.Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if current_key is not None and current_key not in fields:
            fields[current_key] = "\n".join(current_lines).strip()
        current_key = None
        current_lines = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("<!--"):
            continue
        if ":" in line and not line[:1].isspace():
            key, value = line.split(":", 1)
            key = key.strip()
            if KEY_RE.match(key):
                flush()
                current_key = key
                current_lines = [value.strip()]
                continue
        if current_key is not None:
            current_lines.append(line.strip())
    flush()
    return fields


def normalized_evidence_status(fields: dict[str, str]) -> str:
    value = fields.get("evidence_status", "").strip()
    if value:
        return value
    return "valid"


def normalized_delta_strength(fields: dict[str, str]) -> str:
    value = fields.get("delta_strength", "").strip()
    if value:
        return value
    outcome = fields.get("outcome", "").strip()
    if outcome == "pass":
        return "meaningful"
    if outcome == "partial":
        return "weak"
    return "none"


def is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or bool(PLACEHOLDER_RE.search(stripped))


def is_completed_review(fields: dict[str, str], required_fields: list[str]) -> bool:
    review_status = fields.get("review_status", "").strip()
    if review_status and review_status != "completed":
        return False
    return all(not is_placeholder(fields.get(field, "")) for field in required_fields)


def check_common_constraints(fields: dict[str, str], gate: dict) -> bool:
    if normalized_evidence_status(fields) != gate["evidence_status"]:
        return False
    if fields.get("baseline_observed_trigger") != gate["baseline_observed_trigger"]:
        return False
    if fields.get("with_skill_observed_trigger") != gate["with_skill_observed_trigger"]:
        return False
    if gate.get("forbid_overtrigger") and fields.get("overtrigger") == "yes":
        return False
    if gate.get("forbid_undertrigger") and fields.get("undertrigger") == "yes":
        return False
    if fields.get("outcome") not in gate["allowed_outcomes"]:
        return False
    return True


def notes_text(fields: dict[str, str], keys: list[str]) -> str:
    return "\n".join(fields.get(key, "") for key in keys).lower()


def review_indicates_trial_tool_usage(fields: dict[str, str]) -> bool:
    text = notes_text(fields, ["with_skill_notes", "output_notes", "capability_notes"])
    markers = (
        "contains real mcp tool calls",
        "used all four dry-run mcp tools",
        "used the intended mcp surface first",
        "used the dry-run mcp surface",
        "called `runtime_governance_status_snapshot`",
        "used `runtime_governance_status_snapshot`",
    )
    return any(marker in text for marker in markers)


def review_indicates_baseline_tool_absence(fields: dict[str, str]) -> bool:
    text = notes_text(fields, ["baseline_notes", "output_notes"])
    markers = (
        "contains none",
        "no runtime mcp tool calls",
        "had no dry-run mcp surface",
        "had no runtime mcp surface",
    )
    return any(marker in text for marker in markers)


def weak_residue_documented(fields: dict[str, str]) -> bool:
    if normalized_delta_strength(fields) != "weak":
        return True
    text = notes_text(fields, ["delta_notes", "gating_notes", "capability_notes"])
    markers = (
        "parity-like",
        "parity like",
        "boundary case",
        "weak rather than meaningful",
    )
    return any(marker in text for marker in markers)


def qualifies_for_broader_eval_ready(
    skill_name: str,
    reviews: list[dict[str, str]],
    gate: dict,
    denial_reasons: list[str],
) -> bool:
    if skill_name not in gate.get("applies_to_skills", []):
        return False
    completed_reviews = [fields for fields in reviews if fields]
    if len(completed_reviews) < gate["min_reviews"]:
        return False
    if sorted(set(denial_reasons)) != sorted(gate["required_only_denial_reasons"]):
        return False
    if sum(1 for fields in completed_reviews if normalized_delta_strength(fields) == "meaningful") < gate["min_meaningful_delta_count"]:
        return False
    if sum(1 for fields in completed_reviews if normalized_delta_strength(fields) == "weak") > gate["max_weak_delta_count"]:
        return False
    for fields in completed_reviews:
        if normalized_evidence_status(fields) != gate["evidence_status"]:
            return False
        if fields.get("with_skill_observed_trigger") != gate["with_skill_observed_trigger"]:
            return False
        if gate.get("forbid_overtrigger") and fields.get("overtrigger") == "yes":
            return False
        if gate.get("forbid_undertrigger") and fields.get("undertrigger") == "yes":
            return False
        if fields.get("outcome") not in gate["allowed_outcomes"]:
            return False
        if gate.get("require_trial_tool_usage_note") and not review_indicates_trial_tool_usage(fields):
            return False
        if gate.get("require_baseline_tool_absence_note") and not review_indicates_baseline_tool_absence(fields):
            return False
        if gate.get("require_documented_weak_residue") and not weak_residue_documented(fields):
            return False
    return True


def analyze_matrix_manifest(path: pathlib.Path, gates: dict) -> dict[str, dict[str, object]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required_modes = gates["evidence_checks"]["required_run_modes"]
    max_session_id_length = gates["evidence_checks"]["session_id_max_length"]
    per_case: dict[str, dict[str, object]] = {}

    for item in manifest.get("results", []):
        case_id = item.get("case_id", "")
        runs = {run.get("mode"): run for run in item.get("runs", [])}
        reasons: list[str] = []
        for mode in required_modes:
            run = runs.get(mode)
            if run is None:
                reasons.append(f"missing_{mode}_run")
                continue
            summary = run.get("summary") or {}
            if run.get("returncode") != 0 or summary.get("returncode") != 0:
                reasons.append(f"{mode}_returncode_nonzero")
            if summary.get("parse_error") not in (None, ""):
                reasons.append(f"{mode}_parse_error")
            if summary.get("parsed_json") is not True:
                reasons.append(f"{mode}_parsed_json_false")
            if summary.get("assistant_text_present") is not True:
                reasons.append(f"{mode}_assistant_text_missing")
            session_id = summary.get("session_id", "")
            if not session_id:
                reasons.append(f"{mode}_session_id_missing")
            elif len(session_id) > max_session_id_length:
                reasons.append(f"{mode}_session_id_too_long")
        context_modes = {
            mode: (runs.get(mode, {}).get("summary") or {}).get("context_mode")
            for mode in required_modes
            if runs.get(mode) is not None
        }
        missing_context_modes = [
            mode
            for mode in required_modes
            if runs.get(mode) is not None and not ((runs.get(mode, {}).get("summary") or {}).get("context_decision_trace"))
        ]
        projection_modes = [
            mode
            for mode in required_modes
            if (runs.get(mode, {}).get("summary") or {}).get("projection_applied") is True
        ]
        per_case[case_id] = {
            "invalidated": bool(reasons),
            "reasons": reasons,
            "context_modes": context_modes,
            "missing_context_modes": missing_context_modes,
            "projection_applied_modes": projection_modes,
        }
    return per_case


def load_expected_cases(results_dir: pathlib.Path, run_root: pathlib.Path | None) -> tuple[set[str], list[str]]:
    warnings: list[str] = []
    expected_cases = {path.stem.removesuffix("-review") for path in results_dir.glob("*-review.md")}
    if run_root is None:
        return expected_cases, warnings

    trial_plan_manifest = run_root / "summaries" / "trial-plan.json"
    review_pack_manifest = run_root / "summaries" / "review-pack-manifest.json"
    matrix_manifest = run_root / "summaries" / "matrix-run-manifest.json"
    if trial_plan_manifest.exists():
        data = json.loads(trial_plan_manifest.read_text(encoding="utf-8"))
        expected_cases = {item["case_id"] for item in data.get("cases", [])}
    elif review_pack_manifest.exists():
        data = json.loads(review_pack_manifest.read_text(encoding="utf-8"))
        expected_cases = {item["case_id"] for item in data.get("cases", [])}
    elif matrix_manifest.exists():
        data = json.loads(matrix_manifest.read_text(encoding="utf-8"))
        expected_cases = {item.get("case_id", "") for item in data.get("results", []) if item.get("case_id")}
    else:
        warnings.append("run-root has no trial-plan.json, review-pack-manifest.json, or matrix-run-manifest.json")
    return expected_cases, warnings


def evaluate_group(
    skill_name: str,
    reviews: list[dict[str, str]],
    gates: dict,
    expected_case_ids: set[str],
    manifest_evidence: dict[str, dict[str, object]],
) -> dict[str, object]:
    usable_now = gates["verdicts"]["usable_now"]
    usable_with_caveats = gates["verdicts"]["usable_with_caveats"]
    ready_for_broader_eval = gates["verdicts"].get("ready_for_broader_eval")
    required_fields = gates["evidence_checks"]["required_review_fields"]

    completed_reviews = [fields for fields in reviews if is_completed_review(fields, required_fields)]
    completed_case_ids = {fields.get("case_id", "") for fields in completed_reviews if fields.get("case_id")}
    pending_case_ids = sorted(case_id for case_id in expected_case_ids if case_id and case_id not in completed_case_ids)
    invalidated_case_ids = sorted(
        case_id
        for case_id in completed_case_ids
        if normalized_evidence_status(next(fields for fields in completed_reviews if fields.get("case_id") == case_id)) == "invalidated"
        or manifest_evidence.get(case_id, {}).get("invalidated")
    )

    reviewed = len(completed_reviews)
    denial_reasons: list[str] = []
    if reviewed < usable_with_caveats["min_reviews"]:
        denial_reasons.append("insufficient_completed_reviews")
    if pending_case_ids:
        denial_reasons.append("pending_reviews_present")
    if invalidated_case_ids:
        denial_reasons.append("invalidated_evidence_present")

    if denial_reasons:
        verdict = "not yet ready"
    else:
        usable_now_ok = all(check_common_constraints(fields, usable_now) for fields in completed_reviews)
        usable_now_ok = usable_now_ok and any(normalized_delta_strength(fields) == "meaningful" for fields in completed_reviews)

        usable_with_caveats_ok = all(check_common_constraints(fields, usable_with_caveats) for fields in completed_reviews)
        if usable_now_ok:
            verdict = "usable now"
        elif usable_with_caveats_ok:
            verdict = "usable with caveats"
        else:
            verdict = "not yet ready"
            if any(fields.get("baseline_observed_trigger") != usable_with_caveats["baseline_observed_trigger"] for fields in completed_reviews):
                denial_reasons.append("baseline_trigger_mismatch")
            if any(fields.get("with_skill_observed_trigger") != usable_with_caveats["with_skill_observed_trigger"] for fields in completed_reviews):
                denial_reasons.append("with_skill_trigger_mismatch")
            if any(fields.get("outcome") == "fail" for fields in completed_reviews):
                denial_reasons.append("fail_outcome_present")
            if any(fields.get("overtrigger") == "yes" for fields in completed_reviews):
                denial_reasons.append("overtrigger_present")
            if any(fields.get("undertrigger") == "yes" for fields in completed_reviews):
                denial_reasons.append("undertrigger_present")
    if verdict != "usable now" and not any(normalized_delta_strength(fields) == "meaningful" for fields in completed_reviews):
        denial_reasons.append("meaningful_delta_missing")

    warning_signals: list[str] = []
    if (
        verdict == "not yet ready"
        and ready_for_broader_eval
        and qualifies_for_broader_eval_ready(skill_name, completed_reviews, ready_for_broader_eval, denial_reasons)
    ):
        verdict = "ready for broader eval"
        warning_signals = ["baseline_trigger_mismatch"]
        if any(normalized_delta_strength(fields) == "weak" for fields in completed_reviews):
            warning_signals.append("parity_like_residue_present")
        denial_reasons = []

    return {
        "expected_case_count": len(expected_case_ids),
        "expected_case_ids": sorted(expected_case_ids),
        "reviewed": reviewed,
        "pending_case_ids": pending_case_ids,
        "invalidated_case_ids": invalidated_case_ids,
        "invalidated_reasons": {
            case_id: manifest_evidence.get(case_id, {}).get("reasons", [])
            for case_id in invalidated_case_ids
        },
        "completed_case_ids": sorted(completed_case_ids),
        "pass": sum(1 for fields in completed_reviews if fields.get("outcome") == "pass"),
        "partial": sum(1 for fields in completed_reviews if fields.get("outcome") == "partial"),
        "fail": sum(1 for fields in completed_reviews if fields.get("outcome") == "fail"),
        "meaningful_delta_count": sum(1 for fields in completed_reviews if normalized_delta_strength(fields) == "meaningful"),
        "weak_delta_count": sum(1 for fields in completed_reviews if normalized_delta_strength(fields) == "weak"),
        "verdict": verdict,
        "denial_reasons": sorted(set(denial_reasons)),
        "warning_signals": warning_signals,
    }


def build_readiness_task_request(run_root: pathlib.Path, expected_case_ids: set[str]) -> str:
    case_list = ", ".join(sorted(case_id for case_id in expected_case_ids if case_id))
    lines = [
        f"Evaluate readiness for exactly this current run root `{run_root}`.",
        "Use the current run as primary truth for post-run evaluation and keep older derived artifacts supporting-only.",
        "Use the routed matrix manifest, routed case run summaries, review files, and canonical policy files as the evaluation contour.",
    ]
    if case_list:
        lines.append(f"Expected cases: {case_list}.")
    return "\n".join(lines)


def summarize_context_packet(packet: dict, request: str) -> dict[str, object]:
    return {
        "request": request,
        "selected_mode": packet["selected_mode"],
        "confidence": packet["confidence"],
        "warning_signals": packet["warning_signals"],
        "decision_trace": str(packet["decision_trace_path"]),
        "working_set": str(packet["working_set_path"]),
        "projection_summary": str(packet["projection_summary_path"]) if packet["projection_summary_path"] else None,
    }


def collect_matrix_routed_context(run_root: pathlib.Path) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    matrix_manifest_path = run_root / "summaries" / "matrix-run-manifest.json"
    if not matrix_manifest_path.exists():
        return {
            "matrix_manifest_path": str(matrix_manifest_path),
            "matrix_context_present": False,
            "case_run_context_coverage": {
                "total_runs": 0,
                "runs_with_context": 0,
                "modes": {},
                "projection_applied_runs": 0,
            },
            "legacy_compatibility": True,
        }, warnings

    manifest = json.loads(matrix_manifest_path.read_text(encoding="utf-8"))
    top_level_context = manifest.get("context_router")
    global_managed = manifest.get("global_managed")
    total_runs = 0
    runs_with_context = 0
    projection_applied_runs = 0
    mode_counts: dict[str, int] = defaultdict(int)
    missing_context_runs: list[str] = []

    for item in manifest.get("results", []):
        case_id = item.get("case_id", "")
        for run in item.get("runs", []):
            total_runs += 1
            summary = run.get("summary") or {}
            label = f"{case_id}::{run.get('mode')}"
            context_mode = summary.get("context_mode")
            if context_mode:
                runs_with_context += 1
                mode_counts[context_mode] += 1
            else:
                missing_context_runs.append(label)
            if summary.get("projection_applied") is True:
                projection_applied_runs += 1

    if not top_level_context:
        warnings.append("matrix manifest has no top-level context_router block; using readiness-side compatibility routing")
    if missing_context_runs:
        warnings.append(f"matrix manifest is missing per-run routed context for {len(missing_context_runs)} run(s)")

    return {
        "matrix_manifest_path": str(matrix_manifest_path),
        "matrix_context_present": bool(top_level_context),
        "matrix_context": top_level_context,
        "global_managed": global_managed,
        "case_run_context_coverage": {
            "total_runs": total_runs,
            "runs_with_context": runs_with_context,
            "modes": dict(sorted(mode_counts.items())),
            "projection_applied_runs": projection_applied_runs,
            "missing_context_runs": missing_context_runs,
        },
        "legacy_compatibility": not bool(top_level_context),
    }, warnings


def render_readiness_report(result: dict[str, object]) -> str:
    context_router = result.get("context_router") or {}
    readiness_context = context_router.get("readiness") or {}
    matrix_context = context_router.get("matrix_execution") or {}
    global_managed = matrix_context.get("global_managed") or {}
    lines = [
        "# Routed Readiness Evaluation",
        "",
        f"- Run root: `{result.get('run_root')}`",
        f"- Results dir: `{result.get('results_dir')}`",
        f"- Selected mode: `{readiness_context.get('selected_mode')}`",
        f"- Confidence: `{readiness_context.get('confidence')}`",
        f"- Warnings: {', '.join(result.get('warnings') or []) or 'none'}",
        "",
        "## Routed context",
        f"- Readiness decision trace: `{readiness_context.get('decision_trace')}`",
        f"- Readiness working set: `{readiness_context.get('working_set')}`",
        f"- Matrix context present: `{matrix_context.get('matrix_context_present')}`",
        f"- Global managed launch trace: `{global_managed.get('launch_trace')}`",
        f"- Global managed memory fabric: `{global_managed.get('memory_fabric')}`",
        f"- Global managed memory selection: `{global_managed.get('memory_selection')}`",
        f"- Global managed default enforced: `{global_managed.get('default_path_enforced')}`",
        f"- Global managed invocation mode: `{global_managed.get('invocation_mode')}`",
    ]
    coverage = matrix_context.get("case_run_context_coverage") or {}
    lines.extend(
        [
            f"- Matrix total runs: `{coverage.get('total_runs', 0)}`",
            f"- Matrix runs with routed context: `{coverage.get('runs_with_context', 0)}`",
            f"- Matrix routed modes: `{json.dumps(coverage.get('modes', {}), sort_keys=True)}`",
            f"- Projection-applied runs: `{coverage.get('projection_applied_runs', 0)}`",
            "",
            "## Skill verdicts",
        ]
    )
    for skill_name, payload in sorted((result.get("skills") or {}).items()):
        lines.append(
            f"- `{skill_name}` -> verdict `{payload.get('verdict')}`, pass `{payload.get('pass')}`, partial `{payload.get('partial')}`, fail `{payload.get('fail')}`, denial reasons `{json.dumps(payload.get('denial_reasons', []), sort_keys=True)}`"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir")
    parser.add_argument("--run-root")
    parser.add_argument("--skill-name")
    parser.add_argument("--readiness-mode-override")
    args = parser.parse_args()

    gates = json.loads(gates_path().read_text(encoding="utf-8"))
    if not args.results_dir and not args.run_root:
        raise SystemExit("either --results-dir or --run-root is required")
    run_root = pathlib.Path(args.run_root) if args.run_root else None
    results_dir = pathlib.Path(args.results_dir) if args.results_dir else run_root / "results"
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    manifest_evidence: dict[str, dict[str, object]] = {}
    warnings: list[str] = []

    if run_root is not None:
        matrix_manifest = run_root / "summaries" / "matrix-run-manifest.json"
        if matrix_manifest.exists():
            manifest_evidence = analyze_matrix_manifest(matrix_manifest, gates)
        else:
            warnings.append(f"matrix manifest missing: {matrix_manifest}")
    expected_case_ids, expected_case_warnings = load_expected_cases(results_dir, run_root)
    warnings.extend(expected_case_warnings)

    readiness_context_summary = None
    matrix_routed_context = None
    if run_root is not None:
        readiness_request = build_readiness_task_request(run_root, expected_case_ids)
        readiness_packet = build_context_packet(
            task_request=readiness_request,
            output_dir=run_root / "summaries" / "context-router" / "readiness-evaluation",
            target_paths=[run_root],
            caller_surface="evaluate_readiness",
            mode_override=args.readiness_mode_override,
            create_projection=False,
        )
        readiness_context_summary = summarize_context_packet(readiness_packet, readiness_request)
        matrix_routed_context, routed_context_warnings = collect_matrix_routed_context(run_root)
        warnings.extend(routed_context_warnings)

    for path in sorted(results_dir.glob("*.md")):
        fields = parse_review(path)
        skill_name = fields.get("target_skill", "")
        if not skill_name:
            continue
        if args.skill_name and skill_name != args.skill_name:
            continue
        grouped[skill_name].append(fields)

    output = {
        skill_name: evaluate_group(
            skill_name,
            reviews,
            gates,
            {fields.get("case_id", "") for fields in reviews if fields.get("case_id")} or expected_case_ids,
            manifest_evidence,
        )
        for skill_name, reviews in sorted(grouped.items())
    }
    result = {
        "results_dir": str(results_dir),
        "run_root": str(run_root) if run_root else None,
        "warnings": warnings,
        "context_router": {
            "readiness": readiness_context_summary,
            "matrix_execution": matrix_routed_context,
        } if run_root is not None else None,
        "skills": output,
    }
    if run_root is not None:
        out_dir = run_root / "summaries" / "context-router" / "readiness-evaluation"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "readiness-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out_dir / "readiness-report.md").write_text(render_readiness_report(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
