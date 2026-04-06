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

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) project-research-step17/1.0"
MAX_CANDIDATES = 4
MAX_BYTES = 2_000_000
MAX_EXCERPT = 4000

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

def _candidate_rows(context: dict, sources) -> list[dict]:
    rows: list[dict] = []
    fetch_extraction = context.get("fetch_extraction") or {}
    planned = fetch_extraction.get("planned_candidates") or []
    for item in planned:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("source_url") or item.get("link")
        if not url:
            continue
        rows.append({
            "url": str(url),
            "title": item.get("title") or item.get("label") or "",
            "source_role": item.get("source_role") or item.get("role") or "",
            "fetch_method": item.get("fetch_method") or item.get("fetch_method_hint") or "",
        })
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
            url = item.get("url") or item.get("source_url") or item.get("link")
            if not url:
                continue
            rows.append({
                "url": str(url),
                "title": item.get("title") or item.get("name") or "",
                "source_role": item.get("source_role") or item.get("role") or "",
                "fetch_method": item.get("fetch_method") or "",
            })
    dedup = {}
    for row in rows:
        dedup[row["url"]] = row
    return list(dedup.values())[:MAX_CANDIDATES]

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

def run(artifact_dir: Path) -> int:
    context_path = artifact_dir / "context.json"
    sources_path = artifact_dir / "sources.json"
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
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

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
            "source_role": item.get("source_role") or "",
            "fetch_method_planned": planned_method,
            "fetch_method_used": "",
            "host": urllib.parse.urlparse(url).netloc,
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

    fetch_extraction = context.get("fetch_extraction") or {}
    fetch_extraction["status"] = "implemented_v1"
    fetch_extraction["scaffold_only"] = False
    fetch_extraction["extraction_backend"] = "urllib_stdlib"
    fetch_extraction["planned_candidates_count"] = len(candidates)
    fetch_extraction["extracted_evidence_file"] = str(evidence_path)
    fetch_extraction["extracted_text_dir"] = str(extracted_dir)
    fetch_extraction["fetch_extraction_report"] = str(report_path)
    fetch_extraction["successful_extractions"] = report["successful_count"]
    context["fetch_extraction"] = fetch_extraction

    architecture_layers = context.get("architecture_layers")
    if isinstance(architecture_layers, dict):
        layer = architecture_layers.get("layer3_fetch_extraction")
        if isinstance(layer, dict):
            layer["status"] = "implemented_v1"
            layer["scaffold_only"] = False
            layer["successful_extractions"] = report["successful_count"]
        else:
            architecture_layers["layer3_fetch_extraction"] = {
                "status": "implemented_v1",
                "scaffold_only": False,
                "successful_extractions": report["successful_count"],
            }
        context["architecture_layers"] = architecture_layers

    _write_json(context_path, context)
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: project-research-fetch-extract-step17.py <artifact_dir>")
    raise SystemExit(run(Path(sys.argv[1])))
