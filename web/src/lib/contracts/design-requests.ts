import { MODULE_BINDINGS, type EngineFor, type ModuleId } from "./module-bindings.generated";
import type {
  ColonyHostClass,
  ColonyPreparation,
  DigitalConsumableId,
  DigitalPlatformId,
  QpcrInstrumentProfile,
} from "../flanking-protocol-authority.generated";
import type {
  LampProtocolId,
  LampReadout,
  LampReadoutChemistry,
  LampFormulation,
  LampDesignIntent,
  LampLoopPolicy,
  LampDesignStage,
  LampMutationAnchor,
} from "../lamp-protocol-authority.generated";

export interface ModifiedOligoSpec {
  role: string;
  sequence?: string;
  fivePrimeLabel?: string;
  threePrimeBlock?: string;
  fluorophore?: string;
  quencher?: string;
  affinityLabel?: string;
  lateralFlowLabel?: string;
  cleavageSite?: number;
  manufacturerNotes?: string;
  internalModifications?: Array<{
    kind: "thf" | "dSpacer" | "fluorophore" | "quencher" | "other-reviewed";
    position: number;
    identity?: string;
  }>;
}

export interface ProbeMultiplexTarget {
  target: string;
  reporter: string;
  quencher: string;
  internalQuencher?: string;
  channel?: string;
  forwardPrimer?: string;
  reversePrimer?: string;
  probeSequence?: string;
}

export interface DigitalMultiplexTarget {
  target: string;
  reporter?: string;
  channel?: string;
  amplitudeClass?: string;
  primerEachNm?: number;
  probeNm?: number;
}

export interface DesignPayload {
  /** Manufacturing/readout annotations only; topology execution remains separately versioned and fail-closed. */
  modifiedOligos?: ModifiedOligoSpec[];
  /**
   * The sequence to design against — for the engines that have one.
   *
   * Optional because `junction-primers` does not: an assembly is described by
   * its segments, and that engine has no `template` field at all. It was
   * required here, so the client sent `template: ""` and every Gibson design
   * came back `unknown field \`template\``.
   */
  template?: string;
  /** Explicit semantics for lowercase sequence letters; never inferred from a percentage. */
  lowercaseMasking?: boolean;
  name?: string;
  polymerase?: string;
  /** What the product is for, which sets the sizes before anything is typed. */
  purpose?: string;
  /** Regions no primer may overlap, as `[start, length]` pairs. */
  excluded?: [number, number][];
  /**
   * Positions the template is known to be polymorphic at, counted from zero.
   *
   * Scientific-Strict treats every supplied polymorphic coordinate as excluded
   * from primer placement unless richer allele/frequency/chemistry evidence is
   * supplied by a separately versioned assay model.
   */
  variants?: number[];
  background?: string;
  /** FASTA records of intended target strains/variants for species-specific inclusivity. */
  inclusivity?: string;
  /** Database/release/isolate provenance for the intended-target inclusivity panel. */
  inclusivityPanelProvenance?: string;
  /** Database/release/isolate provenance for the near-neighbour exclusion panel. */
  backgroundPanelProvenance?: string;
  /** Why these intended targets and near neighbours represent the biological claim. */
  speciesPanelSelectionRationale?: string;
  /** Declared NCBI Taxonomy identifier for the intended target scope. */
  speciesTargetTaxid?: number;
  /** Pinned taxonomy authority/release/date used when the panel was curated. */
  speciesTaxonomySnapshot?: string;
  /** Pinned sequence database/release used to curate the panel. */
  speciesDatabaseSnapshot?: string;
  /** Accession.version manifest for the reviewed inclusivity/exclusivity panel. */
  speciesPanelAccessionManifest?: string;
  speciesPanelAccessionAuthorityManifest?: string;
  /** Per-FASTA-record accession, role, topology and optional population-evidence metadata. */
  speciesPanelRecordMetadataManifest?: string;
  /** ISO YYYY-MM-DD retrieval/review date for the pinned panel snapshot. */
  speciesPanelRetrievedDate?: string;
  /** Whole-primer mismatch budget for specificity-v5 discovery. */
  maxMismatches?: number;
  howMany?: number;
  targetStart?: number;
  targetLength?: number;
  constraints?: Record<string, number>;
  /**
   * Low-level reaction-condition transport.
   *
   * Current Scientific-Strict browser flows do not expose anonymous chemistry
   * overrides: changing salt/Mg/dNTP/oligo concentration changes the reviewed
   * thermodynamic context and requires a named/versioned chemistry profile. The
   * core retains this field for typed low-level validation, but the current UI
   * does not synthesize or restore it through hidden draft state.
   */
  conditions?: Record<string, number>;
  /**
   * Whether the tube starts from RNA.
   *
   * Only sent for assays whose profile declares the reverse-transcription
   * modifier — eight of them, none of which could say so before.
   */
  fromRna?: boolean;
  /**
   * Zero-based boundaries between transcript bases. When supplied to the
   * flanking-pair engine, at least one primer in each returned pair must
   * cross one boundary; this is an annotation, not an inferred property.
   */
  exonJunctions?: number[];

