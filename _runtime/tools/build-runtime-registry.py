#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_paths import live_runtime_root, repo_relative, repo_root

REPO_ROOT = repo_root(__file__)
RUNTIME_ROOT = REPO_ROOT / "_runtime"
TOOLS_DIR = RUNTIME_ROOT / "tools"
CANONICAL_ROOT = RUNTIME_ROOT / "canonical"
CANONICAL_BIN_ROOT = CANONICAL_ROOT / "bin"
CANONICAL_META_ROOT = CANONICAL_ROOT / "meta"
LIVE_ROOT = live_runtime_root()
SCRIPT_PATH = Path(__file__).resolve()

OUTFILE = RUNTIME_ROOT / "runtime-registry.json"
MANIFEST_FILE = CANONICAL_META_ROOT / "runtime-manifest.json"


def die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def bool_str(value: bool) -> str:
    return "YES" if value else "NO"


def file_record(path: Path, role: str, executable_expected: bool = False) -> dict[str, Any]:
    present = path.is_file()
    executable = os.access(path, os.X_OK) if present else False
    return {
        "name": path.name,
        "path": str(path),
        "role": role,
        "present": present,
        "executable_expected": executable_expected,
        "executable": executable,
    }


def load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"_parse_error": True}

    if not isinstance(data, dict):
        return {"_parse_error": True}

    return data


def manifest_summary(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "present": path.is_file(),
        "parse_ok": False,
        "schema_version": "",
        "generated_at_utc": "",
        "protected_file_count": 0,
        "live_missing_count": 0,
        "canonical_missing_count": 0,
        "parity_ok_count": 0,
        "parity_bad_count": 0,
        "in_sync": False,
    }

    data = load_json_object(path)
    if data is None:
        return result

    if data.get("_parse_error"):
        return result

    summary = data.get("summary") or {}
    if not isinstance(summary, dict):
        summary = {}

    result["parse_ok"] = True
    result["schema_version"] = data.get("schema_version", "")
    result["generated_at_utc"] = data.get("generated_at_utc", "")
    result["protected_file_count"] = int(summary.get("protected_file_count", 0) or 0)
    result["live_missing_count"] = int(summary.get("live_missing_count", 0) or 0)
    result["canonical_missing_count"] = int(summary.get("canonical_missing_count", 0) or 0)
    result["parity_ok_count"] = int(summary.get("parity_ok_count", 0) or 0)
    result["parity_bad_count"] = int(summary.get("parity_bad_count", 0) or 0)
    result["in_sync"] = bool(summary.get("in_sync"))

    return result


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


def write_json_if_needed(path: Path, data: dict[str, Any]) -> str:
    if not path.exists():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return "CREATED"

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        existing = None

    if strip_volatile(existing) == strip_volatile(data):
        return "UNCHANGED"

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "UPDATED"


