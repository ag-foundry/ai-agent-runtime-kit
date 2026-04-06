#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLACEHOLDER_RE = re.compile(r"^<[^>]+>$")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def read_key_value_markdown(path: Path) -> tuple[dict[str, str], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    fields: dict[str, str] = {}
    body_lines: list[str] = []
    in_body = False
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\n")
        if not in_body and index == 0 and line.startswith("<!--"):
            continue
        if not in_body and (line == "Prompt:" or line.startswith("Prompt:")):
            in_body = True
            body_lines.append(line)
            continue
        if not in_body and line.startswith("# "):
            in_body = True
            body_lines.append(line)
            continue
        if not in_body and not line.strip():
            in_body = True
            continue
        if not in_body and re.match(r"^[A-Za-z0-9_./-]+:\s", line):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.lstrip()
            continue
        if not in_body and re.match(r"^[A-Za-z0-9_./-]+:$", line):
            fields[line[:-1].strip()] = ""
            continue
        in_body = True
        body_lines.append(line)
    return fields, "\n".join(body_lines).strip()


def parse_declared_capabilities(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def has_placeholder(payload: dict[str, Any]) -> bool:
    for value in payload.values():
        if isinstance(value, str) and PLACEHOLDER_RE.search(value):
            return True
    return False


def normalize_bool_flag(raw: str | None) -> str:
    if raw is None:
        return "unknown"
    value = raw.strip().lower()
    if value in {"yes", "no", "unknown"}:
        return value
    return raw.strip()


def extract_date(value: str) -> str | None:
    match = DATE_RE.search(value)
    return match.group(1) if match else None


def parse_token_usage(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {"raw": raw}
    text = raw.strip()
    if text.isdigit():
        return {"raw": raw, "total": int(text)}
    data: dict[str, Any] = {"raw": raw}
    for part in text.split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        try:
            data[key] = int(value)
        except ValueError:
            data[key] = value
    return data


def derive_surface_family(target_skill: str, source_meta: dict[str, Any]) -> str:
    if source_meta.get("surface_family"):
        return source_meta["surface_family"]
    if target_skill == "promotion-bundle-admission-guard":
        return "bundle-state"
    if target_skill in {"ledger-evidence-audit", "promotion-readiness-auditor"}:
        return "prompt-contained-contract"
    if target_skill.startswith("runtime-governance-"):
        return "runtime-governance-mcp"
    if target_skill == "server-vault-write":
        return "controlled-write-delta"
    return "unclassified"


def blocker_tags_from_notes(entry: dict[str, Any]) -> list[str]:
    text_parts = [
        entry.get("gating_notes", ""),
        entry.get("harness_faults", ""),
        entry.get("delta_notes", ""),
        entry.get("baseline_notes", ""),
        entry.get("with_skill_notes", ""),
        entry.get("evidence_reason", ""),
    ]
    combined = " ".join(text_parts).lower().replace("`", "")
    tags: list[str] = []
    checks = [
        ("baseline_trigger_mismatch", ["baseline_trigger_mismatch"]),
        ("meaningful_delta_missing", ["meaningful_delta_missing"]),
        ("undertrigger", ["undertrigger", "under trigger"]),
        ("overtrigger", ["overtrigger", "over trigger"]),
        ("transport_caveat", ["timeout", "meta.aborted=true", "transport caveat", "transport/runtime ceiling"]),
        ("malformed_output", ["malformed"]),
        ("tool_surface_not_used", ["no mcp tool hits", "did not reliably use the exposed mcp tools", "failed the intended operational path"]),
        ("bootstrap_overlap", ["workspace bootstrap", "bootstrap layer already teaches", "baseline already"]),
        ("summary_only_decoy", ["summary-only", "supporting evidence", "supporting note"]),
        ("authoritative_proof_missing", ["authoritative proof missing"])
    ]
    for tag, needles in checks:
        if any(needle in combined for needle in needles):
            if tag in {"baseline_trigger_mismatch", "meaningful_delta_missing"}:
                if f"{tag} blocker is resolved" in combined or f"{tag} is also cleared" in combined or f"{tag} is cleared" in combined:
                    continue
            if tag == "transport_caveat":
                if "removed the earlier transport caveat" in combined or "without the prior transport caveat" in combined:
                    continue
            tags.append(tag)
    return tags


def pattern_tags_for_entry(entry: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    target_skill = entry["target_skill"]
    case_id = entry["case_id"]
    run_root = entry["run_root"]
    delta_notes = entry.get("delta_notes", "").lower()
    capability_notes = entry.get("capability_notes", "").lower()
    notes_blob = " ".join(
        [
            entry.get("delta_notes", ""),
            entry.get("with_skill_notes", ""),
            entry.get("capability_notes", ""),
            entry.get("gating_notes", ""),
        ]
    ).lower()

    if "strict" in run_root or "one-skill-under-test" in notes_blob:
        tags.add("strict-profile-isolation")
    if target_skill == "server-vault-write":
        tags.add("controlled-write-surface")
        if "clarify-ambiguous" in case_id:
            tags.add("explicit-ambiguity-boundary")
        if "refuse-verbatim-raw-dump" in case_id:
            tags.add("raw-artifact-refusal")
        if "accepted case" in notes_blob or "generalized promotion path" in notes_blob or run_root.endswith("-v5") or run_root.endswith("-v6"):
            tags.add("accepted-case-regeneration")
    if target_skill == "promotion-bundle-admission-guard":
        tags.add("real-bundle-root-inspection")
        tags.add("artifact-state-classification")
        if "summary-only" in notes_blob or "summary-only" in delta_notes:
            tags.add("refusal-to-trust-summary-only-evidence")
        if "helper" in notes_blob or "script-backed" in run_root:
            tags.add("script-assisted-audit")
        if "tool-backed" in run_root or "wrapper" in notes_blob:
            tags.add("tool-backed-wrapper")
    if target_skill in {"ledger-evidence-audit", "promotion-readiness-auditor"}:
        tags.add("prompt-contained-contract")
    if target_skill.startswith("runtime-governance-"):
        tags.add("narrow-mcp-surface")
        if "dry-run" in notes_blob or "dry-run" in capability_notes:
            tags.add("dry-run-governance-surface")
    return sorted(tags)


def classify_entry(entry: dict[str, Any]) -> dict[str, Any]:
    review_complete = entry.get("review_complete", False)
    evidence_status = entry.get("evidence_status") or "valid"
    verdict = (entry.get("verdict") or "").strip()
    outcome = (entry.get("outcome") or "").strip()
    delta_strength = (entry.get("delta_strength") or "").strip()
    gating_notes = entry.get("gating_notes", "")
    blocker_tags = blocker_tags_from_notes(entry)

    platform_valid = review_complete and evidence_status == "valid"
    usefulness_proven = (
        platform_valid
        and verdict == "usable now"
        and outcome == "pass"
        and delta_strength == "meaningful"
    )
    negative_result = (
        outcome == "fail"
        or entry.get("undertrigger") == "yes"
        or "malformed_output" in blocker_tags
        or "transport_caveat" in blocker_tags
        or (verdict == "not yet ready" and delta_strength in {"weak", "none"})
    )
    parity_revealing = (
        platform_valid
        and not usefulness_proven
        and not (outcome == "fail" or entry.get("undertrigger") == "yes" or "malformed_output" in blocker_tags)
        and (
            delta_strength in {"weak", "none"}
            or "baseline_trigger_mismatch" in gating_notes
            or "meaningful_delta_missing" in gating_notes
        )
        and verdict in {"not yet ready", "usable with caveats"}
    )
    next_class_transition_signal = (
        platform_valid
        and not usefulness_proven
        and entry["line_id"] in {"prompt-contained-net-new", "bundle-state-net-new", "runtime-governance-net-new"}
    )

    return {
        "platform_valid_result": platform_valid,
        "usefulness_proven_result": usefulness_proven,
        "parity_revealing_candidate": parity_revealing,
        "negative_result_worth_remembering": negative_result,
        "next_class_transition_signal": next_class_transition_signal,
        "blocker_tags": blocker_tags,
        "pattern_tags": pattern_tags_for_entry(entry),
    }


def build_root_case_index(root: Path, trial_plan: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not trial_plan:
        return {}
    return {case["case_id"]: case for case in trial_plan.get("cases", [])}


def build_matrix_index(matrix_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not matrix_manifest:
        return {}
    return {result["case_id"]: result for result in matrix_manifest.get("results", [])}


def collect_reviews(root: Path, root_meta: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trial_plan_path = root / "summaries" / "trial-plan.json"
    matrix_path = root / "summaries" / "matrix-run-manifest.json"
    trial_plan = load_json(trial_plan_path) if trial_plan_path.exists() else None
    matrix_manifest = load_json(matrix_path) if matrix_path.exists() else None
    trial_plan_index = build_root_case_index(root, trial_plan)
    matrix_index = build_matrix_index(matrix_manifest)

    review_candidates: list[Path] = []
    if trial_plan:
        for case in trial_plan.get("cases", []):
            review_candidates.append(Path(case["review_path"]))
    else:
        results_dir = root / "results"
        if results_dir.exists():
            review_candidates.extend(sorted(results_dir.glob("*-review.md")))

    experiments: list[dict[str, Any]] = []
    skipped_reviews: list[dict[str, Any]] = []
    for case_index, review_path in enumerate(review_candidates, start=1):
        if not review_path.exists():
            skipped_reviews.append(
                {
                    "review_path": str(review_path),
                    "reason": "missing review file"
                }
            )
            continue
        review_fields, _review_body = read_key_value_markdown(review_path)
        if has_placeholder(review_fields):
            skipped_reviews.append(
                {
                    "review_path": str(review_path),
                    "reason": "pending or placeholder review"
                }
            )
            continue

        case_id = review_fields.get("case_id") or review_path.name.removesuffix("-review.md")
        case_meta = trial_plan_index.get(case_id, {})
        matrix_meta = matrix_index.get(case_id, {})
        run_root = str(root)
        target_skill = (
            review_fields.get("target_skill")
            or case_meta.get("target_skill")
            or matrix_meta.get("target_skill")
            or "unknown"
        )

        baseline_profile = (
            review_fields.get("baseline_profile")
            or case_meta.get("baseline_profile")
            or matrix_meta.get("profiles", {}).get("baseline")
            or matrix_meta.get("baseline_profile")
        )
        trial_profile = (
            review_fields.get("trial_profile")
            or case_meta.get("trial_profile")
            or matrix_meta.get("profiles", {}).get("trial")
            or review_fields.get("with_skill_profile")
        )
        with_skill_profile = review_fields.get("with_skill_profile") or trial_profile
        case_path = case_meta.get("case_path") or str(root / "cases" / f"{case_id}.md")
        root_date = extract_date(run_root) or extract_date(root_meta["source_id"]) or ""

        entry: dict[str, Any] = {
            "experiment_id": f"{root_meta['source_id']}::{case_id}",
            "source_id": root_meta["source_id"],
            "source_kind": root_meta["source_kind"],
            "run_root": run_root,
            "root_date": root_date,
            "root_sequence": root_meta["root_sequence"],
            "case_sequence": case_index,
            "line_id": root_meta["line_id"],
            "surface_family": derive_surface_family(target_skill, root_meta),
            "phase_label": root_meta["phase_label"],
            "case_id": case_id,
            "case_path": case_path,
            "review_path": str(review_path),
            "trial_plan_path": str(trial_plan_path) if trial_plan_path.exists() else None,
            "matrix_manifest_path": str(matrix_path) if matrix_path.exists() else None,
            "target_skill": target_skill,
            "declared_capabilities": parse_declared_capabilities(
                review_fields.get("declared_capabilities")
                or ", ".join(case_meta.get("declared_capabilities", []))
            ),
            "review_status": review_fields.get("review_status", "completed"),
            "review_complete": True,
            "expected_trigger": normalize_bool_flag(review_fields.get("expected_trigger")),
            "baseline_observed_trigger": normalize_bool_flag(review_fields.get("baseline_observed_trigger")),
            "with_skill_observed_trigger": normalize_bool_flag(review_fields.get("with_skill_observed_trigger")),
            "evidence_status": review_fields.get("evidence_status", "valid"),
            "evidence_reason": review_fields.get("evidence_reason", ""),
            "outcome": review_fields.get("outcome", ""),
            "delta_strength": review_fields.get("delta_strength", ""),
            "verdict": review_fields.get("verdict", ""),
            "elapsed_time_ms_baseline": review_fields.get("elapsed_time_ms_baseline"),
            "elapsed_time_ms_with_skill": review_fields.get("elapsed_time_ms_with_skill"),
            "token_usage_baseline": parse_token_usage(review_fields.get("token_usage_baseline")),
            "token_usage_with_skill": parse_token_usage(review_fields.get("token_usage_with_skill")),
            "overtrigger": normalize_bool_flag(review_fields.get("overtrigger")),
            "undertrigger": normalize_bool_flag(review_fields.get("undertrigger")),
            "baseline_profile": baseline_profile,
            "trial_profile": trial_profile,
            "with_skill_profile": with_skill_profile,
            "baseline_raw_dir": review_fields.get("baseline_raw_dir"),
            "with_skill_raw_dir": review_fields.get("with_skill_raw_dir"),
            "baseline_run_summary": review_fields.get("baseline_run_summary"),
            "with_skill_run_summary": review_fields.get("with_skill_run_summary"),
            "baseline_notes": review_fields.get("baseline_notes", ""),
            "with_skill_notes": review_fields.get("with_skill_notes", ""),
            "delta_notes": review_fields.get("delta_notes", ""),
            "safety_notes": review_fields.get("safety_notes", ""),
            "output_notes": review_fields.get("output_notes", ""),
            "harness_faults": review_fields.get("harness_faults", ""),
            "capability_notes": review_fields.get("capability_notes", ""),
            "gating_notes": review_fields.get("gating_notes", ""),
        }
        entry["classifications"] = classify_entry(entry)
        experiments.append(entry)

    root_record = {
        "source_id": root_meta["source_id"],
        "root": str(root),
        "source_kind": root_meta["source_kind"],
        "line_id": root_meta["line_id"],
        "surface_family": root_meta["surface_family"],
        "phase_label": root_meta["phase_label"],
        "status": "included" if experiments else "skipped",
        "included_experiment_count": len(experiments),
        "skipped_review_count": len(skipped_reviews),
        "skipped_reviews": skipped_reviews,
    }
    return experiments, root_record


def summarize_registry(experiments: list[dict[str, Any]], roots: list[dict[str, Any]]) -> dict[str, Any]:
    counter = Counter()
    for entry in experiments:
        counter["included_experiments"] += 1
        if entry["classifications"]["platform_valid_result"]:
            counter["platform_valid_results"] += 1
        if entry["classifications"]["usefulness_proven_result"]:
            counter["usefulness_proven_results"] += 1
        if entry["classifications"]["parity_revealing_candidate"]:
            counter["parity_revealing_candidates"] += 1
        if entry["classifications"]["negative_result_worth_remembering"]:
            counter["negative_results"] += 1
    counter["included_roots"] = sum(1 for root in roots if root["status"] == "included")
    counter["skipped_roots"] = sum(1 for root in roots if root["status"] == "skipped")
    return dict(counter)


def build_winning_patterns(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winning = [entry for entry in experiments if entry["classifications"]["usefulness_proven_result"]]
    tag_counter: Counter[str] = Counter()
    evidence: defaultdict[str, list[str]] = defaultdict(list)
    for entry in winning:
        for tag in entry["classifications"]["pattern_tags"]:
            tag_counter[tag] += 1
            evidence[tag].append(entry["experiment_id"])
    labels = {
        "strict-profile-isolation": "Strict one-skill-under-test isolation",
        "explicit-ambiguity-boundary": "Explicit ambiguity boundary cases",
        "raw-artifact-refusal": "Refusal to persist raw artifacts",
        "accepted-case-regeneration": "Accepted-case regeneration for reproducibility",
        "real-bundle-root-inspection": "Real bundle-root inspection instead of prompt-contained contracts",
        "artifact-state-classification": "Artifact-state classification from disk",
        "refusal-to-trust-summary-only-evidence": "Refusal to trust summary-only evidence",
        "script-assisted-audit": "Script-assisted operational audit surface",
        "controlled-write-surface": "Controlled-write decision-boundary surface",
    }
    patterns: list[dict[str, Any]] = []
    for tag, count in tag_counter.most_common():
        if tag not in labels:
            continue
        patterns.append(
            {
                "pattern_id": tag,
                "label": labels[tag],
                "count": count,
                "evidence_experiments": evidence[tag],
            }
        )
    return patterns


def build_parity_prone_families(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in experiments:
        grouped[entry["line_id"]].append(entry)

    results: list[dict[str, Any]] = []
    for line_id, entries in grouped.items():
        parity = [entry for entry in entries if entry["classifications"]["parity_revealing_candidate"]]
        wins = [entry for entry in entries if entry["classifications"]["usefulness_proven_result"]]
        if len(parity) >= 2 and len(parity) >= max(2, len(entries) // 2) and not wins:
            results.append(
                {
                    "line_id": line_id,
                    "surface_family": entries[0]["surface_family"],
                    "experiment_count": len(entries),
                    "parity_count": len(parity),
                    "evidence_experiments": [entry["experiment_id"] for entry in parity],
                }
            )
    return sorted(results, key=lambda item: (-item["parity_count"], item["line_id"]))


def build_locally_exhausted_lines(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exhausted: list[dict[str, Any]] = []

    prompt_entries = [entry for entry in experiments if entry["line_id"] == "prompt-contained-net-new"]
    if prompt_entries and all(not entry["classifications"]["usefulness_proven_result"] for entry in prompt_entries):
        exhausted.append(
            {
                "line_id": "prompt-contained-net-new",
                "label": "Prompt-contained net-new candidates",
                "reason": "Multiple reruns stayed in parity-revealing or weak-delta territory without a threshold-crossing usefulness proof.",
                "evidence_experiments": [entry["experiment_id"] for entry in prompt_entries],
            }
        )

    bundle_entries = [
        entry
        for entry in sorted(experiments, key=lambda item: (item["root_sequence"], item["case_sequence"]))
        if entry["target_skill"] == "promotion-bundle-admission-guard"
    ]
    first_win_index = next(
        (index for index, entry in enumerate(bundle_entries) if entry["classifications"]["usefulness_proven_result"]),
        None,
    )
    if first_win_index is not None:
        followups = bundle_entries[first_win_index + 1 :]
        weak_followups = [
            entry
            for entry in followups
            if not entry["classifications"]["usefulness_proven_result"]
            and entry["classifications"]["parity_revealing_candidate"]
        ]
        if len(weak_followups) >= 4:
            exhausted.append(
                {
                    "line_id": "promotion-bundle-admission-guard-portability-followups",
                    "label": "Bundle-state portability follow-ups after the first win",
                    "reason": "After the initial bundle-state threshold win, repeated follow-up variants kept re-proving operational structure but not family-level outcome delta.",
                    "evidence_experiments": [entry["experiment_id"] for entry in weak_followups],
                }
            )

    return exhausted


def build_repeated_blockers(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    evidence: defaultdict[str, list[str]] = defaultdict(list)
    families: defaultdict[str, set[str]] = defaultdict(set)
    for entry in experiments:
        for blocker in entry["classifications"]["blocker_tags"]:
            counter[blocker] += 1
            evidence[blocker].append(entry["experiment_id"])
            families[blocker].add(entry["line_id"])
    blockers: list[dict[str, Any]] = []
    for blocker, count in counter.most_common():
        blockers.append(
            {
                "blocker_id": blocker,
                "count": count,
                "affected_lines": sorted(families[blocker]),
                "evidence_experiments": evidence[blocker],
            }
        )
    return blockers


def build_negative_results(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []

    def add_if_match(predicate: Any, reason: str) -> None:
        for entry in experiments:
            if predicate(entry):
                picked.append(
                    {
                        "experiment_id": entry["experiment_id"],
                        "target_skill": entry["target_skill"],
                        "line_id": entry["line_id"],
                        "reason": reason,
                    }
                )
                return

    add_if_match(
        lambda entry: entry["experiment_id"] == "server-vault-write-policy-delta-v2::server-vault-write-clarify-ambiguous-write-mode",
        "Meaningful ambiguity delta regressed in the first combined rerun and exposed cross-run contamination plus prompt-shape sensitivity.",
    )
    add_if_match(
        lambda entry: entry["target_skill"] == "runtime-governance-remediation-guard",
        "The first dry-run runtime-governance next-class pass failed by undertrigger and malformed tool-use behavior, so tool exposure alone is not enough.",
    )
    add_if_match(
        lambda entry: entry["experiment_id"] == "promotion-bundle-admission-guard-clean-second-pass::promotion-bundle-admission-guard-missing-provenance-bundle",
        "The clean second bundle-state pass removed the timeout caveat but still fell back to weak delta, clarifying that reproducibility is the blocker.",
    )
    add_if_match(
        lambda entry: entry["target_skill"] == "ledger-evidence-audit" and entry["source_id"] == "ledger-evidence-audit-hardening-rerun",
        "Hardening improved forensic discipline but still did not escape baseline parity on a prompt-contained surface.",
    )
    return picked


def build_next_step_portfolio(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    recommended = {
        "move_id": "runtime-governance-next-class-transition",
        "status": "recommended-now",
        "title": "Resume only with one hardened runtime-governance dry-run case",
        "why": "The read-only runtime-governance checker is already platform-valid but parity-prone, while the remediation guard is the only open next-class transition with a genuinely different machine surface. Its first pass failed because the trial path did not reliably use the exposed tools, not because the class is already disproven.",
        "evidence_lines": [
            "runtime-governance-net-new",
            "bundle-state-net-new"
        ],
        "do_now": [
            "Harden the remediation contract so the with-skill path must call the dry-run MCP tools successfully or fail fast.",
            "Use one case where the decisive proof depends on dry-run-only machine outputs that baseline cannot reconstruct from direct file reads alone.",
            "Keep the connector read-only or dry-run only and preserve explicit rollback preview discipline."
        ],
        "do_not_do": [
            "Do not run another prompt-contained net-new rerun.",
            "Do not run another bundle-state portability rerun that only changes the audit surface while keeping the same proof class.",
            "Do not restart broad skill-line improvement before one next-class transition is selected."
        ]
    }

    portfolio = [
        recommended,
        {
            "move_id": "freeze-prompt-contained-family",
            "status": "freeze",
            "title": "Freeze prompt-contained net-new candidates as diagnostic references",
            "why": "They produced honest parity boundaries and reusable negative evidence, but repeated hardening stayed below the usefulness threshold."
        },
        {
            "move_id": "pause-bundle-state-portability-followups",
            "status": "hold",
            "title": "Pause bundle-state portability follow-ups until the proof class changes",
            "why": "The first bundle-state win stands, but repeated follow-up variants kept re-proving operational structure without crossing the family-level delta threshold."
        },
        {
            "move_id": "keep-server-vault-write-as-benchmark",
            "status": "benchmark-only",
            "title": "Keep server-vault-write accepted-case contour as the strongest reproducible benchmark",
            "why": "This line is already usefulness-proven and should anchor future comparisons rather than becoming the main active improvement line in the paused phase."
        }
    ]

    return {
        "format": "core-next-step-portfolio-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommended_next_move": recommended,
        "portfolio": portfolio,
        "input_experiment_count": len(experiments),
    }


def build_pattern_extraction(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "format": "core-pattern-extraction-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "winning_patterns": build_winning_patterns(experiments),
        "parity_prone_families": build_parity_prone_families(experiments),
        "locally_exhausted_lines": build_locally_exhausted_lines(experiments),
        "repeated_blockers": build_repeated_blockers(experiments),
        "negative_results_worth_remembering": build_negative_results(experiments),
    }


def render_report(
    registry: dict[str, Any],
    pattern_extraction: dict[str, Any],
    portfolio: dict[str, Any],
) -> str:
    summary = registry["summary"]
    lines: list[str] = []
    lines.append("# Skill-Creator Experiment Intelligence V1")
    lines.append("")
    lines.append(f"Generated at: `{registry['generated_at']}`")
    lines.append(f"Scope: `{registry['scope']}`")
    lines.append("")
    lines.append("## Corpus")
    lines.append("")
    lines.append(f"- included experiments: `{summary['included_experiments']}`")
    lines.append(f"- included roots: `{summary['included_roots']}`")
    lines.append(f"- skipped roots: `{summary['skipped_roots']}`")
    lines.append(f"- platform-valid results: `{summary.get('platform_valid_results', 0)}`")
    lines.append(f"- usefulness-proven results: `{summary.get('usefulness_proven_results', 0)}`")
    lines.append(f"- parity-revealing candidates: `{summary.get('parity_revealing_candidates', 0)}`")
    lines.append("")

    lines.append("## Winning Patterns")
    lines.append("")
    for item in pattern_extraction["winning_patterns"][:6]:
        evidence = ", ".join(f"`{exp}`" for exp in item["evidence_experiments"])
        lines.append(f"- `{item['label']}` ({item['count']}): {evidence}")
    if not pattern_extraction["winning_patterns"]:
        lines.append("- none yet")
    lines.append("")

    lines.append("## Parity-Prone Families")
    lines.append("")
    for item in pattern_extraction["parity_prone_families"]:
        evidence = ", ".join(f"`{exp}`" for exp in item["evidence_experiments"][:6])
        lines.append(f"- `{item['line_id']}` parity_count=`{item['parity_count']}` on `{item['experiment_count']}` experiments: {evidence}")
    if not pattern_extraction["parity_prone_families"]:
        lines.append("- none")
    lines.append("")

    lines.append("## Locally Exhausted Lines")
    lines.append("")
    for item in pattern_extraction["locally_exhausted_lines"]:
        lines.append(f"- `{item['label']}`: {item['reason']}")
    if not pattern_extraction["locally_exhausted_lines"]:
        lines.append("- none")
    lines.append("")

    lines.append("## Repeated Blockers")
    lines.append("")
    for item in pattern_extraction["repeated_blockers"][:8]:
        lines.append(f"- `{item['blocker_id']}` count=`{item['count']}` affected_lines=`{', '.join(item['affected_lines'])}`")
    if not pattern_extraction["repeated_blockers"]:
        lines.append("- none")
    lines.append("")

    lines.append("## Negative Results Worth Remembering")
    lines.append("")
    for item in pattern_extraction["negative_results_worth_remembering"]:
        lines.append(f"- `{item['experiment_id']}`: {item['reason']}")
    if not pattern_extraction["negative_results_worth_remembering"]:
        lines.append("- none")
    lines.append("")

    recommended = portfolio["recommended_next_move"]
    lines.append("## Recommended Next Move")
    lines.append("")
    lines.append(f"- `{recommended['title']}`")
    lines.append(f"- why: {recommended['why']}")
    for step in recommended["do_now"]:
        lines.append(f"- do_now: {step}")
    for step in recommended["do_not_do"]:
        lines.append(f"- do_not_do: {step}")
    lines.append("")
    return "\n".join(lines) + "\n"


def validate_registry(registry: dict[str, Any]) -> None:
    required_top_level = {"format", "scope", "generated_at", "source_manifest", "summary", "roots", "experiments"}
    missing = sorted(required_top_level - set(registry.keys()))
    if missing:
        raise SystemExit(f"registry missing required keys: {missing}")
    if registry["format"] != "core-experiment-registry-v1":
        raise SystemExit("registry format mismatch")
    for entry in registry["experiments"]:
        for field in ("experiment_id", "source_id", "run_root", "case_id", "target_skill", "classifications"):
            if field not in entry:
                raise SystemExit(f"experiment missing required field: {field}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build experiment intelligence artifacts for the current skill-creator corpus.")
    parser.add_argument(
        "--source-manifest",
        default="/home/agent/agents/core/runtime/experiment-intelligence/skill_creator_experiment_corpus_v1.json",
        help="Path to the corpus manifest."
    )
    parser.add_argument(
        "--out-dir",
        default="/home/agent/agents/core/artifacts/experiment-intelligence/skill-creator-history-v1",
        help="Output directory for the generated artifacts."
    )
    args = parser.parse_args()

    source_manifest_path = Path(args.source_manifest)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_manifest = load_json(source_manifest_path)
    roots_meta = source_manifest.get("roots", [])

    experiments: list[dict[str, Any]] = []
    root_records: list[dict[str, Any]] = []
    for root_sequence, root_meta in enumerate(roots_meta, start=1):
        enriched_meta = dict(root_meta)
        enriched_meta["root_sequence"] = root_sequence
        root = Path(root_meta["root"])
        collected, root_record = collect_reviews(root, enriched_meta)
        experiments.extend(collected)
        root_records.append(root_record)

    experiments.sort(key=lambda item: (item["root_sequence"], item["case_sequence"], item["experiment_id"]))
    registry = {
        "format": "core-experiment-registry-v1",
        "scope": source_manifest["scope"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_manifest_path),
        "summary": summarize_registry(experiments, root_records),
        "roots": root_records,
        "experiments": experiments,
    }
    validate_registry(registry)
    pattern_extraction = build_pattern_extraction(experiments)
    portfolio = build_next_step_portfolio(experiments)
    report = render_report(registry, pattern_extraction, portfolio)

    dump_json(out_dir / "experiment-registry-v1.json", registry)
    dump_json(out_dir / "pattern-extraction-v1.json", pattern_extraction)
    dump_json(out_dir / "next-step-portfolio-v1.json", portfolio)
    (out_dir / "retrospective-report-v1.md").write_text(report, encoding="utf-8")

    print(json.dumps(
        {
            "out_dir": str(out_dir),
            "included_experiments": registry["summary"].get("included_experiments", 0),
            "included_roots": registry["summary"].get("included_roots", 0),
            "skipped_roots": registry["summary"].get("skipped_roots", 0),
            "recommended_next_move": portfolio["recommended_next_move"]["move_id"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
