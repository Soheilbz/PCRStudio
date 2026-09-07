/**
 * What each assay's design page asks, in what order, in its own words.
 *
 * Every one of the twenty-one modules rendered the same five steps in the same
 * order under the same headings, and a per-assay review of all of them found
 * that this fits exactly one: standard PCR, which is the assay the form was
 * built around. Everywhere else it was wrong in one of three ways.
 *
 * **The order was backwards.** Standard PCR asks "what is the product for?" on
 * step two, and that answer sets the product size — while the region it has to
 * contain is drawn on step one. Draw six hundred bases, then choose a purpose
 * whose products stop at five hundred, and nothing on either screen says the
 * two answers cannot both be true.
 *
 * **The question had no answer.** "What are you amplifying from?" on a Gibson
 * page, which takes a list of fragments and no template. "Paste a background
 * genome" on an assembly, where the specificity that decides the outcome is
 * internal to the construct and already computed.
 *
 * **The step was inert.** LAMP's engine refuses every one of the fifteen
 * generic constraint boxes; typing in any of them turns a valid run into an
 * error. A step that can only do harm is not a step to trim.
 *
 * So the steps are declared per assay rather than fixed. What stays shared is
 * the *components* — a sequence box is a sequence box — and what stops being
 * shared is which of them appear, in what order, under what heading, and with
 * which bench tools beside them.
 *
 * This file is the shape of each page. The controls each assay still wants and
 * no engine can yet take are recorded separately, in
 * `docs/audits/design-pages-per-assay.md`.
 */

import capabilities from "./page-capabilities.generated.json";

import {
  Beaker,
  Blocks,
  Crosshair,
  FlaskConical,
  ListChecks,
  Microscope,
  Radar,
  ScanSearch,
  Scissors,
  SlidersHorizontal,
  Target,
  Thermometer,
  Waypoints,
  type LucideIcon,
} from "lucide-react";

/** The step bodies that exist. Which of them a page uses is per assay. */
export type StepId =
  | "target"
  | "design"
  | "strategy"
  | "constraints"
  | "vector"
  | "reaction"
  | "specificity"
  | "validation"
  | "construct"
  | "review";

/** A bench tool that belongs beside a particular assay, and no others. */
export type ToolId = "enzyme" | "cloning-tails" | "vector-primers" | "check-primers";

/**
 * An optional control an assay may offer, named by the field it fills in.
 *
 * Listed per assay rather than shown wherever its engine happens to accept it.
 * Eight modules share the pair engine, and "is this template a circle?" is a
 * real question for a plasmid screen and a meaningless one for an RPA assay on
 * genomic DNA — the same reason the restriction-enzyme chooser used to appear
 * on the RPA page and had to be taken off it.
 *
 * `page-plan.wiring.test.ts` asserts that every control listed here is a field
 * the assay's engine actually accepts, in both directions.
 */
export type ControlId = "circular" | "tails" | "excluded";

export interface StepPlan {
  id: StepId;
  /** The tab label. Short, because five of them share a row on a phone. */
  title: string;
  icon: LucideIcon;
  /** The question this step asks, in this assay's words. */
  heading: string;
  /** Why it is asked, in this assay's words. */
  description: string;
}

export interface PagePlan {
  steps: StepPlan[];
  /**
   * Tools this assay actually uses.
   *
   * These used to render on every page: the restriction-enzyme chooser and the
   * vector-primer table appeared on the RPA page, under a heading explaining
   * what an inverse PCR needs. Measured in the running app, not inferred.
   */
  tools: ToolId[];
  /**
   * What this assay returns, so nothing says "pairs" for a scheme of tiles.
   *
   * `how` is what the run is asked for; several engines take no such number at
   * all, and for those it is absent and the control is not rendered.
   */
  unit: { one: string; many: string; how: string | null };
  /**
   * Values this assay *is*, rather than values somebody chooses.
   *
   * The three genotyping assays share one engine and are told apart by a
   * `geometry`, which was a dropdown defaulting to `arms-two-tube` on all
   * three. Measured against the running core: the tetra-primer page, left
   * untouched, designed an ARMS two-tube assay and reported it as a success.
   * The wrong assay, silently, for anybody who did not know to change a
   * control that should never have been theirs.
   */
  fixed?: Record<string, string>;
  /**
   * Visible, editable starting states.
   *
   * Unlike `fixed`, these are ordinary controls the user may change. They are
   * seeded into the draft so a value visibly selected in the UI is also what
   * the hidden draft form submits. A rendered fallback such as
   * `value={draft.x || "unresolved"}` without a draft value is not provenance:
   * it looks explicit while the request still omits the field.
   */
  initial?: Record<string, string>;
  /**
   * Optional controls this assay offers, beyond the ones every page has.
   *
   * Absent means the question is not asked here, which is a decision rather
   * than an omission: a control an assay has no use for is a control somebody
   * has to work out is irrelevant to them.
   */
  asks?: ControlId[];
}

/* ── The step bodies, in the words each assay would use ─────────────────── */

const SEQUENCE: Omit<StepPlan, "heading" | "description"> = {
  id: "target",
  title: "Target",
  icon: Target,
};

const ASSAY_DESIGN: Omit<StepPlan, "heading" | "description"> = {
  id: "design",
  title: "Design",
  icon: Crosshair,
};

const STRATEGY: Omit<StepPlan, "heading" | "description"> = {
  id: "strategy",
  title: "Strategy",
  icon: Radar,
};

const VECTOR: Omit<StepPlan, "heading" | "description"> = {
  id: "vector",
  title: "Vector & enzymes",
  icon: Scissors,
};

