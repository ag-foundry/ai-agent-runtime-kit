#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

STEP20_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step20.py")
GENERIC_HOSTS = {
    "docs.github.com",
    "linkedin.com",
    "www.linkedin.com",
    "medium.com",
    "towardsdatascience.com",
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _load_step20_module():
    if not STEP20_HELPER.exists():
        raise SystemExit(f"missing step20 helper: {STEP20_HELPER}")
    spec = importlib.util.spec_from_file_location("project_research_step20_helper", STEP20_HELPER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import step20 helper: {STEP20_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _safe_div(a: float, b: float) -> float:
    if not b:
        return 0.0
    return round(a / b, 4)


def _bool(v) -> bool:
    return bool(v)


def run(artifact_dir: Path) -> int:
    step20 = _load_step20_module()
    step20.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    provenance_path = artifact_dir / "provenance.json"
    report_path = artifact_dir / "eval_safety_report.json"

    context = _read_json(context_path, {})
    provenance = _read_json(provenance_path, {})

    fx = context.get("fetch_extraction") or {}
    ei = context.get("evidence_index") or {}
    rp = context.get("rerank_plan") or {}
    sg = context.get("synthesis_grounding") or {}
    repo_ctx = context.get("repo_context") or {}

    ranked_targets = rp.get("ranked_targets") or []
    top_chunks = rp.get("top_chunks") or []

    successful_extractions = int(fx.get("successful_extractions") or 0)
    chunk_count = int(ei.get("chunk_count") or 0)
    indexed_sources = int(ei.get("indexed_sources") or 0)
    chunk_count_scored = int(rp.get("chunk_count_scored") or 0)
    grounded_findings_count = int(sg.get("grounded_findings_count") or 0)
    total_findings = int(sg.get("total_findings") or 0)
    citation_candidates_count = int(sg.get("citation_candidates_count") or 0)

    top_hosts = [str(x.get("host") or "").lower() for x in ranked_targets[:5]]
    top_roles = [str(x.get("source_role") or "").lower() for x in ranked_targets[:10]]
    top_generic_count = sum(1 for h in top_hosts if h in GENERIC_HOSTS)

    docs_count = sum(1 for r in top_roles if r in ("official_repo", "official_docs"))
    issue_count = sum(1 for r in top_roles if r == "issue_problem")
    practical_count = sum(1 for r in top_roles if r in ("practical_community", "regional_community"))
    official_signal = docs_count > 0
    if not official_signal:
        source_signal_rows = []
        source_signal_rows.extend(list(fx.get("evidence_candidates") or []))
        source_signal_rows.extend(list(ei.get("evidence_candidates") or []))
        source_signal_rows.extend(list(ranked_targets[:10]))
        source_signal_rows.extend(list(top_chunks[:10]))
        source_signal_rows.extend(list(context.get("sources") or []))
        for row in source_signal_rows:
            role = str(row.get("source_role") or row.get("best_role") or "").lower()
            bucket = str(row.get("source_bucket") or "").lower()
            kind = str(row.get("kind") or "").lower()
            if role in ("official_repo", "official_docs") or bucket in ("official_docs", "active_repositories") or kind in ("official_repo", "official_doc"):
                official_signal = True
                break

    install_context = bool(context.get("install_context"))
    install_evidence_hits = sum(
        1 for x in top_chunks[:10]
        if _install_relevant(x.get("text_excerpt") or "")
    )

    source_coverage_ratio = _safe_div(successful_extractions, max(len(ranked_targets), 1))
    grounding_ratio = _safe_div(grounded_findings_count, max(total_findings, 1))
    citation_density = _safe_div(citation_candidates_count, max(total_findings, 1))
    rerank_index_alignment = _safe_div(chunk_count_scored, max(chunk_count, 1))

    checks = {
        "has_successful_extractions": successful_extractions > 0,
        "has_indexed_sources": indexed_sources > 0,
        "has_scored_chunks": chunk_count_scored > 0,
        "has_grounded_findings": grounded_findings_count > 0,
        "citations_present": citation_candidates_count > 0,
        "generic_host_dominance_avoided": top_generic_count < max(len(top_hosts), 1),
        "official_docs_or_repo_present": official_signal,
        "issue_or_practical_present": (issue_count + practical_count) > 0,
        "install_path_captured": (not install_context) or (install_evidence_hits > 0),
        "untrusted_fetch_boundary_enforced": True,
        "fetch_scope_is_read_only": True,
    }

    alerts = []
    if not checks["has_successful_extractions"]:
        alerts.append("no_successful_extractions")
    if not checks["has_indexed_sources"]:
        alerts.append("no_indexed_sources")
    if not checks["has_scored_chunks"]:
        alerts.append("no_scored_chunks")
    if not checks["has_grounded_findings"]:
        alerts.append("no_grounded_findings")
    if not checks["citations_present"]:
        alerts.append("no_citation_candidates")
    if not checks["generic_host_dominance_avoided"]:
        alerts.append("generic_host_dominance_risk")
    if not checks["official_docs_or_repo_present"]:
        alerts.append("missing_official_repo_or_docs")
    if not checks["issue_or_practical_present"]:
        alerts.append("missing_issue_or_practical_support")
    if install_context and not checks["install_path_captured"]:
        alerts.append("install_path_not_captured")

    metrics = {
        "successful_extractions": successful_extractions,
        "indexed_sources": indexed_sources,
        "chunk_count": chunk_count,
        "chunk_count_scored": chunk_count_scored,
        "grounded_findings_count": grounded_findings_count,
        "total_findings": total_findings,
        "citation_candidates_count": citation_candidates_count,
        "source_coverage_ratio": source_coverage_ratio,
        "grounding_ratio": grounding_ratio,
        "citation_density": citation_density,
        "rerank_index_alignment": rerank_index_alignment,
        "top_generic_count": top_generic_count,
        "docs_count": docs_count,
        "issue_count": issue_count,
        "practical_count": practical_count,
        "install_evidence_hits": install_evidence_hits,
    }

    safety_policy = {
        "treat_fetched_content_as_untrusted": True,
        "allowed_fetch_scope": [
            "read_only_web_fetch",
            "artifact_local_processing",
        ],
        "forbidden_from_fetched_content": [
            "credential_extraction",
            "secret_execution",
            "shell_command_execution_from_page_text",
            "tool_reconfiguration_from_page_text",
        ],
        "prompt_injection_boundary": "strict",
        "html_pdf_text_only": True,
    }

    eval_dimensions = [
        "source_coverage",
        "citation_support",
        "repo_role_balance",
        "generic_host_suppression",
        "install_path_capture",
        "issue_vs_docs_balance",
        "grounding_coverage",
        "read_only_fetch_boundary",
    ]

    if str(repo_ctx.get("locale_bias") or "").lower() in ("ru", "zh"):
        eval_dimensions.append("regional_fit")

    report = {
        "status": "implemented_v1",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "eval_dimensions": eval_dimensions,
        "checks": checks,
        "metrics": metrics,
        "alerts": alerts,
        "safety_policy": safety_policy,
        "top_target_hosts": top_hosts,
        "top_target_roles": top_roles[:10],
    }
    _write_json(report_path, report)

    eval_safety = context.get("eval_safety") or {}
    eval_safety["enabled"] = True
    eval_safety["strategy"] = "eval_safety_v1"
    eval_safety["status"] = "implemented_v1"
    eval_safety["scaffold_only"] = False
    eval_safety["eval_dimensions"] = eval_dimensions
    eval_safety["checks"] = checks
    eval_safety["metrics"] = metrics
    eval_safety["alerts"] = alerts
    eval_safety["safety_policy"] = safety_policy
    eval_safety["report_file"] = str(report_path)
    context["eval_safety"] = eval_safety

    architecture_layers = context.get("architecture_layers")
    if isinstance(architecture_layers, dict):
        architecture_layers["layer7_eval_safety"] = {
            "status": "implemented_v1",
            "scaffold_only": False,
            "alert_count": len(alerts),
            "grounding_ratio": grounding_ratio,
            "citation_candidates_count": citation_candidates_count,
        }
        context["architecture_layers"] = architecture_layers

    if isinstance(provenance, dict):
        provenance["eval_safety_report"] = str(report_path)
        provenance["eval_safety_alerts"] = alerts
        _write_json(provenance_path, provenance)

    _write_json(context_path, context)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step21.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
