# PCRStudio LAMP Evidence Ledger

Generated: 2026-09-04

This ledger maps every major LAMP decision class to its source, executable implementation, regression evidence and claim boundary. It deliberately separates mechanistic invariants, compatibility constraints, evidence-weighted preferences, soft risk diagnostics and research-only signals.

## LAMP-MECH-001 — core six-region topology and composite inner primers

- **Decision role:** `hard_mechanistic_invariant`
- **Status:** `implemented`
- **Source:** Loop-mediated isothermal amplification of DNA (2000). https://pmc.ncbi.nlm.nih.gov/articles/PMC102748/. DOI: `10.1093/nar/28.12.e63`. Authority: `foundational_peer_reviewed`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::check_geometry`, `tools/src/pcr_tools/loop_set.py::oligos`
- **Regression evidence:** `test_the_composite_primers_are_built_back_to_front`, `test_the_eight_regions_are_in_order_along_the_plus_strand`
- **Claim boundary:** Mechanistic topology is enforceable in silico; amplification performance remains empirical.

## LAMP-LOOP-001 — optional LF/LB loop primers

- **Decision role:** `mechanistic_optional_feature`
- **Status:** `implemented`
- **Source:** Accelerated reaction by loop-mediated isothermal amplification using loop primers (2002). https://pubmed.ncbi.nlm.nih.gov/12144774/. DOI: `10.1006/mcpr.2002.0415`. Authority: `peer_reviewed`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::candidates`, `tools/src/pcr_tools/loop_set.py::sets`
- **Regression evidence:** `test_a_four_primer_core_is_not_refused_when_no_loop_primer_can_fit`, `test_optional_loop_primers_survive_selection_without_overriding_interaction_risk`, `test_loop_alternatives_keep_no_loop_and_bounded_candidates_for_set_level_ranking`
- **Claim boundary:** Loop primers are optional and may accelerate LAMP; PCRStudio preserves the four-primer alternative and does not let loop count override stronger interaction-risk evidence.

## LAMP-V5-001 — PrimerExplorer V5 public-rule windows and terminal stability

- **Decision role:** `versioned_compatibility_constraint`
- **Status:** `implemented`
- **Source:** PrimerExplorer V5 Manual (accessed 2026-09-02; publication year not asserted). https://primerexplorer.eiken.co.jp/e/v5_manual/02.html. Authority: `vendor_primary_documentation`.
- **Source:** PrimerExplorer V5 Manual PDF (accessed 2026-09-02; publication year not asserted). https://primerexplorer.eiken.co.jp/e/v5_manual/pdf/PrimerExplorerV5_Manual.pdf. Authority: `vendor_primary_documentation`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::PRIMEREXPLORER_V5_GEOMETRY`, `tools/src/pcr_tools/loop_set.py::primerexplorer_v5_tm`, `tools/src/pcr_tools/loop_set.py::primerexplorer_v5_end_dg`
- **Regression evidence:** `test_geometry_profile_is_versioned_and_does_not_silently_widen_v5`, `test_primerexplorer_v5_tm_matches_the_manual_figure_1_10_reference_outputs`, `test_primerexplorer_v5_end_dg_matches_manual_figure_1_10_reference_outputs`, `test_primerexplorer_v5_figure_1_4_coordinates_match_loop_geometry_convention`, `test_the_end_stability_threshold_is_measured_over_six_bases_not_five`, `test_loop_primer_uses_the_published_v5_loop_end_stability_threshold`
- **Claim boundary:** PCRStudio reproduces the reviewed V5 geometry convention and the public Figure 1.10 Tm/terminal-six-base ΔG numeric outputs within declared regression tolerances. Regular critical ends use the reviewed −4 kcal/mol criterion, while LF/LB use the separate V5 loop-primer screen's published 3′ stability threshold of −2 kcal/mol. It does not claim to clone PrimerExplorer's proprietary candidate-generation/search algorithm. The core critical-end policy follows Eiken's role-specific −4 kcal/mol guidance rather than claiming identity with every generic Expert-Mode 5′/3′ field, and PrimerExplorer's own dimer-check threshold is not transplanted into Primer3 because the thermodynamic models are not assumed numerically interchangeable; set-level structure evidence is evaluated separately.

