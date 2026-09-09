/**
 * Result-schema migration and retention coverage.
 *
 * Historical captures live under `__fixtures__/historical/` and are used only
 * to prove saved runs still parse/render safely. They are not current runtime
 * authority and must never be refreshed by hand to imitate a new worker.
 * Current field-retention regressions below use explicitly synthetic objects
 * until a qualified runtime can produce a new capture.
 *
 * A schema written from reading the worker is a second copy of the worker's
 * output format, and the two drift silently: the parse fails at runtime, in the
 * browser, as an empty page rather than as an error anybody can act on. Both
 * mismatches found while wiring these engines were of exactly that kind —
 * a tiling order sheet that carried no melting temperature, and a probe line
 * carrying a note the schema had no room for. Neither was visible in either
 * file on its own.
 *
 * To refresh a fixture: post the same request to a running API and overwrite
 * the file. A schema change that the worker did not make should fail here.
 */

import { describe, expect, it } from "vitest";

import universalFixture from "../__fixtures__/universal-real.json";
import junctionFixture from "./__fixtures__/historical/gibson-assembly__pre-e5510-orderability-contract.json";
import historicalLoopSetFixture from "./__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json";
import historicalProbeFixture from "./__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
// Historical successful qPCR-probe response retained only to parse saved pre-chemistry runs; it is not a current executable fixture.
import mutagenicFixture from "./__fixtures__/historical/site-directed-mutagenesis__pre-q5-orderability-contract.json";
import flankingFixture from "./__fixtures__/historical/rpa__pre-specificity-v5-source-mirrored.json";
import singleFixture from "./__fixtures__/historical/sequencing-primer__pre-explicit-read-envelope.json";
import discriminatingFixture from "./__fixtures__/historical/tetra-primer-arms__pre-orderability-contract.json";
import tilingFixture from "./__fixtures__/historical/tiled-scheme__pre-orderability-contract.json";
import {
  discriminatingResultSchema,
  junctionResultSchema,
  loopSetResultSchema,
  outwardPairSchema,
  mutagenicResultSchema,
  probeResultSchema,
  universalResultSchema,
  runResultSchema,
  presetsSchema,
  designResultSchema,
  nestSchema,
  multiplexResultSchema,
  singleResultSchema,
  tilingResultSchema,
} from "./types";

const CAPTURED = [
  { name: "pair-and-probe", body: historicalProbeFixture, schema: probeResultSchema },
  { name: "single-primer", body: singleFixture, schema: singleResultSchema },
  { name: "mutagenic-pair", body: mutagenicFixture, schema: mutagenicResultSchema },
  { name: "tiling-scheme", body: tilingFixture, schema: tilingResultSchema },
  { name: "junction-primers", body: junctionFixture, schema: junctionResultSchema },
  { name: "flanking-pair", body: flankingFixture, schema: designResultSchema },
  { name: "consensus-pair", body: universalFixture, schema: universalResultSchema },
  {
    name: "discriminating-pair",
    body: discriminatingFixture,
    schema: discriminatingResultSchema,
  },
  { name: "loop-set", body: historicalLoopSetFixture, schema: loopSetResultSchema },
] as const;

type MutableLoopSetFixture = {
  [key: string]: unknown;
  sets?: Array<Record<string, unknown>>;
};

