#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
compose="$root/scripts/compose-linux.sh"
stamp="$(date -u +%Y%m%d-%H%M%S)-$$"
name="restore-drill-$stamp.dump"
backup="$root/.local/backups/$name"
drill_db="pcrstudio_restore_drill_${stamp//-/_}"
container_dump="/tmp/$name"
cleanup() {
  "$compose" exec -T db sh -ceu 'dropdb --if-exists --force -U "${POSTGRES_USER:-pcr}" "$1"' sh "$drill_db" >/dev/null 2>&1 || true
  "$compose" exec -T db rm -f "$container_dump" >/dev/null 2>&1 || true
  rm -f -- "$backup" "$backup.sha256"
}
trap cleanup EXIT

"$root/scripts/backup-db.sh" "$name"
"$root/scripts/verify-backup.sh" "$backup"
"$compose" cp "$backup" "db:$container_dump"
"$compose" exec -T db sh -ceu '
  user="${POSTGRES_USER:-pcr}"; db="$1"; dump="$2"
  dropdb --if-exists --force -U "$user" "$db"
  createdb -U "$user" "$db"
  pg_restore -U "$user" -d "$db" --exit-on-error --no-owner --no-privileges "$dump"
  migrations=$(psql -U "$user" -d "$db" -Atqc "SELECT count(*) FROM _sqlx_migrations")
  test "$migrations" -gt 0
  tables=$(psql -U "$user" -d "$db" -Atqc "SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\''")
  test "$tables" -gt 0
  unvalidated=$(psql -U "$user" -d "$db" -Atqc "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = '\''public'\'' AND NOT c.convalidated")
  test "$unvalidated" -eq 0
  echo "restore drill verified: migrations=$migrations tables=$tables unvalidated_constraints=$unvalidated"
' sh "$drill_db" "$container_dump"
