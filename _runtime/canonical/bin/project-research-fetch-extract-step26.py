#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

STEP24_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step24.py")
STEP22_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step22.py")

ROLE_PRIORITY = {
    "official_repo": 5,
    "official_docs": 4,
    "issue_problem": 3,
    "practical_community": 2,
    "regional_community": 2,
    "generic_reference": 1,
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

def _bucket(role: str) -> str:
    role = str(role or "").lower()
    if role in ("official_repo", "official_docs"):
        return "official"
    if role == "issue_problem":
        return "issue"
    if role in ("practical_community", "regional_community"):
        return "community"
    return "generic"

def _build_candidates(reranked_rows: list[dict]) -> list[dict]:
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
        row_role = str(row.get("source_role") or "")
        if row_score > entry["best_score"]:
            entry["best_score"] = row_score
            entry["best_chunk_id"] = row.get("chunk_id")
            entry["source_role"] = row_role
            entry["host"] = row.get("host")
            entry["title"] = row.get("title")
        elif _priority(row_role) > _priority(entry.get("source_role")):
            entry["source_role"] = row_role

        for hit in row.get("focus_hits") or []:
            entry["focus_hits"].add(hit)

    candidates = []
    for entry in source_map.values():
        aggregate_score = round(float(entry["best_score"]) + min(int(entry["supporting_chunks"]), 5) * 0.15, 4)
        candidates.append({
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
    candidates.sort(
        key=lambda x: (
            _priority(x.get("source_role")),
            float(x.get("aggregate_score") or 0.0),
            float(x.get("best_score") or 0.0),
            int(x.get("supporting_chunks") or 0),
        ),
        reverse=True,
    )
    return candidates

def _diverse_select(candidates: list[dict], limit: int = 8) -> list[dict]:
    buckets = {"official": [], "issue": [], "community": [], "generic": []}
    for row in candidates:
        buckets[_bucket(row.get("source_role"))].append(row)

    selected = []
    used = set()

    def take_from(name: str, count: int):
        for row in buckets.get(name, []):
            if len([x for x in selected if x["url"] == row["url"]]) > 0:
                continue
            selected.append(row)
            used.add(row["url"])
            if count <= 1:
                return
            count -= 1

    # guarantee diversity when available
    take_from("official", 2)
    take_from("issue", 1)
    take_from("community", 2)

    # fill the rest by global priority+score
    for row in candidates:
        if row["url"] in used:
            continue
        selected.append(row)
        used.add(row["url"])
        if len(selected) >= limit:
            break

    # final stable sort
    selected.sort(
        key=lambda x: (
            _priority(x.get("source_role")),
            float(x.get("aggregate_score") or 0.0),
            float(x.get("best_score") or 0.0),
            int(x.get("supporting_chunks") or 0),
        ),
        reverse=True,
    )
    return selected[:limit]

def run(artifact_dir: Path) -> int:
    step24 = _load_module(STEP24_HELPER, "project_research_step24_helper")
    step22 = _load_module(STEP22_HELPER, "project_research_step22_helper")

    step24.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    provenance_path = artifact_dir / "provenance.json"
    rerank_path = artifact_dir / "reranked_evidence.jsonl"
    eval_report_path = artifact_dir / "eval_safety_report.json"

    context = _read_json(context_path, {})
    provenance = _read_json(provenance_path, {})
    reranked_rows = _read_jsonl(rerank_path)

    candidates = _build_candidates(reranked_rows)
    ranked_targets = _diverse_select(candidates, limit=8)

    rerank_plan = context.get("rerank_plan") or {}
    rerank_plan["strategy"] = "evidence_chunk_rerank_v4_diverse_targets"
    rerank_plan["official_first_ordering"] = True
    rerank_plan["official_aware_chunk_rerank"] = True
    rerank_plan["target_diversity_guard"] = True
    rerank_plan["ranked_targets"] = ranked_targets
    rerank_plan["ranked_target_count"] = len(ranked_targets)
    context["rerank_plan"] = rerank_plan

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer5_rerank"] = {
            "status": "implemented_v4",
            "scaffold_only": False,
            "retrieval_unit": "evidence_chunks",
            "chunk_count_scored": int(rerank_plan.get("chunk_count_scored") or 0),
            "ranked_target_count": len(ranked_targets),
            "official_aware_chunk_rerank": True,
            "target_diversity_guard": True,
        }
        context["architecture_layers"] = arch

    if isinstance(provenance, dict):
        provenance["target_diversity_guard"] = {
            "status": "implemented_v1",
            "candidate_count": len(candidates),
            "selected_count": len(ranked_targets),
        }
        _write_json(provenance_path, provenance)

    _write_json(context_path, context)
    step22._update_eval(context, eval_report_path)
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step26.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
