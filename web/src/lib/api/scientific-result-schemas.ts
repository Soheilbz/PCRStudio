import { z } from "zod";

export const methodFidelityRowSchema = z
  .object({
    method_id: z.string(),
    use_role: z.string(),
    display_name: z.string(),
    grade: z.enum([
      "F0-upstream-exact",
      "F1-exact-public-port",
      "F2-manual-rule-faithful",
      "F3-compatible-approximate",
      "F4-external-authority-only",
    ]),
    implementation: z.string(),
    decision_impact: z.string(),
    scientific_strict_eligible: z.boolean(),
    public_algorithm_complete: z.boolean(),
    upstream_code_available: z.boolean(),
    claim_boundary: z.string(),
    authority_url: z.string(),
  })
  .strict();

export const methodFidelityRegistrySchema = z
  .object({
    registry_id: z.string(),
    registry_schema_version: z.string(),
    canonical_sha256: z.string(),
  })
  .strict();
export const scientificAuthorityIdentitySchema = z
  .object({
    authority_id: z.string(),
    authority_revision: z.string(),
    effective_date: z.string().nullable().optional(),
    canonical_source: z.string(),
    canonical_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  })
  .strict();

export const speciesRevalidationPolicySchema = z.object({
  silent_update_allowed: z.literal(false),
  triggers: z.array(z.string()),
  required_action: z.string(),
  claim_boundary: z.string(),
});

export const digitalPlatformAuthorityReferenceSchema = z.object({
  software_suite_reference: z.string(),
  volume_precision_factor_reference: z.string(),
  authority_use: z.string(),
  inference_policy: z.string(),
});

export const digitalMultiplexContextSchema = z
  .object({
    mode: z.enum(["channel", "amplitude", "hybrid", "probe-mix"]),
    panel: z
      .array(
        z
          .object({
            target: z.string(),
            reporter: z.string().nullable().optional(),
            channel: z.string().nullable().optional(),
            amplitude_class: z.string().nullable().optional(),
            primer_each_nm: z.number().positive().optional(),
            probe_nm: z.number().positive().optional(),
          })
          .strict(),
      )
      .min(2)
      .max(12),
    panel_sha256: z.string().regex(/^[0-9a-f]{64}$/),
    target_count: z.number().int().min(2).max(12),
    software_planning_bound: z.literal(12),
    wet_lab_qualified_plex: z.null(),
    sequence_design_scope: z.string(),
    threshold_rain_cluster_inference: z.literal("forbidden-from-sequence"),
    run_evidence: z.record(z.string(), z.unknown()).nullable().optional(),
    decision_impact: z.literal("planning-and-run-evidence-only"),
  })
  .strict();

export const raceAdapterSchema = z.object({
  id: z.string().optional(),
  name: z.string(),
  sequence: z.string(),
  direction: z.string().optional(),
  round: z.string().optional(),
  authority: z.string().optional(),
  protocol_identity: z.string().optional(),
  source_publication: z.string().optional(),
  source_identity: z.string().optional(),
  source_url: z.string().optional(),
  source_reviewed_date: z.string().optional(),
  source_revision: z.string().optional(),
  source_revision_date: z.string().optional(),
});

export const raceContextSchema = z.object({
  substrate: z.enum(["total-rna", "mrna", "cdna"]),
  preparation: z.string(),
  caller_sop_revision: z.string().optional(),
  caller_sop_sha256: z
    .string()
    .regex(/^[0-9a-f]{64}$/)
    .optional(),
  round: z.enum(["primary", "nested"]),
  polyadenylated: z.boolean().nullable().optional(),
  end_status: z.literal("candidate-transcript-end"),
  validation_required: z.array(z.string()).default([]),
  note: z.string(),
});

export const modifiedOligoAnnotationSchema = z
  .object({
    role: z.string().min(1).max(40),
    sequence: z
      .string()
      .regex(/^[ACGT]+$/)
      .max(500)
      .optional(),
    fivePrimeLabel: z.string().max(80).optional(),
    threePrimeBlock: z.string().max(80).optional(),
    fluorophore: z.string().max(80).optional(),
    quencher: z.string().max(80).optional(),
    affinityLabel: z.string().max(80).optional(),
    lateralFlowLabel: z.string().max(80).optional(),
    cleavageSite: z.number().int().min(0).max(499).optional(),
    manufacturerNotes: z.string().max(500).optional(),
    internalModifications: z
      .array(
        z
          .object({
            kind: z.enum(["thf", "dSpacer", "fluorophore", "quencher", "other-reviewed"]),
            position: z.number().int().min(0).max(499),
            identity: z.string().max(80).optional(),
          })
          .strict(),
      )
      .max(12)
      .optional(),
  })
  .strict();

export const modifiedOligosProvenanceSchema = z
  .object({
    schema: z.literal("contracts/oligos/modified-oligo.schema.json"),
    annotations: z.array(modifiedOligoAnnotationSchema).max(24),
    decision_impact: z.literal("none"),
    note: z.string(),
  })
  .strict();
