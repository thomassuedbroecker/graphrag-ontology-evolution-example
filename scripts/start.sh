#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

offline=false
case "${1:-}" in
    --help|-h)
        printf 'Usage: %s [--offline]\nSet up Python, start Rancher Desktop (macOS), Neo4j, Ollama and MCP, then import data.\n--offline skips package/model/image downloads and requires preloaded artifacts.\n' "$0"
        exit 0 ;;
    --offline) offline=true ;;
    "") ;;
    *) fail "Unknown argument: $1" ;;
esac
[[ $# -le 1 ]] || fail "Too many arguments. Use --help."

mkdir "$RUNTIME/start.lock" 2>/dev/null || fail "Another lifecycle command is active. If interrupted, remove the empty .runtime/start.lock directory after checking processes."
cleanup() {
    local code=$?
    rmdir "$RUNTIME/start.lock"
    if [[ "$code" -ne 0 ]]; then
        printf '[graphrag] Startup failed; inspect .runtime/*.log. Use ./scripts/status.sh or ./scripts/stop.sh to manage any services already started.\n' >&2
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for command in docker ollama curl; do require_command "$command"; done
if "$offline"; then bash "$ROOT/scripts/setup.sh" --offline; else bash "$ROOT/scripts/setup.sh"; fi
load_settings

select_docker
if ! "${DOCKER[@]}" info >/dev/null 2>&1; then
    if [[ "$(uname -s)" == Darwin ]]; then
        log "Opening Rancher Desktop; waiting for its Docker engine."
        open -a "Rancher Desktop"
    else
        log "Waiting for Docker. Start Rancher Desktop with the Moby engine."
    fi
    ready=false
    for ((i=0; i<90; i++)); do
        select_docker
        if "${DOCKER[@]}" info >/dev/null 2>&1; then ready=true; break; fi
        sleep 2
    done
    "$ready" || fail "Docker is unavailable. Select dockerd (Moby) in Rancher Desktop."
fi
"${DOCKER[@]}" compose version >/dev/null

if ! http_ready "$OLLAMA_BASE_URL/api/tags"; then
    require_command lsof
    ollama_port="$("$PYTHON" -c 'from urllib.parse import urlparse; import os; print(urlparse(os.environ["OLLAMA_BASE_URL"]).port or 80)')"
    if lsof -nP -iTCP:"$ollama_port" -sTCP:LISTEN >/dev/null 2>&1; then
        fail "Port $ollama_port is occupied but Ollama is not responding."
    fi
    log "Starting local Ollama."
    export OLLAMA_NO_CLOUD=1
    start_managed ollama "$(command -v ollama)" serve
    wait_http "$OLLAMA_BASE_URL/api/tags" Ollama
else
    log "Using the existing Ollama server."
fi
for model in "$OLLAMA_CHAT_MODEL" "$OLLAMA_EMBED_MODEL"; do
    if ! ollama show "$model" >/dev/null 2>&1; then
        "$offline" && fail "Model $model is missing. Download it with ollama pull before offline startup."
        log "Downloading local model $model."
        ollama pull "$model"
    fi
done

log "Starting Neo4j."
if "$offline"; then
    "${DOCKER[@]}" compose up -d --wait --wait-timeout 180 --pull never
else
    "${DOCKER[@]}" compose up -d --wait --wait-timeout 180
fi
"$PYTHON" -m local_graphrag ingest --apply --skip-if-migrated

if ! managed_running mcp; then
    require_command lsof
    mcp_port="$("$PYTHON" -c 'from urllib.parse import urlparse; import os; print(urlparse(os.environ["MCP_URL"]).port or 80)')"
    if lsof -nP -iTCP:"$mcp_port" -sTCP:LISTEN >/dev/null 2>&1; then
        fail "MCP port $mcp_port is occupied by an unmanaged process. Stop it or change MCP_URL."
    fi
    log "Starting the read-only MCP server."
    start_managed mcp "$PYTHON" -m local_graphrag serve
fi
wait_http "$MCP_HEALTH_URL" MCP 30
"$PYTHON" -m local_graphrag doctor
log "Ready. Neo4j: http://localhost:7474 | MCP: $MCP_URL"
log "Ask: ./scripts/ask.sh 'Which destination can Galaxium Travels customers visit?'"
log "Logs: $RUNTIME | Stop: ./scripts/stop.sh"
