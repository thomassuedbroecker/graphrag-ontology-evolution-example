#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
case "${1:-}" in
    --help|-h) printf 'Usage: %s\nShow process/container status and check application readiness.\n' "$0"; exit 0 ;;
    "") ;;
    *) fail "Unknown argument: $1" ;;
esac
[[ $# -eq 0 ]] || fail "Too many arguments."
for service in ollama mcp; do
    if managed_running "$service"; then log "$service: project process running";
    else log "$service: no running project process (may be externally managed)"; fi
done
require_command docker
select_docker
"${DOCKER[@]}" compose ps
load_settings
"$PYTHON" -m local_graphrag doctor
