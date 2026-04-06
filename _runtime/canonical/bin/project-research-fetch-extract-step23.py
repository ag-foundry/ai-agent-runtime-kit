#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

STEP22_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step22.py")

ROLE_PRIORITY = {
    "official_repo": 4,
    "official_docs": 3,
    "issue_problem": 2,
    "practical_community": 1,
    "regional_community": 1,
    "generic_reference": 0,
}

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")

def _load_step22_module():
    if not STEP22_HELPER.exists():
        raise SystemExit(f"missing step22 helper: {STEP22_HELPER}")
    spec = importlib.util.spec_from_file_location("project_research_step22_helper", STEP22_HELPER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import step22 helper: {STEP22_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _priority(role: str) -> int:
    return ROLE_PRIORITY.get(str(role or "").lower(), 0)

def run(artifact_dir: Path) -> int:
    step22 = _load_step22_module()
    step22.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    eval_report_path = artifact_dir / "eval_safety_report.json"

    context = _read_json(context_path, {})
    rerank_plan = context.get("rerank_plan") or {}
    ranked_targets = rerank_plan.get("ranked_targets") or []

    ranked_targets.sort(
        key=lambda x: (
            _priority(x.get("source_role")),
            float(x.get("aggregate_score") or 0.0),
            float(x.get("best_score") or 0.0),
            int(x.get("supporting_chunks") or 0),
        ),
        reverse=True,
    )

    rerank_plan["strategy"] = "evidence_chunk_rerank_v2_official_first"
    rerank_plan["ranked_targets"] = ranked_targets
    rerank_plan["official_first_ordering"] = True
    context["rerank_plan"] = rerank_plan

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer5_rerank"] = {
            "status": "implemented_v2",
            "scaffold_only": False,
            "retrieval_unit": "evidence_chunks",
            "chunk_count_scored": int(rerank_plan.get("chunk_count_scored") or 0),
            "ranked_target_count": len(ranked_targets),
            "official_first_ordering": True,
        }
        context["architecture_layers"] = arch

    _write_json(context_path, context)

    rep = _read_json(eval_report_path, {})
    if isinstance(rep, dict):
        rep["ranking_policy"] = "official_first_after_role_normalization"
        rep["top_target_roles"] = [str(x.get("source_role") or "").lower() for x in ranked_targets[:10]]
        rep["top_target_hosts"] = [str(x.get("host") or "").lower() for x in ranked_targets[:10]]
        _write_json(eval_report_path, rep)

    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step23.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
