# PCRStudio

A web workbench for designing and checking PCR primers. One module per design
system.

Twenty-one design systems over eleven engines, and every engine computes.
Every system is marked **experimental** at the public module level:
implemented and computationally testable, not bench validated. Hydrolysis-probe
qPCR executes versioned conventional Thermo Fisher/IDT chemistry directly. MGB/NFQ is
`external-authority-required`: PCRStudio exports a content-bound candidate set and accepts
MGB-aware Tm only when the imported result matches the same candidate-set SHA-256; it never
substitutes ordinary-DNA Tm. The status and typed refusal/authority boundaries are shown on
module pages because a refusal is safer than silently substituting a different chemistry.

## Architecture integrity

PCRStudio is maintained as a **layered modular monolith**. The machine-readable architecture contract is `contracts/architecture.toml`; architectural decisions are recorded under `docs/adr/`, including ADR 0008. Generated projections are read-only derivatives of canonical contracts, workflow evidence uses one canonical shape, persistence contracts are versioned, and release qualification enforces locked Rust dependency resolution.

## Method fidelity

PCRStudio distinguishes **using a named method** from merely using a similar heuristic. The canonical registry is `contracts/method-fidelity.json` and the generated review is `knowledge/reviews/METHOD-FIDELITY-AUDIT.md`. Upstream tools such as Primer3, BLAST+, MFEprimer, MAFFT, PrimerPooler, PrimalScheme3, Olivar and pydna are identified separately from internal ports, public-manual rule implementations, compatible approximations and external-authority-only methods. Scientific-Strict refuses a primary design/ranking path when its declared fidelity is insufficient rather than silently presenting an approximation as the named method.

Examples of deliberate boundaries include: PCRStudio implements the published SADDLE Badness objective but does **not** claim its deterministic local optimiser is the SADDLE simulated-annealing optimiser; proprietary PrimerExplorer/Kraken/NEBaseChanger software internals are not guessed; MGB-aware Tm remains external-authority bound; and generalized ARMS/KASP-compatible policies are labelled as PCRStudio policies rather than their named external tools.


## How it is put together

| Piece | Lives in | Does |
| --- | --- | --- |
| Domain core | `crates/pcr-core` | The `DesignModule` contract, the registry, the shared types. Knows nothing about HTTP. |
| Accounts | `crates/pcr-accounts` | Users, Argon2id passwords, revocable sessions, over PostgreSQL. |
| API server | `crates/pcr-server` | Publishes both over HTTP with axum. Transport only. |
| Projects | `crates/pcr-projects` | Projects, drafts, and saved runs. Same database, separate domain. |
| Design worker | `tools` | The Python that actually designs: primer3-py for the search, ViennaRNA for folding. The Rust side spawns it per request and speaks JSON over a pipe. |
| Interface | `web` | Next.js App Router, shadcn/ui, Tailwind v4. Fetches from the API while rendering on the server. |

The interface never hard-codes a list of design systems: it asks the core what
it has and renders the answer. Adding a module means registering it in
`pcr-core`; the navigation, the routes, the sitemap and the module pages follow
on their own.

The browser never talks to the API. Pages fetch from it while rendering on the
Node side, which is why the API and the database can stay on a private network
and why a crawler receives complete HTML.

## Source availability

This repository is prepared as the **CURRENT source candidate**. The source
tree is structurally closed and all 21 design modules are marked
`experimental`, which means computationally implemented but not claimed as
bench-validated. The repository may be temporarily visible on GitHub for CI
and deployment verification, but visibility does not grant reuse rights.
Native Linux qualification and wet-lab validation are separate evidence gates;
see [`release/STATUS.md`](release/STATUS.md).

