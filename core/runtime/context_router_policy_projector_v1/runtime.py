#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/agent/agents")
SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR / "context_router_rules_v1.json"
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".py",
    ".sh",
    ".toml",
    ".csv",
}
RUN_ID_RE = re.compile(r"/(runs|artifacts)/([^/]+)")
DATE_PREFIX_RE = re.compile(r"^(20\d{2}-\d{2}-\d{2})")
PATH_RE = re.compile(r"(/home/agent/[^\s`\"')]+)")
HISTORICAL_KEYWORDS = (
    "checkpoint",
    "where we stopped",
    "where did we stop",
    "repeated signal",
    "historical review",
    "history",
    "accumulated runs",
    "branch checkpoint",
    "compare accumulated",
    "где мы остановились",
    "истор",
    "чекпоинт",
    "повторяющ",
    "накоплен",
)
CURRENT_KEYWORDS = (
    "current run",
    "latest run",
    "last run",
    "this run",
    "run root",
    "current-root",
    "analyze this run",
    "why the new run",
    "why this run",
    "new run root",
    "именно этот новый run root",
    "последн",
    "текущ",
    "разберись",
    "почему новый запуск",
)
CLEAN_KEYWORDS = (
    "clean rerun",
    "clean run",
    "honest rerun",
    "without leakage",
    "without old conclusions",
    "no leakage",
    "contamination",
    "contaminated",
    "fresh rerun",
    "strict rerun",
    "чист",
    "честно",
    "утечк",
    "загрязн",
    "без старых выводов",
)
COMPARE_KEYWORDS = (
    "compare",
    "vs",
    "versus",
    "before and after",
    "before patch",
    "after patch",
    "old vs new",
    "stronger eval",
    "broader eval",
    "сравни",
    "до патча",
    "после патча",
    "старое и новое",
)
PATCH_KEYWORDS = (
    "patch",
    "implement",
    "implementation",
    "fix",
    "add layer",
    "add routing",
    "integrate",
    "modify",
    "change system",
    "code change",
    "внедри",
    "реализац",
    "патч",
    "исправ",
    "добавь",
    "почини",
    "измени систему",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def extract_paths_from_text(text: str) -> list[Path]:
    paths: list[Path] = []
    for raw in PATH_RE.findall(text):
        candidate = Path(raw)
        if candidate.exists():
            paths.append(candidate.resolve())
        else:
            paths.append(candidate)
    return dedupe_paths(paths)


def dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def guess_topic_from_path(path: Path) -> str | None:
    parts = path.resolve().parts if path.exists() else path.parts
    try:
        agents_index = parts.index("agents")
    except ValueError:
        return None
    if agents_index + 1 >= len(parts):
        return None
    return parts[agents_index + 1]


def topic_root(topic: str) -> Path:
    return ROOT / topic


def infer_topic(explicit_topic: str | None, target_paths: list[Path]) -> str:
    if explicit_topic:
        return explicit_topic
    for path in target_paths:
        guessed = guess_topic_from_path(path)
        if guessed:
            return guessed
    return "core"


def git_branch() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    branch = completed.stdout.strip()
    return branch or None


def find_latest_run_root(topic: str) -> Path | None:
    runs_dir = topic_root(topic) / "runs"
    if not runs_dir.exists():
        return None
    candidates = [path for path in runs_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]


def path_run_id(path: Path) -> str | None:
    match = RUN_ID_RE.search(str(path))
    if not match:
        return None
    container, candidate = match.groups()
    if container == "runs":
        return candidate
    if date_prefix(candidate):
        return candidate
    return None


def date_prefix(value: str | None) -> str | None:
    if not value:
        return None
    match = DATE_PREFIX_RE.match(value)
    if not match:
        return None
    return match.group(1)


def nearest_run_root(path: Path) -> Path | None:
    for ancestor in [path] + list(path.parents):
        if ancestor.parent.name in {"runs", "artifacts"} and date_prefix(ancestor.name):
            return ancestor
    return None


def is_run_root(path: Path) -> bool:
    return nearest_run_root(path) == path


def keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    normalized = normalize_text(text)
    return sorted({keyword for keyword in keywords if keyword in normalized})


def classify_artifact_kind(path: Path) -> str:
    name = path.name.lower()
    full = str(path)
    if "/cases/" in full or name == "prompt.txt":
        return "raw_input"
    if name == "response.json":
        return "raw_output"
    if name == "assistant.txt":
        return "assistant_output"
    if name in {"stdout.txt", "command.txt"}:
        return "stdout_output"
    if name.endswith("-review.md"):
        return "review_artifact"
    if name == "verdict.md" or "verdict" in name:
        return "verdict_artifact"
    if name == "matrix-run-manifest.json":
        return "result_matrix"
    if "readiness" in name:
        return "readiness_note"
    if "pattern-extraction" in name or "repeated" in name:
        return "repeated_signal"
    if name in {"log.md"} or "checkpoint" in name or name == "method.md":
        return "checkpoint_artifact"
    if name in {"agents.md", "project-steering.md", "todo.md"} or "policy" in name or "rules" in name or "schema" in name:
        return "policy_artifact"
    if "/memory/" in full:
        return "reference_memory_artifact"
    if path.suffix in {".py", ".sh"} or "/bin/" in full or "/scripts/" in full:
        return "code_runner_script"
    return "summary_artifact"


def raw_or_derived(kind: str) -> str:
    if kind in {"raw_input", "raw_output", "assistant_output", "stdout_output", "code_runner_script", "policy_artifact"}:
        return "raw"
    return "derived"


def allowed_modes(kind: str) -> list[str]:
    if kind in {"checkpoint_artifact", "repeated_signal"}:
        return ["historical_review", "current_run_analysis", "compare_runs", "implementation_patch", "conservative_hybrid"]
    if kind in {"review_artifact", "verdict_artifact", "result_matrix", "readiness_note", "summary_artifact"}:
        return ["historical_review", "current_run_analysis", "clean_execution", "compare_runs", "implementation_patch", "conservative_hybrid"]
    return ["historical_review", "current_run_analysis", "clean_execution", "compare_runs", "implementation_patch", "conservative_hybrid"]


def contamination_risk(kind: str, exact_target_match: bool, compare_target_match: bool) -> str:
    if kind in {"raw_input", "raw_output", "assistant_output", "stdout_output", "code_runner_script", "policy_artifact", "reference_memory_artifact"}:
        return "low"
    if exact_target_match or compare_target_match:
        return "medium"
    if kind in {"review_artifact", "verdict_artifact", "checkpoint_artifact", "repeated_signal", "summary_artifact", "readiness_note"}:
        return "high"
    return "medium"


def latest_role(path: Path, latest_run_root: Path | None) -> str:
    if "latest" in path.parts or path.name == "latest":
        return "latest_pointer"
    if latest_run_root and (path == latest_run_root or latest_run_root in path.parents):
        return "latest_run_root"
    return "none"


def currentness(
    path: Path,
    primary_target: Path | None,
    compare_targets: list[Path],
    latest_run_root: Path | None,
) -> tuple[str, bool, bool]:
    compare_match = any(path == target or target in path.parents for target in compare_targets)
    exact_match = False
    if primary_target:
        exact_match = path == primary_target or primary_target in path.parents
    if compare_match:
        return "compare_target", exact_match, compare_match
    if exact_match:
        return "exact_target", exact_match, compare_match
    if latest_run_root and (path == latest_run_root or latest_run_root in path.parents):
        return "latest", exact_match, compare_match
    run_id = path_run_id(path)
    if run_id:
        return "historical", exact_match, compare_match
    return "timeless_canonical", exact_match, compare_match


def authority_level(path: Path, kind: str, currentness_value: str, latest_role_value: str) -> str:
    if kind in {"policy_artifact", "code_runner_script"}:
        return "canonical_live"
    if kind == "reference_memory_artifact":
        return "canonical_reference"
    if currentness_value == "exact_target" and kind in {"raw_input", "raw_output", "assistant_output", "stdout_output"}:
        return "current_run_raw"
    if currentness_value in {"exact_target", "compare_target"}:
        return "target_derived"
    if latest_role_value != "none":
        return "latest_derived"
    return "historical_derived"


def relative_priority(authority: str, currentness_value: str, contamination: str, kind: str) -> int:
    score = {
        "canonical_live": 80,
        "canonical_reference": 72,
        "current_run_raw": 68,
        "target_derived": 58,
        "latest_derived": 45,
        "historical_derived": 28,
    }.get(authority, 20)
    score += {
        "exact_target": 18,
        "compare_target": 16,
        "latest": 8,
        "historical": -4,
        "timeless_canonical": 6,
    }.get(currentness_value, 0)
    score += {
        "low": 6,
        "medium": 0,
        "high": -18,
    }.get(contamination, 0)
    if kind in {"review_artifact", "verdict_artifact"} and currentness_value not in {"exact_target", "compare_target"}:
        score -= 6
    return score


def source_lineage(path: Path, kind: str) -> list[str]:
    lineage: list[str] = []
    full = str(path)
    run_root = nearest_run_root(path)
    if run_root:
        lineage.append(f"run-root:{run_root.name}")
    if "/raw/" in full:
        lineage.append("raw-evidence")
    if kind in {"review_artifact", "verdict_artifact", "readiness_note"}:
        lineage.append("review-layer")
    if kind == "result_matrix":
        lineage.append("matrix-layer")
    if kind == "repeated_signal":
        lineage.append("pattern-layer")
    if kind == "checkpoint_artifact":
        lineage.append("checkpoint-layer")
    if kind == "policy_artifact":
        lineage.append("policy-layer")
    if kind == "reference_memory_artifact":
        lineage.append("memory-layer")
    if kind == "code_runner_script":
        lineage.append("runtime-layer")
    if not lineage:
        lineage.append("derived-summary-layer")
    return lineage


def shared_context_paths(topic: str, caller_surface: str) -> list[Path]:
    root = topic_root(topic)
    paths = [
        root / "AGENTS.md",
        root / "PROJECT-STEERING.md",
        root / "TODO.md",
        root / "LOG.md",
        root / "memory" / "index.md",
        root / "memory" / "facts.md",
        root / "memory" / "lessons.md",
    ]
    if caller_surface in {"run_local_agent_eval", "review_current_run"}:
        paths.extend(
            [
                root / "artifacts" / "skills" / "openclaw-skill-eval-harness-v1" / "scripts" / "run_local_agent_eval.py",
                root / "artifacts" / "skills" / "openclaw-skill-eval-harness-v1" / "scripts" / "run_skill_trial_matrix.py",
                root / "artifacts" / "skills" / "openclaw-skill-creator-v1" / "scripts" / "evaluate_readiness.py",
            ]
        )
    return [path for path in paths if path.exists()]


def historical_seed_paths(topic: str) -> list[Path]:
    root = topic_root(topic)
    corpus = root / "runtime" / "experiment-intelligence" / "skill_creator_experiment_corpus_v1.json"
    if corpus.exists():
        return [corpus]
    latest = find_latest_run_root(topic)
    if latest:
        return [latest]
    return []


def collect_text_files(root: Path, limit: int = 120) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(files) >= limit:
            break
        if not path.is_file():
            continue
        if path.name in {".DS_Store"} or "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def collect_run_root_files(run_root: Path) -> list[Path]:
    files: list[Path] = []
    important_patterns = [
        "cases/*.md",
        "summaries/*.json",
        "summaries/*.md",
        "results/*-review.md",
        "raw/*/*/assistant.txt",
        "raw/*/*/response.json",
        "raw/*/*/run-summary.json",
        "raw/*/*/stdout.txt",
        "raw/*/*/prompt.txt",
        "raw/*/*/command.txt",
        "generated/**/*.json",
        "generated/**/*.md",
    ]
    for pattern in important_patterns:
        for path in sorted(run_root.glob(pattern)):
            if path.is_file():
                files.append(path)
    bundle_root = run_root / "bundle-under-test"
    if bundle_root.exists():
        files.extend(collect_text_files(bundle_root, limit=80))
    return dedupe_paths(files)


def expand_candidate(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    if is_run_root(path):
        return collect_run_root_files(path)
    return collect_text_files(path)


def choose_mode(
    task_request: str,
    target_paths: list[Path],
    compare_targets: list[Path],
    caller_surface: str,
    topic: str,
    mode_override: str | None,
) -> tuple[str, dict[str, int], list[str], str, str]:
    if mode_override:
        return mode_override, {mode_override: 100}, ["manual_override"], "high", "manual override"

    normalized = normalize_text(task_request)
    scores = {
        "historical_review": 0,
        "current_run_analysis": 0,
        "clean_execution": 0,
        "compare_runs": 0,
        "implementation_patch": 0,
    }
    guardrails: list[str] = []

    historical_hits = keyword_hits(normalized, HISTORICAL_KEYWORDS)
    current_hits = keyword_hits(normalized, CURRENT_KEYWORDS)
    clean_hits = keyword_hits(normalized, CLEAN_KEYWORDS)
    compare_hits = keyword_hits(normalized, COMPARE_KEYWORDS)
    patch_hits = keyword_hits(normalized, PATCH_KEYWORDS)

    scores["historical_review"] += len(historical_hits) * 5
    scores["current_run_analysis"] += len(current_hits) * 5
    scores["clean_execution"] += len(clean_hits) * 6
    scores["compare_runs"] += len(compare_hits) * 6
    scores["implementation_patch"] += len(patch_hits) * 5

    run_root_targets = [path for path in target_paths if nearest_run_root(path)]
    bundle_targets = [path for path in target_paths if "/bundle-under-test/" in str(path)]
    code_targets = [path for path in target_paths if path.suffix in {".py", ".sh"} or "/runtime/" in str(path)]

    if run_root_targets:
        scores["current_run_analysis"] += 7
        scores["clean_execution"] += 5
    if compare_targets:
        scores["compare_runs"] += 14
    if len(compare_targets) >= 2:
        guardrails.append("explicit_compare_targets")
    if code_targets:
        scores["implementation_patch"] += 10
    if caller_surface == "run_local_agent_eval":
        scores["clean_execution"] += 6
        scores["current_run_analysis"] += 4
    if bundle_targets:
        scores["clean_execution"] += 8
        scores["current_run_analysis"] += 3
    if "inspect only files" in normalized and "bundle root" in normalized:
        scores["clean_execution"] += 8
        guardrails.append("bundle_root_clean_guard")
    if "do not let copied summaries" in normalized or "summary-only evidence" in normalized:
        scores["clean_execution"] += 4
    if caller_surface == "review_current_run":
        scores["current_run_analysis"] += 12
        scores["compare_runs"] += 4

    if "latest" in normalized or "последн" in normalized:
        scores["current_run_analysis"] += 3
    if "rerun" in normalized or "перезапусти" in normalized:
        scores["clean_execution"] += 5

    if compare_targets and len(compare_targets) >= 2:
        selected = "compare_runs"
        confidence = "high"
        reason = "explicit compare targets provided"
        return selected, scores, guardrails, confidence, reason
    if clean_hits and not compare_hits and not patch_hits:
        guardrails.append("clean_keyword_guard")
    if historical_hits and not patch_hits and not compare_hits and not clean_hits:
        guardrails.append("historical_keyword_guard")
    if current_hits and run_root_targets and not compare_hits:
        guardrails.append("current_run_guard")
    if patch_hits and code_targets:
        guardrails.append("implementation_guard")

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    selected, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0
    margin = top_score - second_score
    if top_score < 9 or margin < 3:
        return "conservative_hybrid", scores, guardrails, "low", "low score or narrow margin"
    if top_score < 14 or margin < 5:
        return selected, scores, guardrails, "medium", "useful signal but not decisive"
    return selected, scores, guardrails, "high", "decisive lexical and target-path signal"


def choose_primary_target(
    selected_mode: str,
    task_request: str,
    target_paths: list[Path],
    compare_targets: list[Path],
    topic: str,
) -> tuple[Path | None, list[Path], list[str]]:
    warnings: list[str] = []
    latest_run_root = find_latest_run_root(topic)
    normalized = normalize_text(task_request)
    explicit_targets = dedupe_paths(target_paths)
    compare_list = dedupe_paths(compare_targets)

    def rank_target(path: Path) -> int:
        score = 0
        if "/bundle-under-test/" in str(path):
            score += 50
        if path.is_dir():
            score += 35
        if is_run_root(path):
            score += 25
        if nearest_run_root(path):
            score += 10
        if "/cases/" in str(path):
            score -= 15
        if path.suffix in {".py", ".sh"}:
            score += 5
        return score

    if selected_mode == "compare_runs":
        if not compare_list and len(explicit_targets) >= 2:
            compare_list = explicit_targets[:2]
        if len(compare_list) == 1 and latest_run_root and latest_run_root != compare_list[0]:
            compare_list.append(latest_run_root)
            warnings.append("inferred latest run root as the second compare target")
        primary = compare_list[0] if compare_list else None
        if len(compare_list) < 2:
            warnings.append("compare mode has fewer than two compare targets")
        return primary, compare_list, warnings

    promoted: list[Path] = []
    for path in explicit_targets:
        run_root = nearest_run_root(path)
        if "/bundle-under-test/" in str(path):
            promoted.append(path)
        elif selected_mode in {"current_run_analysis", "clean_execution"} and run_root:
            promoted.append(run_root)
        else:
            promoted.append(path)
    promoted = dedupe_paths(promoted)
    promoted.sort(key=rank_target, reverse=True)

    if promoted:
        return promoted[0], compare_list, warnings
    if ("latest" in normalized or "последн" in normalized) and latest_run_root:
        warnings.append("primary target inferred from latest run root")
        return latest_run_root, compare_list, warnings
    return None, compare_list, warnings


def discover_candidates(
    topic: str,
    selected_mode: str,
    primary_target: Path | None,
    target_paths: list[Path],
    compare_targets: list[Path],
    caller_surface: str,
) -> list[Path]:
    candidates: list[Path] = []
    if primary_target:
        candidates.append(primary_target)
    candidates.extend(target_paths)
    candidates.extend(compare_targets)
    candidates.extend(shared_context_paths(topic, caller_surface))
    if selected_mode in {"historical_review", "conservative_hybrid"}:
        candidates.extend(historical_seed_paths(topic))
    if selected_mode == "compare_runs" and not compare_targets:
        latest = find_latest_run_root(topic)
        if latest:
            candidates.append(latest)
    expanded: list[Path] = []
    for candidate in dedupe_paths(candidates):
        expanded.extend(expand_candidate(candidate))
    expanded = dedupe_paths(expanded)
    expanded.sort(key=lambda path: str(path))
    return expanded[:160]


def build_catalog(
    files: list[Path],
    primary_target: Path | None,
    compare_targets: list[Path],
    latest_run_root: Path | None,
) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for path in files:
        stat = path.stat()
        currentness_value, exact_match, compare_match = currentness(path, primary_target, compare_targets, latest_run_root)
        kind = classify_artifact_kind(path)
        latest_role_value = latest_role(path, latest_run_root)
        authority = authority_level(path, kind, currentness_value, latest_role_value)
        contamination = contamination_risk(kind, exact_match, compare_match)
        metadata = {
            "path": str(path),
            "topic": guess_topic_from_path(path) or "core",
            "run_id": path_run_id(path),
            "artifact_kind": kind,
            "raw_or_derived": raw_or_derived(kind),
            "authority_level": authority,
            "source_lineage": source_lineage(path, kind),
            "currentness": currentness_value,
            "exact_target_match": exact_match,
            "compare_target_match": compare_match,
            "allowed_modes": allowed_modes(kind),
            "contamination_risk": contamination,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "latest_role": latest_role_value,
            "relative_priority": relative_priority(authority, currentness_value, contamination, kind),
        }
        catalog.append(metadata)
    catalog.sort(key=lambda item: (item["relative_priority"], item["path"]), reverse=True)
    return catalog


def analytical_disposition(mode: str, artifact: dict[str, Any]) -> tuple[str, str]:
    kind = artifact["artifact_kind"]
    currentness_value = artifact["currentness"]
    authority = artifact["authority_level"]
    contamination = artifact["contamination_risk"]
    compare_match = artifact.get("compare_target_match", False)
    exact_match = artifact["exact_target_match"]

    if mode == "compare_runs" and not (compare_match or exact_match or authority.startswith("canonical")):
        return "excluded", "outside the explicit compare scope"
    if mode == "historical_review":
        return "included", "historical review keeps broad visibility"
    if exact_match or compare_match:
        return "included", "exact or compare-target match"
    if authority.startswith("canonical"):
        return "included", "canonical context remains visible"
    if mode in {"clean_execution", "implementation_patch", "conservative_hybrid"} and contamination == "high":
        return "supporting", "visible for analysis only because contamination risk is high"
    if kind in {"checkpoint_artifact", "repeated_signal", "review_artifact", "verdict_artifact", "summary_artifact"}:
        return "supporting", "historical derived context is supporting-only"
    return "included", "bounded supporting context"


def execution_disposition(mode: str, artifact: dict[str, Any], rules: dict[str, Any]) -> tuple[str, str]:
    policy = rules["mode_policies"][mode]
    kind = artifact["artifact_kind"]
    exact_match = artifact["exact_target_match"]
    compare_match = artifact.get("compare_target_match", False)
    contamination = artifact["contamination_risk"]
    authority = artifact["authority_level"]

    if mode == "compare_runs" and not (compare_match or exact_match or authority.startswith("canonical")):
        return "excluded", "compare execution only allows explicit compare targets plus shared canon"

    if kind in policy["execution_exclude_unless_exact"] and not exact_match and not compare_match:
        return "excluded", "excluded by mode policy unless it exactly matches the selected target"

    if contamination == "high" and not exact_match and not compare_match and mode in {"clean_execution", "implementation_patch", "conservative_hybrid"}:
        return "excluded", "high contamination risk outside the exact target"

    if kind in policy["execution_allow_kinds"]:
        if contamination == "medium" and not exact_match and not compare_match and mode in {"current_run_analysis", "implementation_patch"}:
            return "supporting", "allowed but demoted to supporting because it is derived and not exact-target"
        return "allowed", "allowed by mode policy"

    if authority.startswith("canonical"):
        return "supporting", "canonical context is supporting-only in the execution contour"

    return "excluded", "not selected for the execution contour"


def shape_contour_entries(catalog: list[dict[str, Any]], mode: str, rules: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    analytical = {"included": [], "supporting": [], "excluded": []}
    execution = {"allowed": [], "supporting": [], "excluded": []}

    for artifact in catalog:
        analytical_state, analytical_reason = analytical_disposition(mode, artifact)
        analytical[analytical_state].append(
            {
                **artifact,
                "reason": analytical_reason,
            }
        )
        execution_state, execution_reason = execution_disposition(mode, artifact, rules)
        execution[execution_state].append(
            {
                **artifact,
                "reason": execution_reason,
            }
        )

    return analytical, execution


def summarize_warnings(
    selected_mode: str,
    confidence: str,
    primary_target: Path | None,
    compare_targets: list[Path],
    projection_requested: bool,
) -> list[str]:
    warnings: list[str] = []
    if confidence == "low":
        warnings.append("low routing confidence")
    if selected_mode == "compare_runs" and len(compare_targets) < 2:
        warnings.append("compare mode has incomplete compare targets")
    if selected_mode in {"current_run_analysis", "clean_execution"} and primary_target is None:
        warnings.append("no explicit primary target was found")
    if projection_requested and primary_target is None:
        warnings.append("projection requested without an explicit target")
    return warnings


def copy_material(source: Path, projection_root: Path) -> Path:
    relative = Path(*source.resolve().parts[1:])
    destination = projection_root / "mirror" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
    else:
        shutil.copy2(source, destination)
    return destination


def projection_destination(source: Path, projection_root: Path) -> Path:
    relative = Path(*source.resolve().parts[1:])
    return projection_root / "mirror" / relative


def projection_target_label(target: Path, used_labels: set[str]) -> str:
    resolved = target.resolve()
    if resolved == ROOT:
        base = "repo-root"
    elif ROOT in resolved.parents:
        relative = resolved.relative_to(ROOT)
        base = "-".join(relative.parts) or "repo-root"
    else:
        tail = resolved.parts[-3:] if len(resolved.parts) >= 3 else resolved.parts
        base = "-".join(tail) or target.name or "target"
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "target"
    candidate = base
    suffix = 2
    while candidate in used_labels:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used_labels.add(candidate)
    return candidate


def copy_relative_material(source: Path, source_root: Path, target_root: Path) -> Path:
    relative = source.resolve().relative_to(source_root.resolve())
    destination = target_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def ensure_projection_placeholder(target: Path, projection_root: Path) -> Path:
    destination = projection_destination(target, projection_root)
    if target.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def contour_material_paths(entries: list[dict[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for item in entries:
        try:
            path = Path(item["path"])
        except KeyError:
            continue
        if path.exists():
            paths.append(path.resolve())
    return dedupe_paths(paths)


def select_projection_materials(
    *,
    target_paths: list[Path],
    explicit_targets: list[Path],
    analytical_contour: dict[str, Any],
    execution_contour: dict[str, Any],
) -> list[Path]:
    directory_targets = [path.resolve() for path in target_paths if path.exists() and path.is_dir()]
    selected: list[Path] = []

    for path in explicit_targets:
        if path.exists() and path.is_file():
            selected.append(path.resolve())

    execution_materials = contour_material_paths(
        [
            item
            for item in execution_contour["allowed"] + execution_contour["supporting"]
            if item.get("exact_target_match")
            or item.get("compare_target_match")
            or item.get("currentness") in {"latest", "exact_target", "compare_target"}
        ]
    )
    analytical_exact_materials = contour_material_paths(
        [
            item
            for item in analytical_contour["included"]
            if item.get("exact_target_match") or item.get("compare_target_match")
        ]
    )

    for material in execution_materials + analytical_exact_materials:
        if not directory_targets:
            selected.append(material)
            continue
        if any(material == target or target in material.parents for target in directory_targets):
            selected.append(material)
    return dedupe_paths(selected)


def build_projection(target_paths: list[Path], projection_root: Path, material_paths: list[Path] | None = None) -> dict[str, Any]:
    projection_root.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    projected_items: list[dict[str, str]] = []
    projected_materials: list[dict[str, str]] = []
    wholesale_targets: list[Path] = []
    curated_targets: dict[Path, Path] = {}
    used_labels: set[str] = set()
    normalized_targets = dedupe_paths(target_paths)

    for target in normalized_targets:
        if target.exists() and target.is_dir() and not nearest_run_root(target) and "/bundle-under-test/" not in str(target):
            label = projection_target_label(target, used_labels)
            curated_root = projection_root / "targets" / label
            curated_root.mkdir(parents=True, exist_ok=True)
            curated_targets[target.resolve()] = curated_root

    for target in normalized_targets:
        if not target.exists():
            continue
        resolved_target = target.resolve()
        if target.is_dir() and resolved_target in curated_targets:
            projected = curated_targets[resolved_target]
            projection_style = "curated_directory_mount"
        elif target.is_file():
            parent_curated_root = None
            parent_curated_source = None
            for curated_source, curated_root in curated_targets.items():
                if curated_source in resolved_target.parents:
                    parent_curated_source = curated_source
                    parent_curated_root = curated_root
                    break
            if parent_curated_root and parent_curated_source:
                projected = copy_relative_material(target, parent_curated_source, parent_curated_root)
                projection_style = "curated_file_mount"
            else:
                projected = copy_material(target, projection_root)
                projection_style = "file_copy"
        elif nearest_run_root(target) or "/bundle-under-test/" in str(target):
            projected = copy_material(target, projection_root)
            wholesale_targets.append(resolved_target)
            projection_style = "wholesale_directory_copy"
        else:
            projected = ensure_projection_placeholder(target, projection_root)
            projection_style = "directory_placeholder"
        mapping[str(resolved_target)] = str(projected)
        projected_items.append(
            {
                "source_path": str(resolved_target),
                "projected_path": str(projected),
                "source_kind": "directory" if target.is_dir() else "file",
                "projection_style": projection_style,
            }
        )

    for material in dedupe_paths(material_paths or []):
        if not material.exists() or not material.is_file():
            continue
        resolved = material.resolve()
        if any(resolved == target or target in resolved.parents for target in wholesale_targets):
            continue
        copied = False
        for curated_source, curated_root in curated_targets.items():
            if resolved == curated_source or curated_source in resolved.parents:
                projected = copy_relative_material(material, curated_source, curated_root)
                projected_materials.append(
                    {
                        "source_path": str(resolved),
                        "projected_path": str(projected),
                        "source_kind": "file",
                    }
                )
                copied = True
        if copied:
            continue
        if str(resolved) not in mapping:
            continue
        projected = copy_material(material, projection_root)
        projected_materials.append(
            {
                "source_path": str(resolved),
                "projected_path": str(projected),
                "source_kind": "file",
            }
        )
    manifest = {
        "generated_at": now_utc(),
        "projection_root": str(projection_root),
        "items": projected_items,
        "material_files": projected_materials,
        "path_mapping": mapping,
    }
    dump_json(projection_root / "projection-manifest.json", manifest)
    return manifest


def rewrite_text_with_projection(text: str, mapping: dict[str, str]) -> str:
    rewritten = text
    placeholders: dict[str, str] = {}
    for index, (source, destination) in enumerate(sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True)):
        placeholder = f"__CONTEXT_ROUTER_PROJECTION_{index}__"
        rewritten = rewritten.replace(source, placeholder)
        placeholders[placeholder] = destination
    for placeholder, destination in placeholders.items():
        rewritten = rewritten.replace(placeholder, destination)
    return rewritten


def build_context_packet(
    *,
    task_request: str,
    output_dir: Path,
    topic: str | None = None,
    target_paths: list[str | Path] | None = None,
    compare_targets: list[str | Path] | None = None,
    caller_surface: str = "manual_cli",
    mode_override: str | None = None,
    create_projection: bool = False,
) -> dict[str, Any]:
    explicit_targets = [Path(path) for path in (target_paths or [])]
    compare_list = [Path(path) for path in (compare_targets or [])]
    text_targets = extract_paths_from_text(task_request)
    merged_targets = dedupe_paths(explicit_targets + text_targets)
    resolved_topic = infer_topic(topic, merged_targets + compare_list)
    rules = load_json(RULES_PATH)

    selected_mode, mode_scores, guardrails, confidence, confidence_reason = choose_mode(
        task_request,
        merged_targets,
        compare_list,
        caller_surface,
        resolved_topic,
        mode_override,
    )
    primary_target, normalized_compare_targets, target_warnings = choose_primary_target(
        selected_mode,
        task_request,
        merged_targets,
        compare_list,
        resolved_topic,
    )
    latest_run_root = find_latest_run_root(resolved_topic)
    candidate_files = discover_candidates(
        resolved_topic,
        selected_mode,
        primary_target,
        merged_targets,
        normalized_compare_targets,
        caller_surface,
    )
    catalog = build_catalog(candidate_files, primary_target, normalized_compare_targets, latest_run_root)
    analytical_contour, execution_contour = shape_contour_entries(catalog, selected_mode, rules)

    projection_manifest = None
    projection_mapping: dict[str, str] = {}
    projection_targets: list[Path] = []
    projection_materials: list[Path] = []
    if create_projection:
        for path in merged_targets:
            if not path.exists():
                continue
            if path.is_file():
                projection_targets.append(path)
                continue
            resolved_path = path.resolve()
            if path.is_dir() and (
                nearest_run_root(path)
                or "/bundle-under-test/" in str(path)
                or (caller_surface == "run_local_agent_eval" and (resolved_path == ROOT or ROOT in resolved_path.parents))
            ):
                projection_targets.append(path)
        projection_targets = dedupe_paths(projection_targets)
        if projection_targets:
            projection_materials = select_projection_materials(
                target_paths=projection_targets,
                explicit_targets=explicit_targets,
                analytical_contour=analytical_contour,
                execution_contour=execution_contour,
            )
            projection_manifest = build_projection(
                projection_targets,
                output_dir / "projection",
                material_paths=projection_materials,
            )
            projection_mapping = projection_manifest["path_mapping"]

    warnings = summarize_warnings(selected_mode, confidence, primary_target, normalized_compare_targets, create_projection)
    warnings.extend(target_warnings)
    trace = {
        "generated_at": now_utc(),
        "topic": resolved_topic,
        "git_branch": git_branch(),
        "task_request": task_request,
        "caller_surface": caller_surface,
        "selected_mode": selected_mode,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "mode_scores": mode_scores,
        "deterministic_guardrails": guardrails,
        "primary_target": str(primary_target) if primary_target else None,
        "compare_targets": [str(path) for path in normalized_compare_targets],
        "warning_signals": warnings,
        "fallback_used": selected_mode == rules["fallback_mode"],
        "projection_requested": create_projection,
        "projection_applied": bool(projection_mapping),
        "projection_targets": [str(path) for path in projection_targets],
        "projection_material_count": len(projection_materials),
        "analytical_counts": {key: len(value) for key, value in analytical_contour.items()},
        "execution_counts": {key: len(value) for key, value in execution_contour.items()},
    }
    working_set = {
        "generated_at": now_utc(),
        "selected_mode": selected_mode,
        "primary_target": str(primary_target) if primary_target else None,
        "compare_targets": [str(path) for path in normalized_compare_targets],
        "analytical_contour": analytical_contour,
        "execution_contour": execution_contour,
        "warning_signals": warnings,
        "projection_root": str(output_dir / "projection") if projection_mapping else None,
        "projection_mapping": projection_mapping,
        "projection_material_count": len(projection_materials),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    dump_json(output_dir / "artifact-catalog.json", catalog)
    dump_json(output_dir / "decision-trace.json", trace)
    dump_json(output_dir / "working-set.json", working_set)
    if projection_manifest:
        dump_json(output_dir / "projection-summary.json", projection_manifest)

    return {
        "topic": resolved_topic,
        "selected_mode": selected_mode,
        "confidence": confidence,
        "primary_target": primary_target,
        "compare_targets": normalized_compare_targets,
        "warning_signals": warnings,
        "artifact_catalog_path": output_dir / "artifact-catalog.json",
        "decision_trace_path": output_dir / "decision-trace.json",
        "working_set_path": output_dir / "working-set.json",
        "projection_root": output_dir / "projection" if projection_mapping else None,
        "projection_summary_path": output_dir / "projection-summary.json" if projection_manifest else None,
        "projection_mapping": projection_mapping,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a context router / policy / projector packet.")
    parser.add_argument("--task-request", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--topic")
    parser.add_argument("--target-path", action="append", default=[])
    parser.add_argument("--compare-target", action="append", default=[])
    parser.add_argument("--caller-surface", default="manual_cli")
    parser.add_argument("--mode-override")
    parser.add_argument("--create-projection", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_context_packet(
        task_request=args.task_request,
        output_dir=Path(args.output_dir),
        topic=args.topic,
        target_paths=args.target_path,
        compare_targets=args.compare_target,
        caller_surface=args.caller_surface,
        mode_override=args.mode_override,
        create_projection=args.create_projection,
    )
    print(
        json.dumps(
            {
                "selected_mode": packet["selected_mode"],
                "confidence": packet["confidence"],
                "decision_trace": str(packet["decision_trace_path"]),
                "working_set": str(packet["working_set_path"]),
                "projection": str(packet["projection_summary_path"]) if packet["projection_summary_path"] else None,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
