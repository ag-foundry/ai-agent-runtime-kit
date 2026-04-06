#!/usr/bin/env python3
"""Shared generation rules for commentable text files."""

from __future__ import annotations

import re
from pathlib import Path


INVOCATION_TEXT = "Во имя Отца и Сына и Святаго Духа. Аминь."
STRUCTURED_HEADER_RE = re.compile(r"^[a-z_]+:\s*", re.MULTILINE)


def invocation_line_for(path: Path, content: str) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".py", ".sh", ".yaml", ".yml"}:
        return f"# {INVOCATION_TEXT}"
    if suffix == ".md":
        if content.startswith("---\n"):
            return f"# {INVOCATION_TEXT}"
        return f"<!-- {INVOCATION_TEXT} -->"
    return None


def apply_invocation_line(path: Path, content: str) -> str:
    invocation_line = invocation_line_for(path, content)
    if invocation_line is None or any(INVOCATION_TEXT in line for line in content.splitlines()[:4]):
        return content
    if path.suffix.lower() == ".md" and content.startswith("---\n"):
        _, remainder = content.split("\n", 1)
        return f"---\n{invocation_line}\n{remainder}"
    if path.suffix.lower() == ".md" and STRUCTURED_HEADER_RE.match(content):
        separator = "\n"
    else:
        separator = "\n\n" if content else "\n"
    return f"{invocation_line}{separator}{content}"
