#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) project-research-step18/1.0"
MAX_CANDIDATES = 4
MAX_BYTES = 2_000_000
MAX_EXCERPT = 4000
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 250

KNOWN_OFFICIAL_DOCS_HOSTS = {
    "developers.openai.com",
    "platform.openai.com",
    "docs.pydantic.dev",
    "ai.pydantic.dev",
    "docs.langchain.com",
    "docs.prefect.io",
    "opentelemetry.io",
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _jsonl_write(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return value[:80] or "item"


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p\s*>", "\n\n", raw)
    raw = re.sub(r"(?i)</div\s*>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = raw.replace("\r", "\n")
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r" *\n *", "\n", raw)
    return raw.strip()


def _github_raw(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc != "github.com":
        return url
    parts = parsed.path.strip("/").split("/")
    if len(parts) >= 5 and parts[2] == "blob":
        owner, repo, _, branch = parts[:4]
        rest = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rest}"
    return url


def _guess_fetch_method(url: str, planned: str | None) -> str:
    if planned:
        return planned
    parsed = urllib.parse.urlparse(url)
    if parsed.path.endswith(".pdf"):
        return "pdf_text"
    if parsed.netloc == "github.com" and "/blob/" in parsed.path:
        return "github_blob"
    if parsed.netloc == "github.com" and "/wiki" in parsed.path:
        return "github_wiki"
    if parsed.netloc == "github.com" and ("/issues/" in parsed.path or "/discussions/" in parsed.path):
        return "github_issue_discussion"
    if parsed.netloc in {"raw.githubusercontent.com", "gist.githubusercontent.com"}:
        return "raw_text"
    return "html_readable"


def _download(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
        body = resp.read(MAX_BYTES)
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.geturl()
        return body, content_type, final_url


def _decode_text(body: bytes, content_type: str) -> str:
    m = re.search(r"charset=([A-Za-z0-9._-]+)", content_type or "", re.I)
    encodings = [m.group(1)] if m else []
    encodings += ["utf-8", "utf-8-sig", "cp1251", "latin-1"]
    for enc in encodings:
        try:
            return body.decode(enc)
        except Exception:
            continue
    return body.decode("utf-8", errors="replace")


def _extract_pdf_text(body: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(body))
        pages = []
        for page in reader.pages[:10]:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages).strip()
    except Exception:
        return ""


def _role(value) -> str:
    role = str(value or "").strip().lower()
    return role or "generic_reference"


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
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not host:
        return ""
    if parts:
        return f"{host}/{parts[0].lower()}"
    return host


def _infer_role_from_metadata(item: dict) -> str:
    role = _role(item.get("source_role") or item.get("role") or item.get("best_role"))
    if role != "generic_reference":
        return role

    kind = str(item.get("kind") or "").strip().lower()
    bucket = str(item.get("source_bucket") or "").strip().lower()
    url = str(item.get("url") or item.get("source_url") or item.get("fetch_url") or "")
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    low_path = parsed.path.lower()

    if kind in ("official_repo", "active_repository"):
        return "official_repo"
    if kind == "official_doc":
        return "official_docs"
    if kind == "issue_problem":
        return "issue_problem"
    if kind == "community_doc":
        if bucket == "regional_community":
            return "regional_community"
        return "practical_community"

    if bucket == "official_docs":
        return "official_docs"
    if bucket == "active_repositories":
        return "official_repo"
    if bucket == "issue_problem_sources":
        return "issue_problem"
    if bucket == "regional_community":
        return "regional_community"

    if host == "github.com":
        if "/issues/" in low_path or "/discussions/" in low_path:
            return "issue_problem"
        if "/wiki" in low_path:
            return "official_docs"
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return "official_repo"

    if host in KNOWN_OFFICIAL_DOCS_HOSTS or any(host.endswith("." + x) for x in KNOWN_OFFICIAL_DOCS_HOSTS):
        return "official_docs"

    if any(marker in host for marker in ("docs.", "developers.", "developer.", "api.", "ai.")):
        if any(token in host for token in ("openai", "pydantic", "langchain", "prefect", "opentelemetry")):
            return "official_docs"

    return "generic_reference"


def _infer_bucket_from_role(role: str) -> str:
    role = _role(role)
    if role == "official_repo":
        return "active_repositories"
    if role == "official_docs":
        return "official_docs"
    if role == "issue_problem":
        return "issue_problem_sources"
    if role == "regional_community":
        return "regional_community"
    if role == "practical_community":
        return "similar_solutions"
    return "similar_solutions"


def _infer_kind_from_role(role: str, source_bucket: str) -> str:
    role = _role(role)
    bucket = str(source_bucket or "").strip().lower()

    if role == "official_repo":
        return "official_repo"
    if role == "official_docs":
        return "official_doc"
    if role == "issue_problem":
        return "issue_problem"
    if role in ("practical_community", "regional_community"):
        return "community_doc"

    if bucket == "active_repositories":
        return "official_repo"
    if bucket == "official_docs":
        return "official_doc"
    if bucket == "issue_problem_sources":
        return "issue_problem"
    if bucket in ("similar_solutions", "regional_community"):
        return "community_doc"

    return "external_search"



def _canonicalize_metadata(source_role: str, source_bucket: str, kind: str) -> tuple[str, str, str]:
    role = _role(source_role)
    bucket = str(source_bucket or "").strip().lower()
    kind_value = str(kind or "").strip().lower()

    if role == "official_repo" or kind_value == "official_repo" or bucket == "active_repositories":
        return "official_repo", "active_repositories", "official_repo"
    if role == "official_docs" or kind_value == "official_doc" or bucket == "official_docs":
        return "official_docs", "official_docs", "official_doc"
    if role == "issue_problem" or kind_value == "issue_problem" or bucket == "issue_problem_sources":
        return "issue_problem", "issue_problem_sources", "issue_problem"
    if role == "regional_community" or bucket == "regional_community":
        return "regional_community", "regional_community", "community_doc"
    if role == "practical_community" or kind_value == "community_doc" or bucket == "similar_solutions":
        return "practical_community", "similar_solutions", "community_doc"

    inferred_role = _infer_role_from_metadata(
        {
            "source_role": role,
            "source_bucket": bucket,
            "kind": kind_value,
        }
    )
    inferred_role = _role(inferred_role)
    inferred_bucket = bucket or _infer_bucket_from_role(inferred_role)
    inferred_kind = kind_value or _infer_kind_from_role(inferred_role, inferred_bucket)
    return inferred_role, inferred_bucket, inferred_kind

def _item_url(item: dict) -> str:
    return str(item.get("url") or item.get("source_url") or item.get("link") or "").strip()


def _source_lookup(sources) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    if isinstance(sources, list):
        source_items = sources
    elif isinstance(sources, dict):
        source_items = sources.get("sources") or sources.get("items") or []
    else:
        source_items = []

    for item in source_items:
        if not isinstance(item, dict):
            continue
        url = _item_url(item)
        if not url:
            continue
        lookup[url] = item
    return lookup


def _merge_candidate(raw: dict, source_item: dict | None) -> dict:
    src = source_item or {}
    url = _item_url(raw) or _item_url(src)
    title = raw.get("title") or raw.get("label") or src.get("title") or src.get("name") or ""
    source_title = raw.get("source_title") or src.get("source_title") or title

    role_seed = {
        "url": url,
        "source_url": url,
        "source_role": raw.get("source_role") or raw.get("role") or src.get("source_role") or src.get("role"),
        "best_role": raw.get("best_role") or src.get("best_role"),
        "kind": raw.get("kind") or src.get("kind"),
        "source_bucket": raw.get("source_bucket") or src.get("source_bucket"),
        "fetch_url": raw.get("fetch_url") or src.get("fetch_url"),
    }
    source_role = _infer_role_from_metadata(role_seed)

    source_bucket = str(raw.get("source_bucket") or src.get("source_bucket") or _infer_bucket_from_role(source_role))
    kind = str(raw.get("kind") or src.get("kind") or _infer_kind_from_role(source_role, source_bucket))

    source_role, source_bucket, kind = _canonicalize_metadata(source_role, source_bucket, kind)

    normalized_repo_url = str(
        raw.get("normalized_repo_url")
        or src.get("normalized_repo_url")
        or _normalize_repo_url(url)
    )
    repo_url = str(raw.get("repo_url") or src.get("repo_url") or normalized_repo_url)
    canonical_doc_id = str(raw.get("canonical_doc_id") or src.get("canonical_doc_id") or url or source_title)
    repo_family_id = str(raw.get("repo_family_id") or src.get("repo_family_id") or _repo_family_id_from_url(repo_url or url))
    why_extract = raw.get("why_extract") or src.get("why_relevant") or src.get("notes") or ""
    fetch_method = raw.get("fetch_method") or raw.get("fetch_method_hint") or src.get("fetch_method") or ""

    return {
        "url": url,
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
    }


def _candidate_rows(context: dict, sources) -> list[dict]:
    rows: list[dict] = []
    lookup = _source_lookup(sources)

    fetch_extraction = context.get("fetch_extraction") or {}
    planned = fetch_extraction.get("planned_candidates") or []
    for item in planned:
        if not isinstance(item, dict):
            continue
        url = _item_url(item)
        if not url:
            continue
        rows.append(_merge_candidate(item, lookup.get(url)))

    if not rows:
        if isinstance(sources, list):
            source_items = sources
        elif isinstance(sources, dict):
            source_items = sources.get("sources") or sources.get("items") or []
        else:
            source_items = []
        for item in source_items[:8]:
            if not isinstance(item, dict):
                continue
            url = _item_url(item)
            if not url:
                continue
            rows.append(_merge_candidate(item, lookup.get(url)))

    dedup: dict[str, dict] = {}
    for row in rows:
        if row["url"]:
            dedup[row["url"]] = row

    ordered = list(dedup.values())
    if len(ordered) <= MAX_CANDIDATES:
        return ordered

    selected: list[dict] = []
    selected_urls: set[str] = set()
    seen_roles: set[str] = set()

    for row in ordered:
        url = row.get("url") or ""
        role = _role(row.get("source_role"))
        if not url or url in selected_urls:
            continue
        if role == "generic_reference" or role in seen_roles:
            continue
        selected.append(row)
        selected_urls.add(url)
        seen_roles.add(role)
        if len(selected) >= MAX_CANDIDATES:
            return selected

    for row in ordered:
        url = row.get("url") or ""
        if not url or url in selected_urls:
            continue
        selected.append(row)
        selected_urls.add(url)
        if len(selected) >= MAX_CANDIDATES:
            break

    return selected


def _load_sources(path: Path):
    if not path.exists():
        return []
    data = _read_json(path, [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("sources") or data.get("items") or []
    return []


def _save_text(out_dir: Path, idx: int, title: str, text: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{idx:02d}-{_slug(title or 'source')}.txt"
    path = out_dir / name
    path.write_text(text, encoding="utf-8")
    return str(path)


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


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append((start, end, piece))
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _build_evidence_index(artifact_dir: Path, evidence_rows: list[dict], focus_terms: list[str]):
    index_path = artifact_dir / "evidence_index.jsonl"
    report_path = artifact_dir / "evidence_index_report.json"

    rows = []
    indexed_sources = 0

    for evidence in evidence_rows:
        if evidence.get("status") != "ok":
            continue
        text_file = evidence.get("text_file") or ""
        if not text_file:
            continue
        path = Path(text_file)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue

        indexed_sources += 1
        for idx, (start, end, piece) in enumerate(_chunk_text(text), start=1):
            low_piece = piece.lower()
            hits = [term for term in focus_terms if term.lower() in low_piece][:8]
            rows.append({
                "chunk_id": f"{evidence.get('id', 'evidence')}-chunk-{idx:03d}",
                "evidence_id": evidence.get("id"),
                "source_url": evidence.get("url"),
                "fetch_url": evidence.get("fetch_url"),
                "title": evidence.get("title"),
                "source_title": evidence.get("source_title"),
                "source_role": evidence.get("source_role"),
                "source_bucket": evidence.get("source_bucket"),
                "kind": evidence.get("kind"),
                "canonical_doc_id": evidence.get("canonical_doc_id"),
                "repo_family_id": evidence.get("repo_family_id"),
                "normalized_repo_url": evidence.get("normalized_repo_url"),
                "repo_url": evidence.get("repo_url"),
                "why_extract": evidence.get("why_extract"),
                "fetch_method_planned": evidence.get("fetch_method_planned"),
                "fetch_method_used": evidence.get("fetch_method_used"),
                "content_type": evidence.get("content_type"),
                "text_file": text_file,
                "host": evidence.get("host"),
                "start_char": start,
                "end_char": end,
                "focus_hits": hits,
                "text": piece,
            })

    _jsonl_write(index_path, rows)
    report = {
        "status": "implemented_v1",
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "chunk_count": len(rows),
        "indexed_sources": indexed_sources,
        "chunking_policy": {
            "chars_per_chunk": CHUNK_SIZE,
            "overlap_chars": CHUNK_OVERLAP,
        },
        "retrieval_modes": [
            "lexical_local_jsonl",
        ],
        "focus_terms": focus_terms,
        "fields": [
            "chunk_id",
            "evidence_id",
            "source_url",
            "source_role",
            "source_bucket",
            "kind",
            "canonical_doc_id",
            "repo_family_id",
            "title",
            "source_title",
            "start_char",
            "end_char",
            "focus_hits",
            "text",
        ],
    }
    _write_json(report_path, report)
    return index_path, report_path, len(rows), indexed_sources


def run(artifact_dir: Path) -> int:
    context_path = artifact_dir / "context.json"
    sources_path = artifact_dir / "sources.json"
    provenance_path = artifact_dir / "provenance.json"

    if not context_path.exists():
        return 0

    context = _read_json(context_path, {})
    sources = _load_sources(sources_path)
    candidates = _candidate_rows(context, sources)
    if not candidates:
        return 0

    extracted_dir = artifact_dir / "extracted_texts"
    evidence_path = artifact_dir / "extracted_evidence.jsonl"
    report_path = artifact_dir / "fetch_extraction_report.json"
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    evidence_rows = []
    report = {
        "status": "implemented_v1",
        "generated_at": now,
        "candidate_count": len(candidates),
        "fetched_count": 0,
        "successful_count": 0,
        "items": [],
    }

    for idx, item in enumerate(candidates, start=1):
        url = item["url"]
        planned_method = _guess_fetch_method(url, item.get("fetch_method"))
        fetch_url = _github_raw(url)
        row = {
            "id": f"evidence-{idx:02d}",
            "url": url,
            "fetch_url": fetch_url,
            "title": item.get("title") or "",
            "source_title": item.get("source_title") or item.get("title") or "",
            "source_role": item.get("source_role") or "",
            "source_bucket": item.get("source_bucket") or "",
            "kind": item.get("kind") or "",
            "canonical_doc_id": item.get("canonical_doc_id") or url or item.get("title") or "",
            "repo_family_id": item.get("repo_family_id") or "",
            "normalized_repo_url": item.get("normalized_repo_url") or "",
            "repo_url": item.get("repo_url") or "",
            "why_extract": item.get("why_extract") or "",
            "fetch_method_planned": planned_method,
            "fetch_method_used": "",
            "host": urllib.parse.urlparse(url).netloc.lower(),
            "status": "pending",
            "content_type": "",
            "char_count": 0,
            "text_file": "",
            "excerpt": "",
            "extracted_at": now,
        }
        report["fetched_count"] += 1
        try:
            body, content_type, final_url = _download(fetch_url)
            row["fetch_url"] = final_url
            row["content_type"] = content_type
            lowered = content_type.lower()

            if planned_method == "pdf_text" or "application/pdf" in lowered or final_url.lower().endswith(".pdf"):
                text = _extract_pdf_text(body)
                row["fetch_method_used"] = "pdf_text"
                row["status"] = "ok" if text else "pdf_text_unavailable"
            elif any(x in lowered for x in ["text/plain", "text/markdown", "application/json", "application/xml"]):
                text = _decode_text(body, content_type)
                row["fetch_method_used"] = "raw_text"
                row["status"] = "ok"
            else:
                raw_html = _decode_text(body, content_type)
                text = _strip_html(raw_html)
                row["fetch_method_used"] = "html_readable"
                row["status"] = "ok" if text else "empty_text"

            text = (text or "").strip()
            if text:
                row["char_count"] = len(text)
                row["excerpt"] = text[:MAX_EXCERPT]
                row["text_file"] = _save_text(extracted_dir, idx, row["title"] or row["host"], text)
                if row["status"] == "ok":
                    report["successful_count"] += 1

            report["items"].append(dict(row))
            evidence_rows.append(row)

        except urllib.error.HTTPError as exc:
            row["status"] = f"http_error_{exc.code}"
            report["items"].append(dict(row))
            evidence_rows.append(row)
        except Exception as exc:
            row["status"] = "fetch_error"
            row["error"] = str(exc)[:300]
            report["items"].append(dict(row))
            evidence_rows.append(row)

    _jsonl_write(evidence_path, evidence_rows)
    _write_json(report_path, report)

    focus_terms = _load_focus_terms(context)
    index_path, index_report_path, chunk_count, indexed_sources = _build_evidence_index(
        artifact_dir=artifact_dir,
        evidence_rows=evidence_rows,
        focus_terms=focus_terms,
    )

    fetch_extraction = context.get("fetch_extraction") or {}
    fetch_extraction["status"] = "implemented_v1"
    fetch_extraction["scaffold_only"] = False
    fetch_extraction["extraction_backend"] = "urllib_stdlib"
    fetch_extraction["planned_candidates_count"] = len(candidates)
    fetch_extraction["extracted_evidence_file"] = str(evidence_path)
    fetch_extraction["extracted_text_dir"] = str(extracted_dir)
    fetch_extraction["fetch_extraction_report"] = str(report_path)
    fetch_extraction["successful_extractions"] = report["successful_count"]
    fetch_extraction["evidence_candidates"] = [
        {
            "evidence_id": row.get("id"),
            "url": row.get("url"),
            "title": row.get("title"),
            "source_role": row.get("source_role"),
            "source_bucket": row.get("source_bucket"),
            "kind": row.get("kind"),
            "canonical_doc_id": row.get("canonical_doc_id"),
            "repo_family_id": row.get("repo_family_id"),
            "status": row.get("status"),
            "char_count": row.get("char_count"),
        }
        for row in evidence_rows[:10]
    ]
    context["fetch_extraction"] = fetch_extraction

    evidence_index = context.get("evidence_index") or {}
    evidence_index["enabled"] = True
    evidence_index["strategy"] = "local_hybrid_evidence_v1"
    evidence_index["status"] = "implemented_v1"
    evidence_index["scaffold_only"] = False
    evidence_index["planned_store"] = "artifact_local_only"
    evidence_index["chunking_policy"] = {
        "chars_per_chunk": CHUNK_SIZE,
        "overlap_chars": CHUNK_OVERLAP,
    }
    evidence_index["retrieval_modes"] = [
        "lexical_local_jsonl",
    ]
    evidence_index["index_fields"] = [
        "chunk_id",
        "evidence_id",
        "source_url",
        "source_role",
        "source_bucket",
        "kind",
        "canonical_doc_id",
        "repo_family_id",
        "title",
        "source_title",
        "start_char",
        "end_char",
        "focus_hits",
        "text",
    ]
    evidence_index["index_focus"] = focus_terms
    evidence_index["evidence_index_file"] = str(index_path)
    evidence_index["evidence_index_report"] = str(index_report_path)
    evidence_index["chunk_count"] = chunk_count
    evidence_index["indexed_sources"] = indexed_sources
    evidence_index["evidence_candidates"] = [
        {
            "evidence_id": row.get("id"),
            "url": row.get("url"),
            "title": row.get("title"),
            "source_role": row.get("source_role"),
            "source_bucket": row.get("source_bucket"),
            "kind": row.get("kind"),
            "canonical_doc_id": row.get("canonical_doc_id"),
            "repo_family_id": row.get("repo_family_id"),
            "status": row.get("status"),
            "char_count": row.get("char_count"),
        }
        for row in evidence_rows[:10]
    ]
    context["evidence_index"] = evidence_index

    architecture_layers = context.get("architecture_layers")
    if isinstance(architecture_layers, dict):
        architecture_layers["layer3_fetch_extraction"] = {
            "status": "implemented_v1",
            "scaffold_only": False,
            "candidate_count": len(candidates),
            "successful_extractions": report["successful_count"],
            "extraction_backend": "urllib_stdlib",
        }
        architecture_layers["layer4_evidence_index"] = {
            "status": "implemented_v1",
            "scaffold_only": False,
            "chunk_count": chunk_count,
            "indexed_sources": indexed_sources,
            "retrieval_modes": ["lexical_local_jsonl"],
        }
        context["architecture_layers"] = architecture_layers

    _write_json(context_path, context)

    provenance = _read_json(provenance_path, {})
    if isinstance(provenance, dict):
        provenance["fetch_extraction_report"] = str(report_path)
        provenance["extracted_evidence_file"] = str(evidence_path)
        provenance["evidence_index_file"] = str(index_path)
        provenance["evidence_index_report"] = str(index_report_path)
        _write_json(provenance_path, provenance)

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step18.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