  /** Experimental workflow evidence persisted with the run but excluded from sequence ranking. */
  workflowEvidence?: Record<string, string | number | boolean | null>;
  /** Recipient vector for the exact-insert restriction-cloning branch. */
  cloningVector?: string;
  cloningVectorName?: string;
  cloningVectorTopology?: "circular";
  /** Source-conditioned restriction digest workflow authority. */
  restrictionDigestProtocol?:
    "neb-cutsmart-standard" | "neb-cutsmart-timesaver" | "thermo-fastdigest-universal";
  /** Explicit vector dephosphorylation workflow; `none` records deliberate omission. */
  restrictionDephosphorylationProtocol?: "none" | "neb-quick-cip-m0525";
  /** Source-conditioned ligation workflow authority. */
  restrictionLigationProtocol?: "neb-t4-dna-ligase-m0202" | "neb-quick-ligation-m2200";
  /** Coding/fusion semantics for restriction cloning; provenance/validation only. */
  cloningCodingIntent?: "noncoding" | "preserve-orf" | "in-frame-fusion";
  cloningCdsStart?: number;
  cloningCdsEnd?: number;
  cloningStopCodonPolicy?: "not-applicable" | "preserve" | "remove";
  cloningFusionTag?: string;
  cloningLinkerAa?: string;
  cloningVectorJunctionFrame?: 0 | 1 | 2;

  /**
   * What goes on the 5' end of every oligo.
   *
   * One wire name and two shapes, because three assays mean two different
   * things by it and each engine's own request struct accepts only its own.
   *
   * Restriction cloning names two enzymes and the worker builds the sites: the
   * two must differ or the insert goes into the vector either way round, and
   * neither may occur inside the insert.
   *
   * A tiled scheme and a degenerate pair give the bases themselves — a
   * sequencing adapter, an M13 tail — because which one belongs there is fixed
   * by what happens after the PCR and is not derivable from a template.
   */
  tails?:
    | {
        tailProtocol?: "neb-general-6bp";
        forwardEnzyme?: string;
        reverseEnzyme?: string;
        protectiveBases?: number;
        forwardProtectiveSequence?: string;
        reverseProtectiveSequence?: string;
      }
    | {
        forward?: string;
        reverse?: string;
      };
  /**
   * The primer already on the bench to pair one insert primer against.
   *
   * Only colony screening fills this in. A name from the catalogue, or the
   * bases themselves for one this build has never heard of — a cloning bench
   * is full of primers that predate any catalogue.
   */
  /** Colony-PCR host class; required for crude-template interpretation. */
  colonyHostClass?: ColonyHostClass;
  /** Colony material preparation branch. */
  colonyPreparation?: ColonyPreparation;
  /** Exact source-backed colony-PCR workflow, or custom-sop for a local/lab protocol. */
  colonyProtocolId?:
    | "custom-sop"
    | "neb-onetaq-m0482-colony"
    | "neb-onetaq-hotstart-m0488-colony"
    | "neb-insert-screening-e1202"
    | "pcrbio-hs-taq-pb10-22-colony"
    | "neb-onetaq-m0689-colony";
  /** Custom SOP identity; required only for colonyProtocolId=custom-sop. */
  colonyProtocolName?: string;
  colonyProtocolProvenance?: string;

