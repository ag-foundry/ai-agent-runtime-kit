#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path

STEP18_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step18.py")

ROLE_WEIGHTS = {
    "official_repo": 2.2,
    "official_docs": 2.0,
    "issue_problem": 1.5,
    "practical_community": 1.2,
    "regional_community": 1.0,
    "generic_reference": 0.4,
}

GENERIC_HOST_PENALTIES = {
    "docs.github.com": -1.3,
    "linkedin.com": -1.0,
    "www.linkedin.com": -1.0,
    "medium.com": -0.8,
    "towardsdatascience.com": -0.8,
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


def _load_step18_module():
    if not STEP18_HELPER.exists():
        raise SystemExit(f"missing step18 helper: {STEP18_HELPER}")
    spec = importlib.util.spec_from_file_location("project_research_step18_helper", STEP18_HELPER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import step18 helper: {STEP18_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_focus_terms(context: dict) -> list[str]:
    terms = []
    fx = context.get("fetch_extraction") or {}
    for item in (fx.get("extract_focus") or []):
        if isinstance(item, str) and item.strip():
            terms.append(item.strip())
    repo_ctx = context.get("repo_context") or {}
    for item in (repo_ctx.get("focus_terms") or []):
        if isinstance(item, str) and item.strip():
            terms.append(item.strip())
    out = []
    seen = set()
    for term in terms:
        low = term.lower()
        if low not in seen:
            seen.add(low)
            out.append(term)
    return out[:20]


def _install_relevant(text: str) -> bool:
    low = str(text or "").lower()
    markers = [
        "install",
        "installation",
        "setup",
        "configure",
        "configuration",
        "quickstart",
        "getting started",
        "docker compose",
        "docker-compose",
        ".env",
        "readme",
        "requirements.txt",
        "pip install",
        "uv add",
        "poetry add",
        "npm install",
        "make install",
        "usage",
        "run the app",
        "after install",
        "после установки",
        "установка",
        "настройка",
        "настроить",
        "конфиг",
        "порт",
        "путь",
    ]
    return any(m in low for m in markers)


def _host_penalty(host: str) -> float:
    host = str(host or "").lower()
    for key, penalty in GENERIC_HOST_PENALTIES.items():
        if host == key or host.endswith("." + key):
            return penalty
    return 0.0


def _role(value) -> str:
    role = str(value or "").strip().lower()
    return role or "generic_reference"


def _infer_bucket_from_role(role: str) -> str:
    role = _role(role)
    if role == "issue_problem":
        return "issue_problem_sources"
    if role == "official_docs":
        return "official_docs"
    if role == "official_repo":
        return "active_repositories"
    if role in ("practical_community", "regional_community"):
        return "similar_solutions"
    return "similar_solutions"


def _infer_kind_from_role(role: str) -> str:
    role = _role(role)
    if role == "official_docs":
        return "official_doc"
    if role == "official_repo":
        return "official_repo"
    if role == "issue_problem":
        return "issue_problem"
    if role in ("practical_community", "regional_community"):
        return "community_doc"
    return "external_search"


def _normalize_repo_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url or ""))
    host = parsed.netloc.lower()
    if host != "github.com":
        return ""
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return ""
    return f"https://github.com/{parts[0].lower()}/{parts[1].lower()}"


def _repo_family_id_from_url(url: str) -> str:
    normalized = _normalize_repo_url(url)
    if normalized:
        return normalized
    parsed = urllib.parse.urlparse(str(url or ""))
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    if not host:
        return ""
    if path:
        return f"{host}/{path.split('/')[0].lower()}"
    return host


def _score_chunk(chunk: dict, focus_terms: list[str], install_context: bool) -> tuple[float, dict]:
    text = str(chunk.get("text") or "")
    low = text.lower()
    title = str(chunk.get("title") or "")
    low_title = title.lower()
    host = str(chunk.get("host") or "")
    role = _role(chunk.get("source_role"))
    focus_hits = chunk.get("focus_hits") or []

    occurrence_count = 0
    title_hits = 0
    for term in focus_terms[:12]:
        lt = term.lower()
        occurrence_count += low.count(lt)
        if lt in low_title:
            title_hits += 1

    focus_hit_count = len(focus_hits)
    role_bonus = ROLE_WEIGHTS.get(role, 0.0)
    install_bonus = 1.3 if install_context and _install_relevant(text) else 0.0
    generic_penalty = _host_penalty(host)
    title_bonus = 0.5 * min(title_hits, 3)
    short_penalty = -0.4 if len(text.strip()) < 200 else 0.0

    score = (
        occurrence_count * 0.8
        + focus_hit_count * 1.1
        + role_bonus
        + install_bonus
        + title_bonus
        + generic_penalty
        + short_penalty
    )

    details = {
        "occurrence_count": occurrence_count,
        "focus_hit_count": focus_hit_count,
        "role_bonus": role_bonus,
        "install_bonus": install_bonus,
        "title_bonus": title_bonus,
        "generic_penalty": generic_penalty,
        "short_penalty": short_penalty,
    }
    return round(score, 4), details


def _build_rerank(artifact_dir: Path, context: dict) -> tuple[Path, Path, int, list[dict], list[dict]]:
    evidence_rows = _read_jsonl(artifact_dir / "evidence_index.jsonl")
    focus_terms = _load_focus_terms(context)
    install_context = bool(context.get("install_context"))

    scored_chunks = []
    for row in evidence_rows:
        score, details = _score_chunk(row, focus_terms, install_context)

        source_url = str(row.get("source_url") or "")
        fetch_url = str(row.get("fetch_url") or "")
        title = row.get("title")
        source_title = row.get("source_title") or title
        source_role = _role(row.get("source_role"))
        host = row.get("host")
        source_bucket = str(row.get("source_bucket") or _infer_bucket_from_role(source_role))
        kind = str(row.get("kind") or _infer_kind_from_role(source_role))
        canonical_doc_id = str(row.get("canonical_doc_id") or source_url or source_title or "")
        normalized_repo_url = str(row.get("normalized_repo_url") or _normalize_repo_url(source_url or fetch_url))
        repo_url = str(row.get("repo_url") or normalized_repo_url)
        repo_family_id = str(row.get("repo_family_id") or _repo_family_id_from_url(repo_url or source_url or fetch_url))
        why_extract = row.get("why_extract")
        fetch_method = row.get("fetch_method")

        scored_chunks.append({
            "chunk_id": row.get("chunk_id"),
            "evidence_id": row.get("evidence_id"),
            "source_url": source_url,
            "fetch_url": fetch_url,
            "title": title,
            "source_title": source_title,
            "source_role": source_role,
            "source_bucket": source_bucket,
            "kind": kind,
            "canonical_doc_id": canonical_doc_id,
            "repo_family_id": repo_family_id,
            "normalized_repo_url": normalized_repo_url,
            "repo_url": repo_url,
            "why_extract": why_extract,
            "fetch_method": fetch_method,
            "host": host,
            "score": score,
            "score_details": details,
            "focus_hits": row.get("focus_hits") or [],
            "start_char": row.get("start_char"),
            "end_char": row.get("end_char"),
            "text_excerpt": str(row.get("text") or "")[:500],
        })

    scored_chunks.sort(
        key=lambda x: (
            x.get("score", 0),
            len(x.get("focus_hits") or []),
            1 if _role(x.get("source_role")) in ("official_repo", "official_docs") else 0,
        ),
        reverse=True,
    )

    ranked_chunks_path = artifact_dir / "reranked_evidence.jsonl"
    _jsonl_write(ranked_chunks_path, scored_chunks)

    source_map = {}
    for row in scored_chunks:
        url = str(row.get("source_url") or "")
        if not url:
            continue
        entry = source_map.setdefault(url, {
            "url": url,
            "title": row.get("title"),
            "source_title": row.get("source_title"),
            "source_role": row.get("source_role"),
            "source_bucket": row.get("source_bucket"),
            "kind": row.get("kind"),
            "canonical_doc_id": row.get("canonical_doc_id"),
            "repo_family_id": row.get("repo_family_id"),
            "normalized_repo_url": row.get("normalized_repo_url"),
            "repo_url": row.get("repo_url"),
            "why_extract": row.get("why_extract"),
            "fetch_method": row.get("fetch_method"),
            "host": row.get("host"),
            "best_score": row.get("score", 0),
            "best_chunk_id": row.get("chunk_id"),
            "supporting_chunks": 0,
            "focus_hits": set(),
        })
        entry["supporting_chunks"] += 1
        if row.get("score", 0) > entry["best_score"]:
            entry["best_score"] = row.get("score", 0)
            entry["best_chunk_id"] = row.get("chunk_id")
            entry["title"] = row.get("title")
            entry["source_title"] = row.get("source_title")
            entry["source_role"] = row.get("source_role")
            entry["source_bucket"] = row.get("source_bucket")
            entry["kind"] = row.get("kind")
            entry["canonical_doc_id"] = row.get("canonical_doc_id")
            entry["repo_family_id"] = row.get("repo_family_id")
            entry["normalized_repo_url"] = row.get("normalized_repo_url")
            entry["repo_url"] = row.get("repo_url")
            entry["why_extract"] = row.get("why_extract")
            entry["fetch_method"] = row.get("fetch_method")
            entry["host"] = row.get("host")
        for hit in row.get("focus_hits") or []:
            entry["focus_hits"].add(hit)

    ranked_targets = []
    for entry in source_map.values():
        aggregate_score = round(
            float(entry["best_score"]) + min(int(entry["supporting_chunks"]), 5) * 0.15,
            4,
        )
        ranked_targets.append({
            "url": entry["url"],
            "title": entry["title"],
            "source_title": entry["source_title"],
            "source_role": entry["source_role"],
            "source_bucket": entry["source_bucket"],
            "kind": entry["kind"],
            "canonical_doc_id": entry["canonical_doc_id"],
            "repo_family_id": entry["repo_family_id"],
            "normalized_repo_url": entry["normalized_repo_url"],
            "repo_url": entry["repo_url"],
            "why_extract": entry["why_extract"],
            "fetch_method": entry["fetch_method"],
            "host": entry["host"],
            "aggregate_score": aggregate_score,
            "best_score": entry["best_score"],
            "best_chunk_id": entry["best_chunk_id"],
            "supporting_chunks": entry["supporting_chunks"],
            "focus_hits": sorted(entry["focus_hits"])[:8],
        })

    ranked_targets.sort(
        key=lambda x: (x.get("aggregate_score", 0), x.get("best_score", 0), x.get("supporting_chunks", 0)),
        reverse=True,
    )

    report_path = artifact_dir / "rerank_report.json"
    report = {
        "status": "implemented_v1",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "retrieval_unit": "evidence_chunks",
        "chunk_count_scored": len(scored_chunks),
        "ranked_target_count": len(ranked_targets),
        "weights": {
            "term_occurrences": 0.8,
            "focus_hits": 1.1,
            "role_bonus": "per-role",
            "install_bonus": 1.3,
            "title_bonus": 0.5,
            "generic_host_penalty": "per-host",
            "short_chunk_penalty": -0.4,
        },
        "criteria": [
            "focus_term_density",
            "source_role_priority",
            "install_relevance",
            "generic_host_suppression",
            "title_alignment",
        ],
        "top_chunk_ids": [x.get("chunk_id") for x in scored_chunks[:10]],
        "top_target_urls": [x.get("url") for x in ranked_targets[:10]],
    }
    _write_json(report_path, report)
    return ranked_chunks_path, report_path, len(scored_chunks), scored_chunks[:10], ranked_targets[:10]


def run(artifact_dir: Path) -> int:
    step18 = _load_step18_module()
    step18.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    context = _read_json(context_path, {})
    if not context:
        return 0

    ranked_chunks_path, report_path, chunk_count_scored, top_chunks, ranked_targets = _build_rerank(
        artifact_dir=artifact_dir,
        context=context,
    )

    rerank_plan = context.get("rerank_plan") or {}
    rerank_plan["enabled"] = True
    rerank_plan["strategy"] = "evidence_chunk_rerank_v1"
    rerank_plan["status"] = "implemented_v1"
    rerank_plan["scaffold_only"] = False
    rerank_plan["retrieval_unit"] = "evidence_chunks"
    rerank_plan["weights"] = {
        "term_occurrences": 0.8,
        "focus_hits": 1.1,
        "role_bonus": "per-role",
        "install_bonus": 1.3,
        "title_bonus": 0.5,
        "generic_host_penalty": "per-host",
        "short_chunk_penalty": -0.4,
    }
    rerank_plan["criteria"] = [
        "focus_term_density",
        "source_role_priority",
        "install_relevance",
        "generic_host_suppression",
        "title_alignment",
    ]
    rerank_plan["ranked_targets"] = ranked_targets
    rerank_plan["top_chunks"] = top_chunks
    rerank_plan["ranked_chunks_file"] = str(ranked_chunks_path)
    rerank_plan["rerank_report"] = str(report_path)
    rerank_plan["chunk_count_scored"] = chunk_count_scored
    context["rerank_plan"] = rerank_plan

    architecture_layers = context.get("architecture_layers")
    if isinstance(architecture_layers, dict):
        architecture_layers["layer5_rerank"] = {
            "status": "implemented_v1",
            "scaffold_only": False,
            "retrieval_unit": "evidence_chunks",
            "chunk_count_scored": chunk_count_scored,
            "ranked_target_count": len(ranked_targets),
        }
        context["architecture_layers"] = architecture_layers

    _write_json(context_path, context)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step19.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))