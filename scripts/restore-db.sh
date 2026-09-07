#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
compose="$root/scripts/compose-linux.sh"
source_dump="${1:-}"
if [[ -z "$source_dump" || ! -f "$source_dump" || "$source_dump" != *.dump ]]; then
  echo "usage: $0 path/to/backup.dump" >&2
  exit 2
fi
source_dump="$(realpath -- "$source_dump")"

# A backup without its checksum is not a production restore artifact. An
# explicit break-glass variable exists for historical/manual dumps, but normal
# operations fail closed instead of silently restoring unverifiable bytes.
if [[ -f "$source_dump.sha256" ]]; then
  "$root/scripts/verify-backup.sh" "$source_dump"
elif [[ "${PCRSTUDIO_ALLOW_UNVERIFIED_RESTORE:-}" == "YES" ]]; then
  echo "warning: break-glass restore of a dump without a SHA-256 sidecar" >&2
else
  echo "refusing restore without $source_dump.sha256; set PCRSTUDIO_ALLOW_UNVERIFIED_RESTORE=YES only for a deliberate break-glass restore" >&2
  exit 2
fi

if [[ "${PCRSTUDIO_ALLOW_DESTRUCTIVE_RESTORE:-}" != "YES" ]]; then
  echo "refusing destructive restore; set PCRSTUDIO_ALLOW_DESTRUCTIVE_RESTORE=YES" >&2
  exit 2
fi

container_path="/tmp/pcrstudio-restore-$$.dump"
app_stopped=0
cleanup() {
  "$compose" exec -T db rm -f "$container_path" >/dev/null 2>&1 || true
  if [[ "$app_stopped" -eq 1 ]]; then
    echo "restore did not complete; application tiers remain stopped to prevent traffic against a partially restored database" >&2
    echo "after correcting the problem, run: $compose up -d --wait" >&2
  fi
}
trap cleanup EXIT

# Copy and parse the archive before taking the application offline. pg_restore
# --list validates the custom-format archive structure without mutating data.
"$compose" cp "$source_dump" "db:$container_path"
"$compose" exec -T db sh -ceu 'pg_restore --list "$1" >/dev/null' sh "$container_path"

# Quiesce every application writer before taking the rollback snapshot. This
# makes the pre-restore dump an exact rollback point: no application write can
# commit after the snapshot and disappear if rollback becomes necessary.
# PostgreSQL stays up because it performs both the snapshot and the restore.
"$compose" stop caddy web api runner
app_stopped=1

# Make a same-host emergency snapshot unless the operator explicitly opts out.
# A failed snapshot aborts before any destructive database operation; the
# application remains stopped so an operator cannot unknowingly serve traffic
# against an unprotected/partially restored database.
if [[ "${PCRSTUDIO_SKIP_PRE_RESTORE_BACKUP:-}" != "YES" ]]; then
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  "$root/scripts/backup-db.sh" "pre-restore-${stamp}-$$.dump"
fi

"$compose" exec -T db sh -ceu '
  db="${POSTGRES_DB:-pcrstudio}"
  user="${POSTGRES_USER:-pcr}"
  dropdb --if-exists --force -U "$user" "$db"
  createdb -U "$user" "$db"
  pg_restore -U "$user" -d "$db" --exit-on-error --no-owner --no-privileges "$1"
  psql -U "$user" -d "$db" -Atqc "SELECT count(*) FROM _sqlx_migrations" >/dev/null
' sh "$container_path"

# Bring a historical backup to the current schema and run post-migration
# ownership/invariant validation before exposing the application again.
"$compose" run --rm --no-deps migrate

# Start the complete topology and wait for its declared health checks. Bootstrap
# additionally requires /ready/scientific, so restore follows the same strict
# operational standard rather than accepting control-plane-only readiness.
"$compose" up -d --wait
"$compose" exec -T api curl --fail --silent http://127.0.0.1:8080/ready/scientific >/dev/null

app_stopped=0
echo "database restored, migrated, invariant-validated, and scientific readiness verified"
