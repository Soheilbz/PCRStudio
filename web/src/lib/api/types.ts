/**
 * The wire contract with the core, restated in TypeScript.
 *
 * These schemas are the only place the frontend asserts what the backend sends.
 * Parsing rather than casting means a drift between Rust and TypeScript shows
 * up as a loud, located error instead of `undefined` three components later.
 *
 * Closed vocabularies with an existing canonical contract are imported from
 * generated projections. Vocabulary wording remains owned by the core and is
 * published at `/goals`, `/engines` and `/modifiers`; the interface does not
 * maintain a second engine registry.
 *
 * The interface calls an assay profile a *module*, which is what it is to
 * somebody using it: one design system with its own page and its own form.
 */
import { z } from "zod";
import foundationContract from "@/lib/contracts/foundation.generated.json";
import { ENGINE_IDS } from "@/lib/contracts/module-bindings.generated";
import {
  GOAL_IDS,
  MODIFIER_IDS,
  MODULE_STATUS_IDS,
} from "@/lib/contracts/domain-vocabulary.generated";
import {
  rpaFullEmpiricalAssayDevelopmentSchema,
  rpaMultiplexPanelResultSchema,
} from "./rpa-result-schemas";
import {
  outwardClosureResultShape,
  probeClosureResultShape,
  singleClosureResultShape,
  tilingClosureResultShape,
} from "./engine-result-schemas";
import { tilingOutputLicenseSchema } from "./tiling-output-license";
import { projectLimitsSchema } from "./project-limits";
import { userSchema } from "./user-schema";
import { transcriptModeSchema } from "./transcript-mode";

export { userSchema } from "./user-schema";
import {
  digitalMultiplexContextSchema,
  digitalPlatformAuthorityReferenceSchema,
  methodFidelityRegistrySchema,
  methodFidelityRowSchema,
  modifiedOligosProvenanceSchema,
  raceAdapterSchema,
  raceContextSchema,
  scientificAuthorityIdentitySchema,
  speciesRevalidationPolicySchema,
} from "./scientific-result-schemas";
export { projectLimitsSchema } from "./project-limits";
export { scientificAuthorityIdentitySchema } from "./scientific-result-schemas";

const CURRENT_DRAFT_SCHEMA_VERSION = foundationContract.draft_schema_version;
const CURRENT_REQUEST_SCHEMA_VERSION = foundationContract.request_schema_version;
const CURRENT_RESULT_SCHEMA_VERSION = foundationContract.result_schema_version;
const CURRENT_MODULE_CONTRACT_VERSION = foundationContract.module_contract_version;
export const goalSchema = z.enum(GOAL_IDS);
export type Goal = z.infer<typeof goalSchema>;
export const engineIdSchema = z.enum(ENGINE_IDS);
export type EngineId = z.infer<typeof engineIdSchema>;
/** Something applied to an engine rather than listed beside it. */
export const modifierSchema = z.enum(MODIFIER_IDS);
export type Modifier = z.infer<typeof modifierSchema>;
export const moduleStatusSchema = z.enum(MODULE_STATUS_IDS);
export type ModuleStatus = z.infer<typeof moduleStatusSchema>;
/** One assay: an engine, the goal it serves, and its wording. */
export const moduleManifestSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  summary: z.string(),
  /** What sets it apart from its neighbours, and when to reach for it. */
  guidance: z.string(),
  engine: engineIdSchema,
  goal: goalSchema,
  status: moduleStatusSchema,
  modifiers: z.array(modifierSchema),
  /**
   * What this assay differs from its engine's own defaults by.
   *
   * The server has always sent this and this schema always dropped it, which
   * meant the form could not know its own assay's numbers. Long-range PCR pins
   * the long-range enzyme mix in `profiles.toml`; the form seeded standard Taq
   * and sent it on every run, so the pinned enzyme never once applied.
   *
   * Loose about its contents on purpose. The constraint and cycling names
   * belong to the worker, which publishes them and refuses one it does not
   * know — a second list here could only go stale.
   */
  defaults: z
    .object({
      polymerase: z.string().nullish(),
      allowedPolymerases: z.array(z.string()).default([]),
      chemistryFamily: z.string().nullish(),
      defaultPurpose: z.string().nullish(),
      purposes: z.array(z.string()).default([]),
      constraints: z.record(z.string(), z.unknown()).default({}),
      cycling: z.record(z.string(), z.unknown()).default({}),
    })
    .default({ allowedPolymerases: [], purposes: [], constraints: {}, cycling: {} }),
  /** Inputs this assay cannot be run without — see `Requirement` in pcr-core. */
  requires: z.array(z.string()).default([]),
});
export type ModuleManifest = z.infer<typeof moduleManifestSchema>;

/** One engine, and what it will be combined with. */
export const engineDescriptionSchema = z.object({
  id: engineIdSchema,
  name: z.string(),
  input: z.string(),
  accepts: z.array(modifierSchema),
  /** Whether asking it to design something produces a result or a refusal. */
  implemented: z.boolean(),
});
export type EngineDescription = z.infer<typeof engineDescriptionSchema>;

/** One goal, the rule that decides what belongs in it, and how many do. */
export const goalDescriptionSchema = z.object({
  id: goalSchema,
  label: z.string(),
  rule: z.string(),
  count: z.number().int().nonnegative(),
});
export type GoalDescription = z.infer<typeof goalDescriptionSchema>;

/** One modifier and its wording. */
export const modifierTermSchema = z.object({
  id: modifierSchema,
  label: z.string(),
});
export type ModifierTerm = z.infer<typeof modifierTermSchema>;

/**
 * What a status word claims, and what would change it.
 *
 * A badge reading "Experimental" with nothing behind it is not a claim
 * anybody can act on, and the people this is for are deciding whether to order
 * oligos from it. All twenty-one assays carry that word, so the sentence
 * behind it is the most consequential one in the catalogue.
 */
export const statusTermSchema = z.object({
  id: moduleStatusSchema,
  label: z.string(),
  /** What the word claims, in the words somebody at a bench would use. */
  means: z.string(),
  /** What it would take to move past it. Absent for the last one. */
  promotion: z.string().nullish(),
});
export type StatusTerm = z.infer<typeof statusTermSchema>;

export type User = z.infer<typeof userSchema>;

export const sessionSchema = z.object({
  user: userSchema,
  token: z.string(),
  expiresIn: z.number().int().positive(),
  /**
   * Present only on the two responses that mint one — registering, and
   * recovering — and absent on an ordinary sign-in.
   *
   * This is the only time it exists in plain text anywhere. It is stored
   * hashed, it cannot be read back, and it is not sent again.
   */
  recoveryCode: z.string().optional(),
});
export type Session = z.infer<typeof sessionSchema>;

export const endedSchema = z.object({ ended: z.number().int().nonnegative() });

/** Metadata carried by the common Rust HTTP error envelope. */
export const apiErrorEnvelopeMetaShape = {
  code: z.string().optional(),
  fieldPath: z.string().nullable().optional(),
  stage: z.string().nullable().optional(),
  retryable: z.boolean().optional(),
  requestId: z.string().nullable().optional(),
};

/** Mirrors `pcr_accounts::AccountError`, plus the limiter's own refusal. */
export const accountErrorSchema = z.discriminatedUnion("kind", [
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("emailTaken") }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("invalidEmail"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("weakPassword"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("invalidName"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("invalidCredentials") }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("sessionEnded") }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("noSuchUser") }),
  /* A setting whose value is wrong: about the request, not the name. */
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("badRequest"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("store"), detail: z.string() }),
  z.object({
    ...apiErrorEnvelopeMetaShape,
    kind: z.literal("tooManyAttempts"),
    detail: z.string(),
  }),
  /* Too many wrong recovery codes against one account, too recently. Its own
     kind rather than folded into invalidCredentials, because the two need
     different words: "that was wrong" against "stop, and come back later". */
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("recoveryLocked") }),
  /* The design endpoints refusing work rather than credentials. */
  z.object({
    ...apiErrorEnvelopeMetaShape,
    kind: z.literal("tooManyRequests"),
    detail: z.string(),
  }),
]);
export type AccountError = z.infer<typeof accountErrorSchema>;

/** A recovery code on its way to somebody, once. */
export const recoveryCodeSchema = z.object({ recoveryCode: z.string() });

/** Whether an account has a recovery code, for the settings page to say so. */
export const recoveryStatusSchema = z.object({
  /** False for accounts made before recovery existed. */
  hasCode: z.boolean(),
  issuedAt: z.string().nullable(),
});
export type RecoveryStatus = z.infer<typeof recoveryStatusSchema>;

export const appInfoSchema = z.object({
  name: z.string(),
  version: z.string(),
});
export type AppInfo = z.infer<typeof appInfoSchema>;

