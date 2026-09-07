# PCRStudio documentation atlas

This directory is the maintained documentation surface for PCRStudio. It is organized around a single-source-of-truth rule: **each scientific or operational claim has one canonical owner; other documents link to that owner instead of copying its values.**

## Start here

- [`engines/README.md`](engines/README.md) — canonical map for the 11 design engines and 21 assay modules.
- [`knowledge/design-intelligence.md`](knowledge/design-intelligence.md) — cross-engine computational design concepts and ownership boundaries.
- [`knowledge/laboratory-effects.md`](knowledge/laboratory-effects.md) — cross-engine laboratory, matrix, oligo-manufacturing and platform effects.
- [`knowledge/validation-evidence.md`](knowledge/validation-evidence.md) — shared validation, metrology, failure-evidence and claim-boundary rules.
- [`audits/current-state.md`](audits/current-state.md) — current documentation status and release-gate results.
- [`audits/tool-file-parity.md`](audits/tool-file-parity.md) — parity/remediation record for all eleven production-grade `01-tools.md` contracts.
- [`operations/deployment.md`](operations/deployment.md) — local preview and persistent deployment runbook.

## Canonical hierarchy

Use the narrowest owner that fully owns a claim:

1. **Assay-specific science or numeric evidence** → the numbered module record under `engines/<engine>/`.
2. **Semantics shared by modules of one engine** → `00-engine.md`.
3. **Tool vocabulary shared by one engine** → `01-tools.md`.
4. **Knowledge shared across multiple engines** → one of the three files under `knowledge/`.
5. **Current audit status** → `audits/current-state.md`.
6. **Deployment procedure** → `operations/deployment.md`.
7. **Historical research/review material** → Git history / prior signed source bundles; it is deliberately absent from the current active tree.

## Anti-duplication rules

- A scientific value must have exactly one canonical owner.
- A source-derived numeric value stays beside the claim it supports. There is no central bibliography and no second numeric catalogue.
- Cross-engine documents describe shared concepts and route ownership; they do not copy module-specific concentrations, temperatures, times, lengths, thresholds or vendor recipes.
- Audit documents report state; they do not redefine scientific rules.
- Historical snapshots are not carried in the current active tree; Git history/prior signed bundles preserve them without polluting current specification scans.
- If a shared rule has an assay-specific exception, the shared rule remains in `knowledge/` and only the exception is recorded in the owning assay module.

## Scientific claim boundary

PCRStudio distinguishes sequence-computable design claims from empirical assay performance. A theoretically complete design does not by itself establish analytical sensitivity, specificity, LOD/LOQ, matrix robustness, instrument performance or clinical/specimen validity. Where such evidence matters, the module or shared validation layer records the required handoff rather than inventing a sequence-only conclusion.

## Current evidence state

The atlas has completed six consecutive heavy cross-engine research passes through **2026-08-30** covering multiplex/set-level optimization, population-aware design and assay drift, oligo manufacturing/QC, matrix inhibition and polymerase robustness, validation/metrology/failure evidence, and database/thermodynamic provenance plus formal benchmark criteria. A final long-tail verification then rechecked current tool/model versions, supplier QC/storage guidance, synthesis-error mechanisms, optical-versus-enzymatic inhibition and the live ISO 20395 revision lifecycle. The resulting shared knowledge is centralized in the three `knowledge/` owners above; only assay-specific consequences are promoted into engine modules. An additional independent adversarial re-audit then targeted August 2026 long-tail literature, tool point releases, vendor technical-note details and internal consistency; material findings were promoted without adding new active knowledge files.

Evidence status is preserved rather than flattened: peer-reviewed literature, published standards, draft standards, vendor documentation, preprints/patents/watchlists and internal software contracts remain distinguishable. Exact study/vendor numbers are not copied into cross-engine files when a narrower assay owner already exists. See [`audits/current-state.md`](audits/current-state.md) for the reproducible release-gate results.

## Generation-1 toolchain maturity

The scientific atlas now also carries a **toolchain execution contract**. Cross-engine production roles, adapter/provenance schema, parameter precedence, local-first privacy policy, version pinning and regression rules live in [`knowledge/design-intelligence.md`](knowledge/design-intelligence.md#generation-1-toolchain-maturity-contract). Each engine's `01-tools.md` owns only its tool-specific production disposition and parameter/execution deltas. Tool-native CLI defaults may be recorded there as versioned software behavior; assay/kit scientific values remain in numbered modules.

Generation 1 intentionally prioritizes mature, automatable existing tools. Experimental/ML methods, browser-only services and specialized topologies remain benchmark/reference/watchlist unless they meet explicit deployment, licensing, reproducibility and regression gates.

## Maintenance workflow

When new evidence arrives:

1. classify it as assay-specific, engine-shared, cross-engine, operational or historical;
2. update only the canonical owner;
3. add a link from dependent documents if discovery would otherwise be difficult;
4. preserve source/version conflicts instead of overwriting them;
5. run the documentation QA described in [`audits/current-state.md`](audits/current-state.md).

The active documentation surface intentionally stays small. Superseded audits and pre-refactor Markdown are removed from the current tree and remain recoverable from Git history or prior signed source bundles.
## Canonical machine-readable contracts

Generation-1 runtime semantics are no longer inferred only from prose. Four active JSON artifacts are normative:

- [`contracts/runtime-contract.schema.json`](contracts/runtime-contract.schema.json) — canonical enums and schemas for tool roles/qualifiers, coordinates, candidates, parameter resolution, database manifests, validation evidence, errors/refusals and tool-run provenance;
- [`contracts/toolchain-manifest.json`](contracts/toolchain-manifest.json) — canonical shared-tool identity, catalog disposition, exact accepted release policies, coordinate convention, parameter precedence and artifact-digest policy;
- [`contracts/engine-tool-contracts.json`](contracts/engine-tool-contracts.json) — canonical engine-scoped execution roles and purposes for the 11 engine toolchains;
- [`contracts/engine-tool-contracts.schema.json`](contracts/engine-tool-contracts.schema.json) — validation schema for the engine-scoped bindings.

If prose and these machine-readable contracts disagree on runtime field semantics, the contract/schema is the implementation authority and the prose must be corrected. Scientific numeric evidence remains owned by its assay/module documentation and evidence register.

