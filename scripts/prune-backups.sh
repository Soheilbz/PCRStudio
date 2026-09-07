#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="$root/.local/backups"
days="${PCRSTUDIO_BACKUP_RETENTION_DAYS:-14}"
if [[ ! "$days" =~ ^[0-9]+$ ]] || (( days < 1 || days > 3650 )); then
  echo "PCRSTUDIO_BACKUP_RETENTION_DAYS must be an integer from 1 to 3650" >&2
  exit 2
fi
[[ -d "$backup_dir" ]] || exit 0
# Delete only the two exact artifact shapes this project creates. Never follow
# symlinks and never traverse outside the canonical backup directory.
find -P "$backup_dir" -maxdepth 1 -type f \
  \( -name 'pcrstudio-*.dump' -o -name 'pcrstudio-*.dump.sha256' \
     -o -name 'pre-deploy-*.dump' -o -name 'pre-deploy-*.dump.sha256' \
     -o -name 'pre-restore-*.dump' -o -name 'pre-restore-*.dump.sha256' \) \
  -mtime "+$days" -print -delete
