#!/usr/bin/env node
/** Dependency-light browser/source contract check for the unified engine system. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const util = require("util");

const ROOT = path.resolve(__dirname, "..");
const ts = require(path.join(ROOT, "web/node_modules/typescript"));
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), "utf8");
const json = (rel) => JSON.parse(read(rel));
const assert = (condition, message) => { if (!condition) throw new Error(message); };

const system = json("web/src/lib/engine-system.generated.json");
const matrix = json("web/src/lib/engine-capability-matrix.generated.json");
const parity = json("web/src/lib/engine-transport-parity.generated.json");
assert(system.engine_count === 11, `engine registry count drift: ${system.engine_count}`);
assert(matrix.engine_count === 11, `capability engine count drift: ${matrix.engine_count}`);
assert(parity.engine_count === 11, `transport engine count drift: ${parity.engine_count}`);
assert(JSON.stringify(Object.keys(system.engines).sort()) === JSON.stringify(Object.keys(matrix.engines).sort()), "engine registry/capability set drift");
assert(JSON.stringify(Object.keys(system.engines).sort()) === JSON.stringify(Object.keys(parity.engines).sort()), "engine registry/transport set drift");

const corpusPaths = new Set();
for (const row of Object.values(system.engines)) {
  for (const rel of row.differential_corpora || []) corpusPaths.add(rel);
}
for (const rel of [...corpusPaths].sort()) {
  const canonical = json(rel);
  const stem = path.basename(rel, ".json");
  const projected = json(`web/src/lib/${stem}.generated.json`);
  assert(util.isDeepStrictEqual(canonical, projected), `${stem} browser differential corpus projection drift`);
}

const generatedAuthorities = read("web/src/lib/engine-authorities.generated.ts");
for (const name of ["ASSEMBLY", "CONSENSUS", "DISCRIMINATING", "FLANKING", "INVERSE", "LAMP", "MUTAGENESIS", "NESTED", "PROBE", "RACE", "SEQUENCING", "TILING"]) {
  assert(generatedAuthorities.includes(`export const ${name}_AUTHORITY`), `unified browser authority missing: ${name}`);
}

const requestSource = read("web/src/lib/projects/request.ts");
const designTypes = read("web/src/lib/contracts/design-requests.ts");
const fieldSources = [
  "web/src/components/design/engine-fields.tsx",
  ...fs.readdirSync(path.join(ROOT, "web/src/components/design/engine-fields"))
    .filter((name) => name.endsWith(".tsx"))
    .sort()
    .map((name) => `web/src/components/design/engine-fields/${name}`),
];
const fields = fieldSources.map(read).join("\n");
const discriminatingAuthority = json("contracts/chemistry/discriminating-protocols.json");
const discriminatingCorpus = json("contracts/chemistry/discriminating-differential-corpus.json");
for (const token of [
  "consensusPolicy", "panelMetadata", "formulationMode", "nontarget", "alternativeAlignment",
  "variantType", "variantRef", "variantAlt", "nearbyVariantsVcf", "kaspAssayMode", "kaspProtocol",
  "assemblyMethod", "assemblyProtocol", "mutagenesisTopology", "editsJson", "libraryMode",
  "transferMode", "cleanupProtocol", "round1ThermalProgram", "round2ThermalProgram",
]) {
  assert(requestSource.includes(token) || fields.includes(token), `browser field missing: ${token}`);
}
for (const token of ["neb-nebuilder-e2621", "neb-nebuilder-e5520", "neb-nebuilder-e2623", "lgc-kasp-tf-v5", "quikchange-complementary", "quikchange-lightning-multi"]) {
  assert(designTypes.includes(token), `browser type vocabulary missing: ${token}`);
}

const mismatchModelId = discriminatingAuthority.mismatch_model.model_id;
assert(generatedAuthorities.includes(`DISCRIMINATING_MISMATCH_MODEL_ID = "${mismatchModelId}"`), "browser mismatch-model identity projection drift");
const discriminatingCases = Object.fromEntries(discriminatingCorpus.cases.map((row) => [row.id, row]));
assert(discriminatingCases["kasp-biallelic-indel-refusal"]?.expected?.status === "refused", "KASP biallelic+indel refusal corpus drift");
const presenceAbsence = discriminatingCases["kasp-plus-minus-presence-absence"];
assert(presenceAbsence?.request?.kasp_assay_mode === "plus-minus-presence-absence", "KASP presence/absence mode drift");
assert(presenceAbsence?.request?.variant?.ref && presenceAbsence?.request?.variant?.alt === "", "KASP presence/absence REF-present convention drift");
const compactFields = fields.replace(/\s+/g, "");
for (const token of [
  'value="biallelic-genotype" disabled={variantType !== "snv" && variantType !== "mnv"}',
  'value="plus-minus-presence-absence" disabled={variantType === "snv" || variantType === "mnv"}',
  'next === "snv" || next === "mnv" ? "biallelic-genotype" : "plus-minus-presence-absence"',
]) {
  assert(compactFields.includes(token.replace(/\s+/g, "")), `KASP UI mode/variant separation drift: ${token}`);
}

const endpointSource = read("web/src/lib/kasp-endpoint.ts");
const transpiled = ts.transpileModule(endpointSource, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  reportDiagnostics: true,
});
const errors = (transpiled.diagnostics || []).filter((row) => row.category === ts.DiagnosticCategory.Error);
assert(errors.length === 0, errors.map((row) => ts.flattenDiagnosticMessageText(row.messageText, " ")).join("\n"));
const moduleObject = { exports: {} };
vm.runInNewContext(transpiled.outputText, { module: moduleObject, exports: moduleObject.exports, require }, { filename: "kasp-endpoint.generated-check.js" });
const { parseKaspEndpoint, kaspPlotBounds } = moduleObject.exports;
const parsed = parseKaspEndpoint("Sample,Well,FAM,HEX,Call\nA,A01,100,10,AA\nB,A02,40,45,AB\nC,A03,8,120,BB\nNTC,H12,1,1,no-template\n");
assert(parsed.rows.length === 4, "KASP endpoint parser row count drift");
assert(parsed.rows[0].call === "AA" && parsed.rows[2].call === "BB", "provider calls must be preserved");
assert(parsed.callSummary.AA === 1 && parsed.callSummary["no-template"] === 1, "KASP call-summary drift");
const bounds = kaspPlotBounds(parsed.rows);
assert(bounds.xMin < 1 && bounds.xMax > 100 && bounds.yMin < 1 && bounds.yMax > 120, "KASP plot bound drift");
assert(!endpointSource.includes("autoCall") && !endpointSource.includes("auto_call"), "KASP endpoint parser must not grow silent auto-calling");

console.log("ENGINE_WEB_CONTRACT=PASS engines=11");