  vectorPrimer?: {
    name?: string;
    sequence?: string;
    readsInto?: string;
    howMany?: number;
    /**
     * The plasmid, linearised where the insert goes in.
     *
     * What it buys is the product size. Every colony screen this build ever
     * produced reported its product as unknown, because the distance from the
     * vector primer to the cloning site belongs to a molecule the worker had
     * never seen — and that is the one number somebody holds a gel against.
     */
    vector?: string;
  };

  /* Standard Gen-1 two-flank inverse-PCR preparation. The complete submitted
     sequence is the intact known anchor; internal cut coordinates and one-sided
     selectors are not part of the current request surface. */
  circleLength?: number;
  enzyme?: string;
  inverseBranch?: "restriction-self-ligation" | "supplied-circular-template" | "unresolved";
  enzymeCohortSize?: number;
  inverseReferenceSequence?: string;
  inverseReferenceCircular?: boolean;
  inverseCandidateEnzymes?: string[];
  mappingUseCase?: "generic-flank" | "transposon-insertion" | "integration-site";
  leftEndPhosphate?: "phosphorylated" | "unphosphorylated" | "unresolved";
  rightEndPhosphate?: "phosphorylated" | "unphosphorylated" | "unresolved";
  circularizationProvenance?: string;
  linearControlProvenance?: string;
  methylationBranch?: string;
  unknownFlankMin?: number;
  unknownFlankMax?: number;

