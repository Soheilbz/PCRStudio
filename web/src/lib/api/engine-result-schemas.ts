import { z } from "zod";

const nullableNumber = z.number().nullable();

export const outwardClosureResultShape = {
  topology_validation: z
    .object({
      status: z.string(),
      reason: z.string().optional(),
      enzyme: z.string().optional(),
      cut_count: z.number().int().nonnegative().optional(),
      cut_positions: z.array(z.number()).optional(),
      left_flanking_cut: z.number().optional(),
      right_flanking_cut: z.number().optional(),
      fragment_length: z.number().positive().optional(),
      anchor_offset: z.number().nonnegative().optional(),
      anchor_length: z.number().positive().optional(),
      upstream_flank_length: z.number().nonnegative().optional(),
      downstream_flank_length: z.number().nonnegative().optional(),
      unknown_flank_total: z.number().nonnegative().optional(),
      source_segments: z
        .array(
          z.object({
            source_start: z.number().nonnegative(),
            source_end: z.number().nonnegative(),
            length: z.number().nonnegative(),
          }),
        )
        .optional(),
      origin_spanning: z.boolean().optional(),
      ligation_junction: z
        .object({
          left_source_cut: z.number(),
          right_source_cut: z.number(),
          circle_coordinate: z.number(),
          status: z.string(),
        })
        .optional(),
      circle_sha256: z.string().optional(),
      reference_length: z.number().positive().optional(),
      reference_circular: z.boolean().optional(),
      anchor_start: z.number().nonnegative().optional(),
      anchor_end: z.number().positive().optional(),
      submitted_anchor_orientation: z.string().optional(),
      coordinate_system: z.string().optional(),
      decision_impact: z.string(),
    })
    .loose()
    .nullable()
    .optional(),
};

const mgbCandidateSchema = z
  .object({
    candidate_id: z.string(),
    sequence: z.string(),
    template_start: z.number().int().nonnegative(),
    length: z.number().int().positive(),
    strand: z.string(),
    tm: z.number().optional(),
    tm_source: z.string().optional(),
  })
  .loose();

export const probeClosureResultShape = {
  optical_authority: z
    .object({
      status: z.string(),
      schema: z.string().optional(),
      authority_id: z.string().optional(),
      instrument: z.string().optional(),
      version: z.string().optional(),
      validations: z.array(z.record(z.string(), z.unknown())).default([]),
      decision_impact: z.string(),
      note: z.string(),
    })
    .loose()
    .optional(),
  mgb_authority: z
    .object({
      status: z.string().optional(),
      exchange: z
        .object({
          schema: z.literal("pcrstudio.mgb-authority-exchange.v1"),
          mode: z.string(),
          authority_id: z.string(),
          candidate_set_sha256: z.string(),
          candidates: z.array(mgbCandidateSchema),
          decision_impact: z.string(),
          note: z.string(),
        })
        .optional(),
      resolution: z
        .object({
          schema: z.literal("pcrstudio.mgb-authority-resolution.v1"),
          status: z.string(),
          authority_id: z.string(),
          candidate_set_sha256: z.string(),
          tool: z.string(),
          version: z.string(),
          calculated_at: z.string(),
          target_tm_c: z.number(),
          ranked_candidates: z.array(mgbCandidateSchema),
          decision_impact: z.string(),
          note: z.string(),
        })
        .optional(),
    })
    .loose()
    .optional(),
  multiplex_interactions: z
    .object({
      status: z.string(),
      pairs: z.array(z.record(z.string(), z.unknown())).default([]),
      decision_impact: z.string().optional(),
      threshold: z.string().optional(),
      note: z.string().optional(),
    })
    .loose()
    .nullable()
    .optional(),
};

