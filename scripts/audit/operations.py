"""Operational policy, monitoring and recovery drift guards."""
from __future__ import annotations

import hashlib
import json
import tomllib

from .common import *  # noqa: F403


def _text(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        error(f"missing operations artifact: {rel}")
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def audit_operations_policy() -> None:
    policy_path = ROOT / "contracts/operations.toml"
    runtime_path = ROOT / "knowledge/runtime/operations.generated.json"
    alerts_path = ROOT / "ops/prometheus/pcrstudio-alerts.yml"
    docs_path = ROOT / "docs/OPERATIONS.md"
    if not policy_path.is_file():
        error("missing canonical operations policy")
        return
    try:
        with policy_path.open("rb") as handle:
            policy = tomllib.load(handle)
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error(f"operations policy/projection cannot be parsed: {exc}")
        return

    digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    if runtime.get("canonical_sha256") != digest:
        error("generated operations runtime projection is stale")
    backup = policy.get("backup") or {}
    storage = policy.get("storage") or {}
    bootstrap = _text("scripts/bootstrap-linux.py")
    guard = _text("scripts/storage-guard.py")
    prune = _text("scripts/prune-backups.sh")
    docs = _text("docs/OPERATIONS.md")
    storage_docs = _text("docs/DOCKER-STORAGE.md")
    if runtime.get("storage") != storage:
        error("generated operations runtime storage policy is stale")
    if storage.get("mode") != "dedicated-host-budget" or storage.get("application_budget_gib") != 20:
        error("operations storage policy no longer enforces the 20 GiB dedicated-host budget")
    for marker in (
        "verify_managed_storage_layout",
        "containerd_root_dir",
    ):
        if marker not in bootstrap:
            error(f"Linux bootstrap lost managed-storage preflight marker: {marker}")
    if "managed_usage_bytes" not in guard:
        error("storage guard lost its allocated-byte usage measurement")
    for marker in (
        "20 GiB managed application budget",
        "containerd",
        "8 GiB free",
        "emergency floor",
    ):
        if marker not in storage_docs:
            error(f"Docker storage runbook lost hard-storage marker: {marker}")
    for marker in (
        str(backup.get("backup_on_calendar") or ""),
        str(backup.get("backup_randomized_delay") or ""),
        str(backup.get("restore_drill_on_calendar") or ""),
        str(backup.get("restore_drill_randomized_delay") or ""),
    ):
        if not marker or marker not in bootstrap:
            error(f"Linux backup automation drifted from operations policy: {marker!r}")
    retention = int(backup.get("default_retention_days") or 0)
    if f'PCRSTUDIO_BACKUP_RETENTION_DAYS:-{retention}' not in prune:
        error("backup-prune default retention drifted from operations policy")
    if f'PCRSTUDIO_BACKUP_TOTAL_MAX_GIB:-{int(storage.get("backup_total_max_gib") or 0)}' not in prune:
        error("backup total-size cap drifted from operations storage policy")
    backup_script = _text("scripts/backup-db.sh")
    if f'PCRSTUDIO_BACKUP_MAX_GIB:-{int(storage.get("backup_file_max_gib") or 0)}' not in backup_script:
        error("per-file backup cap drifted from operations storage policy")
    for marker in (
        f"RPO: {int(backup.get('target_rpo_hours') or 0)} hours",
        f"RTO: {int(backup.get('target_rto_hours') or 0)} hours",
        f"{retention} days",
        "host-loss disaster recovery",
        "off-host",
    ):
        if marker not in docs:
            error(f"operations runbook lost recovery marker: {marker}")

    diagnostics = _text("crates/pcr-server/src/diagnostics.rs")
    alerts = _text("ops/prometheus/pcrstudio-alerts.yml")
    seen: set[str] = set()
    for row in policy.get("alert") or []:
        alert_id = str(row.get("id") or "")
        if not alert_id or alert_id in seen:
            error(f"operations policy has invalid/duplicate alert id: {alert_id!r}")
            continue
        seen.add(alert_id)
        if f"alert: {alert_id}" not in alerts:
            error(f"generated Prometheus rules lost alert: {alert_id}")
        runbook = str(row.get("runbook") or "")
        if f"### {runbook}" not in docs:
            error(f"operations runbook lost alert section: {runbook}")
        for metric in row.get("metrics") or []:
            if str(metric) not in diagnostics:
                error(f"operations alert references metric not emitted by API: {metric}")
            if str(metric) not in str(row.get("expr") or ""):
                error(f"operations alert declares metric absent from its expression: {alert_id}: {metric}")

    for rel, markers in {
        "scripts/backup-db.sh": ("umask 077", "sha256sum", "chmod 0600"),
        "scripts/verify-backup.sh": ("exactly one non-empty record", "actual=\"$(sha256sum"),
        "scripts/backup-restore-drill.sh": ("unvalidated_constraints", "_sqlx_migrations"),
    }.items():
        source = _text(rel)
        for marker in markers:
            if marker not in source:
                error(f"backup/restore hardening marker missing from {rel}: {marker}")