describe("historical capture parsing and current field retention", () => {
  it("migrates historical workflow evidence fields to canonical observed view", () => {
    const historical = structuredClone(flankingFixture) as Record<string, unknown>;
    historical.workflow_evidence = {
      recorded: true,
      decision_impact: "none",
      fields: { qpcrInstrument: "historical-instrument" },
      note: "legacy evidence shape",
    };
    const parsed = designResultSchema.parse(historical);
    expect(parsed.workflow_evidence?.observed.qpcrInstrument).toBe("historical-instrument");
    expect("fields" in (parsed.workflow_evidence ?? {})).toBe(false);
  });

  it("accepts nullable worker defaults and result constraints", () => {
    const presets = presetsSchema.parse({
      constraints: { max_end_stability: null },
      fields: [{ name: "max_end_stability", label: "End stability", hint: "", default: null }],
    });
    expect(presets.constraints.max_end_stability).toBeNull();
    expect(presets.fields[0]?.default).toBeNull();

    const result = structuredClone(historicalProbeFixture) as Record<string, unknown> & {
      constraints: { primers: Record<string, unknown> };
    };
    result.constraints = {
      ...result.constraints,
      primers: { ...result.constraints.primers, max_end_stability: null },
    };
    const parsed = probeResultSchema.parse(result);
    expect(parsed.constraints.primers.max_end_stability).toBeNull();
  });

  it("retains the named Standard-PCR bench overlay without promoting it to the screening model", () => {
    const result = structuredClone(flankingFixture) as Record<string, unknown>;
    result.protocol = {
      kind: "standard-pcr",
      protocol_id: "neb-q5u-hot-start-m0515",
      selection: "NEB Q5U Hot Start High-Fidelity DNA Polymerase (M0515)",
      source_publication: "NEB M0515 protocol",
      source_revision: "current reviewed web protocol",
      reaction_volume_uL: { supported_25: 25, supported_50: 50 },
      primer_final_concentration_uM: { starting: 0.5 },
      magnesium_final_mM: 2.0,
      dntp_each_mM: 0.2,
      cycling_model: { cycles: { starting: 30, typical_max: 35 } },
      polymerase_properties: {
        proofreading: true,
        hot_start: true,
        product_end: "blunt",
        dUTP_compatible: true,
        uracil_template_compatible: true,
      },
      difficult_template: { dmso_max_percent: 2, automatic_additive_selection: false },
      carryover_prevention: {
        dUTP_supported: true,
        UDG_built_in: false,
        optional_UDG: "Antarctic Thermolabile UDG M0372",
        note: "record the actual dUTP/UDG state",
      },
      sequence_decision_impact: "none",
      thermodynamic_model_impact: "none",
      screening_context_note: "Primer3 screening context remains separate.",
      constraints: {},
      note: "named bench authority",
    };
    const parsed = designResultSchema.parse(result);
    expect(parsed.protocol?.kind).toBe("standard-pcr");
    if (parsed.protocol?.kind !== "standard-pcr") throw new Error("expected Standard-PCR protocol");
    expect(parsed.protocol.magnesium_final_mM).toBe(2);
    expect(parsed.protocol.sequence_decision_impact).toBe("none");
    expect(parsed.protocol.thermodynamic_model_impact).toBe("none");
  });

  it("retains both K018x cycling branches and lifecycle provenance", () => {
    const result = structuredClone(flankingFixture) as Record<string, unknown>;
    result.protocol = {
      kind: "long-range-pcr",
      selection: "Thermo Scientific Long PCR Enzyme Mix K0181/K0182",
      kit_ids: ["K0181", "K0182"],
      manual: "MAN0016323 / Long PCR Enzyme Mix product information",
      source_publication: "MAN0016323",
      source_revision: "A.00",
      source_revision_date: "2016-11-28",
      lifecycle: {
        status: "discontinued",
        discontinued_date: "2017-05-01",
        replacement_part: "F530S",
        replacement_name: "Phusion High-Fidelity DNA Polymerase",
        replacement_is_informational_only: true,
        silent_substitution_allowed: false,
      },
      reaction_volume_uL: 50,
      primer_final_concentration_uM: { min: 0.3, max: 1.0 },
      magnesium_chloride_mM: 1.5,
      dntp_each_mM: 0.2,
      enzyme_units: { up_to_20kb_min: 1, up_to_20kb_max: 1.25, at_or_above_20kb_max: 2.5 },
      cycling_model: {
        supplier_preference: "two-step-in-most-cases",
        branch_selection: {
          supplier_rule:
            "use three-step cycling when the primer annealing temperature is below 65 C",
          selected_branch: "unresolved-until-kit-compatible-annealing-temperature-authority",
          screening_tm_is_not_bench_ta_authority: true,
        },
        two_step: {
          initial_denaturation: { temperature_c: 94, minutes: { min: 1, max: 3 } },
          phase_1: {
            cycles: 10,
            denaturation: { temperature_c: { min: 94, max: 96 }, seconds: 20 },
            anneal_extend: { temperature_c: 68, seconds_per_kb: { min: 45, max: 60 } },
          },
          phase_2: {
            cycles: { min: 15, max: 25 },
            denaturation: { temperature_c: 94, seconds: 20 },
            anneal_extend_temperature_c: 68,
            base_extension_seconds_per_kb: { min: 45, max: 60 },
            auto_extension: "manual table",
          },
          final_extension: { temperature_c: 68, minutes: 2 },
        },
        three_step: {
          initial_denaturation: { temperature_c: 94, minutes: { min: 1, max: 3 } },
          phase_1: {
            cycles: 10,
            denaturation: { temperature_c: { min: 94, max: 96 }, seconds: 20 },
            annealing: { temperature_rule: "Tm-5 C", seconds: 30 },
            extension: { temperature_c: 68, seconds_per_kb: { min: 45, max: 60 } },
          },
          phase_2: {
            cycles: { min: 15, max: 25 },
            denaturation: { temperature_c: 94, seconds: 20 },
            annealing: { temperature_rule: "Tm-5 C", seconds: 30 },
            extension_temperature_c: 68,
            base_extension_seconds_per_kb: { min: 45, max: 60 },
            auto_extension: "manual table",
          },
          final_extension: { temperature_c: 68, minutes: 2 },
        },
      },
      note: "Historical named branch",
    };

    const parsed = designResultSchema.parse(result);
    expect(parsed.protocol?.kind).toBe("long-range-pcr");
    if (parsed.protocol?.kind !== "long-range-pcr") throw new Error("expected long-range protocol");
    const cyclingModel = parsed.protocol.cycling_model as {
      two_step: { phase_1: { anneal_extend: { temperature_c: number } } };
      three_step: { phase_1: { annealing: { temperature_rule: string } } };
      branch_selection: { screening_tm_is_not_bench_ta_authority: boolean };
    };
    expect(parsed.protocol.source_revision).toBe("A.00");
    expect(parsed.protocol.lifecycle.silent_substitution_allowed).toBe(false);
    expect(cyclingModel.two_step.phase_1.anneal_extend.temperature_c).toBe(68);
    expect(cyclingModel.three_step.phase_1.annealing.temperature_rule).toBe("Tm-5 C");
    expect(cyclingModel.branch_selection.screening_tm_is_not_bench_ta_authority).toBe(true);
  });

  it("does not strip Universal canonical-profile or constraint provenance", () => {
    const result = structuredClone(universalFixture) as Record<string, unknown>;
    result.assay = {
      id: "universal-primers",
      name: "Universal Primers",
      engine: "consensus-pair",
      status: "available",
      profile_authority: {
        source: "pcr-core:profiles.toml",
        profileId: "universal-primers",
        transport: "server-injected-canonical-profile",
      },
      modifiers: [],
      requires: [],
      enzyme: [],
    };
    result.provenance = {
      worker: "pcr-tools",
      primer3_py: "test",
      python: "test",
      platform: "test",
      note: "test",
      model: { name: "test" },
    };
    result.constraints = { length_min: 18, length_max: 26, tm_spread_max: 5, min_coverage: 1 };

    const parsed = universalResultSchema.parse(result);
    expect(parsed.assay?.profile_authority?.profileId).toBe("universal-primers");
    expect(parsed.provenance?.worker).toBe("pcr-tools");
    expect(parsed.constraints?.tm_spread_max).toBe(5);
  });

  it("retains per-nest two-tube Tm relationship evidence", () => {
    const oligo = {
      sequence: "ACGTACGTACGTACGTACGT",
      length: 20,
      gc_percent: 50,
      tm: 60,
      hairpin: { found: false, dg: 0, tm: 0 },
      self_dimer: { found: false, dg: 0, tm: 0 },
      three_prime_dg: -3,
    };
    const round = {
      left: oligo,
      right: oligo,
      left_at: { start: 10, length: 20 },
      right_at: { start: 190, length: 20 },
      product_size: 200,
      tm_difference: 0,
      cross_dimer_dg: -1,
      penalty: 0,
    };
    const parsed = nestSchema.parse({
      outer: round,
      inner: {
        ...round,
        left_at: { start: 40, length: 20 },
        right_at: { start: 160, length: 20 },
        product_size: 140,
      },
      shares: "nothing",
      moved_in: { left: 30, right: 30 },
      tm_note:
        "The two tubes need independent annealing-temperature review; no universal separation gate was applied.",
    });
    expect(parsed.tm_note).toContain("independent annealing-temperature");
  });

  it("retains flanking-pair thermodynamic, uniformity, and quality diagnostics", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = structuredClone(flankingFixture) as Record<string, any>;
    if (!Array.isArray(result.pairs) || !result.pairs[0]) throw new Error("fixture needs a pair");
    result.pairs[0] = {
      ...result.pairs[0],
      cross_dimer_temperature_c: 37,
      thermodynamic_temperature_role: "model-reference-not-bench-annealing",
      uniformity: { window_bp: 50, min_window_gc: 34, max_window_gc: 68, note: "" },
      quality: {
        score: 81,
        parts: {
          specificity: 1,
          dimer_margin: 0.75,
          accessibility: null,
          end_stability: 0.8,
          tm_centeredness: null,
        },
      },
    };

    const parsed = designResultSchema.parse(result);
    expect(parsed.pairs[0]?.cross_dimer_temperature_c).toBe(37);
    expect(parsed.pairs[0]?.thermodynamic_temperature_role).toBe(
      "model-reference-not-bench-annealing",
    );
    expect(parsed.pairs[0]?.uniformity?.window_bp).toBe(50);
    expect(parsed.pairs[0]?.quality?.parts.accessibility).toBeNull();
    expect(parsed.pairs[0]?.quality?.parts.tm_centeredness).toBeNull();
  });

  it("keeps the executable assay contract when a worker returns it", () => {
    const result = structuredClone(flankingFixture) as Record<string, unknown> & {
      assay: Record<string, unknown>;
    };
    result.assay = {
      ...result.assay,
      modifiers: ["variant-masking"],
      requires: ["background"],
      enzyme: ["thermostable"],
    };

    const parsed = designResultSchema.parse(result);
    expect(parsed.assay?.modifiers).toEqual(["variant-masking"]);
    expect(parsed.assay?.requires).toEqual(["background"]);
    expect(parsed.assay?.enzyme).toEqual(["thermostable"]);
  });

  it("retains LAMP ranking and interaction evidence instead of stripping worker diagnostics", () => {
    const body = structuredClone(historicalLoopSetFixture) as MutableLoopSetFixture;
    const first = body.sets?.[0];
    if (!first) throw new Error("historical LAMP fixture has no set");
    first.evidence_rank = {
      preferred_f2_b2_distance_penalty: 0,
      preferred_outer_gap_penalty: 2,
      preferred_loop_tm_penalty: 1.5,
      preferred_f2_b2_span: [120, 160],
      preferred_outer_gap: [40, 60],
      preferred_loop_tm: [64, 66],
      geometry_profile: "pcrstudio-evidence-2026",
      classification: "soft-ranking-only",
    };
    first.sequence_interaction_risk = {
      classification: "risk-ranking-not-pass-fail",
      review_at_or_above_bases: 4,
      core_core_max_bases: 3,
      core_core_review_events: 0,
      all_max_bases: 4,
      all_review_events: 1,
      events: [{ primer_3p: "FIP", partner: "BIP", bases: 4, review: true, core_core: true }],
      note: "review trigger only",
    };
    first.terminal_gc = {
      FIP: {
        gc_in_last_6: 4,
        has_gc_clamp_in_last_6: true,
        three_prime_gc_run: 2,
        review: false,
        classification: "soft-evidence-feature",
      },
    };
    first.lamp_background_topology = {
      checked: true,
      risk_class: 2,
      classification: "mismatch-tolerant-compatible-locus",
    };
    first.target_inclusivity = { checked: true, supplied: true, critical_terminal_events: 0 };

    const parsed = loopSetResultSchema.parse(body);
    expect(parsed.sets[0]?.evidence_rank?.geometry_profile).toBe("pcrstudio-evidence-2026");
    expect(parsed.sets[0]?.sequence_interaction_risk?.events[0]?.bases).toBe(4);
    expect(parsed.sets[0]?.terminal_gc?.FIP?.gc_in_last_6).toBe(4);
    expect(parsed.sets[0]?.lamp_background_topology?.risk_class).toBe(2);
    expect(parsed.sets[0]?.target_inclusivity?.checked).toBe(true);
  });

  it("keeps LAMP-only topology evidence out of the outward-pair schema", () => {
    const parsed = outwardPairSchema.parse({
      off_targets: { checked: false, status: "not-run", findings: [], note: "not run" },
      left: {
        sequence: "ACGT",
        length: 4,
        tm: 60,
        gc_percent: 50,
        hairpin: { found: false, dg: 0, tm: 0 },
        self_dimer: { found: false, dg: 0, tm: 0 },
        three_prime_dg: 0,
      },
      right: {
        sequence: "TGCA",
        length: 4,
        tm: 60,
        gc_percent: 50,
        hairpin: { found: false, dg: 0, tm: 0 },
        self_dimer: { found: false, dg: 0, tm: 0 },
        three_prime_dg: 0,
      },
      left_at: { start: 1, length: 4 },
      right_at: { start: 10, length: 4 },
      reads: "outward",
      left_reads_into: "unknown",
      right_reads_into: "unknown",
      walks_into: "unknown",
      known_span: 9,
      product_size: null,
      product_note: "unknown",
      unknown_interval: { status: "unknown", minimum: null, maximum: null, exact: null },
      product_path: [],
      tm_difference: 0,
      cross_dimer_dg: 0,
      penalty: 0,
      lamp_background_topology: {
        checked: true,
        risk_class: 3,
        classification: "must-not-survive",
      },
    });
    expect("lamp_background_topology" in parsed).toBe(false);
  });

  it("retains multiplex profile, readout, colony and per-target scientific evidence", () => {
    const parsed = multiplexResultSchema.parse({
      engine: "flanking-pair",
      mode: "multiplex",
      readout: "agarose",
      readout_profile: "qiagen-multiplex-agarose-guideline",
      assay: {
        id: "colony-pcr",
        name: "Colony PCR",
        engine: "flanking-pair",
        status: "available",
        profile_authority: {
          source: "pcr-core:profiles.toml",
          profileId: "colony-pcr",
          transport: "server-injected-canonical-profile",
        },
        modifiers: ["multiplex"],
        requires: [],
        enzyme: [],
      },
      reaction: {
        polymerase: "taq",
        polymerase_name: "Taq DNA polymerase",
        mv_conc: 50,
        dv_conc: 1.5,
        dntp_conc: 0.2,
        dna_conc: 50,
        model: { name: "SantaLucia 1998 nearest-neighbour", salt_correction: "SantaLucia 1998" },
      },
      provenance: {
        worker: "0.1.0",
        primer3_py: "2.3.1",
        python: "3.12.13",
        platform: "Linux",
        note: "fixture",
        model: { name: "SantaLucia 1998 nearest-neighbour" },
      },
      colony_context: {
        host_class: "bacterial",
        preparation: "direct-transfer",
        protocol_name: "named colony SOP",
        protocol_provenance: "laboratory QA system / rev 3 / 2026-08-01",
        interpretation_status: "in-silico-screen-design",
        lysis_timing_inferred: false,
        sample_amount_inferred: false,
        source_recovery_status:
          "user-managed-retained-source-required-for-recoverable-positive-screen",
        cycling_authority: "named-user-sop-required",
        required_observations: ["positive control"],
        note: "No lysis timing was inferred.",
      },
      crowded_above: 0,
      constraint_scope: "per-target",
      targets: [
        {
          name: "target-a",
          candidates: 4,
          constraints: { product_min: 120, product_max: 240 },
          background: {
            checked: true,
            bases: 1200,
            contigs: 2,
            max_mismatches: 3,
            template_only: false,
            note: "exclusion panel checked",
          },
          inclusivity: {
            checked: true,
            supplied: true,
            template_only: false,
            bases: 900,
            contigs: 3,
            pairs_checked: 4,
            pairs_rejected: 1,
            note: "sequence-coverage evidence only",
          },
        },
      ],
      tubes: [],
      order_sheet: [
        {
          name: "target-a_F",
          sequence: "ACGTACGTACGTACGTACGT",
          annealing_sequence: "ACGTACGTACGTACGTACGT",
          tail_sequence: "",
          kind: "primer",
          length: 20,
          gc_percent: 50,
          tube: "tube-1",
          pool: 0,
          note: "No Tm is invented by the multiplex set engine.",
        },
      ],
      panel_identity: {
        panel_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        formulation_sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        identity_scope: "target-panel",
        formulation_identity_scope: "shared-tube-formulation",
        software_target_bound: 1,
        wet_lab_qualified_plex: null,
      },
      selection_method: {
        objective: "readout spacing then interaction badness",
        readout_in_selection: true,
        optimizer: "deterministic-greedy-plus-local-improving-swaps",
        optimizer_mode: "local",
        simulated_annealing: false,
        exhaustive_within_evaluated_candidate_pools: false,
        global_optimum_claimed: false,
        candidate_pool_optimum_claimed: false,
        candidates_per_target: 5,
        rounds_per_tube: 10,
        seed: 1,
        per_tube: 4,
        tube_split_explicit: true,
        tube_assignment: {
          strategy: "deterministic-fewest-candidates-first-chunking",
          global_partition_optimized: false,
          explicit: true,
          tube_count: 1,
          note: "Target-to-tube partition is deterministic and not globally optimized.",
        },
      },
    });

    expect(parsed.readout_profile).toBe("qiagen-multiplex-agarose-guideline");
    expect(parsed.assay?.profile_authority?.profileId).toBe("colony-pcr");
    expect(parsed.colony_context?.protocol_name).toBe("named colony SOP");
    expect(parsed.colony_context?.protocol_provenance).toContain("rev 3");
    expect(parsed.constraint_scope).toBe("per-target");
    expect(parsed.constraints).toBeUndefined();
    expect(parsed.targets[0]?.constraints).toEqual({ product_min: 120, product_max: 240 });
    expect(parsed.targets[0]?.background?.checked).toBe(true);
    expect(parsed.targets[0]?.inclusivity?.pairs_rejected).toBe(1);
    expect(parsed.order_sheet[0]?.tm).toBeUndefined();
    expect(parsed.order_sheet[0]?.tube).toBe("tube-1");
    expect(parsed.order_sheet[0]?.pool).toBe(0);
    expect(parsed.selection_method?.readout_in_selection).toBe(true);
    expect(parsed.selection_method?.tube_assignment.global_partition_optimized).toBe(false);
  });

  it("keeps named wet-lab overlays in the result contract", () => {
    const junction = structuredClone(junctionFixture) as Record<string, unknown>;
    junction.protocol = {
      selection: "NEB Gibson Assembly Cloning Kit E5510",
      master_mix: "Gibson Assembly Master Mix (2X)",
      reaction_volume_uL: 20,
      fragment_count: 2,
      total_fragment_input_pmol_min: 0.02,
      total_fragment_input_pmol_max: 0.5,
      vector_input_ng: "50–100",
      insert_molar_excess: "2–3× each insert",
      incubation: { temperature_c: 50, minutes: 15, branch: "2-3-fragments" },
      unpurified_pcr_fraction_max: 0.2,
      after_incubation: "hold on ice",
      note: "Named protocol only",
    };
    expect(junctionResultSchema.parse(junction).protocol?.fragment_count).toBe(2);

    const kasp = structuredClone(discriminatingFixture) as Record<string, unknown>;
    kasp.protocol = {
      selection: "LGC KASP-TF V4.0 96/384 standard 61-55 C touchdown branch",
      source_identity: "LGC KASP Genotyping Assays FAQs (current web guidance)",
      source_revision: null,
      chemistry_identity: "KASP-TF V4.0 2X Master Mix 96/384",
      master_mix: "KASP-TF V4.0 2X Master Mix 96/384",
      assay_mix: "KASP Assay mix (72X)",
      plate_format: "96",
      instrument_model: "unresolved",
      rox_policy: "unresolved",
      reaction_volume_uL: 10,
      dna_volume_uL: 4.86,
      master_mix_volume_uL: 5,
      assay_mix_volume_uL: 0.14,
      dna_final_ng_per_uL: 2.5,
      dna_input_note: "Named protocol only",
      touchdown: {
        activation_c: 94,
        activation_min: 15,
        denature_c: 94,
        denature_seconds: 20,
        anneal_extend_start_c: 61,
        anneal_extend_final_c: 55,
        anneal_extend_delta_c: 0.6,
        cycles: 10,
        hold_seconds: 60,
      },
      amplification: {
        denature_c: 94,
        denature_seconds: 20,
        anneal_extend_c: 55,
        anneal_extend_seconds: 60,
        cycles: 26,
      },
      readout: {
        channels: ["FAM", "HEX"],
        singleplex: true,
        ntc_minimum: 2,
        qpcr_read_stage: "optional",
        endpoint_note: "cool before read",
      },
      note: "Named protocol only",
    };
    expect(discriminatingResultSchema.parse(kasp).protocol?.readout?.channels).toEqual([
      "FAM",
      "HEX",
    ]);

    const sequencing = structuredClone(singleFixture) as Record<string, unknown>;
    sequencing.protocol = {
      selection: "Applied Biosystems BigDye Terminator v3.1 cycle sequencing",
      kit_id: "4337454–4337458",
      reaction_volumes_uL: [10, 20],
      primer_input_pmol: 3.2,
      source_publication: "MAN1000355",
      source_revision: "B",
      source_revision_date: "2026-07-17",
      supplier_table_ambiguity:
        "Supplier table columns are not arithmetically reconciled by PCRStudio.",
      cycling: {
        cycles: 25,
        denature: { temperature_c: 96, seconds: 10 },
        anneal: { temperature_c: 50, seconds: 5 },
        extend: { temperature_c: 60, seconds: 240 },
        initial_denature: { temperature_c: 96, seconds: 60 },
        ramp_rate_c_per_s: 1,
        hold_temperature_c: 4,
      },
      template_input: {
        pcr_product_ng_by_length: { "100–200_bp": "1–3" },
        single_stranded_dna_ng: "25–50",
        double_stranded_dna_ng: "150–300",
      },
      cleanup_options: ["BigDye XTerminator purification"],
      readout: "capillary electrophoresis",
      note: "Named protocol only",
    };
    const parsedSequencing = singleResultSchema.parse(sequencing);
    expect(parsedSequencing.protocol?.cycling.cycles).toBe(25);
    expect(parsedSequencing.protocol?.source_publication).toBe("MAN1000355");
    expect(parsedSequencing.protocol?.source_revision).toBe("B");

    const probe = structuredClone(historicalProbeFixture) as Record<string, unknown>;
    probe.protocol = {
      selection: "Applied Biosystems TaqMan MGB quantification / gene-expression reference overlay",
      application_scope: "single-probe quantification / gene-expression-style hydrolysis assay",
      source_identity:
        "Applied Biosystems / Thermo Fisher official TaqMan MGB quantification guidance",
      source_revision: null,
      source_revision_date: null,
      source_revision_date_precision: null,
      source_documents: [
        {
          identity: "TaqMan Assay Multiplex PCR Optimization Application Guide",
          publication: "MAN0010189",
          revision: "F",
          revision_date: "2025-08-26",
          supports: ["gene-expression starting concentrations 900 nM primer each / 250 nM probe"],
        },
      ],
      probe_chemistry: "MGB-NFQ",
      reporter_options: ["FAM", "VIC", "ABY", "JUN", "Cy5", "TET", "NED"],
      quencher: "nonfluorescent quencher / minor-groove binder",
      primer_final_concentration_nM: 900,
      probe_final_concentration_nM: 250,
      amplicon_bp: { min: 50, max: 150 },
      primer_tm_c: { min: 58, max: 60 },
      probe_tm_c: { min: 68, max: 70 },
      probe_length_nt: { min: 13, max: 25 },
      primer_constraints: { product_min: 50, product_max: 150, tm_min: 58, tm_opt: 59, tm_max: 60 },
      probe_constraints: {
        length_min: 13,
        length_opt: 20,
        length_max: 25,
        tm_min: 68,
        tm_opt: 69,
        tm_max: 70,
      },
      note: "Named protocol only",
    };
    const parsedProbe = probeResultSchema.parse(probe);
    expect(parsedProbe.protocol?.probe_length_nt?.max).toBe(25);
    expect(parsedProbe.protocol?.application_scope).toContain("quantification");
    expect(parsedProbe.protocol?.source_documents?.[0]?.publication).toBe("MAN0010189");
    expect(parsedProbe.protocol?.primer_constraints?.product_max).toBe(150);
    expect(parsedProbe.protocol?.probe_constraints?.tm_max).toBe(70);

    const sybr = structuredClone(flankingFixture) as Record<string, unknown>;
    sybr.protocol = {
      kind: "qpcr-sybr",
      selection: "Bio-Rad iTaq Universal SYBR Green Supermix",
      master_mix: "iTaq Universal SYBR Green Supermix",
      amplicon_bp_preferred: { min: 70, max: 150 },
      primer_tm_c: { target: 60 },
      cycles: { min: 35, max: 40 },
      anneal_extend_c: 60,
      readout: "SYBR Green fluorescence with a dissociation/melt-curve review",
      note: "Named protocol only",
    };
    const parsedSybr = designResultSchema.parse(sybr);
    expect(parsedSybr.protocol?.kind).toBe("qpcr-sybr");
    if (parsedSybr.protocol?.kind === "qpcr-sybr") {
      expect(parsedSybr.protocol.amplicon_bp_preferred.max).toBe(150);
    }

    const powerupSybr = structuredClone(flankingFixture) as Record<string, unknown>;
    powerupSybr.protocol = {
      kind: "qpcr-sybr",
      protocol_id: "thermo-powerup-sybr-a2574x",
      selection: "Applied Biosystems PowerUp SYBR Green Master Mix",
      master_mix: "PowerUp SYBR Green Master Mix",
      reaction_volume_uL: { supported_10: 10, supported_20: 20 },
      primer_final_concentration_nM: { optimization_min: 300, optimization_max: 800 },
      amplicon_bp_preferred: { min: 50, max: 150 },
      primer_tm_c: { target: 60 },
      cycles: { min: 40, max: 40 },
      anneal_extend_c: 60,
      carryover_prevention: { dUTP_in_master_mix: true, UDG_built_in: true },
      readout: "SYBR Green fluorescence with dissociation curve",
      sequence_decision_impact: "none",
      note: "Named protocol only",
    };
    const parsedPowerup = designResultSchema.parse(powerupSybr);
    expect(parsedPowerup.protocol?.kind).toBe("qpcr-sybr");
    if (parsedPowerup.protocol?.kind === "qpcr-sybr") {
      expect(parsedPowerup.protocol.reaction_volume_uL).toEqual({
        supported_10: 10,
        supported_20: 20,
      });
      expect(parsedPowerup.protocol.primer_final_concentration_nM?.optimization_max).toBe(800);
    }

    const rtSybr = structuredClone(flankingFixture) as Record<string, unknown>;
    rtSybr.protocol = {
      kind: "qpcr-sybr",
      protocol_id: "neb-luna-one-step-rt-qpcr-e3005",
      selection: "NEB Luna Universal One-Step RT-qPCR Kit (E3005)",
      master_mix: "Luna Universal One-Step Reaction Mix + Luna WarmStart RT Enzyme Mix",
      reaction_volume_uL: { recommended_96_well: 20, recommended_384_well: 10 },
      primer_final_concentration_nM: {
        starting: 400,
        optimization_min: 100,
        optimization_max: 900,
      },
      amplicon_bp_preferred: { min: 70, max: 200 },
      primer_tm_c: { target: 60 },
      cycles: { min: 40, max: 45 },
      anneal_extend_c: 60,
      reverse_transcription: {
        mode: "one-step-rt-qpcr",
        authority_status: "named-neb-e3005-one-step-rt-qpcr",
        temperature_c: 55,
        incubation_minutes: 10,
        minimum_recommended_temperature_c: 50,
        difficult_target_temperature_c: 60,
        reverse_transcriptase: "Luna WarmStart Reverse Transcriptase",
        rnase_inhibitor: "Murine RNase Inhibitor",
        note: "Named one-step RT branch",
      },
      carryover_prevention: {
        dUTP_in_master_mix: true,
        UDG_built_in: false,
        optional_UDG: "Antarctic Thermolabile UDG M0372",
        optional_udg_pretreatment: { temperature_c: 25, minutes: 2 },
      },
      transcript_design: {
        splice_site_spanning_recommended_when_known: true,
        purpose: "reduce genomic-DNA amplification risk",
        hard_requirement_for_every_transcript: false,
      },
      genomic_dna_control: {
        no_rt_control_recommended: true,
        no_template_control_recommended: true,
        dnase_treatment_if_genomic_dna_is_detected: true,
        exon_exon_junction_design_recommended_when_annotated_and_appropriate: true,
        note: "No-RT remains a measured control",
      },
      readout: "dsDNA-dye fluorescence with melt curve",
      sequence_decision_impact: "none",
      note: "Named protocol only",
    };
    const parsedRtSybr = designResultSchema.parse(rtSybr);
    expect(parsedRtSybr.protocol?.kind).toBe("qpcr-sybr");
    if (parsedRtSybr.protocol?.kind === "qpcr-sybr") {
      expect(parsedRtSybr.protocol.reverse_transcription?.temperature_c).toBe(55);
    }

    const rpa = structuredClone(flankingFixture) as Record<string, unknown>;
    rpa.protocol = {
      kind: "rpa",
      selection: "TwistAmp Basic (TABAS03KIT; DNA)",
      primer_length_nt: {
        rapid_preferred_min: 30,
        rapid_preferred_max: 35,
        reviewed_upper_nt: 45,
        below_preferred_note:
          "Shorter oligos may function but are outside the preferred range; no hard minimum is asserted",
      },
      amplicon_bp: {
        preferred_rapid_min: 100,
        preferred_rapid_max: 200,
        supported_context_max: 500,
      },
      temperature_c: 39,
      incubation_minutes: 20,
      agitation: { after_minutes: 4, action: "vortex-and-brief-spin" },
      primer_final_concentration_nM: 480,
      magnesium_acetate_mM: 14,
      contamination_control: {
        carryover_risk: "high-copy-isothermal-amplicon",
        environment_and_carryover_false_positive_recognized: true,
        separate_pre_post_amplification_areas: true,
        post_amplification_opening_high_risk: true,
        high_copy_material_near_setup_avoid: true,
        bleach_decontamination_guidance: "10% bleach when contamination is suspected",
        closed_tube_readout_preferred_when_available:
          "risk-reduction-not-a-universal-readout-requirement",
        note: "TwistDx-specific workflow handoff",
      },
      readout: "Endpoint Basic reaction",
      note: "Named protocol only",
    };
    expect(designResultSchema.parse(rpa).protocol?.kind).toBe("rpa");

    const digital = structuredClone(flankingFixture) as Record<string, unknown>;
    digital.protocol = {
      kind: "digital-pcr",
      selection: "Bio-Rad QX200 ddPCR EvaGreen Supermix",
      supermix: "QX200 ddPCR EvaGreen Supermix",
      reaction_volume_uL: 20,
      droplets_target: 20000,
      cycling: {
        activation: { temperature_c: 95, minutes: 5 },
        denaturation: { temperature_c: 95, seconds: 30 },
        annealing_extension: { temperature_c: 60, minutes: 1 },
        cycles: 40,
        ramp_rate_c_per_s: 2,
      },
      stabilization: [
        { temperature_c: 4, minutes: 5 },
        { temperature_c: 90, minutes: 5 },
        { temperature_c: 4, minutes: 30 },
      ],
      readout: "QX200 droplet reader",
      quantitation: "copies per µL",
      note: "Named protocol only",
    };
    expect(designResultSchema.parse(digital).protocol?.kind).toBe("digital-pcr");

    const rtDigital = structuredClone(flankingFixture) as Record<string, unknown>;
    rtDigital.protocol = {
      kind: "digital-pcr",
      protocol_id: "qiagen-qiacuity-onestep-advanced-eg",
      selection: "QIAGEN QIAcuity OneStep Advanced EvaGreen Kit",
      supermix: "QIAcuity OneStep Advanced EvaGreen Master Mix",
      reaction_volume_uL: { "8.5k_nanoplate": 12, "26k_nanoplate": 40 },
      primer_final_concentration_uM: 0.75,
      supports_dna: true,
      supports_rna: true,
      constraints: {
        primer_length_min: 18,
        primer_length_max: 30,
        primer_tm_min: 58,
        primer_tm_max: 62,
        tm_pair_max_difference: 2,
        primer_gc_min: 30,
        primer_gc_max: 70,
        max_poly_x: 3,
      },
      reverse_transcription: {
        mode: "one-step-rt-dpcr",
        authority_status: "named-qiagen-qiacuity-onestep-advanced-eg",
        temperature_c: 50,
        incubation_minutes: 40,
        before: "RT enzyme inactivation and PCR cycling",
        note: "Named one-step RT-dPCR branch",
      },
      q_solution: {
        strongly_recommended: true,
        especially_useful_for: ["amplicons >150 bp", "GC-rich targets", "structured RNA"],
        not_a_sequence_validity_rule: true,
      },
      readout: "EvaGreen fluorescence",
      quantitation: "partition-positive fraction with platform volume model",
      sequence_decision_impact: "constraint-envelope",
      thermodynamic_model_impact: "none",
      note: "Named protocol only",
    };
    const parsedRtDigital = designResultSchema.parse(rtDigital);
    expect(parsedRtDigital.protocol?.kind).toBe("digital-pcr");
    if (parsedRtDigital.protocol?.kind === "digital-pcr") {
      expect(parsedRtDigital.protocol.reverse_transcription?.temperature_c).toBe(50);
      expect(parsedRtDigital.protocol.constraints?.tm_pair_max_difference).toBe(2);
    }

    const race = structuredClone(singleFixture) as Record<string, unknown>;
    delete race.protocol;
    delete race.read;
    race.race_direction = "5prime";
    race.race_placement = {
      direction: "reverse",
      race_direction: "5prime",
      search_region: [100, 200],
      semantics: "known-sequence-gsp-search-region",
      note: "Known-sequence GSP search region",
    };
    race.race_adapter = {
      id: "generacer-kit-25-0355-vl",
      name: "GeneRacer 5′ Primer",
      sequence: "CGACTGGAGCACGAGGACACTGA",
      direction: "5prime",
      round: "primary",
      authority: "Thermo Fisher GeneRacer Kit instruction manual 25-0355 Version L",
      protocol_identity: "thermo-fisher-generacer-kit",
      source_publication: "25-0355",
      source_revision: "Version L",
      source_revision_date: "2004-04-08",
    };
    expect(singleResultSchema.parse(race)).toMatchObject({
      race_direction: "5prime",
      race_placement: { race_direction: "5prime", direction: "reverse" },
      race_adapter: {
        id: "generacer-kit-25-0355-vl",
        source_publication: "25-0355",
        source_revision: "Version L",
      },
    });
  });

  it.each(CAPTURED)("$name parses against its own schema", ({ body, schema }) => {
    const parsed = schema.safeParse(body);
    expect(parsed.error?.issues ?? []).toEqual([]);
    expect(parsed.success).toBe(true);
  });

  it.each(CAPTURED)("$name is routed by the union to the right branch", ({ name, body }) => {
    // The view is chosen by which engine answered, so the discriminator has to
    // land on the right member — a result parsed into the wrong branch renders
    // the wrong component with missing fields.
    const parsed = runResultSchema.safeParse(body);
    expect(parsed.success).toBe(true);
    expect(parsed.success && parsed.data.engine).toBe(name);
  });
});

