#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Shared helpers; entry points enable strict mode before sourcing this file.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUNTIME="$ROOT/.runtime"
PYTHON="$ROOT/.venv/bin/python"
mkdir -p "$RUNTIME"

log() { printf '[graphrag] %s\n' "$*"; }
fail() { printf '[graphrag] ERROR: %s\n' "$*" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || fail "Install $1 before continuing."; }

load_settings() {
    [[ -x "$PYTHON" ]] || fail "Run ./scripts/setup.sh first."
    local config line key
    config="$("$PYTHON" - <<'PY'
from local_graphrag.config import Settings
from urllib.parse import urlparse
s = Settings.load()
for key, value in {
    "OLLAMA_BASE_URL": s.ollama.rstrip("/"),
    "OLLAMA_CHAT_MODEL": s.chat_model,
    "OLLAMA_EMBED_MODEL": s.embed_model,
    "MCP_URL": s.mcp_url,
    "MCP_HEALTH_URL": urlparse(s.mcp_url)._replace(path="/health", query="", fragment="").geturl(),
    "OLLAMA_HOST": urlparse(s.ollama).netloc,
}.items():
    if "\n" in value or "\r" in value:
        raise ValueError(f"Invalid multiline setting: {key}")
    print(f"{key}={value}")
PY
    )" || fail "Invalid configuration; check .env."
    # Parse values as data; never execute .env as shell code.
    while IFS= read -r line; do
        key="${line%%=*}"
        export "$key=${line#*=}"
    done <<< "$config"
}

select_docker() {
    DOCKER=(docker)
    if [[ -z "${DOCKER_CONTEXT:-}" && -z "${DOCKER_HOST:-}" ]] &&
        docker context inspect rancher-desktop >/dev/null 2>&1; then
        DOCKER=(docker --context rancher-desktop)
    fi
}

http_ready() { curl --noproxy '*' --fail --silent --max-time 2 "$1" >/dev/null 2>&1; }

wait_http() {
    local url="$1" label="$2" attempts="${3:-60}" i
    for ((i=0; i<attempts; i++)); do
        if http_ready "$url"; then return 0; fi
        sleep 2
    done
    fail "$label did not become ready at $url. Check $RUNTIME/*.log."
}

# Pair PID with its process start time so stale PID files cannot target a reused PID.
managed_running() {
    local service="$1" pid saved actual
    [[ -f "$RUNTIME/$service.pid" ]] || return 1
    { IFS= read -r pid; IFS= read -r saved; } < "$RUNTIME/$service.pid" || return 1
    [[ "$pid" =~ ^[0-9]+$ && -n "$saved" ]] || return 1
    actual="$(ps -p "$pid" -o lstart= 2>/dev/null)" || return 1
    [[ "$actual" == "$saved" ]]
}

start_managed() {
    local service="$1" pid started
    shift
    if managed_running "$service"; then
        log "$service is already managed by this project."
        return
    fi
    nohup "$@" >> "$RUNTIME/$service.log" 2>&1 < /dev/null &
    pid=$!
    if ! started="$(ps -p "$pid" -o lstart=)"; then
        kill "$pid" 2>/dev/null || true
        fail "Could not track $service; stopped the process just launched."
    fi
    printf '%s\n%s\n' "$pid" "$started" > "$RUNTIME/$service.pid"
}

stop_managed() {
    local service="$1" pid i
    if ! managed_running "$service"; then
        log "$service has no running process owned by this project."
        return
    fi
    IFS= read -r pid < "$RUNTIME/$service.pid"
    kill "$pid"
    for ((i=0; i<30; i++)); do
        if ! managed_running "$service"; then
            log "Stopped $service."
            return
        fi
        sleep 1
    done
    fail "$service did not stop within 30 seconds; inspect PID $pid."
}
