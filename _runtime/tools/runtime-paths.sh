#!/usr/bin/env bash

runtime_tools_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

runtime_repo_root() {
  if [[ -n "${AGENT_REPO_ROOT:-}" ]]; then
    printf '%s\n' "$AGENT_REPO_ROOT"
    return
  fi

  local tools_dir
  tools_dir="$(runtime_tools_dir)"
  cd "$tools_dir/../.." && pwd
}

runtime_bin_dir() {
  if [[ -n "${AGENT_BIN_DIR:-}" ]]; then
    printf '%s\n' "$AGENT_BIN_DIR"
    return
  fi

  printf '%s\n' "/home/agent/bin"
}
