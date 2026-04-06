#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {
    "name": "graphmem-readonly",
    "version": "0.1.2",
}
GRAPHMEM_BIN = Path("/home/agent/bin/graphmem")
GRAPHMEM_RECALL_BIN = Path("/home/agent/bin/graphmem-recall")
MAX_RECALL_QUERY_LEN = 200
MAX_GROUNDING_FILE_BYTES = 200_000
MAX_GROUNDING_CANDIDATES = 3


class ServerError(Exception):
    def __init__(self, message: str, *, code: int = -32000, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


def emit(message: dict) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def emit_result(request_id, result: dict) -> None:
    emit({"jsonrpc": "2.0", "id": request_id, "result": result})


def emit_error(request_id, code: int, message: str, data=None) -> None:
    payload = {"code": code, "message": message}
    if data is not None:
        payload["data"] = data
    emit({"jsonrpc": "2.0", "id": request_id, "error": payload})


def tool_content(text: str) -> list[dict]:
    return [{"type": "text", "text": text}]


def base_child_env() -> dict:
    child_env = {}
    for key in ("HOME", "LANG", "LC_ALL", "PATH"):
        value = os.environ.get(key)
        if value:
            child_env[key] = value
    return child_env


def discover_neo4j_auth() -> dict:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise ServerError("docker is required for auth discovery")

    proc = subprocess.run(
        [docker_bin, "inspect", "ai-neo4j", "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ServerError("failed to inspect ai-neo4j for ephemeral auth discovery")

    auth = None
    for line in proc.stdout.splitlines():
        if line.startswith("NEO4J_AUTH="):
            auth = line.split("=", 1)[1]
            break

    if not auth or "/" not in auth:
        raise ServerError("NEO4J_AUTH was not found on ai-neo4j")

    user, password = auth.split("/", 1)
    if not user or not password:
        raise ServerError("NEO4J_AUTH on ai-neo4j is incomplete")

    env = base_child_env()
    env["NEO4J_URI"] = "bolt://127.0.0.1:7687"
    env["NEO4J_USER"] = user
    env["NEO4J_PASS"] = password
    return env


def run_graph_command(argv: list[str]) -> str:
    env = discover_neo4j_auth()
    proc = subprocess.run(argv, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise ServerError(stderr or "graphmem command failed")
    return (proc.stdout or "").strip()


def parse_graph_stats(text: str) -> dict:
    counts = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = label.strip()
        value = value.strip()
        if not label or not value:
            continue
        try:
            counts[label] = int(value)
        except ValueError:
            counts[label] = value
    return counts


def run_graph_stats() -> dict:
    output = run_graph_command([str(GRAPHMEM_BIN), "stats"])
    counts = parse_graph_stats(output)
    return {
        "content": tool_content(output),
        "structuredContent": {
            "counts": counts,
            "surface": "graph_stats",
        },
        "isError": False,
    }


def sanitize_recall_query(arguments: dict) -> str:
    query = arguments.get("query", "")
    if not isinstance(query, str):
        raise ServerError("graph_recall requires a string `query` argument", code=-32602)

    query = " ".join(query.split())
    if not query:
        raise ServerError("graph_recall requires a non-empty `query` argument", code=-32602)
    if len(query) > MAX_RECALL_QUERY_LEN:
        raise ServerError(
            f"graph_recall query exceeds max length of {MAX_RECALL_QUERY_LEN}",
            code=-32602,
        )
    return query


def tokenize_text(value: str) -> list[str]:
    return [token for token in re.split(r"[^0-9a-zа-яё]+", (value or "").lower()) if len(token) >= 2]


def normalize_text(value: str) -> str:
    return " ".join(tokenize_text(value))


def build_needles(value: str) -> list[str]:
    needles = []
    raw = (value or "").strip().lower()
    normalized = normalize_text(raw)

    for candidate in (raw, normalized):
        if candidate and candidate not in needles:
            needles.append(candidate)

    for suffix in ("/tcp", "/udp"):
        if raw.endswith(suffix):
            stripped = raw[: -len(suffix)].strip()
            if stripped and stripped not in needles:
                needles.append(stripped)

    for token in tokenize_text(raw):
        if token not in needles:
            needles.append(token)

    return needles


def classify_needles(text: str, needles: list[str]) -> tuple[str, list[str]]:
    if not needles:
        return "none", []

    lowered = (text or "").lower()
    normalized = normalize_text(text)
    matched = []

    for needle in needles:
        if not needle:
            continue
        if needle in lowered or needle in normalized:
            matched.append(needle)

    if not matched:
        return "none", []

    exact_preferred = [
        needle
        for needle in needles[:3]
        if (" " in needle or ":" in needle or "." in needle or "-" in needle or "/" in needle or needle.isdigit())
    ]
    if any(needle in matched for needle in exact_preferred):
        return "exact", matched

    full_needles = [needle for needle in needles if " " in needle or ":" in needle or "." in needle]
    token_needles = [needle for needle in needles if needle not in full_needles]

    if any(needle in matched for needle in full_needles):
        return "exact", matched
    if token_needles and all(token in matched for token in token_needles):
        return "exact", matched
    return "partial", matched


def describe_match(kind: str, matched: list[str]) -> str:
    if kind == "exact":
        return f"exact match via {', '.join(matched[:3])}"
    if kind == "partial":
        return f"partial match via {', '.join(matched[:3])}"
    return "no textual match"


def read_grounding_text(path: Path) -> str:
    try:
        if not path.is_file() or path.stat().st_size > MAX_GROUNDING_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def is_filtered_payload_source(path: Path) -> bool:
    raw = str(path)
    if "/artifacts/" in raw:
        return True
    return path.name == "index.md" and path.parent.name == "memory" and raw.startswith("/home/agent/agents/")


def evaluate_source_file(path: Path, subject: str, object_value: str) -> dict:
    text = read_grounding_text(path)
    exists = path.exists()
    subject_kind, subject_hits = classify_needles(text, build_needles(subject))
    object_kind, object_hits = classify_needles(text, build_needles(object_value))

    if subject_kind == "exact" and object_kind == "exact":
        tier = "authoritative-text"
    elif subject_kind != "none" and object_kind != "none":
        tier = "supporting-text"
    else:
        tier = "unconfirmed"

    return {
        "path": str(path),
        "exists": exists,
        "tier": tier,
        "subject_match": subject_kind,
        "object_match": object_kind,
        "reason": (
            f"subject={describe_match(subject_kind, subject_hits)}; "
            f"object={describe_match(object_kind, object_hits)}"
        ),
    }


def build_filtered_source_record(path: Path, exists: bool) -> dict:
    return {
        "path": "[filtered-derived-source]",
        "exists": exists,
        "tier": "unconfirmed",
        "subject_match": "filtered",
        "object_match": "filtered",
        "reason": "suppressed derived source path; not returned as textual grounding source",
    }


def collect_grounding_candidates(declared_source: str, subject: str, object_value: str) -> dict:
    path = Path(declared_source) if declared_source else None
    declared = None
    declared_allowed = False
    candidates = []

    if path is not None:
        evaluated_declared = evaluate_source_file(path, subject, object_value)
        if is_filtered_payload_source(path):
            declared = build_filtered_source_record(path, evaluated_declared["exists"])
        else:
            declared = evaluated_declared
            declared_allowed = declared["tier"] in {"authoritative-text", "supporting-text"}
        if path.parent.exists():
            for sibling in sorted(path.parent.iterdir()):
                if sibling == path or not sibling.is_file():
                    continue
                if sibling.suffix.lower() not in {".md", ".txt", ".json"}:
                    continue
                if is_filtered_payload_source(sibling):
                    continue
                candidate = evaluate_source_file(sibling, subject, object_value)
                if candidate["tier"] == "unconfirmed":
                    continue
                candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            {"authoritative-text": 2, "supporting-text": 1}.get(item["tier"], 0),
            item["path"],
        ),
        reverse=True,
    )
    candidates = candidates[:MAX_GROUNDING_CANDIDATES]

    best = declared if declared_allowed else None
    for candidate in candidates:
        if best is None:
            best = candidate
            continue
        if {"authoritative-text": 2, "supporting-text": 1}.get(candidate["tier"], 0) > {
            "authoritative-text": 2,
            "supporting-text": 1,
        }.get(best["tier"], 0):
            best = candidate

    grounding_tier = "graph-only"
    if best is not None and best["tier"] in {"authoritative-text", "supporting-text"}:
        grounding_tier = best["tier"]

    return {
        "declared_source": declared,
        "supporting_sources": candidates,
        "best_source": best,
        "grounding_tier": grounding_tier,
    }


def parse_graph_recall_output(text: str) -> dict:
    query = ""
    matched_entities = []
    relations = []
    section = None

    relation_pattern = re.compile(
        r"^- (?P<subject>.+?) --(?P<relation>[A-Z0-9_]+)--> (?P<object>.+?)  "
        r"\(conf=(?P<confidence>[^,]+), src=(?P<source>.*)\)$"
    )
    entity_pattern = re.compile(r"^- (?P<type>.+?) :: (?P<name>.+?)  \((?P<key>.+?)\)$")

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        if line.startswith("- query:"):
            query = line.split(":", 1)[1].strip().strip("'")
            continue
        if line == "## Matched entities":
            section = "entities"
            continue
        if line == "## Relations (1-hop)":
            section = "relations"
            continue
        if not line.startswith("- "):
            continue

        if section == "entities":
            match = entity_pattern.match(line)
            if match:
                matched_entities.append(match.groupdict())
            continue

        if section == "relations":
            match = relation_pattern.match(line)
            if not match:
                continue
            data = match.groupdict()
            confidence_value = data["confidence"]
            try:
                confidence = float(confidence_value)
            except ValueError:
                confidence = None
            relations.append(
                {
                    "subject": data["subject"],
                    "relation": data["relation"],
                    "object": data["object"],
                    "confidence": confidence,
                    "declared_source": data["source"],
                }
            )

    return {
        "query": query,
        "matched_entities": matched_entities,
        "relations": relations,
    }


def enrich_graph_recall(parsed: dict) -> dict:
    enriched_relations = []
    counts = {
        "authoritative-text": 0,
        "supporting-text": 0,
        "graph-only": 0,
    }

    for relation in parsed["relations"]:
        grounding = collect_grounding_candidates(
            relation["declared_source"],
            relation["subject"],
            relation["object"],
        )
        counts[grounding["grounding_tier"]] += 1
        enriched = dict(relation)
        best_source = grounding["best_source"]
        enriched["declared_source"] = best_source["path"] if best_source is not None else None
        enriched["grounding"] = grounding
        enriched_relations.append(enriched)

    return {
        "query": parsed["query"],
        "matched_entities": parsed["matched_entities"],
        "relations": enriched_relations,
        "grounding_counts": counts,
    }


def format_confidence(value) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return "?"


def format_relation_source(value) -> str:
    return value or "graph-only"


def format_sanitized_raw_output(enriched: dict) -> str:
    lines = ["# Graph recall", f"- query: {enriched['query']!r}", ""]

    if enriched["matched_entities"]:
        lines.append("## Matched entities")
        for entity in enriched["matched_entities"]:
            lines.append(f"- {entity['type']} :: {entity['name']}  ({entity['key']})")
        lines.append("")

    lines.append("## Relations (1-hop)")
    for relation in enriched["relations"]:
        lines.append(
            "- {subject} --{relation_name}--> {object_value}  (conf={confidence}, src={source})".format(
                subject=relation["subject"],
                relation_name=relation["relation"],
                object_value=relation["object"],
                confidence=format_confidence(relation["confidence"]),
                source=format_relation_source(relation["declared_source"]),
            )
        )
    return "\n".join(lines)


def format_graph_recall_text(enriched: dict) -> str:
    lines = ["# Graph recall", f"- query: {enriched['query']!r}", ""]
    counts = enriched["grounding_counts"]
    lines.append("## Grounding summary")
    lines.append(
        "- authoritative-text={authoritative}; supporting-text={supporting}; graph-only={graph_only}".format(
            authoritative=counts["authoritative-text"],
            supporting=counts["supporting-text"],
            graph_only=counts["graph-only"],
        )
    )
    lines.append("")

    if enriched["matched_entities"]:
        lines.append("## Matched entities")
        for entity in enriched["matched_entities"]:
            lines.append(f"- {entity['type']} :: {entity['name']}  ({entity['key']})")
        lines.append("")

    lines.append("## Relations (1-hop)")
    for relation in enriched["relations"]:
        lines.append(
            "- {subject} --{relation_name}--> {object_value}  (conf={confidence}, src={source})".format(
                subject=relation["subject"],
                relation_name=relation["relation"],
                object_value=relation["object"],
                confidence=format_confidence(relation["confidence"]),
                source=format_relation_source(relation["declared_source"]),
            )
        )
    lines.append("")

    lines.append("## Provenance review")
    for relation in enriched["relations"]:
        grounding = relation["grounding"]
        declared = grounding["declared_source"]
        best = grounding["best_source"]
        declared_summary = "declared_src=none"
        if declared is not None:
            declared_summary = (
                f"declared_src={declared['path']} "
                f"[{declared['tier']}; {declared['reason']}]"
            )
        best_summary = "best_local_src=none"
        if best is not None:
            best_summary = (
                f"best_local_src={best['path']} "
                f"[{best['tier']}; {best['reason']}]"
            )
        lines.append(
            "- {subject} --{relation_name}--> {object_value} | grounding={tier} | {declared} | {best}".format(
                subject=relation["subject"],
                relation_name=relation["relation"],
                object_value=relation["object"],
                tier=grounding["grounding_tier"],
                declared=declared_summary,
                best=best_summary,
            )
        )

    return "\n".join(lines)


def run_graph_recall(arguments: dict) -> dict:
    query = sanitize_recall_query(arguments)
    output = run_graph_command([str(GRAPHMEM_RECALL_BIN), query])
    parsed = parse_graph_recall_output(output)
    enriched = enrich_graph_recall(parsed)
    enriched_text = format_graph_recall_text(enriched)
    sanitized_raw_output = format_sanitized_raw_output(enriched)
    return {
        "content": tool_content(enriched_text),
        "structuredContent": {
            "query": query,
            "surface": "graph_recall",
            "raw_output": sanitized_raw_output,
            "matched_entities": enriched["matched_entities"],
            "relations": enriched["relations"],
            "grounding_counts": enriched["grounding_counts"],
        },
        "isError": False,
    }


def build_tools() -> list[dict]:
    return [
        {
            "name": "graph_stats",
            "description": "Return bounded read-only graph counts from local graphmem.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
            },
        },
        {
            "name": "graph_recall",
            "description": "Return bounded read-only graph recall text for one query string.",
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_RECALL_QUERY_LEN,
                        "description": "One bounded recall query for graphmem-readonly.",
                    }
                },
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
            },
        },
    ]


