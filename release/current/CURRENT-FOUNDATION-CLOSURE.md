# Generation 1 foundation — source closure matrix

**Release:** PCRStudio Generation 1 foundation
**Scope:** source architecture, cross-layer contracts, release integrity and environment-independent qualification.
**Native Linux qualification:** deliberately external; execute `scripts/run-linux-qualification.py` on the target host.

States are maturity claims, not a binary checklist. `WIRED-SOURCE-TESTED` means source wiring and source-level regression evidence exist while native/runtime acceptance remains a separate dimension. `SOURCE-READY/HOST-GATED` requires an external Linux/runtime/operator gate. `SCHEMA-RESERVED` is intentionally not a CURRENT public feature. `DEBT-BOUNDED` means behavior is current but a known maintainability hotspot is explicitly prevented from growing. `DEFERRED BY DESIGN` is intentionally disabled. The machine-readable authority is `contracts/capability-maturity.json`.

| # | Work item | State | Closure |
|---:|---|---|---|
| 1 | Canonical Module/Engine authority | **DONE** | contracts/modules.toml + engines.toml; generated projections across Rust/Python/Web. |
| 2 | Discriminated DesignRequest | **DONE** | Web request payload is module-discriminated and module→engine binding is generated. |
| 3 | Versioned typed Rust↔Python IPC | **DONE** | IPC v2 envelope carries protocol/request/result schema, requestId, module, engine and command. |
| 4 | Persistence schema versioning/migrations | **DONE** | Draft/request/result/module-contract versions plus non-destructive read migration framework. |
| 5 | Generic numeric recipe resolver | **DONE** | Assay-neutral baseline/overlay/range/override/derivation core; LAMP is a policy consumer. |
| 6 | Scientific registries separated from algorithms | **DONE** | LAMP and flanking protocol/bench registries extracted; canonical tool/contract data is data-driven. |
| 7 | Python monolith decomposition | **DEBT-BOUNDED** | Major concerns are split, but `pipeline.run` and `loop_set.run` remain explicit no-growth debt until native differential qualification can prove a behavior-preserving extraction. |
| 8 | Web workspace/engine-field decomposition | **DONE** | LAMP-heavy field logic and contract/data layers split; specialised assay pages remain explicit by design. |
| 9 | Typed Draft model | **DONE** | Raw DOM strings normalize through ModuleDraft(schemaVersion,moduleId,values). |
| 10 | Universal ValidationIssue | **DONE** | Shared code/severity/ownerStep/fieldPath/source/blocking vocabulary drives readiness. |
| 11 | Typed coordinates | **DONE** | Boundary/HalfOpenInterval/CircularPosition primitives and property tests. |
| 12 | Typed units | **DONE** | Unit-bearing quantities used in generic numeric derivation; unit conversions are explicit. |
| 13 | Progressive Python typing | **DEBT-BOUNDED** | Typed boundaries exist for contracts, IPC, recipes, manifests, validation and provenance, but no repository-wide mypy/pyright gate is claimed until the frozen Python environment can validate it. |
| 14 | Generated HTTP route/OpenAPI operation contract | **WIRED-SOURCE-TESTED** | 58 transport operations are generated from contracts/http-api.toml; scientific payload Zod schemas remain explicit typed no-growth debt in web/src/lib/api/types.ts rather than being misrepresented as generated. |
| 15 | Pure domain core boundary | **DONE** | OS/process execution moved to pcr-worker-client; pcr-core keeps domain adapter. |
| 16 | Warm-worker lifecycle manager | **DEFERRED BY DESIGN** | Not enabled until native benchmark proves benefit; per-request isolation is retained for Gen1. |
| 17 | Real cancellation | **DONE** | Cancellation token kills/reaps active worker and durable jobs expose cancel. |
| 18 | Measured progress | **DONE** | Backend lifecycle/stage telemetry replaces timer-invented progress. |
| 19 | Observability/redaction | **DONE** | Operator diagnostics/metrics and stage/tool timings exclude sequence/user/project payloads. |
| 20 | Weighted resource scheduling | **DONE** | Module resource weights are canonical; external tool thread budget is bounded by acquired capacity. |
| 21 | Canonical tool registry | **DONE** | contracts/tools.toml generates runtime/readiness/provenance tool identities. |
| 22 | Toolchain fingerprint | **DONE** | Run provenance includes a stable digest over contracts/tools/database authority plus the module-relevant content-addressed chemistry/protocol/differential authority set. |
| 23 | Run fingerprint | **DONE** | Canonical request + contract/toolchain identity supports duplicate/reproducibility checks. |
| 24 | Sequence assets | **WIRED-SOURCE-TESTED** | Large sequence/FASTA payloads are content-addressed, referenced by project/run/job ownership tables and hydrated only at the persistence boundary; native DB qualification remains host-bound. |
| 25 | Materialized immutable run summaries | **DONE** | Module/engine/result count/unit/target/schema metadata is persisted for indexed history. |
| 26 | Migration authority separation | **DONE** | Database migrations live behind pcr-storage rather than account-domain ownership. |
| 27 | Static audit decomposition | **DONE** | audit-source.py is a small orchestrator over concern-specific audit modules. |
| 28 | Property-based/large generated checks | **DONE** | Deterministic property loops cover coordinates, numeric bounds and IUPAC reverse-complement. |
| 29 | Cross-language differential testing | **DONE** | Canonical 21-module differential corpus is consumed independently by Python, Web and Rust tests. |
| 30 | Metamorphic scientific tests | **DONE** | Involution, overlay-order invariance and hard-bound monotonicity checks are present. |
| 31 | Performance regression architecture | **DONE** | Portable benchmark records wall time/RSS/stage/tool telemetry; native budgets are a reviewed baseline. |
| 32 | Benchmark before worker pooling | **DONE** | Source benchmark evidence recorded; native Linux baseline is explicitly external before optimization. |
| 33 | Container hardening | **DONE** | API/Web read-only, tmpfs, cap-drop, no-new-privileges and PID limits; DB/Caddy retain only required write/capability behavior. |
| 34 | Container digest pinning | **DONE** | Every external Compose/Dockerfile image is tag+sha256 pinned. |
| 35 | GitHub Action SHA pinning | **DONE** | All action references use immutable commit SHA and Dependabot maintains updates. |
| 36 | SBOM/signing/attestation | **SOURCE-READY/HOST-GATED** | Deterministic CycloneDX SBOM + in-toto source/archive attestations + cosign signing entrypoints; real signature needs operator/CI identity. |
| 37 | cargo-deny | **DONE** | License/source/duplicate/banned dependency policy added alongside cargo-audit. |
| 38 | Linux first-class CI | **SOURCE-READY/HOST-GATED** | Pinned Linux workflow compiles/tests Rust, installs frozen Python/Web environments; native scientific host qualification remains operator gate. |
| 39 | Machine-readable API errors | **DONE** | Stable code/kind/detail/fieldPath/stage/retryable/requestId contract; storage internals are not exposed. |
| 40 | RunJob lifecycle | **DONE** | Durable queued/running/cancel_requested/cancelled/completed/failed model. |
| 41 | Idempotency | **DONE** | Idempotency-Key is request-fingerprint bound; conflicting payload reuse fails closed. |
| 42 | Generic scientific ToolAdapter | **DONE** | Capabilities/version/fingerprint/run lifecycle is unified; run_tool is compatibility wrapper. |
| 43 | Execution context separation | **DONE** | Execution resource settings are structurally separate from design/reaction/validation context. |
| 44 | AssayQualification entity | **SCHEMA-RESERVED** | Immutable qualification persistence exists, but CURRENT deliberately exposes no public HTTP/UI qualification workflow yet. |
| 45 | Attachment architecture | **SCHEMA-RESERVED** | Hashed attachment metadata persistence exists, but CURRENT deliberately exposes no public upload/download attachment workflow yet. |
| 46 | Three-way autosave merge | **DONE** | Base/local/remote field merge auto-resolves independent edits and surfaces true same-field conflicts. |
| 47 | Release authority organization | **DONE** | release/current holds active authority; release/baseline preserves only the immutable baseline required by current release tooling. |
| 48 | Architecture Decision Records | **DONE** | Seven load-bearing ADRs document boundary, coordinates, evidence, pinning, authority, recipes and persistence. |
| 49 | Generated artifact graph | **DONE** | Machine-readable source→generated graph plus generator --check gates. |
| 50 | Operator diagnostics surface | **DONE** | Operator-token protected diagnostics/Prometheus-compatible metrics expose versions/queue/tools, never sample data. |
| 51 | Backup/restore drill | **SOURCE-READY/HOST-GATED** | Script creates backup, restores to temporary DB and verifies migrations/tables; runtime execution needs Docker/DB host. |
| 52 | Secret delivery | **DONE** | Database URL/password-file pattern supports secret-file delivery; plaintext secret is not required. |
| 53 | Egress hardening | **DONE** | HTTPS-only compiled host allowlist, exact-host redirects, proxy opt-in and segregated egress network. |
| 54 | API versioning | **DONE** | /api/v1 is stable; /api compatibility alias preserves legacy clients without duplicate implementation. |
| 55 | Scientific cache fingerprint policy | **DONE** | No shared scientific cache in Gen1; future cache key must include canonical request + contract/toolchain/reference DB fingerprints. |

