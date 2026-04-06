#!/usr/bin/env python3
# Во имя Отца и Сына и Святаго Духа. Аминь.
"""Shared utilities for creator-compatible skill discovery and manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def metadata_contract_path() -> Path:
    return package_root() / "definitions" / "skill-metadata-contract.json"


def trial_contract_path() -> Path:
    return package_root() / "definitions" / "trial-plan-contract.json"


def load_metadata_contract() -> dict[str, Any]:
    return json.loads(metadata_contract_path().read_text(encoding="utf-8"))


def load_trial_contract() -> dict[str, Any]:
    return json.loads(trial_contract_path().read_text(encoding="utf-8"))


def extract_frontmatter(content: str) -> str | None:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return None


def parse_simple_frontmatter(frontmatter_text: str) -> dict[str, str] | None:
    parsed: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in frontmatter_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[:1].isspace():
            if current_key is None:
                return None
            existing = parsed[current_key]
            parsed[current_key] = f"{existing}\n{stripped}" if existing else stripped
            continue
        if ":" not in stripped:
            return None
        key, value = stripped.split(":", 1)
        current_key = key.strip()
        parsed[current_key] = value.strip().strip("\"'")
    return parsed


def load_skill_frontmatter(skill_dir: Path) -> tuple[dict[str, Any], str]:
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    frontmatter_text = extract_frontmatter(content)
    if frontmatter_text is None:
        raise ValueError("invalid or missing YAML frontmatter")
    if yaml is not None:
        data = yaml.safe_load(frontmatter_text)
    else:
        data = parse_simple_frontmatter(frontmatter_text)
    if not isinstance(data, dict):
        raise ValueError("frontmatter must parse to a mapping")
    return data, content


def discover_skill_dirs(skills_roots: list[Path], explicit_skill_dirs: list[Path]) -> list[Path]:
    discovered: dict[str, Path] = {}
    for root in skills_roots:
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                discovered[str(child.resolve())] = child.resolve()
    for skill_dir in explicit_skill_dirs:
        if (skill_dir / "SKILL.md").exists():
            discovered[str(skill_dir.resolve())] = skill_dir.resolve()
    return sorted(discovered.values())


def normalize_profile_name(skill_name: str, role: str) -> str:
    if role == "baseline":
        return "skill-eval-baseline"
    if role == "trial":
        return f"skill-eval-with-{skill_name}"
    raise ValueError(f"unsupported profile role: {role}")


def load_inventory_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inventory_skill_map(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        entry["skill_name"]: entry
        for entry in inventory.get("skills", [])
        if isinstance(entry, dict) and entry.get("skill_name")
    }
