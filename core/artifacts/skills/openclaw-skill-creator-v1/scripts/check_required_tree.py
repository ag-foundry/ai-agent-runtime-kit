#!/usr/bin/env python3
"""Check the required file tree for a creator-compatible skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def default_spec() -> Path:
    return Path(__file__).resolve().parents[1] / "definitions" / "required-skill-tree.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--spec", default=str(default_spec()))
    args = parser.parse_args()

    root = Path(args.root)
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))

    missing_files = [path for path in spec.get("required_files", []) if not (root / path).exists()]
    missing_dirs = [path for path in spec.get("recommended_dirs", []) if not (root / path).exists()]

    result = {
        "root": str(root),
        "spec": str(args.spec),
        "missing_files": missing_files,
        "missing_recommended_dirs": missing_dirs,
        "ok": not missing_files,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