## Generation 1 foundation twelve-step program

1. Persistence schema versioning and read migrations — closed.
2. Canonical Module/Engine manifest — closed.
3. Generated required-context/PagePlan capability metadata — closed.
4. Typed/versioned Rust↔Python envelope — closed.
5. Discriminated Web request and typed draft — closed.
6. Shared ValidationIssue model — closed.
7. Generic numeric recipe resolver — closed.
8. Canonical scientific tool manifest — closed.
9. Python decomposition with behavior-preserving compatibility seams — closed.
10. Web decomposition while preserving specialised assay pages — closed.
11. Cross-language differential/property/metamorphic framework — closed.
12. Static audit decomposition and re-audit — closed.

## Independent re-audit closure

A second audit was performed against the previously frozen CURRENT archive rather than trusting the work tree or the first closure report. It found and closed the following source-side defects/drift before the final re-freeze:

- release verification imported a local helper and could create `__pycache__` inside an extracted archive; verifier/qualifier are now non-bytecode and `--no-write` verification is non-mutating.
- the retained runtime-artifact generator still expected legacy Python literal authorities; it now consumes Generation 1 foundation generated canonical contracts and has a deterministic `--check` gate.
- the retained fold test API expected `_configure_dna_model`; a compatibility helper was restored without changing model semantics.
- strict IPC v2 hardening had made legacy diagnostic CLI tests bypass scientific validation; legacy CLI is now test-only opt-in while production Rust↔Python IPC remains fail-closed v2.
- hardened NCBI egress tests were still patching `urlopen`; they now exercise the strict exact-host opener, HTTPS-only redirect policy and proxy opt-in behavior.
- Atlas citation proximity and external-validator role expectations were aligned with the canonical CURRENT evidence/tool contracts.
- nested `tails` unknown-field validation now fails before cloning-vector/scientific execution.
- Standard-PCR retained protocol expectations include the canonical Thermo Platinum SuperFi II identity and the restriction-cloning test uses a deterministic exact-site circular vector.
- `test_kasp.py`, inherited from legacy with helpers but zero test cases, now contains seven dependency-light contract tests for fixed tails, dye identity, protocol scaling and fail-closed context.
- all 54 Python test modules now contain at least one test case. With an import-only Primer3 compatibility shim, pytest collects **1074 tests** without collection/API errors; native thermodynamic execution remains the Linux gate.

