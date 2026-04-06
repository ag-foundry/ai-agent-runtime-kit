#!/usr/bin/env python3
"""Natural-language AI meta-launcher for server-wide managed workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import launch_managed_workflow as managed


AI_META_CLASSIFICATION_FORMAT = "openclaw-ai-meta-classification-v1"
AI_META_MANIFEST_FORMAT = "openclaw-ai-meta-launch-manifest-v1"
AI_META_TRACE_FORMAT = "openclaw-ai-meta-launch-trace-v1"
CODEX_FRONTDOOR_CONTRACT_FORMAT = "openclaw-codex-frontdoor-contract-v1"
SYSTEM_ROOT_NAMES = {"_runtime", "_shared"}
MANAGED_BACKEND_INTENTS = {
    "historical_review",
    "current_run_review",
    "readiness_review",
    "compare_runs",
    "clean_rerun",
    "canonical_managed_eval",
    "promotion_preview",
    "topic_bootstrap",
    "topic_migration",
}
STRUCTURAL_INTENTS = {
    "clean_rerun",
    "canonical_managed_eval",
    "promotion_preview",
    "topic_bootstrap",
    "topic_migration",
}


def definition_root() -> Path:
    return managed.definition_root()


def registry_path() -> Path:
    return managed.global_policy_registry_path()


def schema_path() -> Path:
    return definition_root() / "ai-meta-launcher-classification-schema-v1.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    managed.write_json(path, payload)


def write_text(path: Path, content: str) -> None:
    managed.write_text(path, content)


def slugify(text: str, *, fallback: str = "request") -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower()).strip("-")
    return value[:80] or fallback


def now_stamp() -> str:
    return managed.now_utc_iso().replace(":", "").replace("+00:00", "Z")


def latest_run_roots(topic_root: Path) -> list[Path]:
    runs_dir = topic_root / "runs"
    if not runs_dir.is_dir():
        return []
    candidates = [path for path in runs_dir.iterdir() if path.is_dir()]
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def newest_run_with_file(topic_root: Path, relative_path: str) -> Path | None:
    for run_root in latest_run_roots(topic_root):
        if (run_root / relative_path).exists():
            return run_root
    return None


def is_reviewable_run_root(run_root: Path) -> bool:
    return any(
        [
            (run_root / "REPORT.md").exists(),
            (run_root / "VERDICT.md").exists(),
            (run_root / "RESULT-MATRIX.md").exists(),
            (run_root / "summaries" / "review-pack-manifest.json").exists(),
            (run_root / "summaries" / "trial-plan.json").exists(),
            any((run_root / "results").glob("*-review.md")),
        ]
    )


def reviewable_run_roots(topic_root: Path) -> list[Path]:
    return [run_root for run_root in latest_run_roots(topic_root) if is_reviewable_run_root(run_root)]


def search_case_file(topic_root: Path, case_hint: str | None) -> Path | None:
    if not case_hint:
        return None
    normalized = case_hint.strip().lower()
    candidates: list[Path] = []
    for run_root in latest_run_roots(topic_root)[:25]:
        for case_path in (run_root / "cases").glob("*.md"):
            stem = case_path.stem.lower()
            if normalized == stem or normalized in stem:
                candidates.append(case_path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def list_topic_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(managed.agents_root().iterdir(), key=lambda item: item.name.lower()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        run_roots = latest_run_roots(path)
        inventory.append(
            {
                "name": path.name,
                "path": str(path.resolve()),
                "kind": "system_root" if path.name in SYSTEM_ROOT_NAMES else "topic_root",
                "managed_defaults": (path / "managed-defaults.json").exists(),
                "agents_hook": (path / "AGENTS.md").exists(),
                "readme_hook": (path / "README.md").exists(),
                "run_count": len(run_roots),
                "latest_run": str(run_roots[0]) if run_roots else None,
            }
        )
    return inventory


def topic_lookup(inventory: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in inventory}


def topic_from_name(name: str | None, inventory_by_name: dict[str, dict[str, Any]]) -> Path | None:
    if not name:
        return None
    record = inventory_by_name.get(name)
    if not record:
        return None
    return Path(record["path"]).resolve()


def topic_matches_from_request(request: str, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lowered = request.lower()
    matches: list[dict[str, Any]] = []
    for item in inventory:
        if item["kind"] != "topic_root":
            continue
        topic_name = item["name"].lower()
        if re.search(rf"(?<![a-z0-9_-]){re.escape(topic_name)}(?![a-z0-9_-])", lowered):
            matches.append(item)
    return matches


def infer_topic_root_from_request(request: str, inventory: list[dict[str, Any]]) -> Path | None:
    matches = topic_matches_from_request(request, inventory)
    if len(matches) == 1:
        return Path(matches[0]["path"]).resolve()
    return None


def request_has_any(request: str, phrases: list[str] | tuple[str, ...]) -> bool:
    lowered = request.lower()
    return any(phrase in lowered for phrase in phrases)


def infer_scope_class(
    *,
    request: str,
    intent_class: str,
    inventory: list[dict[str, Any]],
    topic_candidate: str | None,
) -> str:
    lowered = request.lower()
    topic_matches = topic_matches_from_request(request, inventory) if request else []
    if intent_class in {"topic_bootstrap", "topic_migration", "current_state_lookup"}:
        return "global_server"
    if len(topic_matches) > 1:
        return "cross_topic"
    if any(word in lowered for word in ["global", "server", "сервер", "router", "роутер", "receiver", "ресивер", "vpn"]):
        return "global_server"
    if any(word in lowered for word in ["cross-topic", "cross topic", "межпроект", "mcp"]) or topic_candidate is None:
        if intent_class in {"research_request", "general_project_analysis"}:
            return "cross_topic"
    return "single_topic"


def infer_complexity(*, request: str, intent_class: str) -> str:
    lowered = request.lower()
    if intent_class in {"canonical_managed_eval", "promotion_preview", "topic_migration"}:
        return "high"
    if intent_class == "current_state_lookup" and len(request.split()) <= 6:
        return "low"
    if any(
        word in lowered
        for word in [
            "deep",
            "глуб",
            "full audit",
            "полный аудит",
            "architecture",
            "архитект",
            "migration",
            "миграц",
            "bootstrap",
            "promotion",
            "adoption",
            "clean rerun",
            "многоход",
            "end-to-end",
        ]
    ):
        return "high"
    if intent_class in MANAGED_BACKEND_INTENTS | {"research_request", "general_project_analysis"}:
        return "medium"
    return "low"


def infer_depth(*, request: str, intent_class: str) -> str:
    lowered = request.lower()
    if intent_class in {"canonical_managed_eval", "promotion_preview", "topic_migration", "research_request"} and any(
        word in lowered for word in ["deep", "глуб", "full", "полно", "comprehensive", "архитект", "end-to-end"]
    ):
        return "deep"
    if intent_class in {"canonical_managed_eval", "promotion_preview", "topic_migration"}:
        return "deep"
    if intent_class in MANAGED_BACKEND_INTENTS | {"research_request", "general_project_analysis"}:
        return "medium"
    return "shallow"


def infer_risk_level(*, request: str, intent_class: str, operation_mode: str) -> str:
    lowered = request.lower()
    if operation_mode == "workspace_write" or intent_class in STRUCTURAL_INTENTS:
        return "high"
    if any(word in lowered for word in ["server", "сервер", "router", "роутер", "receiver", "ресивер", "vpn", "override"]):
        return "high"
    return "low"


def infer_substantiality(*, intent_class: str, complexity: str, depth: str) -> str:
    if intent_class in MANAGED_BACKEND_INTENTS | {"research_request", "general_project_analysis"}:
        return "substantial"
    if complexity != "low" or depth != "shallow":
        return "substantial"
    return "lightweight"


def build_classification(
    *,
    request: str,
    inventory: list[dict[str, Any]],
    intent_class: str,
    confidence: str,
    topic_candidate: str | None,
    topic_name_candidate: str | None,
    case_id_candidate: str | None,
    run_reference_hint: str,
    operation_mode: str,
    research_mode: str,
    routing_rationale: list[str],
    needs_clarification: bool = False,
    clarification_reason: str | None = None,
    substantiality: str | None = None,
    complexity: str | None = None,
    depth: str | None = None,
    risk_level: str | None = None,
    scope_class: str | None = None,
) -> dict[str, Any]:
    resolved_complexity = complexity or infer_complexity(request=request, intent_class=intent_class)
    resolved_depth = depth or infer_depth(request=request, intent_class=intent_class)
    resolved_scope = scope_class or infer_scope_class(
        request=request,
        intent_class=intent_class,
        inventory=inventory,
        topic_candidate=topic_candidate,
    )
    resolved_risk = risk_level or infer_risk_level(
        request=request,
        intent_class=intent_class,
        operation_mode=operation_mode,
    )
    resolved_substantiality = substantiality or infer_substantiality(
        intent_class=intent_class,
        complexity=resolved_complexity,
        depth=resolved_depth,
    )
    return {
        "intent_class": intent_class,
        "confidence": confidence,
        "substantiality": resolved_substantiality,
        "complexity": resolved_complexity,
        "depth": resolved_depth,
        "risk_level": resolved_risk,
        "scope_class": resolved_scope,
        "topic_candidate": topic_candidate,
        "topic_name_candidate": topic_name_candidate,
        "case_id_candidate": case_id_candidate,
        "run_reference_hint": run_reference_hint,
        "operation_mode": operation_mode,
        "research_mode": research_mode,
        "needs_clarification": needs_clarification,
        "clarification_reason": clarification_reason,
        "routing_rationale": routing_rationale,
    }


def explicit_classification(args: argparse.Namespace, request: str | None) -> dict[str, Any] | None:
    operation_mode = "workspace_write" if args.write_mode == "edit" else "read_only"
    if args.compat_topic and not request:
        return build_classification(
            request=request or "",
            inventory=list_topic_inventory(),
            intent_class="general_project_analysis",
            confidence="high",
            topic_candidate=args.compat_topic,
            topic_name_candidate=None,
            case_id_candidate=args.case_id,
            run_reference_hint="explicit",
            operation_mode=operation_mode,
            research_mode="none",
            routing_rationale=["explicit compatibility topic execution was requested without a natural-language task"],
        )
    if args.force_intent_class:
        return build_classification(
            request=request or "",
            inventory=list_topic_inventory(),
            intent_class=args.force_intent_class,
            confidence="high",
            topic_candidate=args.topic,
            topic_name_candidate=args.topic_name,
            case_id_candidate=args.case_id,
            run_reference_hint="explicit",
            operation_mode=operation_mode,
            research_mode=args.research_mode_override or "none",
            routing_rationale=[f"forced intent class `{args.force_intent_class}` was requested"],
        )
    if args.topic_name and not args.topic_root:
        return build_classification(
            request=request or args.topic_name,
            inventory=list_topic_inventory(),
            intent_class="topic_bootstrap",
            confidence="high",
            topic_candidate=None,
            topic_name_candidate=args.topic_name,
            case_id_candidate=None,
            run_reference_hint="explicit",
            operation_mode="workspace_write",
            research_mode="none",
            routing_rationale=["topic name was provided explicitly"],
        )
    if args.topic_root:
        intent = "topic_migration" if any(word in (request or "").lower() for word in ["migr", "migration", "перевед", "мигр"]) else "general_project_analysis"
        return build_classification(
            request=request or args.topic_root,
            inventory=list_topic_inventory(),
            intent_class=intent,
            confidence="high",
            topic_candidate=Path(args.topic_root).name,
            topic_name_candidate=None,
            case_id_candidate=None,
            run_reference_hint="explicit",
            operation_mode="workspace_write" if intent == "topic_migration" else operation_mode,
            research_mode="none",
            routing_rationale=["topic root path was provided explicitly"],
        )
    if args.case_path:
        return build_classification(
            request=request or args.case_path,
            inventory=list_topic_inventory(),
            intent_class="clean_rerun",
            confidence="high",
            topic_candidate=args.topic,
            topic_name_candidate=None,
            case_id_candidate=Path(args.case_path).stem,
            run_reference_hint="explicit",
            operation_mode=operation_mode,
            research_mode="none",
            routing_rationale=["explicit case path was provided"],
        )
    if args.run_root and (args.readiness_mode_override or any(word in (request or "").lower() for word in ["готовност", "readiness"])):
        return build_classification(
            request=request or args.run_root,
            inventory=list_topic_inventory(),
            intent_class="readiness_review",
            confidence="high",
            topic_candidate=args.topic,
            topic_name_candidate=None,
            case_id_candidate=None,
            run_reference_hint="explicit",
            operation_mode=operation_mode,
            research_mode="none",
            routing_rationale=["explicit run root plus readiness signal was detected"],
        )
    if args.compare_target or ("сравн" in (request or "").lower()):
        return build_classification(
            request=request or "compare",
            inventory=list_topic_inventory(),
            intent_class="compare_runs",
            confidence="high" if args.compare_target else "medium",
            topic_candidate=args.topic,
            topic_name_candidate=None,
            case_id_candidate=None,
            run_reference_hint="explicit" if args.review_run_root else "latest",
            operation_mode=operation_mode,
            research_mode="none",
            routing_rationale=["explicit compare target or compare intent was detected"],
        )
    if args.review_run_root:
        if any(word in (request or "").lower() for word in ["готовност", "readiness"]):
            intent = "readiness_review"
        else:
            intent = "current_run_review" if any(word in (request or "").lower() for word in ["последн", "текущ", "current", "latest"]) else "historical_review"
        return build_classification(
            request=request or args.review_run_root,
            inventory=list_topic_inventory(),
            intent_class=intent,
            confidence="high",
            topic_candidate=args.topic,
            topic_name_candidate=None,
            case_id_candidate=None,
            run_reference_hint="explicit",
            operation_mode=operation_mode,
            research_mode="none",
            routing_rationale=["explicit review run root was provided"],
        )
    if args.promotion_run_root or args.case_set_id:
        return build_classification(
            request=request or (args.promotion_run_root or args.case_set_id or "promotion"),
            inventory=list_topic_inventory(),
            intent_class="promotion_preview",
            confidence="high",
            topic_candidate=args.topic,
            topic_name_candidate=None,
            case_id_candidate=None,
            run_reference_hint="explicit",
            operation_mode=operation_mode,
            research_mode="none",
            routing_rationale=["promotion inputs were provided explicitly"],
        )
    return None


def deterministic_fallback(args: argparse.Namespace, request: str, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    lowered = request.lower()
    topic_root = infer_topic_root_from_request(request, inventory)
    topic_name = topic_root.name if topic_root else (args.topic or args.compat_topic)
    intent = "general_project_analysis"
    research_mode = "none"
    run_reference_hint = "none"

    if any(word in lowered for word in ["исслед", "research", "разберись как устроен", "подними память и предложи следующий шаг"]):
        intent = "research_request"
        research_mode = args.research_mode_override or ("deep" if any(word in lowered for word in ["глуб", "deep"]) else "quick")
    elif any(word in lowered for word in ["current state", "текущее состояние", "статус сервера", "current project state"]):
        intent = "current_state_lookup"
    elif any(word in lowered for word in ["создай новую тему", "новую тему", "new topic", "new project"]):
        intent = "topic_bootstrap"
    elif any(word in lowered for word in ["мигрир", "migration", "переведи старую тему"]):
        intent = "topic_migration"
    elif any(word in lowered for word in ["promotion", "adoption", "промо", "acceptance preview"]):
        intent = "promotion_preview"
        run_reference_hint = "latest"
    elif any(word in lowered for word in ["оцени готовность", "evaluate readiness", "readiness only", "readiness review", "готовность линии"]):
        intent = "readiness_review"
        run_reference_hint = "latest"
    elif any(word in lowered for word in ["clean rerun", "чистый rerun", "contamination", "чистый перезапуск"]):
        intent = "clean_rerun"
    elif any(word in lowered for word in ["broader eval", "managed eval", "оцени готовность линии", "запусти broader eval"]):
        intent = "canonical_managed_eval"
        run_reference_hint = "latest"
    elif any(word in lowered for word in ["сравни", "compare", "old vs new", "до и после"]):
        intent = "compare_runs"
        run_reference_hint = "latest"
    elif any(word in lowered for word in ["проверь последний прогон", "последний прогон", "current run", "latest run"]):
        intent = "current_run_review"
        run_reference_hint = "latest"
    elif any(word in lowered for word in ["checkpoint", "чекпоинт", "где мы остановились", "historical review"]):
        intent = "historical_review"
        run_reference_hint = "historical"

    return build_classification(
        request=request,
        inventory=inventory,
        intent_class=intent,
        confidence="medium",
        topic_candidate=topic_name,
        topic_name_candidate=None,
        case_id_candidate=args.case_id,
        run_reference_hint=run_reference_hint,
        operation_mode="workspace_write" if args.write_mode == "edit" or intent in {"topic_bootstrap", "topic_migration"} else "read_only",
        research_mode=research_mode,
        routing_rationale=["deterministic keyword fallback selected the intent because AI classification was unavailable or inconclusive"],
    )


def high_precision_shortcut(args: argparse.Namespace, request: str, inventory: list[dict[str, Any]]) -> dict[str, Any] | None:
    lowered = request.lower()
    topic_root = infer_topic_root_from_request(request, inventory)
    topic_name = topic_root.name if topic_root else (args.topic or args.compat_topic)
    operation_mode = "workspace_write" if args.write_mode == "edit" else "read_only"
    bootstrap_match = re.search(r"(?:создай(?:\s+новую)?\s+тему|new topic|создай\s+новый\s+проект)\s+([a-z0-9._-]+)", lowered)

    shortcuts: list[tuple[str, tuple[str, ...], str, str]] = [
        ("current_state_lookup", ("текущее состояние", "статус сервера", "current state", "current project state"), "none", "high"),
        ("historical_review", ("чекпоинт", "checkpoint", "где мы остановились", "historical review"), "historical", "high"),
        ("current_run_review", ("проверь последний прогон", "последний прогон", "latest run", "current run"), "latest", "high"),
        ("readiness_review", ("оцени готовность", "evaluate readiness", "readiness review"), "latest", "high"),
        ("compare_runs", ("сравни", "compare", "old vs new", "до и после"), "latest", "medium"),
        ("research_request", ("исследуй", "research", "разберись как сейчас устроен research"), "none", "high"),
        ("topic_bootstrap", ("создай новую тему", "new topic", "создай новый проект"), "none", "high"),
        ("topic_migration", ("мигрируй", "migration", "переведи старую тему"), "none", "high"),
        ("promotion_preview", ("подготовь promotion", "promotion", "adoption"), "latest", "medium"),
    ]
    for intent, phrases, run_hint, confidence in shortcuts:
        if any(phrase in lowered for phrase in phrases):
            topic_name_candidate = args.topic_name
            if intent == "topic_bootstrap":
                topic_name_candidate = args.topic_name or (bootstrap_match.group(1) if bootstrap_match else None)
                if topic_name_candidate is None:
                    return None
            return build_classification(
                request=request,
                inventory=inventory,
                intent_class=intent,
                confidence=confidence,
                topic_candidate=topic_name,
                topic_name_candidate=topic_name_candidate,
                case_id_candidate=args.case_id,
                run_reference_hint=run_hint,
                operation_mode="workspace_write" if intent in {"topic_bootstrap", "topic_migration"} else operation_mode,
                research_mode=args.research_mode_override or ("deep" if "deep" in lowered or "глуб" in lowered else ("quick" if intent == "research_request" else "none")),
                routing_rationale=[f"high-precision deterministic shortcut matched intent `{intent}`"],
            )
    return None


def build_classification_prompt(
    *,
    request: str,
    args: argparse.Namespace,
    inventory: list[dict[str, Any]],
    registry: dict[str, Any],
) -> str:
    inventory_lines = []
    for item in inventory:
        inventory_lines.append(
            f"- {item['name']} | kind={item['kind']} | managed_defaults={'yes' if item['managed_defaults'] else 'no'} | runs={item['run_count']}"
        )
    hint_lines = [
        f"explicit_topic={args.topic or 'none'}",
        f"explicit_topic_root={args.topic_root or 'none'}",
        f"explicit_run_root={args.run_root or 'none'}",
        f"explicit_review_run_root={args.review_run_root or 'none'}",
        f"explicit_case_path={args.case_path or 'none'}",
        f"explicit_case_id={args.case_id or 'none'}",
        f"explicit_compare_targets={','.join(args.compare_target) or 'none'}",
        f"explicit_promotion_run_root={args.promotion_run_root or 'none'}",
        f"explicit_case_set_id={args.case_set_id or 'none'}",
        f"explicit_topic_name={args.topic_name or 'none'}",
    ]
    intent_help = "\n".join(
        [
            "- historical_review: checkpoint/history/where we stopped requests",
            "- current_run_review: last run/current run/why latest is weak",
            "- readiness_review: readiness-only evaluation of one explicit or inferred canonical run",
            "- compare_runs: compare old vs new / before vs after",
            "- clean_rerun: contamination-sensitive rerun of one explicit case",
            "- canonical_managed_eval: broader eval / managed eval / line readiness pack",
            "- promotion_preview: promotion/adoption preview",
            "- topic_bootstrap: create a new topic or project root",
            "- topic_migration: migrate an old topic to managed defaults",
            "- research_request: research, architecture understanding, next-step synthesis",
            "- current_state_lookup: current server/project status lookup",
            "- general_project_analysis: fallback free-form managed analysis",
        ]
    )
    return "\n".join(
        [
            "Classify the following server operator request into one managed workflow intent.",
            "Return only valid JSON following the schema.",
            "Use the provided topic roots only; do not invent new topic names unless the request clearly asks to create a new topic.",
            "Choose workspace_write only when the request clearly implies file changes, topic creation, or topic migration.",
            "Set needs_clarification=true only when a structural workflow would be unsafe without one missing target.",
            "Estimate substantiality as lightweight only for short low-risk lookups; otherwise use substantial.",
            "Estimate complexity as low/medium/high, depth as shallow/medium/deep, risk_level as low/high, and scope_class as single_topic/cross_topic/global_server.",
            "Prefer global_server for server-wide operational requests, bootstrap/migration, or current-state questions.",
            "",
            "Available topic roots:",
            *inventory_lines,
            "",
            "Explicit hints:",
            *hint_lines,
            "",
            "Intent help:",
            intent_help,
            "",
            "Managed default backend:",
            f"- server entrypoint: {registry.get('default_server_entrypoint')}",
            f"- managed backend launcher: {registry.get('default_launcher_entrypoint')}",
            "",
            "User request:",
            request,
        ]
    )


def run_ai_classifier(
    *,
    request: str,
    args: argparse.Namespace,
    inventory: list[dict[str, Any]],
    registry: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prompt = build_classification_prompt(request=request, args=args, inventory=inventory, registry=registry)
    with tempfile.TemporaryDirectory(prefix="ai-meta-classifier-") as temp_dir:
        temp_root = Path(temp_dir)
        output_path = temp_root / "classification.json"
        stderr_path = temp_root / "classification.stderr.txt"
        cmd = [
            "codex",
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path()),
            "--output-last-message",
            str(output_path),
            prompt,
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(managed.core_root()),
            text=True,
            capture_output=True,
            check=False,
            timeout=45,
        )
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"codex classifier failed with exit code {completed.returncode}")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        raw = {
            "command": cmd,
            "stderr": completed.stderr,
            "stdout": completed.stdout,
        }
        payload["format"] = AI_META_CLASSIFICATION_FORMAT
        return payload, raw


def normalize_classification(
    classification: dict[str, Any],
    *,
    request: str,
    args: argparse.Namespace,
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = dict(classification)
    intent = normalized["intent_class"]
    operational_signal = request_has_any(request, ["router", "роутер", "receiver", "ресивер", "vpn", "server", "сервер"])
    action_signal = request_has_any(request, ["plan", "план", "предложи", "playbook", "patch", "патч", "program", "программа", "fix", "почини"])
    if intent == "current_state_lookup" and operational_signal and action_signal:
        normalized["intent_class"] = "general_project_analysis"
        normalized.setdefault("routing_rationale", []).append(
            "guardrail upgraded an operational request from current_state_lookup to general_project_analysis because action planning was requested"
        )
        intent = normalized["intent_class"]
    topic_candidate = normalized.get("topic_candidate")
    operation_mode = normalized.get("operation_mode") or ("workspace_write" if args.write_mode == "edit" else "read_only")
    if intent in {"topic_bootstrap", "topic_migration"}:
        operation_mode = "workspace_write"
    research_mode = normalized.get("research_mode") or "none"
    if research_mode == "auto":
        research_mode = "quick" if intent == "research_request" else "none"
    normalized["operation_mode"] = operation_mode
    normalized["research_mode"] = research_mode
    normalized["substantiality"] = normalized.get("substantiality") or infer_substantiality(
        intent_class=intent,
        complexity=normalized.get("complexity") or infer_complexity(request=request, intent_class=intent),
        depth=normalized.get("depth") or infer_depth(request=request, intent_class=intent),
    )
    normalized["complexity"] = normalized.get("complexity") or infer_complexity(request=request, intent_class=intent)
    normalized["depth"] = normalized.get("depth") or infer_depth(request=request, intent_class=intent)
    normalized["risk_level"] = normalized.get("risk_level") or infer_risk_level(
        request=request,
        intent_class=intent,
        operation_mode=operation_mode,
    )
    normalized["scope_class"] = normalized.get("scope_class") or infer_scope_class(
        request=request,
        intent_class=intent,
        inventory=inventory,
        topic_candidate=topic_candidate,
    )
    if intent in STRUCTURAL_INTENTS:
        normalized["substantiality"] = "substantial"
        normalized["risk_level"] = "high"
        normalized["complexity"] = "high" if intent in {"canonical_managed_eval", "promotion_preview", "topic_migration"} else normalized["complexity"]
        normalized["depth"] = "deep" if intent in {"canonical_managed_eval", "promotion_preview", "topic_migration"} else normalized["depth"]
    if operation_mode == "workspace_write":
        normalized["risk_level"] = "high"
    if normalized["complexity"] != "low" or normalized["depth"] != "shallow":
        normalized["substantiality"] = "substantial"
    if normalized["scope_class"] == "single_topic" and len(topic_matches_from_request(request, inventory)) > 1:
        normalized["scope_class"] = "cross_topic"
    if normalized["scope_class"] == "cross_topic" and request_has_any(request, ["server", "сервер", "router", "роутер", "receiver", "ресивер", "vpn"]):
        normalized["scope_class"] = "global_server"
    return normalized


def resolve_topic_root(
    *,
    args: argparse.Namespace,
    classification: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> tuple[Path | None, list[str]]:
    reasons: list[str] = []
    inventory_by_name = topic_lookup(inventory)
    if classification.get("intent_class") == "topic_bootstrap" and not args.topic_root:
        reasons.append("topic bootstrap does not bind to an existing topic root before creation")
        return None, reasons

    if args.topic_root:
        topic_root = Path(args.topic_root).resolve()
        reasons.append(f"explicit topic root `{topic_root}` was provided")
        return topic_root, reasons
    if args.compat_topic:
        topic_root = topic_from_name(args.compat_topic, inventory_by_name)
        if topic_root:
            reasons.append(f"compatibility topic `{args.compat_topic}` was selected")
            return topic_root, reasons
    if args.topic:
        topic_root = topic_from_name(args.topic, inventory_by_name)
        if topic_root:
            reasons.append(f"explicit topic hint `{args.topic}` was selected")
            return topic_root, reasons

    for raw in [args.run_root, args.review_run_root, args.promotion_run_root, args.case_path]:
        if raw:
            inferred = managed.topic_root_for_path(Path(raw).resolve())
            if inferred is not None:
                reasons.append(f"topic root was inferred from explicit path `{raw}`")
                return inferred, reasons

    candidate = classification.get("topic_candidate")
    topic_root = topic_from_name(candidate, inventory_by_name)
    if topic_root is not None:
        reasons.append(f"AI classification selected topic `{candidate}`")
        return topic_root, reasons

    inferred = infer_topic_root_from_request(" ".join(args.request), inventory)
    if inferred is not None:
        reasons.append(f"topic root was inferred from natural-language request as `{inferred.name}`")
        return inferred, reasons

    reasons.append(f"defaulted to core topic `{managed.core_root().name}`")
    return managed.core_root(), reasons


def infer_review_roots(intent: str, topic_root: Path) -> tuple[Path | None, list[Path]]:
    runs = reviewable_run_roots(topic_root)
    if intent == "compare_runs":
        if len(runs) >= 2:
            return runs[0], [runs[1]]
        if len(runs) == 1:
            return runs[0], []
        return None, []
    if intent in {"historical_review", "current_run_review"}:
        return (runs[0] if runs else None), []
    return None, []


def infer_pack_run_root(topic_root: Path) -> Path | None:
    return newest_run_with_file(topic_root, "summaries/trial-plan.json")


def infer_ready_run_root(topic_root: Path) -> Path | None:
    return newest_run_with_file(topic_root, "summaries/context-router/readiness-evaluation/readiness-result.json")


def prepare_dynamic_memory(
    *,
    launch_dir: Path,
    topic_root: Path | None,
    request: str,
    allow_graph: bool,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    dynamic_sources: list[dict[str, Any]] = []
    warnings: list[str] = []
    artifacts: dict[str, Any] = {}

    if topic_root is not None and topic_root.name not in SYSTEM_ROOT_NAMES and request.strip():
        query_snapshot = launch_dir / "memory" / "query-memory-snapshot.md"
        cmd = [
            "memory",
            "snapshot",
            "--topic",
            topic_root.name,
            "--query",
            request,
            "--out",
            str(query_snapshot),
        ]
        step = managed.run_command(cmd, cwd=Path("/home/agent"), logs_dir=launch_dir / "logs", step_name="query-memory-snapshot")
        artifacts["query_memory_snapshot"] = step
        if step["returncode"] == 0 and query_snapshot.exists():
            dynamic_sources.append(
                {
                    "source_class": "query_memory_snapshot",
                    "path": str(query_snapshot),
                    "scope": "query_memory",
                    "currentness": "request",
                    "note": "best-effort topic-scoped memory snapshot for the current request",
                }
            )
        else:
            warnings.append("query memory snapshot could not be generated")

    if allow_graph and request.strip():
        env = os.environ.copy()
        if "NEO4J_PASS" not in env:
            docker_cmd = [
                "docker",
                "inspect",
                "ai-neo4j",
                "--format",
                "{{range .Config.Env}}{{println .}}{{end}}",
            ]
            completed = subprocess.run(docker_cmd, text=True, capture_output=True, check=False)
            if completed.returncode == 0:
                for line in completed.stdout.splitlines():
                    if line.startswith("NEO4J_AUTH="):
                        auth = line.split("=", 1)[1]
                        user, _, password = auth.partition("/")
                        if user and password:
                            env["NEO4J_URI"] = "bolt://127.0.0.1:7687"
                            env["NEO4J_USER"] = user
                            env["NEO4J_PASS"] = password
                        break
        if env.get("NEO4J_PASS"):
            graph_path = launch_dir / "memory" / "query-graph-recall.md"
            completed = subprocess.run(
                ["graphmem-recall", request],
                cwd=str(Path("/home/agent")),
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            (launch_dir / "logs").mkdir(parents=True, exist_ok=True)
            (launch_dir / "logs" / "query-graph-recall.stdout.txt").write_text(completed.stdout, encoding="utf-8")
            (launch_dir / "logs" / "query-graph-recall.stderr.txt").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode == 0:
                write_text(graph_path, completed.stdout)
                dynamic_sources.append(
                    {
                        "source_class": "query_graph_recall",
                        "path": str(graph_path),
                        "scope": "query_memory",
                        "currentness": "request",
                        "note": "best-effort graph helper recall for the current request",
                    }
                )
            else:
                warnings.append("graph recall was available but did not return a clean result")
        else:
            warnings.append("graph recall credentials were not available in the local runtime")

    return dynamic_sources, warnings, artifacts


def build_general_prompt(
    *,
    topic_root: Path,
    request: str,
    memory_selection_path: Path,
    query_snapshot: Path | None,
    graph_snapshot: Path | None,
) -> str:
    lines = [
        f"You are running inside a managed topic workspace: {topic_root}",
        "",
        "MUST do first:",
        "1) Read ./AGENTS.md",
        "2) Read ./README.md if it exists",
        "3) Read ./managed-defaults.json if it exists",
        "4) Use the managed memory selection and per-request memory bundles below before answering.",
        "",
        "Task:",
        request,
        "",
        "Managed memory selection:",
        str(memory_selection_path),
    ]
    if query_snapshot is not None:
        lines.extend(["", "Per-request memory snapshot:", str(query_snapshot)])
    if graph_snapshot is not None:
        lines.extend(["", "Per-request graph recall:", str(graph_snapshot)])
    lines.extend(
        [
            "",
            "Output requirements:",
            "- Follow the user request strictly.",
            "- Keep the answer grounded in the selected topic and managed memory.",
            "- Do not reopen accepted closed repair themes unless a new blocker is visible in the current evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_general_project_analysis(
    *,
    topic_root: Path,
    request: str,
    launch_dir: Path,
    memory_selection_path: Path,
    query_snapshot: Path | None,
    graph_snapshot: Path | None,
    operation_mode: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    prompt_path = launch_dir / "prompt.txt"
    jsonl_path = launch_dir / "response.jsonl"
    stderr_path = launch_dir / "stderr.log"
    last_path = launch_dir / "last.md"
    summary_path = launch_dir / "summary.md"
    prompt = build_general_prompt(
        topic_root=topic_root,
        request=request,
        memory_selection_path=memory_selection_path,
        query_snapshot=query_snapshot,
        graph_snapshot=graph_snapshot,
    )
    write_text(prompt_path, prompt)
    sandbox = "workspace-write" if operation_mode == "workspace_write" else "read-only"
    try:
        completed = subprocess.run(
            [
                "codex",
                "exec",
                "--json",
                "--sandbox",
                sandbox,
                "--skip-git-repo-check",
                prompt,
            ],
            cwd=str(topic_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stderr_value = exc.stderr.decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stdout_value = exc.stdout.decode("utf-8", errors="ignore") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        if stdout_value:
            jsonl_path.write_text(stdout_value, encoding="utf-8")
        stderr_path.write_text(stderr_value + "\nTIMED_OUT=true\n", encoding="utf-8")
        raise RuntimeError(f"general project analysis timed out after {timeout_seconds}s") from exc
    jsonl_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"general project analysis codex exec failed with exit code {completed.returncode}")
    subprocess.run(["/home/agent/bin/codex-jsonl-last", str(jsonl_path)], text=True, capture_output=True, check=False)
    last_completed = subprocess.run(
        ["/home/agent/bin/codex-jsonl-last", str(jsonl_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    last_path.write_text(last_completed.stdout, encoding="utf-8")
    summary_completed = subprocess.run(
        ["/home/agent/bin/agent-run-report", str(jsonl_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    summary_path.write_text(summary_completed.stdout, encoding="utf-8")
    return {
        "prompt": str(prompt_path),
        "jsonl": str(jsonl_path),
        "stderr": str(stderr_path),
        "last": str(last_path),
        "summary": str(summary_path),
        "sandbox": sandbox,
    }


def create_meta_root(intent: str, request: str, topic_root: Path | None, run_root: Path | None) -> Path:
    slug = slugify(request or intent, fallback=intent)
    if run_root is not None:
        target = run_root / "summaries" / "ai-meta-launcher" / f"{now_stamp()}-{slugify(intent)}-{slug}"
        target.mkdir(parents=True, exist_ok=True)
        return target
    stamp = managed.now_utc_iso().split("T", 1)[0]
    if topic_root is not None:
        target = topic_root / "runs" / f"{stamp}-{slugify(intent)}-{slug}-v1"
    else:
        target = managed.core_root() / "runs" / f"{stamp}-{slugify(intent)}-{slug}-v1"
    target.mkdir(parents=True, exist_ok=True)
    return target


def default_run_root(topic_root: Path, request: str, intent: str) -> Path:
    stamp = managed.now_utc_iso().split("T", 1)[0]
    run_root = topic_root / "runs" / f"{stamp}-{slugify(intent)}-{slugify(request, fallback='managed')}-v1"
    run_root.mkdir(parents=True, exist_ok=True)
    return run_root


def resolve_managed_targets(
    *,
    args: argparse.Namespace,
    request: str,
    intent: str,
    topic_root: Path | None,
    classification: dict[str, Any],
) -> tuple[dict[str, Any], list[str], str | None]:
    reasons: list[str] = []
    clarification: str | None = None
    resolved: dict[str, Any] = {
        "topic_root": str(topic_root) if topic_root else None,
        "run_root": args.run_root,
        "review_run_root": args.review_run_root,
        "compare_targets": list(args.compare_target),
        "case_path": args.case_path,
        "case_id": args.case_id or classification.get("case_id_candidate"),
        "profile": args.profile,
        "promotion_run_root": args.promotion_run_root,
        "case_set_id": args.case_set_id,
        "description": args.description or request,
        "topic_name": args.topic_name or classification.get("topic_name_candidate"),
    }

    if intent in {"historical_review", "current_run_review", "compare_runs"} and topic_root is not None:
        review_root = Path(args.review_run_root).resolve() if args.review_run_root else None
        compare_targets = [Path(item).resolve() for item in args.compare_target]
        if review_root is None:
            review_root, inferred_compare = infer_review_roots(intent, topic_root)
            if review_root is not None:
                reasons.append(f"{intent} defaulted to latest run `{review_root}`")
            compare_targets = inferred_compare if not compare_targets else compare_targets
        if intent == "compare_runs" and not compare_targets:
            clarification = "compare_runs requires at least two run roots, but only one or zero candidate runs were found"
        resolved["review_run_root"] = str(review_root) if review_root else None
        resolved["compare_targets"] = [str(path) for path in compare_targets]

    elif intent == "readiness_review" and topic_root is not None:
        run_root = Path(args.run_root).resolve() if args.run_root else None
        if run_root is None:
            run_root = infer_pack_run_root(topic_root) or infer_ready_run_root(topic_root)
        if run_root is None:
            clarification = "readiness_review requires an explicit or inferable canonical run root"
        else:
            reasons.append(f"readiness_review resolved canonical run root `{run_root}`")
        resolved["run_root"] = str(run_root) if run_root else None

    elif intent == "clean_rerun":
        case_path = Path(args.case_path).resolve() if args.case_path else search_case_file(topic_root, resolved["case_id"]) if topic_root else None
        run_root = Path(args.run_root).resolve() if args.run_root else None
        if case_path is not None:
            run_root = case_path.parent.parent
        elif run_root is None and topic_root is not None:
            run_root = infer_pack_run_root(topic_root)
        if run_root is None:
            clarification = "clean_rerun requires a run root, but no canonical run root could be inferred"
        elif case_path is None:
            clarification = "clean_rerun requires one explicit case path or case id, but no matching case file was found"
        elif not resolved["profile"]:
            clarification = "clean_rerun requires an explicit profile; pass --profile or make the request profile-specific"
        resolved["run_root"] = str(run_root) if run_root else None
        resolved["case_path"] = str(case_path) if case_path else None

    elif intent == "canonical_managed_eval" and topic_root is not None:
        run_root = Path(args.run_root).resolve() if args.run_root else None
        if run_root is None:
            run_root = infer_pack_run_root(topic_root)
            if run_root is not None:
                reasons.append(f"canonical_managed_eval reused latest canonical pack run `{run_root}`")
        if run_root is None and (args.case_file or args.accepted_case_set or args.case_id):
            run_root = default_run_root(topic_root, request, intent)
            reasons.append(f"canonical_managed_eval allocated a new run root `{run_root}` for explicit pack inputs")
        if run_root is None:
            clarification = "canonical_managed_eval needs either an explicit run root or canonical pack inputs"
        resolved["run_root"] = str(run_root) if run_root else None

    elif intent == "promotion_preview" and topic_root is not None:
        run_root = Path(args.promotion_run_root).resolve() if args.promotion_run_root else infer_ready_run_root(topic_root)
        if run_root is None:
            clarification = "promotion_preview requires a ready run root, but none could be inferred"
        case_set_id = args.case_set_id or f"{topic_root.name}-ai-meta-preview-{managed.now_utc_iso().split('T', 1)[0]}"
        resolved["promotion_run_root"] = str(run_root) if run_root else None
        resolved["case_set_id"] = case_set_id
        reasons.append(f"promotion preview case-set id resolved to `{case_set_id}`")

    elif intent == "topic_bootstrap":
        if not resolved["topic_name"]:
            clarification = "topic_bootstrap requires a target topic name"
        else:
            reasons.append(f"topic bootstrap target resolved to `{resolved['topic_name']}`")

    elif intent == "topic_migration":
        topic_root = Path(args.topic_root).resolve() if args.topic_root else topic_root
        if topic_root is None or not topic_root.exists():
            clarification = "topic_migration requires an existing topic root"
        elif not args.topic_root and not args.topic and not classification.get("topic_candidate") and topic_root == managed.core_root():
            clarification = "topic_migration requires a specific existing topic root; defaulting to core would be unsafe"
        resolved["topic_root"] = str(topic_root) if topic_root else None

    return resolved, reasons, clarification


def build_managed_command(intent: str, args: argparse.Namespace, resolved: dict[str, Any], request: str) -> list[str]:
    cmd = [
        "python3",
        str(managed.creator_script_root() / "launch_managed_workflow.py"),
        "--workflow-class",
        intent,
        "--task-request",
        request,
    ]
    topic_hint_root = topic_from_name(args.topic, topic_lookup(list_topic_inventory())) if args.topic else None
    effective_topic_root = resolved.get("topic_root") or (str(topic_hint_root) if topic_hint_root is not None else None)
    if intent != "topic_bootstrap" and effective_topic_root:
        cmd.extend(["--topic-root", effective_topic_root])
    if resolved.get("run_root"):
        cmd.extend(["--run-root", resolved["run_root"]])
    if resolved.get("review_run_root"):
        cmd.extend(["--review-run-root", resolved["review_run_root"]])
    for compare_target in resolved.get("compare_targets", []):
        cmd.extend(["--compare-target", compare_target])
    if resolved.get("case_path"):
        cmd.extend(["--case-path", resolved["case_path"]])
    if resolved.get("profile"):
        cmd.extend(["--profile", resolved["profile"]])
    if intent == "promotion_preview" and resolved.get("promotion_run_root"):
        cmd.extend(["--promotion-run-root", resolved["promotion_run_root"]])
    if intent == "promotion_preview" and resolved.get("case_set_id"):
        cmd.extend(["--case-set-id", resolved["case_set_id"]])
    if intent == "promotion_preview" and resolved.get("description"):
        cmd.extend(["--description", resolved["description"]])
    if resolved.get("topic_name"):
        cmd.extend(["--topic-name", resolved["topic_name"]])
    if args.bootstrap_root:
        cmd.extend(["--bootstrap-root", args.bootstrap_root])
    if args.force:
        cmd.append("--force")
    if args.case_id:
        cmd.extend(["--case-id", args.case_id])
    for case_file in args.case_file:
        cmd.extend(["--case-file", case_file])
    if args.accepted_case_set:
        cmd.extend(["--accepted-case-set", args.accepted_case_set])
    if args.skill_name:
        cmd.extend(["--skill-name", args.skill_name])
    if args.baseline_profile:
        cmd.extend(["--baseline-profile", args.baseline_profile])
    if args.trial_profile:
        cmd.extend(["--trial-profile", args.trial_profile])
    if args.inventory_manifest:
        cmd.extend(["--inventory-manifest", args.inventory_manifest])
    if args.pack_mode:
        cmd.extend(["--pack-mode", args.pack_mode])
    for value in args.selection_artifact:
        cmd.extend(["--selection-artifact", value])
    for value in args.candidate_case_id:
        cmd.extend(["--candidate-case-id", value])
    for value in args.rejected_case:
        cmd.extend(["--rejected-case", value])
    for value in args.case_selection:
        cmd.extend(["--case-selection", value])
    if args.prepare_only:
        cmd.append("--prepare-only")
    if args.skip_matrix:
        cmd.append("--skip-matrix")
    if args.skip_readiness:
        cmd.append("--skip-readiness")
    if args.matrix_mode_override:
        cmd.extend(["--matrix-mode-override", args.matrix_mode_override])
    if args.readiness_mode_override:
        cmd.extend(["--readiness-mode-override", args.readiness_mode_override])
    if args.review_mode_override:
        cmd.extend(["--review-mode-override", args.review_mode_override])
    if args.runner_surface:
        cmd.extend(["--runner-surface", args.runner_surface])
    if args.override_reason:
        cmd.extend(["--override-reason", args.override_reason])
    if args.out_dir:
        cmd.extend(["--out-dir", args.out_dir])
    if args.run_label:
        cmd.extend(["--run-label", args.run_label])
    if args.timeout:
        cmd.extend(["--timeout", str(args.timeout)])
    if args.thinking:
        cmd.extend(["--thinking", args.thinking])
    if args.session_id:
        cmd.extend(["--session-id", args.session_id])
    if intent == "promotion_preview" and args.preview_root:
        cmd.extend(["--preview-root", args.preview_root])
    if intent == "promotion_preview" and args.promotion_status:
        cmd.extend(["--promotion-status", args.promotion_status])
    return cmd


def frontdoor_execution_mode(intent: str, frontdoor_source: str) -> str:
    if intent in MANAGED_BACKEND_INTENTS:
        return "managed_backend"
    if intent == "current_state_lookup":
        return "current_state_backend"
    if intent == "research_request":
        return "research_backend"
    if frontdoor_source == "codex_chat":
        return "codex_chat_local"
    return "general_analysis_backend"


def build_backend_command(
    *,
    intent: str,
    args: argparse.Namespace,
    classification: dict[str, Any],
    resolved: dict[str, Any],
    request: str,
    frontdoor_source: str,
) -> list[str] | None:
    if frontdoor_execution_mode(intent, frontdoor_source) == "managed_backend":
        return build_managed_command(intent, args, resolved, request)
    if intent == "current_state_lookup":
        return ["/home/agent/bin/openclaw-retrieval-bridge", "current-state"]
    if intent == "research_request":
        research_mode = args.research_mode_override or classification.get("research_mode") or "auto"
        if research_mode == "none":
            research_mode = "auto"
        topic_name = Path(resolved["topic_root"]).name if resolved.get("topic_root") else (args.topic or "core")
        return ["/home/agent/bin/project-research-run", "--mode", research_mode, topic_name, request]
    return None


def build_tool_selection(
    *,
    registry: dict[str, Any],
    classification: dict[str, Any],
    intent: str,
    request: str,
    frontdoor_source: str,
) -> dict[str, Any]:
    families = registry.get("tool_families", {})
    policy = registry.get("intent_tool_policies", {}).get(intent, {})
    selected_primary: list[dict[str, Any]] = []
    selected_optional: list[dict[str, Any]] = []
    desired_unavailable: list[dict[str, Any]] = []
    high_impact: list[dict[str, Any]] = []

    keyword_optional: list[str] = []
    if request_has_any(request, ["github", "pull request", "pr ", " issue", "repo", "repository", "commit", "branch"]):
        keyword_optional.append("github_connector")
    if request_has_any(request, ["research", "search", "latest", "docs", "documentation", "источник", "документац", "web"]):
        keyword_optional.append("web_search")
    if request_has_any(request, ["memory", "graph", "history", "timeline", "context", "контекст", "память", "mcp"]):
        keyword_optional.append("graphmem_readonly")
    if request_has_any(request, ["mcp", "tool", "connector", "инструмент"]):
        keyword_optional.append("mcp_registry_audit")

    wanted = list(dict.fromkeys(policy.get("primary", []) + policy.get("optional", []) + keyword_optional))
    for family_name in wanted:
        spec = families.get(family_name)
        if not spec:
            desired_unavailable.append(
                {
                    "family": family_name,
                    "availability": "unregistered",
                    "reason": "tool family is not present in the global policy registry",
                }
            )
            continue
        surfaces = set(spec.get("execution_surfaces", ["human_cli", "codex_chat"]))
        enabled = bool(spec.get("enabled", True)) and (frontdoor_source in surfaces or "all" in surfaces)
        entry = {
            "family": family_name,
            "description": spec.get("description"),
            "availability": "available" if enabled else "unavailable",
            "high_impact": bool(spec.get("high_impact", False)),
            "source": spec.get("source"),
        }
        if not enabled:
            entry["reason"] = spec.get("unavailable_reason", "tool family is not exposed on this execution surface")
            desired_unavailable.append(entry)
            continue
        role = "primary" if family_name in policy.get("primary", []) else "optional"
        entry["selection_reason"] = (
            f"intent policy `{intent}` selected `{family_name}` as {role}"
            if family_name in policy.get("primary", []) + policy.get("optional", [])
            else "request-specific keyword signal selected this optional tool family"
        )
        if role == "primary":
            selected_primary.append(entry)
        else:
            selected_optional.append(entry)
        if entry["high_impact"]:
            high_impact.append(entry)

    if classification["operation_mode"] == "workspace_write":
        for item in selected_primary + selected_optional:
            if item["family"] == "shell_exec" and item not in high_impact:
                high_impact.append(item)

    return {
        "primary": selected_primary,
        "optional": selected_optional,
        "desired_unavailable": desired_unavailable,
        "high_impact": high_impact,
    }


def build_skill_decision(
    *,
    registry: dict[str, Any],
    classification: dict[str, Any],
    intent: str,
    request: str,
) -> dict[str, Any]:
    policy = registry.get("skill_routing_policy", {})
    lowered = request.lower()
    durable_create_signals = policy.get(
        "durable_create_signals",
        ["create skill", "new skill", "skill-creator", "durable skill", "reusable workflow", "повторяем", "многоразов"],
    )
    durable_update_signals = policy.get(
        "durable_update_signals",
        ["update skill", "refresh skill", "existing skill", "обнови skill", "доработай skill"],
    )
    temporary_signals = policy.get(
        "temporary_signals",
        ["temporary skill", "temp skill", "ephemeral skill", "временный skill"],
    )
    reusable_signals = policy.get(
        "reusable_pattern_signals",
        ["workflow", "repeat", "automation", "playbook", "standardize", "policy", "маршрут", "контур"],
    )
    durable_negative_signals = ["without durable skill", "no durable skill", "без durable skill", "без создания durable skill"]

    reasons: list[str] = []
    decision = "no_skill"
    if any(signal in lowered for signal in durable_update_signals):
        decision = "durable_skill_update"
        reasons.append("request explicitly asked to update an existing reusable skill surface")
    elif any(signal in lowered for signal in temporary_signals):
        decision = "temporary_skill"
        reasons.append("request explicitly asked for a temporary or ephemeral skill-like helper")
    elif any(signal in lowered for signal in durable_negative_signals):
        decision = "temporary_skill"
        reasons.append("request explicitly rejected a durable-skill outcome, so the frontdoor kept the decision at temporary_skill")
    elif any(signal in lowered for signal in durable_create_signals):
        decision = "durable_skill_create"
        reasons.append("request explicitly asked for a reusable or durable skill capability")
    elif classification["complexity"] == "high" and classification["depth"] == "deep" and any(signal in lowered for signal in reusable_signals):
        decision = "durable_skill_create"
        reasons.append("deep high-complexity request plus reusable-pattern signals justify a durable skill path")
    elif classification["complexity"] == "high" and intent in {"general_project_analysis", "research_request"}:
        decision = "temporary_skill"
        reasons.append("high-complexity open-ended work may benefit from a temporary task-skill plan before durable promotion")
    else:
        reasons.append("existing managed workflows plus direct execution are sufficient for this request")

    return {
        "decision": decision,
        "use_skill_creator": decision in {"durable_skill_create", "durable_skill_update"},
        "reasons": reasons,
    }


def build_mode_flags(intent: str, classification: dict[str, Any]) -> dict[str, bool]:
    return {
        "needs_review": intent in {"historical_review", "current_run_review", "readiness_review"},
        "needs_current_state": intent == "current_state_lookup",
        "needs_compare": intent == "compare_runs",
        "needs_clean_rerun": intent == "clean_rerun",
        "needs_eval": intent == "canonical_managed_eval",
        "needs_promotion": intent == "promotion_preview",
        "needs_bootstrap": intent == "topic_bootstrap",
        "needs_migration": intent == "topic_migration",
        "needs_research": intent == "research_request" or classification["research_mode"] != "none",
    }


def build_frontdoor_contract(
    *,
    args: argparse.Namespace,
    request: str,
    registry: dict[str, Any],
    classification: dict[str, Any],
    resolved: dict[str, Any],
    selected_intent: str,
    clarification: str | None,
    memory_selection_path: Path,
    manifest_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    execution_mode = frontdoor_execution_mode(selected_intent, args.frontdoor_source)
    backend_command = build_backend_command(
        intent=selected_intent,
        args=args,
        classification=classification,
        resolved=resolved,
        request=request,
        frontdoor_source=args.frontdoor_source,
    )
    tool_selection = build_tool_selection(
        registry=registry,
        classification=classification,
        intent=selected_intent,
        request=request,
        frontdoor_source=args.frontdoor_source,
    )
    skill_decision = build_skill_decision(
        registry=registry,
        classification=classification,
        intent=selected_intent,
        request=request,
    )
    if clarification:
        recommended_next_action = "ask_for_clarification"
    elif execution_mode == "codex_chat_local":
        recommended_next_action = "continue_in_current_chat_using_memory_selection_and_selected_tools"
    else:
        recommended_next_action = "run_backend_command"
    return {
        "format": CODEX_FRONTDOOR_CONTRACT_FORMAT,
        "generated_at": managed.now_utc_iso(),
        "frontdoor_source": args.frontdoor_source,
        "preflight_only": bool(args.preflight_only),
        "request": request,
        "selected_intent": selected_intent,
        "substantiality": classification["substantiality"],
        "complexity": classification["complexity"],
        "depth": classification["depth"],
        "risk_level": classification["risk_level"],
        "scope_class": classification["scope_class"],
        "operation_mode": classification["operation_mode"],
        "execution_mode": execution_mode,
        "mode_flags": build_mode_flags(selected_intent, classification),
        "research_mode": classification["research_mode"],
        "tool_selection": tool_selection,
        "skill_decision": skill_decision,
        "backend_command": backend_command,
        "memory_selection": str(memory_selection_path),
        "manifest": str(manifest_path),
        "trace": str(trace_path),
        "clarification_required": bool(clarification),
        "clarification_reason": clarification,
        "recommended_next_action": recommended_next_action,
        "binding_policy": registry.get("codex_frontdoor_binding", {}),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Global AI meta-launcher for server-wide managed workflows.",
    )
    parser.add_argument("request", nargs="*", help="Natural-language operator request")
    parser.add_argument("--task-request", help="Explicit natural-language request")
    parser.add_argument("--topic", help="Optional topic hint for meta routing")
    parser.add_argument("--topic-root", help="Optional explicit topic root")
    parser.add_argument("--compat-topic", help="Explicit compatibility topic execution mode")
    parser.add_argument("--frontdoor-source", choices=["human_cli", "codex_chat", "automation"], default="human_cli")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--force-intent-class", choices=sorted(MANAGED_BACKEND_INTENTS | {"research_request", "current_state_lookup", "general_project_analysis"}))
    parser.add_argument("--research-mode-override", choices=["auto", "quick", "deep"])
    parser.add_argument("--write-mode", choices=["readonly", "edit"], default=os.environ.get("AGENT_MODE", "readonly"))

    parser.add_argument("--run-root")
    parser.add_argument("--review-run-root")
    parser.add_argument("--compare-target", action="append", default=[])
    parser.add_argument("--case-path")
    parser.add_argument("--case-id")
    parser.add_argument("--profile")
    parser.add_argument("--out-dir")
    parser.add_argument("--run-label")
    parser.add_argument("--thinking", default="off")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--session-id")

    parser.add_argument("--skill-name")
    parser.add_argument("--case-file", action="append", default=[])
    parser.add_argument("--accepted-case-set")
    parser.add_argument("--baseline-profile")
    parser.add_argument("--trial-profile")
    parser.add_argument("--inventory-manifest")
    parser.add_argument("--pack-mode")
    parser.add_argument("--selection-artifact", action="append", default=[])
    parser.add_argument("--candidate-case-id", action="append", default=[])
    parser.add_argument("--rejected-case", action="append", default=[])
    parser.add_argument("--case-selection", action="append", default=[])
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--skip-matrix", action="store_true")
    parser.add_argument("--skip-readiness", action="store_true")
    parser.add_argument("--matrix-mode-override")
    parser.add_argument("--readiness-mode-override")
    parser.add_argument("--review-mode-override")
    parser.add_argument("--runner-surface", choices=["canonical", "legacy"], default="canonical")
    parser.add_argument("--override-reason")

    parser.add_argument("--promotion-run-root")
    parser.add_argument("--case-set-id")
    parser.add_argument("--description")
    parser.add_argument("--preview-root")
    parser.add_argument("--promotion-status", default="candidate", choices=["accepted", "candidate", "superseded"])

    parser.add_argument("--topic-name")
    parser.add_argument("--bootstrap-root")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = (args.task_request or " ".join(args.request)).strip()
    if not request and not args.force_intent_class and not args.topic_name and not args.compat_topic:
        raise SystemExit("natural-language request is required unless an explicit structural target is provided")

    registry = load_json(registry_path())
    inventory = list_topic_inventory()
    explicit = explicit_classification(args, request)
    shortcut = None if explicit else high_precision_shortcut(args, request, inventory)
    classification_source = "explicit" if explicit else ("deterministic_shortcut" if shortcut else "ai")
    classifier_raw: dict[str, Any] | None = None
    if explicit is not None:
        classification = explicit
    elif shortcut is not None:
        classification = shortcut
    else:
        try:
            classification, classifier_raw = run_ai_classifier(request=request, args=args, inventory=inventory, registry=registry)
        except Exception as exc:
            classification = deterministic_fallback(args, request, inventory)
            classification_source = "deterministic_fallback"
            classifier_raw = {"error": str(exc)}
    classification = normalize_classification(classification, request=request, args=args, inventory=inventory)

    topic_root, topic_reasons = resolve_topic_root(args=args, classification=classification, inventory=inventory)
    selected_intent = classification["intent_class"]
    resolved, target_reasons, clarification = resolve_managed_targets(
        args=args,
        request=request,
        intent=selected_intent,
        topic_root=topic_root,
        classification=classification,
    )
    multi_topic_matches = topic_matches_from_request(request, inventory) if request else []
    if (
        clarification is None
        and len(multi_topic_matches) > 1
        and not any([args.topic, args.topic_root, args.compat_topic])
        and selected_intent not in {"topic_bootstrap", "current_state_lookup"}
    ):
        clarification = (
            "multiple topic roots were mentioned in one request; "
            "pass an explicit --topic/--topic-root or split the request into separate managed workflows"
        )
        target_reasons.append(
            "meta-launcher refused to silently default to one topic because multiple topic roots were detected"
        )
    launch_run_root = None
    if selected_intent in {"historical_review", "current_run_review", "compare_runs"} and resolved.get("review_run_root"):
        launch_run_root = Path(resolved["review_run_root"]).resolve()
    elif selected_intent == "clean_rerun" and resolved.get("run_root"):
        launch_run_root = Path(resolved["run_root"]).resolve()
    elif selected_intent == "readiness_review" and resolved.get("run_root"):
        launch_run_root = Path(resolved["run_root"]).resolve()
    elif selected_intent == "canonical_managed_eval" and resolved.get("run_root"):
        launch_run_root = Path(resolved["run_root"]).resolve()
    elif selected_intent == "promotion_preview" and resolved.get("promotion_run_root"):
        launch_run_root = Path(resolved["promotion_run_root"]).resolve()

    meta_root = create_meta_root(selected_intent, request or selected_intent, topic_root, launch_run_root)
    if meta_root.name == "ai-meta-launcher" or meta_root.parent.name == "ai-meta-launcher":
        launch_dir = meta_root
    else:
        launch_dir = meta_root / "ai-meta-launcher"
    launch_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = launch_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    dynamic_sources, dynamic_warnings, dynamic_artifacts = prepare_dynamic_memory(
        launch_dir=launch_dir,
        topic_root=topic_root,
        request=request,
        allow_graph=selected_intent not in {"clean_rerun", "topic_bootstrap", "topic_migration"},
    )
    memory_fabric_path, memory_selection_path, _fabric, selection = managed.build_memory_artifacts(
        workflow_class=selected_intent if selected_intent in load_json(managed.memory_fabric_definition_path())["workflow_policies"] else "general_project_analysis",
        registry_path=registry_path(),
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=launch_run_root,
        compare_targets=resolved.get("compare_targets", []),
        task_request=request,
        case_paths=[Path(resolved["case_path"]).resolve()] if resolved.get("case_path") else [],
        extra_sources=dynamic_sources,
    )

    classification_path = launch_dir / "ai-meta-classification.json"
    manifest_path = launch_dir / "ai-meta-launch-manifest.json"
    trace_path = launch_dir / "ai-meta-launch-trace.json"
    contract_path = launch_dir / "codex-frontdoor-contract.json"

    classification_payload = {
        "format": AI_META_CLASSIFICATION_FORMAT,
        "generated_at": managed.now_utc_iso(),
        "source": classification_source,
        "request": request,
        "classification": classification,
        "topic_resolution_reasons": topic_reasons,
        "target_resolution_reasons": target_reasons,
        "resolved_topic_root": str(topic_root) if topic_root else None,
        "request_topic_matches": [item["name"] for item in multi_topic_matches],
        "resolved_targets": resolved,
        "clarification": clarification,
        "raw_classifier": classifier_raw,
    }
    manifest_payload = {
        "format": AI_META_MANIFEST_FORMAT,
        "generated_at": managed.now_utc_iso(),
        "request": request,
        "server_entrypoint": registry.get("default_server_entrypoint"),
        "meta_launcher_backend": registry.get("meta_launcher_backend"),
        "policy_registry": str(registry_path()),
        "memory_fabric_definition": str(managed.memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "frontdoor_source": args.frontdoor_source,
        "selected_intent": selected_intent,
        "classification_source": classification_source,
        "classification_confidence": classification["confidence"],
        "substantiality": classification["substantiality"],
        "complexity": classification["complexity"],
        "depth": classification["depth"],
        "risk_level": classification["risk_level"],
        "scope_class": classification["scope_class"],
        "resolved_topic_root": str(topic_root) if topic_root else None,
        "request_topic_matches": [item["name"] for item in multi_topic_matches],
        "resolved_targets": resolved,
        "dynamic_memory_artifacts": dynamic_artifacts,
        "warnings": sorted(set(selection["warning_signals"] + dynamic_warnings)),
        "downstream": {},
    }
    trace_payload = {
        "format": AI_META_TRACE_FORMAT,
        "generated_at": managed.now_utc_iso(),
        "request": request,
        "selected_intent": selected_intent,
        "classification_confidence": classification["confidence"],
        "classification_rationale": classification["routing_rationale"],
        "frontdoor_source": args.frontdoor_source,
        "substantiality": classification["substantiality"],
        "complexity": classification["complexity"],
        "depth": classification["depth"],
        "risk_level": classification["risk_level"],
        "scope_class": classification["scope_class"],
        "needs_clarification": bool(classification.get("needs_clarification") or clarification),
        "clarification_reason": clarification or classification.get("clarification_reason"),
        "resolved_topic_root": str(topic_root) if topic_root else None,
        "request_topic_matches": [item["name"] for item in multi_topic_matches],
        "resolved_targets": resolved,
        "memory_selection": str(memory_selection_path),
        "warnings": sorted(set(selection["warning_signals"] + dynamic_warnings)),
        "override_mode": "compatibility_topic_exec" if args.compat_topic else ("legacy_runner" if args.runner_surface == "legacy" else None),
        "default_path_enforced": not bool(args.compat_topic or args.runner_surface == "legacy"),
        "steps": [],
    }
    contract_payload = build_frontdoor_contract(
        args=args,
        request=request,
        registry=registry,
        classification=classification,
        resolved=resolved,
        selected_intent=selected_intent,
        clarification=clarification or classification.get("clarification_reason"),
        memory_selection_path=memory_selection_path,
        manifest_path=manifest_path,
        trace_path=trace_path,
    )
    manifest_payload["frontdoor_contract"] = str(contract_path)
    manifest_payload["frontdoor_execution_mode"] = contract_payload["execution_mode"]
    manifest_payload["tool_selection"] = contract_payload["tool_selection"]
    manifest_payload["skill_decision"] = contract_payload["skill_decision"]
    if contract_payload["backend_command"] is not None:
        manifest_payload["downstream"]["recommended_backend_command"] = contract_payload["backend_command"]
    trace_payload["frontdoor_execution_mode"] = contract_payload["execution_mode"]
    trace_payload["tool_selection"] = contract_payload["tool_selection"]
    trace_payload["skill_decision"] = contract_payload["skill_decision"]
    write_json(classification_path, classification_payload)
    write_json(manifest_path, manifest_payload)
    write_json(trace_path, trace_payload)
    write_json(contract_path, contract_payload)
    meta_env = {
        "OPENCLAW_META_LAUNCHED": "1",
        "OPENCLAW_META_INTENT": selected_intent,
        "OPENCLAW_META_CLASSIFICATION_CONFIDENCE": classification["confidence"],
        "OPENCLAW_META_LAUNCH_MANIFEST": str(manifest_path),
        "OPENCLAW_META_LAUNCH_TRACE": str(trace_path),
        "OPENCLAW_META_POLICY_REGISTRY": str(registry_path()),
        "OPENCLAW_META_MEMORY_SELECTION": str(memory_selection_path),
        "OPENCLAW_META_MEMORY_FABRIC": str(memory_fabric_path),
        "OPENCLAW_META_TOPIC_ROOT": str(topic_root) if topic_root else "",
        "OPENCLAW_META_FRONTDOOR_CONTRACT": str(contract_path),
    }

    if classification.get("needs_clarification") or clarification:
        result = {
            "status": "clarification_required",
            "selected_intent": selected_intent,
            "clarification_reason": clarification or classification.get("clarification_reason"),
            "contract": str(contract_path),
            "trace": str(trace_path),
            "manifest": str(manifest_path),
        }
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    stop_after_contract = bool(args.preflight_only or (args.frontdoor_source == "codex_chat" and contract_payload["execution_mode"] == "codex_chat_local"))
    if stop_after_contract:
        write_json(manifest_path, manifest_payload)
        write_json(trace_path, trace_payload)
        write_json(contract_path, contract_payload)
        result = {
            "status": "preflight_only",
            "selected_intent": selected_intent,
            "classification_confidence": classification["confidence"],
            "contract": str(contract_path),
            "manifest": str(manifest_path),
            "trace": str(trace_path),
            "memory_selection": str(memory_selection_path),
            "recommended_next_action": contract_payload["recommended_next_action"],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if selected_intent in MANAGED_BACKEND_INTENTS:
        cmd = build_managed_command(selected_intent, args, resolved, request)
        step = managed.run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="managed-backend", env_extra=meta_env)
        trace_payload["steps"].append({"name": "managed-backend", **step})
        if step["returncode"] != 0:
            write_json(trace_path, trace_payload)
            raise SystemExit(f"managed backend failed; see {step['stderr_log']}")
        manifest_payload["downstream"]["backend_command"] = cmd
        manifest_payload["downstream"]["backend_result"] = step["parsed_json"] or {"stdout_log": step["stdout_log"]}
    elif selected_intent == "current_state_lookup":
        cmd = ["/home/agent/bin/openclaw-retrieval-bridge", "current-state"]
        step = managed.run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="current-state", env_extra=meta_env)
        trace_payload["steps"].append({"name": "current-state", **step})
        if step["returncode"] != 0:
            write_json(trace_path, trace_payload)
            raise SystemExit(f"current-state backend failed; see {step['stderr_log']}")
        current_state_path = launch_dir / "current-state.md"
        write_text(current_state_path, Path(step["stdout_log"]).read_text(encoding="utf-8"))
        manifest_payload["downstream"]["current_state_output"] = str(current_state_path)
    elif selected_intent == "research_request":
        research_mode = args.research_mode_override or classification.get("research_mode") or "auto"
        if research_mode == "none":
            research_mode = "auto"
        topic_name = topic_root.name if topic_root is not None else "core"
        cmd = ["/home/agent/bin/project-research-run", "--mode", research_mode, topic_name, request]
        step = managed.run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="research", env_extra=meta_env)
        trace_payload["steps"].append({"name": "research", **step})
        if step["returncode"] != 0:
            write_json(trace_path, trace_payload)
            raise SystemExit(f"research backend failed; see {step['stderr_log']}")
        latest_root = managed.resolve_latest_link_target(managed.core_root() / "artifacts" / "research" / "latest")
        latest_summary = managed.detect_best_artifact_file(latest_root, preferred_names=["RESEARCH.md", "SUMMARY.md", "README.md"])
        manifest_payload["downstream"]["research_latest_root"] = str(latest_root) if latest_root else None
        manifest_payload["downstream"]["research_summary"] = str(latest_summary) if latest_summary else None
    else:
        general_topic_root = topic_root or managed.core_root()
        if general_topic_root.name not in SYSTEM_ROOT_NAMES:
            managed.ensure_topic_structure(general_topic_root)
        query_snapshot = None
        graph_snapshot = None
        for item in dynamic_sources:
            if item["source_class"] == "query_memory_snapshot":
                query_snapshot = Path(item["path"])
            if item["source_class"] == "query_graph_recall":
                graph_snapshot = Path(item["path"])
        try:
            backend = run_general_project_analysis(
                topic_root=general_topic_root,
                request=request,
                launch_dir=meta_root if meta_root.name != "ai-meta-launcher" else meta_root.parent,
                memory_selection_path=memory_selection_path,
                query_snapshot=query_snapshot,
                graph_snapshot=graph_snapshot,
                operation_mode=classification["operation_mode"],
                timeout_seconds=args.timeout or 180,
            )
        except RuntimeError as exc:
            trace_payload["steps"].append({"name": "general-project-analysis", "returncode": 1, "error": str(exc)})
            write_json(trace_path, trace_payload)
            raise SystemExit(str(exc))
        trace_payload["steps"].append({"name": "general-project-analysis", "returncode": 0, "backend": backend})
        manifest_payload["downstream"]["general_project_analysis"] = backend

    write_json(manifest_path, manifest_payload)
    write_json(trace_path, trace_payload)
    result = {
        "status": "ok",
        "selected_intent": selected_intent,
        "classification_confidence": classification["confidence"],
        "contract": str(contract_path),
        "manifest": str(manifest_path),
        "trace": str(trace_path),
        "memory_selection": str(memory_selection_path),
        "downstream": manifest_payload["downstream"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
