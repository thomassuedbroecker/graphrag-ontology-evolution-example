#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
case "${1:-}" in
    --help|-h)
        printf 'Usage: %s [--services]\nRun unit tests. --services also runs data-modifying tests against dedicated local services.\n' "$0"
        exit 0 ;;
    --services) export RUN_SERVICE_TESTS=1 ;;
    "") ;;
    *) fail "Unknown argument: $1" ;;
esac
[[ $# -le 1 ]] || fail "Too many arguments."
[[ -x "$PYTHON" ]] || fail "Run ./scripts/setup.sh first."
exec "$PYTHON" -m unittest discover -s tests -v