## Intentional boundaries

- A warm Python worker pool is not enabled until target-host measurements justify trading away per-request isolation.
- A cryptographic release signature is not fabricated; signing requires the operator/CI identity via the supplied cosign scripts.
- Native Rust/Web/scientific executable qualification is not claimed by the source-only environment; the Linux workflow/runbook is the authority for that gate.
- Native performance budgets remain empty until a qualified Linux baseline is measured.
## Executed source-side evidence

- Canonical static audit: **0 errors / 0 warnings**.
- Foundation/property tests: **13/13 PASS**.
- LAMP numeric-contract tests: **9/9 PASS**.
- KASP dependency-light contract tests: **7/7 PASS**.
- Hardened egress/fetch security tests: **24/24 PASS**.
- Runtime artifact generator deterministic `--check`: **PASS**.
- Python test collection with import-only Primer3 shim: **1074 tests / 0 collection errors**; native Primer3 execution is not asserted.
- Python test files with zero test cases: **0/54**.
- Independent verifier + `qualify-source.py --no-write` tree mutation check: **PASS; 755 filesystem files before/after, 0 added / 0 removed / 0 changed**.
- Python AST: **145 files PASS**.
- JSON parse: **90 files PASS**.
- TOML parse: **17 files PASS**.
- TS/TSX syntax/transpile: **231 files PASS**.
- Source hygiene: **0 symlinks / 0 case collisions / 0 cache residue**.
- Supply-chain source check: **6 external image references digest-pinned; 13 GitHub Action references commit-SHA pinned**.
- CycloneDX SBOM: **902 components** from Rust/Python/npm/scientific-tool authorities.
- Source-environment cold-start median: **576.785 ms**; dependency-light Foundation import median: **582.297 ms**.
- Full worker import in this source environment is intentionally **not qualified** because `primer3-py` is absent; this is preserved as evidence rather than converted into a false PASS.