  /* The probe engine designs a third oligo whose window is not the primers'
     with different numbers — it melts above them rather than alongside.
     Nested keys are worker-facing snake_case (`tm_min`, `length_max`, ...);
     top-level camelCase does not apply inside this record. */
  probe?: Record<string, number>;
  /** Explicit named hydrolysis-probe chemistry authority. */
  probeProtocol?:
    | "thermofisher-taqman-conventional"
    | "idt-primetime-conventional"
    | "taqman-mgb-reference"
    | "taqman-mgb";
  probeChemistry?: "conventional-hydrolysis" | "double-quenched-hydrolysis" | "mgb-nfq";
  probeReporter?: string;
  probeQuencher?: string;
  probeInternalQuencher?: string;
  probeInstrumentProfile?: string;
  probeOpticalAuthorityPayload?: Record<string, unknown>;
  probeMgbAuthorityMode?: "export-candidates" | "import-results";
  probeMgbAuthorityPayload?: Record<string, unknown>;
  probeTranscriptMode?: "generic" | "exon-junction" | "exon-spanning" | "transcript-specific";
  probeTranscriptJunctions?: number[];
  probeVariantPositions?: number[];
  probeMultiplexPanel?: ProbeMultiplexTarget[];
  /** Optional named Standard-PCR bench chemistry. It does not change Primer3 ranking. */
  standardPcrProtocol?:
    | "not-selected"
    | "neb-taq-m0273"
    | "neb-q5-hot-start-m0493"
    | "neb-q5u-hot-start-m0515"
    | "thermo-dreamtaq-hot-start-ep170x"
    | "thermo-phusion-plus"
    | "promega-gotaq-m300"
    | "thermo-platinum-superfi-ii"
    | "neb-onetaq-hot-start-m0484"
    | "neb-onetaq-hot-start-gc-m0485"
    | "neb-onetaq-hot-start-quickload-m0488"
    | "neb-onetaq-hot-start-quickload-gc-m0489"
    | "pcrbio-hs-taq-mix-pb10-22"
    | "qiagen-alltaq-master-mix-203144"
    | "thermo-platinum-ii-taq-hot-start"
    | "toyobo-kod-one-kmm101"
    | "neb-multiplex-pcr-m0284";
  /** Explicit named intercalating-dye chemistry overlay for the qPCR/SYBR-compatible module. */
  qpcrProtocol?:
    | "not-selected"
    | "bio-rad-itaq-sybr"
    | "neb-luna-universal-m3003"
    | "neb-luna-one-step-rt-qpcr-e3005"
    | "thermo-powerup-sybr-a2574x"
    | "promega-gotaq-qpcr-a600x"
    | "promega-gotaq-one-step-rt-qpcr-a6020"
    | "thermo-powertrack-sybr-a46xxx"
    | "qiagen-quantinova-sybr-208052"
    | "bio-rad-ssoadvanced-sybr-172527x"
    | "solis-hot-firepol-evagreen-rox"
    | "solis-hot-firepol-evagreen-norox"
    | "solis-hot-firepol-evagreen-capillary"
    | "vazyme-q713-suprealq-ultra-hunter-sybr";
  /** Explicit named TwistAmp chemistry overlay for the RPA module. */
  rpaProtocol?:
    | "not-selected"
    | "twistamp-basic"
    | "twistamp-liquid-basic"
    | "thermo-lyo-ready-rpa"
    | "gbiosciences-rpa-786-2155"
    | "twistamp-exo"
    | "twistamp-nfo"
    | "twistamp-fpg"
    | "siba-reference";
  /** Explicit supported chemistry/protocol identity for long-range PCR. */
  longRangeProtocol?:
    | "not-selected"
    | "thermo-long-pcr-k018x"
    | "neb-longamp-taq-m0323"
    | "takara-primestar-gxl-r050a-standard"
    | "qiagen-ultrarun-longrange-206442-206444"
    | "neb-q5-xt-m2499"
    | "promega-gotaq-long-m4021"
    | "thermo-platinum-superfi-ii-longrange"
    | "toyobo-kod-long-kml101";
  /** Explicit named Bio-Rad EvaGreen overlay for the digital-PCR module. */
  digitalProtocol?:
    | "not-selected"
    | "bio-rad-qx200-evagreen"
    | "bio-rad-qx700-naica-evagreen"
    | "bio-rad-qx700-evagreen-supermix"
    | "qiagen-qiacuity-eg"
    | "qiagen-qiacuity-onestep-advanced-eg";
  /** Source-conditioned bench numeric context for flanking-pair modules.
   * This context is provenance/reaction planning only and never silently changes Primer3 ranking. */
  flankingNumericContext?: {
    reactionVolumeUl?: number;
    primerEachUm?: number;
    primerEachNm?: number;
    gcEnhancerPercent?: number;
    additive?: "none" | "high-gc-enhancer" | "yellow-sample-buffer";
    cyclingProfile?: "protocol-default" | "fast" | "standard";
    templateFractionPercent?: number;
    targetLengthKb?: number;
    partitionFormatDetail?: "not-specified" | "8.5k" | "26k";
    preparation?:
      | "protocol-default"
      | "direct-colony"
      | "direct-transfer"
      | "liquid-culture"
      | "water-lysate"
      | "buffer-lysate"
      | "host-specific-lysis"
      | "other";
    initialDenaturationTimeMin?: number;
    /** Thermo Lyo-ready RPA reviewed temperature window; bench-only. */
    rpaTemperatureC?: number;
    /** Thermo Lyo-ready RPA reviewed incubation window; bench-only. */
    rpaTimeMin?: number;
    /** Thermo Lyo-ready RPA Bst concentration within the reviewed range. */
    rpaBstUnitsPerUl?: number;
    /** Explicit RPA multiplex context; when true the reviewed 100 nM starting point applies. */
    rpaMultiplex?: boolean;
    templateInputNg?: number;
    templateInputUl?: number;
    templateClass?:
      | "genomic"
      | "hmw-genomic"
      | "plasmid"
      | "lambda"
      | "lower-complexity"
      | "cDNA"
      | "RNA"
      | "crude"
      | "other";
    hmwTemplateVerified?: boolean;
    qpcrInstrumentProfile?: QpcrInstrumentProfile;
    digitalConsumableId?: DigitalConsumableId;
    effectivePartitionVolumeNl?: number;
    fragmentationEnzyme?: string;
    colonySampleInputUl?: number;
  };
  /** Physical partition format; required for digital-pcr and independent of primer ranking. */
  digitalPartitionFormat?: "droplet" | "chip" | "chamber" | "other";
  /** Structured platform identity; prevents a named overlay from being paired with unrelated free text. */
  digitalPlatformId?: DigitalPlatformId;
  /** Free-text instrument/platform provenance, required only for other-validated. */
  digitalPlatformName?: string;
  /** Exact model for platform families whose multiplex optical capacity differs. */
  digitalInstrumentModel?:
    | "qiacuity-one-2plex"
    | "qiacuity-one-5plex"
    | "qiacuity-four"
    | "qiacuity-eight"
    | "bio-rad-qx600"
    | "other-validated";
  /** Explicit template-fragmentation state; never inferred from sequence alone. */
  digitalFragmentationState?: "not-assessed" | "not-required" | "planned" | "performed";
  /** Digital multiplex optical/amplitude architecture. This is planning/run evidence, not a probe-design claim by flanking-pair. */
  digitalMultiplexMode?: "none" | "channel" | "amplitude" | "hybrid" | "probe-mix";
  digitalMultiplexPanel?: DigitalMultiplexTarget[];
  /** Caller-imported measured-run evidence; never changes sequence ranking. */
  digitalRunEvidence?: Record<string, unknown>;
  /** Selected peer RPA assays; empirical evidence context only, never a sequence-only validation claim. */
  rpaMultiplexPanel?: Array<{
    target: string;
    forwardPrimer: string;
    reversePrimer: string;
    detectionIdentity?: string;
    empiricalEvidenceRef?: string;
  }>;

