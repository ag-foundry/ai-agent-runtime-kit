#!/usr/bin/env python3
"""Launch the global managed workflow with explicit trace, memory, and override discipline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from file_rules import apply_invocation_line


GLOBAL_MANAGED_TRACE_FORMAT = "openclaw-global-managed-launch-trace-v1"
GLOBAL_MANAGED_MANIFEST_FORMAT = "openclaw-global-managed-launch-manifest-v1"
GLOBAL_MANAGED_MEMORY_FABRIC_FORMAT = "openclaw-global-managed-memory-fabric-v1"
GLOBAL_MANAGED_MEMORY_SELECTION_FORMAT = "openclaw-global-managed-memory-selection-v1"
TOPIC_DEFAULTS_FORMAT = "openclaw-managed-topic-defaults-v1"


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def definition_root() -> Path:
    return package_root() / "definitions"


def global_policy_registry_path() -> Path:
    return definition_root() / "global-managed-policy-registry-v1.json"


def memory_fabric_definition_path() -> Path:
    return definition_root() / "global-managed-memory-fabric-v1.json"


def core_root() -> Path:
    return Path(__file__).resolve().parents[4]


def agents_root() -> Path:
    return core_root().parent


def shared_root() -> Path:
    return agents_root() / "_shared"


def vault_root() -> Path:
    return Path("/home/agent/vaults/main/OpenClaw")


def openclaw_workspace_root() -> Path:
    return Path("/home/agent/.openclaw/workspace")


def harness_script_root() -> Path:
    return core_root() / "artifacts" / "skills" / "openclaw-skill-eval-harness-v1" / "scripts"


def creator_script_root() -> Path:
    return package_root() / "scripts"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(apply_invocation_line(path, content), encoding="utf-8")


def infer_workflow_class(args: argparse.Namespace) -> tuple[str, str, list[str]]:
    if args.workflow_class != "auto":
        return args.workflow_class, "high", [f"explicit workflow class `{args.workflow_class}` was requested"]

    request = (args.task_request or "").lower()
    if args.topic_name and not args.topic_root:
        return "topic_bootstrap", "high", ["topic bootstrap inputs were provided"]
    if args.topic_root:
        return "topic_migration", "high", ["topic migration root was provided"]
    if args.promotion_run_root or args.case_set_id:
        return "promotion_preview", "high", ["promotion preview inputs were provided"]
    if args.case_path or args.profile:
        return "clean_rerun", "high", ["clean rerun inputs were provided"]
    if args.run_root and args.readiness_mode_override:
        return "readiness_review", "high", ["readiness override plus run root were provided"]
    if args.review_run_root and args.compare_target:
        return "compare_runs", "high", ["review root plus compare targets were provided"]
    if args.review_run_root and any(keyword in request for keyword in ["current run", "latest run", "new run", "why weak", "analyze current"]):
        return "current_run_review", "medium", ["request matched current-run review keywords"]
    if args.review_run_root:
        return "historical_review", "high", ["historical review run root was provided"]
    if any(keyword in request for keyword in ["clean rerun", "contamination", "clean execution", "rerun this case"]):
        return "clean_rerun", "medium", ["task request matched clean-rerun keywords"]
    if any(keyword in request for keyword in ["compare old vs new", "compare runs", "before and after", "compare this run"]):
        return "compare_runs", "medium", ["task request matched compare keywords"]
    if any(keyword in request for keyword in ["evaluate readiness", "readiness review", "оцени готовность", "готовность линии"]):
        return "readiness_review", "medium", ["task request matched readiness-only keywords"]
    if any(keyword in request for keyword in ["current run", "latest run", "analyze current", "why this run"]):
        return "current_run_review", "medium", ["task request matched current-run review keywords"]
    if any(keyword in request for keyword in ["historical", "checkpoint", "where we stopped", "branch checkpoint"]):
        return "historical_review", "medium", ["task request matched historical/checkpoint review keywords"]
    return "canonical_managed_eval", "medium", ["defaulted to canonical managed eval because no other workflow signals were stronger"]


def build_override(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.runner_surface == "legacy":
        if not args.override_reason:
            raise SystemExit("--override-reason is required when --runner-surface=legacy")
        return {
            "mode": "legacy_runner",
            "reason": args.override_reason,
            "selected_entrypoint": str(harness_script_root() / "run_managed_skills_matrix.py"),
        }
    if args.override_reason:
        return {
            "mode": "note_only",
            "reason": args.override_reason,
            "selected_entrypoint": None,
        }
    return None


def has_pack_inputs(args: argparse.Namespace) -> bool:
    return bool(
        args.case_id
        or args.case_file
        or args.accepted_case_set
        or args.inventory_manifest
        or args.declared_capability
        or args.selection_artifact
        or args.candidate_case_id
        or args.rejected_case
        or args.case_selection
        or args.pack_mode
    )


def launch_dir_for_run_root(run_root: Path, workflow_class: str) -> Path:
    return run_root / "summaries" / "global-managed" / workflow_class


def launch_dir_for_topic_root(topic_root: Path, workflow_class: str) -> Path:
    return topic_root / ".managed" / workflow_class


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    logs_dir: Path,
    step_name: str,
    env_extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    serialized_env: dict[str, str] = {}
    if env_extra:
        serialized_env = {key: str(value) for key, value in env_extra.items()}
        env.update(serialized_env)
    completed = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False, env=env)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / f"{step_name}.command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    (logs_dir / f"{step_name}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (logs_dir / f"{step_name}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    env_log = None
    if serialized_env:
        env_log = logs_dir / f"{step_name}.env.json"
        write_json(env_log, serialized_env)
    parsed_json = None
    try:
        parsed_json = json.loads(completed.stdout) if completed.stdout.strip() else None
    except json.JSONDecodeError:
        parsed_json = None
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout_log": str(logs_dir / f"{step_name}.stdout.txt"),
        "stderr_log": str(logs_dir / f"{step_name}.stderr.txt"),
        "command_log": str(logs_dir / f"{step_name}.command.txt"),
        "env_log": str(env_log) if env_log else None,
        "parsed_json": parsed_json,
    }


def build_subprocess_env(
    *,
    workflow_class: str,
    launch_manifest_path: Path,
    launch_trace_path: Path,
    registry_path: Path,
    memory_fabric_path: Path,
    memory_selection_path: Path,
    default_path_enforced: bool,
    invocation_mode: str,
) -> dict[str, str]:
    return {
        "OPENCLAW_MANAGED_LAUNCHED": "1",
        "OPENCLAW_MANAGED_WORKFLOW_CLASS": workflow_class,
        "OPENCLAW_MANAGED_LAUNCH_MANIFEST": str(launch_manifest_path),
        "OPENCLAW_MANAGED_LAUNCH_TRACE": str(launch_trace_path),
        "OPENCLAW_MANAGED_POLICY_REGISTRY": str(registry_path),
        "OPENCLAW_MANAGED_MEMORY_FABRIC": str(memory_fabric_path),
        "OPENCLAW_MANAGED_MEMORY_SELECTION": str(memory_selection_path),
        "OPENCLAW_MANAGED_DEFAULT_PATH_ENFORCED": "1" if default_path_enforced else "0",
        "OPENCLAW_MANAGED_INVOCATION_MODE": invocation_mode,
    }


def resolve_latest_link_target(link_path: Path) -> Path | None:
    if not link_path.exists() and not link_path.is_symlink():
        return None
    try:
        return link_path.resolve(strict=True)
    except FileNotFoundError:
        return None


def detect_best_artifact_file(root: Path | None, *, preferred_names: list[str]) -> Path | None:
    if root is None or not root.exists():
        return None
    for name in preferred_names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    for candidate in sorted(root.glob("*.md")):
        if candidate.is_file():
            return candidate
    for candidate in sorted(root.glob("*.json")):
        if candidate.is_file():
            return candidate
    return None


def ensure_topic_structure(topic_root: Path) -> list[str]:
    created_or_updated: list[str] = []
    for directory in [
        topic_root,
        topic_root / "artifacts",
        topic_root / "runs",
        topic_root / "memory",
        topic_root / "DECISIONS",
    ]:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_or_updated.append(str(directory))

    defaults = {
        topic_root / "LOG.md": "# LOG\n\nКороткая хронология: что сделали -> почему -> результат.\n",
        topic_root / "TODO.md": "# TODO\n\n- [ ] Цель темы\n- [ ] DoD\n",
        topic_root / "memory" / "context.md": "# context\n\n",
        topic_root / "memory" / "index.md": "# index\n\n",
        topic_root / "memory" / "facts.md": "# facts\n\n",
        topic_root / "memory" / "refs.md": "# refs\n\n",
        topic_root / "memory" / "lessons.md": "# lessons\n\n",
    }
    for path, content in defaults.items():
        if not path.exists():
            write_text(path, content)
            created_or_updated.append(str(path))
    return created_or_updated


def topic_root_for_path(path: Path) -> Path | None:
    resolved = path.resolve()
    for candidate in [resolved, *resolved.parents]:
        if candidate.parent == agents_root():
            return candidate
    return None


def infer_topic_root(args: argparse.Namespace) -> Path | None:
    if args.topic_root:
        return Path(args.topic_root).resolve()
    candidates: list[Path] = []
    for raw in [
        args.run_root,
        args.review_run_root,
        args.promotion_run_root,
        args.case_path,
        args.out_dir,
    ]:
        if raw:
            candidates.append(Path(raw).resolve())
    for raw in args.case_file + args.compare_target:
        candidates.append(Path(raw).resolve())
    for candidate in candidates:
        topic_root = topic_root_for_path(candidate)
        if topic_root is not None:
            return topic_root
    return core_root()


def ensure_eval_inputs(args: argparse.Namespace, run_root: Path) -> tuple[bool, Path | None, Path | None]:
    trial_plan_path = run_root / "summaries" / "trial-plan.json"
    review_pack_manifest_path = run_root / "summaries" / "review-pack-manifest.json"
    existing_pack = trial_plan_path.exists()
    if existing_pack and not has_pack_inputs(args):
        return True, trial_plan_path, review_pack_manifest_path if review_pack_manifest_path.exists() else None
    if not has_pack_inputs(args):
        raise SystemExit(
            "canonical_managed_eval requires either an existing canonical trial-plan.json "
            "or pack assembly inputs such as --case-file / --case-id / --accepted-case-set"
        )
    if not args.skill_name:
        raise SystemExit("--skill-name is required when assembling a new canonical pack")
    return False, trial_plan_path if trial_plan_path.exists() else None, review_pack_manifest_path if review_pack_manifest_path.exists() else None


def register_memory_source(
    inventory: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    source_class: str,
    *,
    path: Path | None = None,
    section: str | None = None,
    scope: str = "global",
    currentness: str = "global",
    note: str | None = None,
) -> None:
    path_text = str(path.resolve()) if path is not None else ""
    key = (source_class, path_text, section or "", scope)
    if key in seen:
        return
    seen.add(key)
    inventory.append(
        {
            "source_class": source_class,
            "path": path_text or None,
            "section": section,
            "scope": scope,
            "currentness": currentness,
            "exists": path.exists() if path is not None else False,
            "note": note,
        }
    )


def register_dynamic_memory_sources(
    inventory: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    *,
    extra_sources: list[dict[str, Any]] | None,
) -> None:
    for item in extra_sources or []:
        register_memory_source(
            inventory,
            seen,
            item["source_class"],
            path=Path(item["path"]).resolve() if item.get("path") else None,
            section=item.get("section"),
            scope=item.get("scope", "global"),
            currentness=item.get("currentness", "global"),
            note=item.get("note"),
        )


def add_run_memory_sources(
    inventory: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    *,
    run_root: Path,
    scope: str,
) -> None:
    summaries_dir = run_root / "summaries"
    register_memory_source(inventory, seen, "run_review_pack_manifest", path=summaries_dir / "review-pack-manifest.json", scope=scope, currentness=scope)
    register_memory_source(inventory, seen, "run_trial_plan", path=summaries_dir / "trial-plan.json", scope=scope, currentness=scope)
    register_memory_source(
        inventory,
        seen,
        "run_pack_selection_manifest",
        path=summaries_dir / "pack-selection-manifest.json",
        scope=scope,
        currentness=scope,
    )
    register_memory_source(
        inventory,
        seen,
        "run_pack_selection_trace",
        path=summaries_dir / "pack-selection-trace.json",
        scope=scope,
        currentness=scope,
    )
    register_memory_source(inventory, seen, "run_matrix_manifest", path=summaries_dir / "matrix-run-manifest.json", scope=scope, currentness=scope)
    register_memory_source(
        inventory,
        seen,
        "run_readiness_result",
        path=summaries_dir / "context-router" / "readiness-evaluation" / "readiness-result.json",
        scope=scope,
        currentness=scope,
    )
    register_memory_source(inventory, seen, "run_result_matrix", path=run_root / "RESULT-MATRIX.md", scope=scope, currentness=scope)
    register_memory_source(inventory, seen, "run_verdict_artifact", path=run_root / "VERDICT.md", scope=scope, currentness=scope)
    register_memory_source(
        inventory,
        seen,
        "run_repeated_signal_artifact",
        path=run_root / "REPEATED-SIGNAL.md",
        scope=scope,
        currentness=scope,
    )
    for case_path in sorted((run_root / "cases").glob("*.md")):
        register_memory_source(inventory, seen, "run_case_file", path=case_path, scope=scope, currentness=scope)
    for review_path in sorted((run_root / "results").glob("*-review.md")):
        register_memory_source(inventory, seen, "run_review_file", path=review_path, scope=scope, currentness=scope)


def build_memory_artifacts(
    *,
    workflow_class: str,
    registry_path: Path,
    launch_dir: Path,
    topic_root: Path | None,
    run_root: Path | None,
    compare_targets: list[str],
    task_request: str | None,
    case_paths: list[Path] | None = None,
    extra_sources: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    definition_path = memory_fabric_definition_path()
    definition = load_json(definition_path)
    policy = definition["workflow_policies"][workflow_class]
    source_defs = definition["source_classes"]
    inventory: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    warnings: list[str] = []

    register_memory_source(inventory, seen, "policy_registry", path=registry_path, scope="global")
    register_memory_source(inventory, seen, "accepted_caveat_registry", path=registry_path, section="accepted_caveats", scope="global")
    register_memory_source(inventory, seen, "do_not_reopen_registry", path=registry_path, section="do_not_reopen", scope="global")
    register_memory_source(inventory, seen, "memory_fabric_definition", path=definition_path, scope="global")
    register_memory_source(inventory, seen, "operator_agents", path=Path("/home/agent/.codex/AGENTS.md"), scope="global")
    register_memory_source(inventory, seen, "project_steering", path=core_root() / "PROJECT-STEERING.md", scope="global")
    register_memory_source(inventory, seen, "shared_agents", path=shared_root() / "AGENTS.md", scope="global")
    register_memory_source(inventory, seen, "shared_readme", path=shared_root() / "README.md", scope="global")
    register_memory_source(inventory, seen, "shared_security", path=shared_root() / "SECURITY.md", scope="global")
    register_memory_source(inventory, seen, "shared_news", path=shared_root() / "NEWS.md", scope="global")
    register_memory_source(inventory, seen, "shared_memory_index", path=shared_root() / "memory" / "index.md", scope="global")
    register_memory_source(inventory, seen, "core_memory_index", path=core_root() / "memory" / "index.md", scope="global")
    register_memory_source(inventory, seen, "core_memory_facts", path=core_root() / "memory" / "facts.md", scope="global")
    register_memory_source(inventory, seen, "core_memory_lessons", path=core_root() / "memory" / "lessons.md", scope="global")
    register_memory_source(inventory, seen, "runtime_readme", path=agents_root() / "_runtime" / "README.md", scope="global")
    register_memory_source(inventory, seen, "runtime_registry", path=agents_root() / "_runtime" / "runtime-registry.json", scope="global")
    register_memory_source(
        inventory,
        seen,
        "runtime_manifest",
        path=agents_root() / "_runtime" / "canonical" / "meta" / "runtime-manifest.json",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "experiment_registry",
        path=core_root() / "artifacts" / "experiment-intelligence" / "skill-creator-history-v1" / "experiment-registry-v1.json",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "experiment_patterns",
        path=core_root() / "artifacts" / "experiment-intelligence" / "skill-creator-history-v1" / "pattern-extraction-v1.json",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "research_brain_state",
        path=core_root() / "artifacts" / "research-brain" / "skill-creator-history-v2" / "research-brain-state-v2.json",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "research_brain_portfolio",
        path=core_root() / "artifacts" / "research-brain" / "skill-creator-history-v2" / "next-step-portfolio-v2.json",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "research_brain_rules",
        path=core_root() / "runtime" / "research-brain-v2" / "research_brain_rules_v2.json",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "openclaw_workspace_memory",
        path=openclaw_workspace_root() / "MEMORY.md",
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "openclaw_workspace_tools",
        path=openclaw_workspace_root() / "TOOLS.md",
        scope="global",
    )
    register_memory_source(inventory, seen, "vault_current_status", path=vault_root() / "current-project-status.md", scope="global")
    for summary_path in sorted((vault_root() / "session-summaries").glob("*.md"), reverse=True)[:3]:
        register_memory_source(inventory, seen, "vault_session_summary", path=summary_path, scope="global", currentness="historical")
    register_memory_source(
        inventory,
        seen,
        "retrieval_latest_answer",
        path=detect_best_artifact_file(
            resolve_latest_link_target(core_root() / "artifacts" / "retrieval-execution" / "latest"),
            preferred_names=["ANSWER.md", "SUMMARY.md", "REPORT.md", "README.md"],
        ),
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "research_latest_summary",
        path=detect_best_artifact_file(
            resolve_latest_link_target(core_root() / "artifacts" / "research" / "latest"),
            preferred_names=["RESEARCH.md", "SUMMARY.md", "README.md"],
        ),
        scope="global",
    )
    register_memory_source(
        inventory,
        seen,
        "graph_memory_connector",
        scope="global",
        note="best-effort helper connector exposed through graphmem-recall when local auth is available",
    )
    register_memory_source(inventory, seen, "vector_memory_connector", scope="global", note="no local runtime connector is currently exposed")

    if topic_root is not None:
        register_memory_source(inventory, seen, "topic_agents", path=topic_root / "AGENTS.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_readme", path=topic_root / "README.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_managed_defaults", path=topic_root / "managed-defaults.json", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_todo", path=topic_root / "TODO.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_log", path=topic_root / "LOG.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_memory_context", path=topic_root / "memory" / "context.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_memory_index", path=topic_root / "memory" / "index.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_memory_facts", path=topic_root / "memory" / "facts.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_memory_refs", path=topic_root / "memory" / "refs.md", scope="topic", currentness="topic")
        register_memory_source(inventory, seen, "topic_memory_lessons", path=topic_root / "memory" / "lessons.md", scope="topic", currentness="topic")

    if run_root is not None:
        add_run_memory_sources(inventory, seen, run_root=run_root, scope="current_run")

    for case_path in case_paths or []:
        register_memory_source(
            inventory,
            seen,
            "run_case_file",
            path=case_path.resolve(),
            scope="current_case",
            currentness="current_case",
        )

    for raw_target in compare_targets:
        compare_root = Path(raw_target).resolve()
        if compare_root.is_dir():
            add_run_memory_sources(inventory, seen, run_root=compare_root, scope="compare_target")

    register_dynamic_memory_sources(inventory, seen, extra_sources=extra_sources)

    primary: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    human_only: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    graph_recall_available = any(item["source_class"] == "query_graph_recall" and item["exists"] for item in inventory)

    for item in inventory:
        source_class = item["source_class"]
        exists = item["exists"]
        if source_class == "graph_memory_connector":
            if graph_recall_available:
                role = "supporting"
            else:
                role = "unavailable"
                warnings.append("graph memory connector is best-effort and no authenticated graph recall was available for this request")
        elif source_class == "vector_memory_connector":
            role = "unavailable"
            warnings.append("vector memory connector is declared in the fabric, but no local callable vector runtime is currently exposed")
        elif not exists and item["path"] is not None:
            role = "unavailable"
            warnings.append(f"memory source missing: {source_class} -> {item['path']}")
        elif source_class in policy["primary"]:
            role = "primary"
        elif source_class in policy["supporting"]:
            role = "supporting"
        elif source_class in policy["human_only"]:
            role = "human_only"
        else:
            role = "excluded"

        item["authority"] = source_defs[source_class]["authority"]
        item["description"] = source_defs[source_class]["description"]
        item["selected_role"] = role
        item["selection_reason"] = f"workflow policy `{workflow_class}` mapped `{source_class}` to `{role}`"

        if role == "primary":
            primary.append(item)
        elif role == "supporting":
            supporting.append(item)
        elif role == "human_only":
            human_only.append(item)
        elif role == "excluded":
            excluded.append(item)
        else:
            unavailable.append(item)

    fabric_payload = {
        "format": GLOBAL_MANAGED_MEMORY_FABRIC_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(definition_path),
        "topic_root": str(topic_root) if topic_root else None,
        "run_root": str(run_root) if run_root else None,
        "compare_targets": compare_targets,
        "task_request": task_request,
        "source_inventory": inventory,
    }
    selection_payload = {
        "format": GLOBAL_MANAGED_MEMORY_SELECTION_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "contamination_sensitive": policy["contamination_sensitive"],
        "topic_root": str(topic_root) if topic_root else None,
        "run_root": str(run_root) if run_root else None,
        "compare_targets": compare_targets,
        "task_request": task_request,
        "primary": primary,
        "supporting": supporting,
        "excluded": excluded,
        "human_only": human_only,
        "unavailable": unavailable,
        "warning_signals": sorted(set(warnings)),
        "counts": {
            "primary": len(primary),
            "supporting": len(supporting),
            "excluded": len(excluded),
            "human_only": len(human_only),
            "unavailable": len(unavailable),
        },
    }

    fabric_path = launch_dir / "managed-memory-fabric.json"
    selection_path = launch_dir / "managed-memory-selection.json"
    write_json(fabric_path, fabric_payload)
    write_json(selection_path, selection_payload)
    return fabric_path, selection_path, fabric_payload, selection_payload


def inject_global_managed_fields(
    path: Path,
    *,
    registry_path: Path,
    launch_manifest_path: Path,
    launch_trace_path: Path,
    memory_fabric_path: Path,
    memory_selection_path: Path,
    workflow_class: str,
    default_path_enforced: bool,
    override: dict[str, Any] | None,
    invocation_mode: str,
) -> None:
    if not path.exists():
        return
    payload = load_json(path)
    payload["global_managed_policy_registry"] = str(registry_path)
    payload["global_managed_launch_manifest"] = str(launch_manifest_path)
    payload["global_managed_launch_trace"] = str(launch_trace_path)
    payload["global_managed_memory_fabric"] = str(memory_fabric_path)
    payload["global_managed_memory_selection"] = str(memory_selection_path)
    payload["global_managed_workflow_class"] = workflow_class
    payload["global_managed_default_path_enforced"] = default_path_enforced
    payload["global_managed_override"] = override
    payload["global_managed_invocation_mode"] = invocation_mode
    write_json(path, payload)


def build_eval_manifest(
    *,
    run_root: Path,
    workflow_class: str,
    registry_path: Path,
    inferred_confidence: str,
    classification_reasons: list[str],
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    canonical_steps = load_json(registry_path)["canonical_managed_path"]
    return {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "classification_confidence": inferred_confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": override is None,
        "override": override,
        "canonical_steps": canonical_steps,
        "component_entrypoints": {
            "pack_generator": str(creator_script_root() / "generate_review_pack.py"),
            "canonical_runner": str(harness_script_root() / "run_skill_trial_matrix.py"),
            "legacy_runner": str(harness_script_root() / "run_managed_skills_matrix.py"),
            "case_runner": str(harness_script_root() / "run_local_agent_eval.py"),
            "readiness": str(creator_script_root() / "evaluate_readiness.py"),
            "historical_review": str(harness_script_root() / "review_current_run.py"),
        },
        "outputs": {},
    }


def render_topic_agents(topic_name: str, registry_path: Path) -> str:
    return "\n".join(
        [
            f"# {topic_name} Topic Rules",
            "",
            "Status: managed-topic-bootstrap",
            f"Updated: {datetime.now().date().isoformat()}",
            "",
            "This topic inherits the global managed canonical default path.",
            "",
            "## Managed workflow rule",
            "",
            "- Use `/home/agent/bin/agent-exec` as the default natural-language server entrypoint for managed work.",
            "- When substantial work is performed from Codex chat, start with `/home/agent/bin/codex-frontdoor-preflight` so routing, memory, tool, and skill decisions are traced before execution.",
            f"- Use `{Path(__file__).resolve()}` as the managed backend launcher for structured workflows in this topic.",
            f"- Use `{registry_path}` as the source-of-truth policy registry for managed workflow defaults, coverage, override modes, caveats, and do-not-reopen items.",
            f"- Use `{memory_fabric_definition_path()}` as the source-of-truth memory-fabric policy for managed workflow memory selection.",
            "- Treat compatibility or legacy paths as explicit exception modes, not as the default route.",
            "- Record an explicit override reason whenever a managed workflow bypasses the canonical launcher or asks for a compatibility-only entrypoint.",
            "",
        ]
    ) + "\n"


def render_topic_readme(topic_name: str, registry_path: Path) -> str:
    return "\n".join(
        [
            f"# {topic_name}",
            "",
            "## Managed default",
            "",
            "- Server AI entrypoint: `/home/agent/bin/agent-exec`",
            "- Codex chat preflight helper: `/home/agent/bin/codex-frontdoor-preflight`",
            f"- Managed backend launcher: `{Path(__file__).resolve()}`",
            f"- Policy registry: `{registry_path}`",
            f"- Memory fabric: `{memory_fabric_definition_path()}`",
            "- Default workflow class: `canonical_managed_eval`",
            "- Default canonical path: `generate_review_pack.py -> pack-selection-trace.json -> pack-selection-manifest.json -> trial-plan.json -> run_skill_trial_matrix.py -> completed reviews -> evaluate_readiness.py -> promotion-preview or deliberate adoption`",
            "- Additional managed workflows: `historical_review`, `current_run_review`, `readiness_review`, `compare_runs`, `clean_rerun`, `promotion_preview`, `topic_migration`, `research_request`, `current_state_lookup`.",
            "- Codex chat stays in the current conversation for open-ended substantial work after preflight instead of silently switching to a parallel mode.",
            "- Compatibility paths remain available, but only as explicit override modes.",
            "",
        ]
    ) + "\n"


def topic_defaults_payload(topic_root: Path, registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    return {
        "format": TOPIC_DEFAULTS_FORMAT,
        "topic_name": topic_root.name,
        "topic_root": str(topic_root),
        "server_ai_entrypoint": registry.get("default_server_entrypoint", "/home/agent/bin/agent-exec"),
        "codex_frontdoor_preflight": registry.get("meta_launcher_policy", {}).get("codex_chat_preflight_entrypoint", "/home/agent/bin/codex-frontdoor-preflight"),
        "codex_frontdoor_binding": f"{registry_path}#codex_frontdoor_binding",
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "managed_standard": registry["managed_standard"],
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "accepted_caveats_registry": f"{registry_path}#accepted_caveats",
        "do_not_reopen_registry": f"{registry_path}#do_not_reopen",
        "default_workflow_class": registry["default_workflow_class"],
        "allowed_workflow_classes": sorted(registry["workflow_classes"].keys()),
        "frontdoor_intent_classes": sorted(registry.get("meta_intent_classes", {}).keys()),
        "canonical_managed_path": registry["canonical_managed_path"],
        "override_requires_reason": True,
    }


def upsert_hook_block(path: Path, marker: str, lines: list[str]) -> bool:
    block = "\n".join(lines).rstrip() + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if marker in existing:
            prefix = existing.split(marker, 1)[0].rstrip()
            updated = f"{prefix}\n\n{block}" if prefix else block
        else:
            updated = existing.rstrip() + "\n\n" + block
    else:
        updated = block
    if path.exists() and existing == updated:
        return False
    write_text(path, updated)
    return True


def bootstrap_topic(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    registry_path = global_policy_registry_path()
    bootstrap_root = Path(args.bootstrap_root or str(agents_root()))
    topic_root = bootstrap_root / args.topic_name
    if topic_root.exists() and any(topic_root.iterdir()) and not args.force:
        raise SystemExit(f"topic root already exists and is not empty: {topic_root}; pass --force to continue")

    topic_root.mkdir(parents=True, exist_ok=True)
    created_paths = ensure_topic_structure(topic_root)
    agents_path = topic_root / "AGENTS.md"
    readme_path = topic_root / "README.md"
    defaults_path = topic_root / "managed-defaults.json"
    launch_dir = launch_dir_for_topic_root(topic_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"

    write_text(agents_path, render_topic_agents(args.topic_name, registry_path))
    write_text(readme_path, render_topic_readme(args.topic_name, registry_path))
    write_json(defaults_path, topic_defaults_payload(topic_root, registry_path))
    memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
        workflow_class=workflow_class,
        registry_path=registry_path,
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=None,
        compare_targets=[],
        task_request=args.task_request,
        case_paths=[],
    )

    manifest = {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "topic_root": str(topic_root),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": True,
        "override": None,
        "created_files": sorted(set(created_paths + [str(agents_path), str(readme_path), str(defaults_path)])),
    }
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(topic_root),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": "topic_bootstrap",
        "default_path_enforced": True,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": None,
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    env_extra = build_subprocess_env(
        workflow_class=workflow_class,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        registry_path=registry_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        default_path_enforced=True,
        invocation_mode="launcher_default",
    )
    return {
        "workflow_class": workflow_class,
        "topic_root": str(topic_root),
        "managed_defaults": str(defaults_path),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "created_files": manifest["created_files"],
    }


def migrate_topic(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    registry_path = global_policy_registry_path()
    topic_root = Path(args.topic_root).resolve()
    if not topic_root.is_dir():
        raise SystemExit(f"topic root missing: {topic_root}")

    changed_files: list[str] = ensure_topic_structure(topic_root)
    agents_path = topic_root / "AGENTS.md"
    readme_path = topic_root / "README.md"
    defaults_path = topic_root / "managed-defaults.json"
    launch_dir = launch_dir_for_topic_root(topic_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"
    memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
        workflow_class=workflow_class,
        registry_path=registry_path,
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=None,
        compare_targets=[],
        task_request=args.task_request,
        case_paths=[],
    )

    agents_changed = upsert_hook_block(
        agents_path,
        "<!-- managed-default-hook -->",
        [
            "<!-- managed-default-hook -->",
            "## Managed default path",
            "- Server AI entrypoint: `/home/agent/bin/agent-exec`",
            "- Codex chat preflight helper: `/home/agent/bin/codex-frontdoor-preflight`",
            f"- Managed backend launcher: `{Path(__file__).resolve()}`",
            f"- Global managed policy registry: `{registry_path}`",
            f"- Global memory fabric: `{memory_fabric_definition_path()}`",
            "- In Codex chat, substantial work should start with the preflight helper so frontdoor routing and trace are created before execution.",
            "- Compatibility and direct script paths are exception modes, not the default route.",
        ],
    )
    if agents_changed:
        changed_files.append(str(agents_path))

    readme_changed = upsert_hook_block(
        readme_path,
        "<!-- managed-default-hook -->",
        [
            "<!-- managed-default-hook -->",
            "## Managed default path",
            "- Server AI entrypoint: `/home/agent/bin/agent-exec`",
            "- Codex chat preflight helper: `/home/agent/bin/codex-frontdoor-preflight`",
            f"- Managed backend launcher: `{Path(__file__).resolve()}`",
            "- Default workflow class: `canonical_managed_eval`",
            "- Canonical managed path: `generate_review_pack.py -> pack-selection-trace.json -> pack-selection-manifest.json -> trial-plan.json -> run_skill_trial_matrix.py -> evaluate_readiness.py -> promotion-preview or deliberate adoption`",
            "- For open-ended substantial work in Codex chat, use the preflight helper first and continue in the same chat unless the contract selects a narrower backend.",
            "- Use compatibility or direct component paths only as explicit exception modes.",
        ],
    )
    if readme_changed:
        changed_files.append(str(readme_path))

    write_json(defaults_path, topic_defaults_payload(topic_root, registry_path))
    changed_files.append(str(defaults_path))

    manifest = {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "topic_root": str(topic_root),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": True,
        "override": None,
        "changed_files": changed_files,
    }
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(topic_root),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": "topic_migration",
        "default_path_enforced": True,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": None,
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    return {
        "workflow_class": workflow_class,
        "topic_root": str(topic_root),
        "managed_defaults": str(defaults_path),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "changed_files": changed_files,
    }


def canonical_managed_eval(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    run_root = Path(args.run_root).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    registry_path = global_policy_registry_path()
    topic_root = infer_topic_root(args)
    override = build_override(args)
    existing_pack, trial_plan_path, review_pack_manifest_path = ensure_eval_inputs(args, run_root)
    launch_dir = launch_dir_for_run_root(run_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"
    logs_dir = launch_dir / "logs"
    case_paths = [Path(value).resolve() for value in args.case_file]
    trace: dict[str, Any] | None = None

    def refresh_memory_artifacts() -> tuple[Path, Path, dict[str, Any]]:
        nonlocal manifest, trace
        memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
            workflow_class=workflow_class,
            registry_path=registry_path,
            launch_dir=launch_dir,
            topic_root=topic_root,
            run_root=run_root,
            compare_targets=[],
            task_request=args.task_request,
            case_paths=case_paths,
        )
        manifest["outputs"]["memory_fabric"] = str(memory_fabric_path)
        manifest["outputs"]["memory_selection"] = str(memory_selection_path)
        if trace is not None:
            trace["warnings"] = selection["warning_signals"]
            trace["memory_selection"] = str(memory_selection_path)
        return memory_fabric_path, memory_selection_path, selection

    manifest = build_eval_manifest(
        run_root=run_root,
        workflow_class=workflow_class,
        registry_path=registry_path,
        inferred_confidence=confidence,
        classification_reasons=classification_reasons,
        override=override,
    )
    memory_fabric_path, memory_selection_path, selection = refresh_memory_artifacts()
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(run_root),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": "canonical_managed_eval",
        "default_path_enforced": override is None,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": override,
        "used_existing_pack": existing_pack,
        "steps": [],
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    env_extra = build_subprocess_env(
        workflow_class=workflow_class,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        registry_path=registry_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        default_path_enforced=override is None,
        invocation_mode="launcher_default" if override is None else "launcher_override",
    )

    if not existing_pack:
        cmd = [
            "python3",
            str(creator_script_root() / "generate_review_pack.py"),
            "--run-root",
            str(run_root),
            "--skill-name",
            args.skill_name,
        ]
        for value in args.case_id:
            cmd.extend(["--case-id", value])
        for value in args.case_file:
            cmd.extend(["--case-file", value])
        if args.accepted_case_set:
            cmd.extend(["--accepted-case-set", args.accepted_case_set])
        if args.baseline_profile:
            cmd.extend(["--baseline-profile", args.baseline_profile])
        if args.trial_profile:
            cmd.extend(["--trial-profile", args.trial_profile])
        if args.inventory_manifest:
            cmd.extend(["--inventory-manifest", args.inventory_manifest])
        if args.pack_mode:
            cmd.extend(["--pack-mode", args.pack_mode])
        for value in args.declared_capability:
            cmd.extend(["--declared-capability", value])
        for value in args.selection_artifact:
            cmd.extend(["--selection-artifact", value])
        for value in args.candidate_case_id:
            cmd.extend(["--candidate-case-id", value])
        for value in args.rejected_case:
            cmd.extend(["--rejected-case", value])
        for value in args.case_selection:
            cmd.extend(["--case-selection", value])
        step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="generate-review-pack", env_extra=env_extra)
        trace["steps"].append({"name": "generate-review-pack", **step})
        if step["returncode"] != 0:
            write_json(launch_trace_path, trace)
            raise SystemExit(f"generate_review_pack.py failed; see {step['stderr_log']}")
        memory_fabric_path, memory_selection_path, selection = refresh_memory_artifacts()
        env_extra = build_subprocess_env(
            workflow_class=workflow_class,
            launch_manifest_path=launch_manifest_path,
            launch_trace_path=launch_trace_path,
            registry_path=registry_path,
            memory_fabric_path=memory_fabric_path,
            memory_selection_path=memory_selection_path,
            default_path_enforced=override is None,
            invocation_mode="launcher_default" if override is None else "launcher_override",
        )

    trial_plan_path = run_root / "summaries" / "trial-plan.json"
    review_pack_manifest_path = run_root / "summaries" / "review-pack-manifest.json"
    inject_global_managed_fields(
        trial_plan_path,
        registry_path=registry_path,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        workflow_class=workflow_class,
        default_path_enforced=override is None,
        override=override,
        invocation_mode="launcher_default",
    )
    inject_global_managed_fields(
        review_pack_manifest_path,
        registry_path=registry_path,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        workflow_class=workflow_class,
        default_path_enforced=override is None,
        override=override,
        invocation_mode="launcher_default",
    )

    manifest["outputs"]["review_pack_manifest"] = str(review_pack_manifest_path)
    manifest["outputs"]["trial_plan"] = str(trial_plan_path)

    runner_entrypoint = (
        harness_script_root() / "run_managed_skills_matrix.py"
        if override and override.get("mode") == "legacy_runner"
        else harness_script_root() / "run_skill_trial_matrix.py"
    )
    manifest["selected_runner_entrypoint"] = str(runner_entrypoint)

    if not args.skip_matrix:
        cmd = ["python3", str(runner_entrypoint), "--run-root", str(run_root)]
        if args.prepare_only:
            cmd.append("--prepare-only")
        if args.matrix_mode_override:
            cmd.extend(["--matrix-mode-override", args.matrix_mode_override])
        step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="matrix-run", env_extra=env_extra)
        trace["steps"].append({"name": "matrix-run", **step})
        if step["returncode"] != 0:
            write_json(launch_trace_path, trace)
            raise SystemExit(f"matrix runner failed; see {step['stderr_log']}")
        manifest["outputs"]["matrix_manifest"] = str(run_root / "summaries" / "matrix-run-manifest.json")
        memory_fabric_path, memory_selection_path, selection = refresh_memory_artifacts()
        env_extra = build_subprocess_env(
            workflow_class=workflow_class,
            launch_manifest_path=launch_manifest_path,
            launch_trace_path=launch_trace_path,
            registry_path=registry_path,
            memory_fabric_path=memory_fabric_path,
            memory_selection_path=memory_selection_path,
            default_path_enforced=override is None,
            invocation_mode="launcher_default" if override is None else "launcher_override",
        )

    if not args.skip_readiness:
        cmd = ["python3", str(creator_script_root() / "evaluate_readiness.py"), "--run-root", str(run_root)]
        if args.readiness_mode_override:
            cmd.extend(["--readiness-mode-override", args.readiness_mode_override])
        step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="evaluate-readiness", env_extra=env_extra)
        trace["steps"].append({"name": "evaluate-readiness", **step})
        if step["returncode"] != 0:
            write_json(launch_trace_path, trace)
            raise SystemExit(f"evaluate_readiness.py failed; see {step['stderr_log']}")
        manifest["outputs"]["readiness_result"] = str(
            run_root / "summaries" / "context-router" / "readiness-evaluation" / "readiness-result.json"
        )
        memory_fabric_path, memory_selection_path, selection = refresh_memory_artifacts()

    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    return {
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "review_pack_manifest": str(review_pack_manifest_path),
        "trial_plan": str(trial_plan_path),
        "matrix_manifest": manifest["outputs"].get("matrix_manifest"),
        "readiness_result": manifest["outputs"].get("readiness_result"),
        "runner_entrypoint": str(runner_entrypoint),
        "override": override,
    }


def review_workflow(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    run_root = Path(args.review_run_root).resolve()
    registry_path = global_policy_registry_path()
    topic_root = infer_topic_root(args)
    launch_dir = launch_dir_for_run_root(run_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"
    logs_dir = launch_dir / "logs"
    out_dir = launch_dir / "review-output"
    if workflow_class == "historical_review":
        request = args.task_request or "Review this run root through the managed historical/checkpoint path."
    elif workflow_class == "current_run_review":
        request = args.task_request or "Analyze this current run with the current run root as primary truth and history as supporting-only."
    else:
        request = args.task_request or "Compare this run root against the explicit compare targets through the managed compare path."
    memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
        workflow_class=workflow_class,
        registry_path=registry_path,
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=run_root,
        compare_targets=args.compare_target,
        task_request=request,
        case_paths=[],
    )

    manifest = {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": True,
        "override": None,
        "selected_review_entrypoint": str(harness_script_root() / "review_current_run.py"),
        "outputs": {},
    }
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(run_root),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": workflow_class,
        "default_path_enforced": True,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": None,
        "steps": [],
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    env_extra = build_subprocess_env(
        workflow_class=workflow_class,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        registry_path=registry_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        default_path_enforced=True,
        invocation_mode="launcher_default",
    )

    cmd = [
        "python3",
        str(harness_script_root() / "review_current_run.py"),
        "--run-root",
        str(run_root),
        "--request",
        request,
        "--out-dir",
        str(out_dir),
    ]
    for value in args.compare_target:
        cmd.extend(["--compare-target", value])
    if args.review_mode_override:
        cmd.extend(["--mode-override", args.review_mode_override])
    step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name=workflow_class, env_extra=env_extra)
    trace["steps"].append({"name": workflow_class, **step})
    if step["returncode"] != 0:
        write_json(launch_trace_path, trace)
        raise SystemExit(f"review_current_run.py failed; see {step['stderr_log']}")

    manifest["outputs"]["review_json"] = str(out_dir / "current-run-review.json")
    manifest["outputs"]["review_md"] = str(out_dir / "current-run-review.md")
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    return {
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "review_json": manifest["outputs"]["review_json"],
        "review_md": manifest["outputs"]["review_md"],
    }


def readiness_review(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    run_root = Path(args.run_root).resolve()
    registry_path = global_policy_registry_path()
    topic_root = infer_topic_root(args)
    launch_dir = launch_dir_for_run_root(run_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"
    logs_dir = launch_dir / "logs"
    request = args.task_request or "Evaluate readiness for this canonical managed run through the readiness-only path."
    memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
        workflow_class=workflow_class,
        registry_path=registry_path,
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=run_root,
        compare_targets=[],
        task_request=request,
        case_paths=[],
    )

    manifest = {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": True,
        "override": None,
        "selected_readiness_entrypoint": str(creator_script_root() / "evaluate_readiness.py"),
        "outputs": {},
    }
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(run_root),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": "readiness_review",
        "default_path_enforced": True,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": None,
        "steps": [],
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    env_extra = build_subprocess_env(
        workflow_class=workflow_class,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        registry_path=registry_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        default_path_enforced=True,
        invocation_mode="launcher_default",
    )

    cmd = ["python3", str(creator_script_root() / "evaluate_readiness.py"), "--run-root", str(run_root)]
    if args.readiness_mode_override:
        cmd.extend(["--readiness-mode-override", args.readiness_mode_override])
    step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="readiness-review", env_extra=env_extra)
    trace["steps"].append({"name": "readiness-review", **step})
    if step["returncode"] != 0:
        write_json(launch_trace_path, trace)
        raise SystemExit(f"evaluate_readiness.py failed; see {step['stderr_log']}")

    manifest["outputs"]["readiness_result"] = str(
        run_root / "summaries" / "context-router" / "readiness-evaluation" / "readiness-result.json"
    )
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    return {
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "readiness_result": manifest["outputs"]["readiness_result"],
    }


def clean_rerun(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    if not args.run_root:
        raise SystemExit("--run-root is required for clean_rerun")
    if not args.case_path:
        raise SystemExit("--case-path is required for clean_rerun")
    if not args.profile:
        raise SystemExit("--profile is required for clean_rerun")

    run_root = Path(args.run_root).resolve()
    case_path = Path(args.case_path).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else run_root / "raw" / case_path.stem / "managed-clean-rerun"
    registry_path = global_policy_registry_path()
    topic_root = infer_topic_root(args)
    launch_dir = launch_dir_for_run_root(run_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"
    logs_dir = launch_dir / "logs"
    memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
        workflow_class=workflow_class,
        registry_path=registry_path,
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=run_root,
        compare_targets=[],
        task_request=args.task_request,
        case_paths=[case_path],
    )

    manifest = {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "case_path": str(case_path),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": True,
        "override": None,
        "selected_case_runner": str(harness_script_root() / "run_local_agent_eval.py"),
        "outputs": {},
    }
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(case_path),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": "clean_rerun",
        "default_path_enforced": True,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": None,
        "steps": [],
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    env_extra = build_subprocess_env(
        workflow_class=workflow_class,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        registry_path=registry_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        default_path_enforced=True,
        invocation_mode="launcher_default",
    )

    cmd = [
        "python3",
        str(harness_script_root() / "run_local_agent_eval.py"),
        "--profile",
        args.profile,
        "--case",
        str(case_path),
        "--out-dir",
        str(out_dir),
        "--timeout",
        str(args.timeout),
        "--thinking",
        args.thinking,
        "--mode-override",
        "clean_execution",
    ]
    if args.run_label:
        cmd.extend(["--run-label", args.run_label])
    if args.session_id:
        cmd.extend(["--session-id", args.session_id])
    if args.prepare_only:
        cmd.append("--prepare-only")
    step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="clean-rerun", env_extra=env_extra)
    trace["steps"].append({"name": "clean-rerun", **step})
    if step["returncode"] != 0:
        write_json(launch_trace_path, trace)
        raise SystemExit(f"run_local_agent_eval.py failed; see {step['stderr_log']}")

    manifest["outputs"]["run_summary"] = str(out_dir / "run-summary.json")
    manifest["outputs"]["decision_trace"] = str(out_dir / "context-router" / "decision-trace.json")
    manifest["outputs"]["working_set"] = str(out_dir / "context-router" / "working-set.json")
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    return {
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "case_path": str(case_path),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "run_summary": manifest["outputs"]["run_summary"],
    }


def promotion_preview(
    args: argparse.Namespace,
    *,
    workflow_class: str,
    confidence: str,
    classification_reasons: list[str],
) -> dict[str, Any]:
    run_root = Path(args.promotion_run_root).resolve()
    registry_path = global_policy_registry_path()
    topic_root = infer_topic_root(args)
    preview_root = Path(args.preview_root).resolve() if args.preview_root else run_root / "promotion-preview"
    launch_dir = launch_dir_for_run_root(run_root, workflow_class)
    launch_manifest_path = launch_dir / "managed-launch-manifest.json"
    launch_trace_path = launch_dir / "managed-launch-trace.json"
    logs_dir = launch_dir / "logs"
    memory_fabric_path, memory_selection_path, _fabric, selection = build_memory_artifacts(
        workflow_class=workflow_class,
        registry_path=registry_path,
        launch_dir=launch_dir,
        topic_root=topic_root,
        run_root=run_root,
        compare_targets=[],
        task_request=args.task_request,
        case_paths=[],
    )

    manifest = {
        "format": GLOBAL_MANAGED_MANIFEST_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "launcher_entrypoint": str(Path(__file__).resolve()),
        "policy_registry": str(registry_path),
        "memory_fabric_definition": str(memory_fabric_definition_path()),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "default_path_enforced": True,
        "override": None,
        "selected_promotion_entrypoint": str(creator_script_root() / "promote_accepted_case_set.py"),
        "preview_root": str(preview_root),
        "outputs": {},
    }
    trace = {
        "format": GLOBAL_MANAGED_TRACE_FORMAT,
        "generated_at": now_utc_iso(),
        "workflow_class": workflow_class,
        "target": str(run_root),
        "selected_policy_path": str(registry_path),
        "selected_path_kind": "promotion_preview",
        "default_path_enforced": True,
        "classification_confidence": confidence,
        "classification_reasons": classification_reasons,
        "warnings": selection["warning_signals"],
        "memory_selection": str(memory_selection_path),
        "override": None,
        "steps": [],
    }
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    env_extra = build_subprocess_env(
        workflow_class=workflow_class,
        launch_manifest_path=launch_manifest_path,
        launch_trace_path=launch_trace_path,
        registry_path=registry_path,
        memory_fabric_path=memory_fabric_path,
        memory_selection_path=memory_selection_path,
        default_path_enforced=True,
        invocation_mode="launcher_default",
    )

    cmd = [
        "python3",
        str(creator_script_root() / "promote_accepted_case_set.py"),
        "--run-root",
        str(run_root),
        "--case-set-id",
        args.case_set_id,
        "--description",
        args.description,
        "--registry-root",
        str(preview_root),
        "--status",
        args.promotion_status,
        "--force",
    ]
    step = run_command(cmd, cwd=Path("/home/agent"), logs_dir=logs_dir, step_name="promotion-preview", env_extra=env_extra)
    trace["steps"].append({"name": "promotion-preview", **step})
    if step["returncode"] != 0:
        write_json(launch_trace_path, trace)
        raise SystemExit(f"promote_accepted_case_set.py failed; see {step['stderr_log']}")

    preview_manifest = preview_root / args.case_set_id / "manifest.json"
    manifest["outputs"]["promotion_preview_manifest"] = str(preview_manifest)
    write_json(launch_manifest_path, manifest)
    write_json(launch_trace_path, trace)
    return {
        "workflow_class": workflow_class,
        "run_root": str(run_root),
        "memory_fabric": str(memory_fabric_path),
        "memory_selection": str(memory_selection_path),
        "launch_manifest": str(launch_manifest_path),
        "launch_trace": str(launch_trace_path),
        "promotion_preview_manifest": str(preview_manifest),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow-class",
        default="auto",
        choices=[
            "auto",
            "canonical_managed_eval",
            "historical_review",
            "current_run_review",
            "readiness_review",
            "compare_runs",
            "clean_rerun",
            "promotion_preview",
            "topic_bootstrap",
            "topic_migration",
        ],
    )
    parser.add_argument("--task-request")

    parser.add_argument("--run-root")
    parser.add_argument("--skill-name")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--case-file", action="append", default=[])
    parser.add_argument("--accepted-case-set")
    parser.add_argument("--baseline-profile")
    parser.add_argument("--trial-profile")
    parser.add_argument("--declared-capability", action="append", default=[])
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
    parser.add_argument("--runner-surface", choices=["canonical", "legacy"], default="canonical")
    parser.add_argument("--override-reason")

    parser.add_argument("--review-run-root")
    parser.add_argument("--compare-target", action="append", default=[])
    parser.add_argument("--review-mode-override")

    parser.add_argument("--case-path")
    parser.add_argument("--profile")
    parser.add_argument("--out-dir")
    parser.add_argument("--run-label")
    parser.add_argument("--thinking", default="off")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--session-id")

    parser.add_argument("--promotion-run-root")
    parser.add_argument("--case-set-id")
    parser.add_argument("--description")
    parser.add_argument("--preview-root")
    parser.add_argument("--promotion-status", default="candidate", choices=["accepted", "candidate", "superseded"])

    parser.add_argument("--topic-name")
    parser.add_argument("--topic-root")
    parser.add_argument("--bootstrap-root")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflow_class, confidence, classification_reasons = infer_workflow_class(args)

    if workflow_class == "topic_bootstrap":
        if not args.topic_name:
            raise SystemExit("--topic-name is required for topic_bootstrap")
        result = bootstrap_topic(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )
    elif workflow_class == "topic_migration":
        if not args.topic_root:
            raise SystemExit("--topic-root is required for topic_migration")
        result = migrate_topic(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )
    elif workflow_class in {"historical_review", "current_run_review", "compare_runs"}:
        if not args.review_run_root:
            raise SystemExit("--review-run-root is required for review workflows")
        if workflow_class == "compare_runs" and not args.compare_target:
            raise SystemExit("--compare-target is required for compare_runs")
        result = review_workflow(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )
    elif workflow_class == "readiness_review":
        if not args.run_root:
            raise SystemExit("--run-root is required for readiness_review")
        result = readiness_review(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )
    elif workflow_class == "promotion_preview":
        if not args.promotion_run_root or not args.case_set_id or not args.description:
            raise SystemExit("--promotion-run-root, --case-set-id, and --description are required for promotion_preview")
        result = promotion_preview(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )
    elif workflow_class == "clean_rerun":
        result = clean_rerun(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )
    else:
        if not args.run_root:
            raise SystemExit("--run-root is required for canonical_managed_eval")
        result = canonical_managed_eval(
            args,
            workflow_class=workflow_class,
            confidence=confidence,
            classification_reasons=classification_reasons,
        )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
