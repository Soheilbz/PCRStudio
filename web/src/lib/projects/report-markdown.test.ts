/**
 * The markdown report, against real API responses.
 *
 * The fixtures are captured from a running API, so the assertions pin what the
 * serializer does with shapes the core actually sends — not with hand-written
 * objects that agree with it by construction. A report that quietly dropped a
 * primer or misquoted a temperature would be worse than no report at all,
 * because somebody pastes this into a notebook and orders from it.
 */

import { describe, expect, it } from "vitest";

import historicalLoopSetFixture from "@/lib/api/__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json";
import junctionFixture from "@/lib/api/__fixtures__/historical/gibson-assembly__pre-e5510-orderability-contract.json";
import historicalProbeFixture from "@/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
import rpaFixture from "@/lib/api/__fixtures__/historical/rpa__pre-specificity-v5-source-mirrored.json";
import sequencingFixture from "@/lib/api/__fixtures__/historical/sequencing-primer__pre-explicit-read-envelope.json";
import discriminatingFixture from "@/lib/api/__fixtures__/historical/tetra-primer-arms__pre-orderability-contract.json";
import mutagenicFixture from "@/lib/api/__fixtures__/historical/site-directed-mutagenesis__pre-q5-orderability-contract.json";
import { designResultSchema, loopSetResultSchema, runResultSchema } from "@/lib/api/types";

import { reportMarkdown } from "./report-markdown";

const input = (
  resultJson: unknown,
  overrides: Partial<Parameters<typeof reportMarkdown>[0]> = {},
) => {
  const result = runResultSchema.parse(resultJson);
  return reportMarkdown({
    label: "Run 3",
    createdAt: "2026-08-24T10:30:00Z",
    moduleName: null,
    result,
    ...overrides,
  });
};

