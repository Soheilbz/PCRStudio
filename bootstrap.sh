#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
if [ "${1:-}" = "--local" ]; then
    shift
    exec python3 scripts/bootstrap-local.py "$@"
fi
exec python3 scripts/bootstrap-linux.py --install-system-deps "$@"
