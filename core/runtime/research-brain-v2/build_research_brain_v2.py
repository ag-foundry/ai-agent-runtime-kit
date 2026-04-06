#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CORE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_INTAKE = SCRIPT_DIR / "skill_creator_history_intake_v2.json"
DEFAULT_RULES = SCRIPT_DIR / "research_brain_rules_v2.json"
DEFAULT_OUTPUT_SCHEMA = SCRIPT_DIR / "research_brain_output_schema_v2.json"
DEFAULT_REGISTRY_ROOT = CORE_ROOT / "artifacts" / "experiment-intelligence" / "skill-creator-history-v1"
DEFAULT_OUT_DIR = CORE_ROOT / "artifacts" / "research-brain" / "skill-creator-history-v2"


def default_durable_context_inputs() -> list[str]:
    return [
        str(CORE_ROOT / "PROJECT-STEERING.md"),
        str(CORE_ROOT / "LOG.md"),
        str(CORE_ROOT / "TODO.md"),
        str(CORE_ROOT / "memory" / "index.md"),
        str(CORE_ROOT / "memory" / "facts.md"),
        str(CORE_ROOT / "memory" / "lessons.md"),
    ]


def default_writeback_targets() -> dict[str, str]:
    return {
        "log": str(CORE_ROOT / "LOG.md"),
        "todo": str(CORE_ROOT / "TODO.md"),
        "memory_index": str(CORE_ROOT / "memory" / "index.md"),
        "steering": str(CORE_ROOT / "PROJECT-STEERING.md"),
        "facts": str(CORE_ROOT / "memory" / "facts.md"),
        "lessons": str(CORE_ROOT / "memory" / "lessons.md"),
    }


def default_writeback_candidates() -> dict[str, dict[str, str]]:
    return {
        "steering": {
            "class": "steering-level rule or direction",
            "candidate": "Route future skill/usefulness research through research-brain-v2 before any new rerun so search depth, execution class, and exhausted-line enforcement are explicit.",
        },
        "facts": {
            "class": "durable fact",
            "candidate": "research-brain-v2 exists and reads experiment-intelligence v1 plus durable steering/memory as first-class inputs.",
        },
        "lessons": {
            "class": "durable lesson / anti-pattern",
            "candidate": "Use the registry-backed blocker and exhaustion picture as a pre-run gate, not only as a retrospective summary.",
        },
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def dump_text(path: Path, payload: str) -> None:
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def require_fields(payload: dict[str, Any], name: str, fields: list[str]) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"{name} is missing required fields: {', '.join(missing)}")


def clip_text(text: str | None, limit: int = 220) -> str:
    if not text:
        return ""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def choose_search_depth(
    intake: dict[str, Any],
    exhausted_lines: set[str],
    rules: dict[str, Any],
) -> tuple[str, str, str]:
    rule_map = {rule["rule_id"]: rule for rule in rules["search_depth_rules"]}
    target_line = intake.get("target_line_id")

    if intake["task_kind"] in {"meta-layer-build", "retrospective-synthesis"} and not intake["needs_external_sources"]:
        rule = rule_map["local-memory-sufficient-meta-layer"]
        return rule["search_depth"], rule["reason"], rule["rule_id"]
    if target_line in exhausted_lines and not intake["proof_class_change"]:
        rule = rule_map["blocked-same-class-rerun"]
        return rule["search_depth"], rule["reason"], rule["rule_id"]
    if intake["needs_cross_topic_search"] or intake["task_kind"] == "cross-topic-intake":
        rule = rule_map["cross-topic-local-smoke"]
        return rule["search_depth"], rule["reason"], rule["rule_id"]
    if intake["needs_external_sources"]:
        rule = rule_map["ambiguous-new-area"]
        return rule["search_depth"], rule["reason"], rule["rule_id"]
    rule = rule_map["cross-topic-local-smoke"]
    return rule["search_depth"], rule["reason"], rule["rule_id"]


def choose_execution_class(
    intake: dict[str, Any],
    exhausted_lines: set[str],
    rules: dict[str, Any],
) -> tuple[str, str]:
    execution_class = rules["task_kind_to_execution_class"].get(
        intake["task_kind"],
        "registry-steered-retrospective",
    )
    target_line = intake.get("target_line_id")

    if intake["requires_new_experiment_run"] and target_line in exhausted_lines and not intake["proof_class_change"]:
        execution_class = "blocked-same-class-rerun"
    elif (
        intake["requires_new_experiment_run"]
        and intake["proof_class_change"]
        and target_line == intake.get("deferred_resume_line_id")
    ):
        execution_class = "narrow-next-class-validation"

    description = rules["execution_classes"][execution_class]["label"]
    return execution_class, description


