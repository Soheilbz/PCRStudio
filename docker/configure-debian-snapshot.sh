#!/bin/sh
set -eu

snapshot="${1:-}"
case "$snapshot" in
  20??????T??????Z) ;;
  *) echo "invalid Debian snapshot timestamp: $snapshot" >&2; exit 64 ;;
esac

# The Python base image is digest-pinned, but its Debian package indexes would
# otherwise come from the moving mirror at build time. Bind every package
# install in this image graph to one immutable snapshot instead.
rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources
printf '%s\n' \
  'Types: deb' \
  "URIs: https://snapshot.debian.org/archive/debian/$snapshot" \
  'Suites: trixie trixie-updates' \
  'Components: main' \
  'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
  '' \
  'Types: deb' \
  "URIs: https://snapshot.debian.org/archive/debian-security/$snapshot" \
  'Suites: trixie-security' \
  'Components: main' \
  'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
  > /etc/apt/sources.list.d/pcrstudio-snapshot.sources
printf '%s\n' \
  'Acquire::Check-Valid-Until "false";' \
  'Acquire::Retries "2";' \
  'Acquire::ConnectTimeout "15";' \
  'Acquire::http::Timeout "30";' \
  'Acquire::https::Timeout "30";' \
  'Dpkg::Use-Pty "0";' \
  > /etc/apt/apt.conf.d/80pcrstudio-snapshot