def build_registry() -> dict[str, Any]:
    if not REPO_ROOT.is_dir():
        die(f"repo root not found: {REPO_ROOT}")
    if not RUNTIME_ROOT.is_dir():
        die(f"runtime root not found: {RUNTIME_ROOT}")
    if not TOOLS_DIR.is_dir():
        die(f"tools dir not found: {TOOLS_DIR}")
    if not CANONICAL_ROOT.is_dir():
        die(f"canonical root not found: {CANONICAL_ROOT}")
    if not CANONICAL_META_ROOT.is_dir():
        die(f"canonical meta root not found: {CANONICAL_META_ROOT}")
    if not LIVE_ROOT.is_dir():
        die(f"live runtime root not found: {LIVE_ROOT}")

    docs = [
        file_record(RUNTIME_ROOT / "README.md", "runtime_readme"),
        file_record(RUNTIME_ROOT / "RUNTIME_SYNC_WORKFLOW.md", "workflow_doc"),
        file_record(TOOLS_DIR / "README.md", "tools_readme"),
    ]

    tools = [
        file_record(TOOLS_DIR / "sync-protected-runtime.sh", "sync_tool", executable_expected=True),
        file_record(TOOLS_DIR / "status-protected-runtime.sh", "status_tool", executable_expected=True),
        file_record(TOOLS_DIR / "build-runtime-manifest.py", "manifest_builder", executable_expected=True),
        file_record(TOOLS_DIR / "runtime-commit-readiness.sh", "readiness_helper", executable_expected=True),
        file_record(TOOLS_DIR / "runtime-sync-flow.sh", "runtime_sync_flow", executable_expected=True),
        file_record(TOOLS_DIR / "runtime-governance-status.sh", "governance_status_helper", executable_expected=True),
        file_record(TOOLS_DIR / "runtime-governance-flow.sh", "governance_flow_wrapper", executable_expected=True),
        file_record(TOOLS_DIR / "build-runtime-registry.py", "registry_builder", executable_expected=True),
    ]

    canonical_meta_files = [
        file_record(CANONICAL_META_ROOT / "protected-working-set.txt", "protected_working_set"),
        file_record(CANONICAL_META_ROOT / "src-from-bin.sha256", "source_hashes"),
        file_record(CANONICAL_META_ROOT / "canonical.sha256", "canonical_hashes"),
        file_record(CANONICAL_META_ROOT / "runtime-manifest.json", "runtime_manifest"),
    ]

    manifest = manifest_summary(MANIFEST_FILE)

    required_docs_present = all(bool(item["present"]) for item in docs)
    required_tools_present = all(bool(item["present"]) for item in tools)
    executable_tools_ok = all(
        (not item["executable_expected"]) or bool(item["executable"])
        for item in tools
    )
    canonical_meta_present = sum(1 for item in canonical_meta_files if item["present"])
    manifest_healthy = bool(manifest["present"] and manifest["parse_ok"] and manifest["in_sync"])

    registry_healthy = (
        required_docs_present
        and required_tools_present
        and executable_tools_ok
        and manifest_healthy
    )

    return {
        "schema_version": "runtime-registry-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generated_by": repo_relative(SCRIPT_PATH, REPO_ROOT),
        "runtime_layer": {
            "repo_root": str(REPO_ROOT),
            "runtime_root": str(RUNTIME_ROOT),
            "live_runtime_root": str(LIVE_ROOT),
            "canonical_root": str(CANONICAL_ROOT),
            "canonical_bin_root": str(CANONICAL_BIN_ROOT),
            "canonical_meta_root": str(CANONICAL_META_ROOT),
        },
        "entrypoints": {
            "workflow_doc": str(RUNTIME_ROOT / "RUNTIME_SYNC_WORKFLOW.md"),
            "runtime_sync_flow": str(TOOLS_DIR / "runtime-sync-flow.sh"),
            "runtime_governance_status": str(TOOLS_DIR / "runtime-governance-status.sh"),
            "runtime_governance_flow": str(TOOLS_DIR / "runtime-governance-flow.sh"),
        },
        "required_docs": docs,
        "required_tools": tools,
        "canonical_meta_files": canonical_meta_files,
        "manifest_summary": manifest,
        "governance_summary": {
            "required_docs_present": required_docs_present,
            "required_tools_present": required_tools_present,
            "executable_tools_ok": executable_tools_ok,
            "canonical_meta_present_count": canonical_meta_present,
            "canonical_meta_total_count": len(canonical_meta_files),
            "manifest_healthy": manifest_healthy,
            "registry_healthy": registry_healthy,
        },
    }


def main() -> int:
    registry = build_registry()
    write_mode = write_json_if_needed(OUTFILE, registry)
    summary = registry["governance_summary"]
    manifest = registry["manifest_summary"]

    print("REGISTRY_OK")
    print(f"outfile: {OUTFILE}")
    print(f"write_mode: {write_mode}")
    print(f"required_docs_present: {bool_str(bool(summary['required_docs_present']))}")
    print(f"required_tools_present: {bool_str(bool(summary['required_tools_present']))}")
    print(f"executable_tools_ok: {bool_str(bool(summary['executable_tools_ok']))}")
    print(f"manifest_healthy: {bool_str(bool(summary['manifest_healthy']))}")
    print(f"manifest_in_sync: {bool_str(bool(manifest['in_sync']))}")
    print(f"canonical_meta_present_count: {summary['canonical_meta_present_count']}")
    print(f"canonical_meta_total_count: {summary['canonical_meta_total_count']}")
    print("REGISTRY_STATUS=HEALTHY" if bool(summary["registry_healthy"]) else "REGISTRY_STATUS=BLOCK")

    return 0 if bool(summary["registry_healthy"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
