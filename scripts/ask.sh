#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
if [[ $# -eq 0 || "${1:-}" == --help || "${1:-}" == -h ]]; then
    printf 'Usage: %s "Your question"\nAsk the local agent after start.sh completes.\n' "$0"
    exit 0
fi
load_settings
exec "$PYTHON" -m local_graphrag ask "$*"
