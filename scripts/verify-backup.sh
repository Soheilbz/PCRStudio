#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Verify the bytes of exactly the dump path supplied by the operator. We do not
# use `sha256sum -c` here because checksum sidecars carry a filename; trusting
# that filename can accidentally validate a different dump than the one about
# to be restored.
dump="${1:-}"
if [[ -z "$dump" || ! -f "$dump" || "$dump" != *.dump ]]; then
  echo "usage: $0 path/to/backup.dump" >&2
  exit 2
fi
sidecar="$dump.sha256"
if [[ ! -f "$sidecar" ]]; then
  echo "missing checksum sidecar: $sidecar" >&2
  exit 2
fi

# Accept the conventional sha256sum sidecar format for compatibility, but use
# only its digest field and bind that digest to the caller-selected dump.
IFS=' ' read -r expected _rest < "$sidecar" || true
if [[ ! "$expected" =~ ^[0-9a-f]{64}$ ]]; then
  echo "invalid SHA-256 sidecar: $sidecar" >&2
  exit 2
fi
# Reject additional non-empty records so a hand-edited/multi-file sidecar is
# never ambiguous.
if [[ "$(grep -cve '^[[:space:]]*$' "$sidecar")" -ne 1 ]]; then
  echo "checksum sidecar must contain exactly one non-empty record: $sidecar" >&2
  exit 2
fi
actual="$(sha256sum -- "$dump" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "SHA-256 mismatch for $dump" >&2
  echo "expected: $expected" >&2
  echo "actual:   $actual" >&2
  exit 1
fi
printf 'SHA-256 verified: %s\n' "$dump"
