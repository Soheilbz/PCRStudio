# PCRStudio Generation-1 full-system static review — current public source

**Scope:** static source review against the canonical scientific Atlas and runtime contracts. Native builds, scientific executables, databases, browser flows, and wet-lab behavior remain separate qualification/evidence gates.

## Verdict

- **Scientific/contract baseline:** PASS — the embedded 57-file Atlas is byte-for-byte identical to the canonical Atlas supplied for this project.
- **21 module / 11 engine topology:** PASS — module IDs, engine assignments, worker commands, hard-gate families, fallback declarations and UI page plans agree across Rust profile data, Python runtime contract and runtime JSON registry.
- **Engine/tool bindings:** PASS after correction — runtime roles, purposes, operations **and artifact identity strings** now exactly mirror the Atlas contract for all 11 engines.
- **Sequence molecule semantics:** PASS — supplier-ready ordered sequence, template-binding annealing core and 5′ tail are kept distinct; specificity uses binding core while interaction/structure checks can use the full ordered oligo.
- **Independent validation authority:** PASS — MFEprimer/BLAST/PrimerPooler evidence is explicit and advisory unless a target-aware interpretation contract makes a biological selection consequence reproducible.
- **Reproducibility mode:** strengthened — strict mode requires the pinned MAFFT 7.526 alignment authority and PrimalScheme3 3.3.0 primary tiled-scheme backend; it does not silently substitute another aligner or the internal tiling walker.
- **Wet-lab claim boundary:** PASS — all 21 profiles remain `experimental`; the result envelope separates computational completion, external evidence and wet-lab validation.
- **UX architecture:** PASS with implemented upgrades — assay-specific workflows, compact result orientation, progressive disclosure, verified examples, reduced-motion handling and non-absolute ranking language are now contractual.

## Canonical pipeline authority

```text
UI / assay selection
  → request schema + module resolution
  → input / coordinate / chemistry normalization
  → engine-specific candidate generation
  → assay hard gates
  → thermodynamics / structure / interaction evaluation
  → request-context specificity / inclusivity
  → deterministic ranking + stable tie-break
  → controlled fallback only where declared
  → independent local toolchain evidence
  → verification / provenance envelope
  → typed API result
  → assay-specific result UI / compare / export
```

**Important authority boundary:** database or external-tool hits are not treated as automatic off-target failures merely because they exist. Intended target identity, background scope, orientation/product semantics and database snapshot must make the interpretation explicit before evidence is allowed to change selection.

## Module-by-module contract coverage