  /* A single primer is placed relative to something, so its target is required
     rather than defaulted, and which way it reads is a fact about the
     experiment. The two read figures are left alone unless a service provider
     quotes different ones. */
  direction?: "forward" | "reverse";
  deadZone?: number;
  readLength?: number;
  /** Explicit named cycle-sequencing chemistry overlay for the sequencing module. */
  sequencingProtocol?: "not-selected" | "bigdye-v3-1";
  sequencingDesignProfile?: "generic-cycle-sequencing" | "azenta-genewiz" | "eurofins" | "cornell";
  sequencingProvider?: string;
  sequencingUniversalPrimerScan?: boolean;
  sequencingBidirectional?: boolean;
  sequencingPrimerWalking?: boolean;
  sequencingWalkingOverlap?: number;
  sequencingTraceAb1Base64?: string;
  sequencingTraceFilename?: string;
  /** Capillary instrument family; unresolved is an explicit valid handoff state. */
  sequencingInstrument?:
    "unresolved" | "seqstudio" | "seqstudio-flex" | "3500" | "3500xl" | "3730" | "3730xl" | "other";
  /** Free-text identity only when sequencingInstrument is other. */
  sequencingInstrumentName?: string;
  /** Optional facility/provider SOP identifier. */
  sequencingFacilitySop?: string;
  /** Explicit RACE chemistry family/kit authority. */
  raceChemistry?:
    "generacer-kit-25-0355-vl" | "custom" | "firstchoice-rlm-race" | "smarter-race-current";
  /** Historical/exact PCR-partner identity retained for migration. */
  raceAdapter?:
    | "not-selected"
    | "generacer-kit-25-0355-vl"
    | "firstchoice-rlm-race"
    | "smarter-race-current"
    | "custom";
  /** Actual partner sequence when a RACE kit/SOP uses an unlisted universal primer. */
  racePartnerSequence?: string;
  /** Revision/identifier of caller-reviewed SOP/manual for custom/current SMARTer exact-partner authority. */
  raceSopRevision?: string;
  /** SHA-256 of the reviewed SOP/manual bytes or approved authority snapshot. */
  raceSopSha256?: string;
  /** Biological input provenance for RACE; required by the race module. */
  raceSubstrate?: "total-rna" | "mrna" | "cdna";
  /** Kit/SOP/RT/template-switch preparation provenance for RACE. */
  racePreparation?: string;
  /** Primary design or nested confirmation branch. */
  raceRound?: "primary" | "nested";
  racePolyadenylated?: boolean;
  /** Required by the RACE module; maps 5′/3′ transcript direction to read strand. */
  raceDirection?: "5prime" | "3prime";

