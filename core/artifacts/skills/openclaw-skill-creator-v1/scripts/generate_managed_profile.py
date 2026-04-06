#!/usr/bin/env python3
# Во имя Отца и Сына и Святаго Духа. Аминь.
"""Generate an isolated one-skill-under-test OpenClaw profile."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from skill_manifest import (
    discover_skill_dirs,
    inventory_skill_map,
    load_inventory_manifest,
    load_skill_frontmatter,
)


def profile_root(profile_name: str, home: Path) -> Path:
    return home / f".openclaw-{profile_name}"


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def prepare_profile_workspace(profile_root_dir: Path, source_workspace: Path) -> Path:
    workspace_root = profile_root_dir / "workspace"
    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    if source_workspace.exists():
        shutil.copytree(source_workspace, workspace_root)
    else:
        workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "skills").mkdir(parents=True, exist_ok=True)
    return workspace_root


def build_config(source_config: dict, workspace: str, managed_skills: list[str], enabled_skills: set[str]) -> dict:
    cfg = json.loads(json.dumps(source_config))
    agents = cfg.setdefault("agents", {})
    defaults = agents.setdefault("defaults", {})
    defaults["workspace"] = workspace

    skills = cfg.setdefault("skills", {})
    entries = skills.setdefault("entries", {})
    for skill_name in managed_skills:
        entry = dict(entries.get(skill_name) or {})
        entry["enabled"] = skill_name in enabled_skills
        entries[skill_name] = entry
    return cfg


def verify_config(config: dict, managed_skills: list[str], expected_enabled: set[str]) -> None:
    entries = (((config.get("skills") or {}).get("entries")) or {})
    enabled = {
        skill_name
        for skill_name in managed_skills
        if isinstance(entries.get(skill_name), dict) and entries[skill_name].get("enabled") is True
    }
    if enabled != expected_enabled:
        raise SystemExit(
            f"generated profile drifted from expected enablement: expected {sorted(expected_enabled)}, got {sorted(enabled)}"
        )


def resolve_skill_sources(
    inventory_manifest: str | None,
    source_skills: str,
    explicit_skill_dirs: list[str],
) -> dict[str, Path]:
    if inventory_manifest:
        inventory = load_inventory_manifest(Path(inventory_manifest))
        return {
            name: Path(entry["skill_dir"])
            for name, entry in inventory_skill_map(inventory).items()
            if entry.get("skill_dir")
        }

    skill_dirs = discover_skill_dirs([Path(source_skills)], [Path(path) for path in explicit_skill_dirs])
    resolved: dict[str, Path] = {}
    for skill_dir in skill_dirs:
        frontmatter, _content = load_skill_frontmatter(skill_dir)
        name = frontmatter.get("name", skill_dir.name)
        if isinstance(name, str):
            resolved[name] = skill_dir
    return resolved


def copied_skill_names(managed_skills: list[str], enabled_skills: set[str], skill_copy_mode: str) -> list[str]:
    if skill_copy_mode == "enabled-only":
        return sorted(enabled_skills)
    return managed_skills


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--enable-skill")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--managed-skill", action="append", default=[])
    parser.add_argument("--include-skill", action="append", default=[])
    parser.add_argument("--inventory-manifest")
    parser.add_argument("--source-config", default="/home/agent/.openclaw/openclaw.json")
    parser.add_argument("--source-skills", default="/home/agent/.openclaw/skills")
    parser.add_argument("--skill-dir", action="append", default=[])
    parser.add_argument("--workspace", default="/home/agent/.openclaw/workspace")
    parser.add_argument("--home", default="/home/agent")
    parser.add_argument("--skill-copy-mode", choices=["selected", "enabled-only"], default="selected")
    parser.add_argument("--output-manifest")
    args = parser.parse_args()

    skill_sources = resolve_skill_sources(args.inventory_manifest, args.source_skills, args.skill_dir)
    selected_names = sorted(set(args.include_skill + args.managed_skill))
    managed_skills = selected_names or sorted(skill_sources)
    if args.baseline and args.enable_skill:
        raise SystemExit("--baseline and --enable-skill are mutually exclusive")
    if not args.baseline and not args.enable_skill:
        raise SystemExit("either --baseline or --enable-skill is required")
    if args.enable_skill and args.enable_skill not in managed_skills:
        raise SystemExit("--enable-skill must be included in the managed skill set")
    enabled_skills = set()
    if args.enable_skill:
        enabled_skills = {args.enable_skill}

    home = Path(args.home)
    root = profile_root(args.profile_name, home)
    root.mkdir(parents=True, exist_ok=True)

    source_config = json.loads(Path(args.source_config).read_text(encoding="utf-8"))
    config_path = root / "openclaw.json"
    source_workspace = Path(args.workspace)
    profile_workspace = prepare_profile_workspace(root, source_workspace)
    config = build_config(source_config, str(profile_workspace), managed_skills, enabled_skills)
    verify_config(config, managed_skills, enabled_skills)

    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    target_skills_dir = profile_workspace / "skills"
    copied_skills = copied_skill_names(managed_skills, enabled_skills, args.skill_copy_mode)
    for skill_name in copied_skills:
        src = skill_sources.get(skill_name)
        if src and src.exists():
            copy_tree(src, target_skills_dir / skill_name)

    disabled_skills = [name for name in managed_skills if name not in enabled_skills]
    manifest = {
        "format": "openclaw-skill-profile-v1",
        "profile_name": args.profile_name,
        "profile_mode": "baseline" if args.baseline else "with-skill",
        "profile_root": str(root),
        "config_path": str(config_path),
        "skills_dir": str(target_skills_dir),
        "workspace": str(profile_workspace),
        "source_workspace": str(source_workspace),
        "inventory_manifest": args.inventory_manifest,
        "managed_skills": managed_skills,
        "selected_skills": managed_skills,
        "copied_skills": copied_skills,
        "enabled_skill": args.enable_skill,
        "enabled_skills": sorted(enabled_skills),
        "disabled_skills": disabled_skills,
        "isolation_rule": "zero or one managed skills enabled",
        "skill_copy_mode": args.skill_copy_mode,
        "profile_role": "baseline" if args.baseline else "trial",
    }
    if args.output_manifest:
        output_manifest = Path(args.output_manifest)
        output_manifest.parent.mkdir(parents=True, exist_ok=True)
        output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
