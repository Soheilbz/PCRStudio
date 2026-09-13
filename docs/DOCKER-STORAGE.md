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
fails. The server's `pcrstudio-storage-guard.timer` checks every five minutes.
On a developer workstation with a running systemd user manager, maintainers
can run `python3 scripts/docker-maintenance.py setup` once to create the
builder and enable a persistent daily, checkout-scoped maintenance timer. It
logs under that user's journal; a failed maintenance run is visible as a
failed timer service.

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
the release puller removes only obsolete full-SHA tags for PCRStudio's four
runtime images and source trees, retaining the active and immediately previous
release for rollback. It never forces image removal; if Docker reports an
image is still in use, that tag is kept and a warning is logged.

CI uses ephemeral runners and runs a final bounded BuildKit prune so a failed
qualification cannot leave a large cache on a reused runner. Cloud hosts
should invoke the repository bootstrap/maintenance path from the same release
checkout rather than using ad-hoc daemon-wide pruning.

The web build uses the official `registry.npmjs.com` endpoint and the exact
pnpm `11.26.0` package-manager version (Corepack signature/integrity checks).
Its dependency-fetch steps use the dedicated BuildKit builder's explicit
`network.host` entitlement because this host's Docker bridge cannot complete
TLS connections to the Cloudflare-backed `registry.npmjs.org` hostname; the
entitlement is build-time only and is not granted to runtime containers.
Frozen lockfile integrity hashes remain mandatory.

## Dedicated-host storage budget

The dedicated PCRStudio host uses a **20 GiB managed application budget**, not
a separate partition or kernel directory quota. The budget counts allocated
storage under `/srv/pcrstudio`, Docker's reported `DockerRootDir`, and
containerd's configured root. It is an operational budget enforced by
measurement, cleanup, and service stops; it is not a filesystem-enforced hard
quota. The host also preserves at least 8 GiB free for normal operation and 4
GiB as an emergency floor. Bootstrap rejects a host smaller than 32 GiB and
records the observed storage roots and capacity in deployment evidence.

The systemd guard starts one minute after boot and checks every five minutes.
Before measuring, it removes only stale PCRStudio release-download staging,
expired/over-budget PCRStudio backups, and—when storage pressure warrants
it—the PCRStudio BuildKit cache and dangling PCRStudio-labelled images. It
pauses the scientific runner at 16 GiB of managed use or below 8 GiB host-free;
it stops PCRStudio services at 20 GiB managed use or below 4 GiB host-free.
It never deletes database state, a current/rollback release image, or another
project's Docker resources. Docker build-cache GC remains capped at 8 GB.

Release downloads are serialized, limited by the exact GitHub-declared asset
size and conservative per-asset ceilings, and removed automatically if a
transfer fails. Interrupted staging directories are cleaned under the same
lock on the next maintenance pass. Successful updates retain only the active
and immediately previous source/image releases. PostgreSQL backups stream
directly to a file capped at 4 GiB each; retention keeps at most 8 GiB in
total and 14 days, while preserving the newest usable backup. Restore drills
preflight space for their temporary duplicate before running. Per-container
logs remain capped at 10 MiB × 3 files, and scientific scratch remains bounded
tmpfs rather than persistent disk.

PCRStudio also applies request and per-account data ceilings in the API. These
application limits and the periodic host guard reduce growth risk, but the
20 GiB managed budget is not a kernel quota: unexpected growth can cross a
threshold between five-minute checks. The emergency free-space floor is the
independent protection against host exhaustion. Host-local backups are not
off-host disaster recovery; follow the backup section of `docs/OPERATIONS.md`.

The prebuilt production deployment verifies exact base-image digests from the
server's local OCI cache and fails closed if any is absent or differs; it does
not silently substitute a tag, mirror or unpinned image.
