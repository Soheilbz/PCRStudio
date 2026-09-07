#!/usr/bin/env sh
set -eu
if [ "$#" -lt 1 ]; then echo "usage: $0 <archive.zip> [identity-token]" >&2; exit 2; fi
command -v cosign >/dev/null 2>&1 || { echo "cosign is required" >&2; exit 127; }
archive=$1
[ -f "$archive" ] || { echo "archive not found: $archive" >&2; exit 2; }
# Keyless signing is intentionally interactive/CI-identity dependent. PCRStudio
# never ships a private signing key or fabricates a signature in the source tree.
cosign sign-blob --yes --bundle "${archive}.cosign.bundle.json" "$archive"
