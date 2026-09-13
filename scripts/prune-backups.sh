#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="$root/.local/backups"
days="${PCRSTUDIO_BACKUP_RETENTION_DAYS:-14}"
max_gib="${PCRSTUDIO_BACKUP_TOTAL_MAX_GIB:-8}"
if [[ ! "$days" =~ ^[0-9]+$ ]] || (( days < 1 || days > 3650 )); then
  echo "PCRSTUDIO_BACKUP_RETENTION_DAYS must be an integer from 1 to 3650" >&2
  exit 2
fi
if [[ ! "$max_gib" =~ ^[1-8]$ ]]; then
  echo "PCRSTUDIO_BACKUP_TOTAL_MAX_GIB must be an integer from 1 to 8" >&2
  exit 2
fi
[[ -d "$backup_dir" ]] || exit 0

# Delete only the exact dump names PCRStudio generates. `find -P` and
# maxdepth=1 prevent symlink following or traversal outside this backup root.
find -P "$backup_dir" -maxdepth 1 -type f \
  \( -name 'pcrstudio-*.dump' -o -name 'pcrstudio-*.dump.sha256' \
     -o -name 'pre-deploy-*.dump' -o -name 'pre-deploy-*.dump.sha256' \
     -o -name 'pre-restore-*.dump' -o -name 'pre-restore-*.dump.sha256' \) \
  -mtime "+$days" -print -delete

# Remove only interrupted temporary outputs older than a day. A running
# backup writes *.partial and publishes the final name atomically afterward.
find -P "$backup_dir" -maxdepth 1 -type f \
  \( -name 'pcrstudio-*.dump.partial' -o -name 'pcrstudio-*.dump.sha256.partial' \
     -o -name 'pre-deploy-*.dump.partial' -o -name 'pre-deploy-*.dump.sha256.partial' \
     -o -name 'pre-restore-*.dump.partial' -o -name 'pre-restore-*.dump.sha256.partial' \) \
  -mmin +1440 -print -delete

max_bytes=$((max_gib * 1024 * 1024 * 1024))
mapfile -d '' -t records < <(
  find -P "$backup_dir" -maxdepth 1 -type f \
    \( -name 'pcrstudio-*.dump' -o -name 'pre-deploy-*.dump' -o -name 'pre-restore-*.dump' \) \
    -printf '%T@ %p\0' | sort -z -n -r
)
total=0
kept=0
for record in "${records[@]}"; do
  dump="${record#* }"
  checksum="$dump.sha256"
  [[ -f "$dump" && -f "$checksum" && ! -L "$dump" && ! -L "$checksum" ]] || continue
  dump_size="$(stat -c '%s' -- "$dump")"
  checksum_size="$(stat -c '%s' -- "$checksum")"
  pair_size=$((dump_size + checksum_size))
  if (( total + pair_size <= max_bytes )); then
    total=$((total + pair_size))
    kept=$((kept + 1))
  elif (( kept == 0 )); then
    # Keep the newest usable recovery point; backup-db.sh independently caps
    # one dump at the same configured bound.
    total=$pair_size
    kept=1
    echo "newest PCRStudio backup alone exceeds the configured total backup budget" >&2
    exit 1
  else
    printf 'removing old PCRStudio backup over total-size budget: %s\n' "$dump"
    rm -f -- "$dump" "$checksum"
  fi
done
printf 'PCRStudio backup retention: %s usable dump(s), %s bytes of %s-byte limit\n' \
  "$kept" "$total" "$max_bytes"
