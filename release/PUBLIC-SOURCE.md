# PCRStudio CURRENT public source

This tree is the cleaned CURRENT public-source form of PCRStudio for Linux x86_64.
It is built on the Generation 1 foundation. It retains only current release evidence
plus the immutable R15 file-manifest baseline required by release tooling.
Superseded checkpoint/audit history and obsolete release-control scripts are not
part of the public bundle.

The unified Generation 1 engine registry covers: Outward Pair / Inverse
PCR, Pair and Probe / qPCR Probe, Single Primer / RACE + Sequencing Primer, and
Tiling Scheme. Conventional named hydrolysis-probe profiles execute directly; MGB/NFQ uses a
hash-bound external-authority export/import workflow and PCRStudio never invents MGB Tm.
FirstChoice RLM-RACE is versioned to its canonical authority; SMARTer current design is
executable only with the exact caller-supplied partner plus content-addressed SOP/manual
revision. PrimalScheme/Olivar remain independent tiling backends; circular scheme creation,
native visual evidence, depth/dropout repair handoff and scheme/version diff are surfaced with provenance.

The current candidate's source, runtime, Docker/OCI, and release evidence is indexed under [`release/current/README.md`](current/README.md); source-only audits remain clearly scoped and do not replace native or wet-lab gates.

Method-fidelity closure is part of the current source candidate. `contracts/method-fidelity.json` classifies every public module's named methods as upstream-exact, exact public component port, manual-rule-faithful, compatible/approximate, or external-authority-only. The source gate prevents Scientific-Strict primary decisions from using an ineligible approximation and keeps active run methods separate from reference/vendor authorities. The generated review is `knowledge/reviews/METHOD-FIDELITY-AUDIT.md`.

Generated projections are read-only derivatives of canonical sources. Do not
hand-edit them to make a qualification check pass.

For release qualification follow `release/current/CURRENT-LINUX-QUALIFICATION.md`.
