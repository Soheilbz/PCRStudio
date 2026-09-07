/**
 * Every assay has a page of its own, and each page is about that assay.
 *
 * The registry is the authority on which modules exist. The test reads the
 * generated canonical module contract that the source auditor proves is an
 * exact projection of that registry, so it runs even when no API is listening.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { isPlanned, planFor, plannedModules } from "./page-plan";

/**
 * The generated canonical contract is the registry authority available to a
 * unit test. Unlike a live HTTP request, it is present in every Web CI job, so
 * this coverage can never turn into a green skip merely because the API is not
 * running. The source auditor separately proves this generated contract matches
 * the Rust/profile registry.
 */
function registered(): string[] {
  const path = resolve(process.cwd(), "../knowledge/runtime/module-contracts.json");
  const parsed = JSON.parse(readFileSync(path, "utf8")) as { modules: Record<string, unknown> };
  return Object.keys(parsed.modules).sort();
}

describe("every registered assay has its own page", () => {
  it("plans a page for each module the registry holds", () => {
    const missing = registered().filter((id) => !isPlanned(id));

    expect(missing, "these modules would fall back to the generic amplification page").toEqual([]);
  });

  it("plans no page for a module that does not exist", () => {
    const known = new Set(registered());
    const orphans = plannedModules().filter((id) => !known.has(id));

    expect(orphans, "a plan for an assay nobody can reach").toEqual([]);
  });
});

