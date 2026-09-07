/**
 * The seam between the interface and whatever is carrying its requests.
 *
 * Nothing above this file knows that the core is reached over HTTP. Moving the
 * core — into the same process, behind a queue, compiled to WebAssembly in the
 * browser — means implementing this interface again and changing one line
 * in `./index.ts`; every component and test stays where it is.
 */
import type {
  Aligned,
  AppInfo,
  ConsensusResult,
  FetchAnswer,
  EngineDescription,
  GoalDescription,
  ModifierTerm,
  StatusTerm,
  ModuleManifest,
  Presets,
  Catalogue,
  Preferences,
  Project,
  ProjectLimits,
  RecoveryStatus,
  CheckedPair,
  EnzymeRanking,
  MultiplexResult,
  RunResult,
  VectorPrimers,
  Run,
  RunJob,
  RunSummary,
  SharedRun,
  Session,
  User,
} from "./types";
import type { DesignPayload } from "@/lib/contracts/design-requests";

/** A pair somebody already has, and what to check it against. */
export interface CheckRequest {
  /** Optional assay whose canonical profile supplies the evaluation envelope. */
  moduleId?: string;
  /** The sequence these primers were made for. Required. */
  template: string;
  /** Explicit lowercase semantics when the template contains lowercase bases. */
  lowercaseMasking?: boolean;
  left: string;
  right: string;
  background?: string;
  /** The window to hold them to, which is rarely the default one. */
  constraints?: Record<string, number>;
  polymerase?: string;
  purpose?: string;
  maxMismatches?: number;
}

/** Several targets meant to share one tube. */
export interface MultiplexRequest {
  /** How the products will be read. No default: it decides the answer. */
  readout: "agarose" | "capillary" | "ngs";
  /** Required for agarose/capillary size-based readout: named supplier reference used for resolution-risk screening. */
  readoutProfile?:
    | "qiagen-multiplex-agarose-guideline"
    | "qiagen-qiaxcel-high-resolution"
    | "qiagen-qiaxcel-screening";
  /** RNA-derived targets require RT. Placement/timing remain unresolved unless the selected named chemistry provides explicit RT authority. */
  fromRna?: boolean;
  /** Optional Standard-PCR bench chemistry shared by every target in this physical tube. */
  standardPcrProtocol?: DesignPayload["standardPcrProtocol"];
  /** Colony-PCR crude-template context shared by every target in this multiplex reaction. */
  colonyHostClass?: "bacterial" | "yeast" | "filamentous-fungus" | "microalgae" | "other";
  colonyPreparation?:
    | "direct-transfer"
    | "liquid-culture"
    | "water-lysate"
    | "buffer-lysate"
    | "host-specific-lysis"
    | "other";
  colonyProtocolId?: DesignPayload["colonyProtocolId"];
  colonyProtocolName?: string;
  colonyProtocolProvenance?: string;
  targets: {
    name: string;
    template: string;
    /** Required by species-specific multiplex designs: sequences that must not amplify. */
    background?: string;
    /** Required by executable species-specific multiplex designs: declared intended-target diversity panel. */
    inclusivity?: string;
    /** User-declared source/version/accession provenance for the inclusivity panel. */
    inclusivityPanelProvenance?: string;
    /** User-declared source/version/accession provenance for the exclusion panel. */
    backgroundPanelProvenance?: string;
    /** Why these target and near-neighbour records represent the intended validation panel. */
    speciesPanelSelectionRationale?: string;
    speciesTargetTaxid?: number;
    speciesTaxonomySnapshot?: string;
    speciesDatabaseSnapshot?: string;
    speciesPanelAccessionManifest?: string;
    speciesPanelRecordMetadataManifest?: string;
    speciesPanelRetrievedDate?: string;
    /** Explicit physical tube/pool identity. Scientific-Strict requires this for multi-tube panels. */
    tube?: string;
    /** Planned/measured primer concentration; evidence metadata only and never a sequence-ranking input. */
    primerConcentrationNm?: number;
    /** Bench/run reference supporting any target-level formulation adjustment. */
    empiricalEvidenceRef?: string;
    constraints?: Record<string, number>;
  }[];
  candidatesPerTarget?: number;
  perTube?: number;
  rounds?: number;
  /** Exact is required by Scientific-Strict; local is an explicitly approximate development path. */
  optimizerMode?: "auto" | "exact" | "local";
  /** Optional deterministic local-search seed; omitted uses the worker's stable default. */
  seed?: number;
}

