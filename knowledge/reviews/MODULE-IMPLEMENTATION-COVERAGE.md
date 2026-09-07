# PCRStudio Generation-1 — 21-Module Implementation Coverage

> Current static coverage record. This document distinguishes executable runtime bindings from evidence that remains source-scoped in the canonical Atlas.

## Interpretation

- **21/21 modules** resolve to one of **11 engines**.
- Every runtime numeric default below is copied from the active `crates/pcr-core/profiles.toml`; the generated JSON snapshot pins its SHA-256.
- Atlas Numeric Evidence is not automatically a runtime default. Study-, vendor-, protocol- and historical values activate only through the documented named profile/overlay or explicit contract.
- Hard scientific identities (variant/edit identity, topology, enzyme capability, KASP chemistry, LAMP geometry, nested containment, etc.) are refusal gates, not ranking weights.
- Native operational execution remains a separate Linux qualification gate; this record is static source/contract coverage.

## Module matrix

| Module | Engine | Runtime gates | Active numeric/profile binding | Coverage |
|---|---|---|---|---|
| `standard-pcr` | `flanking-pair` | `flanking_geometry`, `primer_thermodynamics`, `template_specificity` | `gc_clamp=0` | **PASS** |
| `long-range-pcr` | `flanking-pair` | `long_product_geometry`, `proofreading_capability`, `extension_protocol_compatibility` | `length_min=27`, `length_opt=30`, `length_max=36`, `tm_min=60.0`, `tm_opt=68.0`, `tm_max=74.0`, `gc_clamp=0`, `max_end_gc=3`, `product_min=5000`, `product_max=20000`, `polymerase=long-range`, `defaultPurpose=general` | **PASS** |
| `colony-pcr` | `flanking-pair` | `screen_product_geometry`, `host_class`, `colony_preparation_provenance`, `colony_lysis_profile`, `optional_vector_context`, `predicted_screen_status`; required context: `colony_host_class, colony_preparation, colony_protocol_name` | `polymerase=taq-standard`, `defaultPurpose=screen`, `purposes=general,screen,sanger` | **PASS** |
| `nested-pcr` | `nested` | `outer_pair`, `inner_pair`, `strict_containment`, `round_specificity`, `cross_round_interaction`, `single_tube_supported_mechanism_if_selected`, `single_tube_generic_fail_closed_unless_supported_mechanism` | engine-/module-owned typed contract; no generic numeric profile block | **PASS** |
| `inverse-pcr` | `outward-pair` | `circular_or_digest_topology`, `named_branch_identity`, `outward_orientation`, `junction_reconstruction`, `per_end_phosphate_state`, `circularization_provenance`, `linear_control_provenance`, `methylation_branch`, `unknown_flank_bounds`, `primer_to_junction_product_path`, `predicted_result_status` | engine-/module-owned typed contract; no generic numeric profile block | **PASS** |
| `qpcr-sybr` | `flanking-pair` | `short_qpcr_product`, `primer_specificity`, `dimer_sensitivity`, `shared_tm` | `product_min=80`, `product_max=200`, `tm_min=59.0`, `tm_opt=60.0`, `tm_max=65.0`, `tm_pair_max_difference=3.0`, `length_min=18`, `length_opt=20`, `length_max=24`, `gc_min=40.0`, `gc_max=60.0`, `gc_clamp=0`, `max_end_gc=3`, `max_poly_x=4`, `polymerase=qpcr-dye`, `defaultPurpose=general` | **PASS** |
| `qpcr-probe` | `pair-and-probe` | `primer_pair`, `probe_inside_product`, `probe_tm_offset`, `probe_structure`, `primer_probe_interactions`, `optical_configuration` | `product_min=70`, `product_max=200`, `tm_min=59.0`, `tm_opt=60.0`, `tm_max=65.0`, `tm_pair_max_difference=3.0`, `length_min=18`, `length_opt=20`, `length_max=27`, `gc_min=30.0`, `gc_max=65.0`, `gc_clamp=0`, `max_end_gc=4`, `max_poly_x=4`, `polymerase=qpcr-dye` | **PASS** |
| `digital-pcr` | `flanking-pair` | `short_product`, `partition_compatible_assay`, `partition_format`, `platform_identity`, `fragmentation_state`, `specificity`, `shared_tm`, `measured_run_quantification_boundary`; required context: `digital_partition_format, digital_platform_name, digital_fragmentation_state` | `polymerase=digital-pcr`, `defaultPurpose=general`, `purposes=general`, `constraints.product_min=60`, `constraints.product_max=150`, `constraints.length_min=18`, `constraints.length_opt=20`, `constraints.length_max=24`, `constraints.tm_min=59.0`, `constraints.tm_opt=60.0`, `constraints.tm_max=65.0`, `constraints.gc_min=40.0`, `constraints.gc_max=60.0`, `constraints.gc_clamp=0`, `constraints.max_end_gc=3`, `constraints.tm_pair_max_difference=2.0`, `constraints.max_poly_x=3` | **PASS** |
| `arms-pcr` | `discriminating-pair` | `variant_normalization`, `three_prime_allele_identity`, `polymerase_mismatch_behavior`, `differential_extension` | `tm_min=55.0`, `tm_opt=61.0`, `tm_max=68.0`, `tm_pair_max_difference=5.0`, `length_min=17`, `length_opt=22`, `length_max=30`, `gc_min=30.0`, `gc_max=75.0`, `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=4`, `product_min=120`, `product_max=500`, `polymerase=taq-standard` | **PASS** |
| `tetra-primer-arms` | `discriminating-pair` | `variant_normalization`, `four_primer_geometry`, `diagnostic_band_separation`, `multi_oligo_interactions` | `tm_min=55.0`, `tm_opt=61.0`, `tm_max=68.0`, `tm_pair_max_difference=5.0`, `length_min=17`, `length_opt=22`, `length_max=30`, `gc_min=30.0`, `gc_max=75.0`, `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=4`, `product_min=120`, `product_max=500`, `polymerase=taq-standard` | **PASS** |
| `kasp` | `discriminating-pair` | `variant_normalization`, `explicit_assay_mode`, `kasp_endpoint_fret_chemistry`, `nonproofreading_polymerase`, `allele_specific_cores`, `common_primer_geometry`, `standard_lgc_product_max_100bp`, `fixed_fam_hex_tail_assignment`, `singleplex_readout`, `annealing_vs_ordered_sequence`, `target_aware_specificity` | `tm_min=55.0`, `tm_opt=61.0`, `tm_max=68.0`, `tm_pair_max_difference=5.0`, `length_min=17`, `length_opt=22`, `length_max=30`, `gc_min=30.0`, `gc_max=75.0`, `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=4`, `product_min=61`, `product_max=100`, `polymerase=taq-standard`, `chemistryFamily=kasp-endpoint-fret` | **PASS** |
| `species-specific-pcr` | `flanking-pair` | `target_inclusivity`, `required_exclusion_background`, `product_specificity` | `gc_clamp=0`, `polymerase=taq-standard` | **PASS** |
| `lamp` | `loop-set` | `f3_b3`, `f2_b2`, `f1c_b1c`, `inner_primer_composition`, `spacing_geometry`, `loop_primer_geometry`, `target_inclusivity_when_supplied`, `finite_six_region_background_topology_when_supplied`, `indexed_lamp_specificity_evidence_for_large_scope`, `set_interaction_risk_review`, `independent_lamp_specificity_evidence` | `polymerase=bst` | **PASS** |
| `rpa` | `flanking-pair` | `rpa_compatible_chemistry`, `rpa_primer_profile`, `target_specificity` | `length_min=30`, `length_opt=32`, `length_max=35`, `tm_min=50.0`, `tm_opt=75.0`, `tm_max=100.0`, `tm_pair_max_difference=100.0`, `gc_min=30.0`, `gc_max=70.0`, `gc_clamp=0`, `max_poly_x=5`, `product_min=100`, `product_max=200`, `min_three_prime_distance=1`, `polymerase=rpa` | **PASS** |
| `universal-primers` | `consensus-pair` | `msa`, `conservation`, `degeneracy`, `member_coverage`, `conserved_pair_geometry` | `tm_min=47.0`, `tm_max=71.0`, `tm_pair_max_difference=16.0`, `gc_min=25.0`, `gc_max=78.0`, `length_min=17`, `length_opt=20`, `length_max=27`, `product_min=250`, `product_max=1500`, `max_poly_x=5`, `tm_spread_max=5.0`, `max_degeneracy=64`, `conserved_end=3`, `min_coverage=1.0`, `min_three_prime_distance=5`, `cycling.cycles=35`, `cycling.anneal_seconds=60`, `cycling.final_extend_seconds=600` | **PASS** |
| `tiled-scheme` | `tiling-scheme` | `coverage`, `amplicon_overlap`, `pool_separation`, `variant_risk`, `interaction_audit`, `repairability` | `product_min=300`, `product_max=500`, `tm_min=59.0`, `tm_opt=61.0`, `tm_max=64.0`, `tm_pair_max_difference=2.0`, `length_min=20`, `length_opt=24`, `length_max=30`, `gc_min=30.0`, `gc_max=65.0`, `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=5`, `polymerase=proofreading` | **PASS** |
| `race` | `single-primer` | `boundary`, `extension_direction`, `adapter_partner_identity`, `substrate_preparation_provenance`, `nested_round_state`, `single_primer_specificity`, `candidate_transcript_end_claim_boundary`; required context: `race_direction, race_adapter, race_substrate, race_preparation, race_round` | `polymerase=long-range`, `purposes=general,cloning,sequencing`, `constraints.tm_min=64.0`, `constraints.tm_opt=68.0`, `constraints.tm_max=72.0`, `constraints.length_min=23`, `constraints.length_opt=26`, `constraints.length_max=30`, `constraints.gc_min=45.0`, `constraints.gc_max=65.0`, `constraints.gc_clamp=1`, `constraints.max_end_gc=3`, `constraints.max_poly_x=4` | **PASS** |
| `sequencing-primer` | `single-primer` | `read_direction`, `readable_distance`, `single_binding`, `instrument_handoff`, `trace_quality_unresolved_until_run` | `polymerase=taq-standard`, `purposes=general`, `constraints.tm_min=52.0`, `constraints.tm_opt=55.0`, `constraints.tm_max=62.0`, `constraints.length_min=18`, `constraints.length_opt=20`, `constraints.length_max=27`, `constraints.gc_min=40.0`, `constraints.gc_max=60.0`, `constraints.gc_clamp=1`, `constraints.max_end_gc=3`, `constraints.max_poly_x=4` | **PASS** |
| `gibson-assembly` | `junction-primers` | `fragment_order`, `junction_normalization`, `annealing_cores`, `overlap_composition`, `whole_oligo_structure`, `construct_reconstruction` | `tm_min=58.0`, `tm_opt=60.0`, `tm_max=65.0`, `tm_pair_max_difference=3.0`, `length_min=18`, `length_opt=20`, `length_max=25`, `gc_min=40.0`, `gc_max=60.0`, `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=4`, `product_min=200`, `product_max=10000`, `polymerase=proofreading` | **PASS** |
| `restriction-cloning` | `flanking-pair` | `restriction_site_policy`, `tail_composition`, `frame_or_product_verification`, `annealing_core_quality` | `polymerase=proofreading`, `defaultPurpose=cloning` | **PASS** |
| `site-directed-mutagenesis` | `mutagenic-pair` | `edit_normalization`, `edited_reference`, `edit_spanning_geometry`, `whole_oligo_quality`, `edited_product_verification` | `tm_min=60.0`, `tm_opt=65.0`, `tm_max=72.0`, `length_min=22`, `length_opt=28`, `length_max=35`, `gc_min=40.0`, `gc_max=65.0`, `gc_clamp=1`, `max_end_gc=3`, `max_poly_x=4`, `polymerase=proofreading` | **PASS** |

