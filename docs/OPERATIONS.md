# PCRStudio CURRENT operations runbook

Docker build storage is bounded separately in
[`DOCKER-STORAGE.md`](DOCKER-STORAGE.md). The supported bootstrap uses the
dedicated `pcrstudio` BuildKit builder with an 8 GB cache ceiling and performs
scoped cleanup on both success and failure; it never performs a daemon-wide
prune that could remove another project's images.

This runbook describes the operational contract shipped with the source tree. The machine-readable authority is `contracts/operations.toml`; Prometheus-compatible alert rules are generated at `ops/prometheus/pcrstudio-alerts.yml` and the normalized runtime projection is `knowledge/runtime/operations.generated.json`.

## Recovery objectives

The default Linux bootstrap installs a database backup every day at `02:20 UTC` with up to `10m` randomized delay, retains scheduled backups for **14 days**, and executes a restore drill every Sunday at `03:20 UTC` with up to `15m` randomized delay. The explicit host-local targets are:

- **RPO: 25 hours.** This includes the daily cadence plus randomized delay rather than claiming an exact 24-hour bound.
- **RTO: 2 hours.** This is the operator target for restoring a verified dump on a healthy, provisioned host; the restore-drill service itself has a two-hour timeout.

Backups created by the bundled scripts are **host-local**. They protect against database/schema/application failure on that host; they do **not** constitute host-loss disaster recovery. A production operator that needs host-loss recovery must replicate verified `.dump` and `.dump.sha256` pairs to independently administered off-host storage and test restoration from that copy. PCRStudio intentionally does not embed cloud credentials or pretend that a local directory is an off-site backup.

Before destructive restore, use `scripts/verify-backup.sh` on the exact selected dump. `scripts/restore-db.sh` takes a pre-restore rollback snapshot unless the operator explicitly uses its documented emergency override. `scripts/backup-restore-drill.sh` restores into a temporary database and rejects missing migration history, an empty public schema, or unvalidated public constraints.

## Monitoring contract

`/operator/metrics` is disabled unless the operator token is configured. Scrapers must send the token in the `x-pcrstudio-operator-token` header over the internal/operator path; do not expose this endpoint publicly and do not put the token in a URL. The surface deliberately contains no user identifiers, project names, sequences, request bodies, or database credentials.

Import `ops/prometheus/pcrstudio-alerts.yml` into a Prometheus-compatible monitoring system. Thresholds are source-controlled in `contracts/operations.toml`; edit the authority and regenerate rather than hand-editing the YAML.

For incident correlation, use the API request ID plus structured JSON logs. Durable queue/runner metrics come from PostgreSQL and therefore describe the actual external-runner topology rather than the API process's interactive worker gate.

## Alert response

### runner-unavailable

`PCRStudioNoFreshDurableRunner` means PostgreSQL has no fresh durable-runner heartbeat for at least two minutes. Check the `runner` container health, its JSON logs, database connectivity, scientific-toolchain readiness and build/fingerprint compatibility. Do not clear or manually rewrite job leases as a first response; restart/repair the runner and allow the durable lease/recovery path to reclaim work.

### durable-queue-stalled

`PCRStudioDurableQueueStalled` means at least one durable job has waited more than two minutes and the condition persisted for five minutes. First verify that a fresh runner exists and has nonzero advertised capacity. Then inspect runner failures/timeouts and database latency. Increase concurrency only after confirming CPU/RAM/native-tool capacity; queue pressure is not evidence that unbounded parallelism is safe.

### durable-queue-pressure

`PCRStudioDurableQueuePressure` means queued durable work exceeds eight jobs per advertised fresh runner capacity for ten minutes. Confirm this is real demand rather than a stuck runner. Scale runner capacity or reduce upstream submission only within the canonical worker/resource limits; do not bypass weighted scheduling.

### database-pool-saturation

`PCRStudioDatabasePoolSaturation` means more than 90% of API PostgreSQL pool connections are checked out for five minutes. Check database latency, blocked/long transactions and host resource pressure before increasing pool size. Pool limits must remain within PostgreSQL `max_connections` headroom for the API, runner, migration and operator connections.

### api-server-errors

`PCRStudioAPIServerErrorBurst` means five or more API 5xx responses occurred inside five minutes and persisted. Correlate request IDs in JSON logs, check database/readiness state and determine whether failures are transport/persistence or interactive scientific-worker failures. Never enable payload logging to diagnose this; sequence and project data are intentionally excluded from telemetry.

### interactive-worker-failures

`PCRStudioInteractiveWorkerFailures` covers repeated failures of the API's latency-sensitive scientific worker path. Check strict toolchain readiness, external-reference configuration, bounded subprocess termination and worker stderr summaries. Durable design jobs are a separate runner path; do not infer durable-runner health from this alert alone.

## Backup and restore checks

On systemd hosts, verify the automation with `systemctl list-timers pcrstudio-backup.timer pcrstudio-restore-drill.timer`. Review failed services with `systemctl status` and `journalctl -u`. A successful timer invocation is not enough for disaster recovery: periodically confirm that the independently stored off-host copy has the same SHA-256 sidecar and perform a restoration from the off-host bytes.

Before application promotion, the canonical host gate remains:

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

Source/static qualification, generated alert rules and a successful local restore drill do not substitute for native scientific, Docker, PostgreSQL and functional acceptance on the Linux qualification host.

## OCI registry failure diagnosis

