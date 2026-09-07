#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
compose="$root/scripts/compose-linux.sh"
name="${1:-pcrstudio-$(date -u +%Y%m%d-%H%M%S)-$$.dump}"
backup_dir="$root/.local/backups"
destination="$backup_dir/$name"
checksum="$destination.sha256"
container_path="/tmp/$name"

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

cleanup() {
  "$compose" exec -T db rm -f "$container_path" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Keep custom-format bytes inside the container until Compose copies them out.
dump_command='pg_dump -U "${POSTGRES_USER:-pcr}" -Fc -f "'$container_path'" "${POSTGRES_DB:-pcrstudio}"'
"$compose" exec -T db sh -ceu "$dump_command"
"$compose" cp "db:$container_path" "$destination"
[[ -s "$destination" ]] || { echo "backup copy is empty" >&2; exit 1; }
chmod 0600 "$destination"
(
  cd "$backup_dir"
  sha256sum "$name" > "$name.sha256"
)
chmod 0600 "$checksum"
echo "database backup written to $destination"
echo "checksum written to $checksum"