## Explicitly resolved Atlas software gaps

### KASP

- Replaced the legacy `qpcr-dye` identity with `polymerase=taq-standard` for the computation preset **plus** the separate typed `chemistryFamily=kasp-endpoint-fret`.
- Standard LGC branch no longer inherits the generic `120–500 bp` product window: active profile is `61–100 bp`; `61` is explicitly documented as the software geometry floor `(2 × 30 nt) + 1`, not a universal KASP biological minimum.
- KASP mode is explicit and topology-separated in R16. `biallelic-genotype` is executable for SNV/MNV, while `plus-minus-presence-absence` is executable for insertion/deletion/complex/presence–absence junction-aware designs. Endpoint FAM/HEX evidence remains observational: PCRStudio does not invent universal cluster thresholds, hidden genotype calls, or Kraken-equivalent behavior.
- LGC named overlay retains 96/384-well reaction branch, instrument context, ROX/reference-dye policy, FAM/HEX endpoint readout, NTC guidance and singleplex status.
- Tail sequence is part of the ordered oligo but excluded from first-round annealing Tm/specificity core semantics.

### Inverse PCR

- Added typed preparation branch, per-end phosphate state, circularization provenance, linear-control provenance, methylation branch and unknown-flank bounds.
- Product length is never inferred from the known span. Each pair serializes the primer→unknown-flank→ligation-junction→known-span path and an exact/bounded/unresolved unknown interval.
- Design output status is `predicted`; `amplified` and `sequence-confirmed` are reserved for later external bench evidence.

### Nested PCR one-tube mode

- The optional one-tube path declares the supported `thermal-switch` mechanism and serializes the internal `10 °C` Tm-window refusal boundary in the result.
- The `10 °C` value is explicitly labeled `pcrstudio-internal-conservative-heuristic`, not a universal nested-PCR scientific default.
- Polymerase compatibility is enforced for the supported mechanism; concentration ratios, cleanup products and cycling remain named-protocol/user-resolved rather than silently inferred.

## Intentional non-implementation boundaries

- Unvalidated or insufficiently specified branches in the Atlas remain explicit refusals/unresolved states rather than invented algorithms.
- Named vendor protocol numbers only activate when that named overlay is selected.
- External validators supply evidence; they do not automatically override assay-aware engine logic unless the interpretation contract is target-aware.
- Strict toolchain mode refuses missing/mismatched pinned artifacts rather than silently changing backend behavior.