Production bootstrap owns the OCI dependency gate. Before BuildKit starts, it
checks system DNS for `auth.docker.io`, `registry-1.docker.io`, and
`production.cloudfront.docker.com`, then pulls the exact digest-pinned
references discovered in `compose.yaml`, `docker/api.Dockerfile`, and
`docker/web.Dockerfile`. It uses the configured Docker credential helper and
never weakens TLS, changes an image identity, or falls back to a tag. Only
timeouts and comparable transport failures are retried, with a finite
exponential backoff. Authentication, rate-limit, TLS, DNS, and digest/pin
errors stop immediately with a distinct diagnosis.

When this gate reports DNS failure, inspect both the resolver and the active
network path:

```bash
resolvectl status
resolvectl query auth.docker.io
resolvectl query registry-1.docker.io
ip -4 route
ip -6 route
docker info
```

On NetworkManager hosts, disable broken DHCP-provided DNS on the active
connection and set the network-approved resolvers persistently, then reapply
the device. If IPv6 has no default route, IPv4 must still resolve and reach the
registry; this is reported as an address-family condition, not hidden as an
authentication failure. If the network requires a proxy, configure the Docker
daemon's proxy drop-in and restart Docker; shell proxy variables alone do not
configure daemon pulls. For private or rate-limited registries, use `docker
login` and a credential helper. Never copy credentials into the repository,
`.env`, image layers, or build arguments.

The web dependency boundary is separate from Docker Hub: this host can reach
the official `registry.npmjs.com` endpoint while its Docker bridge times out at
the Cloudflare-backed `registry.npmjs.org` hostname. The repository therefore
uses the official alternate npm endpoint, the exact pnpm `11.26.0`
package-manager version with Corepack signature/integrity checks, frozen-lockfile
integrity checks and bounded fetch retries. Only those
dependency-fetch build steps use the dedicated builder's `network.host`
entitlement; it does not affect the runtime network or image identity.

## GitHub-to-server deployment

Production does not follow `main` or execute arbitrary branch contents. The
`production-deploy.yml` workflow deploys only a published `CURRENT-*` release
tag, or the same exact tag when an operator starts the workflow manually. The
GitHub `production` environment should require approval and should contain
these environment secrets:

- `PCRSTUDIO_PRODUCTION_DOMAIN`
- `PCRSTUDIO_PRODUCTION_DATABASE_ID`
- `PCRSTUDIO_PRODUCTION_SSH_HOST`
- `PCRSTUDIO_PRODUCTION_SSH_USER`
- `PCRSTUDIO_PRODUCTION_SSH_PRIVATE_KEY`
- `PCRSTUDIO_PRODUCTION_SSH_KNOWN_HOSTS`

The server is not granted a GitHub write token and does not poll GitHub. GitHub
Actions builds the qualified runtime image set on the ephemeral runner,
transfers the verified release archive and those images over host-key-pinned
SSH, runs the repository bootstrap in explicit control-plane mode, and checks
readiness on the server. The server still verifies pinned base images, image
presence, migrations, public readiness and bounded Docker cleanup. Scientific
readiness and the durable runner remain intentionally withheld until the
approved reference database is supplied.

For several applications on one host, one host-level Caddy/Traefik instance
must own ports 80/443. Each application gets its own Compose project, internal
networks, volumes, secrets and resource limits. PCRStudio's default Compose
file owns 80/443 for a single-application host; a multi-application host must
use a reviewed shared-edge overlay before production deployment. Do not
publish PostgreSQL, API or runner ports directly.

## Runtime configuration reference

The following settings are operator controls rather than end-user options.
`PCR_MAX_QUEUED_WORKERS` bounds callers waiting for a worker permit; it defaults
to 256 and accepts 0–1024. `PCR_CORS_ORIGINS` is a comma-separated allow-list of
exact `http`/`https` browser origins. It defaults to empty because the normal
Next server talks to the API server-side; paths, credentials and malformed origins are rejected.
`PCR_WORKER_TIMEOUT_SECONDS` bounds one worker run and
accepts 1–299 seconds.

`PCR_RUNNER_SCRATCH_SIZE` sets the runner's ephemeral tmpfs ceiling and accepts
128m through 8g. It is not a host directory and is discarded when the runner
is recreated, so abandoned scientific temporary files cannot accumulate on
the server filesystem. Increase it only together with a reviewed runner
memory/resource profile.

The host storage guard limits PCRStudio to a 20 GiB host-storage budget with
4 GiB emergency headroom. It is installed as
`pcrstudio-storage-guard.timer`; inspect it with:

```bash
systemctl list-timers pcrstudio-storage-guard.timer
journalctl -u pcrstudio-storage-guard.service
```

For a new host, `./bootstrap.sh --install-system-deps --prepare-host-only`
installs and verifies the supported Docker/Compose host dependencies and
activates the storage guard without building images or starting the application.
The full production bootstrap is run only after DNS, secrets and the approved
deployment data are ready; it additionally enables the database backup and
restore-drill timers after the application passes readiness.

If the public website must be brought online before the scientific database is
reviewed, use the explicit control-plane path:

```bash
./bootstrap.sh --install-system-deps --domain pcrstudio.ir --control-plane-only
```

This starts PostgreSQL, migrations, API, Web and Caddy and verifies `/ready`,
but deliberately does not start the durable runner or claim `/ready/scientific`.
It must not be presented as BLAST/MFEprimer-qualified production until an
approved reference snapshot has been built and fingerprinted.

`PCR_DB_MAX_CONNECTIONS`, `PCR_DB_MIN_CONNECTIONS`, and
`PCR_DB_ACQUIRE_TIMEOUT_SECONDS` control the API PostgreSQL pool. Invalid
explicit values fail startup. Production uses file-backed deployment secrets:
PostgreSQL reads `/run/secrets/postgres_password`, while the API, migrator, and
runner read `/run/secrets/database_url`; secret bytes do not belong in `.env` or
container environment interpolation.