Security, development, and release guidance live in
[`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md),
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md), and
[`release/INDEX.md`](release/INDEX.md).

## Repository layout

The repository keeps product source, scientific knowledge, operations, and
generated release evidence separate:

| Directory | Purpose |
| --- | --- |
| `crates` | Rust domain, account, project, and API services. |
| `web` | Next.js interface, shared UI, and browser tests. |
| `tools` | Python design worker, scientific adapters, and worker tests. |
| `knowledge` | Current module/engine knowledge, contracts, reviews, and runtime policy. |
| `scripts` | Launchers, provisioning, database helpers, audits, and release generators. |
| `docker` | Container images, Caddy configuration, and development database compose file. |
| `release` | Current release metadata, qualification guidance, integrity evidence, and the immutable baseline needed by release tooling. |
| `.local` | Machine-local logs, backups, tool installations, databases, and generated ZIPs; never source. |

Build output and dependency directories such as `target`, `node_modules`,
`web/.next`, and Python environments are intentionally kept out of source
archives and are recreated locally when needed.

## Adding a design system

This is the seam the first real module drops into.

1. Implement `DesignModule` in `crates/pcr-core`. `manifest()` returns a
   url-safe id, a name, a one-line summary, a category and a status; `design()`
   takes the request shape your module defines and returns its own result shape.
2. Register its canonical profile/runtime contract and bind it into
   `default_registry()`; the catalogue is generated from those current
   authorities rather than from a second placeholder list.
3. Give it a form. `POST /api/modules/{id}/design` already carries the request
   and the answer end to end, and `api.runDesign()` on the interface side calls
   it — but the fields belong to the module, so the page that collects them is
   written with the module rather than before it.

Nothing else in `web` needs to change for the module to appear in the sidebar,
the palette, the catalogue and the sitemap.

Set `status` honestly, and note where the line falls: `planned` until it
computes, `experimental` once it does, and `stable` only after somebody has
ordered oligos from it and run them. Checking the output against a reference
sequence is what `experimental` already means here — every assay does that, and
their recorded answers fail the build when they move — so passing tests is not
what promotes one. `Status::means` and `Status::promotion` in
`crates/pcr-core/src/taxonomy.rs` state both in the words the module page shows.

The interface shows this everywhere the module appears, and that badge is the
only thing standing between a bench scientist and a number they should not
trust.

## Running it locally

For a complete fresh local Linux checkout, run `./bootstrap.sh --local`. It
installs/reuses the project-local uv environment, materialises the pinned
Python/Web dependencies, provisions and verifies the pinned scientific tools,
installs Chromium/Firefox/WebKit into `.local`, runs the source qualification
gates, starts the PostgreSQL/API/Next full stack, waits for all readiness
probes, and creates or verifies a mode-600 local administrator credential file.
The command is idempotent: a second run reuses a healthy stack and never starts
a duplicate API or web listener. The production Docker deployment remains
`./bootstrap.sh` with its domain/reference arguments.

The bootstrap prints the selected full-stack URL. Open that URL in a browser;
the exact API and web endpoints are also recorded in
`.local/runtime/endpoints.json`. The generated administrator credentials are in
`.local/admin-credentials.json` and are intentionally never printed or checked
into source control. `./run.sh` or `pnpm launch` remains available when you want
to start/restart the development services manually.

Three processes. The database first:

```bash
docker compose -f docker/compose.devdb.yaml up -d --wait db
```

The development compose file prefers Postgres on `127.0.0.1:55432` — loopback
only, so it is still not reachable from off-host. Production uses the separate
`compose.yaml` file and does not publish Postgres at all.

Then initialise the design worker environment. The worker is Python and is not
optional for design requests:

```bash
uv sync --project tools --frozen --extra dev
```

Then start the API. Local/development mode applies migrations on startup for
convenience; production Compose uses the dedicated one-shot `pcr-migrate`
service and starts API/runner only after it succeeds. The launcher automatically
uses `tools/.venv` when it contains the worker. `PCR_PYTHON` may still be set
explicitly when a development deployment uses a different interpreter:

```bash
PCR_DATABASE_URL=postgres://pcr:YOUR_PASSWORD@localhost:55432/pcrstudio PCR_PYTHON=$PWD/tools/.venv/bin/python pnpm api
```

You may place `PCR_DATABASE_URL` and other local overrides in `.env`. The launcher refuses to start when no usable worker can import `pcr_tools`, so a misconfigured design environment is reported before the API can accept a request.

Ask it whether it can actually work before wondering why a design fails:

```bash
curl -s localhost:8080/ready
```

`/health` says only that the process is answering, which is what a liveness
probe should say. `/ready` proves the database hands out a connection and the
Python design worker imports/answers. `/ready/scientific` is the stricter host
qualification probe: it additionally checks the pinned local/embedded
scientific toolchain. Public readiness bodies expose component state only; raw
driver/tool errors stay in logs.

Then the interface:

```bash
pnpm install && pnpm dev
```

For manual full-stack launches, use `pnpm launch`. It prefers ports 3000, 8080,
and 55432, but automatically selects free loopback ports when any is occupied,
passes the selected API address to the web server, and closes only the child
processes it started. `./bootstrap.sh --local` performs this launch and the
readiness checks for you.

The workspace pins pnpm to `11.19.0`. Its project `.npmrc` also permits a
non-interactive reconciliation of stale `node_modules`, so IDE and CI runs do
not hang waiting for a confirmation that cannot be typed. Docker and the
Linux launcher disable Corepack's download prompt as well; if Corepack has
not cached the pinned pnpm version yet, it downloads that exact version without
blocking on stdin.

When started manually, the interface expects the API on
`http://127.0.0.1:8080`; point it elsewhere with `PCR_API_URL`. `pnpm launch`
wires the selected API port automatically. If the API is down the site still
renders — it says so in a banner and shows an empty registry rather than
inventing one.

## Linux CURRENT qualification

The distributable CURRENT identity is qualified only on Linux x86_64. Follow [`release/current/CURRENT-LINUX-QUALIFICATION.md`](release/current/CURRENT-LINUX-QUALIFICATION.md). Run `python scripts/prepare-linux.py --sync-dependencies --provision-tools`, configure an approved specificity database, optionally bind Olivar 1.3.3 with `scripts/configure-olivar-linux.py`, then execute `python scripts/run-linux-qualification.py --full`. Functional evidence remains a separate explicit gate and is never inferred from a source-only PASS.

## Checks

```bash
pnpm check
```

That runs, in order: TypeScript, ESLint, the interface tests, Clippy with
warnings denied, and the Rust tests.

The account tests need a database. Without `PCR_TEST_DATABASE_URL` they print
`SKIPPED` and do nothing, which is not the same as passing:

```bash
PCR_TEST_DATABASE_URL=postgres://pcr:pcr@localhost:5432/pcrstudio \
PCR_DB_MAX_CONNECTIONS=4 PCR_DB_MIN_CONNECTIONS=0 cargo test --locked --workspace
```

Each of those tests creates its own schema, so they run in parallel without
seeing each other's rows.

One test is worth knowing about: `web/src/lib/api/contract.test.ts` reads the
Rust enums and fails if the TypeScript wire types have drifted from them. The
vocabulary is written twice, so something has to hold the two together.

## Design tokens

Every colour in the interface comes from a token in `web/src/app/globals.css`,
defined once for light and once for dark. Nothing should introduce a raw hex or
a Tailwind palette colour; if a shade is missing, the fix is a token.

| Token | For |
| --- | --- |
| `primary` | Actions. A deep terracotta, dark enough to hold white text at 4.5:1. |
| `brand` | Identity — the mark, accents. The lighter terracotta, which never carries text. |
| `success` `warning` `info` | Outcomes. `success` and `warning` are what the stable and experimental module badges use, so a colour never means one thing in one place and another elsewhere. |
| `destructive` | Deleting. Deliberately 19° of hue from `primary`: a button that removes an account must not read as a warmer version of one that saves. |
| `chart-1` … `chart-5` | A categorical ramp, warm enough not to fight the interface, for when a module has something to plot. |
| `sidebar-*` | The frame, a shade deeper than the page. |

Colours are written in OKLCH, so lightness is perceptual: two tokens with the
same `L` look equally light, which is what makes a light and a dark theme
derivable from each other rather than hand-matched.

Spacing is deliberately tight — `py-4` on cards, `space-y-6` between sections,
a 48px header. The interface is dense by intent; a module that needs room
should take it locally rather than loosening the shell.

## Accounts

Passwords are hashed with Argon2id. Sessions are opaque random tokens, stored
only as their SHA-256, so a database dump does not hand anyone a working
session; they are checked on every request, which is what makes "sign out
everywhere" take effect immediately.

The token reaches the browser in an `HttpOnly` cookie set by Next, never by
script, and never leaves the server otherwise. Signing in and signing out are
server actions, so Next checks the request origin as well.

Registration, sign-in and sensitive account operations are rate limited.
Deployed account/design routes use shared PostgreSQL buckets, so several API
replicas enforce one logical ceiling instead of multiplying it per process. An
in-process limiter remains only for isolated routers/tests that intentionally
have no account store.

The password policy is length and nothing else — at least ten characters.
Composition rules push people towards `Password1!` and away from passphrases.

## Somebody's data

Three things an account can do with its own work, and one thing the server does
on a clock.

**Take it out.** `GET /api/projects/export` returns every project with its
notes and its draft, and every saved run with the request that produced it —
enough to reproduce a design elsewhere, not merely to read it. Passwords and
recovery codes are stored hashed and are not in it.

**Put it back.** `POST /api/projects/import` accepts that same document. The
account page proxies export/import as streams rather than materialising the
whole backup in a Server Action. Live project/run payload is capped below the
authenticated import transport ceiling, so a state the application permits can
be backed up and restored through its own supported path. Importing one file
twice does nothing the second time. A deleted project comes back rather than
being reported as already present. If restoring into an already-populated
account would exceed the live-data ceiling, the import transaction fails
atomically instead of leaving an unreported partial backup.

**Change their mind.** Deleting a project marks it rather than removing it, and
it can be brought back for thirty days. Every ordinary query reads through a
view that cannot see marked rows, so the filtering is a property of the schema
rather than something each new query has to remember.

**Forget it eventually.** The API purges anything past that window hourly, in
the same loop that clears expired sessions. "Delete" has to mean deleted in the
end, or the window is just a longer name for keeping everything.

## Share links

`GET /api/shared/{token}` is the one route that answers without a session, so
its shape is deliberate.

Opt-in per run, never per project — sharing a project would share every run made
in it afterwards, including ones that do not exist yet. Only the SHA-256 of the
token is stored, exactly as with a session, so a database dump yields no working
links and an interface cannot show you a link you have lost. Sharing again mints
a new token and kills the old one, which is what somebody reaches for after
sending a link to the wrong person.

The response carries one run and nothing around it: no owner, no project name,
and not even the project id — two links from the same project would otherwise
tell their holder they were siblings. A token matching nothing gets the same
404 as one that was withdrawn, so the endpoint cannot be used to test tokens.
Deleting a project stops every link into it, because the lookup joins through
the view that cannot see deleted rows.

## Deploying to a Linux host

The canonical production path is the fail-closed Linux bootstrap. Before changing
a host, run the read-only doctor to expose RAM/disk/Docker/DNS/permission issues:

```bash
python3 scripts/doctor-linux.py --domain pcrstudio.example.org --allow-docker-install
```

On a Debian/Ubuntu x86_64 VM, point DNS at the host, copy the source tree, then run:

```bash
./bootstrap.sh --domain pcrstudio.example.org \
  --reference-fasta /absolute/path/to/approved-reference.fasta \
  --database-id approved-reference-2026-09
```

`bootstrap.sh` installs/validates Docker Engine + Compose v2 when needed, creates
`.env` and file-backed deployment secrets with least-privilege host permissions, chooses a RAM-aware
resource profile, rejects insufficient disk before an expensive build, selects
non-conflicting Docker subnets, builds the exact Linux API/Web images, smoke-tests
every bundled scientific executable and Python environment, fingerprints/builds
the supplied MFEprimer + BLAST reference indexes inside the exact API image,
starts the stack, and requires `/ready/scientific` to report `ready=true`.
Re-running the bootstrap
is idempotent: existing secrets are retained and existing database artifacts are
re-hashed before they are trusted. Use `--private` instead of `--domain` for the
loopback-only SSH/VPN bootstrap profile.

Deployment credentials are never interpolated into Compose environment metadata.
Postgres reads its password from `/run/secrets/postgres_password`; API, migrator,
and runner read a percent-encoded full database URL from
`/run/secrets/database_url`. The optional operator bearer and NCBI API key are
likewise mounted as `/run/secrets/operator_token` and `/run/secrets/ncbi_api_key`;
empty files mean the optional capability is disabled. The bootstrap creates and
migrates these files atomically while keeping secret bytes out of `.env`. On
Linux, Compose file secrets preserve the source file metadata, so application
secrets stay host-user-owned but are group-readable only by the fixed unprivileged
PCR runtime (`10001:10001`, mode `0640`); they are never made world-readable.
The stable Next Server Actions encryption key remains host-private and is supplied
only as a BuildKit secret at **web image build time**, matching Next.js
self-hosting semantics.

> **Scientific-runtime boundary:** the API image contains the release-pinned Linux scientific toolchain. The large specificity reference database remains deployment-owned, fingerprinted data mounted read-only. Strict mode stays fail-closed until both the image freeze and an approved/production database manifest pass qualification; `/ready/scientific` is the runtime authority. See [`docker/SCIENTIFIC-RUNTIME.md`](docker/SCIENTIFIC-RUNTIME.md).

The bootstrap always supplies the explicit production Compose file, so it does
not accidentally load `compose.override.yaml` (the developer-only loopback DB
publication). The long-lived topology is PostgreSQL + API + scientific runner +
Web + Caddy, with a sixth one-shot `pcr-migrate` container at deployment time.
Only Caddy is public — TCP 80/443 plus UDP 443 for HTTP/3. PostgreSQL is confined
to the internal data network; Web reaches only API; the runner joins only the
internal data network. Internet egress belongs to API, because NCBI accession
fetching is an API control-plane operation rather than a runner capability.

Durable design jobs are PostgreSQL-authoritative. Production API uses
`PCR_JOB_EXECUTION_MODE=external`; `/ready` reports control-plane/database
availability while `/ready/scientific` additionally requires a fresh runner
heartbeat whose build identity and scientific-freeze fingerprint match the
approved deployment. A dead or mismatched runner therefore keeps scientific
readiness red without unnecessarily hiding login, projects, or diagnostics.

Resource budgets are split by role: API, runner, Web, PostgreSQL and Caddy have
separate memory/PID ceilings and rotated JSON logs. Scientific scratch is a
dedicated host directory mounted only into the runner and prepared with the
unprivileged runtime UID.

### Environment knobs

A few variables worth knowing about, all optional:

- `PCR_MAX_CONCURRENT_WORKERS` caps request-driven Python workers at 1–16.
  Each burns roughly a core while searching, so it defaults to the machine's
  parallelism (clamped to 1–16); extra designs queue for a permit instead of
  starting interpreters. An explicitly configured invalid value fails startup
  rather than being silently clamped.
- `PCR_MAX_QUEUED_WORKERS` bounds callers waiting for a worker permit; it
  defaults to 256 and accepts 0–1024. Zero means fail busy immediately once all
  worker permits are occupied. Invalid explicit values fail startup.
- Production separates request-driven API capacity from durable runner capacity:
  `PCR_API_MAX_CONCURRENT_WORKERS`/`PCR_API_MAX_QUEUED_WORKERS` budget compatibility
  synchronous work in the API, while `PCR_RUNNER_MAX_CONCURRENT_WORKERS` and
  `PCR_RUNNER_MAX_QUEUED_WORKERS` budget durable jobs. `PCR_RUNNER_POLL_MILLISECONDS`
  controls the PostgreSQL polling cadence (100–60000 ms; default 1000).
- `PCR_DATABASE_MIGRATIONS` is `startup` for direct development and `external`
  in production. Do not set production API back to `startup`: Compose owns schema
  migration through the fail-closed one-shot migrator.
- `PCR_TRUSTED_PROXIES` is a comma-separated list of exact proxy IPs or canonical
  CIDR ranges whose `X-Forwarded-For` is believed when deciding who to rate-limit.
  Unset or unmatched, the header is ignored and the peer address counts — which
  is why a caller cannot rotate buckets by forging it. Network CIDRs deliberately
  fail closed when they are noncanonical or over-broad (IPv4 broader than `/16`,
  IPv6 broader than `/64`); exact host IPs remain valid.
- `PCR_CORS_ORIGINS` is a comma-separated allow-list of exact `http`/`https`
  browser origins. It defaults to empty because the normal Next server talks to
  the API server-side. Paths, credentials and malformed origins are rejected.
- `PCR_WORKER_TIMEOUT_SECONDS` bounds one worker run; it defaults to 120 and an
  explicit value must be 1–299 seconds so the subprocess ends before the API's
  300-second request deadline (the Web transport allows 310 seconds).
- `PCR_DB_MAX_CONNECTIONS` sets the per-API PostgreSQL pool ceiling (default 32,
  allowed 4–128), `PCR_DB_MIN_CONNECTIONS` sets the warm floor (default 2,
  allowed 0 through the configured maximum), and
  `PCR_DB_ACQUIRE_TIMEOUT_SECONDS` bounds how long a request waits for a pool
  connection (default 5, allowed 1–60 seconds). Explicit malformed or
  out-of-range database-pool overrides fail startup instead of being silently
  clamped or replaced by defaults.
- Rate limiting itself needs no configuration: 30 designs per minute per
  caller, and 15 sequence lookups, alignments, or consensus builds in that
  same window — lower because those fork the same kind of worker and one of
  them talks to NCBI. NCBI EFetch spacing is additionally reserved in
  PostgreSQL, so adding API replicas cannot multiply the upstream request rate.
  The shared reservation horizon is bounded to five seconds; excess bursts are
  rejected without reserving an unbounded queue of future upstream capacity.

The API container's health check asks `/ready`, not `/health`, so the web tier
waits for the database/control plane rather than merely for a listening process.
Full scientific-host qualification is intentionally separate at
`/ready/scientific`: it additionally requires the Python worker, exact toolchain,
approved reference database, and a fresh compatible runner. Login/projects can
remain available during a scientific outage, while deployment/release gates
still fail closed until scientific readiness is fully green.

`SITE_URL` is compiled into the bundle, because canonical URLs and the sitemap
need the real origin at build time. Changing it means rebuilding the web image.

The API is not reachable while the web image builds. Module pages that would
have been pre-rendered are rendered on first request instead, so the build does
not depend on the core being up.

Back up the `db_data` volume. It is the only state that cannot be rebuilt from
this repository.

## Search engines

Every module has its own address, title, description, canonical URL and
JSON-LD, all derived from the manifest the core published — so what a crawler
reads cannot drift from what a visitor sees. `sitemap.xml` is generated from the
registry rather than kept by hand. `/account`, `/sign-in` and `/sign-up` are
excluded in `robots.txt`.

Two known gaps: pages render per request rather than as static files, because
the sidebar state is read from a cookie during the server render; and the API
being down during a crawl yields a page with an error body rather than a clean
5xx, though it carries `noindex` either way. An unknown module id used to be a
third — it answered `200` with a not-found body — but `generateMetadata` and
the page both call `notFound()` when the registry has no such module, so it is
a real `404` now.

## Licensing

The Web/Rust/application source is proprietary and unlicensed for reuse; see
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). The Python scientific worker under
[`tools/`](tools/) is separately licensed
GPL-2.0-or-later; see [`tools/LICENSE`](tools/LICENSE) and
[`tools/README.md`](tools/README.md). Third-party dependencies retain their own
licenses and are inventoried in the release SBOM/toolchain records.
