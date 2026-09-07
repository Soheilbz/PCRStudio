/**
 * Server-side loaders used by pages.
 *
 * A page should render something useful when the core is down rather than
 * showing an error screen for the whole site, so these turn a transport failure
 * into a value the page can display beside whatever else it has.
 */
import "server-only";

import { api } from "./index";
import { describe, PcrStudioError } from "./error";
import moduleCopy from "@/lib/module-copy.generated.json";
import type {
  Catalogue,
  AppInfo,
  EngineDescription,
  GoalDescription,
  ModifierTerm,
  StatusTerm,
  ModuleManifest,
  Presets,
} from "./types";

export interface Loaded<T> {
  data: T | null;
  error: string | null;
}

export type LoadedModuleManifest = ModuleManifest & { checks: string };

export async function loadModules(): Promise<{
  modules: LoadedModuleManifest[];
  error: string | null;
}> {
  try {
    return { modules: (await api.listModules()).map(withCanonicalCopy), error: null };
  } catch (cause) {
    return { modules: [], error: describe(cause, "The design core did not answer.") };
  }
}

/**
 * One module, or `null` when the core says no such id exists.
 *
 * The distinction matters: a missing module is a 404 for the page, while an
 * unreachable core is a message shown inside an otherwise working page.
 */
export async function loadModule(
  id: string,
): Promise<Loaded<LoadedModuleManifest> & { missing: boolean }> {
  try {
    return { data: withCanonicalCopy(await api.getModule(id)), error: null, missing: false };
  } catch (cause) {
    if (cause instanceof PcrStudioError && cause.core?.kind === "unknownProfile") {
      return { data: null, error: null, missing: true };
    }
    return {
      data: null,
      error: describe(cause, "The design core did not answer."),
      missing: false,
    };
  }
}

type ModuleCopy = { name: string; summary: string; guidance: string; checks: string };
const canonicalModuleCopy = moduleCopy.modules as Record<string, ModuleCopy>;

/** Keep visible copy aligned with the canonical profile even during a backend restart. */
function withCanonicalCopy(module: ModuleManifest): LoadedModuleManifest {
  const copy = canonicalModuleCopy[module.id];
  if (!copy) throw new Error(`Missing canonical page copy for module: ${module.id}`);
  return { ...module, ...copy };
}

/**
 * The vocabularies the interface groups and labels by.
 *
 * Every label comes from the core, so adding a goal or renaming one is a change
 * in Rust and nowhere else. An unreachable core yields empty lists, and the
 * pages fall back to showing modules ungrouped rather than to an error screen.
 */
export async function loadVocabulary(): Promise<{
  goals: GoalDescription[];
  engines: EngineDescription[];
  modifiers: ModifierTerm[];
  statuses: StatusTerm[];
}> {
  const [goals, engines, modifiers, statuses] = await Promise.all([
    api.listGoals().catch(() => []),
    api.listEngines().catch(() => []),
    api.listModifiers().catch(() => []),
    api.listStatuses().catch(() => []),
  ]);
  return { goals, engines, modifiers, statuses };
}

/**
 * The settings one module offers, or an empty set when the core is unreachable.
 *
 * Empty rather than thrown: a form with no presets is still usable, and losing
 * the whole page because a dropdown could not be filled is a bad trade.
 */
export async function loadPresets(id: string): Promise<Loaded<Presets>> {
  try {
    return { data: await api.getPresets(id), error: null };
  } catch (cause) {
    return { data: null, error: describe(cause, "The design settings could not be loaded.") };
  }
}

/**
 * Whether an accession can be looked up in this build.
 *
 * False rather than thrown when the core is unreachable: the accession tab
 * simply does not appear, which is a better answer than a tab that fails.
 */
export async function loadCanFetch(): Promise<boolean> {
  try {
    return (await api.canFetch()).available;
  } catch {
    return false;
  }
}

/** Whether an aligner is installed on the server. */
export async function loadCanAlign(): Promise<boolean> {
  try {
    return (await api.canAlign()).available;
  } catch {
    return false;
  }
}

export async function loadAppInfo(): Promise<Loaded<AppInfo>> {
  try {
    return { data: await api.appInfo(), error: null };
  } catch (cause) {
    return { data: null, error: describe(cause, "The design core did not answer.") };
  }
}

/**
 * Every named reaction any assay offers.
 *
 * An empty list when the core cannot be asked, which renders as "no
 * preference" and nothing else — a settings page that cannot reach the
 * catalogue should offer no choice rather than a wrong one.
 */
export async function loadCatalogue(): Promise<Catalogue> {
  try {
    return await api.catalogue();
  } catch {
    return { polymerases: [] };
  }
}