  /* Mutagenesis is told what to change rather than where to amplify.  Single-edit
     Q5 remains backward compatible; topology-specific workflows use the richer
     fields below and are never coerced into one another. */
  edit?: { kind: string; at: number; to?: string; replacing?: number };
  edits?: { kind: string; at: number; to?: string; replacing?: number }[];
  mutagenesisTopology?:
    | "q5-back-to-back"
    | "quikchange-complementary"
    | "quikchange-lightning-multi"
    | "nebuilder-multisite";
  aminoAcidEdit?: {
    cdsStart: number;
    residue: number;
    fromAa?: string;
    toAa: string;
    codon?: string;
  };
  codonPolicy?: "minimum-nucleotide-changes" | "user-selected-codon" | "host-codon-usage";
  codonUsage?: Record<string, number>;
  libraryMode?: "none" | "NNK" | "NNS" | "custom";
  libraryEdit?: { at: number; codon: string };
  templateMethylationStatus?: "unknown" | "dam-methylated" | "unmethylated" | "other-reviewed";

  /** Universal-primer input handling: auto-align through the pinned alignment backend, or preserve a reviewed alignment. */
  alignmentMode?: "auto" | "prealigned";
  /** Explicit consensus construction policy; weights/strata are supplied-panel evidence, not prevalence. */
  consensusPolicy?:
    "strict-all-members" | "coverage-threshold" | "majority" | "weighted" | "stratified";
  /** JSON metadata keyed by FASTA record id, including optional weight/stratum and sampling-frame descriptors. */
  panelMetadata?: Record<string, Record<string, unknown>>;
  /** Physical degenerate-primer formulation intent. */
  formulationMode?:
    | "mixed-base-synthesis"
    | "defined-oligo-pool"
    | "discrete-subprimer-mixture"
    | "user-defined-formulation";
  formulationTotalConcentrationNm?: number;
  /** Finite non-target FASTA panel for bounded exact-IUPAC specificity evidence. */
  nontarget?: string;
  /** Optional alternative reviewed MSA for alignment-sensitivity evidence. */
  alternativeAlignment?: string;
  alignmentAuditBackend?: string;

  /* A tiling scheme covers everything, so it has no target — what it takes
     instead is backend/lifecycle identity plus geometry and evidence. */
  overlap?: number;
  pools?: number;
  tilingBackend?: "primalscheme3" | "olivar" | "compare" | "internal-development";
  tilingMinBaseFrequency?: number;
  tilingBacktrack?: boolean;
  tilingHighGc?: boolean;
  olivarSeed?: number;
  olivarDegenerateMode?: boolean;
  olivarCheckVariants?: boolean;
  tilingTargets?: unknown[];
  schemeVersion?: string;
  tilingDepthTsv?: string;
  tilingDropoutThreshold?: number;
  /** PrimalScheme3 lifecycle operation for tiled-scheme. */
  tilingOperation?: "scheme-create" | "panel-create" | "repair-mode" | "scheme-replace";
  /** Alignment authority for multi-sequence tiled input. */
  tilingAlignmentMode?: "auto" | "prealigned";
  /** Existing ARTIC/PrimalScheme primer BED content for repair/replace/panel extension. */
  existingBed?: string;
  /** Original PrimalScheme config.json content for repair/replace. */
  schemeConfig?: string;
  /** Optional region BED content for panel-create. */
  regionBed?: string;
  panelMode?: "region-only" | "entropy" | "equal";
  primerName?: string;

  /* An assembly is given a plan rather than a template, and the joining
     chemistry has no default. Current Gen-1 Gibson is executable only through
     the reviewed named E5510 protocol; policy mode does not activate a generic recipe. */
  segments?: {
    name?: string;
    kind?:
      | "amplified"
      | "fixed"
      | "literal"
      | "pcr-amplified"
      | "restriction-digest"
      | "synthetic-dsdna"
      | "ssdna-oligo"
      | "annealed-oligos"
      | "existing-linear";
    sequence: string;
    template?: string;
    orientation?: "final-construct" | "forward" | "reverse";
    concentrationNgUl?: number;
    massNg?: number;
    volumeUl?: number;
    restriction?: Record<string, unknown>;
    features?: Array<Record<string, unknown>>;
    provenance?: Record<string, unknown>;
  }[];
  /**
   * Whether the thing being designed against closes on itself.
   *
   * A Gibson plan says whether the last fragment meets the first; a template
   * says whether it is a plasmid, which makes the specificity scan wrap across
   * the join and a tiling scheme close rather than stop at a boundary that is
   * only where the file happens to begin. One wire field, because it is one
   * question — does this end, or does it come back round?
   */
  circular?: boolean;
  /**
   * Adjustments to whichever LAMP parameter set is in force.
   *
   * Loose because the worker owns which fields exist and what each is bounded
   * by — it refuses anything else by name, and duplicating that list here
   * would be a second place for it to be wrong.
   */
  windows?: Record<string, unknown>;
  method?: "gibson" | "nebuilder";
  /** Explicit named assembly-kit overlay. Gibson and NEBuilder remain distinct chemistries. */
  assemblyProtocol?:
    | "not-selected"
    | "neb-e5510"
    | "neb-nebuilder-e2621"
    | "neb-nebuilder-e5520"
    | "neb-nebuilder-e2623";