/** Mirrors `pcr_core::CoreError`, which serialises as a tagged union. */
export const coreErrorSchema = z.discriminatedUnion("kind", [
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("unknownProfile"), detail: z.string() }),
  z.object({
    ...apiErrorEnvelopeMetaShape,
    kind: z.literal("duplicateProfile"),
    detail: z.string(),
  }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("unknownEngine"), detail: z.string() }),
  z.object({
    ...apiErrorEnvelopeMetaShape,
    kind: z.literal("incompatibleModifier"),
    detail: z.string(),
  }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("invalidRequest"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("notImplemented"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("toolFailed"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("workerBusy"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("cancelled"), detail: z.string() }),
]);
export type CoreError = z.infer<typeof coreErrorSchema>;

/**
 * The one vocabulary whose wording stays here rather than coming over the wire.
 *
 * A status badge renders in a dozen places, several of them client components
 * with no loader of their own, and each label is the identifier with a capital
 * letter — there is nothing here that can drift without the enum drifting too.
 */
/* ── What a design run sends and gets back ─────────────────────────────── */

/** One oligo, measured. */
export const oligoSchema = z.object({
  sequence: z.string(),
  length: z.number(),
  gc_percent: z.number(),
  tm: z.number(),
  hairpin: z.object({ found: z.boolean(), dg: z.number(), tm: z.number() }),
  self_dimer: z.object({ found: z.boolean(), dg: z.number(), tm: z.number() }),
  three_prime_dg: z.number(),
});
export type Oligo = z.infer<typeof oligoSchema>;

/** One term of a candidate's score, and the sentence that explains it. */
export const scoreComponentSchema = z.object({
  name: z.string(),
  value: z.number(),
  detail: z.string(),
});

/** Somewhere a primer would sit that nobody asked it to. */
const specificitySiteSchema = z
  .object({
    role: z.string(),
    contig: z.string(),
    three_prime_at: z.number(),
    orientation: z.enum(["forward", "reverse"]),
    mismatches: z.number(),
    ambiguous_bases: z.number().default(0),
    mismatch_upper_bound: z.number().optional(),
    mismatch_positions_from_three_prime: z.array(z.number()).optional(),
    ambiguous_positions_from_three_prime: z.array(z.number()).optional(),
    mismatch_base_pairs_from_three_prime: z
      .array(
        z.object({
          position: z.number(),
          primer_base: z.string(),
          template_base: z.string(),
          background_plus_base: z.string(),
        }),
      )
      .optional(),
    nearest_three_prime_mismatch: z.number().nullable().optional(),
    dg: z.number(),
    tm: z.number(),
  })
  .loose();

const specificityMethodSchema = z
  .object({
    id: z.string(),
    version: z.number(),
    scope: z.enum(["template-only", "supplied-background", "reported-by-caller"]),
    seed: z
      .object({
        strategy: z.literal("pigeonhole-k-plus-one-partitions"),
        match: z.string(),
        position: z.string(),
        terminal_mismatch_included: z.literal(true),
      })
      .loose(),
    mismatch_scope: z.string(),
    mismatch_topology: z
      .object({
        position_origin: z.string(),
        terminal_position: z.number(),
        reported_fields: z.array(z.string()),
        decision_role: z.string(),
      })
      .optional(),
    max_mismatches: z.number(),
    binding_score: z
      .object({ model: z.string(), minimum_dg_kcal_mol: z.number().nullable() })
      .loose(),
    product_rule: z.string(),
    max_product: z.number(),
    indexed_search: z.boolean(),
    alignment_gaps: z.boolean(),
    whole_database: z.boolean(),
    handoff: z
      .object({
        required_above_background_bases: z.number(),
        method: z.string(),
        automatic: z.boolean(),
        reason: z.string(),
      })
      .optional(),
    ambiguity_policy: z.string().optional(),
    limitations: z.array(z.string()),
  })
  .loose();

/** One binding site inside an off-target product. */
export const offTargetProductSchema = z.object({
  contig: z.string(),
  start: z.number(),
  end: z.number(),
  size: z.number(),
  worst_dg: z.number(),
  forward: specificitySiteSchema.optional(),
  reverse: specificitySiteSchema.optional(),
});

/**
 * Where a set of oligos could sit, other than where it was meant to.
 *
 * One shape for all six workers that scan. Six of the twenty-one pages showed
 * a specificity step whose answer went nowhere, and the fix put the same
 * function behind all of them — this is the type of what it returns, written
 * once for the same reason.
 */
export const offTargetsSchema = z
  .object({
    checked: z.boolean(),
    /** Explicit reason/state when a direct scan did not run; never infer zero hits from checked=false. */
    classification: z.string().optional(),
    background_bases: z.number().optional(),
    direct_limit_bases: z.number().optional(),
    serious: z.number().optional(),
    site_count: z.number().optional(),
    product_count: z.number().optional(),
    terminal_mismatch_scan: z.boolean().optional(),
    method: specificityMethodSchema.optional(),
    products: z.array(offTargetProductSchema).optional(),
    note: z.string().optional(),
  })
  .loose()
  // Older saved runs predate the shared specificity block. Preserve those
  // results as explicitly unchecked rather than refusing to render them or
  // accidentally presenting missing evidence as a clean scan.
  .default({ checked: false });
export type OffTargets = z.infer<typeof offTargetsSchema>;

/**
 * How far the scan looked, carried once per result.
 *
 * `template_only` is the field that keeps two different claims apart: checked
 * against a genome and found unique, versus checked against your own sequence
 * and nothing else. Both report zero off-targets and only one of them is about
 * the sample.
 */
export const backgroundSchema = z
  .object({
    checked: z.boolean(),
    bases: z.number(),
    contigs: z.number(),
    max_mismatches: z.number(),
    method: specificityMethodSchema.optional(),
    template_only: z.boolean().default(false),
    sequence_topology_assumption: z.string().optional(),
    topology_note: z.string().optional(),
    panel_sha256: z
      .string()
      .regex(/^[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    ambiguous_bases: z.number().int().nonnegative().optional(),
    panel_role: z.literal("exclusivity").optional(),
    panel_hash_scope: z.string().optional(),
    panel_identity_claim: z.literal("content-identity-only-not-taxonomic-completeness").optional(),
    panel_provenance: z.string().optional(),
    panel_selection_rationale: z.string().optional(),
    taxonomy_resolution_status: z.literal("not-resolved-from-fasta-labels").optional(),
    biological_traceability_status: z
      .enum([
        "not-validated-from-fasta-alone",
        "user-declared-provenance-recorded-not-independently-validated",
      ])
      .optional(),
    diversity_coverage_status: z.literal("not-computed-from-panel-hash").optional(),
    population_frequency_status: z.literal("not-computed").optional(),
    surveillance_status: z.literal("external-versioned-review-required").optional(),
    note: z.string().default(""),
  })
  .loose();
export type BackgroundScan = z.infer<typeof backgroundSchema>;

/**
 * Spread into every result whose worker scans.
 *
 * Optional, and the absence means something: a run saved before the scan
 * existed has no background block at all, which is a different statement from
 * `checked: false` — that one is a run that could have scanned and did not.
 * Neither should be read as "scanned and clean".
 */
const carriesScan = { background: backgroundSchema.optional() };

/**
 * What was put on the two primer ends, when a cloning tail was asked for.
 *
 * The worker has built these since it was written and nothing could ask for
 * them: the module that exists to add restriction sites was ordering bare
 * primers. `applied: false` means the run was asked and could not — the reason
 * is in `note` — which is a different thing from the block being absent.
 */
export const cloningTailsSchema = z
  .object({
    applied: z.boolean(),
    tail_protocol: z.string().nullish(),
    strategy: z.string().optional(),
    directional: z.boolean().nullable().optional(),
    insert_ends_compatible: z.boolean().nullable().optional(),
    insert_end_compatibility_scope: z.literal("insert-end-sequence-geometry-only").optional(),
    ligation_product_recleavage: z.literal("not-modeled").optional(),
    directionality_evidence: z.string().optional(),
    digest_validation: z
      .object({
        methylation_sensitivity_status: z.string(),
        star_activity_status: z.string(),
        double_digest_compatibility_status: z.string(),
        heat_inactivation_status: z.string(),
        ligation_junction_recleavage_status: z.string(),
        enzyme_formulation_scope: z.string(),
        required_records: z.array(z.string()).default([]),
        note: z.string(),
      })
      .optional(),
    insert_end_geometry: z
      .object({
        forward: z.record(z.string(), z.unknown()),
        reverse: z.record(z.string(), z.unknown()),
      })
      .optional(),
    bench_controls: z.array(z.string()).default([]),
    protective_bases: z.number().optional(),
    forward_protective_bases: z.number().optional(),
    reverse_protective_bases: z.number().optional(),
    protective_sequence_authority: z.string().optional(),
    forward: z
      .object({
        enzyme: z.string(),
        site: z.string(),
        protective: z.string(),
        sequence: z.string(),
        length: z.number(),
        first_observed_activity_flanking_bases: z.number().nullish(),
        end_cleavage_evidence_identity: z.string().nullish(),
      })
      .nullish(),
    reverse: z
      .object({
        enzyme: z.string(),
        site: z.string(),
        protective: z.string(),
        sequence: z.string(),
        length: z.number(),
        first_observed_activity_flanking_bases: z.number().nullish(),
        end_cleavage_evidence_identity: z.string().nullish(),
      })
      .nullish(),
    /** Every enzyme absent from this insert, so a second choice needs no round trip. */
    usable_enzymes: z.array(z.string()).default([]),
    insert_boundary_contract: z
      .object({
        mode: z.literal("exact-submitted-insert"),
        product_size_bp: z.number(),
        terminal_primers_required: z.literal(true),
        donor_plasmid_region_extraction: z.string(),
        note: z.string(),
      })
      .optional(),
    recipient_vector: z
      .object({
        name: z.string(),
        length_bp: z.number(),
        sha256: z.string(),
        topology: z.literal("circular"),
        registry: z.object({ id: z.string(), version: z.string(), scope: z.string() }),
        sites: z.record(z.string(), z.array(z.number())),
        site_count_contract: z.literal("exactly-one-site-per-selected-enzyme"),
      })
      .optional(),
    note: z.string().default(""),
  })
  .nullish();
export type CloningTails = z.infer<typeof cloningTailsSchema>;

/**
 * One insert primer paired against a primer already in the vector.
 *
 * The arrangement that answers the question colony screening exists to ask.
 * Two primers inside the insert give the same band whichever way round it went
 * in; one in the backbone and one in the insert give a band only for the right
 * orientation. Absent unless a partner was chosen.
 */
export const backboneScreenSchema = z
  .object({
    partner: z
      .object({
        name: z.string(),
        sequence: z.string(),
        family: z.string().default(""),
        tm: z.number(),
        note: z.string().default(""),
      })
      .nullish(),
    primers: z
      .array(
        z.object({
          sequence: z.string(),
          length: z.number(),
          tm: z.number(),
          gc_percent: z.number(),
          orientation: z.string(),
          start: z.number(),
          /** How far the primer sits from where the insert meets the vector. */
          from_the_junction: z.number(),
          tm_gap: z.number(),
          cross_dimer_dg: z.number(),
          hairpin_dg: z.number(),
          self_dimer_dg: z.number(),
        }),
      )
      .default([]),
    orientation: z.string().default(""),
    /**
     * How long the band is, when the vector was given.
     *
     * `known: false` for every screen this build produced before the vector
     * could be pasted: the distance from the vector primer to the cloning site
     * belongs to a plasmid nothing here had seen, so the result could only
     * report the half it controlled. That is the one number somebody holds a
     * gel up against, so half of it is worse than none.
     */
    product: z
      .object({
        known: z.boolean(),
        vector_bases: z.number().optional(),
        sizes: z.array(z.object({ primer: z.string(), bases: z.number() })).default([]),
        note: z.string().default(""),
      })
      .nullish(),
    why_nothing: z.string().default(""),
  })
  .nullish();
export type BackboneScreen = z.infer<typeof backboneScreenSchema>;

/**
 * A 5' addition that belongs to a downstream step rather than to the template.
 *
 * `null` means none was asked for — which is not the same as an empty one
 * having been attached. Both temperatures are here because both are true and
 * they are about different rounds: the annealing half is what binds first, and
 * the whole molecule is what binds once the tail has a copy of itself to bind
 * to. Quoting the second where the first belongs is the mistake this exists to
 * prevent, and it is worth about ten degrees.
 */
export const fivePrimeTailSchema = z
  .object({
    role: z.string(),
    tail: z.string(),
    length: z.number(),
    annealing: z.string(),
    annealing_tm: z.number(),
    whole_tm: z.number(),
    note: z.string().default(""),
  })
  .nullish();
export type FivePrimeTail = z.infer<typeof fivePrimeTailSchema>;

/** Spread into the two results whose oligos go on to something else. */
const carriesTails = {
  tails: z.object({ forward: fivePrimeTailSchema, reverse: fivePrimeTailSchema }).nullish(),
};

/** One hold of the block. */
const cycleStepSchema = z.object({ celsius: z.number(), seconds: z.number() });

// The rendered steps are deliberately concise, while this parallel object is
// the complete resolved Cycling contract used by the worker. Keep it
// optional so saved results from before this field was persisted remain
// readable; every current worker result includes it.
const resolvedCyclingParametersSchema = z.object({
  denature_c: z.number(),
  denature_seconds: z.number(),
  initial_denature_seconds: z.number(),
  anneal_seconds: z.number(),
  extend_c: z.number(),
  extend_seconds_per_kb: z.number(),
  min_extend_seconds: z.number(),
  final_extend_seconds: z.number(),
  cycles: z.number(),
  two_step: z.boolean(),
  anneal_extend_c: z.number().nullable(),
  isothermal_c: z.number().nullable(),
  isothermal_seconds: z.number().nullable(),
  extend_seconds_max: z.number().nullable(),
});

/**
 * How to programme the block for one pair — or that there is no programme.
 *
 * Two shapes, because two things happen in a tube and only one of them is
 * cycling. RPA and LAMP hold at a single temperature and never denature: the
 * enzymes open the duplex themselves, which is why their primer rules are not
 * PCR annealing-temperature rules. Tm may still be retained as a broad software
 * guard, but it is not the performance criterion that a PCR annealing step is.
 * The worker has always represented the isothermal programme explicitly —
 * it returns `{ isothermal: true, hold, cycles: 0 }` and its own comment
 * explains that reporting a denaturation and forty cycles for such a reaction
 * "would be a protocol somebody follows and then wonders why their block was
 * busy for two hours".
 *
 * This schema only knew the cycled shape, and required `initial_denature`,
 * `denature` and `final_extend`. So an RPA design that the engine produced
 * correctly was refused here, and its page rendered nothing at all — measured
 * by parsing a real RPA response: three "expected object, received undefined".
 *
 * Discriminated on `isothermal` rather than made permissive, because a reader
 * has to be able to tell the two apart. Optional-everything would let a cycled
 * programme with a missing denaturation step through as valid.
 */
const cycledSchema = z.object({
  isothermal: z.literal(false).default(false),
  initial_denature: cycleStepSchema,
  denature: cycleStepSchema,
  /** Present in a three-step programme. */
  anneal: cycleStepSchema.optional(),
  extend: cycleStepSchema.optional(),
  /** Present instead, when the enzyme anneals and extends at one temperature. */
  anneal_extend: cycleStepSchema.optional(),
  final_extend: cycleStepSchema,
  extension_model: z
    .object({
      seconds_per_kb: z.number(),
      uncapped_seconds: z.number(),
      capped: z.boolean(),
    })
    .optional(),
  cycles: z.number(),
  two_step: z.boolean().default(false),
  resolved_parameters: resolvedCyclingParametersSchema.optional(),
  note: z.string(),
});

const isothermalSchema = z.object({
  isothermal: z.literal(true),
  /** The one temperature, and how long it is held for. */
  hold: cycleStepSchema,
  /** Zero, and meaningfully so: nothing is cycled. */
  cycles: z.literal(0).default(0),
  two_step: z.literal(false).default(false),
  resolved_parameters: resolvedCyclingParametersSchema.optional(),
  note: z.string(),
});

export const cyclingSchema = z.union([isothermalSchema, cycledSchema]);
export type Cycling = z.infer<typeof cyclingSchema>;
export type CycledProgramme = z.infer<typeof cycledSchema>;
export type IsothermalHold = z.infer<typeof isothermalSchema>;
export const variantVerdictSchema = z.object({
  count: z.number().optional(),
  /** Template positions counted from one. */
  at: z.array(z.number()).optional(),
  from_three_prime: z.array(z.number()).optional(),
  closest_to_three_prime: z.number().nullable().optional(),
  fatal: z.boolean(),
  overlaps: z.boolean().optional(),
  positions: z.array(z.number()).optional(),
  policy: z.string().optional(),
});
export type VariantVerdict = z.infer<typeof variantVerdictSchema>;

export const primerPairSchema = z.object({
  left: oligoSchema,
  right: oligoSchema,
  /** The product itself, so nobody has to reconstruct it by hand. */
  amplicon: z.string().default(""),
  left_at: z.object({ start: z.number(), length: z.number() }),
  right_at: z.object({ start: z.number(), length: z.number() }),
  /**
   * Whether the product spans the join of a circular template.
   *
   * When true the right primer's coordinate is *lower* than the left's, which
   * is true of the molecule and looks like a bug to anything that assumes
   * otherwise. Only a template said to be a circle can produce one.
   */
  crosses_the_join: z.boolean().default(false),
  product_size: z.number(),
  penalty: z.number(),
  tm_difference: z.number(),
  cross_dimer_dg: z.number(),
  score: z.number(),
  score_components: z.array(scoreComponentSchema),
  annealing_temperature: z.number().nullable(),
  /** Temperature used for the per-pair off-target duplex screen. */
  specificity_temperature_c: z.number().optional(),
  /** Temperature used for the pair-vs-pair dimer calculation. */
  cross_dimer_temperature_c: z.number().optional(),
  /** Scientific role of temperature-dependent thermodynamic diagnostics. */
  thermodynamic_temperature_role: z.string().optional(),
  /** Temperature used for the per-pair template accessibility fold. */
  accessibility_temperature_c: z.number().optional(),
  /** Predicted interactions after restriction tails are attached. */
  tailed: z
    .object({
      interaction: z.object({
        without_tails: z.object({ dg: z.number(), tm: z.number() }),
        with_tails: z.object({ dg: z.number(), tm: z.number() }),
        worsened_by: z.number(),
      }),
    })
    .optional(),
  accessibility: z.object({ left: z.number(), right: z.number() }).nullable(),
  /**
   * What the product between the primers will be like to amplify.
   *
   * `.loose()` and optional: engines that answer in shapes other than a pair
   * do not carry it, and a saved run from before it existed should still open.
   */
  amplicon_profile: z
    .object({
      length: z.number(),
      gc: z.number(),
      window: z.number(),
      worst_window_gc: z.number(),
      worst_window_at: z.number(),
      one_window_only: z.boolean(),
      difficulty: z.enum(["easy", "hard", "very hard"]),
      difficulty_scope: z.string().optional(),
      note: z.string(),
    })
    .loose()
    .optional(),
  /** Rolling-GC diagnostic across the final amplicon; reported, never a hard gate. */
  uniformity: z
    .object({
      window_bp: z.number(),
      min_window_gc: z.number(),
      max_window_gc: z.number(),
      note: z.string(),
    })
    .optional(),
  /** Heuristic 0–100 summary retained beside, not instead of, the ranking score. */
  quality: z
    .object({
      score: z.number(),
      parts: z.object({
        specificity: z.number().nullable(),
        dimer_margin: z.number().nullable(),
        accessibility: z.number().nullable(),
        end_stability: z.number().nullable(),
        tm_centeredness: z.number().nullable(),
      }),
    })
    .optional(),
  variants: z
    .object({
      left: variantVerdictSchema,
      right: variantVerdictSchema,
    })
    .nullable()
    .default(null),
  off_targets: offTargetsSchema,
});
export type PrimerPair = z.infer<typeof primerPairSchema>;

/** What the resolver understood, shown back before anything is trusted. */
export const targetSummarySchema = z.object({
  name: z.string(),
  length: z.number(),
  raw_length: z.number(),
  gc_percent: z.number(),
  soft_masked: z.boolean(),
  rna_input: z.boolean().default(false),
  ambiguous_count: z.number(),
  ambiguous_at: z.array(z.number()),
  notes: z.array(z.object({ kind: z.string(), message: z.string() })),
});

/** Primer3's account of one stage of the search. */
export const considerationSchema = z.object({
  stage: z.string(),
  considered: z.number(),
  accepted: z.number(),
  sentence: z.string(),
  rejections: z.array(
    z.object({
      reason: z.string(),
      count: z.number(),
      share: z.number(),
      advice: z.string(),
    }),
  ),
});

/** One step of the run, and what it did to what passed through it. */
export const stageSchema = z.object({
  key: z.string(),
  title: z.string(),
  /** A filter removes things; a scorer marks them and removes nothing. */
  kind: z.enum(["filter", "scorer"]),
  ran: z.boolean(),
  unit: z.string(),
  went_in: z.number().nullable(),
  came_out: z.number().nullable(),
  dropped: z.number().nullable(),
  flagged: z.number().nullable(),
  detail: z.string(),
  rejections: z.array(
    z.object({
      reason: z.string(),
      count: z.number(),
      share: z.number(),
      advice: z.string(),
    }),
  ),
});
export type Stage = z.infer<typeof stageSchema>;

/* ── Pieces every engine's result carries ─────────────────────────────── */

/** What produced these numbers, so a result can be repeated a year later. */
export const provenanceSchema = z
  .object({
    worker: z.string(),
    primer3_py: z.string(),
    python: z.string(),
    platform: z.string(),
    note: z.string(),
    runtime_contract_version: z.string().optional(),
    parameter_map_version: z.string().optional(),
    input_schema_version: z.string().optional(),
    output_schema_version: z.string().optional(),
    toolchain_manifest: z
      .record(
        z.string(),
        z.object({ configured_version: z.string(), execution_scope: z.string() }).loose(),
      )
      .optional(),
    model: z.object({ name: z.string() }).loose(),
    tool_versions: z.record(z.string(), z.string().nullable()).optional(),
    methods: z.record(z.string(), z.record(z.string(), z.unknown())).optional(),
    scientific_authorities: z.array(scientificAuthorityIdentitySchema).optional(),
    method_fidelity: z.array(methodFidelityRowSchema).optional(),
    method_fidelity_references: z.array(methodFidelityRowSchema).optional(),
    method_fidelity_scope: z.string().optional(),
    method_fidelity_registry: methodFidelityRegistrySchema.optional(),
  })
  .loose();
export type Provenance = z.infer<typeof provenanceSchema>;

/** Which assay ran, and where its own numbers were not the ones used. */
export const assaySchema = z.object({
  id: z.string(),
  name: z.string(),
  engine: z.string().optional(),
  goal: z.string().optional(),
  status: z.string().optional(),
  profile_authority: z
    .object({
      source: z.string(),
      profileId: z.string(),
      transport: z.string(),
    })
    .optional(),
  defaults: z.record(z.string(), z.union([z.number(), z.string()])).default({}),
  chemistry_family: z.string().default(""),
  /** Capability modifiers that were active for this resolved run. */
  modifiers: z.array(z.string()).default([]),
  /** Inputs required for the assay claim, checked before design. */
  requires: z.array(z.string()).default([]),
  /** Enzyme capabilities required by the assay profile. */
  enzyme: z.array(z.string()).default([]),
  purposes: z.array(z.string()).default([]),
  overruled: z
    .array(
      z.object({
        field: z.string(),
        assay_wanted: z.union([z.number(), z.string()]),
        used: z.union([z.number(), z.string()]),
        because: z.string(),
      }),
    )
    .default([]),
  parameter_resolution: z.record(z.string(), z.unknown()).optional(),
});
export type Assay = z.infer<typeof assaySchema>;

/** Shared generation-1 execution contract carried by every design engine. */
export const runtimeContractSchema = z
  .object({
    contract_version: z.string(),
    parameter_map_version: z.string(),
    input_schema_version: z.string(),
    output_schema_version: z.string(),
    module_id: z.string(),
    engine_id: z.string(),
    coordinate_contract: z
      .object({
        version: z.string(),
        basis: z.number(),
        interval: z.string(),
        notation: z.string(),
        oligo_sequence_orientation: z.string(),
        strand_field_required: z.boolean(),
        single_base_position: z.string(),
        junction_position: z.string(),
      })
      .loose(),
    pipeline_stages: z.array(z.string()).default([]),
    parameter_precedence: z.array(z.string()),
    override_policy: z.record(z.string(), z.string()),
    bindings: z.array(
      z
        .object({
          tool_id: z.string(),
          role: z.enum(["PRIMARY", "VALIDATOR", "FALLBACK", "OPTIONAL", "REFERENCE"]),
          operations: z.array(z.string()),
        })
        .loose(),
    ),
    resolved_parameters: z
      .object({
        reaction: z.record(z.string(), z.unknown()).default({}),
        constraints: z.record(z.string(), z.unknown()).default({}),
      })
      .loose()
      .optional(),
  })
  .loose();
export type RuntimeContract = z.infer<typeof runtimeContractSchema>;

/** Assay-level obligations resolved on top of an engine contract. */
export const moduleContractSchema = z
  .object({
    module_id: z.string().optional(),
    engine: z.string(),
    command: z.string(),
    gates: z.array(z.string()).default([]),
    required_context: z.array(z.string()).optional(),
    conditional_required_context: z
      .array(
        z.object({
          when: z.record(z.string(), z.string()),
          required_context: z.array(z.string()),
        }),
      )
      .optional(),
    fallback: z.string(),
  })
  .loose();
export type ModuleContract = z.infer<typeof moduleContractSchema>;

const toolEvidenceSchema = z
  .object({
    tool_id: z.string(),
    configured_version: z.string(),
    status: z.string(),
    purpose: z.string(),
    decision_impact: z.string().optional(),
    interpretation_contract: z.string().optional(),
    interpretation_complete: z.boolean().optional(),
    evidence: z.record(z.string(), z.unknown()).default({}),
    tool_run: z.record(z.string(), z.unknown()).nullable().optional(),
    warnings: z.array(z.string()).default([]),
  })
  .loose();

export const toolchainValidationSchema = z
  .object({
    contract_version: z.string(),
    mode: z.enum(["off", "auto", "strict"]),
    status: z.string(),
    selected_oligos: z.number(),
    molecule_contract: z
      .object({
        specificity: z.literal("annealing_sequence"),
        interaction: z.literal("ordered_sequence"),
        tail_position: z.literal("5-prime-only"),
      })
      .optional(),
    checks: z.array(toolEvidenceSchema).default([]),
    warnings: z.array(z.string()).default([]),
    interpretation_complete: z.boolean().optional(),
    uninterpreted_required_tools: z.array(z.string()).default([]).optional(),
    selection_policy: z.record(z.string(), z.string()).optional(),
  })
  .loose();
export type ToolchainValidation = z.infer<typeof toolchainValidationSchema>;

export const verificationSchema = z
  .object({
    status: z.string(),
    computational_design_complete: z.boolean(),
    external_evidence_complete: z.boolean(),
    wet_lab_validated: z.boolean(),
    selected_oligos: z.number().optional(),
    note: z.string(),
  })
  .loose();

const runtimeValidationPlanSchema = z
  .object({
    status: z.literal("in-silico-only"),
    scope: z.string().optional(),
    required: z.array(z.string()).default([]),
    items: z
      .array(
        z.object({
          key: z.string(),
          label: z.string(),
          kind: z.enum(["control", "measurement", "decision"]),
          phase: z.enum([
            "design-review",
            "assay-design",
            "pre-run",
            "bench-run",
            "post-run",
            "analysis",
            "assay-validation",
          ]),
          source: z.string(),
          why: z.string(),
          unit: z.string().nullable().optional(),
          required: z.boolean(),
          computable: z.boolean(),
        }),
      )
      .default([]),
    not_computed: z.array(z.string()).default([]),
  })
  .loose();

const scientificIntegritySchema = z
  .object({
    policy_version: z.string(),
    mode: z.enum(["strict", "development"]),
    fail_closed: z.boolean(),
    invariants: z.array(z.string()).default([]),
  })
  .loose();

const carriesRuntime = {
  runtime_contract: runtimeContractSchema.optional(),
  module_contract: moduleContractSchema.optional(),
  toolchain_validation: toolchainValidationSchema.optional(),
  verification: verificationSchema.optional(),
  validation: runtimeValidationPlanSchema.optional(),
  scientific_integrity: scientificIntegritySchema.optional(),
};

/** The conditions every quoted temperature was computed under. */
export const reactionSchema = z.object({
  polymerase: z.string(),
  polymerase_name: z.string(),
  summary: z.string().optional(),
  context_role: z.string().optional(),
  context_note: z.string().optional(),
  mv_conc: z.number(),
  dv_conc: z.number(),
  dntp_conc: z.number(),
  dna_conc: z.number(),
  /** Universal/degenerate pools use this to state what the effective concentration parameter means. */
  dna_conc_role: z.string().optional(),
  chemistry: z
    .object({
      strand_displacing: z.boolean(),
      five_prime_exonuclease: z.boolean(),
      proofreading: z.boolean(),
      thermostable: z.boolean(),
      rpa_compatible: z.boolean(),
    })
    .loose()
    .optional(),
  model: z
    .object({
      name: z.string(),
      salt_correction: z.string(),
      role: z.enum(["design-and-report", "screening-proxy"]).optional(),
      interpretation: z.string().optional(),
      bound_fraction_supported: z.boolean().optional(),
      oligo_concentration_parameter: z.string().optional(),
      oligo_concentration_role: z.string().optional(),
      oligo_concentration_note: z.string().optional(),
    })
    .loose(),
});
export type Reaction = z.infer<typeof reactionSchema>;

/**
 * Reverse-transcription provenance when the tube starts from RNA.
 *
 * `before` records placement because RT-PCR/RT-dPCR usually perform a named RT
 * step before PCR cycling, whereas a true one-pot RT-RPA chemistry can perform
 * RT concurrently with isothermal amplification. `hold` is null whenever no
 * named RT chemistry supplies a release protocol. `one_step: null` likewise
 * means Scientific-Strict did not infer one-step versus two-step operation
 * from the generic RNA modifier.
 */
export const reverseTranscriptionSchema = z
  .object({
    /** null means one-step versus two-step was not inferred without a named RT chemistry. */
    one_step: z.boolean().nullable().default(null),
    hold: z.object({ celsius: z.number(), seconds: z.number() }).nullish(),
    before: z.string().nullish(),
    note: z.string().default(""),
    authority_status: z.string().optional(),
  })
  .nullish();
export type ReverseTranscription = z.infer<typeof reverseTranscriptionSchema>;

/** Spread into the five result shapes an RNA tube can reach. */
const carriesRt = { reverse_transcription: reverseTranscriptionSchema };

/** Transcript geometry applied by the flanking-pair pipeline, when requested. */
export const transcriptSchema = z.object({
  exon_junctions: z.array(z.number()),
  junction_spanning_required: z.boolean(),
  coordinate_system: z.literal("zero-based-boundary-between-bases"),
  note: z.string(),
});
export type TranscriptAudit = z.infer<typeof transcriptSchema>;

/**
 * The target-side half of species-specific PCR specificity.
 *
 * It is separate from `background`: exclusion asks what must stay silent,
 * while inclusivity asks whether the pair still works across the intended
 * target panel. `template_only` keeps a representative-template check from
 * being mistaken for strain-wide coverage.
 */
export const inclusivitySchema = z
  .object({
    checked: z.boolean(),
    supplied: z.boolean(),
    template_only: z.boolean(),
    bases: z.number(),
    contigs: z.number(),
    pairs_checked: z.number(),
    pairs_rejected: z.number(),
    panel_sha256: z.string().length(64).nullable().optional(),
    ambiguous_bases: z.number().int().nonnegative().optional(),
    panel_hash_scope: z.string().optional(),
    panel_identity_claim: z.literal("content-identity-only-not-taxonomic-completeness").optional(),
    panel_provenance: z.string().optional(),
    panel_selection_rationale: z.string().optional(),
    taxonomy_resolution_status: z.literal("not-resolved-from-fasta-labels").optional(),
    biological_traceability_status: z
      .enum([
        "not-validated-from-fasta-alone",
        "user-declared-provenance-recorded-not-independently-validated",
      ])
      .optional(),
    diversity_coverage_status: z.literal("not-computed-from-panel-hash").optional(),
    population_frequency_status: z.literal("not-computed").optional(),
    surveillance_status: z.literal("external-versioned-review-required").optional(),
    binding_ambiguity_policy: z.literal("fail-closed-at-primer-sites").optional(),
    sequence_topology_assumption: z.string().optional(),
    topology_note: z.string().optional(),
    note: z.string(),
  })
  .loose();
export type InclusivityAudit = z.infer<typeof inclusivitySchema>;

/** One line of an order form. */
export const orderLineSchema = z.object({
  name: z.string(),
  sequence: z.string(),
  /** Template-binding segment used for specificity/annealing calculations. */
  annealing_sequence: z.string().optional(),
  /** Non-template 5-prime extension present in the ordered molecule. */
  tail_sequence: z.string().optional(),
  kind: z.enum(["primer", "probe"]).optional(),
  length: z.number(),
  gc_percent: z.number(),
  tm: z.number(),
});
export type OrderLine = z.infer<typeof orderLineSchema>;

export const orderabilitySchema = z.object({
  orderable: z.boolean(),
  status: z.string(),
  note: z.string(),
});
export type Orderability = z.infer<typeof orderabilitySchema>;

/** The resolved inputs and routing decisions for one flanking-pair run. */
export const requestAuditSchema = z
  .object({
    coordinates: z
      .object({
        system: z.string(),
        target_start: z.number().nullable(),
        target_length: z.number().nullable(),
      })
      .loose(),
    circular: z.boolean(),
    rna: z.object({ requested: z.boolean().nullable(), effective: z.boolean() }).loose(),
    transcript: z
      .object({
        exon_junctions: z.array(z.number()),
        junction_spanning_required: z.boolean(),
        coordinate_system: z.literal("zero-based-boundary-between-bases"),
      })
      .loose(),
    polymerase: z
      .object({
        requested: z.string().nullable(),
        effective: z.string(),
        condition_overrides: z.record(z.string(), z.number()),
      })
      .loose(),
    purpose: z.object({ requested: z.string().nullable(), effective: z.string() }).loose(),
    constraint_overrides: z.record(z.string(), z.union([z.number(), z.string()])),
    excluded_regions: z.number(),
    known_variants: z.number(),
    background_supplied: z.boolean(),
    inclusivity_supplied: z.boolean().optional(),
    inclusivity_records: z.number().optional(),
    specificity: z
      .object({
        method: z.string(),
        method_version: z.number(),
        max_mismatches: z.number(),
        terminal_mismatch_reported: z.boolean(),
      })
      .loose(),
    search: z
      .object({
        how_many: z.number(),
        shortlist: z.number(),
        pool: z.number().nullable(),
        primer3_returned: z.number(),
        primer3_examined: z.number(),
      })
      .loose(),
  })
  .loose();
export type RequestAudit = z.infer<typeof requestAuditSchema>;

/** One evidence item still required beyond sequence-only design. */
export const validationItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  kind: z.enum(["control", "measurement", "decision"]),
  phase: z.enum([
    "design-review",
    "assay-design",
    "pre-run",
    "bench-run",
    "post-run",
    "analysis",
    "assay-validation",
  ]),
  source: z.string(),
  why: z.string(),
  unit: z.string().nullable(),
  required: z.boolean(),
  computable: z.boolean(),
});
export type ValidationItem = z.infer<typeof validationItemSchema>;

/** A named flanking-pair protocol remains separate from primer geometry. */
const flankingStandardPcrProtocolSchema = z
  .object({
    kind: z.literal("standard-pcr"),
    protocol_id: z.string().optional(),
    selection: z.string(),
    source_publication: z.string().optional(),
    source_revision: z.string().optional(),
    source_revision_date: z.string().nullable().optional(),
    source_revision_date_precision: z.string().nullable().optional(),
    reaction_volume_uL: z.union([z.number(), z.record(z.string(), z.number())]).optional(),
    primer_final_concentration_uM: z.record(z.string(), z.number()).optional(),
    magnesium_final_mM: z.number().optional(),
    dntp_each_mM: z.number().optional(),
    cycling_model: z.record(z.string(), z.unknown()).optional(),
    polymerase_properties: z.record(z.string(), z.unknown()).optional(),
    difficult_template: z.record(z.string(), z.unknown()).optional(),
    carryover_prevention: z.record(z.string(), z.unknown()).optional(),
    downstream_cloning: z.record(z.string(), z.unknown()).optional(),
    sequence_decision_impact: z.literal("none"),
    thermodynamic_model_impact: z.literal("none"),
    screening_context_note: z.string(),
    constraints: z.record(z.string(), z.number()).optional(),
    note: z.string(),
  })
  .loose();

const flankingQpcrProtocolSchema = z
  .object({
    kind: z.literal("qpcr-sybr"),
    protocol_id: z.string().optional(),
    selection: z.string(),
    source_publication: z.string().optional(),
    source_revision: z.string().optional(),
    source_revision_date: z.string().nullable().optional(),
    source_revision_date_precision: z.string().optional(),
    master_mix: z.string(),
    reaction_volume_uL: z.union([z.number(), z.record(z.string(), z.number())]).optional(),
    primer_final_concentration_nM: z
      .object({
        starting: z.number().optional(),
        optimization_min: z.number().optional(),
        optimization_max: z.number().optional(),
      })
      .loose()
      .optional(),
    amplicon_bp_preferred: z.object({ min: z.number(), max: z.number() }),
    primer_tm_c: z.object({ target: z.number() }),
    cycles: z.object({ min: z.number(), max: z.number() }),
    anneal_extend_c: z.number(),
    reverse_transcription: z
      .object({
        mode: z.literal("one-step-rt-qpcr"),
        authority_status: z.string(),
        temperature_c: z.number(),
        incubation_minutes: z.number(),
        minimum_recommended_temperature_c: z.number().optional(),
        difficult_target_temperature_c: z.number().optional(),
        reverse_transcriptase: z.string(),
        rnase_inhibitor: z.string().optional(),
        note: z.string(),
      })
      .optional(),
    carryover_prevention: z
      .object({
        dUTP_in_master_mix: z.boolean(),
        UDG_built_in: z.boolean(),
        optional_UDG: z.string().optional(),
        optional_udg_pretreatment: z
          .object({ temperature_c: z.number(), minutes: z.number() })
          .optional(),
      })
      .loose()
      .optional(),
    transcript_design: z
      .object({
        splice_site_spanning_recommended_when_known: z.boolean(),
        purpose: z.string(),
        hard_requirement_for_every_transcript: z.literal(false).optional(),
      })
      .optional(),
    genomic_dna_control: z
      .object({
        no_rt_control_recommended: z.boolean(),
        no_template_control_recommended: z.boolean(),
        dnase_treatment_if_genomic_dna_is_detected: z.boolean(),
        exon_exon_junction_design_recommended_when_annotated_and_appropriate: z.boolean(),
        note: z.string(),
      })
      .optional(),
    readout: z.string(),
    readout_profile: z.string().nullable().optional(),
    sequence_decision_impact: z.literal("none").optional(),
    note: z.string(),
  })
  .loose();

const flankingRpaProtocolSchema = z
  .object({
    kind: z.literal("rpa"),
    protocol_id: z.string().optional(),
    selection: z.string(),
    source_publication: z.string().optional(),
    source_revision: z.string().optional(),
    source_revision_date: z.string().nullable().optional(),
    source_revision_date_precision: z.string().nullable().optional(),
    format: z.string().optional(),
    reaction_volume_uL: z.number().optional(),
    primer_length_nt: z.object({
      rapid_preferred_min: z.number(),
      rapid_preferred_max: z.number(),
      reviewed_upper_nt: z.number(),
      below_preferred_note: z.string(),
    }),
    amplicon_bp: z.object({
      preferred_rapid_min: z.number(),
      preferred_rapid_max: z.number(),
      supported_context_max: z.number(),
    }),
    constraints: z.record(z.string(), z.number()).optional(),
    amplicon_gc_percent: z
      .object({ min: z.number(), max: z.number(), status: z.string() })
      .optional(),
    temperature_c: z.number(),
    temperature_range_c: z.object({ min: z.number(), max: z.number() }).optional(),
    incubation_minutes: z.number(),
    incubation_range_minutes: z
      .object({ min: z.number(), max: z.number(), context: z.string().optional() })
      .optional(),
    agitation: z.object({ after_minutes: z.number(), action: z.string() }).optional(),
    mixing: z.object({ optional_rpm: z.number(), effect: z.string() }).optional(),
    primer_final_concentration_nM: z.number(),
    magnesium_acetate_mM: z.number().optional(),
    magnesium_chloride_mM: z.number().optional(),
    dntp_total_mM: z.number().optional(),
    dntp_each_mM: z.number().optional(),
    supports_dna: z.boolean().optional(),
    supports_rna: z.boolean().optional(),
    reverse_transcription: z
      .object({
        mode: z.literal("one-pot-rt-rpa"),
        authority_status: z.string(),
        isothermal: z.literal(true),
        temperature_c: z.number(),
        incubation_minutes: z.number(),
        reverse_transcriptase: z.string(),
        reverse_transcriptase_final_U_per_uL: z.number(),
        rnase_inhibitor: z.string(),
        rnase_inhibitor_final_U_per_uL: z.number(),
        rnase_h: z.string(),
        rnase_h_final_U_per_uL: z.number(),
        note: z.string(),
      })
      .optional(),
    contamination_control: z
      .object({
        carryover_risk: z.string(),
        environment_and_carryover_false_positive_recognized: z.boolean(),
        ntc_prepared_before_positive_samples: z.boolean().optional(),
        filtered_tips: z.boolean().optional(),
        separate_endpoint_workspace_when_opening_tubes: z.boolean().optional(),
        separate_pre_post_amplification_areas: z.boolean().optional(),
        post_amplification_opening_high_risk: z.boolean().optional(),
        high_copy_material_near_setup_avoid: z.boolean().optional(),
        bleach_decontamination_guidance: z.string().optional(),
        closed_tube_readout_preferred_when_available: z.string(),
        note: z.string(),
      })
      .optional(),
    production_dna_warning: z
      .object({
        status: z.literal("unconditional-named-kit-warning"),
        contaminant: z.string(),
        production_strain: z.string(),
        supplier_boundary: z.string(),
        organism_inferred_from_sequence: z.literal(false),
        action: z.string(),
      })
      .optional(),
    readout: z.string(),
    oligo_contract: z.literal("plain-acgt-two-primer").optional(),
    modified_probe_support: z.literal(false).optional(),
    modified_probe_branch_status: z.string().optional(),
    readout_contract: z.literal("endpoint-product-detection-modality-not-inferred").optional(),
    sequence_decision_impact: z.enum(["none", "constraint-envelope"]).optional(),
    thermodynamic_model_impact: z.literal("none").optional(),
    note: z.string(),
  })
  .loose();

const flankingLongRangeProtocolSchema = z
  .object({
    kind: z.literal("long-range-pcr"),
    protocol_id: z.string().optional(),
    selection: z.string(),
    kit_ids: z.array(z.string()),
    manual: z.string(),
    source_publication: z.string(),
    source_revision: z.string(),
    source_revision_date: z.string().nullable().optional(),
    source_revision_date_precision: z.string().optional(),
    lifecycle: z
      .object({
        status: z.enum(["current", "discontinued"]),
        discontinued_date: z.string().optional(),
        replacement_part: z.string().optional(),
        replacement_name: z.string().optional(),
        replacement_is_informational_only: z.boolean().optional(),
        silent_substitution_allowed: z.boolean().optional(),
      })
      .loose(),
    reaction_volume_uL: z.union([z.number(), z.record(z.string(), z.number())]),
    primer_final_concentration_uM: z.record(z.string(), z.number()),
    magnesium_chloride_mM: z.number().nullable().optional(),
    dntp_each_mM: z.number().optional(),
    enzyme_units: z.record(z.string(), z.number()).optional(),
    cycling_summary: z.string().optional(),
    cycling_model: z.record(z.string(), z.unknown()).optional(),
    screening_thermodynamics: z.string().optional(),
    thermodynamic_model_impact: z.literal("none").optional(),
    sequence_decision_impact: z.enum(["none", "constraint-envelope"]).optional(),
    constraints: z.record(z.string(), z.number()).optional(),
    note: z.string(),
  })
  .loose();

const flankingDigitalProtocolSchema = z
  .object({
    kind: z.literal("digital-pcr"),
    protocol_id: z.string().optional(),
    selection: z.string(),
    source_publication: z.string().optional(),
    source_revision: z.string().optional(),
    source_revision_date: z.string().optional(),
    source_revision_date_precision: z.string().optional(),
    supermix: z.string(),
    reaction_volume_uL: z.union([z.number(), z.record(z.string(), z.number())]),
    droplets_target: z.number().optional(),
    partition_model: z.string().optional(),
    primer_final_concentration_nM: z.record(z.string(), z.number()).optional(),
    primer_final_concentration_uM: z.number().optional(),
    primer_concentration_status: z.string().optional(),
    supports_dna: z.boolean().optional(),
    supports_rna: z.boolean().optional(),
    constraints: z.record(z.string(), z.number()).optional(),
    amplicon_bp_preferred: z.object({ min: z.number(), max: z.number() }).optional(),
    buffer_b_final_percent: z
      .object({
        start: z.number(),
        typical_min: z.number(),
        typical_max: z.number(),
        maximum: z.number(),
      })
      .optional(),
    evagreen_final_x: z.number().optional(),
    template_dna_ng: z.record(z.string(), z.number()).optional(),
    fragmentation_guidance: z.record(z.string(), z.unknown()).optional(),
    cycling_summary: z.string().optional(),
    cycling: z.record(z.string(), z.unknown()).optional(),
    reverse_transcription: z
      .object({
        mode: z.literal("one-step-rt-dpcr"),
        authority_status: z.string(),
        temperature_c: z.number(),
        incubation_minutes: z.number(),
        before: z.string().optional(),
        note: z.string(),
      })
      .optional(),
    q_solution: z
      .object({
        strongly_recommended: z.boolean(),
        especially_useful_for: z.array(z.string()),
        not_a_sequence_validity_rule: z.boolean(),
      })
      .optional(),
    stabilization: z.array(z.object({ temperature_c: z.number(), minutes: z.number() })).optional(),
    readout: z.string(),
    quantitation: z.string(),
    sequence_decision_impact: z.enum(["none", "constraint-envelope"]).optional(),
    thermodynamic_model_impact: z.literal("none").optional(),
    note: z.string(),
  })
  .loose();

const flankingProtocolSchema = z.union([
  flankingStandardPcrProtocolSchema,
  flankingQpcrProtocolSchema,
  flankingRpaProtocolSchema,
  flankingLongRangeProtocolSchema,
  flankingDigitalProtocolSchema,
]);

export const colonyContextSchema = z.object({
  host_class: z.enum(["bacterial", "yeast", "filamentous-fungus", "microalgae", "other"]),
  preparation: z.enum([
    "direct-transfer",
    "liquid-culture",
    "water-lysate",
    "buffer-lysate",
    "host-specific-lysis",
    "other",
  ]),
  protocol_id: z.string().optional(),
  protocol_name: z.string(),
  protocol_provenance: z.string(),
  source_url: z.string().nullable().optional(),
  interpretation_status: z.literal("in-silico-screen-design"),
  lysis_timing_inferred: z.literal(false),
  sample_amount_inferred: z.literal(false),
  source_recovery_status: z.string(),
  cycling_authority: z.string(),
  required_observations: z.array(z.string()).default([]),
  note: z.string(),
});
export type ColonyContext = z.infer<typeof colonyContextSchema>;

/** Resolved downstream objective and every search/constraint bias it contributed. */
export const designPurposeSchema = z.object({
  id: z.string(),
  name: z.string(),
  summary: z.string(),
  constraints: z.record(z.string(), z.number()).default({}),
  ranking_weights: z.record(z.string(), z.number()).default({}),
  overridden: z.array(z.string()).default([]),
});
export type DesignPurpose = z.infer<typeof designPurposeSchema>;

const workflowEvidenceObservedSchema = z.object({
  recorded: z.boolean().optional(),
  decision_impact: z.literal("none"),
  observed: z.record(z.string(), z.unknown()),
  note: z.string().optional(),
});

const workflowEvidenceLegacyFieldsSchema = z.object({
  recorded: z.boolean().optional(),
  decision_impact: z.literal("none"),
  fields: z.record(z.string(), z.unknown()),
  note: z.string().optional(),
});

/**
 * Canonical evidence result, with a non-destructive legacy read migration.
 * Stored historical JSON is never rewritten; parsing only exposes one shape to UI code.
 */
const workflowEvidenceResultSchema = z
  .union([workflowEvidenceObservedSchema, workflowEvidenceLegacyFieldsSchema])
  .transform((value) =>
    "observed" in value
      ? value
      : {
          recorded: value.recorded,
          decision_impact: value.decision_impact,
          observed: value.fields,
          note: value.note,
        },
  )
  .nullable()
  .optional();

export const designResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("flanking-pair"),
  workflow_evidence: workflowEvidenceResultSchema,
  /** Only restriction cloning asks for these; absent everywhere else. */
  cloning: cloningTailsSchema,
  /** Only colony screening asks for this; absent everywhere else. */
  backbone: backboneScreenSchema,
  /** Pre-analytical colony provenance; does not imply a physically verified screen. */
  colony_context: colonyContextSchema.optional(),
  /** Pinned specificity-panel authority; records reproducibility, not population completeness. */
  species_panel_snapshot: z
    .object({
      target_taxid: z.number().int().positive(),
      taxonomy_snapshot: z.string(),
      database_snapshot: z.string(),
      accession_manifest_sha256: z.string(),
      accession_manifest_count: z.number().int().positive().optional(),
      record_metadata_manifest_sha256: z.string(),
      record_metadata_summary: z.object({
        record_count: z.number().int().positive(),
        topology_counts: z.record(z.string(), z.number()),
        group_counts: z.record(z.string(), z.number()),
        population_weighting_status: z.string(),
        normalized_inclusivity_weights: z.record(z.string(), z.number()),
        fragment_record_count: z.number().int().nonnegative(),
        claim_boundary: z.string(),
      }),
      retrieved_date: z.string(),
      taxonomy_resolution_status: z.string(),
      panel_completeness_status: z.string(),
      surveillance_status: z.string(),
      revalidation_policy: speciesRevalidationPolicySchema,
      sequence_decision_impact: z.string(),
    })
    .optional(),
  /** Deterministic RPA empirical-screening short-list; never changes primary in-silico ranking. */
  rpa_screening_cohort: z
    .object({
      status: z.string(),
      decision_impact: z.string(),
      selection_method: z.string(),
      minimum_coordinate_distance: z.number(),
      recommended_characterisation_count: z.number().int().nonnegative(),
      pairs: z.array(
        z.object({
          candidate: z.number().int().nonnegative(),
          primary_rank: z.number().int().positive(),
          score: z.number(),
          left_start: z.number().int().nonnegative(),
          right_start: z.number().int().nonnegative(),
          amplicon_length: z.number().int().positive().nullable(),
        }),
      ),
      full_empirical_assay_development: rpaFullEmpiricalAssayDevelopmentSchema,
      claim_boundary: z.string(),
    })
    .optional(),
  rpa_multiplex_panel: rpaMultiplexPanelResultSchema.nullable().optional(),
  /** Coding/fusion intent checked against the exact final insert; does not alter primer ranking. */
  cloning_coding_context: z
    .object({
      intent: z.enum(["noncoding", "preserve-orf", "in-frame-fusion"]),
      cds_start: z.number().int().nonnegative().optional(),
      cds_end: z.number().int().positive().optional(),
      cds_length_bp: z.number().int().positive().optional(),
      terminal_codon: z.string().nullable().optional(),
      terminal_stop_present: z.boolean().optional(),
      stop_codon_policy: z.enum(["not-applicable", "preserve", "remove"]),
      vector_junction_frame: z.number().int().min(0).max(2).nullable().optional(),
      phase_status: z.string().optional(),
      fusion_tag: z.string().nullable().optional(),
      linker_aa: z.string().nullable().optional(),
      coding_validation_status: z.string(),
      sequence_decision_impact: z.string(),
      claim_boundary: z.string(),
    })
    .optional(),
  /** Source-conditioned bench workflow for exact-insert restriction cloning. */
  restriction_workflow: z
    .object({
      schema_version: z.string(),
      decision_impact: z.string(),
      digest: z
        .object({
          id: z.string(),
          name: z.string(),
          vendor: z.string().nullable(),
          source_url: z.string().nullable(),
          values: z.record(z.string(), z.unknown()),
          ranges: z.record(z.string(), z.unknown()),
          unresolved: z.array(z.string()),
        })
        .loose(),
      dephosphorylation: z
        .object({
          id: z.string(),
          name: z.string(),
          vendor: z.string().nullable(),
          source_url: z.string().nullable(),
          values: z.record(z.string(), z.unknown()),
          ranges: z.record(z.string(), z.unknown()),
          unresolved: z.array(z.string()),
        })
        .loose(),
      ligation: z
        .object({
          id: z.string(),
          name: z.string(),
          vendor: z.string().nullable(),
          source_url: z.string().nullable(),
          values: z.record(z.string(), z.unknown()),
          ranges: z.record(z.string(), z.unknown()),
          unresolved: z.array(z.string()),
        })
        .loose(),
      controls: z.object({ required_measured_controls: z.array(z.string()), note: z.string() }),
    })
    .optional(),
  /** Platform/run handoff for digital PCR; never a sequence-derived concentration claim. */
  digital_context: z
    .object({
      platform_id: z.string().optional(),
      platform_name: z.string(),
      instrument_model: z.string().nullable().optional(),
      platform_route: z
        .enum(["dye-flanking", "pair-probe", "custom-validated"])
        .nullable()
        .optional(),
      protocol_id: z.string().nullable().optional(),
      consumable_id: z.string().nullable().optional(),
      multiplex: digitalMultiplexContextSchema.nullable().optional(),
      partition_format: z.enum(["droplet", "chip", "chamber", "other"]),
      fragmentation_state: z.enum(["not-assessed", "not-required", "planned", "performed"]),
      run_status: z.enum(["design-handoff", "multiplex-planning-evidence-handoff"]),
      threshold_status: z.literal("measured-run-required"),
      quantification_status: z.literal("not-computed-from-design"),
      partition_volume_authority_status: z.string(),
      analysis_software_version_status: z.string(),
      volume_precision_factor_status: z.string(),
      current_platform_authority_reference: digitalPlatformAuthorityReferenceSchema
        .nullable()
        .optional(),
      required_run_evidence: z.array(z.string()).default([]),
      note: z.string(),
    })
    .strict()
    .optional(),
  modified_oligos: modifiedOligosProvenanceSchema.optional(),
  ...carriesRt,
  transcript: transcriptSchema.optional(),
  inclusivity: inclusivitySchema.optional(),
  provenance: provenanceSchema.optional(),
  /** Every oligo in this order against every other one. */
  interactions: z
    .object({
      checked: z.number(),
      threshold: z.number(),
      found: z.number(),
      note: z.string(),
      worst: z.array(
        z.object({
          a: z.string(),
          b: z.string(),
          dg: z.number(),
          tm: z.number(),
          same_pair: z.boolean(),
        }),
      ),
    })
    .optional(),
  /** Which assay ran, and where its own numbers were not the ones used. */
  assay: assaySchema.optional(),
  /** Present only when a named Standard-PCR, qPCR/SYBR, RPA, long-range, or digital-PCR overlay was selected. */
  protocol: flankingProtocolSchema.optional(),
  /** Source-conditioned numeric bench recipe. It is provenance-only and never changes sequence ranking. */
  flanking_numeric_recipe: z
    .object({
      schema_version: z.string(),
      module: z.string(),
      protocol: z.string(),
      values: z.record(z.string(), z.number()),
      origins: z.record(z.string(), z.string()),
      ranges: z.record(z.string(), z.tuple([z.number(), z.number()])),
      applied_overlays: z.array(z.string()),
      unresolved_numeric_dependencies: z.array(
        z.object({ id: z.string(), note: z.string() }).loose(),
      ),
      warnings: z.array(z.string()).default([]),
      dependency_axes: z.array(z.string()).default([]),
      sequence_decision_impact: z.literal("none"),
    })
    .optional(),
  /** Follow-up validation required beyond sequence-only design. */
  validation: z
    .object({
      status: z.literal("in-silico-only"),
      scope: z.string().optional(),
      required: z.array(z.string()),
      items: z.array(validationItemSchema).default([]),
      not_computed: z.array(z.string()).default([]),
    })
    .loose()
    .optional(),
  stages: z.array(stageSchema).default([]),
  target: targetSummarySchema,
  request: requestAuditSchema.optional(),
  /** Historical saved results may predate this explicit purpose ledger. */
  purpose: designPurposeSchema.optional(),
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  pairs: z.array(primerPairSchema),
  considered: z.array(considerationSchema),
  why_nothing: z.string(),
  accessibility: z
    .object({
      checked: z.boolean(),
      model: z.string(),
      note: z.string(),
    })
    .loose(),
  /**
   * What masking did to this run: a property of the run, not of a pair.
   *
   * `.loose()` like `accessibility` above, so a field the worker adds does not
   * have to be added here before it can be read.
   */
  variants: z
    .object({
      checked: z.boolean(),
      /** Current worker summary fields. */
      supplied: z.number().optional(),
      coordinates: z.array(z.number()).optional(),
      considered: z.number().optional(),
      rejected: z.number().optional(),
      policy: z.string().nullable().optional(),
      /** Legacy fields retained so historical saved runs remain readable. */
      given: z.number().optional(),
      at: z.array(z.number()).optional(),
      critical_bases: z.number().optional(),
      note: z.string().optional(),
    })
    .loose()
    .optional(),
  ...carriesScan,
  order_sheet: z.array(orderLineSchema),
});
export type DesignResult = z.infer<typeof designResultSchema>;

