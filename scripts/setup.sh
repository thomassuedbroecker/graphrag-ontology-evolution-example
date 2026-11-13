#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

offline=false
case "${1:-}" in
    --help|-h)
        printf 'Usage: %s [--offline]\nCreate .env and .venv; install locked Python dependencies.\nSet PYTHON_BIN to choose Python (3.11+). --offline verifies an existing installation.\n' "$0"
        exit 0 ;;
    --offline) offline=true ;;
    "") ;;
    *) fail "Unknown argument: $1" ;;
esac
[[ $# -le 1 ]] || fail "Too many arguments. Use --help."

if [[ ! -f .env ]]; then
    cp .env.example .env
    log "Created .env from .env.example."
fi

if [[ ! -x "$PYTHON" ]]; then
    "$offline" && fail "Offline startup requires an installed .venv; run setup.sh online first."
    python_bin="${PYTHON_BIN:-python3}"
    require_command "$python_bin"
    "$python_bin" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
    "$python_bin" -m venv "$ROOT/.venv"
fi

if "$offline"; then
    "$PYTHON" -c 'import local_graphrag, fastmcp, langchain, langchain_ollama, langchain_mcp_adapters, neo4j, dotenv'
elif [[ ! -f "$RUNTIME/setup.stamp" || pyproject.toml -nt "$RUNTIME/setup.stamp" ||
        requirements.lock -nt "$RUNTIME/setup.stamp" || ! -x .venv/bin/graphrag ]]; then
    log "Installing locked dependencies (first setup requires network access)."
    "$PYTHON" -m pip install -r requirements.lock
    "$PYTHON" -m pip install --no-deps -e .
    touch "$RUNTIME/setup.stamp"
fi
"$PYTHON" -m pip check
load_settings
"$PYTHON" -m local_graphrag validate
log "Python setup is ready. Configuration: $ROOT/.env"
