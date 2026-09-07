import { z } from "zod";

/** Account/project/job ceilings reported by the Rust store. */
export const projectLimitsSchema = z.object({
  maxProjectsPerUser: z.number(),
  maxRunsPerProject: z.number(),
  maxAccountDataBytes: z.number(),
  maxNameLength: z.number(),
  undoWindowDays: z.number(),
  maxActiveRunJobsPerUser: z.number(),
  maxRetainedRunJobsPerUser: z.number(),
  maxRunJobRequestBytes: z.number(),
  maxRunJobDataBytesPerUser: z.number(),
  runJobRetentionDays: z.number(),
});
