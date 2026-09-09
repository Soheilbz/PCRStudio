# PCRStudio Linux deployment

This is the operational deployment authority for Generation-1 PCRStudio. The production target is a **Linux x86_64** host running Docker Engine and Docker Compose v2. Native scientific artifacts in the CURRENT contract are qualified for Linux x86_64; ARM64 is not an equivalent target and must not be used unless a separate ARM64 toolchain contract and qualification evidence are produced.

## Production topology

```text
Internet
   |
 Caddy  :80/:443
   |
 Next.js Web
   |
 Rust API  (HTTP/auth/control plane)
   |
 PostgreSQL  <---- dedicated pcr-runner
      ^                 |
      |                 +--> Python worker --> native scientific tools
      |
 one-shot pcr-migrate (deployment only)
```

Only Caddy is published. PostgreSQL lives on the internal `data` network. Web sees API through the internal `app` network. The runner joins only the internal `data` network and has no edge-facing or outbound network path; its scientific tools operate on the queued request and deployment-owned local data. The API alone joins the outbound `egress` network for explicitly remote sequence references. Production durable jobs are queued in PostgreSQL and executed by `pcr-runner`; API does not own the durable executor loop.

A deployment is not ready merely because the HTTP process answers. In external execution mode `/ready` also requires a fresh runner heartbeat in PostgreSQL. The heartbeat is bound to the approved scientific Python freeze when one is configured, so a runner built from a different scientific environment does not satisfy readiness.

## Supported host baseline

Use a current Debian/Ubuntu-class x86_64 Linux VM with:

- enough CPU/RAM for the configured scientific concurrency;
- persistent disk for PostgreSQL, Docker images, specificity databases, backups and runner scratch;
- DNS pointing to the host before requesting public TLS;
- only TCP 80/443 and UDP 443 exposed publicly when using direct Caddy TLS;
- SSH/VPN administration on a separately controlled path.

Do not expose PostgreSQL, the Rust API or the Docker socket publicly.

## One-command bootstrap

For a public TLS deployment:

```bash
./bootstrap.sh \
  --domain pcrstudio.example.org \
  --reference-fasta /absolute/path/to/approved-reference.fasta \
  --database-id approved-reference-2026-09
```

For a private loopback deployment reached through SSH/VPN/tunnel:

```bash
./bootstrap.sh \
  --private \
  --reference-fasta /absolute/path/to/approved-reference.fasta \
  --database-id approved-reference-2026-09
```

The bootstrap is the preferred path. It validates Linux/x86_64, installs or validates Docker + Compose where supported, creates file-backed database secrets, chooses non-conflicting bridge subnets, prepares the unprivileged runner scratch directory, builds the immutable API/scientific and Web images, runs container-level scientific smoke tests, fingerprints the scientific Python freeze, builds and hashes MFEprimer/BLAST specificity indexes from the selected FASTA, starts the topology, and requires both application and scientific readiness before recording deployment evidence.

Re-running bootstrap is designed to be idempotent. Existing secret material is retained, while scientific database manifests and hashes are independently revalidated before trust.

## Startup ordering

Production startup is intentionally ordered:

```text
PostgreSQL healthy
      |
pcr-migrate
  - applies SQLx migrations
  - audits historical ownership invariants
  - validates staged PostgreSQL constraints
      |
      +---- success ----> API + runner
                          |
                       Web healthy
                          |
                       Caddy
```

`pcr-migrate` is a one-shot service. API and runner use migration-free database connections in production, so multiple long-lived processes never race for schema ownership. A migration/integrity failure prevents API and runner startup.

## Scientific runtime boundary

The API/runner image contains the exact worker environment and native scientific executables. Large specificity data is deployment-owned and mounted read-only from `.local/scientific-db`. Runner scratch lives under `.local/runner-scratch`, is writable only by the unprivileged runtime UID and is not durable scientific history.

Strict scientific execution remains fail-closed until:

1. bundled tool versions/hashes pass the image smoke;
2. the scientific Python freeze is recorded and approved;
3. the configured reference FASTA and every generated index match their manifest hashes;
4. `/ready/scientific` reports `ready=true`.

