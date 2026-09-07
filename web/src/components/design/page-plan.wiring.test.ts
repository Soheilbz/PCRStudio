/**
 * Every step a page shows, against the engine that would have to answer it.
 *
 * Six pages showed a specificity step whose answer went nowhere: the engines
 * behind them had no `background` field, so a pasted genome was dropped on the
 * way in and the result said nothing about it. That is the worst shape a check
 * can take — a design nobody looked at reads exactly like a design that came
 * back clean — and none of it was visible from either side alone. The page
 * looked complete, the engine looked strict, and the request builder quietly
 * bridged them by throwing the value away.
 *
 * A seventh page had the mirror of it: restriction cloning hid a background box
 * its engine has always accepted.
 *
 * Both directions are asserted, because both are defects. This reads the three
 * files that actually decide it — the plans, `profiles.toml`, and the engine
 * structs — rather than a list kept alongside them.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { EXCLUSION_ONLY, NO_REGION } from "@/lib/api/labels";

import { isPlanned, planFor, type ControlId } from "./page-plan";

const CORE = resolve(process.cwd(), "../crates/pcr-core");
const read = (path: string) => readFileSync(path, "utf8").split("\r\n").join("\n");

/** Which engine each assay runs on, from the file that decides it. */
function engines(): Map<string, string> {
  const found = new Map<string, string>();
  let id = "";
  for (const line of read(resolve(CORE, "profiles.toml")).split("\n")) {
    const text = line.trim();
    const asId = /^id = "([^"]+)"/.exec(text);
    if (asId) id = asId[1]!;
    const asEngine = /^engine = "([^"]+)"/.exec(text);
    if (asEngine && id) found.set(id, asEngine[1]!);
  }
  return found;
}

/** Whether one engine's request struct declares a field, in Rust spelling. */
function declares(engine: string, field: string): boolean {
  const stem = engine.split("-").join("_");
  const source = read(resolve(CORE, `src/engines/${stem}.rs`));
  return new RegExp(`^ {4}pub ${field}:`, "m").test(source);
}

/** Which step id has to be backed by which engine field. */
const BACKED_BY: Record<string, string> = {
  specificity: "background",
};

/**
 * Which optional control fills in which engine field.
 *
 * The same assertion as the steps, one level finer. A control an engine cannot
 * take is an answer thrown away; a field no page fills is a capability nobody
 * can reach. Both have happened here — the cloning module could not send the
 * restriction sites its own engine has always accepted — so both are checked.
 */
const CONTROL_FIELD: Record<ControlId, string> = {
  circular: "circular",
  tails: "tails",
  excluded: "excluded",
};

describe("no page shows a step its engine cannot answer", () => {
  const byModule = engines();

  it("found the modules and the engines", () => {
    // The failure mode of a test like this is an empty map that passes.
    expect(byModule.size).toBe(21);
    expect(byModule.get("standard-pcr")).toBe("flanking-pair");
  });

  for (const [control, field] of Object.entries(CONTROL_FIELD)) {
    it.each([...engines().keys()].filter(isPlanned))(`${control}: %s`, (moduleId) => {
      const engine = byModule.get(moduleId)!;
      const asked = (planFor(moduleId).asks ?? []).includes(control as ControlId);
      const accepted = declares(engine, field);

      // One direction only: several engines accept a field that most of the
      // assays sharing them have no use for, and offering it everywhere is the
      // generic page this work exists to undo. What must never happen is the
      // other way round — a control whose answer the engine refuses.
      if (asked) {
        expect(
          accepted,
          `this page offers ${control} and ${engine} has nowhere to put it, so the answer is discarded`,
        ).toBe(true);
      }
    });
  }

  /*
   * The region picker offers three fields at once — where the product must
   * reach, how far, and what it must avoid — so an engine that takes none of
   * them is shown a whole card whose every value is discarded. Two were: a
   * degenerate pair is designed from an alignment and an inverse PCR is
   * anchored on its cut, and both collected a target region anyway.
   */
  const EVERY_ENGINE = [...engines().values()].filter(
    (engine, index, all) => all.indexOf(engine) === index,
  );

  it.each(EVERY_ENGINE)("the region picker is shown only where it lands: %s", (engine) => {
    const shown = !NO_REGION.includes(engine as never);
    expect(
      shown,
      shown
        ? `${engine} declares no target region, so the picker's values are dropped`
        : `${engine} takes a target region and no page offers one`,
    ).toBe(declares(engine, "target_start"));
  });

  /*
   * And the standalone control, for the three that have somewhere a primer must
   * not go and no region to point at. Derived from the engine structs rather
   * than trusted: the list in `labels.ts` cannot be computed in the browser,
   * so this is the assertion that keeps it from drifting.
   */
  it.each(EVERY_ENGINE)("exclusions are offered wherever they land: %s", (engine) => {
    const viaPicker = !NO_REGION.includes(engine as never);
    const standalone = EXCLUSION_ONLY.includes(engine as never);
    expect(
      viaPicker || standalone,
      viaPicker || standalone
        ? `${engine} is offered an exclusion box and has nowhere to put the answer`
        : `${engine} takes an exclusion and no page offers one`,
    ).toBe(declares(engine, "excluded"));

    // And never both, which would put two of the same control on one page.
    expect(viaPicker && standalone).toBe(false);
  });

  it("every control an assay can offer is one some assay does", () => {
    // The failure mode of the loop above: a control listed in the type, wired
    // into the workspace, and named by no plan at all — which renders nowhere
    // and reads as done.
    const asked = new Set(
      [...engines().keys()].filter(isPlanned).flatMap((id) => planFor(id).asks ?? []),
    );
    expect([...asked].sort()).toEqual(Object.keys(CONTROL_FIELD).sort());
  });

  for (const [step, field] of Object.entries(BACKED_BY)) {
    it.each([...engines().keys()].filter(isPlanned))(`${step}: %s`, (moduleId) => {
      const engine = byModule.get(moduleId)!;
      const shown = planFor(moduleId).steps.some((one) => one.id === step);
      const accepted = declares(engine, field);

      expect(
        shown,
        shown
          ? `this page asks for a ${field} and ${engine} has nowhere to put it, so the answer is silently discarded`
          : `${engine} accepts a ${field} and this page never asks for one, so a real check is hidden`,
      ).toBe(accepted);
    });
  }
});