describe("portable scientific context", () => {
  it("keeps canonical profile authority in the report", () => {
    const result = structuredClone(rpaFixture) as Record<string, unknown> & {
      assay: Record<string, unknown>;
    };
    result.assay = {
      ...result.assay,
      profile_authority: {
        source: "pcr-core:profiles.toml",
        profileId: "rpa",
        transport: "server-injected-canonical-profile",
      },
    };
    const markdown = input(result);
    expect(markdown).toContain("## Profile authority");
    expect(markdown).toContain("Profile: rpa");
    expect(markdown).toContain("server-injected-canonical-profile");
  });

  it("keeps pair diagnostic context without promoting heuristic quality to a validity gate", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    const result = structuredClone(rpaFixture) as Record<string, unknown>;
    if (!Array.isArray(result.pairs) || !result.pairs[0]) throw new Error("fixture needs a pair");
    result.pairs[0] = {
      ...result.pairs[0],
      cross_dimer_temperature_c: 37,
      thermodynamic_temperature_role: "model-reference-not-bench-annealing",
      uniformity: {
        window_bp: 50,
        min_window_gc: 32,
        max_window_gc: 70,
        note: "review local GC extremes",
      },
      quality: {
        score: 79,
        parts: {
          specificity: 1,
          dimer_margin: 0.7,
          accessibility: null,
          end_stability: 0.8,
          tm_centeredness: null,
        },
      },
    };
    const markdown = input(result);
    expect(markdown).toContain("## Pair diagnostic context");
    expect(markdown).toContain("heuristic quality 79/100");
    expect(markdown).toContain("model-reference-not-bench-annealing");
    expect(markdown).toContain("not a universal validity threshold");
  });

  it("reports Standard-PCR chemistry as bench authority without overwriting the screening model", () => {
    const result = structuredClone(rpaFixture) as Record<string, unknown>;
    result.protocol = {
      kind: "standard-pcr",
      protocol_id: "neb-q5u-hot-start-m0515",
      selection: "NEB Q5U Hot Start High-Fidelity DNA Polymerase (M0515)",
      source_publication: "NEB M0515 protocol",
      source_revision: "current reviewed web protocol",
      reaction_volume_uL: { supported_25: 25, supported_50: 50 },
      primer_final_concentration_uM: { starting: 0.5 },
      magnesium_final_mM: 2,
      dntp_each_mM: 0.2,
      cycling_model: {},
      polymerase_properties: { proofreading: true, hot_start: true, product_end: "blunt" },
      difficult_template: { automatic_additive_selection: false },
      carryover_prevention: {
        dUTP_supported: true,
        UDG_built_in: false,
        enabled_by_protocol_selection_alone: false,
        note: "record actual dUTP/UDG state",
      },
      downstream_cloning: {
        product_end: "blunt",
        ta_cloning_direct: false,
        note: "TA cloning requires a separately validated A-addition step",
      },
      sequence_decision_impact: "none",
      thermodynamic_model_impact: "none",
      screening_context_note:
        "Primer3 screening context remains separate from the named bench chemistry.",
      constraints: {},
      note: "Named bench authority.",
    };
    const markdown = input(result);
    expect(markdown).toContain("NEB Q5U Hot Start High-Fidelity DNA Polymerase");
    expect(markdown).toContain("Sequence-design impact: none");
    expect(markdown).toContain("thermodynamic-model impact: none");
    expect(markdown).toContain("Primer3 screening context remains separate");
    expect(markdown).toContain("dUTP supported=true");
    expect(markdown).toContain("enabled by polymerase selection alone=false");
    expect(markdown).toContain("TA cloning requires a separately validated A-addition step");
  });

  it("keeps thermodynamic-model provenance separate from a concurrent one-pot RT-RPA handoff", () => {
    const result = structuredClone(rpaFixture) as Record<string, unknown> & {
      reaction: Record<string, unknown>;
    };
    result.reaction = {
      ...result.reaction,
      context_role: "primer-design-thermodynamic-screening-context",
      context_note: "Calculation context only; not a universal bench programme.",
    };
    result.reverse_transcription = {
      one_step: true,
      hold: { celsius: 42, seconds: 1200 },
      before: "concurrent-with-rpa",
      authority_status: "named-one-pot-rt-rpa-protocol",
      note: "RT occurs in the same isothermal reaction.",
    };
    const markdown = input(result);
    expect(markdown).toContain("## Thermodynamic screening context");
    expect(markdown).toContain("not a universal bench programme");
    expect(markdown).toContain("## Reverse-transcription handoff");
    expect(markdown).toContain("Placement: concurrent with RPA amplification");
    expect(markdown).not.toContain("before concurrent with rpa");
  });

  it("does not strip colony or digital run handoff evidence", () => {
    const colony = structuredClone(rpaFixture) as Record<string, unknown>;
    colony.colony_context = {
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
      required_observations: ["retained source colony/culture", "positive colony control"],
      note: "No lysis timing inferred.",
    };
    let markdown = input(colony);
    expect(markdown).toContain("## Colony-screen provenance");
    expect(markdown).toContain("Protocol/SOP: named colony SOP");
    expect(markdown).toContain("SOP provenance: laboratory QA system / rev 3 / 2026-08-01");
    expect(markdown).toContain("Lysis timing inferred by PCRStudio: no");
    expect(markdown).toContain("Colony/sample amount inferred by PCRStudio: no");
    expect(markdown).toContain(
      "Source recovery: user-managed-retained-source-required-for-recoverable-positive-screen",
    );

    const digital = structuredClone(rpaFixture) as Record<string, unknown>;
    digital.digital_context = {
      platform_name: "Bio-Rad QX200",
      partition_format: "droplet",
      fragmentation_state: "not-assessed",
      run_status: "design-handoff",
      threshold_status: "measured-run-required",
      quantification_status: "not-computed-from-design",
      partition_volume_authority_status:
        "record-platform/software-specific-partition-volume-model-or-calibration",
      analysis_software_version_status: "record-exact-platform-analysis-software/version-required",
      volume_precision_factor_status: "platform-specific-volume-correction-not-inferred",
      required_run_evidence: ["measured droplet run"],
      note: "Design cannot set a measured threshold.",
    };
    markdown = input(digital);
    expect(markdown).toContain("## Digital-PCR run handoff");
    expect(markdown).toContain("Threshold status: measured-run-required");
    expect(markdown).toContain("Partition-volume authority:");
    expect(markdown).toContain("Analysis software/version:");
    expect(markdown).toContain("Required run evidence: measured droplet run");
  });

  it("keeps restriction-cloning directionality and bench-control boundaries", () => {
    const result = structuredClone(rpaFixture) as Record<string, unknown>;
    result.cloning = {
      applied: true,
      tail_protocol: "neb-general-6bp",
      strategy: "two-enzyme",
      directional: null,
      protective_sequence_authority: "user-selected under supplier general rule",
      bench_controls: ["vector-only ligation control"],
      usable_enzymes: [],
      insert_boundary_contract: {
        mode: "exact-submitted-insert",
        product_size_bp: 180,
        terminal_primers_required: true,
        donor_plasmid_region_extraction: "not inferred",
        note: "Exact submitted insert only.",
      },
      note: "Different enzyme names do not prove incompatible ends.",
    };
    const markdown = input(result);
    expect(markdown).toContain("## Restriction-cloning boundary");
    expect(markdown).toContain("Directionality: unresolved");
    expect(markdown).toContain("Bench control: vector-only ligation control");
    expect(markdown).toContain("Different enzyme names do not prove incompatible ends.");
  });
  it("marks a historical successful qPCR-probe result non-orderable when the old result recorded no orderability", () => {
    const markdown = input(historicalProbeFixture);
    expect(markdown).toContain("## Orderability");
    expect(markdown).toContain("historical-result-orderability-not-recorded");
    expect(markdown).toContain("must not be used for ordering");
  });
});