/** Every named reaction any assay in this build offers. */
export const catalogueSchema = z.object({
  polymerases: z
    .array(z.object({ id: z.string(), name: z.string(), summary: z.string() }))
    .default([]),
});
export type Catalogue = z.infer<typeof catalogueSchema>;

/** The named reactions a module offers, defined once in the worker. */
export const presetsSchema = z.object({
  /**
   * What this assay differs by, from the route addressed by assay.
   *
   * The endpoint used to answer by engine, so all eight modules on
   * flanking-pair received the same numbers — and long-range PCR showed
   * "shortest product 200" while running at 5000. Absent when the core is an
   * older build than this interface.
   */
  assay: z
    .object({
      id: z.string(),
      name: z.string(),
      polymerase: z.string().nullish(),
      allowedPolymerases: z.array(z.string()).default([]),
      /** The purpose a new project starts with when the assay has one. */
      defaultPurpose: z.string().nullish(),
      constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()).default({}),
      cycling: z.record(z.string(), z.unknown()).default({}),
      requires: z.array(z.string()).default([]),
      /**
       * What this assay needs of an enzyme, and why.
       *
       * Present so a shortened list is a statement rather than an absence.
       * Somebody who came here knowing which enzyme they use needs to be told
       * it is not offered and told the reason — not left to wonder whether the
       * list is short because the catalogue is small.
       *
       * Empty means every enzyme, which is the honest default: narrowing is a
       * claim about that assay's chemistry, and a claim nobody has researched
       * should not be put in front of a bench.
       */
      enzyme: z.array(z.object({ need: z.string(), why: z.string() })).default([]),
    })
    .optional(),
  polymerases: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        summary: z.string(),
        reaction: z.object({
          mv_conc: z.number(),
          dv_conc: z.number(),
          dntp_conc: z.number(),
          dna_conc: z.number(),
        }),
        thermodynamics: z
          .object({
            oligo_concentration_parameter: z.string().optional(),
            oligo_concentration_role: z.string().optional(),
            oligo_concentration_note: z.string().optional(),
          })
          .loose()
          .optional(),
      }),
    )
    .default([]),
  purposes: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        summary: z.string(),
        constraints: z.record(z.string(), z.number()),
      }),
    )
    .default([]),
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()).default({}),
  /**
   * The settings this engine takes, worded, in declaration order. Rendered as
   * given: the two engines do not take the same fields, and a form that
   * hard-codes one engine's list silently drops the other's.
   */
  fields: z
    .array(
      z.object({
        name: z.string(),
        label: z.string(),
        hint: z.string(),
        // A null default means this setting is intentionally derived or has
        // no sensible universal starting value; it is not a malformed preset.
        default: z.union([z.number(), z.string()]).nullish(),
      }),
    )
    .default([]),
});
export type Presets = z.infer<typeof presetsSchema>;

