#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

STEP23_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step23.py")
STEP20_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step20.py")
STEP22_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step22.py")

ROLE_PRIORITY = {
    "official_repo": 5,
    "official_docs": 4,
    "issue_problem": 3,
    "practical_community": 2,
    "regional_community": 2,
    "generic_reference": 1,
}

ROLE_CHUNK_BONUS = {
    "official_repo": 8.0,
    "official_docs": 6.0,
    "issue_problem": 3.0,
    "practical_community": 1.5,
    "regional_community": 1.2,
    "generic_reference": 0.0,
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _jsonl_write(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_module(path: Path, name: str):
    if not path.exists():
        raise SystemExit(f"missing helper: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _priority(role: str) -> int:
    return ROLE_PRIORITY.get(str(role or "").lower(), 0)


def _role_bonus(role: str) -> float:
    return ROLE_CHUNK_BONUS.get(str(role or "").lower(), 0.0)


def _rebuild_ranked_targets(reranked_rows: list[dict]) -> list[dict]:
    source_map = {}
    for row in reranked_rows:
        url = str(row.get("source_url") or "")
        if not url:
            continue
        entry = source_map.setdefault(url, {
            "url": url,
            "title": row.get("title"),
            "source_role": row.get("source_role"),
            "host": row.get("host"),
            "best_score": float(row.get("score") or 0.0),
            "best_chunk_id": row.get("chunk_id"),
            "supporting_chunks": 0,
            "focus_hits": set(),
        })
        entry["supporting_chunks"] += 1
        row_score = float(row.get("score") or 0.0)
        if row_score > entry["best_score"]:
            entry["best_score"] = row_score
            entry["best_chunk_id"] = row.get("chunk_id")
            entry["source_role"] = row.get("source_role")
        for hit in row.get("focus_hits") or []:
            entry["focus_hits"].add(hit)

    ranked_targets = []
    for entry in source_map.values():
        aggregate_score = round(float(entry["best_score"]) + min(int(entry["supporting_chunks"]), 5) * 0.15, 4)
        ranked_targets.append({
            "url": entry["url"],
            "title": entry["title"],
            "source_role": entry["source_role"],
            "host": entry["host"],
            "aggregate_score": aggregate_score,
            "best_score": entry["best_score"],
            "best_chunk_id": entry["best_chunk_id"],
            "supporting_chunks": entry["supporting_chunks"],
            "focus_hits": sorted(entry["focus_hits"])[:8],
        })

    ranked_targets.sort(
        key=lambda x: (
            _priority(x.get("source_role")),
            float(x.get("aggregate_score") or 0.0),
            float(x.get("best_score") or 0.0),
            int(x.get("supporting_chunks") or 0),
        ),
        reverse=True,
    )
    return ranked_targets


def run(artifact_dir: Path) -> int:
    step23 = _load_module(STEP23_HELPER, "project_research_step23_helper")
    step20 = _load_module(STEP20_HELPER, "project_research_step20_helper")
    step22 = _load_module(STEP22_HELPER, "project_research_step22_helper")

    step23.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    provenance_path = artifact_dir / "provenance.json"
    findings_path = artifact_dir / "findings.jsonl"
    rerank_path = artifact_dir / "reranked_evidence.jsonl"
    grounding_path = artifact_dir / "synthesis_grounding.json"
    grounding_report_path = artifact_dir / "synthesis_grounding_report.json"
    eval_report_path = artifact_dir / "eval_safety_report.json"
    research_path = artifact_dir / "RESEARCH.md"

    context = _read_json(context_path, {})
    provenance = _read_json(provenance_path, {})
    reranked_rows = _read_jsonl(rerank_path)
    findings = _read_jsonl(findings_path)

    roots = step22._focus_roots(context)
    changed = 0
    rescored = []

    for row in reranked_rows:
        url = str(row.get("source_url") or "")
        current_role = str(row.get("source_role") or "")
        normalized_role = step22._guess_normalized_role(url, current_role, roots)
        base_score = float(row.get("score") or 0.0)
        adjusted_score = round(base_score + _role_bonus(normalized_role), 4)

        if normalized_role != current_role:
            changed += 1

        score_details = dict(row.get("score_details") or {})
        score_details["normalized_role"] = normalized_role
        score_details["official_chunk_bonus"] = _role_bonus(normalized_role)
        score_details["base_score_before_official_bonus"] = base_score

        new_row = dict(row)
        new_row["source_role"] = normalized_role
        new_row["score"] = adjusted_score
        new_row["score_details"] = score_details
        rescored.append(new_row)

    rescored.sort(
        key=lambda x: (
            float(x.get("score") or 0.0),
            _priority(x.get("source_role")),
            len(x.get("focus_hits") or []),
        ),
        reverse=True,
    )
    _jsonl_write(rerank_path, rescored)

    rerank_report_path = artifact_dir / "rerank_report.json"
    rerank_report = _read_json(rerank_report_path, {})
    if isinstance(rerank_report, dict):
        rerank_report["status"] = "implemented_v3"
        rerank_report["rerank_policy"] = "official_aware_chunk_rerank"
        rerank_report["role_normalization_changed_rows"] = changed
        rerank_report["top_chunk_ids"] = [x.get("chunk_id") for x in rescored[:10]]
        _write_json(rerank_report_path, rerank_report)

    grounded, citation_candidates = step20._ground_findings(findings, rescored)
    grounding = {
        "status": "implemented_v2",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "grounded_findings_count": sum(1 for x in grounded if (x.get("support_count") or 0) > 0),
        "total_findings": len(grounded),
        "findings": grounded,
        "citation_candidates": citation_candidates,
    }
    _write_json(grounding_path, grounding)

    grounding_report = {
        "status": "implemented_v2",
        "grounded_findings_count": grounding["grounded_findings_count"],
        "total_findings": grounding["total_findings"],
        "citation_candidates_count": len(citation_candidates),
        "top_chunk_ids": [x.get("chunk_id") for x in citation_candidates[:10]],
        "grounding_policy": "official_aware_chunk_rerank",
    }
    _write_json(grounding_report_path, grounding_report)
    step20._append_research_section(research_path, grounded)

    rerank_plan = context.get("rerank_plan") or {}
    rerank_plan["strategy"] = "evidence_chunk_rerank_v3_official_aware_chunks"
    rerank_plan["official_first_ordering"] = True
    rerank_plan["official_aware_chunk_rerank"] = True
    rerank_plan["ranked_chunks_file"] = str(rerank_path)
    rerank_plan["rerank_report"] = str(rerank_report_path)
    rerank_plan["top_chunks"] = rescored[:10]
    rerank_plan["ranked_targets"] = _rebuild_ranked_targets(rescored)
    rerank_plan["chunk_count_scored"] = len(rescored)
    context["rerank_plan"] = rerank_plan

    synthesis_grounding = context.get("synthesis_grounding") or {}
    synthesis_grounding["status"] = "implemented_v2"
    synthesis_grounding["grounding_file"] = str(grounding_path)
    synthesis_grounding["grounding_report"] = str(grounding_report_path)
    synthesis_grounding["grounded_findings_count"] = grounding["grounded_findings_count"]
    synthesis_grounding["total_findings"] = grounding["total_findings"]
    synthesis_grounding["citation_candidates_count"] = len(citation_candidates)
    context["synthesis_grounding"] = synthesis_grounding

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer5_rerank"] = {
            "status": "implemented_v3",
            "scaffold_only": False,
            "retrieval_unit": "evidence_chunks",
            "chunk_count_scored": len(rescored),
            "ranked_target_count": len(rerank_plan.get("ranked_targets") or []),
            "official_aware_chunk_rerank": True,
        }
        arch["layer6_synthesis_provenance"] = {
            "status": "implemented_v2",
            "scaffold_only": False,
            "grounded_findings_count": grounding["grounded_findings_count"],
            "citation_candidates_count": len(citation_candidates),
            "grounding_policy": "official_aware_chunk_rerank",
        }
        context["architecture_layers"] = arch

    if isinstance(provenance, dict):
        provenance["role_normalization"] = {
            "status": "implemented_v2",
            "focus_roots": roots,
            "changed_rows": changed,
            "rerank_report": str(rerank_report_path),
        }
        provenance["synthesis_grounding_file"] = str(grounding_path)
        provenance["synthesis_grounding_report"] = str(grounding_report_path)
        provenance["citation_candidates"] = citation_candidates
        _write_json(provenance_path, provenance)

    _write_json(context_path, context)
    step22._update_eval(context, eval_report_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step24.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