## Secrets

Production database credentials are file-backed. The host keeps generated secret files under `.local/secrets` with restrictive permissions; Compose mounts them as secrets. Do not put the database password, session secrets or operator token in committed `.env` files.

The Next Server Actions encryption key is a stable 32-byte random value encoded as Base64 and is supplied at **Web image build time**. Preserve it across replicas/builds in the same deployment line.

## Health and diagnostics

Useful checks:

```bash
docker compose ps
curl -fsS https://pcrstudio.example.org/health
curl -fsS https://pcrstudio.example.org/ready
curl -fsS https://pcrstudio.example.org/ready/scientific
docker compose logs --tail=200 api runner migrate web caddy db
```

`/health` is liveness only. `/ready` proves database + worker + required runner topology. `/ready/scientific` additionally proves the strict scientific toolchain. Raw driver/tool errors remain in logs rather than public readiness bodies.

## Backup and recovery

Bootstrap can install systemd timers after scientific readiness is green. The default policy creates daily PostgreSQL backups with SHA-256 sidecars and retention, plus a scheduled restore drill. A local backup is not sufficient disaster recovery: copy backups and any required blob/scientific-data manifests to storage outside the VM according to the deployment owner's retention/security policy.

Manual commands use repository wrappers rather than container-name assumptions:

```bash
./scripts/backup-db.sh
./scripts/backup-restore-drill.sh
./scripts/restore-db.sh /path/to/backup.sql.gz
```

Never restore an unverified backup over production. The restore script validates a sidecar digest when present and terminates conflicting DB connections before replacement.

## Updates

Treat a release as immutable source + image + scientific/database fingerprints. For an update, rebuild from the intended source revision, run the Linux release qualification, take an off-host backup, and then rerun bootstrap/deploy. Do not `pip install`, `apt install` scientific tools, or edit container files interactively after qualification; that creates an unrecorded runtime different from the release evidence.

## GitHub Actions staging deployment over SSH

The repository includes a manual-only `.github/workflows/staging-deploy.yml`
workflow for a supplied staging host. It is not a production deployment trigger
and it performs no action on push. The workflow checks out the selected ref,
transfers that exact committed source archive, preserves deployment state under
`/srv/pcrstudio/state`, invokes the repository-supported `bootstrap.sh`, and
checks the host-local health endpoint. It requires a GitHub `staging` environment
and a dedicated non-root `pcrstudio-deploy` account with access only to the
deployment directory and the Docker operations needed by the bootstrap. Do not
use a root login or disable host-key checking.

Generate a dedicated CI key only when no suitable key exists:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_pcrstudio_deploy -C pcrstudio-staging-deploy
```

Add the resulting `.pub` line to the staging account's `authorized_keys` with
`no-agent-forwarding,no-port-forwarding,no-X11-forwarding` restrictions. Review
the server host key out of band, then store the complete reviewed `known_hosts`
line—not fresh unaudited `ssh-keyscan` output—as the GitHub environment secrets:

| Secret | Value |
| --- | --- |
| `PCRSTUDIO_STAGING_SSH_PRIVATE_KEY` | Complete Ed25519 private-key text; never commit or print it. |
| `PCRSTUDIO_STAGING_SSH_KNOWN_HOSTS` | Reviewed host-key line(s) for the staging hostname. |
| `PCRSTUDIO_STAGING_SSH_HOST` | Staging SSH hostname or address. |
| `PCRSTUDIO_STAGING_SSH_USER` | Dedicated non-root deployment username, normally `pcrstudio-deploy`. |

The workflow uses `StrictHostKeyChecking=yes`, `IdentitiesOnly=yes`, and the
exact pinned checkout action. The staging environment should require approval
and should contain no production credentials. Configure the server's DNS,
firewall, Docker Engine/Compose, persistent storage, TLS prerequisites, and
off-host backup policy separately before dispatching it.

## Operational ownership rule

This file owns deployment guidance. Scientific engine documents own assay/tool methodology, not VM procedures. Deployment configuration must not silently alter scientific ranking rules, and scientific documents must not become an alternative operations runbook.