/* ── Getting a sequence in ─────────────────────────────────────────────── */

/** One record as NCBI returned it. */
export const fetchedRecordSchema = z.object({
  id: z.string(),
  description: z.string(),
  length: z.number(),
  sequence: z.string(),
});
export type FetchedRecord = z.infer<typeof fetchedRecordSchema>;

export const fetchAnswerSchema = z.object({
  records: z.array(fetchedRecordSchema),
  /** The same records as text, ready to paste anywhere else. */
  fasta: z.string(),
});
export type FetchAnswer = z.infer<typeof fetchAnswerSchema>;

/** Whether this build can reach NCBI at all. */
export const fetchAvailabilitySchema = z.object({
  available: z.boolean(),
  reason: z.string(),
});

/** What an alignment produced, and which program produced it. */
export const alignedSchema = z.object({
  tool: z.string(),
  tool_version: z.string(),
  depth: z.number(),
  width: z.number(),
  records: z.array(z.object({ id: z.string(), sequence: z.string() })),
  fasta: z.string(),
});
export type Aligned = z.infer<typeof alignedSchema>;

/** Which aligners this build can use. */
export const alignersSchema = z.object({
  available: z.boolean(),
  aligners: z.array(z.object({ id: z.string(), name: z.string(), path: z.string() })).default([]),
  reason: z.string(),
});

/** Several aligned sequences collapsed into one, and what that hid. */
export const consensusSchema = z.object({
  sequence: z.string(),
  length: z.number(),
  from_count: z.number(),
  varied: z.number(),
  gapped: z.number(),
  identity: z.number(),
  notes: z.array(z.string()),
});
export type ConsensusResult = z.infer<typeof consensusSchema>;

/* ── What a consensus-pair run produces ───────────────────────────────── */

/** One degenerate primer, which is a mixture rather than an oligo. */
export const degenerateSiteSchema = z.object({
  sequence: z.string(),
  start: z.number(),
  end: z.number(),
  length: z.number(),
  orientation: z.string(),
  degeneracy: z.number(),
  tm_min: z.number(),
  tm_max: z.number(),
  tm_spread: z.number(),
  gc_min: z.number(),
  gc_max: z.number(),
  covers: z.number(),
  hairpin_dg: z.number(),
  /** Added after the first saved Universal results; absence is historical. */
  tm_member_dna_conc_nM: z.number().optional(),
});
export type DegenerateSite = z.infer<typeof degenerateSiteSchema>;

