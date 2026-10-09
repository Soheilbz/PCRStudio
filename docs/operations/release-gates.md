# Release gates and operational targets

Foundation runs locally with synthetic data. Do not purchase a server, process live payments or accept real scientific data as part of automated qualification.

Production targets (not current guarantees): availability 99.5% over rolling30days; normal API read p95<=300ms/write<=500ms; unexpected errors<=0.1% under the declared workload; composite RPO<=15min and full-host restoration RTO<=4h. Single VPS permits service recovery, not automatic whole-host failover.

100kDAU provisional model: 2 sessions/user/day *20 dynamic requests/session =4M requests/day; qualify500req/s for2h, 8h soak and750req/s overload/recovery. Include authentication, pagination/ACL queries, writes, bounded status polling and file-transfer bandwidth. Seed100k synthetic users/workspaces,500kprojects and1Mrun records when those modules exist. Scientific throughput is separately qualified. Do not throttle valid load to disguise capacity failures.

Production data volumes must be encrypted and access-controlled. Backups use pgBackRest base backups+WAL and restic immutable artifacts/configuration, encrypted independently with keys escrowed outside the host/repository. These controls protect offline media; authorized or compromised running-host administrators remain in the trust model.

Publish a composite restore point only after all referenced finalized artifacts and corresponding WAL are durably off-host. Suspend physical artifact garbage collection during snapshot and protect retained generations. Restore to that point; invalidate sessions, reconcile revocations/deletions and financial/provider state before reopening access or replaying outbox events. Production retention/deletion and recovery governance require their own accepted specification before real data launch.

Build once, promote immutable image digests, serialize migration/deployment, use additive backward-compatible schema changes. Roll back app images/configuration, not user writes. Separate migration/runtime DB identities. Non-root app processes, private database/cache networks, no Docker socket in app/worker containers. Liveness and readiness are distinct; unhealthy status alone does not restart Docker containers.

Structured logs, bounded metrics, audit events and alerts are required before public release; off-host probes detect host loss. No payloads, names, filenames, credentials, query strings or user/project IDs as metric labels. Optional production operations profile may use Prometheus/Alertmanager/host metrics with explicit retention.

External launch inputs: real VPS sizing/region/storage encryption, domain/TLS, SMTP, off-host backup destination/key custody, alert receiver, merchant country/payment provider/currency/pricing, actual retention/deletion terms and jurisdiction/customer requirements. Public GitHub checks need a configured authorized remote; local workflow files alone are not remote CI evidence.