  /* Genotyping is anchored on one base, and both alleles are required: a
     genotype is read by comparing two reactions, and one on its own cannot
     tell a homozygote from a tube that failed. */
  at?: number;
  alleles?: string[];
  /** Rich normalized variant for SNV/MNV/indel/complex/presence-absence assays. */
  variant?: {
    type: "snv" | "mnv" | "insertion" | "deletion" | "complex-replacement" | "presence-absence";
    at: number;
    ref: string;
    alt: string;
    referenceAccession?: string;
    assembly?: string;
    coordinateSystem?: string;
    strand?: "plus" | "minus";
    rsid?: string;
  };
  nearbyVariantsVcf?: string;
  mismatchEvidenceProfile?: string;
  tetraReadout?: "agarose-gel" | "page" | "capillary" | "unresolved";
  tetraGelPercent?: number;
  tetraLadder?: string;
  tetraRunContext?: string;
  geometry?: string;

  /* A loop set is held to three windows at once, chosen from the template's own
     GC content. Naming one overrides that. */
  parameterSet?: string;
  /** Explicit kit-level LAMP protocol overlay from the generated authority. */
  lampProtocol?: LampProtocolId;
  /** Explicit LAMP observation/readout branch; recorded as assay provenance. */
  lampReadout?: LampReadout;
  lampReadoutChemistry?: LampReadoutChemistry;
  lampSampleMatrix?: string;
  lampSamplePreparation?: string;
  lampFormulation?: LampFormulation;
  lampConfirmationMode?: string;
  lampDetectionTopology?: string;
  lampMultiplexPlan?: Array<{
    target: string;
    method: string;
    reporter: string;
    channel: string;
    modifiedOligoRole: string;
    setSha256: string;
    authorityId: string;
    empiricalEvidenceRef: string;
  }>;
  lampDesignIntent?: LampDesignIntent;
  lampDesignStage?: LampDesignStage;
  lampFixedPrimers?: Partial<Record<"F3" | "B3" | "FIP" | "BIP" | "LF" | "LB", string>>;
  lampVariant?: { position: number; ref: string; alt: string; anchor: LampMutationAnchor };
  lampLoopPolicy?: LampLoopPolicy;
  lampBenchOptimization?: Record<string, number>;
  lampCarryoverStrategy?: "protocol-default" | "reviewed-dutp-udg";
  lampReconstitutionX?: "protocol-default" | "2x" | "4x";
  lampSpecificityAdditive?: "none" | "tte-uvrd-reviewed";
  lampAccelerationAdditive?: "none" | "guanidine-hcl-40mm";
  lampPrimerKineticsProfile?: "protocol-default" | "optigene-standard" | "optigene-high";
  lampPreincubationStrategy?: "protocol-default" | "takara-ung-25c-10min";
  lampSampleBufferType?: "none" | "water" | "te" | "other-buffered" | "chelating-other";
  lampInstrumentProfile?:
    | "not-specified"
    | "vazyme-slan96p"
    | "vazyme-quantstudio3"
    | "vazyme-quantstudio5"
    | "vazyme-steponeplus"
    | "vazyme-lightcycler96"
    | "vazyme-cfx96-touch"
    | "vazyme-quantgene9600"
    | "vazyme-gentier96r"
    | "agdia-amplifire"
    | "other-qpcr"
    | "other-validated";
  lampSampleInputPercent?: number;
  lampSampleBufferPh?: number;
  lampSampleBufferPercent?: number;
  lampTransportMediumPercent?: number;
  lampBileSaltMgMl?: number;
  lampCaryBlairPercent?: number;
  lampUpstreamGuanidineMm?: number;
  /** Versioned LAMP geometry policy; omission preserves the PrimerExplorer V5 public-rule profile. */
  lampGeometryProfile?: "primerexplorer-v5-compat" | "pcrstudio-evidence-2026";
  /** Optional synthetic FIP/BIP junction linker. */
  lampInnerLinker?: "none" | "tttt";
  /** New-set design or validation of a user-supplied complete LAMP set. */
  mode?: "design" | "validate-existing";
  existingSet?: {
    f3: string;
    b3: string;
    fip: string;
    bip: string;
    lf?: string;
    lb?: string;
    fipF1cLength: number;
    bipB1cLength: number;
  };