const VALIDATION: Omit<StepPlan, "heading" | "description"> = {
  id: "validation",
  title: "Validation",
  icon: Microscope,
};

const CONSTRUCT: Omit<StepPlan, "heading" | "description"> = {
  id: "construct",
  title: "Simulation",
  icon: Blocks,
};

const NUMBERS: Omit<StepPlan, "heading" | "description"> = {
  id: "constraints",
  title: "Constraints",
  icon: SlidersHorizontal,
};

const TUBE: Omit<StepPlan, "heading" | "description"> = {
  id: "reaction",
  title: "Reaction",
  icon: Beaker,
};

const ELSEWHERE: Omit<StepPlan, "heading" | "description"> = {
  id: "specificity",
  title: "Specificity",
  icon: ScanSearch,
};

const LAST_LOOK: Omit<StepPlan, "heading" | "description"> = {
  id: "review",
  title: "Review and run",
  icon: ListChecks,
};

/** A step, with this assay's words on it. */
function step(
  base: Omit<StepPlan, "heading" | "description">,
  heading: string,
  description: string,
  over: Partial<StepPlan> = {},
): StepPlan {
  return { ...base, heading, description, ...over };
}

/* ── The twenty-one, each stating every step ────────────────────────────── */

/*
 * There is no shared default, deliberately.
 *
 * An earlier version of this file had an `amplification()` helper that filled
 * in whatever an assay did not override, and an audit of the result found what
 * that always produces: ninety-nine step slots carrying fifty distinct
 * headings. "Everything before it runs" appeared on all twenty of the pages
 * with a review step; "What is in the tube?" on fourteen. The shapes differed
 * and the words did not, which is a shared page wearing twenty-one hats.
 *
 * So every assay writes every step. It is more text, and the text is the point:
 * a reaction step that cannot say anything about this particular assay is a
 * reaction step this assay did not need.
 */

type PageCopy = Pick<PagePlan, "steps">;

