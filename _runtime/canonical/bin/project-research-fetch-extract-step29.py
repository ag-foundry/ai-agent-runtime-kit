#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

STEP28_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step28.py")
STEP22_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step22.py")

MAX_SUPPORTS_PER_FINDING = 3
MAX_GLOBAL_CITATIONS = 8
MAX_GLOBAL_PER_SOURCE = 1  # backward-compatible metadata
MAX_PER_CANONICAL_DOC = 1
MAX_PER_REPO_FAMILY = 2

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


def _role(value: str) -> str:
    return str(value or "").strip().lower()


def _priority(role: str) -> int:
    return ROLE_PRIORITY.get(_role(role), 0)


def _score(row: dict) -> float:
    try:
        return float(row.get("support_score") or row.get("score") or 0.0)
    except Exception:
        return 0.0


def _canonical_source_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except Exception:
        return text
    scheme = (parts.scheme or "https").lower()
    host = (parts.netloc or "").lower()
    path = (parts.path or "").rstrip("/")
    if not path:
        path = "/"
    return urlunsplit((scheme, host, path, "", ""))


def _repo_family_id_from_url(url: str) -> str:
    canon = _canonical_source_url(url)
    if not canon:
        return ""
    parts = urlsplit(canon)
    host = (parts.netloc or "").lower()
    seg = [x for x in (parts.path or "").split("/") if x]

    if host == "github.com" and len(seg) >= 2:
        return f"github.com/{seg[0].lower()}/{seg[1].lower()}"

    if host in ("raw.githubusercontent.com", "githubusercontent.com") and len(seg) >= 2:
        return f"githubusercontent/{seg[0].lower()}/{seg[1].lower()}"

    return host


def _chunk_key(row: dict) -> str:
    chunk_id = str(row.get("chunk_id") or "").strip()
    if chunk_id:
        return chunk_id
    url = str(row.get("source_url") or row.get("url") or "").strip()
    title = str(row.get("title") or "").strip()
    return f"{url}|{title}"


def _infer_bucket_from_role(role: str) -> str:
    role = _role(role)
    if role == "official_repo":
        return "active_repositories"
    if role == "official_docs":
        return "official_docs"
    if role == "issue_problem":
        return "issue_problem_sources"
    if role in ("practical_community", "regional_community"):
        return "similar_solutions"
    return "similar_solutions"


def _infer_kind_from_role(role: str) -> str:
    role = _role(role)
    if role == "official_repo":
        return "official_repo"
    if role == "official_docs":
        return "official_doc"
    if role == "issue_problem":
        return "issue_problem"
    if role in ("practical_community", "regional_community"):
        return "community_doc"
    return "reference_doc"


def _candidate_row(item: dict, finding_id: str) -> dict:
    url = _canonical_source_url(item.get("source_url") or item.get("url") or "")
    title = str(item.get("title") or item.get("source_title") or url or "source").strip()
    role = _role(item.get("source_role") or item.get("role") or "generic_reference")

    row = dict(item)
    row["finding_id"] = finding_id
    row["url"] = url
    row["source_url"] = url
    row["title"] = title
    row["source_role"] = role
    row["support_score"] = round(_score(item), 4)
    row["source_bucket"] = str(item.get("source_bucket") or _infer_bucket_from_role(role))
    row["kind"] = str(item.get("kind") or _infer_kind_from_role(role))
    row["canonical_doc_id"] = str(item.get("canonical_doc_id") or url or title)
    row["repo_family_id"] = str(item.get("repo_family_id") or _repo_family_id_from_url(url))
    return row


def _is_official(row: dict) -> bool:
    return _role(row.get("source_role")) in ("official_repo", "official_docs")


def _is_issue(row: dict) -> bool:
    return _role(row.get("source_role")) == "issue_problem"


def _is_community(row: dict) -> bool:
    return _role(row.get("source_role")) in ("practical_community", "regional_community")


