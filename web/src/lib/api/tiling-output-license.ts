import { z } from "zod";

/** Provenance/licensing metadata attached to generated tiling schemes. */
export const tilingOutputLicenseSchema = z.object({
  spdx: z.string(),
  applies_to: z.string(),
  attribution_required: z.boolean(),
  share_alike: z.boolean(),
  upstream: z.string(),
  input_license_separate: z.boolean(),
});
