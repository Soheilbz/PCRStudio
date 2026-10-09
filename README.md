# PCRStudio foundation

A fresh private workspace and project platform. Scientific computation, file uploads, billing and cloud release are later slices. The preserved source archive above this directory is a prototype reference.

PCRStudio-specific code and documentation are **All rights reserved**, as described in [LICENSE](LICENSE). Public visibility does not grant a general reuse license. GitHub's viewing/forking rights and third-party licenses remain unaffected. The setup instructions below are for the owner and authorized contributors.

Install Docker Engine with Docker Compose, then run one command from this directory:

```sh
./bootstrap
```

Open [PCRStudio](http://localhost:8080). Synthetic development messages are captured in [Mailpit](http://localhost:8025). Both ports bind only to `127.0.0.1`. PostgreSQL18 and Valkey have no published ports. Caddy serves the static client and routes API and allauth requests through the same origin.

Bootstrap builds locked container toolchains, initializes separate migration/runtime/test database identities, applies migrations, starts services and verifies readiness. Repeating it keeps PostgreSQL data and the generated secrets in ignored `.local/`. Never commit that directory. `./bootstrap stop` preserves data and secrets; `./bootstrap` restarts it. Captured development email is transient.

Secret directories stay private (`0700`), and secret files are owner/group-readable only (`0440`). API, migration and PostgreSQL processes receive the persisted local group only for their explicitly mounted files. PostgreSQL starts directly as its pinned non-root identity, preserving that group during fresh initialization. Tightening legacy file permissions preserves the secret bytes; bootstrap never rotates existing keys.

```sh
./bootstrap status
./bootstrap doctor
./bootstrap check deep
./bootstrap logs api
./bootstrap tools python --version
```

`python3 scripts/project_gate.py deep` is the sole deterministic quality entry, executed in the project tools container by `./bootstrap check deep`. It checks isolation and database privileges; backend lint, types, security, migrations and real PostgreSQL tests; executor contracts and the non-scientific boundary; exported OpenAPI/generated TypeScript consistency; frontend lint, formatting, types, security, build and unit tests; and real Chromium journeys through Caddy and Mailpit. Failed or unavailable checks fail the gate. Reports stay in `.local/artifacts/`.

Format frontend source with `./bootstrap tools npm --prefix /workspace/frontend run format`. Prettier is pinned in the frontend lockfile; the gate checks formatting, and generated API files are excluded.

All Docker resources use a stable namespace saved in `.local/compose.env`, derived from this checkout's path at first bootstrap. Commands operate only on that namespace; there is no global cleanup or reset command. Application processes run without root privileges on read-only filesystems with explicit temporary paths. The API health check tests process liveness. Bootstrap readiness checks database and shared rate-limiter access. Docker does not restart a container merely because it becomes unhealthy.

PostgreSQL suppresses statement, bind-parameter and detailed error logging to keep confidential input out of routine database logs. The live operations gate verifies these settings alongside database role isolation.

Gunicorn emits bounded lifecycle/error event codes instead of request URIs or traceback contents. Application HTTP diagnostics remain neutral and include an opaque request identifier.

Image tags and immutable registry digests are pinned in Compose and `ops/Dockerfile`; application dependencies are locked in `backend/uv.lock` and `frontend/package-lock.json`. The tools service uses an explicit DNS resolver for registry/security-audit access and build downloads use the host network; these settings affect only project containers, never the Docker daemon.

The tools image copies the exact Chromium headless shell from the matching official Playwright container, pinned by digest. Browser system dependencies are installed in the Python tools image. This keeps browser qualification reproducible when the direct browser-download CDN is unavailable.

This is a loopback development environment with HTTP, a synthetic inbox and container tools. Production TLS, external SMTP, backup/restore, monitoring, load qualification, payment integration and cloud release require the separate [release gates](docs/operations/release-gates.md). GitHub runs the same local gate; [acceptance evidence](docs/testing/verification.md) records the actual local and hosted results and their limits.