def _sorted_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda x: (
            _priority(x.get("source_role")),
            _score(x),
            str(x.get("title") or ""),
            str(x.get("source_url") or x.get("url") or ""),
        ),
        reverse=True,
    )


def _try_take(
    row: dict,
    selected: list[dict],
    used_chunks: set[str],
    doc_counts: dict[str, int],
    family_counts: dict[str, int],
) -> bool:
    key = _chunk_key(row)
    if not key or key in used_chunks:
        return False

    doc_id = str(row.get("canonical_doc_id") or "")
    family_id = str(row.get("repo_family_id") or "")

    if doc_id and doc_counts.get(doc_id, 0) >= MAX_PER_CANONICAL_DOC:
        return False

    if family_id and family_counts.get(family_id, 0) >= MAX_PER_REPO_FAMILY:
        return False

    selected.append(row)
    used_chunks.add(key)

    if doc_id:
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
    if family_id:
        family_counts[family_id] = family_counts.get(family_id, 0) + 1
    return True


def _uniq(seq: list[str]) -> list[str]:
    out = []
    seen = set()
    for x in seq:
        x = str(x or "").strip().lower()
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _finding_target_profile(finding: dict | None) -> dict:
    finding = finding or {}
    finding_id = str(finding.get("finding_id") or finding.get("id") or "").lower()
    claim_text = str(finding.get("claim_text") or "").strip()
    claim_l = claim_text.lower()

    preferred_roles: list[str] = []
    preferred_buckets: list[str] = []
    preferred_kinds: list[str] = []
    prefer_title = ""
    prefer_url = ""
    strict_title_first = False
    strict_community_first = False

    if claim_text.startswith("Curated source selected:"):
        source_name = claim_text.split("Curated source selected:", 1)[1].strip().rstrip(".")
        prefer_title = source_name.lower()
        strict_title_first = True

    if "official_docs" in claim_l or finding_id.endswith("target-2"):
        preferred_roles += ["official_docs", "official_repo"]
        preferred_buckets += ["official_docs", "active_repositories"]
        preferred_kinds += ["official_doc", "official_repo"]

    if "active_repositories" in claim_l or "official repo" in claim_l or "repository" in claim_l:
        preferred_roles += ["official_repo", "official_docs"]
        preferred_buckets += ["active_repositories", "official_docs"]
        preferred_kinds += ["official_repo", "official_doc"]

    if "similar_solutions" in claim_l or finding_id.endswith("target-1"):
        preferred_roles += ["practical_community", "regional_community"]
        preferred_buckets += ["similar_solutions"]
        preferred_kinds += ["community_doc"]
        strict_community_first = True

    if "recurring_risks" in claim_l or "pitfall" in claim_l or "issue" in claim_l or "risk" in claim_l:
        preferred_roles += ["issue_problem", "official_docs"]
        preferred_buckets += ["issue_problem_sources", "official_docs"]
        preferred_kinds += ["issue_problem", "official_doc"]

    if finding_id.startswith("finding-source-"):
        preferred_roles += ["official_repo", "official_docs", "practical_community", "regional_community"]

    return {
        "finding_id": finding_id,
        "claim_text": claim_text,
        "prefer_title": prefer_title,
        "prefer_url": prefer_url,
        "preferred_roles": _uniq(preferred_roles),
        "preferred_buckets": _uniq(preferred_buckets),
        "preferred_kinds": _uniq(preferred_kinds),
        "strict_title_first": strict_title_first,
        "strict_community_first": strict_community_first,
    }