def collect_relevant_blockers(
    repeated_blockers: list[dict[str, Any]],
    line_ids: set[str],
) -> list[dict[str, Any]]:
    relevant = [
        blocker
        for blocker in repeated_blockers
        if line_ids.intersection(set(blocker.get("affected_lines", [])))
    ]
    relevant.sort(key=lambda item: (-item.get("count", 0), item["blocker_id"]))
    return relevant


def select_negative_results(
    registry: dict[str, Any],
    priority_ids: list[str],
) -> list[dict[str, Any]]:
    by_id = {item["experiment_id"]: item for item in registry["experiments"]}
    selected: list[dict[str, Any]] = []
    for experiment_id in priority_ids:
        entry = by_id.get(experiment_id)
        if not entry:
            continue
        selected.append(
            {
                "experiment_id": entry["experiment_id"],
                "line_id": entry["line_id"],
                "target_skill": entry["target_skill"],
                "blocker_tags": entry["classifications"].get("blocker_tags", []),
                "why_it_matters": clip_text(entry.get("delta_notes") or entry.get("gating_notes")),
            }
        )
    return selected


def load_registry_inputs(registry_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    registry = load_json(registry_root / "experiment-registry-v1.json")
    patterns = load_json(registry_root / "pattern-extraction-v1.json")
    portfolio = load_json(registry_root / "next-step-portfolio-v1.json")
    return registry, patterns, portfolio


def build_core_steering_signals(core_root: Path) -> dict[str, Any]:
    steering_text = read_text(core_root / "PROJECT-STEERING.md")
    todo_text = read_text(core_root / "TODO.md")
    facts_text = read_text(core_root / "memory" / "facts.md")
    lessons_text = read_text(core_root / "memory" / "lessons.md")
    return {
        "skills_line_paused": "skills line is paused at this checkpoint" in steering_text.lower(),
        "use_v1_before_rerun": "Use experiment-intelligence `v1` before any new skill/usefulness rerun" in steering_text,
        "todo_prompt_family_frozen": "Keep prompt-contained net-new candidates frozen" in todo_text,
        "todo_bundle_family_paused": "Keep bundle-state portability follow-ups paused" in todo_text,
        "lesson_repeat_same_story": "stop rerunning the same proof class and synthesize first" in lessons_text.lower(),
        "facts_record_runtime_governance_next_class": (
            "current next-class candidate" in facts_text
            and "runtime-governance-remediation-guard" in facts_text
        ),
    }


def build_context_signals(
    intake: dict[str, Any],
    durable_context_inputs: list[str],
) -> dict[str, Any]:
    if intake.get("topic") == "core" and not intake.get("durable_context_inputs"):
        return build_core_steering_signals(CORE_ROOT)

    text_blobs: list[str] = []
    for raw_path in durable_context_inputs:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        try:
            text_blobs.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue

    combined = "\n".join(text_blobs).lower()
    all_paths = [Path(path).resolve() for path in intake.get("seed_artifacts", []) + durable_context_inputs]
    return {
        "cross_topic_search_requested": intake.get("needs_cross_topic_search", False),
        "topic_has_prior_smoke": "cross-project reuse smoke test" in combined,
        "topic_has_explicit_connector_next_step": "explicit connector candidate" in combined,
        "topic_has_safe_smoke_step": "smoke-test one existing integration safely" in combined,
        "topic_blocks_broad_framework": (
            "do not build a broad mcp management framework" in combined
            or "do not build a broad mcp framework" in combined
            or "do not build a broad mcp management framework or custom registry layer yet" in combined
        ),
        "core_steering_seed_present": (CORE_ROOT / "PROJECT-STEERING.md").resolve() in all_paths,
    }


def build_source_of_truth(
    intake_path: Path,
    rules_path: Path,
    registry_root: Path,
    durable_context_inputs: list[str],
) -> dict[str, Any]:
    return {
        "runtime_files": [
            str(SCRIPT_DIR / "build_research_brain_v2.py"),
            str(intake_path),
            str(rules_path),
            str(SCRIPT_DIR / "research_brain_intake_schema_v2.json"),
            str(SCRIPT_DIR / "research_brain_output_schema_v2.json"),
        ],
        "experiment_intelligence_inputs": [
            str(registry_root / "experiment-registry-v1.json"),
            str(registry_root / "pattern-extraction-v1.json"),
            str(registry_root / "next-step-portfolio-v1.json"),
        ],
        "durable_context_inputs": durable_context_inputs,
    }


def build_layer_boundary(
    rules: dict[str, Any],
) -> dict[str, Any]:
    return {
        "already_in_v1": rules["v1_capabilities"],
        "added_in_v2_minimal_form": rules["v2_minimal_components"],
        "deferred_to_v3": rules["v3_deferred"],
    }


def build_enforcement(
    intake: dict[str, Any],
    patterns: dict[str, Any],
    rules: dict[str, Any],
    v1_portfolio: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    registry_scope = intake.get("registry_scope", "full")
    exhausted_lines = {item["line_id"] for item in patterns.get("locally_exhausted_lines", [])}
    parity_lines = {item["line_id"] for item in patterns.get("parity_prone_families", [])}
    repeated_blockers = patterns.get("repeated_blockers", [])
    relevant_line_ids = set(intake.get("paused_line_ids", []))
    if intake.get("deferred_resume_line_id"):
        relevant_line_ids.add(intake["deferred_resume_line_id"])
    if intake.get("target_line_id"):
        relevant_line_ids.add(intake["target_line_id"])

    blocker_countermeasures = rules["blocker_countermeasures"]
    relevant_blockers = collect_relevant_blockers(repeated_blockers, relevant_line_ids)
    global_blockers = sorted(repeated_blockers, key=lambda item: (-item.get("count", 0), item["blocker_id"]))[:5]

    exhausted_guardrails = []
    for item in patterns.get("locally_exhausted_lines", []):
        if item["line_id"] in relevant_line_ids:
            exhausted_guardrails.append(
                {
                    "line_id": item["line_id"],
                    "reason": item["reason"],
                    "enforcement": "block same-proof-class reruns unless the proof surface changes materially",
                }
            )

    blocker_enforcement = []
    for blocker in relevant_blockers:
        blocker_enforcement.append(
            {
                "blocker_id": blocker["blocker_id"],
                "count": blocker["count"],
                "affected_lines": blocker.get("affected_lines", []),
                "countermeasure": blocker_countermeasures.get(
                    blocker["blocker_id"],
                    "Carry the blocker forward explicitly before choosing the next move.",
                ),
            }
        )

    negative_results = select_negative_results(registry, rules["priority_negative_result_ids"])
    if registry_scope == "relevant-only":
        scoped_parity_lines = sorted(line for line in parity_lines if line in relevant_line_ids)
        scoped_exhausted_lines = sorted(line for line in exhausted_lines if line in relevant_line_ids)
        negative_results = [item for item in negative_results if item["line_id"] in relevant_line_ids]
        global_blockers_payload: list[dict[str, Any]] = []
        carried_do_not_do: list[str] = []
    else:
        scoped_parity_lines = sorted(parity_lines)
        scoped_exhausted_lines = sorted(exhausted_lines)
        global_blockers_payload = [
            {
                "blocker_id": blocker["blocker_id"],
                "count": blocker["count"],
                "affected_lines": blocker.get("affected_lines", []),
            }
            for blocker in global_blockers
        ]
        carried_do_not_do = v1_portfolio["recommended_next_move"].get("do_not_do", [])

    return {
        "registry_scope": registry_scope,
        "paused_line_ids": intake.get("paused_line_ids", []),
        "parity_prone_line_ids": scoped_parity_lines,
        "locally_exhausted_line_ids": scoped_exhausted_lines,
        "exhausted_line_guardrails": exhausted_guardrails,
        "global_repeated_blockers": global_blockers_payload,
        "relevant_blocker_enforcement": blocker_enforcement,
        "negative_results_to_remember": negative_results,
        "do_not_do": carried_do_not_do,
    }


def build_portfolio(
    intake: dict[str, Any],
    execution_class: str,
    v1_portfolio: dict[str, Any],
) -> dict[str, Any]:
    deferred_move = dict(v1_portfolio["recommended_next_move"])
    deferred_move["status"] = "deferred-until-skills-resume"

    if execution_class == "meta-layer-build":
        recommended = {
            "move_id": "research-brain-cross-topic-local-smoke",
            "status": "recommended-now",
            "title": "Validate research-brain-v2 on one non-skills local intake",
            "why": "The layer now works on the current skill-creator corpus, but it should prove that intake, depth control, routing, and writeback generalize beyond the paused skills line before wider automation.",
            "do_now": [
                "Run one bounded cross-topic intake on an existing local topic such as `mcp` or runtime hygiene.",
                "Keep the validation local-only: durable memory, steering, and existing artifacts first.",
                "Confirm that the layer does not route the validation back into the paused skills line."
            ],
            "do_not_do": [
                "Do not reopen the paused skills line as the validation target.",
                "Do not add daemons, background workers, or a broad new framework before the second-topic smoke."
            ]
        }
        portfolio = [
            recommended,
            {
                "move_id": "manual-pre-post-hooks",
                "status": "ready-now",
                "title": "Use research-brain-v2 as an explicit pre-run and post-run hook",
                "why": "A manual command invocation is enough for v2; the value now comes from consistent intake, routing, enforcement, and writeback rather than background automation."
            },
            deferred_move,
            {
                "move_id": "keep-paused-lines-frozen",
                "status": "hold",
                "title": "Keep the paused skills lines frozen unless the proof class changes",
                "why": "Prompt-contained net-new and bundle-state portability follow-ups are already marked as locally exhausted for the current proof class."
            }
        ]
        return {
            "format": "core-research-brain-portfolio-v2",
            "recommended_next_move": recommended,
            "portfolio": portfolio,
        }

    if execution_class == "cross-topic-local-smoke":
        recommended = dict(
            intake.get("portfolio_seed")
            or {
                "move_id": f"{intake['topic']}-next-step",
                "status": "recommended-now",
                "title": "Choose one explicit next step from the local topic surface",
                "why": "This intake is a bounded cross-topic validation, so the next move should stay narrow, local, and framework-averse.",
                "do_now": [
                    "Pick one explicit next step grounded in the target topic TODO and artifacts.",
                    "Keep the follow-up as one safe smoke or one planning checkpoint, not a broad rollout."
                ],
                "do_not_do": [
                    "Do not build a broad framework from this smoke alone."
                ],
            }
        )
        portfolio = [
            recommended,
            {
                "move_id": "keep-cross-topic-smoke-bounded",
                "status": "guardrail",
                "title": "Keep the cross-topic smoke bounded and explicit-command driven",
                "why": "The purpose of the smoke is to validate intake/routing quality, not to open a new automation or implementation line."
            }
        ]
        return {
            "format": "core-research-brain-portfolio-v2",
            "recommended_next_move": recommended,
            "portfolio": portfolio,
        }

    if execution_class == "blocked-same-class-rerun":
        recommended = {
            "move_id": "stop-same-class-rerun",
            "status": "recommended-now",
            "title": "Stop the same-proof-class rerun and reframe the next move",
            "why": "The target line is paused or locally exhausted, so another same-class rerun would only replay known blockers.",
            "do_now": [
                "Use the registry and negative-result set to design a materially different proof surface.",
                "Carry forward the blocker countermeasures before proposing the next experiment."
            ],
            "do_not_do": [
                "Do not start another same-class rerun from inertia."
            ]
        }
        return {
            "format": "core-research-brain-portfolio-v2",
            "recommended_next_move": recommended,
            "portfolio": [recommended, deferred_move],
        }

    recommended = deferred_move
    return {
        "format": "core-research-brain-portfolio-v2",
        "recommended_next_move": recommended,
        "portfolio": [recommended],
    }


def build_writeback_plan(
    out_dir: Path,
    intake: dict[str, Any],
) -> dict[str, Any]:
    targets = default_writeback_targets()
    targets.update({key: value for key, value in intake.get("writeback_targets", {}).items() if value})

    automatic_after_builder_run: list[dict[str, str]] = []
    if targets.get("log"):
        automatic_after_builder_run.append(
            {
                "destination": targets["log"],
                "class": "historical checkpoint",
                "action": "record the phase result plus the primary artifact root",
            }
        )
    if targets.get("todo"):
        automatic_after_builder_run.append(
            {
                "destination": targets["todo"],
                "class": "next-step / blocker",
                "action": "update the next required move or the active hold line",
            }
        )
    if targets.get("memory_index"):
        automatic_after_builder_run.append(
            {
                "destination": targets["memory_index"],
                "class": "durable pointer",
                "action": "point to the runtime files, derived artifact root, and rollback pack",
            }
        )

    if intake.get("writeback_candidates"):
        raw_candidates = intake["writeback_candidates"]
    elif intake.get("topic") == "core" and not intake.get("writeback_targets"):
        raw_candidates = default_writeback_candidates()
    else:
        raw_candidates = {}

    candidate_promotions = []
    for key, payload in raw_candidates.items():
        destination = targets.get(key)
        if not destination or not payload:
            continue
        candidate_promotions.append(
            {
                "destination": destination,
                "class": payload["class"],
                "candidate": payload["candidate"],
            }
        )

    return {
        "format": "core-post-run-writeback-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_artifact_root": str(out_dir),
        "automatic_after_builder_run": automatic_after_builder_run,
        "candidate_promotions": candidate_promotions,
        "still_requires_human_judgment": [
            "whether a derived portfolio is mature enough to become a real execution decision",
            "whether a new proof surface is materially different enough to resume a paused line",
            "which conclusions are stable enough to promote into steering or memory",
        ],
    }


def render_report(
    state: dict[str, Any],
    portfolio: dict[str, Any],
    writeback: dict[str, Any],
) -> str:
    lines: list[str] = [
        "# Research Brain V2",
        "",
        f"Generated at: `{state['generated_at']}`",
        f"Scope: `{state['intake']['history_scope']}`",
        "",
        "## What Already Existed In V1",
    ]
    for item in state["layer_boundary"]["already_in_v1"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## What V2 Adds Now",
        ]
    )
    for item in state["layer_boundary"]["added_in_v2_minimal_form"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Deferred To V3",
        ]
    )
    for item in state["layer_boundary"]["deferred_to_v3"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Current Decision",
            f"- intake classification: `{state['classification']['task_intake_class']}`",
            f"- search depth: `{state['classification']['search_depth']}`",
            f"- execution class: `{state['classification']['execution_class']}`",
            f"- why: {state['classification']['execution_reason']}",
            "",
            "## Enforcement",
        ]
    )
    if not state["enforcement"]["exhausted_line_guardrails"] and not state["enforcement"]["relevant_blocker_enforcement"]:
        lines.append("- no relevant exhausted lines or registry blockers were pulled for this intake")
    else:
        for item in state["enforcement"]["exhausted_line_guardrails"]:
            lines.append(f"- `{item['line_id']}`: {item['enforcement']} ({item['reason']})")
        for item in state["enforcement"]["relevant_blocker_enforcement"]:
            lines.append(f"- `{item['blocker_id']}`: {item['countermeasure']}")
    lines.extend(
        [
            "",
            "## Negative Results Worth Remembering",
        ]
    )
    if not state["enforcement"]["negative_results_to_remember"]:
        lines.append("- no registry negative results were relevant to this intake")
    else:
        for item in state["enforcement"]["negative_results_to_remember"]:
            lines.append(f"- `{item['experiment_id']}`: {item['why_it_matters']}")
    lines.extend(
        [
            "",
            "## Portfolio",
            f"- recommended now: `{portfolio['recommended_next_move']['move_id']}`",
            f"- why: {portfolio['recommended_next_move']['why']}",
            "",
            "## Automation Boundary",
            "Automatic once the builder is invoked:",
        ]
    )
    for item in state["automation_boundary"]["automatic_on_builder_run"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Still explicit or manual:")
    for item in state["automation_boundary"]["explicit_only"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Writeback",
        ]
    )
    for item in writeback["candidate_promotions"]:
        lines.append(f"- `{Path(item['destination']).name}`: {item['candidate']}")
    return "\n".join(lines)


