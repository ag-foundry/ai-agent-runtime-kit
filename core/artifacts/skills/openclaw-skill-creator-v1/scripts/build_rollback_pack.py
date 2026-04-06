#!/usr/bin/env python3
"""Create a rollback pack for selected files."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def copy_into_pack(src: Path, output_dir: Path) -> str:
    rel = Path(str(src).lstrip("/"))
    target = output_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
    else:
        shutil.copy2(src, target)
    return str(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--path", action="append", default=[], required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for raw_path in args.path:
        src = Path(raw_path)
        if not src.exists():
            raise SystemExit(f"path does not exist: {src}")
        copied.append({"source": str(src), "backup": copy_into_pack(src, output_dir)})

    manifest = {"output_dir": str(output_dir), "copied": copied}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