## LAMP-NEB-2025-001 — evidence profile geometry and preferred windows

- **Decision role:** `evidence_weighted_profile`
- **Status:** `implemented`
- **Source:** LAMP Primer Design using the NEB LAMP Primer Design Tool: Critical Considerations for Assay Robustness, Speed and Sensitivity (2025). https://media.neb.com/m/cc0bbc21ec612a7/original/LAMP_TechNote_0425.pdf. Authority: `vendor_technical_note`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::PCRSTUDIO_EVIDENCE_2026_GEOMETRY`, `tools/src/pcr_tools/loop_set.py::Set.evidence_rank`
- **Regression evidence:** `test_evidence_profile_outer_gap_preference_is_separate_from_validity`
- **Claim boundary:** 0–60 bp outer-gap eligibility follows the current NEB tool default; 15–60 bp is descriptive “generally good” guidance and 40–60 bp is the active soft preference. These do not silently alter V5 compatibility.

## LAMP-LINKER-001 — FIP/BIP junction linker

- **Decision role:** `explicit_research_variant`
- **Status:** `implemented`
- **Source:** Loop-mediated isothermal amplification of DNA (2000). https://pmc.ncbi.nlm.nih.gov/articles/PMC102748/. DOI: `10.1093/nar/28.12.e63`. Authority: `foundational_peer_reviewed`.
- **Source:** Evaluation of the effect of outer primer structure, and inner primer linker sequences, in the performance of LAMP (2023). https://www.sciencedirect.com/science/article/pii/S0039914023003934. DOI: `10.1016/j.talanta.2023.124642`. Authority: `peer_reviewed`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::inner_linker_for`, `tools/src/pcr_tools/loop_set.py::oligos`, `tools/src/pcr_tools/external_validation.py::_lamp_blast_region_queries`
- **Regression evidence:** `test_tttt_linker_is_explicit_and_kept_separate_from_target_tail`, `test_lamp_blast_queries_split_composite_oligos_and_exclude_synthetic_linker`
- **Claim boundary:** TTTT is an explicit option, not a universal-best default; genomic searches exclude the synthetic linker.

## LAMP-STRUCT-001 — hairpin/self-dimer/cross-dimer/3-prime interaction

- **Decision role:** `soft_risk_ranker`
- **Status:** `implemented`
- **Source:** LAMPrimers iQ: New primer design software for loop-mediated isothermal amplification (2024). https://pubmed.ncbi.nlm.nih.gov/37924966/. DOI: `10.1016/j.ab.2023.115376`. Authority: `peer_reviewed`.
- **Source:** High-temperature ssBP-LAMP breaks the barrier of nonspecific amplification and unlocks the full potential of LAMP diagnostics (2026). https://pmc.ncbi.nlm.nih.gov/articles/PMC13281569/. DOI: `10.1186/s11658-026-00926-8`. Authority: `peer_reviewed`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::three_prime_interaction_risk`, `tools/src/pcr_tools/loop_set.py::interactions`, `tools/src/pcr_tools/loop_set.py::_thermodynamic_structure_rank`
- **Regression evidence:** `test_a_deliberately_complementary_pair_is_flagged`, `test_uncomputed_pairwise_structure_does_not_rank_as_best_evidence`
- **Claim boundary:** Structure evidence changes risk/ranking but no universal ΔG threshold is treated as a wet-lab success/failure oracle.

## LAMP-SPEC-001 — finite-background six-region specificity with mismatches

