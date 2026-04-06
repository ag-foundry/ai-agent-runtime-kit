#!/usr/bin/env python3
import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def base_env() -> dict:
    env = {}
    for key in ("HOME", "PATH", "LANG", "LC_ALL"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def send_message(proc: subprocess.Popen, message: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def read_message(proc: subprocess.Popen, timeout_s: float) -> dict:
    assert proc.stdout is not None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        ready, _, _ = select.select([proc.stdout], [], [], remaining)
        if not ready:
            continue
        line = proc.stdout.readline()
        if line == "":
            break
        line = line.strip()
        if not line:
            continue
        return json.loads(line)
    raise RuntimeError("timed out waiting for connector response")


def expect_result(message: dict, request_id: int) -> dict:
    if message.get("id") != request_id:
        raise RuntimeError(f"unexpected response id: {message.get('id')} != {request_id}")
    if "error" in message:
        raise RuntimeError(f"connector returned error: {message['error']}")
    return message["result"]


def terminate_process(proc: subprocess.Popen) -> str:
    stderr_text = ""
    if proc.stdin:
        proc.stdin.close()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    if proc.stderr:
        stderr_text = proc.stderr.read()
    return stderr_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--recall-query", default="ports xray 3x-ui fallback ssh")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(config_path)
    command = [config["command"], *config.get("args", [])]

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/home/agent/agents/mcp",
        env=base_env(),
        bufsize=1,
    )

    try:
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": config["protocolVersion"],
                "capabilities": {},
                "clientInfo": {
                    "name": "graphmem-readonly-smoke",
                    "version": "0.1.0"
                }
            }
        }
        send_message(proc, initialize_request)
        initialize_response = read_message(proc, timeout_s=5)
        initialize_result = expect_result(initialize_response, 1)
        write_json(out_dir / "initialize-response.json", initialize_response)

        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            },
        )

        send_message(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_response = read_message(proc, timeout_s=5)
        tools_result = expect_result(tools_response, 2)
        write_json(out_dir / "tools-list-response.json", tools_response)

        tool_names = [tool["name"] for tool in tools_result.get("tools", [])]
        if sorted(tool_names) != ["graph_recall", "graph_stats"]:
            raise RuntimeError(f"unexpected tool surface: {tool_names}")

        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "graph_stats",
                    "arguments": {}
                }
            },
        )
        graph_stats_response = read_message(proc, timeout_s=10)
        graph_stats_result = expect_result(graph_stats_response, 3)
        write_json(out_dir / "graph-stats-response.json", graph_stats_response)
        if graph_stats_result.get("isError"):
            raise RuntimeError("graph_stats returned isError=true")

        send_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "graph_recall",
                    "arguments": {"query": args.recall_query}
                }
            },
        )
        graph_recall_response = read_message(proc, timeout_s=10)
        graph_recall_result = expect_result(graph_recall_response, 4)
        write_json(out_dir / "graph-recall-response.json", graph_recall_response)
        if graph_recall_result.get("isError"):
            raise RuntimeError("graph_recall returned isError=true")

        summary = {
            "status": "ok",
            "config": str(config_path),
            "command": command,
            "protocol_version": initialize_result.get("protocolVersion"),
            "tool_names": tool_names,
            "graph_stats_text": graph_stats_result["content"][0]["text"],
            "graph_recall_query": args.recall_query,
            "graph_recall_preview": graph_recall_result["content"][0]["text"][:400],
        }
        write_json(out_dir / "smoke-summary.json", summary)
    finally:
        stderr_text = terminate_process(proc)
        (out_dir / "server-stderr.log").write_text(stderr_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
