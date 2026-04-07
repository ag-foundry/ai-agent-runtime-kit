#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def repo_root(script_file: str) -> Path:
    configured = os.environ.get("AGENT_REPO_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(script_file).resolve().parents[2]


def live_runtime_root() -> Path:
    configured = os.environ.get("AGENT_BIN_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path("/home/agent/bin")


def repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)