- **Decision role:** `set_level_specificity_evidence`
- **Status:** `implemented`
- **Source:** GLAPD: Whole Genome Based LAMP Primer Design for a Set of Target Genomes (2020). https://pmc.ncbi.nlm.nih.gov/articles/PMC6923652/. Authority: `peer_reviewed`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::_lamp_sequence_sites`, `tools/src/pcr_tools/loop_set.py::_lamp_background_topology_audit`
- **Regression evidence:** `test_six_region_background_topology_detects_exact_and_mismatch_tolerant_loci`, `test_six_region_background_topology_is_orientation_invariant`
- **Claim boundary:** Direct matcher is ungapped, substitution-only, <=2 mismatches per region and finite-background scoped; a clean result is only clean within that model.

## LAMP-SPEC-002 — indexed BLAST six-region locus reconstruction

- **Decision role:** `external_set_level_specificity_evidence`
- **Status:** `implemented`
- **Source:** GLAPD: Whole Genome Based LAMP Primer Design for a Set of Target Genomes (2020). https://pmc.ncbi.nlm.nih.gov/articles/PMC6923652/. Authority: `peer_reviewed`.
- **Source:** NCBI BLAST+ (2026). https://blast.ncbi.nlm.nih.gov/doc/blast-help/downloadblastdata.html. Authority: `primary_tool_documentation`.
- **Implementation:** `tools/src/pcr_tools/external_validation.py::_lamp_blast_region_queries`, `tools/src/pcr_tools/external_validation.py::_blast_lamp_topology`
- **Regression evidence:** `test_blast_lamp_topology_detects_reverse_complement_locus`, `test_blast_lamp_topology_surfaces_upstream_hit_truncation_without_clean_claim`, `test_blast_lamp_topology_indexes_out_geometrically_impossible_decoys`, `test_lamp_blast_queries_split_composite_oligos_and_exclude_synthetic_linker`
- **Claim boundary:** All six core regions are queried for topology reconstruction and optional LF/LB are queried as site-level evidence without becoming required topology roles. Hit truncation and bounded topology assembly are surfaced; incomplete hit collection cannot yield a clean proof.

## LAMP-INCL-001 — target-panel inclusivity/conservation

- **Decision role:** `target_coverage_evidence`
- **Status:** `implemented`
- **Source:** GLAPD: Whole Genome Based LAMP Primer Design for a Set of Target Genomes (2020). https://pmc.ncbi.nlm.nih.gov/articles/PMC6923652/. Authority: `peer_reviewed`.
- **Source:** Profiling RT-LAMP tolerance of sequence variation for SARS-CoV-2 RNA detection (2022). https://pubmed.ncbi.nlm.nih.gov/35324900/. Authority: `peer_reviewed`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::_prepare_target_inclusivity`, `tools/src/pcr_tools/loop_set.py::_target_inclusivity_audit`
- **Regression evidence:** `test_loop_set_runtime_contract_declares_conditional_mafft_and_mfe_structure_ops`, `test_lamp_target_inclusivity_audit_is_position_and_role_aware`
- **Claim boundary:** No homologous target panel means no population-coverage claim. Mismatch effects are role/position-aware evidence, not deterministic failure calls.

## LAMP-SEARCH-001 — bounded branch/top-K search

- **Decision role:** `engineering_search_policy`
- **Status:** `implemented`
- **Source:** GLAPD source/usage notes (2026). https://github.com/jiqingxiaoxi/GLAPD. Authority: `upstream_software_reference`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::_round_robin_partner_schedule`, `tools/src/pcr_tools/loop_set.py::_core_pair_expansion_pool`, `tools/src/pcr_tools/loop_set.py::_loop_variants`, `tools/src/pcr_tools/loop_set.py::_spatial_sample`, `tools/src/pcr_tools/loop_set.py::_risk_rank_pool`
- **Regression evidence:** `test_round_robin_core_partner_budget_reaches_all_jobs_before_second_pass`, `test_core_pair_expansion_pool_keeps_best_and_target_wide_diversity`, `test_loop_alternatives_keep_no_loop_and_bounded_candidates_for_set_level_ranking`, `test_outer_pair_topk_truncation_is_disclosed_as_bounded_search`, `test_bounded_search_is_reverse_complement_invariant_for_both_geometry_profiles`, `test_repeated_bounded_search_is_deterministic_for_identical_input`
- **Claim boundary:** Every known computational truncation layer (half cap, loop-alternative pruning, partner sampling, core expansion, outer-candidate/pair top-K, and risk-rank pool) is surfaced in search provenance; any such pruning disables global-optimum claims.

