#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path("/home/agent/agents")
LIVE_ROOT = Path("/home/agent/bin")
CANONICAL_ROOT = REPO_ROOT / "_runtime" / "canonical" / "bin"
META_ROOT = REPO_ROOT / "_runtime" / "canonical" / "meta"

FILELIST = META_ROOT / "protected-working-set.txt"
SRC_HASHES = META_ROOT / "src-from-bin.sha256"
CANONICAL_HASHES = META_ROOT / "canonical.sha256"
OUTFILE = META_ROOT / "runtime-manifest.json"


def die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_entry(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("#"):
        return ""

    candidate = PurePosixPath(line)
    if candidate.is_absolute():
        die(f"absolute path is not allowed in protected-working-set.txt: {line}")

    if any(part in ("", ".", "..") for part in candidate.parts):
        die(f"invalid relative path in protected-working-set.txt: {line}")

    return candidate.as_posix()


def read_protected_set(path: Path) -> list[str]:
    if not path.is_file():
        die(f"missing protected working set file: {path}")

    names: list[str] = []
    seen: set[str] = set()

    for raw in path.read_text(encoding="utf-8").splitlines():
        name = normalize_entry(raw)
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        names.append(name)

    if not names:
        die(f"protected working set file is empty: {path}")

    return sorted(names)


def collect_entry(name: str) -> dict[str, Any]:
    live_path = LIVE_ROOT / name
    canonical_path = CANONICAL_ROOT / name

    live_exists = live_path.is_file()
    canonical_exists = canonical_path.is_file()

    live_sha256 = sha256_file(live_path) if live_exists else None
    canonical_sha256 = sha256_file(canonical_path) if canonical_exists else None

    parity_ok = bool(
        live_exists
        and canonical_exists
        and live_sha256 is not None
        and canonical_sha256 is not None
        and live_sha256 == canonical_sha256
    )

    return {
        "name": name,
        "live_path": str(live_path),
        "canonical_path": str(canonical_path),
        "live_exists": live_exists,
        "canonical_exists": canonical_exists,
        "live_sha256": live_sha256,
        "canonical_sha256": canonical_sha256,
        "parity_ok": parity_ok,
    }


def build_manifest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    live_missing_count = sum(1 for row in entries if not row["live_exists"])
    canonical_missing_count = sum(1 for row in entries if not row["canonical_exists"])
    parity_ok_count = sum(1 for row in entries if row["parity_ok"])
    parity_bad_count = len(entries) - parity_ok_count

    in_sync = (
        live_missing_count == 0
        and canonical_missing_count == 0
        and parity_bad_count == 0
    )

    return {
        "schema_version": "runtime-manifest-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generated_by": "/home/agent/agents/_runtime/tools/build-runtime-manifest.py",
        "repo_root": str(REPO_ROOT),
        "live_runtime_root": str(LIVE_ROOT),
        "canonical_runtime_root": str(CANONICAL_ROOT),
        "meta_root": str(META_ROOT),
        "reference_files": {
            "protected_working_set": str(FILELIST),
            "source_hashes": str(SRC_HASHES),
            "canonical_hashes": str(CANONICAL_HASHES),
        },
        "summary": {
            "protected_file_count": len(entries),
            "live_missing_count": live_missing_count,
            "canonical_missing_count": canonical_missing_count,
            "parity_ok_count": parity_ok_count,
            "parity_bad_count": parity_bad_count,
            "in_sync": in_sync,
        },
        "files": entries,
    }


def load_existing_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"failed to parse existing manifest {path}: {exc}")

    if not isinstance(data, dict):
        die(f"existing manifest is not a JSON object: {path}")

    return data


def strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_volatile(item)
            for key, item in value.items()
            if key != "generated_at_utc"
        }
    if isinstance(value, list):
        return [strip_volatile(item) for item in value]
    return value


def write_manifest_if_needed(manifest: dict[str, Any]) -> str:
    previous = load_existing_manifest(OUTFILE)

    if previous is None:
        OUTFILE.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return "CREATED"

    if strip_volatile(previous) == strip_volatile(manifest):
        return "UNCHANGED"

    OUTFILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return "UPDATED"


def main() -> int:
    if not REPO_ROOT.is_dir():
        die(f"repo root not found: {REPO_ROOT}")
    if not LIVE_ROOT.is_dir():
        die(f"live runtime root not found: {LIVE_ROOT}")
    if not CANONICAL_ROOT.is_dir():
        die(f"canonical runtime root not found: {CANONICAL_ROOT}")
    if not META_ROOT.is_dir():
        die(f"meta root not found: {META_ROOT}")

    protected_names = read_protected_set(FILELIST)
    entries = [collect_entry(name) for name in protected_names]
    manifest = build_manifest(entries)

    write_mode = write_manifest_if_needed(manifest)
    summary = manifest["summary"]

    print("MANIFEST_OK")
    print(f"outfile: {OUTFILE}")
    print(f"write_mode: {write_mode}")
    print(f"protected_file_count: {summary['protected_file_count']}")
    print(f"parity_ok_count: {summary['parity_ok_count']}")
    print(f"parity_bad_count: {summary['parity_bad_count']}")
    print(f"live_missing_count: {summary['live_missing_count']}")
    print(f"canonical_missing_count: {summary['canonical_missing_count']}")
    print("MANIFEST_STATUS=IN_SYNC" if summary["in_sync"] else "MANIFEST_STATUS=DRIFT")

    return 0 if summary["in_sync"] else 2


if __name__ == "__main__":
    raise SystemExit(main())