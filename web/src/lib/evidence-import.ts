export type EvidenceImportKind = "qpcr-sybr" | "digital-pcr";

export type EvidenceImportResult = {
  adapter: "csv-tsv" | "rdml-xml-metadata" | "rdes-xml-metadata";
  fields: Record<string, string>;
  warnings: string[];
};

const QPCR_ALIASES: Record<string, string> = {
  slope: "qpcrStandardCurveSlope",
  standardcurveslope: "qpcrStandardCurveSlope",
  r2: "qpcrStandardCurveR2",
  rsquared: "qpcrStandardCurveR2",
  standardcurver2: "qpcrStandardCurveR2",
  efficiency: "qpcrEfficiencyPercent",
  efficiencypct: "qpcrEfficiencyPercent",
  efficiencypercent: "qpcrEfficiencyPercent",
  lod: "qpcrLod",
  lloq: "qpcrLloq",
  uloq: "qpcrUloq",
  replicates: "qpcrReplicates",
  cq: "qpcrCqMean",
  cqmean: "qpcrCqMean",
  ctmean: "qpcrCqMean",
  dynamicrangelogs: "qpcrDynamicRangeLogs",
  instrument: "qpcrInstrument",
  software: "qpcrSoftwareVersion",
  softwareversion: "qpcrSoftwareVersion",
  baseline: "qpcrBaselineMethod",
  baselinemethod: "qpcrBaselineMethod",
  threshold: "qpcrThresholdMethod",
  thresholdmethod: "qpcrThresholdMethod",
  ntc: "qpcrNtcStatus",
  nort: "qpcrNoRtStatus",
  positivecontrol: "qpcrPositiveControlStatus",
  rawdata: "qpcrRawDataReference",
  rawdatareference: "qpcrRawDataReference",
  referencegenes: "qpcrReferenceGenes",
  normalization: "qpcrNormalizationMethod",
  normalizationmethod: "qpcrNormalizationMethod",
  inhibition: "qpcrInhibitionAssessment",
  meltevidence: "qpcrMeltEvidence",
  notes: "qpcrValidationNotes",
};
const DPCR_ALIASES: Record<string, string> = {
  totalpartitions: "dpcrTotalPartitions",
  acceptedpartitions: "dpcrAcceptedPartitions",
  positivepartitions: "dpcrPositivePartitions",
  negativepartitions: "dpcrNegativePartitions",
  rainpartitions: "dpcrRainPartitions",
  partitionvolumeul: "dpcrPartitionVolumeUl",
  dilutionfactor: "dpcrDilutionFactor",
  copiesperul: "dpcrCopiesPerUl",
  cilower: "dpcrCiLower",
  ciupper: "dpcrCiUpper",
  lob: "dpcrLob",
  lod: "dpcrLod",
  loq: "dpcrLoq",
  uncertaintypercent: "dpcrMeasurementUncertaintyPercent",
  measurementuncertaintypercent: "dpcrMeasurementUncertaintyPercent",
  threshold: "dpcrThresholdMethod",
  thresholdmethod: "dpcrThresholdMethod",
  software: "dpcrInstrumentSoftwareVersion",
  softwareversion: "dpcrInstrumentSoftwareVersion",
  partitionvolumeauthority: "dpcrPartitionVolumeAuthority",
  platelot: "dpcrPlateLot",
  vpf: "dpcrVpf",
  controls: "dpcrControlStatus",
  controlstatus: "dpcrControlStatus",
  rainpolicy: "dpcrRainPolicy",
  rawdata: "dpcrRawDataReference",
  rawdatareference: "dpcrRawDataReference",
  notes: "dpcrValidationNotes",
};

function normalizeKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function splitDelimited(line: string, delimiter: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      values.push(current.trim());
      current = "";
    } else current += char;
  }
  values.push(current.trim());
  return values;
}