## LAMP-EXT-001 — independent ordered-oligo and specificity validators

- **Decision role:** `external_validation`
- **Status:** `implemented`
- **Source:** MFEprimer (2026). https://github.com/quwubin/MFEprimer-3.0. Authority: `upstream_tool`.
- **Source:** MAFFT (2026). https://mafft.cbrc.jp/alignment/software/. Authority: `upstream_tool`.
- **Implementation:** `tools/src/pcr_tools/runtime_contract.py::ENGINE_BINDINGS[loop-set]`, `tools/src/pcr_tools/external_validation.py::validate_result`, `tools/src/pcr_tools/external_validation.py::_mfeprimer_oligo_qc`
- **Regression evidence:** `test_loop_set_runtime_contract_declares_conditional_mafft_and_mfe_structure_ops`, `test_loop_set_mfeprimer_ordered_oligo_qc_executes_dimer_and_hairpin`, `test_loop_set_mfeprimer_qc_never_crosses_alternative_lamp_sets`
- **Claim boundary:** Strict mode requires pinned tool identities and approved specificity databases; missing external evidence cannot be silently upgraded to validated. Ordered-molecule MFEprimer dimer/hairpin evidence is evaluated per physically co-reacting LAMP candidate set, so alternative sets are never pooled into a fictitious cross-set reaction.

### R5 registry/lifecycle clarification

The named LAMP registry remains deliberately finite rather than brand-count driven. R5 rechecked current vendor availability and lifecycle: M1708 remains a valid current NEB identity while M1712 is retained as the newer Bst-XT generation; Thermo A51801/A51802/A51803 and Eiken LMP204/LMP207/LMP244/LMP247 remain current product families. No silent substitution is performed across generations or substrates.

## LAMP-PROTOCOL-001 — named vendor protocol overlays remain bench/provenance context

- **Decision role:** `named_bench_protocol_overlay`
- **Status:** `implemented`
- **Source:** NEB LyoPrime WarmStart Fluorescent LAMP/RT-LAMP Mix with UDG L4401 protocol (current/reviewed 2026). https://www.neb.com/en-us/protocols/protocol-for-lyoprime-warmstart-fluorescent-lamp-rt-lamp-mix-with-udg-neb-l4401. Authority: `vendor_primary_documentation`.
- **Source:** NEB Bst-XT WarmStart DNA Polymerase (Glycerol-free) M9205 LAMP/RT-LAMP protocol (2025). https://www.neb.com/en/protocols/2025/03/18/loop-mediated-isothermal-amplification-lamp-protocol-using-bst-xt-warmstart-dna-polymerase-glycerol-free. Authority: `vendor_primary_documentation`.
- **Source:** Thermo Fisher SuperScript IV RT-LAMP Master Mix Quick Reference MAN0025703 Rev. A.0 (2021). https://documents.thermofisher.com/TFS-Assets/LSG/manuals/MAN0025703_Superscript_IV_RT-LAMP_QR.pdf. Authority: `vendor_primary_documentation`.
- **Source:** Nippon Gene 2x LAMP Master Mix Manual 2024/9, NE6041/NE6043 (2024). https://nippongene.com/kensa/products/tds/NE6041_NE6043_Manual.pdf. Authority: `vendor_primary_documentation`.
- **Source:** Eiken Loopamp RNA/DNA Amplification Reagent D LMP247 package insert (2015 revision). https://loopamp.eiken.co.jp/en/uploads/rna_dna_insert.pdf. Authority: `vendor_primary_documentation`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::LAMP_PROTOCOL_REGISTRY`, `crates/pcr-core/src/engines/loop_set.rs::LAMP_PROTOCOLS`, `web/src/lib/api/types.ts::lampProtocol`, `web/src/components/design/engine-fields.tsx::lampProtocol`
- **Regression evidence:** `test_reviewed_lamp_protocols_keep_their_own_concentrations_and_hold`, `test_protocol_overlay_does_not_change_the_selected_genomic_lamp_set`, `test_thermo_superscript_iv_preserves_protocol_range_and_dual_substrate_authority`, `test_nippon_ne6041_preserves_fluorescence_only_dna_recipe_without_invented_rt`, `test_neb_m9205_preserves_glycerol_free_rt_and_optional_udg_authority`, `test_eiken_dried_rna_dna_reagent_keeps_range_and_one_step_rt_authority`
- **Claim boundary:** Named overlays preserve vendor-specific reaction identity, thermal/substrate authority, carry-over and readout context. Selecting an overlay must not change genomic LAMP candidate generation, geometry, Tm eligibility or specificity ranking, and a computationally represented protocol does not constitute wet-lab validation.

