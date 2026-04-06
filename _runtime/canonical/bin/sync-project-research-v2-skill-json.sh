#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import json

ROOT = Path("/home/agent/agents/_shared/skills/project-research-v2-draft")
SKILL_JSON = ROOT / "skill.json"

data = json.loads(SKILL_JSON.read_text(encoding="utf-8"))

data["artifact_contract_ref"] = "references/RUNNER_V2_ARTIFACT_CONTRACT.md"

data["required_outputs"] = [
    "RESEARCH.md",
    "sources.json",
    "run_manifest.json",
    "findings.jsonl",
    "provenance.json",
    "quality_report.json"
]

data["required_schemas"] = [
    "schemas/context.schema.json",
    "schemas/source.schema.json",
    "schemas/finding.schema.json",
    "schemas/research_report.schema.json",
    "schemas/run_manifest.schema.json"
]

data["quality_gates"] = [
    "search_targets_have_query_sets",
    "no_memory_boilerplate_dominance",
    "starting_approach_not_generic",
    "anti_patterns_present",
    "provenance_present_for_findings"
]

data["runner_contract"] = {
    "artifact_dir_pattern": "artifacts/research/<timestamp>/",
    "canonical_artifacts": [
        "RESEARCH.md",
        "sources.json",
        "run_manifest.json",
        "findings.jsonl",
        "provenance.json",
        "quality_report.json"
    ],
    "convenience_outputs": [
        "RESEARCH.md",
        "sources.json"
    ],
    "latest_symlink": "artifacts/research/latest"
}

data["runner_write_order"] = [
    "context.json",
    "sources.json",
    "findings.jsonl",
    "provenance.json",
    "quality_report.json",
    "run_manifest.json",
    "RESEARCH.md"
]

data["consistency_requirements"] = [
    "project_type_consistent_across_artifacts",
    "mode_consistent_across_artifacts",
    "artifact_dir_consistent_across_artifacts",
    "search_targets_aligned_with_query_sets",
    "starting_approach_consistent_between_sources_and_research",
    "quality_report_and_run_manifest_status_aligned"
]

data["non_goals_current_stage"] = [
    "full_deep_research_execution",
    "self_modify_skill",
    "self_upgrade_dependencies",
    "auto_delete_important_artifacts",
    "weekly_watchtower_logic",
    "hygiene_cleanup_logic"
]

SKILL_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"updated: {SKILL_JSON}")
print()
print("Next run:")
print("python3 /home/agent/agents/_shared/skills/project-research-v2-draft/scripts/validate_skill.py")
print("sed -n '1,260p' /home/agent/agents/_shared/skills/project-research-v2-draft/skill.json")
PY