function parseDelimited(text: string, kind: EvidenceImportKind): EvidenceImportResult {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length)
    return { adapter: "csv-tsv", fields: {}, warnings: ["The evidence file was empty."] };
  const firstLine = lines[0]!;
  const delimiter = firstLine.includes("\t") ? "\t" : ",";
  const aliases = kind === "qpcr-sybr" ? QPCR_ALIASES : DPCR_ALIASES;
  const fields: Record<string, string> = {};
  const warnings: string[] = [];
  const rows = lines.map((line) => splitDelimited(line, delimiter));
  const firstRow = rows[0]!;
  if (firstRow.length === 2 && aliases[normalizeKey(firstRow[0] ?? "")]) {
    for (const row of rows) {
      if (row.length < 2) continue;
      const target = aliases[normalizeKey(row[0] ?? "")];
      const value = row[1] ?? "";
      if (target && value !== "") fields[target] = value;
    }
  } else {
    const headers = firstRow.map((header) => aliases[normalizeKey(header)] ?? "");
    const data = rows[1];
    if (!data) warnings.push("No data row followed the header row; nothing was imported.");
    else
      headers.forEach((target, index) => {
        if (target && data[index] !== undefined && data[index] !== "") fields[target] = data[index];
      });
    if (rows.length > 2)
      warnings.push(
        "Only the first data row was imported. Replicate-level raw data should remain attached/referenced rather than silently averaged by PCRStudio.",
      );
  }
  return { adapter: "csv-tsv", fields, warnings };
}

function firstTag(text: string, names: readonly string[]): string | undefined {
  for (const name of names) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = text.match(new RegExp(`<${escaped}(?:\\s[^>]*)?>([^<]+)</${escaped}>`, "i"));
    if (match?.[1]?.trim()) return match[1].trim();
  }
  return undefined;
}

function parseXmlMetadata(
  text: string,
  kind: EvidenceImportKind,
  rdes: boolean,
): EvidenceImportResult {
  const fields: Record<string, string> = {};
  const put = (field: string, value: string | undefined) => {
    if (value) fields[field] = value;
  };
  if (kind === "qpcr-sybr") {
    put("qpcrCqMean", firstTag(text, ["cq", "Cq", "ct", "Ct"]));
    put("qpcrEfficiencyPercent", firstTag(text, ["efficiency", "amplificationEfficiency"]));
    put("qpcrStandardCurveSlope", firstTag(text, ["slope"]));
    put("qpcrStandardCurveR2", firstTag(text, ["r2", "rSquared"]));
    put("qpcrInstrument", firstTag(text, ["instrument", "machine"]));
    put("qpcrSoftwareVersion", firstTag(text, ["softwareVersion", "software"]));
    put("qpcrThresholdMethod", firstTag(text, ["thresholdMethod", "threshold"]));
    put("qpcrBaselineMethod", firstTag(text, ["baselineMethod", "baseline"]));
  } else {
    put("dpcrAcceptedPartitions", firstTag(text, ["acceptedPartitions", "validPartitions"]));
    put("dpcrPositivePartitions", firstTag(text, ["positivePartitions"]));
    put("dpcrNegativePartitions", firstTag(text, ["negativePartitions"]));
    put("dpcrPartitionVolumeUl", firstTag(text, ["partitionVolumeUl", "partitionVolume"]));
    put("dpcrCopiesPerUl", firstTag(text, ["copiesPerUl", "concentration"]));
    put("dpcrInstrumentSoftwareVersion", firstTag(text, ["softwareVersion", "software"]));
    put("dpcrThresholdMethod", firstTag(text, ["thresholdMethod", "threshold"]));
  }
  return {
    adapter: rdes ? "rdes-xml-metadata" : "rdml-xml-metadata",
    fields,
    warnings: [
      "XML import is metadata-only and deliberately does not average replicate curves, infer thresholds, or claim standards compliance. Keep the original raw-data file/reference with the run.",
    ],
  };
}

export function parseEvidenceFile(
  name: string,
  text: string,
  kind: EvidenceImportKind,
): EvidenceImportResult {
  const lower = name.toLowerCase();
  if (lower.endsWith(".csv") || lower.endsWith(".tsv") || lower.endsWith(".txt"))
    return parseDelimited(text, kind);
  if (lower.endsWith(".rdml") || lower.endsWith(".xml")) return parseXmlMetadata(text, kind, false);
  if (lower.endsWith(".rdes")) return parseXmlMetadata(text, kind, true);
  throw new Error("Evidence import accepts CSV, TSV, TXT, RDML/XML or RDES files.");
}