## LAMP-PERF-ML-001 — 2025 in-silico amplification predictor using F2/B2 GC and local enthalpy

- **Decision role:** `research_watchlist`
- **Status:** `not_integrated_into_ranking`
- **Source:** In silico prediction of loop-mediated isothermal amplification using a generalized linear model (2025). https://academic.oup.com/synbio/article/10/1/ysaf007/8100661. Authority: `peer_reviewed`.
- **Claim boundary:** Promising model (reported AUC ~0.858; prospective AUC ~0.811) is based on a limited 96-set dataset; PCRStudio does not import its coefficients as a universal score without independent calibration.

## LAMP-NSA-2026-001 — primer-driven nonspecific amplification and initiator inner primers

- **Decision role:** `research_watchlist`
- **Status:** `not_sequence_predictable_yet`
- **Source:** Inner primer Blockers inhibit non-specific amplification in LAMP (2026). https://www.sciencedirect.com/science/article/pii/S000326702501414X. DOI: `10.1016/j.aca.2025.345020`. Authority: `peer_reviewed`.
- **Source:** High-temperature ssBP-LAMP breaks the barrier of nonspecific amplification and unlocks the full potential of LAMP diagnostics (2026). https://pmc.ncbi.nlm.nih.gov/articles/PMC13281569/. DOI: `10.1186/s11658-026-00926-8`. Authority: `peer_reviewed`.
- **Claim boundary:** These studies strengthen the need for FIP/BIP-focused risk review and wet-lab NTC screening but do not yet supply a general sequence-only rule that PCRStudio can safely hard-code.


## LAMP-ML-2026-PREPRINT-001 — multi-feature fidelity classifier

- **Decision role:** research watchlist; preprint, not integrated into ranking.
- **Source:** 2026 bioRxiv preprint, DOI `10.64898/2026.06.03.728514`.
- **Claim boundary:** Negative assay data are valuable, but 109 sets with 23 failures are not enough to transplant model parameters or calibrated success probabilities into PCRStudio.

## LAMP-SLAMP-2026-001 — short-target alternative topology

- **Decision role:** separate future topology.
- **Source:** 2026 *Microchemical Journal*, DOI `10.1016/j.microc.2026.117092`.
- **Claim boundary:** SLAMP must receive its own region/composition/validation contract; classic LAMP geometry is not widened to imitate it.

## LAMP-READOUT-002 — Nippon Gene NE6041/NE6043 turbidity incompatibility

