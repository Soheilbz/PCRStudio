# CURRENT Method Fidelity closure

**Status:** **PASS — source fidelity gate closed**
**Date:** 2026-09-06
**Canonical registry:** `contracts/method-fidelity.json`
**Generated review:** `knowledge/reviews/METHOD-FIDELITY-AUDIT.md`

PCRStudio now treats named-method identity as a scientific contract rather than a display label. Every public module declares the methods that are active, diagnostic, conditional, required follow-up, validator or external/reference authorities. Per-run active method fidelity is carried in provenance and contributes to the toolchain fingerprint; external/reference authorities are reported separately so a cited system is not mistaken for one that actually executed.

The canonical grades are F0 upstream-exact, F1 exact public component port, F2 manual-rule-faithful, F3 compatible/approximate and F4 external-authority-only. Scientific-Strict rejects F3 primary decision logic and never upgrades an F4 boundary by inventing unpublished or proprietary rules.

Key closures in this pass:

- **SADDLE:** the published Badness objective is kept separate from PCRStudio's deterministic local optimiser. Exact SADDLE simulated annealing remains an external-authority boundary until official decision-critical code/parameters are available; no cooling/stopping schedule is guessed.
- **Universal Primers:** the former cheap surrogate pre-ranking no longer eliminates candidates. Exact evaluation is used inside a bounded envelope and Scientific-Strict refuses an oversized search rather than thinning it heuristically.
- **LAMP:** the generic linear specificity proxy is diagnostic-only and cannot rank/eliminate LAMP sets. The named PrimerExplorer branch is explicitly a public-rule profile, not a clone of proprietary PrimerExplorer search/ranking; truncated internal search fails closed.
- **Tetra-ARMS:** the named Ye/Collins-Day public-method branch enforces the reviewed −2 deliberate mismatch, ≥26-nt inner-primer rule and mismatch-strength policy rather than inheriting the generalized ARMS heuristic.
- **ARMS/KASP:** generalized PCRStudio policies remain explicitly distinct from ARMSprimer3 and Kraken and are not Scientific-Strict primary methods.
- **RPA:** Primer3 is only an in-silico candidate source. Full assay development exposes the source-backed 8–10 forward × 8–10 reverse empirical matrix and Scientific-Strict requires at least the 8×8 preparation floor; sequence ranking is never called RPA validation.
- **QuikChange/NEBaseChanger:** public manual rules and PCRStudio routing are separated from Agilent/NEB proprietary web-tool equivalence claims.
- **MGB and other proprietary/incomplete methods:** remain content-bound external-authority/refusal paths rather than internal approximations.

The source audit also guards user-facing wording, RPA strict Web transport, generic-multiplex active/reference separation and Scientific-Strict enforcement. Dedicated method-fidelity regression tests cover generic multiplex, generalized ARMS/KASP, Tetra-ARMS and RPA empirical-matrix gates.

This closure is source-only. It does not assert Cargo/Next project builds, Linux/native execution, scientific executable qualification or wet-lab validation. All 21 public modules remain experimental until those later gates pass.
