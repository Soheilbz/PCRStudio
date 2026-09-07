import { describe, expect, it } from "vitest";
import { parseEvidenceFile } from "./evidence-import";

describe("evidence import adapters", () => {
  it("maps qPCR CSV metadata without averaging extra replicate rows", () => {
    const parsed = parseEvidenceFile(
      "run.csv",
      "slope,r2,efficiency,cqmean,instrument\n-3.32,0.998,100,23.4,QuantStudio 5\n-3.30,0.997,101,23.6,QuantStudio 5\n",
      "qpcr-sybr",
    );
    expect(parsed.fields.qpcrStandardCurveSlope).toBe("-3.32");
    expect(parsed.fields.qpcrCqMean).toBe("23.4");
    expect(parsed.warnings.join(" ")).toMatch(/first data row/i);
  });

  it("extracts dPCR XML metadata while preserving metadata-only scope", () => {
    const parsed = parseEvidenceFile(
      "run.xml",
      "<run><acceptedPartitions>19000</acceptedPartitions><positivePartitions>950</positivePartitions><softwareVersion>2.1</softwareVersion></run>",
      "digital-pcr",
    );
    expect(parsed.fields.dpcrAcceptedPartitions).toBe("19000");
    expect(parsed.fields.dpcrPositivePartitions).toBe("950");
    expect(parsed.warnings.join(" ")).toMatch(/metadata-only/i);
  });

  it("rejects unsupported evidence formats instead of guessing", () => {
    expect(() => parseEvidenceFile("run.xlsx", "opaque", "qpcr-sybr")).toThrow(/accepts CSV/i);
  });
});
