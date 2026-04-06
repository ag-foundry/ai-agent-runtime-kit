#!/usr/bin/env python3
"""Build a selective file-level provenance report for an accepted-case-set contour."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from evaluate_readiness import parse_review
from promote_accepted_case_set import validate_manifest as validate_case_set_manifest


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def report_contract_path() -> Path:
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


def add_path_context(
    contexts: list[dict[str, object]],
    seen: set[tuple[str, str]],
    *,
    context_id: str,
    role: str,
    path: Path,
    justification: str,
) -> None:
    key = (role, str(path))
    if key in seen:
        return
    seen.add(key)
    contexts.append(
        {
            "context_id": context_id,
            "role": role,
            "path": str(path),
            "exists": path.exists(),
            "justification": justification,
        }
    )


def add_file_anchor(
    anchors: list[dict[str, object]],
    seen: set[tuple[str, str]],
    *,
    anchor_id: str,
    role: str,
    path: Path,
    justification: str,
    case_id: str | None = None,
    mode: str | None = None,
    source_field: str | None = None,
    backup_path: Path | None = None,
) -> None:
    key = (role, str(path))
    if key in seen:
        return
    seen.add(key)
    item: dict[str, object] = {
        "anchor_id": anchor_id,
        "role": role,
        "path": str(path),
        "exists": path.is_file(),
        "justification": justification,
    }
    if case_id:
        item["case_id"] = case_id
    if mode:
        item["mode"] = mode
    if source_field:
        item["source_field"] = source_field
    if backup_path is not None:
        item["backup_path"] = str(backup_path)
        item["backup_exists"] = backup_path.exists()
    anchors.append(item)


def validate_report(report: dict[str, object]) -> None:
    contract = load_json(report_contract_path())
    missing = [key for key in contract["required_top_level"] if key not in report]
    if missing:
        raise SystemExit(f"provenance report missing required keys: {', '.join(missing)}")
    if report.get("format") != contract["version"]:
        raise SystemExit(f"provenance report format must be {contract['version']!r}")

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checklist", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    checklist_path = Path(args.checklist).resolve()
    checklist = load_json(checklist_path)
    case_set_id = require_non_empty_string(checklist.get("case_set_id"), "case_set_id")
    skill_name = require_non_empty_string(checklist.get("skill_name"), "skill_name")
    registry_manifest_path = Path(require_non_empty_string(checklist.get("registry_manifest_path"), "registry_manifest_path")).resolve()
    source_run_root = Path(require_non_empty_string(checklist.get("source_run_root"), "source_run_root")).resolve()
    rollback = checklist.get("rollback")
    if not isinstance(rollback, dict):
        raise SystemExit("rollback must be an object in the promotion checklist")
    rollback_pack_manifest_path = Path(
        require_non_empty_string(rollback.get("rollback_pack_manifest"), "rollback.rollback_pack_manifest")
    ).resolve()

    registry_manifest = load_json(registry_manifest_path)
    validate_case_set_manifest(registry_manifest)
    rollback_pack_manifest = load_json(rollback_pack_manifest_path)

    path_level_contexts: list[dict[str, object]] = []
    required_file_anchors: list[dict[str, object]] = []
    supporting_file_anchors: list[dict[str, object]] = []
    seen_contexts: set[tuple[str, str]] = set()
    seen_required: set[tuple[str, str]] = set()
    seen_supporting: set[tuple[str, str]] = set()

    accepted_case_set_root = registry_manifest_path.parent
    add_path_context(
        path_level_contexts,
        seen_contexts,
        context_id="accepted_case_set_root",
        role="accepted-case-set-root",
        path=accepted_case_set_root,
        justification="The registry directory stays path-level because it is a stable container for manifest, case files, and optional additive evidence.",
    )
    add_path_context(
        path_level_contexts,
        seen_contexts,
        context_id="source_run_root",
        role="source-run-root",
        path=source_run_root,
        justification="The run root stays path-level because it is a container context for many raw and summary artifacts whose exact file set may expand.",
    )

    evidence_run_roots = registry_manifest.get("evidence_run_roots", [])
    if isinstance(evidence_run_roots, list):
        for index, raw_path in enumerate(evidence_run_roots):
            evidence_path = Path(str(raw_path)).resolve()
            if evidence_path == source_run_root:
                continue
            add_path_context(
                path_level_contexts,
                seen_contexts,
                context_id=f"evidence_run_root_{index}",
                role="evidence-run-root",
                path=evidence_path,
                justification="Historical corroboration run roots stay path-level because they are supporting context rather than the primary promotion evidence bundle.",
            )

    add_path_context(
        path_level_contexts,
        seen_contexts,
        context_id="rollback_pack_root",
        role="rollback-pack-root",
        path=rollback_pack_manifest_path.parent,
        justification="The rollback pack stays path-level as a bundle root, while the files that matter for restore clarity are anchored individually below.",
    )

    add_file_anchor(
        required_file_anchors,
        seen_required,
        anchor_id="registry_manifest",
        role="registry-manifest",
        path=registry_manifest_path,
        justification="This file is the canonical accepted-case-set record, so audit must anchor it directly at file level.",
    )

    for summary_name in ("trial-plan.json", "review-pack-manifest.json", "matrix-run-manifest.json"):
        add_file_anchor(
            required_file_anchors,
            seen_required,
            anchor_id=f"source_run_summary_{summary_name.removesuffix('.json')}",
            role="readiness-summary-file",
            path=source_run_root / "summaries" / summary_name,
            justification="Readiness depends on concrete summary files, so these summary manifests are audit-critical file-level anchors.",
            source_field=f"source_run_root/summaries/{summary_name}",
        )

    cases = registry_manifest.get("cases", [])
    if not isinstance(cases, list):
        raise SystemExit("registry manifest cases must be a list")
    for item in cases:
        if not isinstance(item, dict):
            raise SystemExit("registry manifest case entries must be objects")
        case_id = require_non_empty_string(item.get("case_id"), "registry manifest case_id")
        accepted_case_path = (registry_manifest_path.parent / require_non_empty_string(item.get("path"), f"{case_id}.path")).resolve()
        source_case_path = Path(require_non_empty_string(item.get("source_case_path"), f"{case_id}.source_case_path")).resolve()
        source_review_path = Path(require_non_empty_string(item.get("source_review_path"), f"{case_id}.source_review_path")).resolve()

        add_file_anchor(
            required_file_anchors,
            seen_required,
            anchor_id=f"{case_id}-accepted-case-file",
            role="accepted-case-file",
            path=accepted_case_path,
            justification="Accepted case files are the concrete registry payload, so they are required file-level provenance anchors.",
            case_id=case_id,
            source_field="cases[].path",
        )
        add_file_anchor(
            required_file_anchors,
            seen_required,
            anchor_id=f"{case_id}-source-case-file",
            role="source-case-file",
            path=source_case_path,
            justification="The original case file that was promoted should remain directly inspectable at file level.",
            case_id=case_id,
            source_field="cases[].source_case_path",
        )
        add_file_anchor(
            required_file_anchors,
            seen_required,
            anchor_id=f"{case_id}-source-review-file",
            role="source-review-file",
            path=source_review_path,
            justification="Promotion relies on completed review files, so each source review remains a required file-level anchor.",
            case_id=case_id,
            source_field="cases[].source_review_path",
        )

        review_fields = parse_review(source_review_path)
        for field_name, mode in (("baseline_run_summary", "baseline"), ("with_skill_run_summary", "with-skill")):
            run_summary_path_text = review_fields.get(field_name, "").strip()
            if run_summary_path_text:
                add_file_anchor(
                    required_file_anchors,
                    seen_required,
                    anchor_id=f"{case_id}-{mode}-run-summary",
                    role="readiness-run-summary",
                    path=Path(run_summary_path_text).resolve(),
                    justification="Per-mode run-summary.json files are compact machine-readable anchors for the raw execution evidence behind the review.",
                    case_id=case_id,
                    mode=mode,
                    source_field=field_name,
                )
        for field_name, mode in (("baseline_raw_dir", "baseline"), ("with_skill_raw_dir", "with-skill")):
            raw_dir_text = review_fields.get(field_name, "").strip()
            if raw_dir_text:
                add_file_anchor(
                    supporting_file_anchors,
                    seen_supporting,
                    anchor_id=f"{case_id}-{mode}-assistant-output",
                    role="assistant-output-anchor",
                    path=Path(raw_dir_text).resolve() / "assistant.txt",
                    justification="Assistant output is useful for semantic audit, but it stays supporting rather than mandatory because the gate should not depend on full text interpretation.",
                    case_id=case_id,
                    mode=mode,
                    source_field=field_name,
                )

    copied_items = rollback_pack_manifest.get("copied", [])
    if isinstance(copied_items, list):
        for index, item in enumerate(copied_items):
            if not isinstance(item, dict):
                continue
            source_path = Path(str(item.get("source", ""))).resolve()
            backup_path = Path(str(item.get("backup", ""))).resolve()
            if source_path.is_file() or source_path.suffix:
                add_file_anchor(
                    required_file_anchors,
                    seen_required,
                    anchor_id=f"rollback-covered-file-{index}",
                    role="rollback-covered-file",
                    path=source_path,
                    backup_path=backup_path,
                    justification="Files changed by this phase should be restorable individually, so rollback coverage is anchored at file level.",
                    source_field="rollback_pack_manifest.copied",
                )

    report = {
        "format": "openclaw-promotion-provenance-v1",
        "generated_at": now_utc_iso(),
        "checklist_path": str(checklist_path),
        "case_set_id": case_set_id,
        "skill_name": skill_name,
        "registry_manifest_path": str(registry_manifest_path),
        "source_run_root": str(source_run_root),
        "path_level_contexts": path_level_contexts,
        "required_file_anchors": required_file_anchors,
        "supporting_file_anchors": supporting_file_anchors,
    }
    validate_report(report)

    output_path = Path(args.output).resolve()
    if output_path.exists():
        if not args.force:
            raise SystemExit(f"output already exists: {output_path}; pass --force to overwrite")
        if output_path.is_dir():
            shutil.rmtree(output_path)
        else:
            output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