export const universalPairSchema = z.object({
  left: degenerateSiteSchema,
  right: degenerateSiteSchema,
  product_size: z.number(),
  covers: z.number(),
  of: z.number(),
  degeneracy: z.number(),
  cross_dimer_dg: z.number(),
  score: z.number(),
  score_components: z.array(scoreComponentSchema),
  /** Current workers emit null; numeric values are accepted only to render historical saved results without reclassifying them as current bench authority. */
  annealing_temperature: z.number().nullable(),
  annealing_temperature_role: z.string().optional(),
  coverage_score: z.number().optional(),
  coverage_basis: z.string().optional(),
  coverage_evidence: z.record(z.string(), z.unknown()).optional(),
  formulation: z.record(z.string(), z.unknown()).optional(),
  nontarget_evidence: z.record(z.string(), z.unknown()).optional(),
  alignment_sensitivity: z.record(z.string(), z.unknown()).optional(),
  split_pool_alternative: z.record(z.string(), z.unknown()).optional(),
  amplicon_informativeness: z.record(z.string(), z.unknown()).optional(),
});
export type UniversalPair = z.infer<typeof universalPairSchema>;

export const universalResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("consensus-pair"),
  assay: assaySchema.optional(),
  provenance: provenanceSchema.optional(),
  constraints: z.record(z.string(), z.union([z.number(), z.string(), z.boolean()])).optional(),
  ...carriesTails,
  ...carriesRt,
  alignment_pipeline: z
    .object({
      mode: z.enum(["auto", "prealigned"]),
      tool: z.string(),
      tool_version: z.string(),
      tool_role: z.string(),
      warnings: z.array(z.string()),
      depth: z.number(),
      width: z.number(),
      input_record_count: z.number(),
      decision: z.string(),
    })
    .optional(),
  alignment: z.object({
    sequences: z.number(),
    columns: z.number(),
    names: z.array(z.string()),
    gapped_columns: z.number(),
    conserved_columns: z.number(),
    consensus_policy: z.string().optional(),
    weighted: z.boolean().optional(),
    strata: z.array(z.string()).optional(),
  }),
  panel: z.record(z.string(), z.unknown()).optional(),
  nontarget_panel: z.record(z.string(), z.unknown()).nullable().optional(),
  alignment_audit: z.record(z.string(), z.unknown()).nullable().optional(),
  pairs: z.array(universalPairSchema),
  windows: z.object({
    considered: z.number(),
    accepted: z.number(),
    /** Optional for Universal results saved before the spread reference was recorded. */
    above_tm_spread_reference: z.number().optional(),
    tm_spread_reference_c: z.number().optional(),
    rejections: z.array(
      z.object({
        reason: z.string(),
        count: z.number(),
        share: z.number(),
        advice: z.string(),
      }),
    ),
    by_orientation: z
      .object({
        forward: z.object({
          considered: z.number(),
          accepted: z.number(),
          rejections: z.array(
            z.object({
              reason: z.string(),
              count: z.number(),
              share: z.number(),
              advice: z.string(),
            }),
          ),
        }),
        reverse: z.object({
          considered: z.number(),
          accepted: z.number(),
          rejections: z.array(
            z.object({
              reason: z.string(),
              count: z.number(),
              share: z.number(),
              advice: z.string(),
            }),
          ),
        }),
      })
      .optional(),
  }),
  pair_counts: z.record(z.string(), z.number()),
  capped: z.object({
    sites: z.boolean(),
    pairs: z.boolean().default(false),
    site_limit: z.number(),
    measured_limit: z.number(),
    search_complete: z.boolean().default(true),
    note: z.string(),
  }),
  reaction: z.object({ polymerase: z.string(), polymerase_name: z.string() }).loose(),
  /** Historical Universal results may not carry the later effective-pool ledger. */
  degenerate_thermodynamics: z
    .object({
      member_concentration_model: z.literal("nominal-equal-member-effective-concentration"),
      pool_effective_dna_conc_nM: z.number(),
      formula: z.string(),
      authority: z.literal("explicit-screening-assumption-not-measured-formulation"),
      note: z.string(),
    })
    .optional(),
  workflow_evidence: workflowEvidenceResultSchema,
  /** Raw worker order ledger. The UI still renders degenerate pools from pair extrema rather than pretending they have one scalar Tm. */
  order_sheet: z.array(orderLineSchema.extend({ note: z.string().optional() })).default([]),
});
export type UniversalResult = z.infer<typeof universalResultSchema>;

/**
 * Whatever a run produced.
 *
 * Discriminated on the engine that produced it rather than sniffed from its
 * shape: two engines answer different questions, and a view chosen by guessing
 * is a view that renders the wrong thing the day a third one arrives.
 */

/* ── What a nested run produces ───────────────────────────────────────── */

/** One round of a nested design. */
export const nestedRoundSchema = z.object({
  left: oligoSchema,
  right: oligoSchema,
  left_at: z.object({ start: z.number(), length: z.number() }),
  right_at: z.object({ start: z.number(), length: z.number() }),
  product_size: z.number(),
  tm_difference: z.number(),
  cross_dimer_dg: z.number(),
  penalty: z.number(),
});
export type NestedRound = z.infer<typeof nestedRoundSchema>;

export const nestSchema = z.object({
  outer: nestedRoundSchema,
  inner: nestedRoundSchema,
  shares: z.string(),
  /** How far the second round moved in at each end. */
  moved_in: z.object({ left: z.number(), right: z.number() }),
  /** Two-tube fully nested Tm relationship; informational, not a universal hard gate. */
  tm_note: z.string().optional(),
  /**
   * Where else these oligos sit, keyed by the two executable rounds.
   * Generation-1 is two-tube only: first-round and second-round specificity
   * evidence remains separate because transfer provenance and backgrounds differ.
   */
  off_targets: z.record(z.string(), offTargetsSchema).optional(),
  nested_false_product_graph: z.record(z.string(), z.unknown()).optional(),
});
export type Nest = z.infer<typeof nestSchema>;

export const nestedProtocolSchema = z.object({
  /** Explicit strategy selection; absence is never interpreted as dUTP/UNG. */
  selection: z.enum(["not-selected", "dutp-ung-strategy-only", "dUTP-UNG"]),
  execution_status: z.enum(["not-selected", "strategy-only"]).optional(),
  note: z.string(),
});
export type NestedProtocol = z.infer<typeof nestedProtocolSchema>;

export const nestedResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("nested"),
  ...carriesScan,
  ...carriesRt,
  provenance: provenanceSchema,
  assay: assaySchema,
  target: targetSummarySchema,
  reaction: reactionSchema,
  constraints: z.object({
    outer: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
    inner: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  }),
  nesting: z.object({
    shares: z.string(),
    margin: z.number(),
    single_tube: z.literal(false),
    /** Diagnostic difference only; two-tube rounds may use independent annealing steps. */
    tm_separation: z.number(),
    note: z.string(),
  }),
  nests: z.array(nestSchema).default([]),
  outer_considered: z.number(),
  /** Outer pairs that held no inner pair, and why each of them did not. */
  rejected: z
    .array(
      z.object({
        outer_at: z.array(z.number()),
        outer_product: z.number(),
        reason: z.string(),
        detail: z.string(),
      }),
    )
    .default([]),
  protocol: nestedProtocolSchema.optional(),
  round_reactions: z
    .record(
      z.string(),
      z.object({
        conditions: z.record(z.string(), z.number()),
        polymerase_identity: z.string(),
        thermal_program: z.array(z.record(z.string(), z.unknown())).default([]),
        claim_boundary: z.string(),
      }),
    )
    .optional(),
  transfer: z.record(z.string(), z.unknown()).optional(),
  contamination_evidence_contract: z.record(z.string(), z.unknown()).optional(),
  workflow_evidence: workflowEvidenceResultSchema,
  why_nothing: z.string().default(""),
  order_sheet: z.array(orderLineSchema).default([]),
});
export type NestedResult = z.infer<typeof nestedResultSchema>;

/* ── What an outward-pair run produces ────────────────────────────────── */

export const outwardPairSchema = z.object({
  /** Specificity evidence for the current worker result; absence is never interpreted as clean. */
  off_targets: offTargetsSchema,
  left: oligoSchema,
  right: oligoSchema,
  left_at: z.object({ start: z.number(), length: z.number() }),
  right_at: z.object({ start: z.number(), length: z.number() }),
  reads: z.string(),
  left_reads_into: z.string(),
  right_reads_into: z.string(),
  walks_into: z.string(),
  /** The distance between the primers through sequence you already have. */
  known_span: z.number(),
  /** Null until the circle's length is known. It is not the known span. */
  product_size: z.number().nullable(),
  product_note: z.string(),
  unknown_interval: z.object({
    status: z.string(),
    minimum: z.number().nullable(),
    maximum: z.number().nullable(),
    exact: z.number().nullable(),
  }),
  product_path: z.array(z.record(z.string(), z.unknown())),
  tm_difference: z.number(),
  cross_dimer_dg: z.number(),
  penalty: z.number(),
});
export type OutwardPair = z.infer<typeof outwardPairSchema>;

export const outwardResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("outward-pair"),
  ...carriesScan,
  provenance: provenanceSchema,
  assay: assaySchema,
  target: targetSummarySchema,
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  constraint_semantics: z.record(z.string(), z.string()),
  experiment_contract: z.object({
    branch: z.enum(["restriction-self-ligation", "supplied-circular-template"]),
    left_end_phosphate: z.enum([
      "phosphorylated",
      "unphosphorylated",
      "unresolved",
      "not-applicable",
    ]),
    right_end_phosphate: z.enum([
      "phosphorylated",
      "unphosphorylated",
      "unresolved",
      "not-applicable",
    ]),
    circularization_provenance: z.string(),
    linear_control_provenance: z.string(),
    methylation_branch: z.string(),
    mapping_use_case: z.string().optional(),
    authority: z.record(z.string(), z.unknown()).optional(),
    result_status: z.enum(["predicted", "amplified", "sequence-confirmed", "unresolved"]),
    status_semantics: z.string(),
  }),
  enzymes: z.array(
    z.object({
      enzyme: z.string(),
      site: z.string(),
      cuts_inside: z.array(z.number()),
      usable: z.boolean(),
      why: z.string(),
      expected_fragment: z
        .object({
          cuts: z.number(),
          median: z.number(),
          mean: z.number(),
          mean_at_a_random_base: z.number(),
          note: z.string(),
        })
        .nullable(),
    }),
  ),
  /** Standard Gen-1 inverse-PCR topology: the named enzyme does not cut the known anchor. */
  digest: z.object({
    branch_identity: z.string(),
    enzyme: z.string().nullable(),
    known_sites: z.array(z.number()),
    known_length: z.number(),
    circle_length: z.number().nullable(),
    note: z.string(),
  }),
  /** The self-ligated restriction fragment and the combined unknown flanks it contributes. */
  circle: z.object({
    known_length: z.number(),
    circle_length: z.number().nullable(),
    unknown_interval: z.object({
      status: z.string(),
      minimum: z.number().nullable(),
      maximum: z.number().nullable(),
      exact: z.number().nullable(),
    }),
  }),
  enzyme_cohort: z
    .object({
      requested: z.number(),
      returned: z.number(),
      decision_impact: z.string(),
      note: z.string(),
    })
    .optional(),
  sequencing_handoff: z.record(z.string(), z.unknown()).optional(),
  ...outwardClosureResultShape,
  workflow_evidence: workflowEvidenceResultSchema,
  pairs: z.array(outwardPairSchema),
  considered: z.array(considerationSchema),
  why_nothing: z.string(),
  order_sheet: z.array(orderLineSchema),
});
export type OutwardResult = z.infer<typeof outwardResultSchema>;

/* ── What a pair-and-probe run produces ───────────────────────────────── */

/** The third oligo, and the two things about it that are not about pairs. */
export const probeSchema = oligoSchema.extend({
  at: z.number(),
  /** How far it sits from the forward primer. Never zero: it would compete. */
  after_left: z.number(),
  /** How far above the warmer primer it melts, which is the mechanism. */
  above_primers: z.number(),
  first_base: z.string(),
  note: z.string().default(""),
});
export type Probe = z.infer<typeof probeSchema>;

export const probeAssaySchema = z.object({
  /** Specificity evidence for the current worker result; absence is never interpreted as clean. */
  off_targets: offTargetsSchema,
  left: oligoSchema,
  right: oligoSchema,
  probe: probeSchema,
  product_size: z.number(),
  specificity_layers: z.record(z.string(), z.unknown()).optional(),
  measured_in: z.object({ note: z.string().default("") }).optional(),
});
export type ProbeAssay = z.infer<typeof probeAssaySchema>;

export const probeResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("pair-and-probe"),
  ...carriesScan,
  ...carriesRt,
  provenance: provenanceSchema.optional(),
  modified_oligos: modifiedOligosProvenanceSchema.optional(),
  assay: assaySchema.optional(),
  target: targetSummarySchema,
  reaction: reactionSchema,
  /** Named probe authority; historical records remain parseable through a loose superset. */
  protocol: z
    .object({
      selection: z.string(),
      chemistry: z.string().optional(),
      probe_chemistry: z.string().optional(),
      execution_status: z.string().optional(),
      source_identity: z.string().optional(),
      source_url: z.string().optional(),
      source_reviewed_date: z.string().optional(),
      tm_model: z.string().optional(),
      application_scope: z.string().optional(),
      source_revision: z.string().nullable().optional(),
      probe_length_nt: z.object({ min: z.number(), max: z.number() }).optional(),
      primer_final_concentration_nM: z.number().optional(),
      probe_final_concentration_nM: z.number().optional(),
      reporter_options: z.array(z.string()).optional(),
      quencher: z.string().optional(),
      amplicon_bp: z.object({ min: z.number(), max: z.number() }).optional(),
      source_documents: z
        .array(
          z
            .object({
              identity: z.string(),
              publication: z.string().optional(),
              revision: z.string().optional(),
              revision_date: z.string().optional(),
              supports: z.array(z.string()),
            })
            .loose(),
        )
        .optional(),
      primer_constraints: z.record(z.string(), z.number()).optional(),
      probe_constraints: z.record(z.string(), z.number()).optional(),
    })
    .loose()
    .optional(),
  /** Two windows rather than one: the probe's is not the primers' rescaled. */
  constraints: z.object({
    primers: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
    probe: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  }),
  independent_probe_structure: z
    .object({
      checked: z.boolean(),
      model: z.string().nullable().optional(),
      celsius: z.number().nullable().optional(),
      note: z.string().default(""),
      decision_impact: z.string().default("advisory-independent-structure-evidence"),
      folds: z
        .record(
          z.string(),
          z
            .object({
              length: z.number(),
              dg: z.number().nullable().optional(),
              duplex_dg: z.number().nullable().optional(),
              fraction: z.number().nullable().optional(),
              structure: z.string().nullable().optional(),
            })
            .loose(),
        )
        .default({}),
    })
    .optional(),
  optical_configuration: z.record(z.string(), z.unknown()).nullable().optional(),
  transcript_mode: transcriptModeSchema,
  multiplex_panel: z.record(z.string(), z.unknown()).nullable().optional(),
  ...probeClosureResultShape,
  workflow_evidence: workflowEvidenceResultSchema,
  assays: z.array(probeAssaySchema).default([]),
  considered: z.string().default(""),
  why_nothing: z.string().default(""),
  /** Unbound/development probe geometry is diagnostic only and must never expose supplier actions. */
  orderability: orderabilitySchema.optional(),
  /* A probe carries a note the other lines do not: ordered as a plain oligo it
     is a plain oligo, and it will report nothing. */
  order_sheet: z.array(orderLineSchema.extend({ note: z.string().optional() })).default([]),
});
export type ProbeResult = z.infer<typeof probeResultSchema>;

/* ── What a single-primer run produces ────────────────────────────────── */

export const singlePrimerSchema = oligoSchema.extend({
  /** Specificity evidence for the current worker result; absence is never interpreted as clean. */
  off_targets: offTargetsSchema,
  at: z.number(),
  direction: z.string(),
  penalty: z.number(),
  /** How far the target is from this primer's 3' end (Sanger only). */
  reaches: z.number().optional(),
  /**
   * Whether reaching the target meant going round the join of a circle.
   *
   * A primer that sits *after* the coordinate it reads into looks like a bug
   * until you know the template is a circle and the read comes round the
   * origin to arrive. Reading a target near base zero of a plasmid was not
   * possible before: the string has nothing in front of it, the molecule has
   * the whole rest of itself.
   */
  wrapped_to_reach: z.boolean().default(false),
  /**
   * RACE-only diagnostic cross-dimer evidence against the exact selected
   * kit/custom amplification partner. This is a review flag, never a validity
   * or ranking gate.
   */
  adapter_dimer: z
    .object({
      partner: z.string(),
      partner_sequence: z.string(),
      dg: z.number(),
      tm: z.number(),
      watch_threshold_dg: z.number(),
      flagged: z.boolean(),
      decision_role: z.literal("diagnostic-watch-only-not-validity-or-ranking"),
      temperature_role: z.string(),
      note: z.string(),
    })
    .optional(),
  /** How much readable trace is left after the target ends (Sanger only). */
  spare: z.number().optional(),
  window: z
    .object({
      nearest: z.number(),
      furthest: z.number(),
      searched: z.array(z.number()).default([]),
      widened: z.number().default(0),
    })
    .optional(),
  note: z.string().default(""),
});
export type SinglePrimerCandidate = z.infer<typeof singlePrimerSchema>;

/** Present only when the sequencing module selected a named wet-lab overlay. */
const sequencingProtocolSchema = z.object({
  selection: z.string(),
  kit_id: z.string(),
  reaction_volumes_uL: z.array(z.number()),
  primer_input_pmol: z.number(),
  source_publication: z.string(),
  source_revision: z.string(),
  source_revision_date: z.string(),
  supplier_table_ambiguity: z.string(),
  cycling: z.object({
    cycles: z.number(),
    denature: z.object({ temperature_c: z.number(), seconds: z.number() }),
    anneal: z.object({ temperature_c: z.number(), seconds: z.number() }),
    extend: z.object({ temperature_c: z.number(), seconds: z.number() }),
    initial_denature: z.object({ temperature_c: z.number(), seconds: z.number() }),
    ramp_rate_c_per_s: z.number(),
    hold_temperature_c: z.number(),
  }),
  template_input: z.object({
    pcr_product_ng_by_length: z.record(z.string(), z.string()),
    single_stranded_dna_ng: z.string(),
    double_stranded_dna_ng: z.string(),
  }),
  cleanup_options: z.array(z.string()),
  readout: z.string(),
  note: z.string(),
});

