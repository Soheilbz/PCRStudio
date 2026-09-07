#!/bin/sh
set -eu

TOOLCHAIN_ENV=/opt/pcrstudio/tools/toolchain.env
if [ ! -r "$TOOLCHAIN_ENV" ]; then
  echo "fatal: canonical scientific toolchain environment is missing: $TOOLCHAIN_ENV" >&2
  exit 70
fi

# The file is generated during the image build from hash-verified artifacts and
# contains only simple KEY=VALUE assignments under /opt/pcrstudio. Export them
# before starting the Rust server. Deployment-specific database variables and
# the approved scientific-freeze digest are supplied by Compose and are not
# overwritten because they are intentionally absent from an ordinary build.
set -a
# shellcheck disable=SC1091
. "$TOOLCHAIN_ENV"
set +a

: "${HOME:=/tmp/pcrstudio-home}"
: "${MPLCONFIGDIR:=/tmp/pcrstudio-matplotlib}"
export HOME MPLCONFIGDIR
mkdir -p "$HOME" "$MPLCONFIGDIR"

exec "$@"