def _row_matches_profile(row: dict, profile: dict) -> bool:
    role = _role(row.get("source_role"))
    bucket = str(row.get("source_bucket") or "").lower()
    kind = str(row.get("kind") or "").lower()
    title = str(row.get("title") or "").lower()
    url = str(row.get("url") or row.get("source_url") or "").lower()

    prefer_title = str(profile.get("prefer_title") or "").strip().lower()
    prefer_url = str(profile.get("prefer_url") or "").strip().lower()
    preferred_roles = set(profile.get("preferred_roles") or [])
    preferred_buckets = set(profile.get("preferred_buckets") or [])
    preferred_kinds = set(profile.get("preferred_kinds") or [])

    title_match = bool(prefer_title and (prefer_title == title or prefer_title in title))
    url_match = bool(prefer_url and (prefer_url == url or prefer_url in url))
    role_match = role in preferred_roles if preferred_roles else False
    bucket_match = bucket in preferred_buckets if preferred_buckets else False
    kind_match = kind in preferred_kinds if preferred_kinds else False

    if profile.get("strict_title_first") and (title_match or url_match):
        return True
    if profile.get("strict_community_first") and (role in ("practical_community", "regional_community") or bucket == "similar_solutions"):
        return True

    return title_match or url_match or role_match or bucket_match or kind_match


def _selection_bonus(row: dict, profile: dict) -> float:
    role = _role(row.get("source_role"))
    bucket = str(row.get("source_bucket") or "").lower()
    kind = str(row.get("kind") or "").lower()
    title = str(row.get("title") or "").lower()
    url = str(row.get("url") or row.get("source_url") or "").lower()
    claim_text = str(profile.get("claim_text") or "").lower()

    bonus = 0.0
    prefer_title = str(profile.get("prefer_title") or "").strip().lower()
    prefer_url = str(profile.get("prefer_url") or "").strip().lower()

    if prefer_title:
        if prefer_title == title:
            bonus += 18.0
        elif prefer_title in title:
            bonus += 10.0

    if prefer_url:
        if prefer_url == url:
            bonus += 18.0
        elif prefer_url in url:
            bonus += 10.0

    if role in set(profile.get("preferred_roles") or []):
        bonus += 4.0
    if bucket in set(profile.get("preferred_buckets") or []):
        bonus += 3.0
    if kind in set(profile.get("preferred_kinds") or []):
        bonus += 2.0

    if claim_text.startswith("curated source selected:"):
        if prefer_title and prefer_title not in title:
            bonus -= 8.0
        if role in ("official_repo", "official_docs") and prefer_title and prefer_title not in title:
            bonus -= 3.0

    if "official_docs" in claim_text and role not in ("official_docs", "official_repo"):
        bonus -= 6.0

    if "similar_solutions" in claim_text:
        if role in ("practical_community", "regional_community") or bucket == "similar_solutions":
            bonus += 8.0
        if role in ("official_docs", "official_repo"):
            bonus -= 8.0

    if "recurring_risks" in claim_text:
        if role == "issue_problem" or bucket == "issue_problem_sources":
            bonus += 7.0
        elif role in ("official_docs", "official_repo"):
            bonus += 2.0
        elif role in ("practical_community", "regional_community"):
            bonus -= 2.0

    return bonus


