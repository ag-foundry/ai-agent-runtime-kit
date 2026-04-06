#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

STEP26_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step26.py")
STEP20_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step20.py")
STEP22_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step22.py")
STEP19_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step19.py")

MAX_CHUNKS_PER_SOURCE = 2
DIVERSE_POOL_LIMIT = 60


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


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


def _source_diverse_rows(
    rows: list[dict],
    max_per_source: int = MAX_CHUNKS_PER_SOURCE,
    limit: int = DIVERSE_POOL_LIMIT,
) -> list[dict]:
    counts = {}
    selected = []

    for row in rows:
        url = str(row.get("source_url") or "")
        if not url:
            continue
        used = counts.get(url, 0)
        if used >= max_per_source:
            continue
        selected.append(row)
        counts[url] = used + 1
        if len(selected) >= limit:
            break

    return selected


def run(artifact_dir: Path) -> int:
    step26 = _load_module(STEP26_HELPER, "project_research_step26_helper")
    step20 = _load_module(STEP20_HELPER, "project_research_step20_helper")
    step22 = _load_module(STEP22_HELPER, "project_research_step22_helper")
    step19 = _load_module(STEP19_HELPER, "project_research_step19_helper")

    # step26 may rebuild context/rerank scaffold state.
    # Critical: immediately refresh the real rerank writer from step19 afterwards,
    # so ranked_targets keep full metadata before step27 adds grounding/diversity layers.
    step26.run(artifact_dir)
    step19.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    provenance_path = artifact_dir / "provenance.json"
    findings_path = artifact_dir / "findings.jsonl"
    rerank_path = artifact_dir / "reranked_evidence.jsonl"
    diverse_path = artifact_dir / "reranked_evidence_diverse.jsonl"
    grounding_path = artifact_dir / "synthesis_grounding.json"
    grounding_report_path = artifact_dir / "synthesis_grounding_report.json"
    research_path = artifact_dir / "RESEARCH.md"
    eval_report_path = artifact_dir / "eval_safety_report.json"
    rerank_report_path = artifact_dir / "rerank_report.json"

    context = _read_json(context_path, {})
    provenance = _read_json(provenance_path, {})
    findings = _read_jsonl(findings_path)
    reranked_rows = _read_jsonl(rerank_path)

    diverse_rows = _source_diverse_rows(
        reranked_rows,
        max_per_source=MAX_CHUNKS_PER_SOURCE,
        limit=DIVERSE_POOL_LIMIT,
    )
    _jsonl_write(diverse_path, diverse_rows)

    grounded, citation_candidates = step20._ground_findings(findings, diverse_rows)

    grounding = {
        "status": "implemented_v3",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "grounded_findings_count": sum(1 for x in grounded if (x.get("support_count") or 0) > 0),
        "total_findings": len(grounded),
        "findings": grounded,
        "citation_candidates": citation_candidates,
        "grounding_policy": "source_diverse_chunk_pool",
        "max_chunks_per_source": MAX_CHUNKS_PER_SOURCE,
        "diverse_pool_size": len(diverse_rows),
    }
    _write_json(grounding_path, grounding)

    grounding_report = {
        "status": "implemented_v3",
        "grounded_findings_count": grounding["grounded_findings_count"],
        "total_findings": grounding["total_findings"],
        "citation_candidates_count": len(citation_candidates),
        "top_chunk_ids": [x.get("chunk_id") for x in citation_candidates[:10]],
        "grounding_policy": "source_diverse_chunk_pool",
        "max_chunks_per_source": MAX_CHUNKS_PER_SOURCE,
        "diverse_pool_size": len(diverse_rows),
    }
    _write_json(grounding_report_path, grounding_report)
    step20._append_research_section(research_path, grounded)

    rerank_plan = context.get("rerank_plan") or {}
    rerank_plan["strategy"] = "evidence_chunk_rerank_v5_source_diverse_grounding"
    rerank_plan["grounding_candidate_file"] = str(diverse_path)
    rerank_plan["source_diversity_guard"] = True
    rerank_plan["max_chunks_per_source_for_grounding"] = MAX_CHUNKS_PER_SOURCE
    rerank_plan["top_chunks"] = diverse_rows[:10]
    context["rerank_plan"] = rerank_plan

    synthesis_grounding = context.get("synthesis_grounding") or {}
    synthesis_grounding["grounding_file"] = str(grounding_path)
    synthesis_grounding["grounding_report"] = str(grounding_report_path)
    synthesis_grounding["grounded_findings_count"] = grounding["grounded_findings_count"]
    synthesis_grounding["total_findings"] = grounding["total_findings"]
    synthesis_grounding["citation_candidates_count"] = len(citation_candidates)
    synthesis_grounding.setdefault("status", "implemented_v3")
    synthesis_grounding.setdefault("grounding_policy", "source_diverse_chunk_pool")
    synthesis_grounding.setdefault("max_chunks_per_source", MAX_CHUNKS_PER_SOURCE)
    context["synthesis_grounding"] = synthesis_grounding

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer5_rerank"] = {
            "status": "implemented_v5",
            "scaffold_only": False,
            "retrieval_unit": "evidence_chunks",
            "chunk_count_scored": int(rerank_plan.get("chunk_count_scored") or 0),
            "ranked_target_count": int(rerank_plan.get("ranked_target_count") or 0),
            "official_aware_chunk_rerank": True,
            "target_diversity_guard": True,
            "source_diversity_guard": True,
        }
        existing_layer6 = arch.get("layer6_synthesis_provenance") or {}
        arch["layer6_synthesis_provenance"] = {
            "status": existing_layer6.get("status") or "implemented_v3",
            "scaffold_only": False,
            "grounded_findings_count": grounding["grounded_findings_count"],
            "citation_candidates_count": len(citation_candidates),
            "grounding_policy": existing_layer6.get("grounding_policy") or "source_diverse_chunk_pool",
            **(
                {"citation_diversity_guard": existing_layer6.get("citation_diversity_guard")}
                if "citation_diversity_guard" in existing_layer6 else {}
            ),
            **(
                {"max_per_canonical_doc": existing_layer6.get("max_per_canonical_doc")}
                if "max_per_canonical_doc" in existing_layer6 else {}
            ),
            **(
                {"max_per_repo_family": existing_layer6.get("max_per_repo_family")}
                if "max_per_repo_family" in existing_layer6 else {}
            ),
        }
        context["architecture_layers"] = arch

    if isinstance(provenance, dict):
        provenance["source_diversity_guard"] = {
            "status": "implemented_v1",
            "max_chunks_per_source": MAX_CHUNKS_PER_SOURCE,
            "diverse_pool_size": len(diverse_rows),
            "grounding_candidate_file": str(diverse_path),
        }
        provenance["synthesis_grounding_file"] = str(grounding_path)
        provenance["synthesis_grounding_report"] = str(grounding_report_path)
        provenance["citation_candidates"] = citation_candidates
        _write_json(provenance_path, provenance)

    _write_json(context_path, context)

    rep = _read_json(rerank_report_path, {})
    if isinstance(rep, dict):
        rep["status"] = "implemented_v5"
        rep["grounding_candidate_file"] = str(diverse_path)
        rep["source_diversity_guard"] = True
        rep["max_chunks_per_source_for_grounding"] = MAX_CHUNKS_PER_SOURCE
        _write_json(rerank_report_path, rep)

    step22._update_eval(context, eval_report_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step27.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