export const singleResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("single-primer"),
  ...carriesScan,
  provenance: provenanceSchema.optional(),
  assay: assaySchema.optional(),
  target: targetSummarySchema,
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  /** Sanger capillary placement envelope; absent for RACE. */
  read: z
    .object({
      direction: z.string(),
      dead_zone: z.number(),
      read_length: z.number(),
      nearest: z.number(),
      furthest: z.number(),
      region: z.array(z.number()).default([]),
      note: z.string().default(""),
    })
    .optional(),
  /** RACE-specific placement: a GSP search region in known sequence, not a Sanger read window. */
  race_placement: z
    .object({
      direction: z.string(),
      race_direction: z.enum(["5prime", "3prime"]),
      search_region: z.array(z.number()).length(2),
      semantics: z.literal("known-sequence-gsp-search-region"),
      note: z.string(),
    })
    .optional(),
  primers: z.array(singlePrimerSchema).default([]),
  ...singleClosureResultShape,
  workflow_evidence: workflowEvidenceResultSchema,
  sequencing_design_profile: z.record(z.string(), z.unknown()).nullable().optional(),
  sequencing_submission: z.record(z.string(), z.unknown()).nullable().optional(),
  universal_primer_scan: z.record(z.string(), z.unknown()).nullable().optional(),
  bidirectional_plan: z.record(z.string(), z.unknown()).optional(),
  race_chemistry: z.record(z.string(), z.unknown()).optional(),
  protocol: sequencingProtocolSchema.optional(),
  /** Present only when a named/custom RACE partner was selected. */
  race_adapter: raceAdapterSchema.optional(),
  /** Present only for a RACE run with an explicit transcript end. */
  race_direction: z.enum(["5prime", "3prime"]).optional(),
  /** RACE provenance and the explicit boundary between candidate and validated transcript end. */
  race_context: raceContextSchema.optional(),
  /** Capillary-instrument handoff; trace/basecalling remain external evidence. */
  sequencing_context: z
    .object({
      instrument: z.enum([
        "unresolved",
        "seqstudio",
        "seqstudio-flex",
        "3500",
        "3500xl",
        "3730",
        "3730xl",
        "other",
      ]),
      instrument_name: z.string().nullable(),
      facility_sop: z.string().nullable(),
      trace_status: z.enum(["not-reviewed", "reviewed-abif"]),
      basecalling_status: z.literal("external-run-required"),
      quality_status: z.enum(["unresolved-until-trace", "observed-trace-evidence"]),
      required_run_evidence: z.array(z.string()).default([]),
      note: z.string(),
    })
    .optional(),
  considered: z.string().default(""),
  why_nothing: z.string().default(""),
  order_sheet: z.array(orderLineSchema).default([]),
});
export type SingleResult = z.infer<typeof singleResultSchema>;

/* ── What a mutagenic-pair run produces ───────────────────────────────── */

export const mutagenicPairSchema = z.object({
  forward: oligoSchema.extend({
    at: z.number(),
    carries: z.string().default(""),
    /** Added when ordered-vs-annealing molecule semantics were made explicit. */
    annealing_sequence: z.string().optional(),
    tail_sequence: z.string().default(""),
  }),
  reverse: oligoSchema.extend({
    at: z.number(),
    /** Added when ordered-vs-annealing molecule semantics were made explicit. */
    annealing_sequence: z.string().optional(),
    tail_sequence: z.string().default(""),
  }),
  /** Screening thermodynamics are kept separate from Q5/NEBaseChanger protocol authority. */
  melting: z.object({
    on_template: z.number(),
    on_product: z.number(),
    reverse: z.number(),
    gap: z.number(),
    /** Historical mutagenesis captures may not identify the thermodynamic authority. */
    authority: z.string().optional(),
    note: z.string().default(""),
  }),
  centrality_error_nt: z.number().nullable().optional(),
  cross_dimer_dg: z.number(),
  edit: z.object({ kind: z.string(), at: z.number(), describes: z.string() }),
});
export type MutagenicPair = z.infer<typeof mutagenicPairSchema>;

export const mutagenicResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("mutagenic-pair"),
  provenance: provenanceSchema.optional(),
  assay: assaySchema.optional(),
  target: targetSummarySchema,
  reaction: reactionSchema.optional(),
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()).optional(),
  mutagenesis_topology: z.string().optional(),
  edit: z
    .object({
      kind: z.string(),
      at: z.number(),
      to: z.string().default(""),
      replacing: z.number().default(0),
      describes: z.string().optional(),
      was: z.string().default(""),
      becomes: z.string().default(""),
      product_length: z.number().optional(),
    })
    .optional(),
  edits: z.array(z.record(z.string(), z.unknown())).optional(),
  amino_acid_evidence: z.record(z.string(), z.unknown()).nullable().optional(),
  construct: z.record(z.string(), z.unknown()).optional(),
  library_design: z.record(z.string(), z.unknown()).optional(),
  design: z.record(z.string(), z.unknown()).optional(),
  template_methylation_status: z.string().optional(),
  pairs: z.array(mutagenicPairSchema).default([]),
  protocol: z
    .object({
      selection: z.string(),
      source_identity: z.string().optional(),
      source_url: z.string().optional(),
      topology: z.string().optional(),
    })
    .loose()
    .optional(),
  validation_contract: z.record(z.string(), z.unknown()).optional(),
  workflow_evidence: workflowEvidenceResultSchema,
  why_nothing: z.string().default(""),
  orderability: orderabilitySchema.optional(),
  order_sheet: z
    .array(
      z
        .object({
          name: z.string(),
          sequence: z.string(),
          annealing_sequence: z.string().optional(),
          tail_sequence: z.string().optional(),
          kind: z.string().optional(),
          length: z.number(),
          gc_percent: z.number().optional(),
          tm: z.number().optional(),
          tm_formula_c: z.number().optional(),
          note: z.string().optional(),
        })
        .loose(),
    )
    .default([]),
});
export type MutagenicResult = z.infer<typeof mutagenicResultSchema>;

/* ── What a tiling-scheme run produces ────────────────────────────────── */

export const tileSchema = z.object({
  index: z.number(),
  /** Stable PrimalScheme3 amplicon/stem identity. Optional only for internal/historical results. */
  name: z.string().optional(),
  /** Which tube. Neighbours are never in the same one. */
  pool: z.number(),
  start: z.number(),
  end: z.number(),
  size: z.number(),
  /**
   * Whether this amplicon spans the join between the last base and the first.
   *
   * Said rather than left to be inferred from an `end` past the last base,
   * which reads as a bug to anybody who did not know the sequence was a
   * circle. Default `false` so a scheme saved before circles existed is
   * described correctly rather than ambiguously.
   */
  crosses_the_join: z.boolean().default(false),
  left: z.string(),
  right: z.string(),
  /** BED-like primer intervals emitted for scheme interchange. */
  left_start: z.number().optional(),
  left_end: z.number().optional(),
  right_start: z.number().optional(),
  right_end: z.number().optional(),
});
export type Tile = z.infer<typeof tileSchema>;

export const tilingResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("tiling-scheme"),
  provenance: provenanceSchema.optional(),
  assay: assaySchema.optional(),
  target: targetSummarySchema,
  /** Scheme-level metadata for reproducible downstream primer handling. */
  reference_id: z.string().default("unnamed-reference"),
  coordinate_system: z.string().default("0-based, half-open"),
  scheme_format: z.string().default("pcrstudio-tiling-v1"),
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  tiles: z.array(tileSchema).default([]),
  pools: z.record(z.string(), z.array(z.number())).default({}),
  /** Stretches nothing could be placed over. Reported, never silently skipped. */
  gaps: z
    .array(
      z.object({
        from: z.number(),
        to: z.number(),
        bases: z.number(),
        why: z.string().default(""),
      }),
    )
    .default([]),
  variant_risk: z
    .object({
      status: z.string(),
      semantics: z.string().optional(),
      alignment_depth: z.number(),
      terminal_window_nt: z.number().optional(),
      primers_with_any_non_exact_observation: z.number().optional(),
      primers_with_definite_mismatch_or_gap: z.number().optional(),
      max_definite_nonmatch_fraction: z.number().optional(),
      max_terminal_5nt_non_exact_fraction: z.number().optional(),
      interpretation: z.string().optional(),
      primers: z
        .array(
          z.object({
            name: z.string(),
            role: z.string(),
            strand: z.string(),
            start: z.number(),
            end: z.number(),
            alignment_depth: z.number(),
            exact_match_sequences: z.number(),
            ambiguity_compatible_sequences: z.number(),
            definite_nonmatch_sequences: z.number(),
            gap_sequences: z.number(),
            terminal_5nt_non_exact_sequences: z.number(),
            exact_match_fraction: z.number(),
            definite_nonmatch_fraction: z.number(),
            terminal_5nt_non_exact_fraction: z.number(),
            examples: z.array(z.record(z.string(), z.unknown())).default([]),
          }),
        )
        .default([]),
    })
    .optional(),
  coverage: z.object({
    /** Covered bases inside the declared coverage scope. */
    bases: z.number(),
    /** Denominator inside the declared coverage scope, not necessarily the full reference. */
    of: z.number(),
    percent: z.number(),
    scope: z.string().default("whole-reference"),
    /** Full-reference coordinate domain used by the scheme map. */
    reference_bases: z.number().optional(),
    reference_covered_bases: z.number().optional(),
    /** Merged zero-based half-open panel regions when scope=requested-regions. */
    requested_regions: z
      .array(z.object({ start: z.number(), end: z.number(), bases: z.number() }))
      .optional(),
  }),
  lifecycle: z
    .object({
      operation: z.string(),
      alignment: z.record(z.string(), z.unknown()).default({}),
      tool_runs: z.array(z.record(z.string(), z.unknown())).default([]),
      interaction_evidence: z.record(z.string(), z.unknown()).nullable().optional(),
      input_artifacts: z.record(z.string(), z.record(z.string(), z.unknown())).default({}),
    })
    .optional(),
  scheme_artifacts: z
    .record(
      z.string(),
      z.object({
        kind: z.string(),
        name: z.string(),
        sha256: z.string(),
        content: z.string(),
      }),
    )
    .optional(),
  output_license: tilingOutputLicenseSchema.nullable().optional(),
  primary_backend: z.record(z.string(), z.unknown()).optional(),
  olivar: z.record(z.string(), z.unknown()).optional(),
  backend_comparison: z.record(z.string(), z.unknown()).optional(),
  ...tilingClosureResultShape,
  workflow_evidence: workflowEvidenceResultSchema,
  interactions: z
    .array(
      z.object({
        pool: z.number(),
        oligos: z.number(),
        worst: z.array(z.object({ a: z.string(), b: z.string(), badness: z.number() })).default([]),
      }),
    )
    .default([]),
  how_it_was_laid_out: z.array(z.string()).default([]),
  note: z.string().default(""),
  why_nothing: z.string().default(""),
  orderability: orderabilitySchema.optional(),
  order_sheet: z.array(orderLineSchema.extend({ pool: z.number().optional() })).default([]),
});
export type TilingResult = z.infer<typeof tilingResultSchema>;

/* ── What a junction-primers run produces ─────────────────────────────── */

/** One ordered oligo: a tail that joins, and a portion that anneals. */
export const tailedPrimerSchema = z.object({
  name: z.string(),
  fragment: z.string(),
  direction: z.string(),
  sequence: z.string(),
  length: z.number(),
  /** Annealing-core thermodynamic screening; not by itself a PCR block-temperature authority. */
  anneals: z.object({
    sequence: z.string(),
    length: z.number(),
    tm: z.number(),
    gc_percent: z.number(),
    note: z.string().default(""),
  }),
  /** Not on this fragment's template at all. Null at a construct's outer ends. */
  tail: z
    .object({
      sequence: z.string(),
      length: z.number(),
      wallace_tm: z.number(),
      note: z.string().default(""),
    })
    .nullable(),
  /** A number that describes neither the PCR nor the assembly. */
  whole_oligo: z.object({
    tm: z.number(),
    hairpin_tm: z.number().nullable(),
    note: z.string().default(""),
  }),
});
export type TailedPrimer = z.infer<typeof tailedPrimerSchema>;

export const junctionSchema = z.object({
  index: z.number(),
  between: z.array(z.string()),
  at: z.number(),
  sequence: z.string().optional(),
  length: z.number().optional(),
  from_upstream: z.number().optional(),
  from_downstream: z.number().optional(),
  /** Bases on neither fragment — a tag or a linker both primers must carry. */
  interposed: z.number().optional(),
  carries: z.array(z.string()).default([]),
  wallace_tm: z.number().optional(),
  terminal_homopolymer_runs: z
    .object({
      start: z.number(),
      end: z.number(),
      classification: z.string(),
    })
    .optional(),
  hairpin_tm: z.number().nullable().optional(),
  /**
   * Whether the overlap folds on itself at the assembly temperature.
   *
   * `checked: false` means nothing looked, which is the state every overlap
   * can be in when the declared fold model is unavailable. `fraction` is how much of the duplex the
   * overlap exists to form it spends on itself instead. Read it against
   * `of_alternates`, not against a pass mark: there is not one, and the
   * measurements would not support inventing one.
   */
  fold: z
    .object({
      checked: z.boolean(),
      fraction: z.number().default(0),
      structure: z.string().default(""),
      model: z.string().default(""),
      of_alternates: z.object({ best: z.number(), worst: z.number(), count: z.number() }).nullish(),
      note: z.string().default(""),
    })
    .optional(),
  alternates: z.number().optional(),
  search: z
    .object({
      candidate_windows_generated: z.number(),
      candidate_windows_measured: z.number(),
      /** Whether the optional ViennaRNA diagnostic was measured for every generated window. */
      fold_diagnostic_complete: z.boolean().optional(),
      complete: z.boolean(),
      claim: z.string(),
      fold_claim: z.string().optional(),
    })
    .optional(),
  note: z.string().optional(),
  why_nothing: z.string().optional(),
});
export type JunctionEntry = z.infer<typeof junctionSchema>;

export const junctionResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("junction-primers"),
  provenance: provenanceSchema.optional(),
  assay: assaySchema.optional(),
  target: targetSummarySchema,
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  /** The joining chemistry, which has no default: they are four enzymes. */
  method: z.object({
    id: z.string(),
    name: z.string(),
    overlap_min: z.number(),
    overlap_max: z.number(),
    overlap_tm_min: z.number().nullable(),
    overlap_tm_metric: z.string().nullable().optional(),
    assembly_temperature: z.number().nullable(),
    note: z.string().default(""),
  }),
  /** Exact selected assembly authority; Gibson and NEBuilder carry different numeric shapes. */
  protocol: z
    .object({
      selection: z.string(),
      id: z.string().optional(),
      source_identity: z.string().optional(),
      source_url: z.string().optional(),
      source_revision: z.string().optional(),
      source_reviewed_date: z.string().optional(),
      fragment_count: z.number().optional(),
      execution_status: z.string().optional(),
      note: z.string().optional(),
    })
    .loose()
    .optional(),
  construct: z.object({
    length: z.number(),
    circular: z.boolean(),
    physical_fragments: z.number().optional(),
    segments: z.array(
      z.object({
        name: z.string(),
        kind: z.string(),
        length: z.number(),
        tailable: z.boolean(),
        orientation: z.string().optional(),
        production_method: z.string().optional(),
        concentration_ng_ul: z.number().nullable().optional(),
        mass_ng: z.number().nullable().optional(),
        volume_ul: z.number().nullable().optional(),
        restriction: z.record(z.string(), z.unknown()).nullable().optional(),
        features: z.array(z.record(z.string(), z.unknown())).optional(),
        provenance: z.record(z.string(), z.unknown()).nullable().optional(),
        molarity: z.record(z.string(), z.unknown()).nullable().optional(),
      }),
    ),
    note: z.string().default(""),
  }),
  assembly_graph: z.record(z.string(), z.unknown()).optional(),
  feature_integrity: z.record(z.string(), z.unknown()).optional(),
  workflow_evidence: workflowEvidenceResultSchema,
  search: z
    .object({
      fold_candidate_cap_per_junction: z.number(),
      backtrack_cap: z.number(),
      backtrack_steps_used: z.number(),
      backtrack_limit_hit: z.boolean(),
      complete: z.boolean(),
    })
    .optional(),
  junctions: z.array(junctionSchema).default([]),
  primers: z.array(tailedPrimerSchema).default([]),
  /** One reaction per amplified fragment; primers sharing a join never meet. */
  tubes: z.record(z.string(), z.array(z.string())).default({}),
  clashes: z.array(z.object({ between: z.array(z.number()), why: z.string() })).default([]),
  overlap_interactions: z
    .object({
      classification: z.string(),
      model_temperature_c: z.number().nullable(),
      pairs: z
        .array(
          z.object({
            a: z.number(),
            b: z.number(),
            dg: z.number(),
            tm: z.number(),
            model_temperature_c: z.number().nullable(),
          }),
        )
        .default([]),
      note: z.string(),
    })
    .optional(),
  considered: z.record(z.string(), z.string()).default({}),
  why_nothing: z.string().default(""),
  orderability: orderabilitySchema.optional(),
  order_sheet: z
    .array(
      orderLineSchema.extend({
        tube: z.string().optional(),
        note: z.string().optional(),
      }),
    )
    .default([]),
});
export type JunctionResult = z.infer<typeof junctionResultSchema>;

/* ── What a discriminating-pair run produces ──────────────────────────── */

export const discriminationSchema = z.object({
  strand: z.string(),
  /** Primer base against template base, e.g. "C*C". */
  terminus: z.string(),
  terminus_strength: z.string(),
  second_mismatch: z
    .object({
      at: z.number(),
      was: z.string(),
      now: z.string(),
      why: z.string().default(""),
    })
    .nullable(),
  /** What actually separates the alleles: the terminus, or the second mismatch. */
  rests_on: z.string(),
});
export type Discrimination = z.infer<typeof discriminationSchema>;