def build_state(
    intake: dict[str, Any],
    rules: dict[str, Any],
    registry: dict[str, Any],
    patterns: dict[str, Any],
    v1_portfolio: dict[str, Any],
    context_signals: dict[str, Any],
    intake_path: Path,
    rules_path: Path,
    registry_root: Path,
    durable_context_inputs: list[str],
    search_depth: str,
    search_reason: str,
    search_rule_id: str,
    execution_class: str,
    execution_reason: str,
) -> dict[str, Any]:
    exhausted_lines = {item["line_id"] for item in patterns.get("locally_exhausted_lines", [])}
    parity_lines = {item["line_id"] for item in patterns.get("parity_prone_families", [])}
    active_holds = [
        line_id
        for line_id in intake.get("paused_line_ids", [])
        if line_id in exhausted_lines or line_id in parity_lines
    ]

    return {
        "format": "core-research-brain-state-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_of_truth": build_source_of_truth(intake_path, rules_path, registry_root, durable_context_inputs),
        "layer_boundary": build_layer_boundary(rules),
        "intake": intake,
        "classification": {
            "task_intake_class": intake["task_kind"],
            "history_status": intake.get("history_status", "paused-skills-line-with-meta-layer-build"),
            "search_depth": search_depth,
            "search_depth_rule_id": search_rule_id,
            "search_depth_reason": search_reason,
            "execution_class": execution_class,
            "execution_reason": execution_reason,
            "active_hold_lines": active_holds,
            "deferred_resume_line_id": intake.get("deferred_resume_line_id"),
            "v1_summary": registry["summary"],
            "context_inputs_used": durable_context_inputs,
            "steering_signals": context_signals,
        },
        "enforcement": build_enforcement(intake, patterns, rules, v1_portfolio, registry),
        "automation_boundary": rules["hook_policy"],
    }