TOOLS = {tool["name"]: tool for tool in build_tools()}


def handle_tools_call(params: dict) -> dict:
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}
    if tool_name not in TOOLS:
        raise ServerError(f"unknown tool: {tool_name}", code=-32602)
    if not isinstance(arguments, dict):
        raise ServerError("tool arguments must be an object", code=-32602)
    if tool_name == "graph_stats":
        if arguments:
            raise ServerError("graph_stats does not accept arguments", code=-32602)
        return run_graph_stats()
    if tool_name == "graph_recall":
        return run_graph_recall(arguments)
    raise ServerError(f"unsupported tool: {tool_name}", code=-32602)


def handle_request(method: str, params: dict, state: dict) -> dict:
    if method == "initialize":
        state["server_initialized"] = True
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                }
            },
            "serverInfo": SERVER_INFO,
            "instructions": (
                "This topic-local MCP server is read-only. "
                "Only graph_stats and graph_recall are exposed."
            ),
        }

    if not state["server_initialized"] or not state["session_ready"]:
        raise ServerError(
            "server is not initialized; call initialize then notifications/initialized first",
            code=-32002,
        )

    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": list(TOOLS.values())}
    if method == "tools/call":
        return handle_tools_call(params)
    raise ServerError(f"method not found: {method}", code=-32601)


def main() -> int:
    state = {"server_initialized": False, "session_ready": False}

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            emit_error(None, -32700, "parse error", {"detail": str(exc)})
            continue

        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}

        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not method:
            emit_error(request_id, -32600, "invalid request")
            continue

        if request_id is None:
            if method == "notifications/initialized":
                state["session_ready"] = True
            continue

        try:
            result = handle_request(method, params, state)
        except ServerError as exc:
            emit_error(request_id, exc.code, str(exc), exc.data)
            continue
        except Exception:
            emit_error(request_id, -32603, "internal error")
            continue

        emit_result(request_id, result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