describe("the fields each view leads with", () => {
  // Not a restatement of the schema: these are the specific numbers the views
  // put in front of somebody, and a schema that made one optional would let it
  // render as undefined rather than fail here.

  it("a probe reports how far above its primers it melts", () => {
    const parsed = probeResultSchema.parse(historicalProbeFixture);
    expect(parsed.assays.length).toBeGreaterThan(0);
    for (const assay of parsed.assays) {
      expect(assay.probe.above_primers).toBeGreaterThan(0);
      expect(assay.probe.first_base.toUpperCase()).not.toBe("G");
      // It sits between the primers rather than overlapping one.
      expect(assay.probe.after_left).toBeGreaterThan(0);
    }
  });

  it("a single primer reports where its read puts the target", () => {
    const parsed = singleResultSchema.parse(singleFixture);
    expect(parsed.primers.length).toBeGreaterThan(0);
    if (!parsed.read) throw new Error("the fixture has no read window");
    for (const primer of parsed.primers) {
      expect(primer.reaches).toBeGreaterThanOrEqual(parsed.read.nearest);
      expect(primer.spare).toBeGreaterThanOrEqual(0);
    }
  });

  it("a mutagenic pair reports both of its melting temperatures", () => {
    const parsed = mutagenicResultSchema.parse(mutagenicFixture);
    expect(parsed.pairs.length).toBeGreaterThan(0);
    for (const pair of parsed.pairs) {
      // Reporting only the perfect-match figure overstates the first cycles,
      // which are the ones that can fail.
      expect(pair.melting.on_template).toBeGreaterThan(0);
      expect(pair.melting.on_product).toBeGreaterThan(0);
      expect(pair.melting.note).not.toBe("");
    }
  });

  it("retains the primary PrimalScheme3 amplicon identity on each tile", () => {
    const currentShape = structuredClone(tilingFixture) as typeof tilingFixture & {
      tiles: Array<(typeof tilingFixture.tiles)[number] & { name?: string }>;
    };
    currentShape.tiles = currentShape.tiles.map((tile, index) => ({
      ...tile,
      name: `primary_amplicon_${index + 1}`,
    }));
    const parsed = tilingResultSchema.parse(currentShape);
    expect(parsed.tiles[0]?.name).toBe("primary_amplicon_1");
  });

  it("a tiling scheme puts neighbours in different tubes", () => {
    const parsed = tilingResultSchema.parse(tilingFixture);
    expect(parsed.tiles.length).toBeGreaterThan(1);

    const pools = parsed.tiles.map((tile) => tile.pool);
    for (let index = 1; index < pools.length; index += 1) {
      expect(pools[index]).not.toBe(pools[index - 1]);
    }

    // Every order line carries its pool and its temperature: the person
    // ordering from the sheet is the person setting a block for it.
    for (const line of parsed.order_sheet) {
      expect(line.pool).toBeTypeOf("number");
      expect(line.tm).toBeGreaterThan(0);
    }
  });

  it("a tiling scheme reports its holes rather than rounding them away", () => {
    const parsed = tilingResultSchema.parse(tilingFixture);
    expect(parsed.coverage.percent).toBeGreaterThan(0);
    // Whether or not this fixture has gaps, the field is a list rather than a
    // flag — a scheme somebody knows the holes in is usable, and one that
    // silently skipped a stretch is not.
    expect(Array.isArray(parsed.gaps)).toBe(true);
    for (const gap of parsed.gaps) {
      expect(gap.why).not.toBe("");
    }
  });
});