  /** Explicit named LGC KASP protocol overlay. */
  kaspProtocol?: "not-selected" | "lgc-kasp-tf-v5" | "lgc-standard";
  /** Genotype interpretation branch; never inferred from the two supplied bases. */
  kaspAssayMode?: "biallelic-genotype" | "plus-minus-presence-absence";
  /** Plate-format branch used by the named LGC overlay. */
  kaspPlateFormat?: "96" | "384";
  /** Instrument retained as provenance; `unresolved` is an explicit value. */
  kaspInstrumentModel?: string;
  /** Reference-dye/ROX branch retained explicitly. */
  kaspRoxPolicy?: "none" | "low" | "standard" | "high" | "unresolved";
  /** Declared electrophoresis size-resolution requirement for Tetra-ARMS. */
  tetraMinBandSeparationBp?: number;

  /* The nested engine designs two rounds, so one set of constraints could not
     describe both. */
  outer?: Record<string, number>;
  inner?: Record<string, number>;
  shares?: "nothing" | "forward" | "reverse";
  margin?: number;
  singleTube?: boolean;
  /** Explicit carry-over prevention strategy identity for nested PCR. */
  carryoverPrevention?: "not-selected" | "dutp-ung-strategy-only" | "dUTP-UNG";
  transferMode?:
    | "direct-transfer"
    | "diluted-transfer"
    | "msz-exonuclease-i"
    | "thermolabile-exonuclease-i"
    | "purified-product"
    | "custom-sop";
  cleanupProtocol?: "not-selected" | "neb-msz-exonuclease-i" | "neb-thermolabile-exonuclease-i";
  transferVolumeUl?: number;
  transferDilutionFactor?: number;
  customTransferSop?: string;
  round1Polymerase?: string;
  round2Polymerase?: string;
  round1Conditions?: Record<string, number>;
  round2Conditions?: Record<string, number>;
  round1ThermalProgram?: Array<Record<string, unknown>>;
  round2ThermalProgram?: Array<Record<string, unknown>>;
  /** Explicit post-amplification recovery/removal overlay for the selected mutagenesis topology. */
  postAmplificationProtocol?:
    | "not-selected"
    | "neb-q5-e0554"
    | "agilent-quikchange-lightning-210518"
    | "agilent-quikchange-lightning-multi-210513-210516"
    | "neb-nebuilder-multisite";
}

/** One module/engine-scoped request. Impossible module↔engine pairs do not type-check. */
export type ModuleDesignRequest<M extends ModuleId> = {
  moduleId: M;
  engine: EngineFor<M>;
  payload: DesignPayload;
};

/** Discriminated request union for all twenty-one public modules. */
export type DesignRequest = {
  [M in ModuleId]: ModuleDesignRequest<M>;
}[ModuleId];

/** Build a discriminated request and reject runtime drift from untyped form data. */
export function designRequestFor<M extends ModuleId>(
  moduleId: M,
  engine: string,
  payload: DesignPayload,
): ModuleDesignRequest<M> {
  const expected = MODULE_BINDINGS[moduleId].engine;
  if (engine !== expected) {
    throw new Error(`Module ${moduleId} belongs to engine ${expected}, not ${engine}.`);
  }
  return { moduleId, engine: expected, payload };
}