export const discriminatingResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("discriminating-pair"),
  off_targets: offTargetsSchema.optional(),
  ...carriesScan,
  provenance: provenanceSchema.optional(),
  assay: assaySchema.optional(),
  target: targetSummarySchema,
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  geometry: z.object({
    id: z.string(),
    name: z.string(),
    tubes: z.number(),
    note: z.string().default(""),
  }),
  /** Typed KASP semantics; null on ARMS/Tetra geometries. */
  kasp: z
    .object({
      assay_mode: z.string(),
      chemistry_family: z.string(),
      singleplex: z.boolean(),
      call_status: z.string(),
      call_model: z.record(z.string(), z.unknown()).nullable().optional(),
      junction_model: z.record(z.string(), z.unknown()).nullable().optional(),
      design_authority: z
        .object({
          method: z.string(),
          vendor_kraken_equivalent: z.boolean(),
          validation_required: z.boolean(),
          note: z.string(),
        })
        .optional(),
    })
    .nullable()
    .optional(),
  /** Exact selected KASP authority. Current V5 and historical V4 have intentionally different numeric shapes. */
  protocol: z
    .object({
      selection: z.string(),
      source_identity: z.string().optional(),
      source_url: z.string().optional(),
      source_revision: z.string().nullable().optional(),
      plate_format: z.string().optional(),
      instrument_model: z.string().optional(),
      rox_policy: z.string().optional(),
      readout: z
        .object({ channels: z.array(z.string()) })
        .loose()
        .optional(),
      note: z.string().optional(),
    })
    .loose()
    .optional(),
  /** Whether a blocking terminal mismatch exists at all depends on this. */
  variant: z
    .object({
      at: z.number(),
      alleles: z.array(z.string()).optional(),
      kind: z.string(),
      ref: z.string().optional(),
      alt: z.string().optional(),
      reference_accession: z.string().nullable().optional(),
      assembly: z.string().nullable().optional(),
      coordinate_system: z.string().nullable().optional(),
      strand: z.string().nullable().optional(),
      rsid: z.string().nullable().optional(),
      source: z.string().optional(),
      anchor: z.record(z.string(), z.unknown()).nullable().optional(),
      normalization: z.string().optional(),
      note: z.string().default(""),
    })
    .loose(),
  variant_normalized: z.record(z.string(), z.unknown()).optional(),
  variant_masking: z.record(z.string(), z.unknown()).optional(),
  mismatch_evidence_model: z.record(z.string(), z.unknown()).optional(),
  polymerase_discrimination_scope: z.record(z.string(), z.unknown()).optional(),
  validation_contract: z.record(z.string(), z.unknown()).optional(),
  workflow_evidence: workflowEvidenceResultSchema,
  discrimination: z.record(z.string(), discriminationSchema).default({}),
  primers: z
    .array(
      z.object({
        name: z.string(),
        allele: z.string(),
        strand: z.string(),
        sequence: z.string(),
        at: z.number(),
        length: z.number(),
        tm: z.number(),
        gc_percent: z.number(),
        /**
         * The fluorescent cassette this primer is read by, on KASP only.
         *
         * `null` on the gel-read geometries, and the distinction is the point:
         * a cassette tail on an ARMS primer is 21 bases of a chemistry that
         * assay does not use, and it would move every band by that much.
         */
        cassette: z
          .object({
            dye: z.string(),
            tail: z.string(),
            length: z.number(),
            /** The half that is actually on the template. */
            annealing: z.string(),
            annealing_tm: z.number(),
            note: z.string().default(""),
          })
          .nullish(),
        note: z.string().default(""),
      }),
    )
    .default([]),
  partners: z
    .array(
      z.object({
        for_alleles: z.array(z.string()),
        sequence: z.string(),
        at: z.number(),
        strand: z.enum(["plus", "minus"]).optional(),
        tm: z.number(),
        gc_percent: z.number(),
        length: z.number(),
        product_size: z.number(),
        cross_dimer_dg: z.number(),
        tm_difference: z.number(),
        note: z.string().default(""),
      }),
    )
    .default([]),
  /** Three-product topology for Tetra-ARMS; absent on ARMS/KASP. */
  band_geometry: z
    .object({
      allele_products_bp: z.record(z.string(), z.number()),
      outer_control_bp: z.number(),
      all_products_bp: z.array(z.number()).length(3),
      minimum_pairwise_separation_bp: z.number(),
      topology_complete: z.boolean(),
      resolution_status: z.string(),
      required_minimum_separation_bp: z.number().optional(),
    })
    .optional(),
  /** Named per allele, because one allele can fail while the other works. */
  refused: z.record(z.string(), z.string()).default({}),
  why_nothing: z.string().default(""),
  orderability: orderabilitySchema.optional(),
  order_sheet: z.array(orderLineSchema.extend({ note: z.string().optional() })).default([]),
});
export type DiscriminatingResult = z.infer<typeof discriminatingResultSchema>;

/* ── What a loop-set run produces ─────────────────────────────────────── */

export const loopOligoSchema = z.object({
  name: z.string(),
  sequence: z.string(),
  length: z.number(),
  built_from: z.array(z.string()),
  /** Two of the six are: their 5' half is not on the template at all. */
  composite: z.boolean(),
  target_tail_sequence: z.string().nullable().optional(),
  linker_sequence: z.string().nullable().optional(),
  tm: z.number(),
  gc_percent: z.number(),
  hairpin_tm: z.number().nullable(),
  self_dimer_tm: z.number().nullable(),
  /** Present on the composites: the half that actually binds the template. */
  anneals: z
    .object({ sequence: z.string(), tm: z.number(), note: z.string().default("") })
    .optional(),
  note: z.string().default(""),
});
export type LoopOligo = z.infer<typeof loopOligoSchema>;

export const loopSetEntrySchema = z.object({
  /** Specificity evidence for the current worker result; absence is never interpreted as clean. */
  off_targets: offTargetsSchema,
  /** LAMP-native six-core-region background topology evidence. */
  lamp_background_topology: z
    .object({
      checked: z.boolean(),
      risk_class: z.number(),
      classification: z.string(),
    })
    .loose()
    .optional(),
  /** Optional post-selection RT-LAMP RNA-structure accessibility diagnostic. */
  rna_target_accessibility: z
    .object({
      checked: z.boolean(),
      model: z.string().optional(),
      molecule: z.literal("RNA").optional(),
      parameter_authority: z.string().optional(),
      celsius: z.number().nullable().optional(),
      temperatures_c: z.array(z.number()).optional(),
      openings: z
        .record(
          z.string(),
          z.object({
            start: z.number(),
            length: z.number(),
            unpaired: z.number(),
          }),
        )
        .optional(),
      decision_impact: z.literal("none"),
      note: z.string().default(""),
    })
    .loose()
    .optional(),
  /** Position-aware conservation across an optional intended-target panel. */
  target_inclusivity: z.object({ checked: z.boolean() }).loose().optional(),
  at: z.number(),
  ends: z.number(),
  size: z.number(),
  /** PrimerExplorer amplified-region definition, distinct from the full F3–B3 envelope. */
  /** Historical LAMP results may predate the explicit geometry ledger. */
  f2_b2_span: z.number().optional(),
  /** F1c–B1c distance excluding the primer regions themselves. */
  middle_gap: z.number().optional(),
  /** Optional, and worth having: they roughly halve the time to a result. */
  loop_primers: z.number().optional(),
  /** Diagnostic whole-set Tm range; not the ranking target. */
  spread: z.number(),
  thermal_rank: z
    .object({
      corresponding_region_tm_difference: z.number(),
      inner_minus_outer_5c_error: z.number(),
      published_window_centre_error: z.number(),
    })
    .optional(),
  /** Soft, profile-scoped preferences used by the current LAMP ranker; never a validity verdict. */
  evidence_rank: z
    .object({
      preferred_f2_b2_distance_penalty: z.number(),
      preferred_outer_gap_penalty: z.number(),
      preferred_loop_tm_penalty: z.number(),
      preferred_f2_b2_span: z.array(z.number()).nullable(),
      preferred_outer_gap: z.array(z.number()).nullable(),
      preferred_loop_tm: z.array(z.number()).nullable(),
      geometry_profile: z.string(),
      classification: z.string(),
    })
    .optional(),
  /** Exact 3′-extendability evidence. This is a risk-ranking diagnostic, not a universal rejection threshold. */
  sequence_interaction_risk: z
    .object({
      classification: z.string(),
      review_at_or_above_bases: z.number(),
      core_core_max_bases: z.number(),
      core_core_review_events: z.number(),
      all_max_bases: z.number(),
      all_review_events: z.number(),
      events: z
        .array(
          z.object({
            primer_3p: z.string(),
            partner: z.string(),
            bases: z.number(),
            review: z.boolean(),
            core_core: z.boolean(),
          }),
        )
        .default([]),
      note: z.string(),
    })
    .optional(),
  /** Per-oligo terminal-GC descriptors retained because they participate in evidence ranking/review. */
  terminal_gc: z
    .record(
      z.string(),
      z.object({
        gc_in_last_6: z.number(),
        has_gc_clamp_in_last_6: z.boolean(),
        three_prime_gc_run: z.number(),
        review: z.boolean(),
        classification: z.string(),
      }),
    )
    .optional(),
  regions: z.array(z.object({ name: z.string(), at: z.number(), length: z.number() })),
  oligos: z.array(loopOligoSchema),
  interactions: z
    .object({
      checked: z.number(),
      model_temperature_c: z.number().nullable(),
      classification: z.string(),
      worst: z
        .array(z.object({ a: z.string(), b: z.string(), dg: z.number(), tm: z.number() }))
        .default([]),
      note: z.string(),
    })
    .loose()
    .optional(),
  note: z.string().default(""),
});
export type LoopSetEntry = z.infer<typeof loopSetEntrySchema>;

export const loopSetResultSchema = z.object({
  ...carriesRuntime,
  engine: z.literal("loop-set"),
  workflow_evidence: workflowEvidenceResultSchema,
  mode: z.enum(["design", "validate-existing"]).optional(),
  existing_set_validation: z
    .object({
      mode: z.literal("validate-existing"),
      mapped_unambiguously: z.boolean(),
      role_audits: z.array(
        z
          .object({
            role: z.string(),
            within_selected_design_envelope: z.boolean(),
            issues: z.array(z.string()),
          })
          .loose(),
      ),
      geometry: z.record(z.string(), z.number()),
      geometry_issues: z.array(z.string()),
      within_selected_design_envelope: z.boolean(),
      decision_impact: z.string(),
    })
    .optional(),
  ...carriesScan,
  ...carriesRt,
  provenance: provenanceSchema.optional(),
  modified_oligos: modifiedOligosProvenanceSchema.optional(),
  assay: assaySchema.optional(),
  /** Explicit detection/readout provenance. Historical saved runs may predate it. */
  readout: z
    .object({
      selection: z.string(),
      sequence_decision_impact: z.literal("none"),
      note: z.string(),
    })
    .optional(),
  lamp_scenario: z
    .object({
      sample: z
        .object({
          matrix: z.string(),
          preparation: z.string(),
          direct: z.boolean(),
          decision_impact: z.literal("none"),
        })
        .loose(),
      formulation: z.object({ selection: z.string(), decision_impact: z.literal("none") }).loose(),
      readout_chemistry: z
        .object({ selected: z.string(), branch: z.string(), decision_impact: z.literal("none") })
        .loose(),
      confirmation: z
        .object({
          selection: z.string(),
          reviewed_for_protocol: z.boolean().nullable().optional(),
          note: z.string(),
          decision_impact: z.literal("none"),
        })
        .loose(),
      detection_topology: z
        .object({
          selection: z.string(),
          decision_impact: z.literal("none"),
          multiplex_plan: z
            .object({
              status: z.string(),
              panel: z.array(
                z
                  .object({
                    target: z.string(),
                    method: z.string(),
                    reporter: z.string(),
                    channel: z.string(),
                    modified_oligo_role: z.string(),
                    set_sha256: z.string(),
                    authority_id: z.string(),
                    empirical_evidence_ref: z.string(),
                  })
                  .strict(),
              ),
              panel_sha256: z.string(),
              target_count: z.number().int().positive(),
              software_planning_bound: z.number().int().positive(),
              wet_lab_qualified_plex: z.null(),
              automatic_modified_oligo_design: z.literal(false),
              sequence_decision_impact: z.literal("none"),
              signal_claim: z.string(),
            })
            .strict()
            .nullable()
            .optional(),
        })
        .loose(),
      design_intent: z.object({ selection: z.string(), decision_impact: z.string() }).loose(),
      loop_policy: z.object({ selection: z.string(), decision_impact: z.string() }).loose(),
      bench_optimization: z
        .object({ values: z.record(z.string(), z.number()), decision_impact: z.literal("none") })
        .loose(),
      numeric_context: z.record(z.string(), z.unknown()).optional(),
      resolved_numeric_recipe: z
        .object({
          schema_version: z.string(),
          values: z.record(z.string(), z.number()),
          origins: z.record(z.string(), z.string()),
          ranges: z.record(z.string(), z.tuple([z.number(), z.number()])),
          applied_overlays: z.array(z.string()),
          unresolved_numeric_dependencies: z.array(z.unknown()),
          warnings: z.array(z.string()),
          dependency_axes: z.array(z.string()),
          sequence_decision_impact: z.literal("none"),
        })
        .loose()
        .optional(),
    })
    .loose()
    .optional(),
  target: targetSummarySchema,
  /**
   * LAMP has two distinct temperature authorities. Current workers report
   * `diagnostic_structure_temperature_c` for ordered-oligo structure checks;
   * PrimerExplorer role/Tm eligibility is separately versioned under
   * `parameter_set.thermodynamic_model`, while a bench hold belongs to a
   * selected named protocol. `screening_temperature_c` and `hold` are retained
   * only so historical saved responses remain readable; their old semantics
   * are never silently upgraded to the current diagnostic field.
   */
  reaction: reactionSchema
    .extend({
      diagnostic_structure_temperature_c: z.number().optional(),
      screening_temperature_c: z.number().optional(),
      hold: z.number().optional(),
      note: z.string().optional(),
    })
    .superRefine((value, ctx) => {
      if (
        value.diagnostic_structure_temperature_c == null &&
        value.screening_temperature_c == null &&
        value.hold == null
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message:
            "LAMP reaction must retain a current diagnostic or historical temperature context",
        });
      }
    }),
  /** Present only when a named kit-level LAMP protocol was selected. */
  protocol: z
    .object({
      selection: z.string(),
      vendor: z.string().optional(),
      kit_id: z.string(),
      protocol_kind: z.string().optional(),
      source_identity: z.string().optional(),
      source_url: z.string().url().optional(),
      source_revision: z.string().optional(),
      source_revision_date: z.string().optional(),
      source_revision_date_precision: z.string().optional(),
      source_reviewed_date: z.string().optional(),
      lifecycle: z.string().optional(),
      numeric_authority_status: z.string().optional(),
      primer_concentrations_uM: z.record(z.string(), z.number()).optional(),
      primer_amounts_pmol_per_reaction: z.record(z.string(), z.number()).optional(),
      reaction_volume_uL: z.number().optional(),
      hold_temperature_c: z.number().optional(),
      hold_temperature_range_c: z.tuple([z.number(), z.number()]).optional(),
      hold_time_min: z.number().optional(),
      hold_time_range_min: z.tuple([z.number(), z.number()]).optional(),
      temperature_envelope_c: z.tuple([z.number(), z.number()]).optional(),
      supports_dna: z.boolean().optional(),
      supports_rna: z.boolean().optional(),
      reverse_transcriptase: z.string().optional(),
      formats: z.array(z.string()).optional(),
      sample_matrices: z.array(z.string()).optional(),
      direct_sample_matrices: z.array(z.string()).optional(),
      chemistry: z.record(z.string(), z.unknown()).optional(),
      bench_optimization_scope: z.record(z.string(), z.unknown()).optional(),
      recommended_readouts: z.array(z.string()).optional(),
      recommended_readout_chemistries: z.array(z.string()).optional(),
      forbidden_readouts: z.record(z.string(), z.string()).optional(),
      forbidden_readout_chemistries: z.record(z.string(), z.string()).optional(),
      recommended_confirmation_modes: z.array(z.string()).optional(),
      readout_notes: z.array(z.string()).optional(),
      sample_compatibility_notes: z.array(z.string()).optional(),
      controls: z.array(z.string()).optional(),
      oligo_manufacturing_guidance: z.string().optional(),
      optimization_ranges: z.record(z.string(), z.unknown()).optional(),
      sequence_decision_impact: z.string().optional(),
      post_inactivation: z.string().optional(),
      carryover_prevention: z
        .object({
          included: z.boolean(),
          chemistry: z.string(),
          note: z.string(),
          optional_pre_hold: z.unknown().optional(),
        })
        .loose()
        .optional(),
      readout_compatibility: z
        .object({
          selected: z.string(),
          status: z.string(),
          reviewed_readouts: z.array(z.string()),
          forbidden_readouts: z.array(z.string()).optional(),
          note: z.string(),
        })
        .loose()
        .optional(),
      readout_chemistry_compatibility: z
        .object({
          selected: z.string(),
          branch: z.string(),
          decision_impact: z.string(),
        })
        .loose()
        .optional(),
    })
    .loose()
    .optional(),
  /** Chosen from the template's composition, and always said out loud. */
  parameter_set: z.object({
    id: z.string(),
    name: z.string(),
    /** Versioned PrimerExplorer design-eligibility/ranking authority. */
    thermodynamic_model: z
      .object({
        id: z.string(),
        tm_reference: z.string(),
        end_stability_reference: z.string(),
        oligo_concentration_uM: z.number(),
        sodium_mM: z.number(),
        magnesium_mM: z.number(),
        effective_sodium_mM: z.number(),
        role: z.string(),
      })
      .loose()
      .optional(),
    chosen_from: z.string(),
    geometry_profile: z
      .object({
        id: z.string(),
        name: z.string(),
        source: z.string(),
        claim: z.string(),
        valid_f2_b2_span: z.array(z.number()),
        valid_loop_span: z.array(z.number()),
        valid_outer_gap: z.array(z.number()),
        valid_middle_gap: z.array(z.number()),
        preferred_f2_b2_span: z.array(z.number()).nullable(),
        preferred_outer_gap: z.array(z.number()).nullable(),
        preferred_loop_tm: z.array(z.number()).nullable(),
      })
      .optional(),
    inner_linker: z
      .object({
        id: z.string(),
        sequence: z.string().nullable(),
        classification: z.string(),
        claim: z.string(),
      })
      .optional(),
    preferred_f2_b2_span: z.array(z.number()).nullable().optional(),
    preferred_outer_gap: z.array(z.number()).nullable().optional(),
    preferred_loop_tm: z.array(z.number()).nullable().optional(),
    outer: z.object({ tm: z.array(z.number().nullable()), length: z.array(z.number()) }),
    inner: z.object({ tm: z.array(z.number().nullable()), length: z.array(z.number()) }),
    loop: z.object({ tm: z.array(z.number().nullable()), length: z.array(z.number()) }),
    terminal_stability: z
      .object({
        window_bases: z.number(),
        regular_critical_max_dg_kcal_mol: z.number(),
        loop_3p_max_dg_kcal_mol: z.number(),
        regular_scope: z.string(),
        loop_scope: z.string(),
        classification: z.string(),
      })
      .optional(),
    gc: z.array(z.number().nullable()).default([]),
    f2_b2_span: z.array(z.number()).default([]),
    loop_span: z.array(z.number()).default([]),
    outer_gap: z.array(z.number()).default([]),
    middle_gap: z.array(z.number()).default([]),
    /**
     * Which of the numbers above are somebody's rather than the literature's.
     *
     * A set reported without this reads as published guidance whatever was
     * typed over it. These are thermodynamic/search bounds, not a fabricated
     * bench hold. Empty means the reviewed source profile stands as written.
     */
    overruled: z.array(z.string()).default([]),
    why: z.string().default(""),
  }),
  target_inclusivity: z.object({ checked: z.boolean() }).loose().optional(),
  sets: z.array(loopSetEntrySchema).default([]),
  /** Bounded-search provenance. A false `complete` forbids a global-optimum claim. */
  /** Bounded-search provenance was added after the first persisted LAMP runs. */
  search: z
    .object({
      complete: z.boolean(),
      forward_halves_capped: z.boolean(),
      backward_halves_capped: z.boolean(),
      join_evaluation_capped: z.boolean(),
      half_limit_per_orientation: z.number(),
      join_evaluation_limit: z.number(),
      join_evaluations: z.number(),
      core_pair_evaluation_limit: z.number().optional(),
      core_pair_evaluations: z.number().optional(),
      core_pair_evaluation_capped: z.boolean().optional(),
      core_pair_outer_expansion_capped: z.boolean().optional(),
      core_pairs_outer_expansion_limit: z.number().optional(),
      core_pairs_outer_expanded: z.number().optional(),
      core_pair_outer_expansion_strategy: z.string().optional(),
      feasible_core_partners_before_local_sampling: z.number().optional(),
      feasible_core_partners_after_local_sampling: z.number().optional(),
      forward_halves_with_feasible_partners: z.number().optional(),
      core_pair_budget_allocation: z.string().optional(),
      backward_partner_sampling_used: z.boolean().optional(),
      max_backward_partners_per_forward: z.number().optional(),
      outer_candidate_truncation_used: z.boolean().optional(),
      outer_candidates_per_side: z.number().optional(),
      outer_pairs_retained_per_core: z.number().optional(),
      complete_outer_pair_combinations_evaluated: z.number().optional(),
      risk_ranking_capped: z.boolean().optional(),
      risk_rank_pool_limit: z.number().optional(),
      risk_rank_pool_evaluated: z.number().optional(),
      risk_rank_pool_strategy: z.string().optional(),
      orientation_policy: z.string().optional(),
      orientation_canonicalized: z.boolean().optional(),
      orientation_note: z.string().optional(),
      claim: z.string(),
    })
    .loose()
    .optional(),
  /** What each stage produced, so "nothing" names which of six roles ran out. */
  considered: z.record(z.string(), z.number()).default({}),
  why_nothing: z.string().default(""),
  order_sheet: z.array(orderLineSchema.extend({ note: z.string().optional() })).default([]),
});
export type LoopSetResult = z.infer<typeof loopSetResultSchema>;

