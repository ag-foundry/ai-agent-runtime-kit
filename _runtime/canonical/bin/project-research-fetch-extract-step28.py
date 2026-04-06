#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

STEP27_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step27.py")
STEP22_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step22.py")
STEP19_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step19.py")

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


def _balanced_top_chunks(rows: list[dict], limit: int = 10) -> list[dict]:
    official = []
    issue = []
    community = []
    generic = []

    for row in rows:
        role = str(row.get("source_role") or "").lower()
        if role in ("official_repo", "official_docs"):
            official.append(row)
        elif role == "issue_problem":
            issue.append(row)
        elif role in ("practical_community", "regional_community"):
            community.append(row)
        else:
            generic.append(row)

    selected = []
    used = set()

    def take(bucket, n):
        taken = 0
        for row in bucket:
            key = row.get("chunk_id")
            if key in used:
                continue
            selected.append(row)
            used.add(key)
            taken += 1
            if taken >= n:
                break

    take(official, 3)
    take(issue, 1)
    take(community, 4)

    for row in rows:
        key = row.get("chunk_id")
        if key in used:
            continue
        selected.append(row)
        used.add(key)
        if len(selected) >= limit:
            break

    selected.sort(
        key=lambda x: (
            _priority(x.get("source_role")),
            float(x.get("score") or 0.0),
        ),
        reverse=True,
    )
    return selected[:limit]


def run(artifact_dir: Path) -> int:
    step19 = _load_module(STEP19_HELPER, "project_research_step19_helper")
    step27 = _load_module(STEP27_HELPER, "project_research_step27_helper")
    step22 = _load_module(STEP22_HELPER, "project_research_step22_helper")

    # Сначала обязательно прогоняем реальный rerank writer из step19,
    # чтобы ranked_targets в context уже были с полной metadata.
    step19.run(artifact_dir)
    step27.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    eval_report_path = artifact_dir / "eval_safety_report.json"
    diverse_path = artifact_dir / "reranked_evidence_diverse.jsonl"

    context = _read_json(context_path, {})
    diverse_rows = _read_jsonl(diverse_path)

    rerank_plan = context.get("rerank_plan") or {}
    rerank_plan["strategy"] = "evidence_chunk_rerank_v6_official_balanced_topchunks"
    rerank_plan["top_chunks"] = _balanced_top_chunks(diverse_rows, limit=10)
    rerank_plan["official_balanced_topchunks"] = True
    context["rerank_plan"] = rerank_plan

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer5_rerank"] = {
            "status": "implemented_v6",
            "scaffold_only": False,
            "retrieval_unit": "evidence_chunks",
            "chunk_count_scored": int(rerank_plan.get("chunk_count_scored") or 0),
            "ranked_target_count": int(rerank_plan.get("ranked_target_count") or 0),
            "official_aware_chunk_rerank": True,
            "target_diversity_guard": True,
            "source_diversity_guard": True,
            "official_balanced_topchunks": True,
        }
        context["architecture_layers"] = arch

    _write_json(context_path, context)
    step22._update_eval(context, eval_report_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step28.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
