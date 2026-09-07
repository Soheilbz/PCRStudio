#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
: "${PCR_DEV_PASSWORD:?set PCR_DEV_PASSWORD before creating the development user}"
cd "$root"
exec node scripts/dev-user.mjs "$@"