const PLANS: Record<string, PageCopy> = {
  /* ── Amplify a region ────────────────────────────────────────────────── */

  "standard-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What are you amplifying from?",
        "Paste it, drop a file on it, or give an accession. Anything stripped or converted is listed back to you before a primer is picked.",
      ),
      step(
        NUMBERS,
        "What has to be true of a pair?",
        "Start from what the product is for — that answer sets the sizes every other box is judged against. The rest are empty on purpose: empty means this assay's own value, shown in grey.",
      ),
      step(
        TUBE,
        "What is in the tube?",
        "A melting temperature is not a property of a primer. It is a property of a primer in a buffer, and the buffers people use disagree by more than a design decision does.",
      ),
      step(
        ELSEWHERE,
        "What else could these primers find?",
        "A second band is the failure this assay actually has. The sequence you pasted is always scanned against its own primers, so a repeat inside it is found either way. What this adds is everything else in the tube — a plasmid and its host, a related gene.",
      ),
      step(
        LAST_LOOK,
        "The pair, before you order it",
        "The last place to notice the wrong sequence was pasted. Check the product size against the gel you will run it on, and the annealing temperature against the block you have.",
      ),
    ],
  },

  "colony-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What went into the vector, and what material will you screen?",
        "Record the insert and the host context first. Colony PCR starts from crude biological material, so host identity belongs to the biological input while lysis and SOP provenance stay with the reaction.",
      ),
      step(
        STRATEGY,
        "What answer must the colony screen distinguish?",
        "Choose insert-specific, vector-plus-insert, two-vector-primer or orientation screening before primer selection. Expected positive and empty-vector bands are assay evidence: if the gel cannot resolve the two outcomes, a technically amplifiable pair still does not answer the screening question.",
        { title: "Screen strategy", icon: Radar },
      ),
      step(
        NUMBERS,
        "What has to be true of primers on a crude lysate?",
        "Keep the design envelope short and robust, but treat product-size separation as part of the selected screening strategy rather than as a generic primer-quality score.",
      ),
      step(
        TUBE,
        "How will the colony be prepared and which SOP owns the reaction?",
        "Direct transfer, water or buffer lysate and host-specific preparation are different pre-analytical branches. PCRStudio records the actual vendor or laboratory SOP and does not invent a universal lysis temperature, time or cycle count.",
      ),
      step(
        ELSEWHERE,
        "What else in the colony could make a misleading band?",
        "The host genome and vector backbone are both present whether the insert is correct or not. Challenge the annealing halves against those backgrounds so an apparent positive is not simply an off-target product.",
      ),
      step(
        LAST_LOOK,
        "The screen, before you order it",
        "Confirm the selected strategy, expected positive and control-band logic, resolvable band separation, host/preparation SOP and specificity evidence together. A screen whose two biological outcomes look the same on the chosen readout is not a useful screen.",
      ),
    ],
  },

  "long-range-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What are you amplifying, and is it intact?",
        "For products of several kilobases, template integrity can become as limiting as primer quality. Record the template class and integrity, because a valid pair cannot compensate for a preparation that is too fragmented for the requested span.",
      ),
      step(
        NUMBERS,
        "What has to be true of a pair at this length?",
        "The current long-range profile uses longer primers and a warmer search window, but the cycling relationship is kit-specific. Keep primer bounds separate from the selected polymerase's documented annealing/extension programme.",
      ),
      step(
        TUBE,
        "Which enzyme mix, and how long does it get?",
        "Long-range PCR is not ordinary PCR with a larger product ceiling. Polymerase system, template class, product length and the supplier's extension model are coupled, so the selected kit/protocol must travel with the design.",
      ),
      step(
        ELSEWHERE,
        "What else could start a shorter product?",
        "A long product is unforgiving: a mispriming that would give a faint extra band in an ordinary reaction often gives nothing at all here, because the shorter wrong product amplifies faster than the right one.",
      ),
      step(
        LAST_LOOK,
        "The run, before you commit an afternoon to it",
        "Check the extension time and the total run length. This is the one assay where the programme is most of the cost of being wrong.",
      ),
    ],
  },

  "nested-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What template must survive both amplification rounds?",
        "Provide the sequence and biological target once. Round-one and round-two geometry are designed separately so the Target page never mixes specimen identity with nested-primer architecture.",
      ),
      step(
        ASSAY_DESIGN,
        "How should the outer and inner pairs nest?",
        "Set the two product windows, whether one primer is reused, and the minimum inward relationship. These coupled choices define nested geometry and are not ordinary single-pair constraints.",
        { title: "Nested design", icon: Crosshair },
      ),
      step(
        TUBE,
        "How will product move from round one to round two?",
        "Generation 1 executes two physically separate tubes. Reaction records the thermodynamic context and any explicit carry-over prevention strategy without inventing a one-tube protocol.",
        { title: "Rounds & carry-over", icon: Beaker },
      ),
      step(
        ELSEWHERE,
        "What else could seed either amplification round?",
        "A weak outer off-target can become a strong second-round product, so the relevant background must challenge the scheme before the extra amplification is allowed to create false confidence.",
      ),
      step(
        LAST_LOOK,
        "Both nested products, before you order four primers",
        "Review outer/inner containment, any shared primer, carry-over handling, specificity and the two product sizes together. Nested amplification is a coupled scheme, not two unrelated PCRs.",
      ),
    ],
  },

  "inverse-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What intact known anchor will the primers read away from?",
        "Provide the complete known sequence. Generation 1 treats it as the intact anchor and does not pretend an internal target window can describe an inverse-PCR restriction/self-ligation topology.",
      ),
      step(
        STRATEGY,
        "How was the unknown-flank template created?",
        "Record the restriction enzyme, self-ligation branch, end-phosphate and methylation/circularisation provenance. These preparation facts determine whether the inverse template exists at all.",
        { title: "Digest & circle", icon: Scissors },
      ),
      step(
        NUMBERS,
        "What must be true of the outward-reading pair?",
        "Primer thermodynamics and sequence quality are still design constraints, but product length is partly unknown because the product deliberately enters sequence that was not supplied.",
      ),
      step(
        TUBE,
        "Which amplification context can tolerate the unknown product length?",
        "Reaction chemistry and extension capacity belong here. They do not determine the restriction topology and cannot repair an invalid self-ligation preparation.",
      ),
      step(
        ELSEWHERE,
        "Could the known anchor occur somewhere else in the sample?",
        "The primers intentionally enter unknown flanks, so background evidence is bounded. A supplied host or repeated anchor can still reveal a competing inverse product and should be challenged explicitly.",
      ),
      step(
        LAST_LOOK,
        "The outward walk, before you order it",
        "Check the anchor is complete, the named enzyme has no forbidden site in it, preparation provenance is explicit, and both primers read outward into the two unknown flanks.",
      ),
    ],
  },

  /* ── Quantify ────────────────────────────────────────────────────────── */

  "qpcr-sybr": {
    steps: [
      step(
        SEQUENCE,
        "What are you quantifying?",
        "Declare DNA versus RNA/cDNA, the target window and any exon-junction evidence before design. A short dye-qPCR amplicon can still be biologically wrong if genomic carryover or transcript structure was ignored.",
      ),
      step(
        NUMBERS,
        "What has to be true of a dye-qPCR pair?",
        "Short products and a narrow thermal window support efficient cycling, while the assay-specific defaults stay visible as defaults rather than becoming anonymous user choices.",
      ),
      step(
        TUBE,
        "Which dye chemistry will report double-stranded product?",
        "Intercalating-dye chemistries report every double-stranded product, not only the intended amplicon. The selected master mix is bench provenance; the versioned thermodynamic screening context remains a separate computational authority.",
      ),
      step(
        ELSEWHERE,
        "What else would the dye report as signal?",
        "Primer-dimer and off-target products are fluorescent too. Challenge the pair against relevant background and interpret in-silico specificity as a prerequisite for, not a substitute for, melt-curve and control evidence.",
      ),
      step(
        VALIDATION,
        "What experimental evidence says this dye-qPCR assay is quantitative?",
        "Record standard-curve points or summary statistics, efficiency, linearity, replicate behaviour, NTC and no-RT controls where applicable, and melt-curve evidence. PCRStudio keeps these MIQE-style observations separate from sequence ranking and reports missing evidence rather than fabricating validation.",
        { title: "MIQE validation", icon: Microscope },
      ),
      step(
        LAST_LOOK,
        "The assay, before you call a plate quantitative",
        "Review design specificity, chemistry, melt/control evidence and quantitative-performance evidence together. A well-designed primer pair is not itself a validated qPCR assay.",
      ),
    ],
  },

  "qpcr-probe": {
    steps: [
      step(
        SEQUENCE,
        "What target will this hydrolysis-probe assay quantify?",
        "Provide the exact target/transcript context used by the executable conventional hydrolysis-probe branch. Transcript identity and genomic-DNA avoidance remain explicit assay inputs when applicable.",
      ),
      step(
        ASSAY_DESIGN,
        "Which probe chemistry defines the executable assay envelope?",
        "Conventional Thermo Fisher and IDT hydrolysis-probe profiles are executable under their own source-backed rules. MGB/NFQ exact-Tm ranking uses the explicit external-authority exchange: PCRStudio exports hash-bound candidates and accepts only provenance-complete MGB-aware results.",
        { title: "Probe design", icon: Crosshair },
      ),
      step(
        NUMBERS,
        "What must be true of primers and probe?",
        "Primer and probe constraints are evaluated under the selected chemistry profile and same-reaction thermodynamic context; vendor rules and PCRStudio search envelopes remain separate authorities.",
      ),
      step(
        TUBE,
        "What chemistry generates probe signal?",
        "A hydrolysis-probe reaction requires compatible polymerase activity plus explicit reporter/quencher identities. PCRStudio does not substitute an intercalating-dye master mix or silently approximate an unsupported modified-probe model.",
      ),
      step(
        ELSEWHERE,
        "What else could satisfy primers and probe together?",
        "Amplicon specificity, probe-binding specificity and combined fluorescent-signal specificity are reported separately. Multiplex optical/interaction evidence is not upgraded beyond what the supplied panel data can actually validate.",
      ),
      step(
        LAST_LOOK,
        "Chemistry and evidence boundary",
        "Confirm the selected conventional hydrolysis-probe authority is executable and provenance-complete. MGB/NFQ exact-Tm ranking remains external-authority-required; imported results must match the exported candidate-set hash. Multiplex and MIQE evidence remain diagnostic/observational rather than silently changing sequence ranking.",
      ),
    ],
  },

  "digital-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What are you counting, and is the template physically linked?",
        "Current Gen-1 execution covers dye/EvaGreen digital PCR. Record target and fragmentation state explicitly because physically linked or high-molecular-weight material can change partition occupancy without changing primer sequence quality.",
        { title: "Target & fragmentation", icon: Target },
      ),
      step(
        NUMBERS,
        "What has to be true of the dye-dPCR amplicon?",
        "The sequence design favours short amplicons and a closely matched pair. Those properties support endpoint amplification but do not determine partition acceptance, threshold placement, rain or concentration uncertainty.",
        { title: "Assay design", icon: SlidersHorizontal },
      ),
      step(
        TUBE,
        "Which platform, partition format and dye chemistry define the run?",
        "Instrument identity, partition format and named EvaGreen/dye chemistry are acquisition provenance. They remain separate from primer thermodynamics and must be recorded before any partition-level interpretation is treated as comparable.",
        { title: "Platform & partitions", icon: Beaker },
      ),
      step(
        ELSEWHERE,
        "What else could create a positive partition?",
        "An off-target product can create a positive endpoint partition and bias counting. Sequence specificity is therefore necessary even though the actual positive/negative clusters and threshold remain measured-run evidence.",
      ),
      step(
        VALIDATION,
        "What does the partitioned run itself show?",
        "Record total and accepted partitions, positive and negative counts, ambiguous/rain handling, threshold method, controls, dilution and run metadata. Where counts are supplied, PCRStudio can report occupancy and a Poisson concentration estimate while preserving platform-volume authority and measured-run limitations.",
        { title: "Run QC / dMIQE", icon: Microscope },
      ),
      step(
        LAST_LOOK,
        "The dye-dPCR assay, before you interpret concentration",
        "Review primer specificity, fragmentation, platform identity, partition QC, threshold method and controls together. Current Gen-1 does not claim probe/channel-aware dPCR and does not infer missing partition-volume authority.",
      ),
    ],
  },

  /* ── Genotype a variant ──────────────────────────────────────────────── */

  "arms-pcr": {
    steps: [
      step(
        SEQUENCE,
        "Which template contains the variant to genotype?",
        "Provide the sequence and any known neighbouring variation. The exact interrogated base and alleles are defined on Design so biological input and allele-specific geometry are not collapsed into one page.",
      ),
      step(
        ASSAY_DESIGN,
        "Which base and two alleles define the two-tube ARMS assay?",
        "Anchor the terminal mismatch on the variant and let the fixed ARMS geometry own the two allele-specific reactions. A second deliberate mismatch is evaluated as evidence, not assumed universally useful.",
        { title: "Allele design", icon: Crosshair },
      ),
      step(
        NUMBERS,
        "What search envelope should the allele-specific and common primers satisfy?",
        "Constraints guide candidate generation while preserving the variant at the allele-specific 3′ end; they never move the discriminating base to improve a generic primer score.",
      ),
      step(
        TUBE,
        "Which mismatch-compatible amplification context will run the two reactions?",
        "Terminal-mismatch discrimination depends on polymerase behaviour. The executable branch keeps a non-proofreading context rather than silently replacing it with a 3′-exonuclease-positive enzyme.",
      ),
      step(
        ELSEWHERE,
        "Which other locus could imitate one of the two alleles?",
        "A paralogue or homoeologue with the same terminal base can look like a real genotype. Background specificity is therefore part of genotyping validity, not only band cleanliness.",
      ),
      step(
        LAST_LOOK,
        "The two allele reactions, before you order them",
        "Review variant identity, fixed ARMS geometry, mismatch evidence, common-primer specificity and the reaction context together.",
      ),
    ],
  },

  kasp: {
    steps: [
      step(
        SEQUENCE,
        "Which template contains the SNP to genotype by endpoint fluorescence?",
        "Provide the locus and known nearby variation first. Fluorescent tails and endpoint readout are assay architecture, not part of the biological target sequence.",
      ),
      step(
        ASSAY_DESIGN,
        "Which base and alleles feed the fixed KASP geometry?",
        "Define the SNP while PCRStudio fixes the competitive allele-specific geometry and keeps reporter tails outside annealing thermodynamics.",
        { title: "KASP design", icon: Crosshair },
      ),
      step(
        NUMBERS,
        "What search envelope should the annealing portions satisfy?",
        "Only target-binding portions participate in Primer3 thermodynamics; universal reporter tails belong to the ordered oligo and endpoint chemistry.",
      ),
      step(
        TUBE,
        "Which KASP protocol, plate and instrument will read the endpoint clusters?",
        "Protocol, plate volume, instrument and ROX policy are run provenance. They are not allowed to change which allele base the design interrogates.",
        { title: "KASP reaction", icon: Beaker },
      ),
      step(
        ELSEWHERE,
        "Which other locus could enter either fluorescent cluster?",
        "A homoeologue or paralogue can create an apparently clean endpoint genotype. Challenge the common and allele-specific binding sites against relevant backgrounds before trusting cluster separation.",
      ),
      step(
        LAST_LOOK,
        "The tailed KASP oligos and readout context",
        "Check allele-to-tail identity, annealing-part Tm, protocol/plate/instrument provenance and specificity together. Plus/minus presence–absence remains a separate non-executable branch.",
      ),
    ],
  },

  "tetra-primer-arms": {
    steps: [
      step(
        SEQUENCE,
        "Which template carries the variant that three gel bands must distinguish?",
        "Provide the locus and nearby variation. The SNP and four-primer geometry are defined on Design; electrophoresis resolution is validation/readout context.",
      ),
      step(
        ASSAY_DESIGN,
        "Which base and alleles anchor the four-primer architecture?",
        "Two inner allele-specific and two outer primers are designed as one coupled assay. The module identity fixes tetra geometry so it can never silently fall back to two-tube ARMS.",
        { title: "Tetra design", icon: Crosshair },
      ),
      step(
        NUMBERS,
        "What must four primers sharing one tube satisfy?",
        "The shared thermal window and product geometry are constrained together; the two allele-specific products and outer control must remain interpretable as one assay.",
      ),
      step(
        TUBE,
        "Which mismatch-compatible one-tube context will amplify all four primers?",
        "Primer balance and polymerase behaviour are bench-protocol properties. PCRStudio keeps them distinct from the required electrophoresis resolution evidence.",
      ),
      step(
        ELSEWHERE,
        "What extra products could appear beside the three diagnostic bands?",
        "Four primers create more possible off-target combinations, so background specificity is interpreted against the same gel used to call the genotype.",
      ),
      step(
        VALIDATION,
        "Can the intended readout resolve the three diagnostic bands?",
        "Enter the minimum band separation your validated gel or capillary workflow can resolve. PCRStudio compares predicted product sizes to that declared capability instead of inventing a universal agarose threshold.",
        { title: "Band resolution", icon: Microscope },
      ),
      step(
        LAST_LOOK,
        "Three band sizes, before you order four primers",
        "Review allele identity, three predicted products, declared readout resolution, specificity and reaction context together.",
      ),
    ],
  },

  /* ── Detect an organism ──────────────────────────────────────────────── */

  "species-specific-pcr": {
    steps: [
      step(
        SEQUENCE,
        "What biological entity must this assay detect?",
        "Provide the target sequence and preserve accession/version, isolate or strain and taxonomy context. Species-specific design starts with a positive biological claim, not merely a convenient reference sequence.",
      ),
      step(
        NUMBERS,
        "What has to be true of a discriminating pair?",
        "The reviewed profile does not force a generic 3-prime clamp because the informative difference has to remain where the biology places it. Search constraints support candidate generation; inclusivity and exclusivity define whether the assay is actually species-specific.",
      ),
      step(
        TUBE,
        "What reaction context will carry the discrimination?",
        "Record the computational and bench reaction context without pretending chemistry can rescue an assay whose primers also match the nearest biological neighbours.",
      ),
      step(
        ELSEWHERE,
        "Which targets must amplify, and which neighbours must stay silent?",
        "Build explicit must-amplify and must-not-amplify panels with provenance and a selection rationale. This workspace is part of the assay definition: target diversity, nearest taxa, likely co-occurring organisms and database/release identity determine the scope of the specificity claim.",
        { title: "Inclusivity & exclusivity", icon: ScanSearch },
      ),
      step(
        LAST_LOOK,
        "The biological claim, before you trust a band",
        "Review panel provenance, inclusivity coverage, exclusivity evidence and unresolved biological gaps with the pair itself. A band becomes an identification claim only inside the panel scope that was actually tested.",
      ),
    ],
  },

  rpa: {
    steps: [
      step(
        SEQUENCE,
        "What are you detecting?",
        "RPA uses recombinase-driven strand invasion rather than thermal denaturation. Primer Tm remains only a broad sequence-screening guard, not a PCR annealing-temperature model or a validated predictor of RPA performance.",
      ),
      step(
        NUMBERS,
        "What candidate envelope will you screen experimentally?",
        "The reviewed starting branch uses long RPA primers and broad sequence guards. The purpose of computational design is to produce a defensible candidate pool, not to collapse uncertain RPA kinetics into a false single best score.",
      ),
      step(
        TUBE,
        "Which executable basic chemistry and held-temperature protocol will you use?",
        "Gen-1 executes the reviewed Basic/Liquid Basic/Lyo-ready branches. Exo, Nfo and Fpg detection require modified-probe architectures and remain outside this plain-primer workflow rather than being represented by an ordinary third DNA oligo.",
        { title: "Reaction", icon: Thermometer },
      ),
      step(
        ELSEWHERE,
        "What else could a recombinase invade?",
        "Mismatch tolerance can help target variation and hurt exclusivity at the same time. Challenge candidates against biologically relevant backgrounds and keep in-silico evidence separate from empirical screening performance.",
      ),
      step(
        VALIDATION,
        "How will candidate pairs be screened rather than merely ranked?",
        "Define a candidate panel, replicates, controls and the experimental response you will record — for example time-to-positive, endpoint signal or detection at a stated input. PCRStudio records screening outcomes and selection rationale without converting them into an unsupported universal RPA performance model.",
        { title: "Candidate screening", icon: Microscope },
      ),
      step(
        LAST_LOOK,
        "The candidate panel, before you order and screen it",
        "Review lengths, specificity, chemistry and the screening plan together. A computationally favoured RPA pair remains a candidate until empirical performance and controls support selection.",
      ),
    ],
  },

  lamp: {
    steps: [
      step(
        SEQUENCE,
        "What target or target panel must the LAMP assay recognise?",
        "Start with sequence identity, DNA versus RNA/RT-LAMP context, target window and panel scope. LAMP topology and six-region geometry are designed on the next page rather than being mixed with biological input or bench chemistry.",
      ),
      step(
        ASSAY_DESIGN,
        "How should the six core LAMP regions form one ordered set?",
        "Design or evaluate F3/B3, F2/B2 and F1c/B1c as a coupled topology, with optional LF/LB, explicit PrimerExplorer V5 public-rule or evidence geometry, FIP/BIP linker semantics and advanced windows. Composite inner primers are checked as complete oligos as well as by their target-binding segments.",
        { title: "LAMP design", icon: Crosshair },
      ),
      step(
        TUBE,
        "Which strand-displacing kit, held-temperature protocol and readout will run the set?",
        "Bench protocol, RT capability, UDG/carry-over branch and fluorescence, colour or turbidity readout are reaction provenance. Kit compatibility is enforced independently from sequence ranking so an incompatible readout cannot be hidden by a good geometry score.",
        { title: "Reaction & readout", icon: Thermometer },
      ),
      step(
        ELSEWHERE,
        "Which targets must be covered, and which neighbours must not form a compatible LAMP locus?",
        "When a target panel is supplied, MAFFT becomes the conditional primary alignment authority for inclusivity. Specificity then challenges coordinated LAMP binding geometry against supplied backgrounds; multiple binding regions improve evidence but do not make exclusivity automatic.",
        { title: "Specificity & coverage", icon: ScanSearch },
      ),
      step(
        VALIDATION,
        "How will complete LAMP sets be screened experimentally?",
        "Plan multiple complete candidate sets, NTCs, replicates, target input levels and a measured response such as time-to-positive or endpoint readout. Record non-template amplification and LoD evidence without allowing bench observations to silently rewrite the in-silico ranking model.",
        { title: "Validation plan", icon: Microscope },
      ),
      step(
        LAST_LOOK,
        "The complete LAMP assay, before you order it",
        "Review F3/B3/FIP/BIP and optional LF/LB supplier-ready sequences, geometry, inclusivity/exclusivity evidence, kit/readout compatibility and the experimental validation plan together. Design software selects candidates; it does not confer wet-lab validation.",
        { title: "Review & order", icon: ListChecks },
      ),
    ],
  },

  "universal-primers": {
    steps: [
      step(
        SEQUENCE,
        "Which sequence family must one degenerate pair cover?",
        "Provide multiple sequences or a reviewed alignment. The panel itself is biological input; alignment authority and degeneracy design belong on the next page.",
        { title: "Panel", icon: Waypoints },
      ),
      step(
        ASSAY_DESIGN,
        "How should the panel be aligned before conserved windows are searched?",
        "Choose the MAFFT-first auto policy or preserve a reviewed alignment. PCRStudio records the authority because changing alignment columns changes the biological meaning of conservation.",
        { title: "Alignment & design", icon: Waypoints },
      ),
      step(
        NUMBERS,
        "What degeneracy and thermodynamic envelope should the consensus pair satisfy?",
        "The reviewed search profile bounds degeneracy, Tm spread and candidate quality. It is a transparent Gen-1 policy rather than a claim that one degenerate mixture is universally optimal.",
      ),
      step(
        TUBE,
        "What does a degenerate oligo concentration mean in the actual tube?",
        "A degenerate sequence represents multiple molecules, so nominal concentration is divided across variants. Synthesis proportions and working concentration remain supplier/assay evidence.",
      ),
      step(
        LAST_LOOK,
        "Coverage and degeneracy, before you order the pool",
        "Review member coverage, expansion count, Tm spread, tails and unresolved panel gaps together. One consensus sequence is not the same thing as proof of universal amplification.",
      ),
    ],
  },

  /* ── Sequence a genome ───────────────────────────────────────────────── */

  "sequencing-primer": {
    steps: [
      step(
        SEQUENCE,
        "Which region must be readable from this template?",
        "Provide the template and interval that must fall inside the usable trace. Direction, dead zone and read length are placement geometry and therefore live on Design.",
      ),
      step(
        ASSAY_DESIGN,
        "From which side can the provider's usable read window cover the target?",
        "Choose direction and the provider/SOP read envelope. PCRStudio places one primer from those explicit values and does not assume a universal 40/800-base trace.",
        { title: "Read design", icon: Microscope },
      ),
      step(
        NUMBERS,
        "What must be true of the single sequencing primer?",
        "There is no pair to balance. Candidate quality is judged for one oligo under the selected screening context and against the requested readable interval.",
      ),
      step(
        TUBE,
        "Which capillary instrument, facility SOP and cycle-sequencing chemistry receive it?",
        "Instrument and chemistry are handoff provenance; they do not rewrite the read geometry or claim a successful trace before sequencing occurs.",
        { title: "Provider & reaction", icon: Beaker },
      ),
      step(
        ELSEWHERE,
        "Could this single primer start more than one trace?",
        "A second binding site produces superimposed sequence rather than a neat extra band. Background specificity is therefore a direct trace-quality prerequisite.",
      ),
      step(
        LAST_LOOK,
        "The primer and provider handoff, before you send the sample",
        "Review direction, target coverage by the declared read window, specificity, instrument/SOP and chemistry together.",
      ),
    ],
  },

  race: {
    steps: [
      step(
        SEQUENCE,
        "What known transcript sequence contains the gene-specific primer search region?",
        "Provide the known sequence and the interval from which the GSP may be selected. The transcript end being chased is design direction, while adapter/substrate provenance belongs on Reaction.",
        { title: "Known sequence", icon: Target },
      ),
      step(
        ASSAY_DESIGN,
        "Which transcript end must the GSP read toward?",
        "Choose 5′ or 3′ RACE explicitly. The engine maps that biological direction to the only primer orientation that can extend toward the unknown transcript end.",
        { title: "RACE direction", icon: Radar },
      ),
      step(
        NUMBERS,
        "What must the gene-specific primer satisfy?",
        "The GSP is designed to work with a kit/supplied partner rather than a second genomic primer. Its thermal envelope remains transparent and separate from adapter identity.",
      ),
      step(
        TUBE,
        "Which substrate, preparation, partner primer and amplification round are actually in the RACE workflow?",
        "RACE substrate, RT/cDNA preparation, adapter authority and primary versus nested round are required reaction provenance and are never guessed from sequence.",
        { title: "RACE reaction", icon: Beaker },
      ),
      step(
        ELSEWHERE,
        "Could the GSP sit in a paralogue or another transcript?",
        "A clean RACE product can still be the wrong gene. Challenge the gene-specific binding sequence against relevant backgrounds before interpreting an unknown end.",
      ),
      step(
        LAST_LOOK,
        "Direction, partner and gene specificity, before you order the GSP",
        "Confirm the primer reads toward the intended transcript end and the exact partner/provenance used in the tube is the one against which it was screened.",
      ),
    ],
  },

  "tiled-scheme": {
    steps: [
      step(
        SEQUENCE,
        "Which reference or sequence panel must the scheme cover?",
        "Provide the genome or panel only. Lifecycle operation, alignment authority, imported scheme artifacts and pool geometry are separate decisions and no longer live on the biological-input page.",
        { title: "Genome / panel", icon: Blocks },
      ),
      step(
        STRATEGY,
        "Are you creating, extending, repairing or replacing part of a scheme?",
        "Choose the PrimalScheme3 lifecycle operation, alignment authority and any versioned BED/config inputs. Maintenance must remain traceable to the exact scheme being modified.",
        { title: "Lifecycle", icon: Radar },
      ),
      step(
        ASSAY_DESIGN,
        "What scheme geometry does this lifecycle operation actually accept?",
        "New schemes expose overlap; bounded panels expose panel allocation. Repair/replacement inherit geometry from imported artifacts rather than collecting values the command would ignore.",
        { title: "Scheme design", icon: SlidersHorizontal },
      ),
      step(
        NUMBERS,
        "What must every primer pair satisfy across the whole scheme?",
        "Thermal and oligo constraints are global search envelopes. They stay separate from PrimalScheme3 lifecycle inputs and pool count.",
      ),
      step(
        TUBE,
        "How many multiplex pools will carry overlapping amplicons?",
        "Pool count belongs to create/panel run topology. Repair and replacement inherit pool identity from the reviewed scheme rather than accepting an inert new number.",
        { title: "Pools", icon: Blocks },
      ),
      step(
        LAST_LOOK,
        "Coverage, pools and lifecycle provenance before you order a plate",
        "Review gaps, interaction evidence, imported-artifact hashes, operation history and pool assignment together. A repaired scheme must be reproducible from the BED/config that produced it.",
      ),
    ],
  },

  /* ── Clone or assemble ───────────────────────────────────────────────── */

  "restriction-cloning": {
    steps: [
      step(
        SEQUENCE,
        "What insert will be amplified into the construct?",
        "Provide the exact linear insert sequence that the annealing halves must amplify. Donor-plasmid extraction is not inferred: if the insert came from a larger construct, the sequence supplied here remains the explicit PCR template for Gen-1.",
      ),
      step(
        VECTOR,
        "Which vector and restriction ends define the construct?",
        "Provide the recipient vector sequence and select the reviewed forward and reverse enzymes. PCRStudio checks recognition-site occurrence in insert and vector, end compatibility and directionality at sequence level while keeping methylation sensitivity, star activity and supplier buffer/heat-inactivation behaviour as bounded bench authority rather than guessed facts.",
      ),
      step(
        ASSAY_DESIGN,
        "What annealing halves and 5-prime restriction tails should be ordered?",
        "Protective bases and recognition sites belong to the ordered oligo but stay outside the annealing thermodynamics. Primer design and tail construction therefore remain explicit layers, with the full supplier-ready oligo retained for downstream digest/ligation simulation.",
        { title: "Primer / tail design", icon: Crosshair },
      ),
      step(
        TUBE,
        "Which proofreading PCR context will create the insert product?",
        "Every retained base can enter the final plasmid, so amplification chemistry and sequence provenance matter independently from the restriction digest. The bench chemistry is recorded without silently changing enzyme-site or ligation logic.",
      ),
      step(
        ELSEWHERE,
        "What else could the annealing halves amplify before cloning?",
        "The synthetic restriction tails are absent from template, so specificity is assessed on the annealing halves. Off-target amplification matters more here because an unintended product can be digested and ligated along with the intended insert.",
      ),
      step(
        CONSTRUCT,
        "Does the selected digest and ligation produce the intended circular construct?",
        "When pydna/Biopython support and complete vector/enzyme inputs are available, PCRStudio independently simulates tailed PCR, restriction digest and ligation and reports construct count, size, orientation and sequence hash. Missing or unsupported enzyme semantics remain explicitly unresolved rather than being approximated.",
        { title: "Construct simulation", icon: Blocks },
      ),
      step(
        LAST_LOOK,
        "The insert, vector, ends and simulated construct before you order",
        "Review internal sites, end compatibility, directionality, supplier-ready oligos, PCR specificity and simulation status together. Sequence simulation does not substitute for methylation, star-activity, digestion-efficiency or ligation controls that belong to the bench protocol.",
      ),
    ],
  },

  "gibson-assembly": {
    steps: [
      step(
        ASSAY_DESIGN,
        "In what order and topology should the fragments join?",
        "Enter amplified, fixed or literal fragments in order and choose linear versus circular topology. Each overlap is derived from the adjacent fragments under the reviewed Gibson branch.",
        { title: "Assembly design", icon: Blocks },
      ),
      step(
        NUMBERS,
        "What must the annealing halves of amplified-fragment primers satisfy?",
        "Primer3 constraints apply to the target-binding halves; Gibson overlap tails follow from junction geometry and remain outside annealing thermodynamics.",
      ),
      step(
        TUBE,
        "Which PCR and Gibson reaction authorities create and join the fragments?",
        "Each amplified piece has a proofreading PCR context; joining chemistry is the pinned NEB E5510 Gibson branch. Other assembly chemistries are not silently substituted.",
        { title: "Reactions", icon: FlaskConical },
      ),
      step(
        CONSTRUCT,
        "Does the ordered plan close into the intended construct?",
        "Preflight the fragment order, junction count and topology before ordering. Result-level junction sequences and construct identity remain outputs of the actual design run.",
        { title: "Construct", icon: Blocks },
      ),
      step(
        LAST_LOOK,
        "Every junction and oligo before you order the assembly",
        "Review fragment order, circular closure, overlap lengths, supplier-ready oligos and construct topology together. Internal construct-uniqueness checks are part of the assembly engine rather than an unrelated background-genome tab.",
      ),
    ],
  },

  /* ── Engineer a change ───────────────────────────────────────────────── */

  "site-directed-mutagenesis": {
    steps: [
      step(
        SEQUENCE,
        "Which exact plasmid will be edited?",
        "Provide the complete plasmid sequence. The edit itself is a design instruction, not a target interval, so it is defined on the next page and never moved for primer convenience.",
      ),
      step(
        ASSAY_DESIGN,
        "What exact substitution, insertion or deletion must the back-to-back pair create?",
        "Define edit kind, coordinate and replacement sequence under the executable Q5 topology. Unsupported large split-tail insertions fail closed rather than being approximated.",
        { title: "Edit design", icon: Scissors },
      ),
      step(
        TUBE,
        "Which amplification and KLD recovery workflow owns the edit?",
        "Generation 1 is explicitly the NEB Q5/E0554 branch. Reaction records that chemistry separately from the edit identity so a kit choice can never redefine the intended molecule.",
        { title: "Q5 & KLD", icon: Beaker },
      ),
      step(
        CONSTRUCT,
        "What sequence should exist after the requested edit?",
        "Preview the edited plasmid length and local sequence before running design. This construct preview checks the user instruction; it does not claim transformation or colony validation.",
        { title: "Edited construct", icon: Blocks },
      ),
      step(
        LAST_LOOK,
        "The exact edit and edited construct before you order the pair",
        "Confirm original sequence, coordinate frame, inserted/replaced/deleted bases, Q5/KLD branch and expected edited molecule together.",
      ),
    ],
  },
};

/* ── What an assay this build has not planned for gets ──────────────────── */

/**
 * The plan for one assay.
 *
 * An assay with no plan is a release error. Falling back to Standard PCR would
 * silently ask the wrong scientific questions and can manufacture an invalid
 * request. `isPlanned` exists beside this lookup and the registry tests require
 * every released module to have its own plan.
 */
export function planFor(moduleId: string): PagePlan {
  const plan = PLANS[moduleId];
  if (!plan) {
    throw new Error(
      `No assay-specific design page exists for ${moduleId}. PCRStudio will not fall back to Standard PCR for an unknown module.`,
    );
  }
  const generated = (capabilities.modules as Record<string, Omit<PagePlan, "steps">>)[moduleId];
  if (!generated) {
    throw new Error(`No generated page capability contract exists for ${moduleId}.`);
  }
  return { ...generated, steps: plan.steps };
}

/** Whether this assay has a page of its own, for a test to assert against. */
export function isPlanned(moduleId: string): boolean {
  return moduleId in PLANS;
}

/** Every assay with a plan, so a test can compare against the registry. */
export function plannedModules(): string[] {
  return Object.keys(PLANS);
}