describe("header", () => {
  it("leads with the label, the assay name and the day", () => {
    const markdown = input(rpaFixture, { moduleName: "RPA" });
    expect(markdown).toMatch(/^# Run 3\n/);
    expect(markdown).toContain("RPA · 2026-08-24");
  });

  it("falls back to a plain title when no label was given", () => {
    const markdown = input(rpaFixture, { label: "" });
    expect(markdown).toMatch(/^# A primer design\n/);
  });
});

describe("engines with measured pairs", () => {
  it("writes an RPA pair's oligos, product size and isothermal hold", () => {
    const markdown = input(rpaFixture);
    // The fixture carries at least one pair; a re-capture that dropped it
    // should fail loudly here rather than pass on assertions about nothing.
    const pair = rpaFixture.pairs[0]!;

    expect(markdown).toContain("### Pair 1");
    expect(markdown).toContain(`\`${pair.left.sequence}\``);
    expect(markdown).toContain(`\`${pair.right.sequence}\``);
    // Tm and GC quoted beside each sequence.
    expect(markdown).toContain(`Tm ${pair.left.tm} °C`);
    expect(markdown).toContain(`GC ${pair.left.gc_percent}%`);
    expect(markdown).toContain(`Product size: ${pair.product_size} bp`);
    expect(markdown).toContain("- Isothermal hold: 39 °C for 20 min");
  });

  it("quotes a probe assay's three oligos", () => {
    const markdown = input(historicalProbeFixture);
    const assay = historicalProbeFixture.assays[0]!;

    expect(markdown).toContain("### Assay 1");
    expect(markdown).toContain(`\`${assay.probe.sequence}\``);
    expect(markdown).toContain("**Probe**");
  });

  it("lists single primers without inventing a product size", () => {
    const markdown = input(sequencingFixture);
    const primer = sequencingFixture.primers[0]!;

    expect(markdown).toContain(`\`${primer.sequence}\``);
    expect(markdown).not.toContain("Product size:");
  });

  it("keeps restriction tails in the portable report", () => {
    const pair = rpaFixture.pairs[0]!;
    const markdown = input({
      ...rpaFixture,
      cloning: {
        applied: true,
        protective_bases: 6,
        forward_protective_bases: 6,
        reverse_protective_bases: 6,
        forward: {
          enzyme: "EcoRI",
          site: "GAATTC",
          protective: "TTATTA",
          sequence: "TTATTAGAATTC",
          length: 12,
          first_observed_activity_flanking_bases: 1,
        },
        reverse: {
          enzyme: "BamHI",
          site: "GGATCC",
          protective: "TTATTA",
          sequence: "TTATTAGGATCC",
          length: 12,
          first_observed_activity_flanking_bases: 1,
        },
        usable_enzymes: ["EcoRI", "BamHI"],
        note: "Tails applied.",
      },
    });

    expect(markdown).toContain(`\`TTATTAGAATTC${pair.left.sequence}\``);
    expect(markdown).toContain(`\`TTATTAGGATCC${pair.right.sequence}\``);
  });
});

describe("experimental boundary", () => {
  it("carries a flanking-pair validation plan into the portable report", () => {
    const markdown = input({
      ...rpaFixture,
      validation: {
        status: "in-silico-only",
        required: ["Run an NTC", "Confirm the hold temperature"],
      },
    });

    expect(markdown).toContain("## Required validation");
    expect(markdown).toContain("Status: in-silico only.");
    expect(markdown).toContain("- Run an NTC");
    expect(markdown).toContain("- Confirm the hold temperature");
  });
});

describe("named protocol overlays", () => {
  it("keeps an assembly kit recipe in the portable report", () => {
    const markdown = input({
      ...junctionFixture,
      orderability: {
        orderable: true,
        status: "orderable-named-neb-e5510",
        note: "Current named E5510 branch",
      },
      protocol: {
        selection: "NEB Gibson Assembly Cloning Kit E5510",
        source_identity: "NEB manualE2611_E5510",
        source_revision: "Version 3.0_1/26",
        source_revision_date_precision: "month",
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
      },
    });

    expect(markdown).toContain("## Selected protocol");
    expect(markdown).toContain("NEB Gibson Assembly Cloning Kit E5510");
    expect(markdown).toContain("Version 3.0_1/26");
    expect(markdown).toContain("Incubate at 50 °C for 15 min");
  });

  it("keeps a KASP cycling and control branch in the portable report", () => {
    const markdown = input({
      ...discriminatingFixture,
      protocol: {
        selection: "LGC KASP-TF V4.0 96/384 standard 61-55 C touchdown branch",
        source_identity: "LGC KASP Genotyping Assays FAQs (current web guidance)",
        source_revision: null,
        chemistry_identity: "KASP-TF V4.0 2X Master Mix 96/384",
        master_mix: "KASP-TF V4.0 2X Master Mix 96/384",
        assay_mix: "KASP Assay mix (72X)",
        reaction_volume_uL: 10,
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
      },
    });

    expect(markdown).toContain("LGC KASP-TF V4.0 96/384 standard 61-55 C touchdown branch");
    expect(markdown).toContain("revision not published/recorded");
    expect(markdown).toContain("KASP-TF V4.0 2X Master Mix 96/384");
    expect(markdown).toContain("10 touchdown cycles (61–55 °C)");
    expect(markdown).toContain("at least 2 NTC wells");
  });

  it("renders both supplier long-range cycling branches without inventing a selected bench Ta", () => {
    const markdown = input({
      ...rpaFixture,
      protocol: {
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
            final_extension: { temperature_c: 68, minutes: 10 },
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
            final_extension: { temperature_c: 68, minutes: 10 },
          },
        },
        note: "Historical named K018x branch",
      },
    });

    expect(markdown).toContain("Source: MAN0016323 · A.00 · 2016-11-28");
    expect(markdown).toContain("discontinued 2017-05-01");
    expect(markdown).toContain("silent substitution is not permitted");
    expect(markdown).toContain("Published two-step branch");
    expect(markdown).toContain("Published three-step branch");
    expect(markdown).toContain("unresolved-until-kit-compatible-annealing-temperature-authority");
    expect(markdown).not.toContain("Preferred design window: amplicon");
  });

  it("keeps the named LAMP E1700 handoff in the portable report", () => {
    const markdown = input({
      ...historicalLoopSetFixture,
      protocol: {
        selection: "NEB WarmStart LAMP Kit (DNA & RNA) E1700",
        kit_id: "E1700",
        source_identity: "NEB manualE1700",
        source_revision: "Version 6.0_3/23",
        source_revision_date_precision: "month",
        primer_concentrations_uM: { FIP: 1.6, BIP: 1.6, F3: 0.2, B3: 0.2, LoopF: 0.4, LoopB: 0.4 },
        reaction_volume_uL: 25,
        hold_temperature_c: 65,
        hold_time_min: 30,
        post_inactivation: ">80 °C for 5 min when downstream handling requires it",
      },
    });

    expect(markdown).toContain("NEB WarmStart LAMP Kit (DNA & RNA) E1700");
    expect(markdown).toContain("Version 6.0_3/23");
    expect(markdown).toContain("hold 65 °C for 30 min");
  });

  it("keeps an Eiken LAMP range overlay as a range instead of inventing a hold", () => {
    const markdown = input({
      ...historicalLoopSetFixture,
      protocol: {
        selection: "Eiken Loopamp DNA Amplification Kit LMP204/205/206",
        kit_id: "LMP204/LMP205/LMP206",
        source_identity: "Eiken Loopamp DNA Amplification Kit package insert",
        primer_concentrations_uM: { FIP: 1.6, BIP: 1.6, F3: 0.2, B3: 0.2, LoopF: 0.8, LoopB: 0.8 },
        reaction_volume_uL: 25,
        hold_temperature_range_c: [60, 65],
        hold_time_range_min: [30, 60],
        post_inactivation: "80 °C for 5 min or 95 °C for 2 min",
      },
    });

    expect(markdown).toContain("hold 60–65 °C for 30–60 min");
    expect(markdown).toContain("LoopF 0.8 µM");
    expect(markdown).not.toContain("hold 63 °C");
  });

  it("keeps the named Q5/E0554 amplification and KLD handoff", () => {
    const markdown = input({
      ...mutagenicFixture,
      orderability: {
        orderable: true,
        status: "orderable-named-q5-e0554",
        note: "Current named Q5/E0554 branch",
      },
      protocol: {
        selection: "NEB Q5 Site-Directed Mutagenesis Kit E0554",
        source_identity: "NEB manualE0554",
        source_revision: "Version 2.0_7/20",
        source_revision_date_precision: "month",
        topology: "back-to-back/non-overlapping exponential whole-plasmid PCR",
        pcr: { reaction_volume_uL: 25, primer_final_uM_each: 0.5, cycles: 25 },
        kld: { room_temperature_minutes: 5 },
        note: "Named Q5/E0554 branch only",
      },
    });

    expect(markdown).toContain("NEB Q5 Site-Directed Mutagenesis Kit E0554");
    expect(markdown).toContain("Version 2.0_7/20");
    expect(markdown).toContain("back-to-back/non-overlapping");
    expect(markdown).toContain("KLD handoff: 5 min");
  });

  it("keeps a BigDye sequencing handoff in the portable report", () => {
    const markdown = input({
      ...sequencingFixture,
      protocol: {
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
      },
    });

    expect(markdown).toContain("## Selected protocol");
    expect(markdown).toContain("BigDye Terminator v3.1");
    expect(markdown).toContain("25 cycles");
    expect(markdown).toContain("BigDye XTerminator purification");
  });

  it("keeps a TaqMan MGB chemistry handoff in the portable report", () => {
    const markdown = input({
      ...historicalProbeFixture,
      protocol: {
        selection:
          "Applied Biosystems TaqMan MGB quantification / gene-expression reference overlay",
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
        primer_constraints: {
          product_min: 50,
          product_max: 150,
          tm_min: 58,
          tm_opt: 59,
          tm_max: 60,
        },
        probe_constraints: {
          length_min: 13,
          length_opt: 20,
          length_max: 25,
          tm_min: 68,
          tm_opt: 69,
          tm_max: 70,
        },
        note: "Named protocol only",
      },
    });

    expect(markdown).toContain("## Selected protocol");
    expect(markdown).toContain(
      "Applied Biosystems TaqMan MGB quantification / gene-expression reference overlay · MGB-NFQ",
    );
    expect(markdown).toContain("Application scope: single-probe quantification");
    expect(markdown).toContain("MAN0010189 · revision F · 2025-08-26");
    expect(markdown).toContain("Protocol probe constraint ledger");
    expect(markdown).toContain("MGB probe 13–25 nt");
  });

  it("keeps a SYBR chemistry handoff in the portable report", () => {
    const markdown = input({
      ...rpaFixture,
      protocol: {
        kind: "qpcr-sybr",
        selection: "Bio-Rad iTaq Universal SYBR Green Supermix",
        master_mix: "iTaq Universal SYBR Green Supermix",
        amplicon_bp_preferred: { min: 70, max: 150 },
        primer_tm_c: { target: 60 },
        cycles: { min: 35, max: 40 },
        anneal_extend_c: 60,
        readout: "SYBR Green fluorescence with a dissociation/melt-curve review",
        note: "Named protocol only",
      },
    });

    expect(markdown).toContain("Bio-Rad iTaq Universal SYBR Green Supermix");
    expect(markdown).toContain("amplicon 70–150 bp");
  });

  it("keeps an RPA kit handoff in the portable report", () => {
    const markdown = input({
      ...rpaFixture,
      protocol: {
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
        readout: "Endpoint Basic reaction",
        note: "Named protocol only",
      },
    });

    expect(markdown).toContain("TwistAmp Basic (TABAS03KIT; DNA)");
    expect(markdown).toContain("primer preference 30–35 nt");
    expect(markdown).toContain("reviewed upper evidence boundary 45 nt");
    expect(markdown).not.toContain("1.8 mM total dNTP");
    expect(markdown).toContain("480 nM primer each");
  });

  it("keeps a digital PCR platform handoff in the portable report", () => {
    const markdown = input({
      ...rpaFixture,
      protocol: {
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
      },
    });

    expect(markdown).toContain("Bio-Rad QX200 ddPCR EvaGreen Supermix");
    expect(markdown).toContain("approximately 20000 target droplets");
  });

  it("keeps a named RACE adapter in the portable report", () => {
    const markdown = input({
      ...sequencingFixture,
      race_adapter: {
        id: "generacer-kit-25-0355-vl",
        name: "GeneRacer 5′ Primer",
        sequence: "CGACTGGAGCACGAGGACACTGA",
        protocol_identity: "thermo-fisher-generacer-kit",
        source_publication: "25-0355",
        source_revision: "Version L",
        source_revision_date: "2004-04-08",
      },
    });

    expect(markdown).toContain("Named RACE partner: GeneRacer 5′ Primer");
    expect(markdown).toContain("CGACTGGAGCACGAGGACACTGA");
    expect(markdown).toContain("Source publication: 25-0355");
    expect(markdown).toContain("Source revision: Version L");
  });
});