export const runResultSchema = z.discriminatedUnion("engine", [
  designResultSchema,
  universalResultSchema,
  nestedResultSchema,
  outwardResultSchema,
  probeResultSchema,
  singleResultSchema,
  mutagenicResultSchema,
  tilingResultSchema,
  junctionResultSchema,
  discriminatingResultSchema,
  loopSetResultSchema,
]);
export type RunResult = z.infer<typeof runResultSchema>;

/* ── What is already on the bench ─────────────────────────────────────── */

/** One restriction enzyme, ranked for one region. */
export const enzymeChoiceSchema = z.object({
  enzyme: z.string(),
  site: z.string(),
  cuts_inside: z.array(z.number()).default([]),
  /** Whether it satisfies the explicitly echoed restriction question. */
  usable: z.boolean(),
  why: z.string(),
  expected_fragment: z
    .object({
      cuts: z.number(),
      median: z.number(),
      mean: z.number(),
      /** Longer than the mean, always. The one to plan against. */
      mean_at_a_random_base: z.number(),
      note: z.string(),
    })
    .nullable(),
});
export type EnzymeChoice = z.infer<typeof enzymeChoiceSchema>;

export const enzymeRankingSchema = z.object({
  /**
   * Which question the ranking answers.
   *
   * `inverse-flank` for standard two-flank inverse PCR, `absent` for cloning,
   * or `open-once` only for an explicitly different one-cut workflow. Echoed
   * back rather than assumed because these are different scientific questions.
   */
  purpose: z.enum(["inverse-flank", "absent", "open-once"]),
  enzymes: z.array(enzymeChoiceSchema).default([]),
});
export type EnzymeRanking = z.infer<typeof enzymeRankingSchema>;

/** Where one universal primer really falls in the vector somebody has. */
export const vectorPrimerSchema = z.object({
  name: z.string(),
  sequence: z.string(),
  reads: z.string(),
  family: z.string(),
  tm: z.number(),
  note: z.string().default(""),
  /** Absent until a vector is given, because position is a fact about one. */
  occurrences: z.number().optional(),
  at: z.number().nullable().optional(),
  usable: z.boolean().optional(),
  why: z.string().optional(),
});
export type VectorPrimer = z.infer<typeof vectorPrimerSchema>;

export const vectorPrimersSchema = z.object({
  checked_against: z.string().default(""),
  primers: z.array(vectorPrimerSchema).default([]),
  /** The melting-temperature window a partner for each usable primer needs. */
  partner_windows: z
    .record(z.string(), z.object({ tm_min: z.number(), tm_opt: z.number(), tm_max: z.number() }))
    .default({}),
  note: z.string().default(""),
});
export type VectorPrimers = z.infer<typeof vectorPrimersSchema>;

/* ── Several targets in one tube ──────────────────────────────────────── */

export const multiplexPairSchema = z.object({
  target: z.string(),
  left: z.string(),
  right: z.string(),
  product_size: z.number(),
  candidate: z.number(),
});
export type MultiplexPair = z.infer<typeof multiplexPairSchema>;

export const tubeSchema = z.object({
  tube: z.number(),
  tube_id: z.string().optional(),
  /** The set-level objective. A number to compare sets by, not to threshold. */
  badness: z.number(),
  crowded: z.boolean(),
  how_it_was_chosen: z.array(z.string()).default([]),
  pairs: z.array(multiplexPairSchema).default([]),
  worst_interactions: z
    .array(z.object({ a: z.string(), b: z.string(), badness: z.number() }))
    .default([]),
  separation: z.object({
    classification: z.string().default("reference-spacing-risk-not-observed-resolution"),
    needed: z.number(),
    delivered_by: z.string(),
    unresolvable: z
      .array(
        z.object({
          a: z.string(),
          b: z.string(),
          sizes: z.array(z.number()),
          apart: z.number(),
          needed: z.number(),
        }),
      )
      .default([]),
    note: z.string(),
  }),
});
export type Tube = z.infer<typeof tubeSchema>;

const multiplexOrderLineSchema = orderLineSchema.extend({
  /** Multiplex does not invent a per-primer Tm when the set engine did not compute one. */
  tm: z.number().optional(),
  /** Physical tube/pool provenance survives client-side parsing and export. */
  tube: z.string(),
  pool: z.number().int().nonnegative(),
  planned_primer_concentration_nm: z.number().positive().optional(),
  empirical_evidence_ref: z.string().optional(),
  note: z.string().optional(),
});

export const multiplexResultSchema = z.object({
  ...carriesRuntime,
  engine: z.string(),
  mode: z.literal("multiplex"),
  readout: z.string(),
  readout_profile: z.string().nullable().optional(),
  /** One executable assay contract governs all target searches in the tube. */
  assay: assaySchema,
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.unknown()).optional(),
  constraint_scope: z.enum(["shared", "per-target"]),
  provenance: provenanceSchema,
  /** Named chemistry must be identical across every target in a physical tube. */
  protocol: flankingProtocolSchema.optional(),
  /** Shared RT authority/placement, when the multiplex starts from RNA. */
  reverse_transcription: reverseTranscriptionSchema,
  colony_context: colonyContextSchema.optional(),
  targets: z
    .array(
      z.object({
        name: z.string(),
        candidates: z.number(),
        why_nothing: z.string().default(""),
        target: targetSummarySchema.optional(),
        constraints: z.record(z.string(), z.unknown()),
        background: backgroundSchema.optional(),
        inclusivity: inclusivitySchema.optional(),
        primer_concentration_nm: z.number().positive().optional(),
        empirical_evidence_ref: z.string().optional(),
      }),
    )
    .default([]),
  crowded_above: z.number(),
  tubes: z.array(tubeSchema).default([]),
  order_sheet: z.array(multiplexOrderLineSchema).default([]),
  panel_validation_scope: z.string().default("final-selected-oligos-grouped-by-tube"),
  panel_identity: z
    .object({
      panel_sha256: z.string().regex(/^[0-9a-f]{64}$/),
      formulation_sha256: z.string().regex(/^[0-9a-f]{64}$/),
      identity_scope: z.string(),
      formulation_identity_scope: z.string(),
      software_target_bound: z.number().int().positive(),
      wet_lab_qualified_plex: z.null(),
    })
    .strict(),
  panel_cross_product_specificity: z.array(z.record(z.string(), z.unknown())).default([]),
  selection_method: z
    .object({
      objective: z.string(),
      readout_in_selection: z.boolean().default(false),
      optimizer: z.string(),
      optimizer_mode: z.enum(["exact", "local"]),
      simulated_annealing: z.literal(false),
      exhaustive_within_evaluated_candidate_pools: z.boolean(),
      global_optimum_claimed: z.literal(false),
      candidate_pool_optimum_claimed: z.boolean(),
      candidates_per_target: z.number(),
      rounds_per_tube: z.number(),
      seed: z.number(),
      per_tube: z.number(),
      tube_split_explicit: z.boolean(),
      tube_assignment: z.object({
        strategy: z.enum([
          "explicit-target-tube-identities",
          "single-tube",
          "deterministic-fewest-candidates-first-chunking",
        ]),
        global_partition_optimized: z.literal(false),
        explicit: z.boolean(),
        tube_count: z.number().int().positive(),
        note: z.string(),
      }),
    })
    .optional(),
  note: z.string().default(""),
});
export type MultiplexResult = z.infer<typeof multiplexResultSchema>;

/* ── A pair somebody already has ──────────────────────────────────────── */

/** One measurement beside the window it is compared against. */
export const checkMeasurementSchema = z.object({
  name: z.string(),
  value: z.number(),
  /** Present for structures: the free energy, beside the melting temperature. */
  dg: z.number().optional(),
  wanted: z.array(z.number()).nullable(),
  unit: z.string(),
  inside: z.boolean().nullable(),
  off_by: z.number().nullable(),
  detail: z.string().optional(),
});
export type CheckMeasurement = z.infer<typeof checkMeasurementSchema>;

export const checkedPairSchema = z.object({
  engine: z.string(),
  mode: z.literal("check"),
  provenance: provenanceSchema.optional(),
  target: targetSummarySchema,
  reaction: reactionSchema,
  constraints: z.record(z.string(), z.union([z.number(), z.string()]).nullish()),
  primers: z.record(
    z.string(),
    oligoSchema.extend({
      at: z.number().nullable(),
      occurrences: z.number(),
      orientation: z.string(),
      checks: z.array(checkMeasurementSchema),
    }),
  ),
  pair: z.object({ checks: z.array(checkMeasurementSchema) }),
  product: z.object({
    exists: z.boolean(),
    size: z.number().optional(),
    from: z.number().optional(),
    to: z.number().optional(),
    sequence: z.string().optional(),
    in_range: z.boolean().optional(),
    wanted: z.array(z.number()).optional(),
    note: z.string().optional(),
  }),
  accessibility: z
    .object({ checked: z.boolean(), celsius: z.number().nullable() })
    .loose()
    .nullable(),
  off_targets: z
    .object({
      checked: z.boolean(),
      note: z.string().optional(),
      product_count: z.number().optional(),
    })
    .loose(),
  note: z.string(),
});
export type CheckedPair = z.infer<typeof checkedPairSchema>;

/* ── Projects ──────────────────────────────────────────────────────────── */

/**
 * What somebody has told us about how they work.
 *
 * Every field optional and every absence meaningful: a preference nobody has
 * set falls through to whatever the application would have done anyway, which
 * is what keeps this from being a second source of truth for defaults.
 */
export const preferencesSchema = z.object({
  /** The enzyme actually on this person's bench, when a module offers it. */
  preferredPolymerase: z.string().optional(),
});
export type Preferences = z.infer<typeof preferencesSchema>;

/** A freshly minted share link. The token is returned once and never again. */
export const shareLinkSchema = z.object({ token: z.string() });

/** What an import did, so the interface can say more than "done". */
export const importedSchema = z.object({
  projects: z.number(),
  runs: z.number(),
  alreadyHere: z.number(),
  /** Projects that were deleted and have been brought back. */
  restored: z.number(),
  refused: z.number(),
});
export type Imported = z.infer<typeof importedSchema>;

/** The ceilings an account works inside, as the store enforces them. */
export type ProjectLimits = z.infer<typeof projectLimitsSchema>;

export const projectSchema = z.object({
  id: z.string(),
  name: z.string(),
  notes: z.string(),
  moduleId: z.string(),
  /** The draft: what has been filled in, step by step. */
  settings: z.record(z.string(), z.unknown()).default({}),
  draftSchemaVersion: z.number().int().default(CURRENT_DRAFT_SCHEMA_VERSION),
  moduleContractVersion: z.string().default(CURRENT_MODULE_CONTRACT_VERSION),
  createdAt: z.string(),
  updatedAt: z.string(),
  runCount: z.number(),
});
export type Project = z.infer<typeof projectSchema>;

export const runSummarySchema = z.object({
  id: z.string(),
  label: z.string(),
  createdAt: z.string(),
  pairCount: z.number(),
  resultCount: z.number(),
  resultUnit: z.string(),
  targetName: z.string(),
  /**
   * Whether a share link exists — not which. The token is stored only as its
   * hash, so an interface can offer to withdraw or replace one and can never
   * offer to show you one you have lost.
   */
  shared: z.boolean().default(false),
});
export type RunSummary = z.infer<typeof runSummarySchema>;

export const runSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  label: z.string(),
  /** Exactly what was asked for. Without it the result cannot be repeated. */
  request: z.record(z.string(), z.unknown()),
  result: runResultSchema,
  requestSchemaVersion: z.number().int().default(CURRENT_REQUEST_SCHEMA_VERSION),
  resultSchemaVersion: z.number().int().default(CURRENT_RESULT_SCHEMA_VERSION),
  moduleContractVersion: z.string().default(CURRENT_MODULE_CONTRACT_VERSION),
  toolchainFingerprint: z.string().nullable().optional(),
  runFingerprint: z.string().nullable().optional(),
  engineId: z.string().nullable().optional(),
  moduleId: z.string().nullable().optional(),
  resultCount: z.number().default(0),
  resultUnit: z.string().default("result"),
  targetName: z.string().default(""),
  createdAt: z.string(),
});

/**
 * A run reached through a share link.
 *
 * The same run without its project. Not a trimmed view of the same response —
 * the server does not send the project id to an anonymous caller at all, and
 * this schema is how that stays true: a field added back to the wire would
 * have to be added here too, deliberately, rather than arriving unnoticed.
 */
export const sharedRunSchema = runSchema.omit({ projectId: true });
export type SharedRun = z.infer<typeof sharedRunSchema>;
export type Run = z.infer<typeof runSchema>;

export const runAnswerSchema = z.object({
  run: runSchema,
  project: projectSchema,
});

/** Durable Generation 1 foundation execution job with measured lifecycle stages. */
export const runJobSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  moduleId: z.string(),
  engineId: z.string(),
  requestFingerprint: z.string(),
  label: z.string(),
  runId: z.string().nullable(),
  status: z.enum(["queued", "running", "cancel_requested", "cancelled", "completed", "failed"]),
  stage: z.string(),
  progress: z.record(z.string(), z.unknown()).default({}),
  error: z.record(z.string(), z.unknown()).nullable(),
  createdAt: z.string(),
  startedAt: z.string().nullable(),
  finishedAt: z.string().nullable(),
  updatedAt: z.string(),
});
export type RunJob = z.infer<typeof runJobSchema>;

/** Mirrors `pcr_projects::ProjectError`. */
export const projectErrorSchema = z.discriminatedUnion("kind", [
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("notFound") }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("invalidName"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("invalidData"), detail: z.string() }),
  z.object({
    ...apiErrorEnvelopeMetaShape,
    kind: z.literal("tooManyProjects"),
    detail: z.string(),
  }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("storageLimit"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("conflict"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("notAnExport"), detail: z.string() }),
  z.object({ ...apiErrorEnvelopeMetaShape, kind: z.literal("store"), detail: z.string() }),
]);
export type ProjectError = z.infer<typeof projectErrorSchema>;
export type {
  DesignPayload,
  DesignRequest,
  ModuleDesignRequest,
} from "@/lib/contracts/design-requests";

// `STATUS_LABELS` used to live here. It moved to `labels.ts` because importing
// it from a client component brought zod and every schema below with it — 299 KB
// of bundle to render one word. See that file for the whole story.
