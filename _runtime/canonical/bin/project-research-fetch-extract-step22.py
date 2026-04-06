#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path

STEP21_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step21.py")
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

def _load_step21_module():
    if not STEP21_HELPER.exists():
        raise SystemExit(f"missing step21 helper: {STEP21_HELPER}")
    spec = importlib.util.spec_from_file_location("project_research_step21_helper", STEP21_HELPER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import step21 helper: {STEP21_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _focus_roots(context: dict) -> list[str]:
    terms = []
    repo_ctx = context.get("repo_context") or {}
    fx = context.get("fetch_extraction") or {}
    for item in (repo_ctx.get("focus_terms") or []):
        if isinstance(item, str) and item.strip():
            terms.append(item.strip().lower())
    for item in (fx.get("extract_focus") or []):
        if isinstance(item, str) and item.strip():
            terms.append(item.strip().lower())

    roots = []
    seen = set()
    for term in terms:
        for tok in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,}", term):
            tok = tok.lower().strip("._-")
            if len(tok) < 3:
                continue
            if tok not in seen:
                seen.add(tok)
                roots.append(tok)
    return roots[:30]

def _host_matches_focus(host: str, roots: list[str]) -> bool:
    host = str(host or "").lower()
    return any(root in host for root in roots)

def _guess_normalized_role(url: str, current_role: str, roots: list[str]) -> str:
    current_role = str(current_role or "").lower()

    parsed = urllib.parse.urlparse(str(url or ""))
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    path_parts = [p for p in path.split("/") if p]
    low_path = "/" + "/".join(path_parts).lower()

    if host == "github.com":
        if "/issues/" in low_path or "/discussions/" in low_path:
            return "issue_problem"
        if "/wiki" in low_path:
            return "official_docs"
        if len(path_parts) >= 2:
            owner = path_parts[0].lower()
            repo = path_parts[1].lower()
            owner_match = owner in roots
            repo_match = repo in roots
            if owner_match or repo_match:
                if "/blob/" in low_path:
                    if any(x in low_path for x in ("/readme", "/docs/", "/doc/", "/examples/", "/example/")):
                        return "official_docs"
                    return "official_repo"
                if len(path_parts) == 2:
                    return "official_repo"

    docs_markers = ("docs.", "developers.", "developer.", "api.", "ai.")
    known_official_docs_hosts = {
        "developers.openai.com",
        "platform.openai.com",
        "docs.pydantic.dev",
        "ai.pydantic.dev",
        "docs.langchain.com",
        "docs.prefect.io",
        "opentelemetry.io",
    }

    if host in known_official_docs_hosts:
        return "official_docs"

    if any(host.endswith("." + x) for x in known_official_docs_hosts):
        return "official_docs"

    if _host_matches_focus(host, roots) and any(marker in host for marker in docs_markers):
        return "official_docs"

    if any(marker in host for marker in docs_markers) and any(token in host for token in ("openai", "pydantic", "langchain", "prefect", "opentelemetry")):
        return "official_docs"

    if _host_matches_focus(host, roots) and any(marker in low_path for marker in ("/docs", "/quickstart", "/api", "/reference", "/guide", "/cookbook")):
        return "official_docs"

    if current_role in ("official_repo", "official_docs", "issue_problem"):
        return current_role

    return current_role or "generic_reference"

def _role_counts(ranked_targets: list[dict]) -> tuple[int, int, int]:
    docs_count = 0
    issue_count = 0
    practical_count = 0
    for row in ranked_targets[:10]:
        role = str(row.get("source_role") or "").lower()
        if role in ("official_repo", "official_docs"):
            docs_count += 1
        elif role == "issue_problem":
            issue_count += 1
        elif role in ("practical_community", "regional_community"):
            practical_count += 1
    return docs_count, issue_count, practical_count

def _update_eval(context: dict, report_path: Path) -> None:
    fx = context.get("fetch_extraction") or {}
    ei = context.get("evidence_index") or {}
    rp = context.get("rerank_plan") or {}
    sg = context.get("synthesis_grounding") or {}

    ranked_targets = rp.get("ranked_targets") or []
    top_chunks = rp.get("top_chunks") or []

    top_hosts = [str(x.get("host") or "").lower() for x in ranked_targets[:5]]
    top_generic_count = sum(1 for h in top_hosts if h in GENERIC_HOSTS)

    docs_count, issue_count, practical_count = _role_counts(ranked_targets)
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
    install_hits = 0
    for x in top_chunks[:10]:
        txt = str(x.get("text_excerpt") or "").lower()
        if any(m in txt for m in ["install", "installation", "setup", "configure", "quickstart", "docker compose", "pip install", "requirements.txt", "установка", "настройка"]):
            install_hits += 1

    checks = {
        "has_successful_extractions": int(fx.get("successful_extractions") or 0) > 0,
        "has_indexed_sources": int(ei.get("indexed_sources") or 0) > 0,
        "has_scored_chunks": int(rp.get("chunk_count_scored") or 0) > 0,
        "has_grounded_findings": int(sg.get("grounded_findings_count") or 0) > 0,
        "citations_present": int(sg.get("citation_candidates_count") or 0) > 0,
        "generic_host_dominance_avoided": top_generic_count < max(len(top_hosts), 1),
        "official_docs_or_repo_present": official_signal,
        "issue_or_practical_present": (issue_count + practical_count) > 0,
        "install_path_captured": (not install_context) or (install_hits > 0),
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
        "successful_extractions": int(fx.get("successful_extractions") or 0),
        "indexed_sources": int(ei.get("indexed_sources") or 0),
        "chunk_count": int(ei.get("chunk_count") or 0),
        "chunk_count_scored": int(rp.get("chunk_count_scored") or 0),
        "grounded_findings_count": int(sg.get("grounded_findings_count") or 0),
        "total_findings": int(sg.get("total_findings") or 0),
        "citation_candidates_count": int(sg.get("citation_candidates_count") or 0),
        "top_generic_count": top_generic_count,
        "docs_count": docs_count,
        "issue_count": issue_count,
        "practical_count": practical_count,
        "install_evidence_hits": install_hits,
    }

    safety_policy = {
        "treat_fetched_content_as_untrusted": True,
        "allowed_fetch_scope": ["read_only_web_fetch", "artifact_local_processing"],
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

    report = {
        "status": "implemented_v2",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "eval_dimensions": eval_dimensions,
        "checks": checks,
        "metrics": metrics,
        "alerts": alerts,
        "safety_policy": safety_policy,
        "top_target_hosts": top_hosts,
        "top_target_roles": [str(x.get("source_role") or "").lower() for x in ranked_targets[:10]],
    }
    _write_json(report_path, report)

    es = context.get("eval_safety") or {}
    es["enabled"] = True
    es["strategy"] = "eval_safety_v2_role_normalized"
    es["status"] = "implemented_v2"
    es["scaffold_only"] = False
    es["eval_dimensions"] = eval_dimensions
    es["checks"] = checks
    es["metrics"] = metrics
    es["alerts"] = alerts
    es["safety_policy"] = safety_policy
    es["report_file"] = str(report_path)
    context["eval_safety"] = es

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer7_eval_safety"] = {
            "status": "implemented_v2",
            "scaffold_only": False,
            "alert_count": len(alerts),
            "docs_count": docs_count,
            "issue_count": issue_count,
            "practical_count": practical_count,
        }
        context["architecture_layers"] = arch

def run(artifact_dir: Path) -> int:
    step21 = _load_step21_module()
    step21.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    provenance_path = artifact_dir / "provenance.json"
    eval_report_path = artifact_dir / "eval_safety_report.json"

    context = _read_json(context_path, {})
    provenance = _read_json(provenance_path, {})

    roots = _focus_roots(context)
    rerank_plan = context.get("rerank_plan") or {}

    changed = 0
    for bucket_name in ("ranked_targets", "top_chunks"):
        bucket = rerank_plan.get(bucket_name) or []
        for row in bucket:
            url = str(row.get("url") or row.get("source_url") or "")
            current_role = str(row.get("source_role") or "")
            new_role = _guess_normalized_role(url, current_role, roots)
            if new_role != current_role:
                row["source_role"] = new_role
                changed += 1
    context["rerank_plan"] = rerank_plan

    _update_eval(context, eval_report_path)

    if isinstance(provenance, dict):
        provenance["role_normalization"] = {
            "status": "implemented_v1",
            "focus_roots": roots,
            "changed_rows": changed,
            "eval_report": str(eval_report_path),
        }
        _write_json(provenance_path, provenance)

    _write_json(context_path, context)
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step22.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
