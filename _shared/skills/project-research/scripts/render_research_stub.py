#!/usr/bin/env python3
from pathlib import Path
import argparse
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("--topic", required=True)
parser.add_argument("--project-type", default="mixed")
parser.add_argument("--mode", default="quick", choices=["none", "quick", "deep"])
parser.add_argument("--out-dir", default=".")
parser.add_argument("--force", action="store_true")
args = parser.parse_args()

out_dir = Path(args.out_dir).resolve()
out_dir.mkdir(parents=True, exist_ok=True)

skill_root = Path(__file__).resolve().parents[1]
research_tpl = (skill_root / "assets" / "RESEARCH.md.tpl").read_text(encoding="utf-8")
sources_tpl = (skill_root / "assets" / "sources.json.tpl").read_text(encoding="utf-8")

research_path = out_dir / "RESEARCH.md"
sources_path = out_dir / "sources.json"

if (research_path.exists() or sources_path.exists()) and not args.force:
    raise SystemExit("RESEARCH.md or sources.json already exists; use --force to overwrite")

research_text = research_tpl.replace("<topic>", args.topic)
research_text = research_text.replace("<software | website | analytics | automation | infrastructure | business | content | documentation | mixed>", args.project_type, 1)
research_text = research_text.replace("<none | quick | deep>", args.mode, 1)

sources_text = sources_tpl.replace("<topic>", args.topic)
sources_text = sources_text.replace("<type>", args.project_type)
sources_text = sources_text.replace('"quick"', f'"{args.mode}"', 1)

research_path.write_text(research_text, encoding="utf-8")
sources_path.write_text(sources_text, encoding="utf-8")
print(f"wrote: {research_path}")
print(f"wrote: {sources_path}")