def _rebalance_supports(
    supports: list[dict],
    finding: dict | None = None,
    limit: int = MAX_SUPPORTS_PER_FINDING,
) -> list[dict]:
    rows = []
    seen = set()
    profile = _finding_target_profile(finding)

    for item in supports or []:
        if not isinstance(item, dict):
            continue
        row = _candidate_row(item, finding_id=str(item.get("finding_id") or "support"))
        key = _chunk_key(row)
        if not row.get("source_url") or key in seen:
            continue
        seen.add(key)
        row["_selection_score"] = round(
            _score(row) + _selection_bonus(row, profile) + (0.05 * _priority(row.get("source_role"))),
            4,
        )
        rows.append(row)

    rows = sorted(
        rows,
        key=lambda x: (
            float(x.get("_selection_score") or 0.0),
            _priority(x.get("source_role")),
            _score(x),
            str(x.get("title") or ""),
        ),
        reverse=True,
    )

    selected: list[dict] = []
    used_chunks: set[str] = set()
    doc_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}

    preferred_available = any(_row_matches_profile(x, profile) for x in rows)

    for row in rows:
        chunk_key = _chunk_key(row)
        doc_id = str(row.get("canonical_doc_id") or "")
        family_id = str(row.get("repo_family_id") or "")
        role = _role(row.get("source_role"))

        if chunk_key in used_chunks:
            continue
        if doc_id and doc_counts.get(doc_id, 0) >= MAX_PER_CANONICAL_DOC:
            continue
        if family_id and family_counts.get(family_id, 0) >= MAX_PER_REPO_FAMILY:
            continue

        if not selected and preferred_available and not _row_matches_profile(row, profile):
            continue

        if role_counts.get(role, 0) >= 1 and len(rows) > limit:
            has_alt = any(
                _role(x.get("source_role")) != role
                and str(x.get("canonical_doc_id") or "") != doc_id
                for x in rows
            )
            if has_alt:
                continue

        clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
        selected.append(clean)
        used_chunks.add(chunk_key)

        if doc_id:
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        if family_id:
            family_counts[family_id] = family_counts.get(family_id, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1

        if len(selected) >= limit:
            break

    if len(selected) < min(limit, len(rows)):
        used_chunk_keys = {_chunk_key(x) for x in selected}
        used_doc_ids = {str(x.get("canonical_doc_id") or "") for x in selected if x.get("canonical_doc_id")}
        for row in rows:
            if len(selected) >= limit:
                break
            chunk_key = _chunk_key(row)
            doc_id = str(row.get("canonical_doc_id") or "")
            if chunk_key in used_chunk_keys:
                continue
            if doc_id and doc_id in used_doc_ids:
                continue
            clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
            selected.append(clean)
            used_chunk_keys.add(chunk_key)
            if doc_id:
                used_doc_ids.add(doc_id)

    return selected[:limit]


def _role_counts(rows: list[dict]) -> dict:
    counts = {}
    for row in rows or []:
        role = _role(row.get("source_role"))
        counts[role] = counts.get(role, 0) + 1
    return counts


def _global_finding_priority(finding: dict | None) -> tuple[int, str]:
    finding = finding or {}
    finding_id = str(finding.get("id") or finding.get("finding_id") or "").strip().lower()

    if finding_id.startswith("finding-target-"):
        return (0, finding_id)
    if finding_id.startswith("finding-risk-"):
        return (1, finding_id)
    if finding_id.startswith("finding-source-"):
        return (2, finding_id)
    if finding_id.startswith("finding-start-"):
        return (3, finding_id)
    if finding_id.startswith("finding-memory-"):
        return (4, finding_id)
    if finding_id == "finding-project-type":
        return (8, finding_id)
    if finding_id == "finding-mode":
        return (9, finding_id)
    return (5, finding_id)


def _build_global_citations(
    findings: list[dict],
    extra_rows: list[dict] | None = None,
    limit: int = MAX_GLOBAL_CITATIONS,
) -> list[dict]:
    pool: list[dict] = []
    seen = set()

    ordered_findings = sorted(
        list(findings or []),
        key=_global_finding_priority,
    )

    for idx, finding in enumerate(ordered_findings, start=1):
        finding_id = str(finding.get("id") or finding.get("finding_id") or f"finding-{idx:03d}")
        for support in finding.get("supports") or []:
            if not isinstance(support, dict):
                continue
            row = _candidate_row(support, finding_id=finding_id)
            key = _chunk_key(row)
            if not row.get("source_url") or key in seen:
                continue
            seen.add(key)
            pool.append(row)

    for item in extra_rows or []:
        if not isinstance(item, dict):
            continue
        row = _candidate_row(item, finding_id="global_pool")
        key = _chunk_key(row)
        if not row.get("source_url") or key in seen:
            continue
        seen.add(key)
        pool.append(row)

    rows = _sorted_rows(pool)

    selected: list[dict] = []
    used_chunks: set[str] = set()
    doc_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    selected_roles: set[str] = set()
    family_overrides = 0

    def _selected_role(row: dict) -> str:
        return _role(row.get("source_role"))

    def _try_take_global(row: dict, allow_family_override: bool = False) -> bool:
        nonlocal family_overrides

        key = _chunk_key(row)
        if not key or key in used_chunks:
            return False

        doc_id = str(row.get("canonical_doc_id") or "")
        family_id = str(row.get("repo_family_id") or "")

        if doc_id and doc_counts.get(doc_id, 0) >= MAX_PER_CANONICAL_DOC:
            return False

        family_at_cap = bool(
            family_id and family_counts.get(family_id, 0) >= MAX_PER_REPO_FAMILY
        )
        if family_at_cap and not allow_family_override:
            return False
        if family_at_cap and allow_family_override and family_overrides >= 1:
            return False

        selected.append(row)
        used_chunks.add(key)

        if doc_id:
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1

        if family_id:
            family_counts[family_id] = family_counts.get(family_id, 0) + 1
            if family_counts[family_id] > MAX_PER_REPO_FAMILY:
                family_overrides += 1

        selected_roles.add(_selected_role(row))
        return True

    def take_seed(predicate, allow_family_override: bool = False):
        for row in rows:
            if len(selected) >= limit:
                break
            if not predicate(row):
                continue
            if _selected_role(row) in selected_roles:
                continue
            if _try_take_global(row, allow_family_override=allow_family_override):
                break

    def take_bucket(predicate, n: int):
        taken = 0
        for row in rows:
            if len(selected) >= limit or taken >= n:
                break
            if not predicate(row):
                continue
            if _try_take_global(row):
                taken += 1

    # role-diversity seed pass
    take_seed(_is_official, allow_family_override=False)
    take_seed(_is_issue, allow_family_override=False)
    take_seed(_is_community, allow_family_override=True)

    # regular quota pass
    take_bucket(_is_official, 2)
    take_bucket(_is_issue, 1)
    take_bucket(_is_community, 4)

    for row in rows:
        if len(selected) >= limit:
            break
        _try_take_global(row)

    return selected[:limit]

def run(artifact_dir: Path) -> int:
    step28 = _load_module(STEP28_HELPER, "project_research_step28_helper")
    step22 = _load_module(STEP22_HELPER, "project_research_step22_helper")

    step28.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    provenance_path = artifact_dir / "provenance.json"
    grounding_path = artifact_dir / "synthesis_grounding.json"
    grounding_report_path = artifact_dir / "synthesis_grounding_report.json"
    eval_report_path = artifact_dir / "eval_safety_report.json"
    diverse_path = artifact_dir / "reranked_evidence_diverse.jsonl"

    context = _read_json(context_path, {})
    provenance = _read_json(provenance_path, {})
    grounding = _read_json(grounding_path, {})
    diverse_rows = _read_jsonl(diverse_path)

    raw_findings = grounding.get("findings") or []
    balanced_findings = []

    for idx, finding in enumerate(raw_findings, start=1):
        row = dict(finding) if isinstance(finding, dict) else {}
        row["id"] = str(row.get("id") or row.get("finding_id") or f"finding-{idx:03d}")
        row["supports"] = _rebalance_supports(
            row.get("supports") or [],
            finding=row,
            limit=MAX_SUPPORTS_PER_FINDING,
        )
        row["support_count"] = len(row["supports"])
        balanced_findings.append(row)

    citation_candidates = _build_global_citations(
        balanced_findings,
        extra_rows=diverse_rows,
        limit=MAX_GLOBAL_CITATIONS,
    )

    grounding["status"] = "implemented_v6"
    grounding["generated_at"] = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    grounding["findings"] = balanced_findings
    grounding["citation_candidates"] = citation_candidates
    grounding["grounding_policy"] = "source_diverse_chunk_pool+balanced_citations_v2+finding_aware_v1+source_match_v1"
    grounding["max_supports_per_finding"] = MAX_SUPPORTS_PER_FINDING
    grounding["max_global_citations"] = MAX_GLOBAL_CITATIONS
    grounding["max_global_per_source"] = MAX_GLOBAL_PER_SOURCE
    grounding["max_per_canonical_doc"] = MAX_PER_CANONICAL_DOC
    grounding["max_per_repo_family"] = MAX_PER_REPO_FAMILY
    grounding["grounded_findings_count"] = sum(1 for x in balanced_findings if (x.get("support_count") or 0) > 0)
    grounding["total_findings"] = len(balanced_findings)
    grounding["citation_role_counts"] = _role_counts(citation_candidates)
    _write_json(grounding_path, grounding)

    report = {
        "status": "implemented_v6",
        "grounded_findings_count": grounding["grounded_findings_count"],
        "total_findings": grounding["total_findings"],
        "citation_candidates_count": len(citation_candidates),
        "top_chunk_ids": [x.get("chunk_id") for x in citation_candidates[:10]],
        "grounding_policy": "source_diverse_chunk_pool+balanced_citations_v2+finding_aware_v1+source_match_v1",
        "max_supports_per_finding": MAX_SUPPORTS_PER_FINDING,
        "max_global_citations": MAX_GLOBAL_CITATIONS,
        "max_global_per_source": MAX_GLOBAL_PER_SOURCE,
        "max_per_canonical_doc": MAX_PER_CANONICAL_DOC,
        "max_per_repo_family": MAX_PER_REPO_FAMILY,
        "citation_role_counts": _role_counts(citation_candidates),
        "extra_global_pool_file": str(diverse_path),
    }
    _write_json(grounding_report_path, report)

    sg = context.get("synthesis_grounding") or {}
    sg["status"] = "implemented_v6"
    sg["grounding_file"] = str(grounding_path)
    sg["grounding_report"] = str(grounding_report_path)
    sg["grounded_findings_count"] = grounding["grounded_findings_count"]
    sg["total_findings"] = grounding["total_findings"]
    sg["citation_candidates_count"] = len(citation_candidates)
    sg["grounding_policy"] = "source_diverse_chunk_pool+balanced_citations_v2+finding_aware_v1+source_match_v1"
    sg["max_supports_per_finding"] = MAX_SUPPORTS_PER_FINDING
    sg["max_global_citations"] = MAX_GLOBAL_CITATIONS
    sg["max_global_per_source"] = MAX_GLOBAL_PER_SOURCE
    sg["max_per_canonical_doc"] = MAX_PER_CANONICAL_DOC
    sg["max_per_repo_family"] = MAX_PER_REPO_FAMILY
    sg["citation_diversity_guard"] = True
    sg["citation_role_counts"] = _role_counts(citation_candidates)
    context["synthesis_grounding"] = sg

    arch = context.get("architecture_layers")
    if isinstance(arch, dict):
        arch["layer6_synthesis_provenance"] = {
            "status": "implemented_v6",
            "scaffold_only": False,
            "grounded_findings_count": grounding["grounded_findings_count"],
            "citation_candidates_count": len(citation_candidates),
            "grounding_policy": "source_diverse_chunk_pool+balanced_citations_v2+finding_aware_v1+source_match_v1",
            "citation_diversity_guard": True,
            "max_per_canonical_doc": MAX_PER_CANONICAL_DOC,
            "max_per_repo_family": MAX_PER_REPO_FAMILY,
        }
        context["architecture_layers"] = arch

    if isinstance(provenance, dict):
        provenance["synthesis_grounding_file"] = str(grounding_path)
        provenance["synthesis_grounding_report"] = str(grounding_report_path)
        provenance["citation_candidates"] = citation_candidates
        provenance["citation_diversity_guard"] = {
            "status": "implemented_v3",
            "max_supports_per_finding": MAX_SUPPORTS_PER_FINDING,
            "max_global_citations": MAX_GLOBAL_CITATIONS,
            "max_global_per_source": MAX_GLOBAL_PER_SOURCE,
            "max_per_canonical_doc": MAX_PER_CANONICAL_DOC,
            "max_per_repo_family": MAX_PER_REPO_FAMILY,
            "extra_global_pool_file": str(diverse_path),
            "citation_role_counts": _role_counts(citation_candidates),
        }
        _write_json(provenance_path, provenance)

    _write_json(context_path, context)
    step22._update_eval(context, eval_report_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step29.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))