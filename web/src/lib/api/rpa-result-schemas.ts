import { z } from "zod";

const rpaPreparedOligoSchema = z
  .object({
    sequence: z.string(),
    source_pair_rank: z.number().int().positive(),
    start: z.number().int().nonnegative(),
    length: z.number().int().positive(),
  })
  .strict();

export const rpaFullEmpiricalAssayDevelopmentSchema = z
  .object({
    authority: z.string(),
    source_url: z.string(),
    forward_candidates_recommended: z.tuple([z.number().int(), z.number().int()]),
    reverse_candidates_recommended: z.tuple([z.number().int(), z.number().int()]),
    pair_matrix_recommended: z.tuple([z.number().int(), z.number().int()]),
    prepared_forward_candidates: z.array(rpaPreparedOligoSchema),
    prepared_reverse_candidates: z.array(rpaPreparedOligoSchema),
    prepared_matrix_pair_count: z.number().int().nonnegative(),
    matrix_ready: z.boolean(),
    selection_basis: z.string(),
    sequence_prediction_equivalence: z.boolean(),
    status: z.string(),
    note: z.string(),
  })
  .strict();

export const rpaMultiplexPanelResultSchema = z
  .object({
    status: z.string(),
    panel: z.array(
      z
        .object({
          target: z.string(),
          forward_primer: z.string(),
          reverse_primer: z.string(),
          detection_identity: z.string().nullable().optional(),
          empirical_evidence_ref: z.string().nullable().optional(),
        })
        .strict(),
    ),
    panel_sha256: z.string(),
    target_count: z.number().int().positive(),
    software_planning_bound: z.number().int().positive(),
    wet_lab_qualified_plex: z.null(),
    peer_empirical_evidence_complete: z.boolean(),
    selection_authority: z.string(),
    decision_impact: z.literal("evidence-only"),
  })
  .strict();
