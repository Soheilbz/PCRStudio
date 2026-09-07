import { z } from "zod";

/**
 * Current workers return the complete transcript/variant mode audit. The
 * historical string form remains readable so saved pre-contract runs stay
 * renderable while new runs are checked against the structured shape.
 */
export const transcriptModeSchema = z
  .union([
    z.string(),
    z
      .object({
        mode: z.string(),
        junctions: z.array(z.number()).default([]),
        probe_variant_positions: z.array(z.number()).default([]),
        coordinate_system: z.string(),
      })
      .loose(),
  ])
  .optional();
