#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

STEP19_HELPER = Path("/home/agent/bin/project-research-fetch-extract-step19.py")

TOP_SUPPORT_PER_FINDING = 3
TOP_GLOBAL_CITATIONS = 12
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


def _load_step19_module():
    if not STEP19_HELPER.exists():
        raise SystemExit(f"missing step19 helper: {STEP19_HELPER}")
    spec = importlib.util.spec_from_file_location("project_research_step19_helper", STEP19_HELPER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import step19 helper: {STEP19_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _role(value: str) -> str:
    return str(value or "").strip().lower()


def _priority(role: str) -> int:
    return ROLE_PRIORITY.get(_role(role), 0)


def _score_num(value) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _claim_text(row: dict) -> str:
    for key in ("claim", "finding", "statement", "summary", "text", "content", "title"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(row, ensure_ascii=False)[:500]


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zА-Яа-я0-9_./:+-]{4,}", str(text or "").lower())
    out = []
    seen = set()
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out[:40]


def _uniq(seq: list[str]) -> list[str]:
    out = []
    seen = set()
    for x in seq:
        x = str(x or "").strip().lower()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


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


def _chunk_key(row: dict) -> str:
    chunk_id = str(row.get("chunk_id") or "").strip()
    if chunk_id:
        return chunk_id
    url = str(row.get("source_url") or row.get("url") or "").strip()
    title = str(row.get("title") or "").strip()
    return f"{url}|{title}"


def _candidate_row(chunk: dict, finding_id: str) -> dict:
    url = _canonical_source_url(chunk.get("source_url") or chunk.get("url") or "")
    title = str(chunk.get("title") or chunk.get("source_title") or url or "source").strip()
    role = _role(chunk.get("source_role") or chunk.get("role") or "generic_reference")

    row = dict(chunk)
    row["finding_id"] = finding_id
    row["url"] = url
    row["source_url"] = url
    row["title"] = title
    row["source_role"] = role
    row["source_bucket"] = str(chunk.get("source_bucket") or _infer_bucket_from_role(role))
    row["kind"] = str(chunk.get("kind") or _infer_kind_from_role(role))
    row["canonical_doc_id"] = str(chunk.get("canonical_doc_id") or url or title)
    row["repo_family_id"] = str(chunk.get("repo_family_id") or _repo_family_id_from_url(url))
    return row


def _finding_target_profile(row: dict, claim_text: str) -> dict:
    finding_id = str(row.get("id") or row.get("finding_id") or "").strip().lower()
    claim_l = str(claim_text or "").strip().lower()

    preferred_roles: list[str] = []
    preferred_buckets: list[str] = []
    preferred_kinds: list[str] = []
    prefer_title = ""
    strict_title_first = False

    if claim_text.startswith("Curated source selected:"):
        source_name = claim_text.split("Curated source selected:", 1)[1].strip().rstrip(".")
        prefer_title = source_name.lower()
        strict_title_first = True

    prefer_official = ("official_docs" in claim_l) or finding_id.endswith("target-2")
    prefer_community = ("similar_solutions" in claim_l) or finding_id.endswith("target-1")
    prefer_issue = (
        ("recurring_risks" in claim_l)
        or ("risk" in finding_id)
        or ("risk" in claim_l)
        or ("drift" in claim_l)
    )

    if prefer_official:
        preferred_roles += ["official_docs", "official_repo"]
        preferred_buckets += ["official_docs", "active_repositories"]
        preferred_kinds += ["official_doc", "official_repo"]

    if prefer_community:
        preferred_roles += ["practical_community", "regional_community"]
        preferred_buckets += ["similar_solutions"]
        preferred_kinds += ["community_doc"]

    if prefer_issue:
        preferred_roles += ["issue_problem"]
        preferred_buckets += ["issue_problem_sources"]
        preferred_kinds += ["issue_problem"]

    return {
        "finding_id": finding_id,
        "prefer_title": prefer_title,
        "strict_title_first": strict_title_first,
        "prefer_official": prefer_official,
        "prefer_community": prefer_community,
        "prefer_issue": prefer_issue,
        "preferred_roles": _uniq(preferred_roles),
        "preferred_buckets": _uniq(preferred_buckets),
        "preferred_kinds": _uniq(preferred_kinds),
    }


def _row_matches_profile(row: dict, profile: dict) -> bool:
    title_blob = " ".join(
        [
            str(row.get("title") or "").lower(),
            str(row.get("source_url") or "").lower(),
            str(row.get("canonical_doc_id") or "").lower(),
        ]
    )

    if profile.get("prefer_title"):
        if profile["prefer_title"] in title_blob:
            return True

    role = _role(row.get("source_role"))
    bucket = str(row.get("source_bucket") or "").strip().lower()
    kind = str(row.get("kind") or "").strip().lower()

    return (
        role in set(profile.get("preferred_roles") or [])
        or bucket in set(profile.get("preferred_buckets") or [])
        or kind in set(profile.get("preferred_kinds") or [])
    )


def _selection_bonus(row: dict, profile: dict) -> float:
    bonus = 0.0
    role = _role(row.get("source_role"))
    bucket = str(row.get("source_bucket") or "").strip().lower()
    title_blob = " ".join(
        [
            str(row.get("title") or "").lower(),
            str(row.get("source_url") or "").lower(),
            str(row.get("canonical_doc_id") or "").lower(),
        ]
    )

    if profile.get("prefer_title"):
        if profile["prefer_title"] in title_blob:
            bonus += 18.0
        elif profile.get("strict_title_first"):
            bonus -= 6.0

    if profile.get("prefer_official"):
        if role == "official_docs":
            bonus += 15.0
        elif role == "official_repo":
            bonus += 2.0
        elif role == "issue_problem":
            bonus -= 3.0
        elif role in ("practical_community", "regional_community"):
            bonus -= 4.0

    if profile.get("prefer_community"):
        if role in ("practical_community", "regional_community") or bucket == "similar_solutions":
            bonus += 8.0
        elif role in ("official_docs", "official_repo"):
            bonus -= 5.0
        elif role == "issue_problem":
            bonus -= 2.0

    if profile.get("prefer_issue"):
        if role == "issue_problem" or bucket == "issue_problem_sources":
            bonus += 16.0
        elif role == "official_docs":
            bonus += 1.0
        elif role == "official_repo":
            bonus -= 10.0
        elif role in ("practical_community", "regional_community"):
            bonus -= 3.0

    return bonus


def _score_support(finding_row: dict, claim_text: str, chunk: dict) -> tuple[float, dict]:
    claim_tokens = _tokenize(claim_text)
    excerpt = str(chunk.get("text_excerpt") or "").lower()
    title = str(chunk.get("title") or "").lower()
    source_url = str(chunk.get("source_url") or chunk.get("url") or "").lower()
    source_role = str(chunk.get("source_role") or "").lower()

    overlap = [tok for tok in claim_tokens if tok in excerpt or tok in title or tok in source_url]
    overlap_count = len(overlap)

    rerank_score = _score_num(chunk.get("support_score") or chunk.get("score"))
    role_bonus = 0.8 if source_role in ("official_repo", "official_docs") else 0.0
    issue_bonus = 0.3 if source_role == "issue_problem" else 0.0

    profile = _finding_target_profile(finding_row, claim_text)
    selection_bonus = _selection_bonus(chunk, profile)

    score = rerank_score + overlap_count * 0.9 + role_bonus + issue_bonus + selection_bonus
    details = {
        "overlap_count": overlap_count,
        "overlap_terms": overlap[:10],
        "rerank_score": rerank_score,
        "role_bonus": role_bonus,
        "issue_bonus": issue_bonus,
        "selection_bonus": round(selection_bonus, 4),
    }
    return round(score, 4), details


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

    selected.append({k: v for k, v in row.items() if not str(k).startswith("_")})
    used_chunks.add(key)

    if doc_id:
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
    if family_id:
        family_counts[family_id] = family_counts.get(family_id, 0) + 1
    return True


def _select_supports(scored_rows: list[dict], profile: dict, limit: int) -> list[dict]:
    rows = sorted(
        scored_rows,
        key=lambda x: (
            float(x.get("_selection_score") or x.get("support_score") or 0.0),
            x.get("support_details", {}).get("overlap_count", 0),
            _priority(x.get("source_role")),
            str(x.get("title") or ""),
        ),
        reverse=True,
    )

    selected: list[dict] = []
    used_chunks: set[str] = set()
    doc_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}

    def take_first(predicate):
        for row in rows:
            if len(selected) >= limit:
                return
            if predicate(row) and _try_take(row, selected, used_chunks, doc_counts, family_counts):
                return

    def take_rows(predicate):
        for row in rows:
            if len(selected) >= limit:
                break
            if predicate(row):
                _try_take(row, selected, used_chunks, doc_counts, family_counts)

    if profile.get("strict_title_first") and profile.get("prefer_title"):
        take_first(lambda r: _row_matches_profile(r, profile))

    # role-seed pass for semantic target alignment
    if profile.get("prefer_issue"):
        take_first(
            lambda r: (
                _role(r.get("source_role")) == "issue_problem"
                or str(r.get("source_bucket") or "").strip().lower() == "issue_problem_sources"
            )
        )

    if profile.get("prefer_official"):
        take_first(
            lambda r: (
                _role(r.get("source_role")) == "official_docs"
                or str(r.get("source_bucket") or "").strip().lower() == "official_docs"
            )
        )

    if profile.get("prefer_community"):
        take_first(
            lambda r: (
                _role(r.get("source_role")) in ("practical_community", "regional_community")
                or str(r.get("source_bucket") or "").strip().lower() in ("similar_solutions", "regional_community")
            )
        )

    preferred_available = any(_row_matches_profile(x, profile) for x in rows)

    if len(selected) < limit and preferred_available:
        take_rows(
            lambda r: (
                _row_matches_profile(r, profile)
                and _role(r.get("source_role")) not in {_role(x.get("source_role")) for x in selected}
            )
        )

    if len(selected) < limit:
        take_rows(
            lambda r: _role(r.get("source_role")) not in {_role(x.get("source_role")) for x in selected}
        )

    if len(selected) < limit and preferred_available:
        take_rows(lambda r: _row_matches_profile(r, profile))

    if len(selected) < limit:
        take_rows(lambda r: True)

    return selected[:limit]

def _ground_findings(findings: list[dict], reranked_chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    grounded = []
    citation_candidates = []

    for idx, row in enumerate(findings, start=1):
        finding_id = str(row.get("id") or f"finding-{idx:03d}")
        claim_text = _claim_text(row)
        profile = _finding_target_profile(row, claim_text)

        scored = []
        seen = set()

        for chunk in reranked_chunks[:120]:
            if not isinstance(chunk, dict):
                continue

            base_row = _candidate_row(chunk, finding_id=finding_id)
            chunk_key = _chunk_key(base_row)
            if not base_row.get("source_url") or chunk_key in seen:
                continue
            seen.add(chunk_key)

            score, details = _score_support(row, claim_text, base_row)
            if details["overlap_count"] == 0 and _score_num(base_row.get("score")) < 2.0:
                continue

            scored.append({
                "finding_id": finding_id,
                "chunk_id": base_row.get("chunk_id"),
                "source_url": base_row.get("source_url"),
                "url": base_row.get("url"),
                "title": base_row.get("title"),
                "source_title": base_row.get("title"),
                "source_role": base_row.get("source_role"),
                "source_bucket": base_row.get("source_bucket"),
                "kind": base_row.get("kind"),
                "canonical_doc_id": base_row.get("canonical_doc_id"),
                "repo_family_id": base_row.get("repo_family_id"),
                "host": base_row.get("host"),
                "support_score": score,
                "support_details": details,
                "text_excerpt": base_row.get("text_excerpt"),
                "_selection_score": round(score, 4),
            })

        supports = _select_supports(scored, profile, TOP_SUPPORT_PER_FINDING)

        grounded.append({
            "finding_id": finding_id,
            "claim_text": claim_text,
            "support_count": len(supports),
            "supports": supports,
        })

        for support in supports:
            citation_candidates.append({
                "finding_id": finding_id,
                "chunk_id": support.get("chunk_id"),
                "source_url": support.get("source_url"),
                "url": support.get("url"),
                "title": support.get("title"),
                "source_title": support.get("source_title"),
                "source_role": support.get("source_role"),
                "source_bucket": support.get("source_bucket"),
                "kind": support.get("kind"),
                "canonical_doc_id": support.get("canonical_doc_id"),
                "repo_family_id": support.get("repo_family_id"),
                "support_score": support.get("support_score"),
            })

    citation_candidates.sort(
        key=lambda x: (
            _score_num(x.get("support_score")),
            _priority(x.get("source_role")),
            str(x.get("title") or ""),
        ),
        reverse=True,
    )
    return grounded, citation_candidates[:TOP_GLOBAL_CITATIONS]


def _append_research_section(research_path: Path, grounded: list[dict]) -> None:
    if not research_path.exists():
        return
    original = research_path.read_text(encoding="utf-8", errors="ignore")
    marker = "\n## Evidence grounding\n"
    trimmed = original.split(marker)[0].rstrip()

    lines = [trimmed, "", "## Evidence grounding", ""]
    if not grounded:
        lines.append("- No grounded findings were produced.")
    else:
        for item in grounded[:8]:
            lines.append(f"- {item.get('finding_id')}: {item.get('claim_text')[:180]}")
            supports = item.get("supports") or []
            if not supports:
                lines.append("  - support: none")
                continue
            for support in supports[:2]:
                title = support.get("title") or support.get("source_url") or "source"
                role = support.get("source_role") or "unknown"
                bucket = support.get("source_bucket") or "unknown_bucket"
                kind = support.get("kind") or "unknown_kind"
                chunk_id = support.get("chunk_id") or "chunk"
                score = support.get("support_score")
                url = support.get("source_url") or ""
                lines.append(f"  - {chunk_id} | {role} | {bucket} | {kind} | score={score} | {title}")
                if url:
                    lines.append(f"    {url}")

    research_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run(artifact_dir: Path) -> int:
    step19 = _load_step19_module()
    step19.run(artifact_dir)

    context_path = artifact_dir / "context.json"
    findings_path = artifact_dir / "findings.jsonl"
    rerank_path = artifact_dir / "reranked_evidence.jsonl"
    provenance_path = artifact_dir / "provenance.json"
    research_path = artifact_dir / "RESEARCH.md"

    context = _read_json(context_path, {})
    findings = _read_jsonl(findings_path)
    reranked_chunks = _read_jsonl(rerank_path)

    grounded, citation_candidates = _ground_findings(findings, reranked_chunks)
    grounding_path = artifact_dir / "synthesis_grounding.json"
    grounding_report_path = artifact_dir / "synthesis_grounding_report.json"

    grounding = {
        "status": "implemented_v1",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "grounded_findings_count": sum(1 for x in grounded if (x.get("support_count") or 0) > 0),
        "total_findings": len(grounded),
        "findings": grounded,
        "citation_candidates": citation_candidates,
    }
    _write_json(grounding_path, grounding)

    grounding_report = {
        "status": "implemented_v1",
        "grounded_findings_count": grounding["grounded_findings_count"],
        "total_findings": grounding["total_findings"],
        "citation_candidates_count": len(citation_candidates),
        "top_chunk_ids": [x.get("chunk_id") for x in citation_candidates[:10]],
    }
    _write_json(grounding_report_path, grounding_report)

    _append_research_section(research_path, grounded)

    provenance = _read_json(provenance_path, {})
    if isinstance(provenance, dict):
        provenance["synthesis_grounding_file"] = str(grounding_path)
        provenance["synthesis_grounding_report"] = str(grounding_report_path)
        provenance["citation_candidates"] = citation_candidates
        _write_json(provenance_path, provenance)

    synthesis_grounding = context.get("synthesis_grounding") or {}
    synthesis_grounding["status"] = "implemented_v1"
    synthesis_grounding["grounding_file"] = str(grounding_path)
    synthesis_grounding["grounding_report"] = str(grounding_report_path)
    synthesis_grounding["grounded_findings_count"] = grounding["grounded_findings_count"]
    synthesis_grounding["total_findings"] = grounding["total_findings"]
    synthesis_grounding["citation_candidates_count"] = len(citation_candidates)
    context["synthesis_grounding"] = synthesis_grounding

    architecture_layers = context.get("architecture_layers")
    if isinstance(architecture_layers, dict):
        architecture_layers["layer6_synthesis_provenance"] = {
            "status": "implemented_v1",
            "scaffold_only": False,
            "grounded_findings_count": grounding["grounded_findings_count"],
            "citation_candidates_count": len(citation_candidates),
        }
        context["architecture_layers"] = architecture_layers

    _write_json(context_path, context)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step20.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