- **Decision role:** `named_protocol_readout_gate`
- **Status:** `implemented`
- **Source:** Nippon Gene 2x LAMP Master Mix Manual 2024/9, NE6041/NE6043. https://nippongene.com/kensa/products/tds/NE6041_NE6043_Manual.pdf. Authority: `vendor_primary_documentation`.
- **Source:** Nippon Gene current 2x LAMP Master Mix product page. https://www.nippongene.com/kensa/products/amplification/2x-lamp-mix/2x-lamp-master-mix.html. Authority: `vendor_primary_documentation`.
- **Implementation:** `tools/src/pcr_tools/loop_set.py::_readout_compatibility`, `tools/src/pcr_tools/loop_set.py::LAMP_PROTOCOL_REGISTRY`, `web/src/components/design/engine-fields.tsx::lampReadout`
- **Regression evidence:** `test_nippon_ne6041_turbidity_is_a_source_backed_hard_incompatibility`
- **Claim boundary:** An explicit vendor prohibition is fail-closed. Merely being outside a reviewed recommendation list remains `review-required`; PCRStudio does not turn missing evidence into an impossibility rule.


## R8 scenario/chemistry closure

R8 adds executable ledger entries for scenario-aware specimen/formulation/readout gating, Meridian MDX126 direct air-dryable blood LAMP, and Takara BcaBEST RR385 DNA/RNA TB Green/UNG chemistry. These branches remain source-bounded and do not silently alter sequence ranking.


## R15 canonical LAMP closure

R15 adds a single machine-readable LAMP product/protocol authority, exact PrimerExplorer V5 GC-boundary semantics, fixed/mutation/two-stage design contracts, a source-backed ordered thermal-stage model and a shared Python/Rust/Web differential corpus. The current catalogue is **72 identities (35 DNA-only / 4 RNA-only / 33 dual)** at snapshot `2026-09`. Vazyme RP712 and Hyasen HYB413/HYB414/HYB315 are current named identities; missing exact numeric authority remains unresolved rather than inferred.

### LAMP-GLOBAL-R15-001 — canonical 72-identity runtime catalogue

- **Evidence class:** exact-product/source-bounded catalogue authority.
- **Implementation:** `contracts/chemistry/lamp-protocols.json` → generated Python/Rust/Web/runtime projections.
- **Claim boundary:** catalogue membership is not chemistry equivalence; exact substrate, formulation, specimen, readout, lifecycle and numeric authority remain product-specific.

### LAMP-GEOMETRY-R15-001 — PrimerExplorer V5 automatic profile boundary

- **Evidence class:** reference-tool documented geometry/profile semantics.
- **Implementation:** AT-rich `<=45%`, Normal `>45% and <60%`, GC-rich `>=60%`, with exact boundary regressions.
- **Claim boundary:** the profile is a versioned compatibility/reference mode, not a universal empirical success predictor.

### LAMP-DIFFERENTIAL-R15-001 — Python/browser numeric parity

- **Evidence class:** executable cross-language regression.
- **Implementation:** `contracts/chemistry/lamp-differential-corpus.json`, Python resolver regression, Rust `lamp_differential_contract` integration test and `scripts/check-lamp-web-numeric.js`.
- **Claim boundary:** the corpus guards implementation parity; vendor/source evidence remains the authority for scientific numbers.

## R9 global numeric interaction closure

R9 adds a conditional numeric recipe authority beside the existing sequence-design and scenario contracts. Numeric values may change only when the exact reviewed product/context supports the dependency; unresolved public amounts stay unresolved instead of being fabricated.

## LAMP-NUMERIC-R9-001 — source-conditioned numeric recipe resolution

