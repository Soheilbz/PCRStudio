import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { requestFor } from "./request";

type Transport = { engines: Record<string, { fields: Array<{ web: string }> }> };
const authority = JSON.parse(
  readFileSync(resolve(process.cwd(), "src/lib/engine-transport-parity.generated.json"), "utf8"),
) as Transport;

function form(moduleId: string, values: Record<string, string>): FormData {
  const data = new FormData();
  data.set("moduleId", moduleId);
  for (const [key, value] of Object.entries(values)) data.set(key, value);
  return data;
}

function keys(value: object): Set<string> {
  return new Set(
    Object.keys(value).filter((key) => (value as Record<string, unknown>)[key] !== undefined),
  );
}

function expectAuthorityFields(engine: string, actual: object, allowMissing: string[] = []) {
  const actualKeys = keys(actual);
  const missing = authority.engines[engine]!.fields.map((row) => row.web).filter(
    (key) => !actualKeys.has(key) && !allowMissing.includes(key),
  );
  expect(missing).toEqual([]);
}

describe("Actual Web request mapping follows the unified engine transport authority", () => {
  it("maps outward-pair fields through requestFor", () => {
    const actual = requestFor(
      "outward-pair",
      ">t\n" + "ACGT".repeat(300),
      form("inverse-pcr", {
        inverseBranch: "supplied-circular-template",
        enzyme: "SpeI",
        circleLength: "1200",
        enzymeCohortSize: "3",
        inverseReferenceSequence: ">reference\nACGT",
        inverseCandidateEnzymes: "SpeI,EcoRI",
        mappingUseCase: "integration-site",
        circularizationProvenance: "supplied circle",
        linearControlProvenance: "control",
        methylationBranch: "unresolved",
        inverseValidationNotes: "reviewed",
      }),
    );
    expectAuthorityFields("outward-pair", actual);
  });

  it("maps pair-and-probe fields through requestFor", () => {
    const actual = requestFor(
      "pair-and-probe",
      ">t\n" + "ACGT".repeat(300),
      form("qpcr-probe", {
        probeProtocol: "idt-primetime-conventional",
        probeChemistry: "double-quenched-hydrolysis",
        probeReporter: "FAM",
        probeQuencher: "Iowa Black FQ",
        probeInternalQuencher: "ZEN",
        probeInstrumentProfile: "validated FAM channel",
        probeTranscriptMode: "generic",
        probeMultiplexPanel:
          '[{"target":"A","reporter":"FAM","quencher":"Iowa Black FQ","internalQuencher":"ZEN","channel":"FAM"}]',
        probeOpticalAuthorityPayload: '{"instrument":"validated-reader"}',
        probeMgbAuthorityMode: "external-authority-required",
        probeMgbAuthorityPayload: '{"candidate_set_hash":"abc"}',
        probeTranscriptJunctions: "120,240",
        probeVariantPositions: "80,160",
        probeValidationNotes: "reviewed",
      }),
    );
    expectAuthorityFields("pair-and-probe", actual);
  });

  it("maps the union of RACE and sequencing fields through the shared single-primer request builder", () => {
    const race = requestFor(
      "single-primer",
      ">t\n" + "ACGT".repeat(300),
      form("race", {
        raceChemistry: "generacer-kit-25-0355-vl",
        raceDirection: "5prime",
        raceRound: "primary",
        raceAdapter: "custom",
        racePartnerSequence: "ACGTACGTACGT",
        raceValidationNotes: "reviewed",
      }),
    );
    const sequencing = requestFor(
      "single-primer",
      ">t\n" + "ACGT".repeat(300),
      form("sequencing-primer", {
        direction: "forward",
        sequencingDesignProfile: "generic-cycle-sequencing",
        sequencingProtocol: "not-selected",
        sequencingProvider: "custom-lab",
        sequencingUniversalPrimerScan: "true",
        sequencingBidirectional: "true",
        sequencingWalkingOverlap: "100",
        sequencingTraceAb1Base64: "QUJDMQ==",
        sequencingTraceFilename: "trace.ab1",
        sequencingValidationNotes: "reviewed",
      }),
    );
    expectAuthorityFields("single-primer", { ...race, ...sequencing });
  });

  it("maps tiling fields through requestFor", () => {
    const actual = requestFor(
      "tiling-scheme",
      ">t\n" + "ACGT".repeat(1000),
      form("tiled-scheme", {
        tilingBackend: "primalscheme3",
        tilingOperation: "scheme-create",
        tilingAlignmentMode: "auto",
        tilingDepthTsv: "target\tdepth\nA\t30",
        tilingDropoutThreshold: "0.1",
        tilingMinBaseFrequency: "0.01",
        tilingBacktrack: "true",
        tilingHighGc: "true",
        olivarSeed: "10",
        olivarDegenerateMode: "false",
        schemeVersion: "v1.0.0",
        overlap: "75",
        pools: "2",
        tilingValidationNotes: "reviewed",
      }),
    );
    expectAuthorityFields("tiling-scheme", actual);
  });
});