describe("engines read from their order sheet", () => {
  it("renders a LAMP loop set as a What to order table", () => {
    const markdown = input(historicalLoopSetFixture);
    const line = historicalLoopSetFixture.order_sheet[0]!;

    expect(markdown).toContain("## What to order");
    expect(markdown).toContain(line.name);
    expect(markdown).toContain(`\`${line.sequence}\``);
    expect(markdown).not.toContain("Cycling protocol");
  });

  it("does not duplicate the order sheet for a pair engine", () => {
    const markdown = input(rpaFixture);
    expect(markdown).not.toContain("## What to order");
  });

  it("keeps the LAMP design-model and diagnostic-temperature boundary in the portable report", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body = structuredClone(historicalLoopSetFixture) as Record<string, any>;
    body.reaction = {
      ...body.reaction,
      hold: undefined,
      diagnostic_structure_temperature_c: 65,
      context_role:
        "generic Bst structure-diagnostic model with named-protocol role concentrations",
      context_note: "Structure diagnostics only; this is not a bench hold.",
    };
    body.parameter_set = {
      ...body.parameter_set,
      thermodynamic_model: {
        id: "primerexplorer-v5-sl96-tm-sl98-end-dg",
        tm_reference:
          "SantaLucia et al. 1996 nearest-neighbour + PrimerExplorer Mg-to-Na correction",
        end_stability_reference: "SantaLucia 1998 unified ΔG37 over terminal 6 bases",
        oligo_concentration_uM: 0.1,
        sodium_mM: 50,
        magnesium_mM: 4,
        effective_sodium_mM: 151.846,
        role: "LAMP design eligibility/ranking only; not the selected kit master-mix model",
      },
    };
    const result = loopSetResultSchema.parse(body);
    const report = reportMarkdown({
      label: "LAMP",
      createdAt: "2026-09-01T00:00:00Z",
      moduleName: "LAMP",
      result,
    });
    expect(report).toContain("## LAMP design-model boundary");
    expect(report).toContain("primerexplorer-v5-sl96-tm-sl98-end-dg");
    expect(report).toContain("Structure-diagnostic temperature: 65 °C");
    expect(report).toContain("this is not a bench hold");
  });

  it("renders source-bounded LAMP identities with unresolved bench details without crashing or fabricating values", () => {
    // Some legacy identities are enzyme/formulation authorities, not complete bench recipes.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body = structuredClone(historicalLoopSetFixture) as Record<string, any>;
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
    const result = loopSetResultSchema.parse(body);
    const report = reportMarkdown({
      label: "LAMP assembled enzyme",
      createdAt: "2026-09-04T00:00:00Z",
      moduleName: "LAMP",
      result,
    });
    expect(report).toContain("volume not resolved");
    expect(report).toContain("bench hold not resolved");
    expect(report).toContain("Primer concentrations: not asserted by this registry identity");
    expect(report).not.toContain("undefined µL");
  });

  it("does not reinterpret the historical LAMP hold field in the portable report", () => {
    const result = loopSetResultSchema.parse(historicalLoopSetFixture);
    const report = reportMarkdown({
      label: "LAMP",
      createdAt: "2026-09-01T00:00:00Z",
      moduleName: "LAMP",
      result,
    });
    expect(report).toContain("Structure-diagnostic temperature: not recorded in historical result");
    expect(report).toContain("Historical saved temperature field: 65 °C");
  });

  it("keeps flanking purpose ranking and override provenance in the portable report", () => {
    // This test deliberately mutates a captured JSON response to model a newer worker.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body = structuredClone(rpaFixture) as Record<string, any>;
    body.purpose = {
      id: "screen",
      name: "Screening on a gel",
      summary: "Present or absent, decided by eye.",
      constraints: { product_min: 150, product_max: 500 },
      ranking_weights: { specificity: 2 },
      overridden: ["product_max"],
    };
    const result = designResultSchema.parse(body);
    const report = reportMarkdown({
      label: "Flanking",
      createdAt: "2026-09-01T00:00:00Z",
      moduleName: "Standard PCR",
      result,
    });
    expect(report).toContain("## Search purpose");
    expect(report).toContain("Ranking weights: specificity=2");
    expect(report).toContain("Explicit request overrides of purpose constraints: product_max");
  });

  it("keeps the LAMP readout boundary in the portable report", () => {
    const result = loopSetResultSchema.parse({
      ...historicalLoopSetFixture,
      readout: {
        selection: "colorimetric",
        sequence_decision_impact: "none",
        note: "Colorimetric readout needs empirical controls; no positivity threshold is inferred from sequence.",
      },
    });
    const report = reportMarkdown({
      label: "LAMP",
      createdAt: "2026-09-01T00:00:00Z",
      moduleName: "LAMP",
      result,
    });
    expect(report).toContain("## LAMP readout / detection boundary");
    expect(report).toContain("Selection: colorimetric");
    expect(report).toContain("Sequence-selection impact: none");
  });
});