| Module | Engine | Worker | Hard-gate families | Declared fallback | UI steps | Result view |
| --- | --- | --- | --- | --- | ---: | --- |
| `standard-pcr` (Standard PCR) | `flanking-pair` | `run` | flanking_geometry, primer_thermodynamics, template_specificity | `controlled_constraint_relaxation` | 5 | `DesignResultView` |
| `long-range-pcr` (Long-range PCR) | `flanking-pair` | `run` | long_product_geometry, proofreading_capability, extension_protocol_compatibility | `never_relax_polymerase_capability` | 5 | `DesignResultView` |
| `colony-pcr` (Colony PCR) | `flanking-pair` | `run` | screen_product_geometry, colony_lysis_profile, optional_vector_context | `preserve_colony_protocol` | 5 | `DesignResultView` |
| `nested-pcr` (Nested PCR) | `nested` | `nested` | outer_pair, inner_pair, strict_containment, round_specificity, cross_round_interaction, single_tube_supported_mechanism_if_selected, single_tube_generic_fail_closed_unless_supported_mechanism | `outer_and_inner_profiles_relax_independently` | 4 | `NestedResultView` |
| `inverse-pcr` (Inverse PCR) | `outward-pair` | `inverse` | circular_or_digest_topology, named_branch_identity, outward_orientation, junction_reconstruction, per_end_phosphate_state, circularization_provenance, linear_control_provenance, methylation_branch, unknown_flank_bounds, primer_to_junction_product_path, predicted_result_status | `never_invent_topology_unknown_flank_or_bench_status` | 5 | `OutwardResultView` |
| `qpcr-sybr` (qPCR — Intercalating Dye) | `flanking-pair` | `run` | short_qpcr_product, primer_specificity, dimer_sensitivity, shared_tm | `qpcr_bounds_only` | 5 | `DesignResultView` |
| `qpcr-probe` (qPCR — Hydrolysis Probe) | `pair-and-probe` | `probe` | primer_pair, probe_inside_product, probe_tm_offset, probe_structure, primer_probe_interactions, optical_configuration | `relax_search_window_before_probe_quality` | 5 | `ProbeResultView` |
| `digital-pcr` (Digital PCR) | `flanking-pair` | `run` | short_product, partition_compatible_assay, specificity, shared_tm | `digital_pcr_profile_only` | 5 | `DesignResultView` |
| `arms-pcr` (ARMS-PCR) | `discriminating-pair` | `discriminate` | variant_normalization, three_prime_allele_identity, polymerase_mismatch_behavior, differential_extension | `preserve_discrimination` | 5 | `DiscriminatingResultView` |
| `tetra-primer-arms` (Tetra-primer ARMS) | `discriminating-pair` | `discriminate` | variant_normalization, four_primer_geometry, diagnostic_band_separation, multi_oligo_interactions | `preserve_diagnostic_geometry` | 5 | `DiscriminatingResultView` |
| `kasp` (KASP) | `discriminating-pair` | `discriminate` | variant_normalization, explicit_assay_mode, kasp_endpoint_fret_chemistry, nonproofreading_polymerase, allele_specific_cores, common_primer_geometry, standard_lgc_product_max_100bp, fixed_fam_hex_tail_assignment, singleplex_readout, annealing_vs_ordered_sequence, target_aware_specificity | `never_relax_discrimination_chemistry_or_standard_lgc_product_ceiling` | 5 | `DiscriminatingResultView` |
| `species-specific-pcr` (Species-specific PCR) | `flanking-pair` | `run` | target_inclusivity, required_exclusion_background, product_specificity | `never_drop_exclusion_background` | 5 | `DesignResultView` |
| `lamp` (LAMP) | `loop-set` | `loop_set` | `f3_b3`, `f2_b2`, `f1c_b1c`, `inner_primer_composition`, `spacing_geometry`, `loop_primer_geometry`, `target_inclusivity_when_supplied`, `finite_six_region_background_topology_when_supplied`, `indexed_lamp_specificity_evidence_for_large_scope`, `set_interaction_risk_review`, `independent_lamp_specificity_evidence` | `role_by_role_search_with_unchanged_lamp_geometry` | 4 | `LoopSetResultView` |
| `rpa` (RPA) | `flanking-pair` | `run` | rpa_compatible_chemistry, rpa_primer_profile, target_specificity | `preserve_rpa_chemistry` | 5 | `DesignResultView` |
| `universal-primers` (Universal Primers) | `consensus-pair` | `universal` | msa, conservation, degeneracy, member_coverage, conserved_pair_geometry | `declared_alignment_fallback_then_controlled_degeneracy` | 4 | `UniversalResultView` |
| `tiled-scheme` (Tiled Amplicon Scheme) | `tiling-scheme` | `tiling` | coverage, amplicon_overlap, pool_separation, variant_risk, interaction_audit, repairability | `primalscheme_to_internal_only_in_auto_mode` | 4 | `TilingResultView` |
| `race` (RACE) | `single-primer` | `single` | boundary, extension_direction, adapter_context, single_primer_specificity | `boundary_aware_window_relaxation` | 5 | `SingleResultView` |
| `sequencing-primer` (Sequencing Primer) | `single-primer` | `single` | read_direction, readable_distance, single_binding, sequence_quality | `read_window_relaxation` | 5 | `SingleResultView` |
| `gibson-assembly` (Gibson Assembly) | `junction-primers` | `junction` | fragment_order, junction_normalization, annealing_cores, overlap_composition, whole_oligo_structure, construct_reconstruction | `preserve_junction_identity` | 4 | `JunctionResultView` |
| `restriction-cloning` (Restriction Cloning) | `flanking-pair` | `run` | restriction_site_policy, tail_composition, frame_or_product_verification, annealing_core_quality | `preserve_required_sites_and_product` | 5 | `DesignResultView` |
| `site-directed-mutagenesis` (Site-directed Mutagenesis) | `mutagenic-pair` | `mutagenic` | edit_normalization, edited_reference, edit_spanning_geometry, whole_oligo_quality, edited_product_verification | `never_relax_edit_identity` | 4 | `MutagenicResultView` |

All 21 public profiles are intentionally still marked **experimental**. This means computational design can be complete while wet-lab performance remains unclaimed until empirical validation is recorded.

## Engine/tool execution coverage

