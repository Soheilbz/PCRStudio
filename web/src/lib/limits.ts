/**
 * Canonical transport and persistence ceilings.
 *
 * Values are generated from `contracts/foundation.toml`; this module keeps the
 * ergonomic public imports and display helper without restating any number.
 */
export {
  MAX_ACCOUNT_IMPORT_BYTES,
  MAX_ACTION_BYTES,
  MAX_BACKUP_DOCUMENT_BYTES,
  MAX_HTTP_BODY_BYTES,
  MAX_PROJECT_NOTES_BYTES,
  MAX_PROJECT_SETTINGS_BYTES,
  MAX_RUN_DOCUMENT_BYTES,
  MAX_RUN_JOB_AUX_BYTES,
  MAX_RUN_JOB_REQUEST_BYTES,
  MAX_RUN_LABEL_BYTES,
  MAX_SEQUENCE_BYTES,
  MAX_WORKER_STDERR_BYTES,
  MAX_WORKER_STDOUT_BYTES,
} from "./contracts/limits.generated";

export function inMegabytes(bytes: number): string {
  return `${Math.round(bytes / 1024 / 1024)} MB`;
}