export interface Transport {
  /** Identity of the running build. */
  appInfo(): Promise<AppInfo>;
  /** Every design module this build ships, ordered by id. */
  listModules(): Promise<ModuleManifest[]>;
  /** One module's manifest. */
  getModule(id: string): Promise<ModuleManifest>;
  /** The goals modules are grouped under, in presentation order. */
  listGoals(): Promise<GoalDescription[]>;
  /** The engines this build compiled in, and what each accepts. */
  listEngines(): Promise<EngineDescription[]>;
  /** The modifiers a module can carry. */
  listModifiers(): Promise<ModifierTerm[]>;
  /** What each status word claims, and what promotion from it takes. */
  listStatuses(): Promise<StatusTerm[]>;
  /** The named settings this module's engine offers a form. */
  getPresets(id: string): Promise<Presets>;
  /** Whether an accession can be looked up at all in this build. */
  canFetch(): Promise<{ available: boolean; reason: string }>;
  /** Look one or more accessions up at NCBI. */
  fetchSequences(accessions: string): Promise<FetchAnswer>;
  /** Collapse aligned sequences into one. */
  consensus(fasta: string): Promise<ConsensusResult>;
  /** Which aligners this build can use. */
  canAlign(): Promise<{ available: boolean; reason: string }>;
  /** Align sequences with whatever standard aligner is installed. */
  alignSequences(fasta: string): Promise<Aligned>;
  /** Run a module against a request whose shape that module defines. */
  runDesign(id: string, request: DesignPayload): Promise<RunResult>;
  /**
   * Every restriction enzyme ranked for one of two opposite questions.
   *
   * `inverse-flank` — which leave the complete known anchor intact for standard two-flank inverse PCR.
   * `absent` — which do not cut an insert, for a cloning tail.
   * `open-once` — a separate explicit question for workflows that really require one internal cut.
   */
  rankEnzymes(
    template: string,
    background: string | undefined,
    purpose: "inverse-flank" | "absent" | "open-once",
  ): Promise<EnzymeRanking>;
  /** Where the universal primers really sit in the vector somebody has. */
  placeVectorPrimers(vector?: string, vectorName?: string): Promise<VectorPrimers>;
  /** Design a set of pairs meant to share a tube. */
  runMultiplex(id: string, request: MultiplexRequest): Promise<MultiplexResult>;
  /** Measure a pair somebody already has against the template they have. */
  checkPrimers(request: CheckRequest): Promise<CheckedPair>;

  /** Create an account and start a session for it. */
  register(email: string, displayName: string, password: string): Promise<Session>;
  /** Check an email and password, and start a session. */
  login(email: string, password: string, remember: boolean): Promise<Session>;
  /** End the session this token belongs to. */
  logout(token: string): Promise<void>;
  /** Who a session token belongs to. */
  currentUser(token: string): Promise<User>;
  /** Change a display name. */
  rename(token: string, displayName: string): Promise<User>;
  /** Change the sign-in email, proved with the current password. */
  changeEmail(token: string, currentPassword: string, newEmail: string): Promise<User>;
  /** Replace a password, sparing the calling session. */
  changePassword(token: string, currentPassword: string, newPassword: string): Promise<void>;

  /**
   * Set a new password from a recovery code, for somebody locked out.
   *
   * Returns a session, because whoever just proved who they are should not then
   * be asked to sign in — and a fresh recovery code, because the one they used
   * is spent and an account left without one has no second chance.
   */
  recover(email: string, recoveryCode: string, newPassword: string): Promise<Session>;

  /** Whether this account has a recovery code, and how old it is. */
  recoveryStatus(token: string): Promise<RecoveryStatus>;

  /** Replace the recovery code, proving the password first. */
  reissueRecoveryCode(token: string, password: string): Promise<{ recoveryCode: string }>;
  /** End every session this account has, including the calling one. */
  endAllSessions(token: string): Promise<number>;
  /** Delete the account behind this session. */
  deleteAccount(token: string, password: string): Promise<void>;

  /** Every project this person has, most recently touched first. */
  listProjects(token: string): Promise<Project[]>;
  /** Start a project, optionally with its initial draft in the same transaction. */
  createProject(
    token: string,
    name: string,
    moduleId: string,
    initial?: { notes?: string; settings?: unknown },
  ): Promise<Project>;
  /** One project. */
  getProject(token: string, id: string): Promise<Project>;
  /** Change a project. Anything omitted is left alone. */
  updateProject(
    token: string,
    id: string,
    change: {
      name?: string;
      notes?: string;
      settings?: unknown;
      expectedUpdatedAt?: string;
    },
  ): Promise<Project>;
  /** Delete a project and everything kept in it. Recoverable for thirty days. */
  deleteProject(token: string, id: string): Promise<void>;
  /** Mint a link that shows one run to somebody with no account. Returns it once. */
  shareRun(token: string, projectId: string, runId: string): Promise<string>;
  /** Withdraw it. Takes effect at once. */
  unshareRun(token: string, projectId: string, runId: string): Promise<void>;
  /** One run, to whoever holds the link. No session, and no project around it. */
  sharedRun(shareToken: string): Promise<SharedRun>;
  /** Every named reaction any assay offers, for a settings page to list. */
  catalogue(): Promise<Catalogue>;
  /** What this person has told us about how they work. */
  preferences(token: string): Promise<Preferences>;
  /** Replace them wholesale — a merge has no way to express "unset". */
  setPreferences(token: string, preferences: Preferences): Promise<Preferences>;
  /** The ceilings an account works inside. */
  projectLimits(): Promise<ProjectLimits>;
  /** Bring back a project deleted within that window. */
  restoreProject(token: string, id: string): Promise<Project>;
  /** Every run in a project, without their results. */
  listRuns(token: string, projectId: string): Promise<RunSummary[]>;
  /** One run, whole. */
  getRun(token: string, projectId: string, runId: string): Promise<Run>;
  /** Forget one run. */
  deleteRun(token: string, projectId: string, runId: string): Promise<void>;
  /** Run a design inside a project and keep the result. */
  runInProject(
    token: string,
    projectId: string,
    label: string,
    request: DesignPayload,
  ): Promise<{ run: Run; project: Project }>;
  /** Start one durable, idempotent design execution. */
  startRunJob(
    token: string,
    projectId: string,
    label: string,
    request: DesignPayload,
    idempotencyKey: string,
  ): Promise<RunJob>;
  /** Read measured execution state for a durable job. */
  getRunJob(token: string, projectId: string, jobId: string): Promise<RunJob>;
  /** Request cancellation and return the resulting durable state. */
  cancelRunJob(token: string, projectId: string, jobId: string): Promise<RunJob>;
}
