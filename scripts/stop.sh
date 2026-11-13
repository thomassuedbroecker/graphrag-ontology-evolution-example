#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
case "${1:-}" in
    --help|-h)
        printf 'Usage: %s [--delete-data]\nStop project-managed MCP/Ollama and the Compose services. Preserve Neo4j data.\n--delete-data also deletes the demo Neo4j volume (all graph data and revisions).\nExisting external Ollama servers and Rancher Desktop remain running.\n' "$0"
        exit 0 ;;
    --delete-data) delete_data=true ;;
    "") ;;
    *) fail "Unknown argument: $1" ;;
esac
delete_data="${delete_data:-false}"
[[ $# -le 1 ]] || fail "Too many arguments."
mkdir "$RUNTIME/start.lock" 2>/dev/null || fail "Another lifecycle command is active."
trap 'rmdir "$RUNTIME/start.lock"' EXIT
stop_managed mcp
stop_managed ollama
require_command docker
select_docker
if "$delete_data"; then
    "${DOCKER[@]}" compose down --volumes
    log "Stopped and deleted the demo Neo4j volume. The next start.sh imports a fresh baseline."
else
    "${DOCKER[@]}" compose down
    log "Stopped. Neo4j data is preserved."
fi