| Engine | Public modules | Binding count | Primary authorities | Independent validators / optional evidence |
| --- | ---: | ---: | --- | --- |
| `consensus-pair` | 1 | 5 | `mafft` (PRIMARY), `primer3_core` (PRIMARY), `pcrstudio_consensus_resolver` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR) |
| `discriminating-pair` | 3 | 4 | `primer3_core` (PRIMARY), `pcrstudio_allele_wrapper` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR) |
| `flanking-pair` | 8 | 8 | `primer3_core` (PRIMARY), `pcrstudio_flanking_wrapper` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR), `primerpooler` (OPTIONAL), `viennarna` (OPTIONAL), `primer_blast` (REFERENCE), `nupack4` (REFERENCE) |
| `junction-primers` | 1 | 5 | `primer3_core` (PRIMARY), `pcrstudio_junction_composer` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR), `pydna` (OPTIONAL) |
| `loop-set` | 1 | 4 | `primer3_core` (PRIMARY), `pcrstudio_lamp_enumerator` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR) |
| `mutagenic-pair` | 1 | 5 | `primer3_core` (PRIMARY), `pcrstudio_edit_normalizer` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR), `pydna` (OPTIONAL) |
| `nested` | 1 | 5 | `primer3_core` (PRIMARY), `pcrstudio_nested_containment` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR), `primerpooler` (OPTIONAL) |
| `outward-pair` | 1 | 5 | `primer3_core` (PRIMARY), `pcrstudio_topology_resolver` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR), `pydna` (OPTIONAL) |
| `pair-and-probe` | 1 | 6 | `primer3_core` (PRIMARY), `pcrstudio_probe_wrapper` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR), `viennarna` (OPTIONAL), `primer_blast` (REFERENCE) |
| `single-primer` | 2 | 4 | `primer3_core` (PRIMARY), `pcrstudio_single_primer_wrapper` (PRIMARY) | `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR) |
| `tiling-scheme` | 1 | 6 | `mafft` (PRIMARY), `primalscheme3` (PRIMARY), `pcrstudio_scheme_wrapper` (PRIMARY) | `primerpooler` (VALIDATOR), `mfeprimer` (VALIDATOR), `ncbi_blast_plus` (VALIDATOR) |

## Deep findings retained in the current source

1. **Artifact identity parity was stricter than the previous audit.** The Python binding helper used `inherit:toolchain-manifest` while the Atlas says `inherit:toolchain-manifest.json`. This is now exact, so provenance is not dependent on an implicit filename convention.
2. **Strict alignment is now truly strict.** A strict run that cannot resolve the pinned MAFFT 7.526 Linux artifact fails with a diagnostic rather than silently changing the scientific backend.
3. **5′ extensions do not contaminate specificity interpretation.** Specificity evidence uses `annealing_sequence`; ordered/full oligos remain available to hairpin/dimer/pooling logic. This matters for KASP tails, cloning tails, Gibson overlaps and composite LAMP oligos.
4. **The result recommendation is no longer presented as a universal “best primer”.** Rank 1 is described as top-ranked under the active assay profile and evidence state.
5. **The selected-pair view is internally coherent.** Pair selection now drives the full card, gel/off-target visualization and cycling panel together instead of leaving the gel anchored to rank 1.
6. **Onboarding sample sequences are provenance-backed.** The four UI examples are copied from the versioned NCBI corpus and coupled to accession, length and normalized-sequence SHA-256.

## Static integrity evidence

- File-count evidence is maintained in `release/current/CURRENT-STATIC-CONSISTENCY-AUDIT.md`; this review does not duplicate a stale repository count.
- Python parse evidence is maintained in the current static-source audit.
- JSON/TOML parse evidence is maintained in the current static-source audit.
- Linux path/reserved-name/case-collision hygiene is part of the current static-source audit.
- Linux-invalid/reserved names: **0**; case-insensitive collisions: **0**; symlinks: **0**; cache/bytecode/build artifacts: **0**.
- Runtime JSON schemas: draft 2020-12 valid; module registry validates against its schema.
- Canonical Atlas files: **57/57 identical** to the supplied canonical Atlas.
- Current static-audit disposition is recorded under `release/current/`.

## What this audit deliberately does not claim

- It does **not** claim the Linux build has compiled or that any pinned external binary has run. Those are host-only acceptance gates.
- It does **not** claim wet-lab amplification, efficiency, LOD/LOQ, diagnostic sensitivity/specificity or assay robustness from sequence design alone.
- It does **not** convert a finite local database scan into a claim of universal specificity.
- It does **not** treat an alternative aligner as reproducibly equivalent to MAFFT, or the internal tiling walker as equivalent to PrimalScheme3, in strict mode.

## Native acceptance gate

The release operator must run the complete Python/Rust/TypeScript build and tests, the 21-module smoke matrix, pinned-tool fixtures, database-snapshot checks, path-with-spaces tests and accessibility checks **on Linux**. Runtime failures must be corrected without weakening scientific hard gates.
