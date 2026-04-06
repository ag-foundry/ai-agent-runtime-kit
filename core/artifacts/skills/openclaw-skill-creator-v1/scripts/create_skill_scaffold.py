#!/usr/bin/env python3
"""Create a canonical managed-skill scaffold from bundled templates."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from file_rules import apply_invocation_line
from skill_manifest import load_metadata_contract


PLACEHOLDER_PATTERN = re.compile(r"__([A-Z_]+)__")
NAME_RE = re.compile(r"^[a-z0-9-]+$")


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def template_root() -> Path:
    return package_root() / "templates" / "managed-skill"


def require_valid_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError("skill name must be lowercase hyphen-case")


def render_text(text: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return values[key]

    return PLACEHOLDER_PATTERN.sub(replace, text)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(apply_invocation_line(path, content), encoding="utf-8")


def create_scaffold(output_dir: Path, values: dict[str, str]) -> list[str]:
    created: list[str] = []
    for src in template_root().rglob("*"):
        rel = src.relative_to(template_root())
        if src.is_dir():
            (output_dir / rel).mkdir(parents=True, exist_ok=True)
            continue
        target_rel = rel.with_name(rel.name[:-5]) if rel.name.endswith(".tmpl") else rel
        target = output_dir / target_rel
        rendered = render_text(src.read_text(encoding="utf-8"), values)
        write_text(target, rendered)
        created.append(str(target))

    for extra_dir in ["scripts"]:
        (output_dir / extra_dir).mkdir(parents=True, exist_ok=True)

    return created


def main() -> int:
    contract = load_metadata_contract()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--skill-name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--invocation", default="manual-task")
    parser.add_argument("--maturity", default="draft")
    parser.add_argument("--primary-capability", action="append", default=[])
    parser.add_argument("--secondary-capability", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    require_valid_name(args.skill_name)
    if args.invocation not in set(contract["enums"]["invocation"]):
        raise SystemExit(f"unsupported invocation: {args.invocation}")
    if args.maturity not in set(contract["enums"]["maturity"]):
        raise SystemExit(f"unsupported maturity: {args.maturity}")
    if not args.description.strip():
        raise SystemExit("description must be non-empty")
    primary_capabilities = args.primary_capability or ["replace-with-primary-capability"]
    secondary_capabilities = args.secondary_capability or []

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        raise SystemExit(f"output directory already exists and is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    values = {
        "SKILL_NAME": args.skill_name,
        "SKILL_TITLE": args.skill_name.replace("-", " ").title(),
        "DESCRIPTION": args.description.strip(),
        "INVOCATION": args.invocation,
        "MATURITY": args.maturity,
        "PRIMARY_CAPABILITIES": json.dumps(primary_capabilities),
        "SECONDARY_CAPABILITIES": json.dumps(secondary_capabilities),
    }
    created = create_scaffold(output_dir, values)
    manifest = {
        "output_dir": str(output_dir),
        "skill_name": args.skill_name,
        "created_files": created,
        "template_root": str(template_root()),
    }
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
