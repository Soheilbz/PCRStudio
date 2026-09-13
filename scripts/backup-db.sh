#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
compose="$root/scripts/compose-linux.sh"
name="${1:-pcrstudio-$(date -u +%Y%m%d-%H%M%S)-$$.dump}"
backup_dir="$root/.local/backups"
destination="$backup_dir/$name"
checksum="$destination.sha256"
partial="$destination.partial"
max_gib="${PCRSTUDIO_BACKUP_MAX_GIB:-4}"

if [[ ! "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.dump$ ]]; then
  echo "backup name must contain only safe characters and end in .dump" >&2
  exit 2
fi

mkdir -p "$backup_dir"
chmod 0700 "$backup_dir"
if [[ -e "$destination" || -e "$checksum" ]]; then
  echo "refusing to overwrite existing backup/checksum: $destination" >&2
  exit 2
fi
if [[ ! "$max_gib" =~ ^[1-4]$ ]]; then
  echo "PCRSTUDIO_BACKUP_MAX_GIB must be an integer from 1 to 4" >&2
  exit 2
fi
if [[ -e "$partial" || -e "$checksum.partial" ]]; then
  echo "refusing to overwrite an interrupted backup: $partial" >&2
  exit 2
fi

cleanup() {
  rm -f -- "$partial" "$checksum.partial"
}
trap cleanup EXIT

# Stream directly to a bounded host file. This avoids an unbounded temporary
# dump in Docker's writable layer and retains no duplicate inside the database
# container. RLIMIT_FSIZE provides a kernel-enforced per-backup ceiling.
python3 "$root/scripts/storage-guard.py" --preflight-write-gib "$max_gib"
ulimit -f "$((max_gib * 1024 * 1024 * 1024 / 512))"
"$compose" exec -T db sh -ceu \
  'exec pg_dump -U "${POSTGRES_USER:-pcr}" -Fc "${POSTGRES_DB:-pcrstudio}"' \
  > "$partial"
[[ -s "$partial" ]] || { echo "backup stream is empty" >&2; exit 1; }
chmod 0600 "$partial"
mv -- "$partial" "$destination"
(
  cd "$backup_dir"
  sha256sum "$name" > "$name.sha256.partial"
)
chmod 0600 "$checksum.partial"
mv -- "$checksum.partial" "$checksum"
echo "database backup written to $destination"
echo "checksum written to $checksum"
