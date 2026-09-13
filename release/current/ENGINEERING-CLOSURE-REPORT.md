# PCRStudio current production qualification

Date: 2026-09-13
Current source release: **v1.0.6**

This is the canonical current release-qualification contract. It deliberately
does not copy transient pull-request, CI-run, or server status into source
history. A release is qualified only when its exact-tag GitHub workflow passes,
the verified deployment bundle is published, and the host reports successful
bootstrap/readiness. The workflow run and host service status are the evidence
for those changing facts.

## Release and deployment controls

- Stable releases use exact SemVer tags. Production qualification starts from
  that tag, not from an arbitrary branch push.
- The release remains a draft while source verification, pinned-image builds,
  and restricted-service startup smoke checks run. Only a passing run uploads
  the verified source/OCI bundle and publishes the release.
- The host puller verifies the release tag, declared asset sizes, archive
  SHA-256 values, and portable OCI image-config digests before invoking the
  supported bootstrap. Docker Hub is not needed to obtain the application
  images during that deployment.
- The bootstrap applies database migrations, starts the supported control
  plane and edge, and checks public readiness. Scientific readiness remains a
  separate gate and is never inferred from website availability.

## Runtime and storage limits

The dedicated host policy accounts for the PCRStudio source/state tree and the
Docker/containerd stores under one **20 GiB managed budget**. The host retains
8 GiB for normal operation and 4 GiB as an emergency floor. At the 16 GiB
managed-use threshold, new scientific work is paused; at the 20 GiB budget or
emergency free-space floor, the application is stopped to protect the host.
This is an automated operational guard, not a kernel-enforced quota.

Only PCRStudio-owned staging, bounded BuildKit cache, expired/over-limit
backups, and obsolete release artifacts are eligible for automated cleanup.
Database state, user data, other projects' Docker resources, and the active
plus immediately previous release are retained. See [`DOCKER-STORAGE.md`](../../docs/DOCKER-STORAGE.md)
and [`OPERATIONS.md`](../../docs/OPERATIONS.md) for the supported policy and
operator actions.

## Current runtime defect addressed by this release

The official pinned MAFFT launcher requires Bash, while the minimal API/runner
image previously supplied only BusyBox. The image now includes the required
interpreter from the pinned Debian snapshot in the scientific runtime only;
the database migrator remains minimal. A regression also ensures the
provenance record hashes the MAFFT archive itself rather than a later tool's
archive. The upstream MAFFT digest and all production base-image identities
remain unchanged.

## Evidence boundaries

Source-only checks do not establish successful container execution, database
migration, public TLS, or host deployment. Consult the exact release workflow
and the host's `pcrstudio-release-pull.service`/readiness evidence for those
results. Product/scientific capability maturity remains governed by the
separate current qualification records; this operations report makes no
scientific-validation claim.
