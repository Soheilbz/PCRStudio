# Docker storage policy

PCRStudio builds use a dedicated `docker-container` BuildKit builder named
`pcrstudio`, using the exact BuildKit image digest recorded by the bootstrap
and maintenance scripts. Its explicit `maxUsedSpace = "8GB"` GC policy
triggers collection above the 8 GB target; `reservedSpace = "1GB"` permits GC
to reclaim down to a smaller working set when necessary. This is a cache-GC
threshold, not a filesystem quota, so in-flight builds can temporarily exceed
it. The explicit `buildx prune --max-used-space 8GB` operation enforces the
target at bootstrap/build cleanup and during scheduled maintenance.
Production image identities remain exact digest pins; cache collection cannot
change an image digest, TLS verification, provenance, or the OCI supply-chain
gate.

The Linux bootstrap creates/selects this builder before the first expensive
build, prunes it before work starts, and prunes it again even when a build
fails. The server's `pcrstudio-storage-guard.timer` runs every 15 minutes and
re-enforces the same bound. On a developer workstation with a running systemd
user manager, maintainers can run `python3 scripts/docker-maintenance.py setup`
once to create the builder and enable a persistent daily, checkout-scoped
maintenance timer. It logs under that user's journal; a failed maintenance run
is visible as a failed timer service.

PCRStudio's supported Linux Compose launcher always selects the dedicated
`pcrstudio` builder. The plain Docker `default` builder is shared with other
applications and is intentionally never pruned by PCRStudio automation.

The supported commands are:

```text
python3 scripts/docker-maintenance.py setup
python3 scripts/docker-maintenance.py ensure
python3 scripts/docker-maintenance.py report
python3 scripts/docker-maintenance.py prune
```

Inspect a workstation timer with `systemctl --user list-timers
'pcrstudio-docker-maintenance-*'` and its logs with
`journalctl --user -u <timer-service-name>`. Server cleanup remains host-level
and is inspected with `systemctl list-timers pcrstudio-storage-guard.timer`
and `journalctl -u pcrstudio-storage-guard.service`.

The builder is selected for PCRStudio through `BUILDX_BUILDER` and is not made
the host-wide default, so another project sharing the Docker daemon keeps its
own builder selection.

The maintenance command deliberately does not run `docker system prune` and
does not remove images belonging to other projects. Only dangling images that
carry PCRStudio's `org.pcrstudio.product=PCRStudio` lifecycle label are
eligible for image cleanup. Old unlabelled images must be reviewed by their
owning project before removal. After a successful production release switch,
the release puller also removes only obsolete full-SHA tags for PCRStudio's four
runtime images, retaining the active and immediately previous release for
rollback. It never forces removal; if Docker reports an image is still in use,
that tag is kept and a warning is logged.

CI uses ephemeral runners and runs a final bounded BuildKit prune so a failed
qualification cannot leave a large cache on a reused runner. Cloud hosts
should invoke the repository bootstrap/maintenance path from the same release
checkout rather than using ad-hoc daemon-wide pruning.

The web build uses the official `registry.npmjs.com` endpoint and the exact
pnpm `11.26.0` package-manager version (Corepack signature/integrity checks).
Its dependency-fetch steps use the
dedicated BuildKit builder's explicit `network.host` entitlement because this
host's Docker bridge cannot complete TLS connections to the Cloudflare-backed
`registry.npmjs.org` hostname; the entitlement is build-time only and is not
granted to runtime containers. Frozen lockfile integrity hashes remain
mandatory.

The Linux bootstrap also installs `pcrstudio-storage-guard.timer` on systemd
hosts. Its 20 GiB setting is a **host free-space safety reserve**, with 4 GiB
of emergency headroom; it is not by itself a per-application 20 GiB disk
quota. On the current 48 GiB host, it stops new scientific work before free
space falls below roughly 32 GiB and stops public API/web/edge services before
it falls below roughly 28 GiB. At each run it prunes only PCRStudio's bounded
builder cache and expired, owned backup artifacts. It never deletes PostgreSQL
data or another Compose project's resources. The guard is a last-resort safety
brake, not a substitute for off-host backups or a larger disk.
It measures the application root, Docker's reported root, and containerd's
OCI root; this avoids treating a tiny DockerRootDir as evidence that image
storage is small.

## Hard 20 GiB production boundary

Production bootstrap now defaults to `PCRSTUDIO_STORAGE_ENFORCEMENT=hard-quota`.
Before it pulls/builds/starts anything, it requires these three writable roots
to share one **non-root, dedicated filesystem** whose capacity is no larger
than `PCRSTUDIO_STORAGE_BUDGET_GIB` (20 by default):

| Ownership | Required root |
| --- | --- |
| PCRStudio source, `.local/` scientific data, secrets and backups | `/srv/pcrstudio` |
| Docker engine data | Docker's reported `DockerRootDir` |
| OCI content and snapshots | containerd's configured `root` (default `/var/lib/containerd`) |

The third row matters on current Docker/Ubuntu installations: OCI layers are
often stored by containerd even when `docker info` reports a tiny
`DockerRootDir`. Moving only `/var/lib/docker` is therefore not a quota.
The verifier fails if a root remains on `/`, if the roots are split, or if the
shared filesystem exceeds the configured cap. Its result is recorded in the
bootstrap evidence.

For this host, attach a dedicated 20 GiB block volume (or use an already
dedicated 20 GiB partition) before production bootstrap. Mount it at a stable
path such as `/srv/pcrstudio-storage`, place Docker `data-root` and containerd
`root` below it, and bind or mount the application checkout as
`/srv/pcrstudio`. Stop Docker/containerd first, migrate existing state with a
reviewed backup/restore plan, configure mounts to exist before both daemons,
then restart them and verify `docker info`, `findmnt -T /srv/pcrstudio`, and
`findmnt -T /var/lib/containerd`. This server currently has only the 48 GiB
root disk, so it does not satisfy this production precondition.

`--allow-guard-only-storage` is an explicit development escape hatch. It
records `NOT_REQUIRED` in the evidence and must not be used to describe a
deployment as hard-capped production.

The prebuilt production deployment verifies those same exact base-image digests
from the server's local OCI cache and fails closed if any is absent or differs;
it does not silently substitute a tag, mirror or unpinned image.