- **Decision role:** `conditional_numeric_recipe`
- **Status:** `implemented`
- **Sources:** NEB M1712 current guidance; Thermo SuperScript IV RT-LAMP; Eiken LMP221 insert and the exact-product authorities represented in `lamp_numeric_recipes.py`.
- **Implementation:** `tools/src/pcr_tools/lamp_numeric_recipes.py::resolve_numeric_recipe`, `web/src/lib/lamp-contract.ts::resolveLampNumericPreview`, `tools/src/pcr_tools/loop_set.py::_bench_optimization`.
- **Regression evidence:** `test_m1712_readout_numbers_change`, `test_thermo_calcein_and_syto9_are_distinct_numeric_recipes`, `test_bst_xt_substrate_and_carryover_add_numbers`, `test_eiken_and_ph_colorimetric_fail_closed_for_wrong_buffer_context`.
- **Claim boundary:** Product baselines, automatic conditional overlays, reviewed ranges, bounded user overrides, derived stoichiometry and unresolved dependencies are distinct. Bench chemistry does not silently alter sequence ranking.

## LAMP-GLOBAL-R9-001 — 68-identity exact-product runtime catalogue

- **Decision role:** `named_bench_protocol_overlay`
- **Status:** `implemented`
- **Sources:** Current exact-product documentation for the admitted NEB, Thermo Fisher/Invitrogen, OptiGene, Meridian, Eiken, Nippon Gene, Takara, Jena Bioscience, NZYtech, Yeasen, Vazyme and Agdia branches.
- **Implementation:** `LAMP_PROTOCOL_REGISTRY` → Rust `LAMP_PROTOCOLS` → TypeScript request union → UI selector.
- **Regression evidence:** `test_current_protocol_catalogue_and_substrate_partition`, `test_grouped_vendor_primer_table_normalizes_to_explicit_roles`.
- **Claim boundary:** 68 identities are not interchangeable recipes. The partition is 34 DNA-only / 4 RNA-only / 30 dual, and insufficiently documented current products remain watchlist-only.

## LAMP-VAZYME-R9-001 — instrument-conditioned RP711 dye arithmetic

- **Decision role:** `conditional_numeric_recipe`
- **Status:** `implemented`
- **Source:** Vazyme RP711 V25.1/current product authority: https://bio.vazyme.com/product/763.html
- **Implementation:** Python and browser numeric resolvers plus Rust/Web instrument-profile transport.
- **Regression evidence:** `test_vazyme_instrument_stoichiometry_and_other_instrument_unresolved_exact`, `r9_vazyme_instrument_and_numeric_context_reach_worker`.
- **Claim boundary:** SLAN-96P resolves to 0.1X dye (0.05 µL from 50X stock in 25 µL); named reviewed platforms resolve to 1X (0.5 µL); other qPCR instruments retain 0.1–1X without a fabricated exact value.

## LAMP-AGDIA-R9-001 — RNA/external-RT and AmpliFire branch

- **Decision role:** `conditional_numeric_recipe`
- **Status:** `implemented`
- **Source:** Agdia LMX 54700 User Guide m472 Rev. 2025-01-06: https://orders.agdia.com/assets/site/docs/m472.pdf
- **Implementation:** conditional RNA RT overlay and instrument profile in Python/Rust/Web contracts.
- **Regression evidence:** `test_agdia_rna_adds_external_rt_only_when_needed`, `r9_agdia_rna_and_amplifire_reach_worker`.
- **Claim boundary:** 50 U external RT is added only for RNA input; 65°C/20 min is scoped to the reviewed AmpliFire branch.

## LAMP-NUMERIC-BOUNDARY-R9-001 — unresolved numeric dependency / no-fabrication rule

- **Decision role:** `numeric_admission_boundary`
- **Status:** `implemented`
- **Implementation:** `LAMP_UNRESOLVED_NUMERIC_DEPENDENCIES`, source-bounded optimization envelopes, browser unresolved-state rendering and the canonical unresolved-dependency watchlist.
- **Regression evidence:** `test_unsourced_ranges_are_not_resurrected`, `test_unsourced_override_ranges_are_removed_from_worker_authority`.
- **Claim boundary:** An exact baseline is not an optimization range. A known dependency without a sufficiently specific public amount remains unresolved rather than receiving a guessed Mg²⁺, enzyme, dye, temperature or time value.