describe("the fields the last three views lead with", () => {
  it("an assembly keeps a primer's two halves apart", () => {
    const parsed = junctionResultSchema.parse(junctionFixture);
    expect(parsed.primers.length).toBeGreaterThan(0);

    const tailed = parsed.primers.filter((primer) => primer.tail);
    expect(tailed.length).toBeGreaterThan(0);

    for (const primer of tailed) {
      // The whole oligo melts higher than the part that anneals in cycle one,
      // and only the second is a number a block can be set to.
      expect(primer.whole_oligo.tm).toBeGreaterThan(primer.anneals.tm);
      expect(primer.sequence).toBe(primer.tail!.sequence + primer.anneals.sequence);
    }
  });

  it("an assembly puts primers sharing a join in different tubes", () => {
    const parsed = junctionResultSchema.parse(junctionFixture);
    const tubes = Object.values(parsed.tubes);
    expect(tubes.length).toBeGreaterThan(1);

    // Every primer belongs to exactly one reaction.
    const assigned = tubes.flat();
    expect(new Set(assigned).size).toBe(assigned.length);
    expect(assigned.length).toBe(parsed.primers.length);
  });

  it("a genotyping result says what each allele is discriminated by", () => {
    const parsed = discriminatingResultSchema.parse(discriminatingFixture);
    expect(Object.keys(parsed.discrimination).length).toBeGreaterThan(0);

    for (const [allele, how] of Object.entries(parsed.discrimination)) {
      // The field the whole view exists to show: two primers and two
      // temperatures look identical whether the assay discriminates or not.
      expect(["terminus", "second mismatch", "nothing"]).toContain(how.rests_on);
      expect(how.terminus).toMatch(/^[ACGT]\*[ACGT]$/);
      expect(allele).toMatch(/^[ACGT]$/);
    }
    expect(["transition", "transversion"]).toContain(parsed.variant.kind);
  });

  it("a loop set reports its regions in order along the template", () => {
    const parsed = loopSetResultSchema.parse(historicalLoopSetFixture);
    expect(parsed.sets.length).toBeGreaterThan(0);

    for (const entry of parsed.sets) {
      const places = entry.regions.map((region) => region.at);
      expect(places).toEqual([...places].sort((a, b) => a - b));
    }
  });

  it("retains the Universal effective-pool concentration role", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    const body = structuredClone(universalFixture) as Record<string, unknown>;
    body.reaction = {
      ...(body.reaction as Record<string, unknown>),
      dna_conc_role: "effective-pool-reference-for-nominal-equal-member-tm-model",
    };
    const parsed = universalResultSchema.parse(body);
    expect(parsed.reaction.dna_conc_role).toBe(
      "effective-pool-reference-for-nominal-equal-member-tm-model",
    );
  });

  it("retains Universal orientation search evidence and the worker order ledger", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    const body = structuredClone(universalFixture) as Record<string, unknown>;
    body.windows = {
      ...(body.windows as Record<string, unknown>),
      by_orientation: {
        forward: { considered: 10, accepted: 3, rejections: [] },
        reverse: { considered: 12, accepted: 4, rejections: [] },
      },
    };
    body.order_sheet = [
      {
        name: "universal_1F",
        sequence: "ACGT",
        annealing_sequence: "ACGT",
        tail_sequence: "",
        kind: "primer",
        length: 4,
        gc_percent: 50,
        tm: 55,
        note: "audit ledger",
      },
    ];
    const parsed = universalResultSchema.parse(body);
    expect(parsed.windows.by_orientation?.forward.accepted).toBe(3);
    expect(parsed.order_sheet).toHaveLength(1);
  });

  it("a loop set reports each composite's binding half apart from the whole", () => {
    const parsed = loopSetResultSchema.parse(historicalLoopSetFixture);
    const entry = parsed.sets[0];
    expect(entry).toBeDefined();

    const composites = entry!.oligos.filter((oligo) => oligo.composite);
    expect(composites).toHaveLength(2);

    for (const oligo of composites) {
      // Near 80 °C for the whole molecule against a hold near 65 — half of it
      // is a tail with nothing to bind until the reaction has run.
      expect(oligo.anneals).toBeDefined();
      expect(oligo.anneals!.tm).toBeLessThan(oligo.tm);
      expect(oligo.sequence.endsWith(oligo.anneals!.sequence)).toBe(true);
    }
  });

  it("accepts the current LAMP temperature semantics and retains its design-model authority", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    const body = structuredClone(historicalLoopSetFixture) as MutableLoopSetFixture;
    body.reaction = {
      ...(body.reaction as Record<string, unknown>),
      hold: undefined,
      diagnostic_structure_temperature_c: 65,
      context_role:
        "generic Bst structure-diagnostic model with named-protocol role concentrations",
      context_note: "Structure diagnostics only; this is not a bench hold.",
    };
    body.parameter_set = {
      ...(body.parameter_set as Record<string, unknown>),
      thermodynamic_model: {
        id: "primerexplorer-v5-reference-output-compatible-sl98-tm-end-dg",
        tm_reference:
          "SantaLucia 1998 unified nearest-neighbour + PrimerExplorer Mg-to-Na correction; verified against V5 Manual Figure 1.10 reference outputs",
        end_stability_reference: "SantaLucia 1998 unified ΔG37 over terminal 6 bases",
        oligo_concentration_uM: 0.1,
        sodium_mM: 50,
        magnesium_mM: 4,
        effective_sodium_mM: 151.846,
        role: "LAMP design eligibility/ranking only; not the selected kit master-mix model",
      },
      terminal_stability: {
        window_bases: 6,
        regular_critical_max_dg_kcal_mol: -4,
        loop_3p_max_dg_kcal_mol: -2,
        regular_scope: "F2/B2/F3/B3 3-prime and F1c/B1c 5-prime critical ends",
        loop_scope: "LF/LB 3-prime ends using the separate PrimerExplorer V5 loop-primer screen",
        classification: "source-scoped-hard-candidate-gates",
      },
    };

    const parsed = loopSetResultSchema.parse(body);
    expect(parsed.reaction.diagnostic_structure_temperature_c).toBe(65);
    expect(parsed.reaction.context_role).toBe(
      "generic Bst structure-diagnostic model with named-protocol role concentrations",
    );
    expect(parsed.parameter_set.thermodynamic_model?.id).toBe(
      "primerexplorer-v5-reference-output-compatible-sl98-tm-end-dg",
    );
    expect(parsed.parameter_set.terminal_stability?.regular_critical_max_dg_kcal_mol).toBe(-4);
    expect(parsed.parameter_set.terminal_stability?.loop_3p_max_dg_kcal_mol).toBe(-2);
  });

  it("accepts a reviewed LAMP protocol that keeps vendor temperature/time ranges unresolved", () => {
    const body = structuredClone(historicalLoopSetFixture) as MutableLoopSetFixture;
    body.protocol = {
      selection: "Eiken Loopamp DNA Amplification Kit LMP204/205/206",
      vendor: "Eiken Chemical Co., Ltd.",
      kit_id: "LMP204/LMP205/LMP206",
      protocol_kind: "dna-kit",
      source_identity: "Eiken Loopamp DNA Amplification Kit package insert",
      source_url: "https://loopamp.eiken.co.jp/en/product/cat-102/dna_e.html",
      primer_concentrations_uM: { FIP: 1.6, BIP: 1.6, F3: 0.2, B3: 0.2, LoopF: 0.8, LoopB: 0.8 },
      primer_amounts_pmol_per_reaction: { FIP: 40, BIP: 40, F3: 5, B3: 5, LoopF: 20, LoopB: 20 },
      reaction_volume_uL: 25,
      hold_temperature_range_c: [60, 65],
      hold_time_range_min: [30, 60],
      supports_dna: true,
      supports_rna: false,
      sequence_decision_impact: "none",
      post_inactivation: "80 °C for 5 min or 95 °C for 2 min",
    };

    const parsed = loopSetResultSchema.parse(body);
    expect(parsed.protocol?.hold_temperature_c).toBeUndefined();
    expect(parsed.protocol?.hold_temperature_range_c).toEqual([60, 65]);
    expect(parsed.protocol?.primer_concentrations_uM?.LoopF).toBe(0.8);
  });

  it("accepts source-bounded LAMP enzyme/formulation identities without inventing a bench hold", () => {
    const body = structuredClone(historicalLoopSetFixture) as MutableLoopSetFixture;
    body.protocol = {
      selection: "NEB Bst 2.0 DNA Polymerase · M0537 assembled LAMP",
      vendor: "New England Biolabs",
      kit_id: "M0537",
      protocol_kind: "assembled-enzyme",
      source_identity: "NEB Bst 2.0 DNA Polymerase product/protocol authority",
      source_url: "https://www.neb.com/en-us/products/m0537-bst-20-dna-polymerase",
      supports_dna: true,
      supports_rna: false,
      formats: ["assembled-enzyme"],
      sequence_decision_impact: "none",
    };

    const parsed = loopSetResultSchema.parse(body);
    expect(parsed.protocol?.hold_temperature_c).toBeUndefined();
    expect(parsed.protocol?.hold_temperature_range_c).toBeUndefined();
    expect(parsed.protocol?.hold_time_min).toBeUndefined();
    expect(parsed.protocol?.hold_time_range_min).toBeUndefined();
  });

  it("keeps historical LAMP temperature fields readable without upgrading their semantics", () => {
    const parsed = loopSetResultSchema.parse(historicalLoopSetFixture);
    expect(parsed.reaction.diagnostic_structure_temperature_c).toBeUndefined();
    expect(parsed.reaction.hold).toBe(65);
    expect(parsed.parameter_set.thermodynamic_model).toBeUndefined();
  });

  it("retains per-junction bounded fold-diagnostic evidence", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body = structuredClone(junctionFixture) as Record<string, any>;
    expect(body.junctions[0]).toBeDefined();
    body.junctions[0].search = {
      candidate_windows_generated: 80,
      candidate_windows_measured: 24,
      fold_diagnostic_complete: false,
      complete: true,
      claim:
        "all generated candidates remained available to the source-backed validity/search path",
      fold_claim:
        "ViennaRNA diagnostic was measured only for a bounded prefix and did not affect selection",
    };
    const parsed = junctionResultSchema.parse(body);
    expect(parsed.junctions[0]?.search?.fold_diagnostic_complete).toBe(false);
    expect(parsed.junctions[0]?.search?.fold_claim).toMatch(/bounded prefix/);
  });

  it("retains the RACE GSP interaction diagnostic against the selected partner", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body = structuredClone(singleFixture) as Record<string, any>;
    body.primers[0].adapter_dimer = {
      partner: "UPM-long",
      partner_sequence: "CTAATACGACTCACTATAGGGCAAGCAGTGGTATCAACGCAGAGT",
      dg: -7.2,
      tm: 31.5,
      watch_threshold_dg: -6,
      flagged: true,
      decision_role: "diagnostic-watch-only-not-validity-or-ranking",
      temperature_role: "Primer3 thermodynamic model context; not inferred bench Ta",
      note: "Diagnostic only.",
    };
    const parsed = singleResultSchema.parse(body);
    expect(parsed.primers[0]?.adapter_dimer?.partner).toBe("UPM-long");
    expect(parsed.primers[0]?.adapter_dimer?.flagged).toBe(true);
    expect(parsed.primers[0]?.adapter_dimer?.decision_role).toBe(
      "diagnostic-watch-only-not-validity-or-ranking",
    );
  });

  it("retains the flanking search-purpose constraint, ranking and override ledger", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body = structuredClone(flankingFixture) as Record<string, any>;
    body.purpose = {
      id: "screen",
      name: "Screening on a gel",
      summary: "Present or absent, decided by eye.",
      constraints: { product_min: 150, product_max: 500, max_poly_x: 3 },
      ranking_weights: { product_target: 1.5, specificity: 2 },
      overridden: ["product_max"],
    };

    const parsed = designResultSchema.parse(body);
    expect(parsed.purpose?.constraints.product_max).toBe(500);
    expect(parsed.purpose?.ranking_weights.specificity).toBe(2);
    expect(parsed.purpose?.overridden).toEqual(["product_max"]);
  });

  it("retains the explicit LAMP readout boundary", () => {
    const parsed = loopSetResultSchema.parse({
      ...historicalLoopSetFixture,
      readout: {
        selection: "fluorescence",
        sequence_decision_impact: "none",
        note: "Detection chemistry is explicit provenance and does not define a positivity threshold.",
      },
    });
    expect(parsed.readout?.selection).toBe("fluorescence");
    expect(parsed.readout?.sequence_decision_impact).toBe("none");
  });

  it("a loop set says which parameter set was in force and where it came from", () => {
    const parsed = loopSetResultSchema.parse(historicalLoopSetFixture);
    // One held temperature cannot serve every composition, so a result read
    // under a different set from the one it was made under has temperatures
    // that do not mean what they appear to.
    expect(parsed.parameter_set.chosen_from).not.toBe("");
    expect(parsed.parameter_set.why).not.toBe("");
    expect(parsed.parameter_set.outer.tm).toHaveLength(2);
  });
});
