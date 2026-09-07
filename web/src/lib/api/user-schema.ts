import { z } from "zod";

export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  displayName: z.string(),
  createdAt: z.string(),
  role: z.enum(["user", "admin"]),
});

export type User = z.infer<typeof userSchema>;