def validate_output_against_schema(payload: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    require_fields(payload, "output state", list(schema["required"]))
    if payload.get("format") != schema["properties"]["format"]["const"]:
        raise ValueError("output state format does not match the declared schema")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build research-brain-v2 derived outputs.")
    parser.add_argument("--intake", default=str(DEFAULT_INTAKE))
    parser.add_argument("--rules", default=str(DEFAULT_RULES))
    parser.add_argument("--registry-root", default=str(DEFAULT_REGISTRY_ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    intake_path = Path(args.intake).resolve()
    rules_path = Path(args.rules).resolve()
    registry_root = Path(args.registry_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    intake = load_json(intake_path)
    rules = load_json(rules_path)
    require_fields(
        intake,
        "intake",
        [
            "format",
            "intake_id",
            "task_kind",
            "topic",
            "focus_area",
            "history_scope",
            "requires_new_experiment_run",
            "needs_external_sources",
            "needs_cross_topic_search",
            "proof_class_change",
            "paused_line_ids",
            "requested_capabilities",
            "constraints",
            "seed_artifacts",
            "durable_writeback_required",
        ],
    )
    require_fields(
        rules,
        "rules",
        [
            "format",
            "v1_capabilities",
            "v2_minimal_components",
            "v3_deferred",
            "task_kind_to_execution_class",
            "execution_classes",
            "search_depth_rules",
            "blocker_countermeasures",
            "priority_negative_result_ids",
            "hook_policy",
        ],
    )
    if intake["format"] != "core-research-brain-intake-v2":
        raise ValueError("unexpected intake format")
    if rules["format"] != "core-research-brain-rules-v2":
        raise ValueError("unexpected rules format")

    registry, patterns, v1_portfolio = load_registry_inputs(registry_root)
    durable_context_inputs = intake.get("durable_context_inputs", default_durable_context_inputs())
    context_signals = build_context_signals(intake, durable_context_inputs)

    exhausted_lines = {item["line_id"] for item in patterns.get("locally_exhausted_lines", [])}
    search_depth, search_reason, search_rule_id = choose_search_depth(intake, exhausted_lines, rules)
    execution_class, execution_reason = choose_execution_class(intake, exhausted_lines, rules)

    state = build_state(
        intake,
        rules,
        registry,
        patterns,
        v1_portfolio,
        context_signals,
        intake_path,
        rules_path,
        registry_root,
        durable_context_inputs,
        search_depth,
        search_reason,
        search_rule_id,
        execution_class,
        execution_reason,
    )
    validate_output_against_schema(state, DEFAULT_OUTPUT_SCHEMA)

    portfolio = build_portfolio(intake, execution_class, v1_portfolio)
    portfolio["generated_at"] = datetime.now(timezone.utc).isoformat()
    portfolio["input_experiment_count"] = registry["summary"]["included_experiments"]
    writeback = build_writeback_plan(out_dir, intake)
    report = render_report(state, portfolio, writeback)

    dump_json(out_dir / "research-brain-state-v2.json", state)
    dump_json(out_dir / "next-step-portfolio-v2.json", portfolio)
    dump_json(out_dir / "post-run-writeback-v2.json", writeback)
    dump_text(out_dir / "research-brain-report-v2.md", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
