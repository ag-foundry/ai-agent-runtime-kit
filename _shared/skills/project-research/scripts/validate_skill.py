#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
errors = []

required = [
    root / "SKILL.md",
    root / "references" / "policy.md",
    root / "references" / "checklist.md",
    root / "assets" / "RESEARCH.md.tpl",
    root / "assets" / "sources.json.tpl",
    root / "scripts" / "precheck_memory.sh",
    root / "scripts" / "render_research_stub.py",
    root / "evals" / "trigger_queries.md",
]
for p in required:
    if not p.exists():
        errors.append(f"missing: {p}")

skill_md = root / "SKILL.md"
if skill_md.exists():
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append("SKILL.md: missing YAML front matter")
    if "name:" not in text:
        errors.append("SKILL.md: missing name")
    if "description:" not in text:
        errors.append("SKILL.md: missing description")

    required_phrases = [
        "Use this skill when",
        "Do not use this skill when",
        "Research modes",
        "Source priority",
        "Success criteria",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(f"SKILL.md: missing section phrase: {phrase}")

banned_markers = ["xmltv", "epg ", "python-only", "django-only", "nextjs-only"]

scan_files = [
    root / "SKILL.md",
    root / "README.md",
    root / "references" / "policy.md",
    root / "references" / "checklist.md",
    root / "assets" / "RESEARCH.md.tpl",
    root / "assets" / "sources.json.tpl",
]

text_all = "\n".join(
    p.read_text(encoding="utf-8", errors="ignore")
    for p in scan_files
    if p.exists()
).lower()

for marker in banned_markers:
    if marker in text_all:
        errors.append(f"project-specific marker found in content: {marker}")

if errors:
    print("VALIDATION FAILED")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("VALIDATION OK")
print(root)
