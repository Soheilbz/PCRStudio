# ADR 0009 — External scientific runner and Linux release boundary

- Status: Accepted
- Release line: CURRENT / Generation 1
- Canonical platform: Linux x86_64

## Context

PCRStudio's HTTP API previously owned both request/control-plane work and the
lifecycle of durable scientific jobs. That coupling meant a long-running native
validator could consume API resources, a process restart could interrupt
scientific execution, and deployment readiness could not distinguish a healthy
application control plane from a healthy scientific execution plane.

The repository already had PostgreSQL-authoritative jobs, atomic claims, leases,
heartbeats and recovery semantics. Introducing another queueing product would
therefore add operational state without solving a missing durability primitive.

## Decision

Production uses three explicit execution roles:

1. `pcr-migrate` is the one-shot schema owner for a deployment.
2. `pcr-server` is the HTTP/auth/control-plane composition root. Production
   durable jobs are enqueue-only (`PCR_JOB_EXECUTION_MODE=external`).
3. `pcr-runner` claims durable jobs from PostgreSQL and owns their scientific
   subprocess lifecycle, heartbeat, cancellation, result persistence and lease
   recovery.

Transport-neutral orchestration lives in `pcr-application`; neither the runner
nor that crate depends on Axum. PostgreSQL remains the only durable queue
authority. Redis/RabbitMQ/Kafka are not introduced in the current Generation 1 architecture.

The API's `/ready` endpoint represents database/control-plane availability.
`/ready/scientific` additionally requires the exact scientific environment,
approved specificity database and a fresh runner whose build identity and
scientific-freeze fingerprint match the deployment. Release/bootstrap gates
require scientific readiness even though ordinary application availability does
not.

Scientific Python/native executables are part of the immutable API/runner image.
Large reference/index data is deployment-owned, content-addressed and mounted
read-only. Scientific scratch is writable only in the runner's dedicated scratch
mount.

Every spawned scientific worker is placed in its own POSIX process group. Timeout,
cancellation and shutdown target the complete process group so BLAST/MAFFT or
other grandchildren cannot remain orphaned after their Python parent exits.

## Consequences

- API restarts no longer own durable scientific-job lifetime.
- Scientific capacity can be scaled independently by adding compatible runners.
- A dead or build-mismatched runner makes scientific readiness fail closed.
- Database migration has one owner and cannot race API/runner startup.
- PostgreSQL remains a single operational dependency for state and queueing.
- Component development may retain the embedded executor, but production
  qualification must exercise the external-runner topology.
- Linux x86_64 build/process/filesystem semantics are release authority; Windows,
  WSL and emulation layers are outside the supported production boundary.
