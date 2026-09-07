import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  nestedResultSchema,
  outwardResultSchema,
  probeResultSchema,
  singleResultSchema,
  tilingResultSchema,
  universalResultSchema,
} from "./types";

const live = Boolean(process.env.PCR_RUNTIME_API);
const api = process.env.PCR_API_URL ?? "http://127.0.0.1:8080";
const liveIt = live ? it : it.skip;

function corpus(name: string): string {
  return readFileSync(resolve(process.cwd(), `../tools/tests/corpus/${name}`), "utf8")
    .replace(/^>[^\r\n]*\r?\n/m, "")
    .replace(/\s/g, "");
}

async function design(id: string, body: unknown): Promise<unknown> {
  const response = await fetch(`${api}/api/modules/${id}/design`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  expect(response.ok, text).toBe(true);
  return JSON.parse(text);
}

describe("live result contracts", () => {
  liveIt("parses a real inverse-PCR response as outward-pair", async () => {
    const result = outwardResultSchema.parse(
      await design("inverse-pcr", {
        template: corpus("L09137.2.fasta"),
        howMany: 1,
        enzyme: "SpeI",
        inverseBranch: "restriction-self-ligation",
        leftEndPhosphate: "unresolved",
        rightEndPhosphate: "unresolved",
        circularizationProvenance: "unresolved",
        linearControlProvenance: "unresolved",
        methylationBranch: "unresolved",
      }),
    );

    expect(result.digest.known_sites).toEqual([]);
    expect(result.circle.known_length).toBe(result.target.length);
    expect(result.pairs).toHaveLength(1);
  });

  liveIt(
    "parses a real qPCR-probe response with the current pair-and-probe schema",
    async () => {
      const result = probeResultSchema.parse(
        await design("qpcr-probe", {
          template: corpus("L09137.2.fasta"),
          howMany: 1,
          probeProtocol: "thermofisher-taqman-conventional",
          probeChemistry: "conventional-hydrolysis",
          probeReporter: "FAM",
          probeQuencher: "QSY",
          probeTranscriptMode: "generic",
        }),
      );
      expect(result.engine).toBe("pair-and-probe");
    },
    30_000,
  );

  liveIt(
    "parses a real RACE response with the current single-primer schema",
    async () => {
      const result = singleResultSchema.parse(
        await design("race", {
          template: corpus("L09137.2.fasta"),
          howMany: 1,
          raceChemistry: "firstchoice-rlm-race",
          raceDirection: "5prime",
          raceSubstrate: "total-rna",
          racePreparation: "FirstChoice RLM-RACE current kit workflow",
          raceRound: "primary",
        }),
      );
      expect(result.engine).toBe("single-primer");
    },
    30_000,
  );

  liveIt(
    "parses a real sequencing-primer response with the current single-primer schema",
    async () => {
      const result = singleResultSchema.parse(
        await design("sequencing-primer", {
          template: corpus("L09137.2.fasta"),
          howMany: 1,
          direction: "forward",
          targetStart: 300,
          targetLength: 50,
          deadZone: 50,
          readLength: 650,
          sequencingDesignProfile: "generic-cycle-sequencing",
          sequencingProtocol: "not-selected",
        }),
      );
      expect(result.engine).toBe("single-primer");
    },
    30_000,
  );

  liveIt(
    "parses a real tiled-scheme response with the current tiling schema",
    async () => {
      const result = tilingResultSchema.parse(
        await design("tiled-scheme", {
          template: corpus("L09137.2.fasta"),
          tilingBackend: "primalscheme3",
          tilingOperation: "scheme-create",
          tilingAlignmentMode: "auto",
          overlap: 75,
          pools: 2,
        }),
      );
      expect(result.engine).toBe("tiling-scheme");
    },
    60_000,
  );

  liveIt("parses a real consensus response as consensus-pair", async () => {
    const newline = "\n";
    const template = `>a${newline}${"ACGT".repeat(250)}${newline}>b${newline}${"ACGA".repeat(250)}`;
    const result = universalResultSchema.parse(
      await design("universal-primers", { template, howMany: 1 }),
    );

    expect(result.pairs).toHaveLength(1);
    expect(result.alignment.sequences).toBe(2);
  });

  liveIt(
    "parses a nested response even when no pair survives",
    async () => {
      const result = nestedResultSchema.parse(
        await design("nested-pcr", {
          template: "ACGT".repeat(3000),
          howMany: 1,
          outer: { product_min: 800, product_max: 1500 },
          inner: { product_min: 300, product_max: 700 },
          shares: "nothing",
          margin: 0,
          singleTube: false,
          carryoverPrevention: "not-selected",
        }),
      );

      expect(result.engine).toBe("nested");
      expect(result.nests).toEqual([]);
      expect(result.why_nothing).not.toBe("");
      expect(result.nesting.single_tube).toBe(false);
      expect(result.nesting.tm_separation).toBeTypeOf("number");
      expect(result.nesting.note).toMatch(/Two tubes/);
    },
    30_000,
  );
});