export const singleClosureResultShape = {
  primer_walking: z
    .object({
      requested: z.boolean(),
      usable_read_length: z.number().positive(),
      overlap: z.number().nonnegative(),
      step: z.number().positive(),
      windows: z.array(
        z.object({
          walk_index: z.number().int().positive(),
          target_start: z.number().int().nonnegative(),
          target_end: z.number().int().positive(),
          target_length: z.number().int().positive(),
          overlap: z.number().int().nonnegative(),
          status: z.string(),
        }),
      ),
      decision_impact: z.string(),
      note: z.string(),
    })
    .nullable()
    .optional(),
  trace_review: z
    .object({
      schema: z.literal("pcrstudio.sanger-abif-evidence.v1"),
      status: z.literal("reviewed-abif"),
      filename: z.string().nullable(),
      file_bytes: z.number().int().nonnegative(),
      basecalls: z.string(),
      base_count: z.number().int().nonnegative(),
      positions: z.array(z.number().int().nonnegative()),
      qualities: z.array(z.number().int().nonnegative()),
      mean_phred: nullableNumber,
      q20_interval: z
        .object({
          start: z.number().int().nonnegative(),
          end: z.number().int().nonnegative(),
          length: z.number().int().nonnegative(),
        })
        .nullable(),
      q20_interval_semantics: z.string(),
      mixed_peak_secondary_ratio_threshold: z.number(),
      mixed_peaks: z.array(
        z.object({
          base_index: z.number().int().nonnegative(),
          basecall: z.string(),
          primary_channel: z.string(),
          secondary_channel: z.string(),
          secondary_ratio: z.number(),
        }),
      ),
      trace_order: z.string(),
      traces: z.record(z.string(), z.array(z.number().int().nonnegative())),
      decision_impact: z.string(),
      note: z.string(),
    })
    .nullable()
    .optional(),
  nested_gsp_plan: z
    .object({
      status: z.string(),
      primary: z.record(z.string(), z.unknown()),
      nested: z.record(z.string(), z.unknown()),
      direction: z.string(),
      partner_primary: z.record(z.string(), z.unknown()).nullable().optional(),
      partner_nested: z.record(z.string(), z.unknown()).nullable().optional(),
      decision_impact: z.string(),
      note: z.string(),
    })
    .loose()
    .nullable()
    .optional(),
};

const toolStatusSchema = z.record(z.string(), z.unknown());
export const tilingClosureResultShape = {
  native_visualisations: z
    .object({
      status: z.string(),
      artifacts: z
        .array(
          z
            .object({ kind: z.string(), name: z.string(), sha256: z.string(), content: z.string() })
            .loose(),
        )
        .default([]),
      tool_runs: z.array(z.record(z.string(), z.unknown())).default([]),
      warnings: z.array(z.string()).default([]),
      decision_impact: z.string(),
      note: z.string(),
    })
    .optional(),
  managed_tools: z.record(z.string(), toolStatusSchema).optional(),
  observed_depth_evidence: z
    .object({
      schema: z.literal("pcrstudio.tiling-depth-evidence.v1"),
      status: z.string(),
      dropout_threshold: z.number().nonnegative(),
      rows: z.array(
        z.object({ amplicon: z.string(), depth: z.number().nonnegative(), dropout: z.boolean() }),
      ),
      summary: z.object({
        amplicons: z.number().int().nonnegative(),
        mean_depth: z.number().nonnegative(),
        minimum_depth: z.number().nonnegative(),
        dropout_count: z.number().int().nonnegative(),
      }),
      dropouts: z.array(
        z.object({ amplicon: z.string(), depth: z.number().nonnegative(), dropout: z.boolean() }),
      ),
      decision_impact: z.string(),
      note: z.string(),
    })
    .optional(),
  dropout_repair_handoff: z
    .object({
      schema: z.literal("pcrstudio.tiling-repair-handoff.v1"),
      status: z.string(),
      source_operation: z.string(),
      dropout_amplicons: z.array(z.string()),
      recommended_operation: z.string(),
      decision_impact: z.string(),
      causal_claim: z.string(),
      note: z.string(),
    })
    .optional(),
  scheme_version_diff: z
    .object({
      schema: z.literal("pcrstudio.scheme-diff.v1"),
      status: z.string(),
      added: z.array(z.string()),
      removed: z.array(z.string()),
      changed: z.array(z.string()),
      unchanged_count: z.number().int().nonnegative(),
      decision_impact: z.string(),
    })
    .nullable()
    .optional(),
  version_transition: z
    .object({
      current: z.string(),
      recommended: z.string(),
      reason: z.string(),
      auto_publish: z.boolean(),
      note: z.string(),
    })
    .nullable()
    .optional(),
};