describe("a plan is about its own assay", () => {
  const every = plannedModules().map((id) => [id, planFor(id)] as const);

  it.each(every)("%s has at least a first question and a last look", (_id, plan) => {
    expect(plan.steps.length).toBeGreaterThanOrEqual(3);
    expect(plan.steps.at(-1)!.id).toBe("review");
  });

  it.each(every)("%s never repeats a step", (_id, plan) => {
    const ids = plan.steps.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it.each(every)("%s writes its own words rather than the generic ones", (id, plan) => {
    for (const step of plan.steps) {
      expect(step.heading.length, `${id}/${step.id}`).toBeGreaterThan(10);
      expect(step.description.length, `${id}/${step.id}`).toBeGreaterThan(40);
    }
  });

  it("drops the steps that cannot work for their assay", () => {
    // The three the review found actively harmful rather than merely unhelpful.
    const has = (id: string, step: string) => planFor(id).steps.some((s) => s.id === step);

    // LAMP's engine refuses every one of the fifteen generic constraint boxes:
    // a value typed there turns a valid run into an error.
    expect(has("lamp", "constraints")).toBe(false);

    // A Gibson is decided by whether an overlap occurs twice in the finished
    // construct, which the engine computes. An unrelated genome is not it.
    expect(has("gibson-assembly", "specificity")).toBe(false);

    // A scheme is checked against the genome it tiles — already pasted.
    expect(has("tiled-scheme", "specificity")).toBe(false);
  });

  it("asks for a count only where the engine takes one", () => {
    // A tiling scheme is one scheme and an assembly plan is one plan. Offering
    // "how many to return" rendered a control whose value the edge discarded.
    expect(planFor("tiled-scheme").unit.how).toBeNull();
    expect(planFor("gibson-assembly").unit.how).toBeNull();
    expect(planFor("standard-pcr").unit.how).toContain("pairs");
  });

  it("names what the assay returns rather than always saying pairs", () => {
    expect(planFor("lamp").unit.many).toBe("sets");
    expect(planFor("kasp").unit.many).toBe("assays");
    expect(planFor("sequencing-primer").unit.many).toBe("primers");
  });

  it("keeps bench helpers on their owning specialised step rather than a global tool tray", () => {
    // CURRENT renders inverse-enzyme, colony-vector-primer and existing-primer helpers
    // inside Strategy/Design where their values have assay meaning.  A global
    // tool list would re-introduce the cross-assay leakage this architecture
    // removes.
    for (const id of plannedModules()) expect(planFor(id).tools, id).toEqual([]);
  });

  it("writes every heading for the assay it belongs to", () => {
    /*
     * The audit that caught the first attempt at this file.
     *
     * A helper filled in whatever an assay did not override, and the result was
     * ninety-nine step slots carrying fifty distinct headings: "Everything
     * before it runs" on all twenty pages with a review step, "What is in the
     * tube?" on fourteen. The shapes differed and the words did not, which is
     * one page wearing twenty-one hats.
     *
     * A heading shared by two assays means one of them is being told something
     * that is not about it.
     */
    const seen = new Map<string, string[]>();
    for (const id of plannedModules()) {
      for (const s of planFor(id).steps) {
        const key = `${s.id} :: ${s.heading}`;
        seen.set(key, [...(seen.get(key) ?? []), id]);
      }
    }

    const shared = [...seen.entries()]
      .filter(([, ids]) => ids.length > 1)
      .map(([heading, ids]) => `${heading} — ${ids.join(", ")}`);

    expect(shared, "these assays are being shown another assay's words").toEqual([]);
  });

  it("writes every description for the assay it belongs to", () => {
    const seen = new Map<string, string[]>();
    for (const id of plannedModules()) {
      for (const s of planFor(id).steps) {
        seen.set(s.description, [...(seen.get(s.description) ?? []), id]);
      }
    }
    expect([...seen.values()].filter((ids) => ids.length > 1)).toEqual([]);
  });

  it("gives every released module the reviewed specialised-page architecture", () => {
    const expected: Record<string, string[]> = {
      "standard-pcr": ["target", "constraints", "reaction", "specificity", "review"],
      "long-range-pcr": ["target", "constraints", "reaction", "specificity", "review"],
      "colony-pcr": ["target", "strategy", "constraints", "reaction", "specificity", "review"],
      "nested-pcr": ["target", "design", "reaction", "specificity", "review"],
      "inverse-pcr": ["target", "strategy", "constraints", "reaction", "specificity", "review"],
      "qpcr-sybr": ["target", "constraints", "reaction", "specificity", "validation", "review"],
      "qpcr-probe": ["target", "design", "constraints", "reaction", "specificity", "review"],
      "digital-pcr": ["target", "constraints", "reaction", "specificity", "validation", "review"],
      "arms-pcr": ["target", "design", "constraints", "reaction", "specificity", "review"],
      "tetra-primer-arms": [
        "target",
        "design",
        "constraints",
        "reaction",
        "specificity",
        "validation",
        "review",
      ],
      kasp: ["target", "design", "constraints", "reaction", "specificity", "review"],
      "species-specific-pcr": ["target", "constraints", "reaction", "specificity", "review"],
      lamp: ["target", "design", "reaction", "specificity", "validation", "review"],
      rpa: ["target", "constraints", "reaction", "specificity", "validation", "review"],
      "universal-primers": ["target", "design", "constraints", "reaction", "review"],
      "tiled-scheme": ["target", "strategy", "design", "constraints", "reaction", "review"],
      race: ["target", "design", "constraints", "reaction", "specificity", "review"],
      "sequencing-primer": ["target", "design", "constraints", "reaction", "specificity", "review"],
      "gibson-assembly": ["design", "constraints", "reaction", "construct", "review"],
      "restriction-cloning": [
        "target",
        "vector",
        "design",
        "reaction",
        "specificity",
        "construct",
        "review",
      ],
      "site-directed-mutagenesis": ["target", "design", "reaction", "construct", "review"],
    };

    expect(Object.keys(expected).sort()).toEqual(registered());
    for (const [id, steps] of Object.entries(expected)) {
      expect(
        planFor(id).steps.map((one) => one.id),
        id,
      ).toEqual(steps);
    }
  });

  it("uses one page grammar without forcing every assay through the same shape", () => {
    // Every specialised step exists because at least one assay owns that
    // concept; no module receives a tab merely to make the tab count equal.
    const used = new Set(plannedModules().flatMap((id) => planFor(id).steps.map((s) => s.id)));
    expect([...used].sort()).toEqual([
      "constraints",
      "construct",
      "design",
      "reaction",
      "review",
      "specificity",
      "strategy",
      "target",
      "validation",
      "vector",
    ]);
    expect(planFor("gibson-assembly").steps.some((s) => s.id === "target")).toBe(false);
    expect(planFor("standard-pcr").steps.some((s) => s.id === "construct")).toBe(false);
    expect(planFor("qpcr-sybr").steps.some((s) => s.id === "validation")).toBe(true);
  });

  it("gives no two assays on one engine the same page", () => {
    // The complaint this file answers: eight modules ran flanking-pair and got
    // byte-for-byte the same form.
    const flanking = [
      "standard-pcr",
      "colony-pcr",
      "long-range-pcr",
      "qpcr-sybr",
      "digital-pcr",
      "restriction-cloning",
      "rpa",
      "species-specific-pcr",
    ];
    const shapes = flanking.map((id) =>
      planFor(id)
        .steps.map((s) => `${s.id}:${s.heading}`)
        .join("|"),
    );

    expect(new Set(shapes).size, "some of these eight still share a page").toBe(flanking.length);
  });
});
