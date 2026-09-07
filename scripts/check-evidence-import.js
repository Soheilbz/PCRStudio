#!/usr/bin/env node
/** Dependency-light executable regression for qPCR/dPCR evidence import. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const ts = require(path.join(ROOT, "web/node_modules/typescript"));
const source = fs.readFileSync(path.join(ROOT, "web/src/lib/evidence-import.ts"), "utf8");
const transpiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  reportDiagnostics: true,
});
const errors = (transpiled.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error);
if (errors.length) throw new Error(errors.map((d) => ts.flattenDiagnosticMessageText(d.messageText, " ")).join("\n"));
const moduleObject = { exports: {} };
vm.runInNewContext(transpiled.outputText, { module: moduleObject, exports: moduleObject.exports, require, console }, { filename: "evidence-import.generated-check.js" });
const { parseEvidenceFile } = moduleObject.exports;
const assert = (condition, message) => { if (!condition) throw new Error(message); };

const qpcr = parseEvidenceFile("quantstudio.csv", "cq,efficiency,softwareVersion\n23.5,96.8,1.7\n24.1,95.0,1.7\n", "qpcr-sybr");
assert(qpcr.adapter === "csv-tsv", "qPCR CSV adapter drift");
assert(qpcr.fields.qpcrCqMean === "23.5", "qPCR Cq mapping drift");
assert(qpcr.fields.qpcrEfficiencyPercent === "96.8", "qPCR efficiency mapping drift");
assert(qpcr.fields.qpcrSoftwareVersion === "1.7", "qPCR software mapping drift");
assert(qpcr.warnings.some((x) => x.includes("first data row")), "qPCR importer must disclose that it did not average replicate rows");

const dpcr = parseEvidenceFile("run.rdml", "<rdml><acceptedPartitions>18420</acceptedPartitions><positivePartitions>214</positivePartitions><partitionVolumeUl>0.00085</partitionVolumeUl><softwareVersion>2.1</softwareVersion></rdml>", "digital-pcr");
assert(dpcr.adapter === "rdml-xml-metadata", "dPCR RDML adapter drift");
assert(dpcr.fields.dpcrAcceptedPartitions === "18420", "dPCR accepted-partition mapping drift");
assert(dpcr.fields.dpcrPositivePartitions === "214", "dPCR positive-partition mapping drift");
assert(dpcr.fields.dpcrPartitionVolumeUl === "0.00085", "dPCR partition-volume mapping drift");
assert(dpcr.warnings.some((x) => x.includes("metadata-only")), "XML import must remain explicitly metadata-only");

const rdes = parseEvidenceFile("run.rdes", "<rdes><cq>19.2</cq><instrument>CFX96</instrument><thresholdMethod>manual</thresholdMethod></rdes>", "qpcr-sybr");
assert(rdes.adapter === "rdes-xml-metadata", "RDES adapter drift");
assert(rdes.fields.qpcrCqMean === "19.2" && rdes.fields.qpcrInstrument === "CFX96", "RDES metadata mapping drift");

let rejected = false;
try { parseEvidenceFile("run.xlsx", "binary", "qpcr-sybr"); } catch (error) { rejected = String(error).includes("accepts CSV"); }
assert(rejected, "unsupported evidence file types must fail closed");
console.log("EVIDENCE_IMPORT_CONTRACT=PASS");
