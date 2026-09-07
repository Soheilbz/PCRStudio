# PCRStudio Scientific Integrity Policy

**Release invariant:** PCRStudio may return no candidate or a typed refusal. It may not make a scientific question easier by silently changing the assay, chemistry, evidence scope, backend, hard constraint, or validation claim.

## Strict is the release default

`PCRSTUDIO_SCIENTIFIC_POLICY=strict` is the default. `development` is an explicit engineering-only mode and cannot be interpreted as release-grade evidence. **Policy mode is not an assay-selection switch:** development may expose engineering diagnostics or an incomplete qualification posture, but it may not change assay identity, chemistry, required purpose, hard/bounded parameter authority, topology, named protocol semantics, or silently substitute a scientific algorithm.

## Non-negotiable rules

1. **Named identity is policy-invariant.** Every executable worker run carries an explicit canonical `assay.id`; development cannot synthesize an assay from unprofiled defaults.
2. **No PRIMARY substitution.** A failed PRIMARY algorithm/tool does not silently fall back to a different designer.
3. **No hard-gate relaxation.** Search windows may be explored more broadly only inside the same legal assay envelope.
4. **No anonymous chemistry substitution.** Polymerase/buffer/condition deviations require a separate named, sourced, versioned chemistry profile.
5. **No hidden purpose.** Multi-purpose profiles require an explicit purpose or an explicit versioned default.
6. **No guessed annealing core.** Specificity uses an explicit `annealing_sequence`; ordered 5′ tails/composite oligos are not searched as if they anneal in full.
7. **Production specificity is reproducible.** Production/approved BLAST and MFEprimer evidence requires source-FASTA and index-artifact fingerprints plus scope/release provenance.
8. **Heuristics are not scientific gates.** Ranking weights/tuning parameters act only after assay validity gates and are labelled as ranking logic.
9. **Capability honesty.** UI/API capabilities are exposed only when their assay-specific semantics are implemented end to end.
10. **Wet-lab evidence stays wet-lab evidence.** Sequence design does not infer efficiency, Cq, LOD/LOQ, threshold/rain, partition performance, cluster separation, yield or diagnostic performance.
11. **Refusal beats guessing.** Missing required context or unsupported chemistry/topology produces a typed refusal or explicit limited evidence.
12. **OPTIONAL evidence cannot steer the answer.** An `OPTIONAL`/`REFERENCE` tool may enrich the report, but its availability cannot change hard validity, deterministic ranking, or the default selected candidate. A decision-making tool must be promoted to an explicit required engine role.
13. **Bench protocols need an authority.** Where cycling/chemistry is kit- or platform-specific, PCRStudio requires/preserves the named authority and does not manufacture a generic bench programme from Tm, product length, or a surrogate preset.

The machine-readable authority is `knowledge/runtime/scientific-integrity-policy.json`; `scripts/audit-source.py` guards these rules against source drift.

## Named assay/profile identity

Every executable worker run requires an explicit canonical `assay.id`. Low-level pure/research helpers may remain independently callable for isolated engine research, but a worker request cannot use development mode to invent assay identity, chemistry, parameter authority, topology, purpose, or protocol semantics. Release orchestration additionally requires the server-injected canonical profile-authority marker.
