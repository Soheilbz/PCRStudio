#!/usr/bin/env node
/** Dependency-light executable regression for the browser-side LAMP numeric contract. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const ts = require(path.join(ROOT, "web/node_modules/typescript"));
const sourcePath = path.join(ROOT, "web/src/lib/lamp-contract.ts");
const catalogPath = path.join(ROOT, "web/src/lib/lamp-numeric-recipes.generated.json");
const authorityJsonPath = path.join(ROOT, "web/src/lib/lamp-protocol-authority.generated.json");
const differentialPath = path.join(ROOT, "contracts/chemistry/lamp-differential-corpus.json");
let source = fs.readFileSync(sourcePath, "utf8");
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
const authority = JSON.parse(fs.readFileSync(authorityJsonPath, "utf8"));
const differential = JSON.parse(fs.readFileSync(differentialPath, "utf8"));

source = source.replace(
  /import numericCatalog from "\.\/lamp-numeric-recipes\.generated\.json";\s*/,
  "const numericCatalog = __CATALOG__;\n",
);
if (!source.includes("const numericCatalog = __CATALOG__;")) throw new Error("failed to substitute generated LAMP numeric catalogue import");
source = source.replace(
  /import \{ LAMP_PROTOCOL_METADATA, LAMP_AUTHORITY \} from "\.\/lamp-protocol-authority\.generated";\s*/,
  "const LAMP_AUTHORITY = __AUTHORITY__;\nconst LAMP_PROTOCOL_METADATA = __AUTHORITY__.protocols;\n",
);
if (!source.includes("const LAMP_AUTHORITY = __AUTHORITY__;")) throw new Error("failed to substitute generated LAMP authority import");

const transpiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true },
  reportDiagnostics: true,
});
const errors = (transpiled.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error);
if (errors.length) throw new Error(errors.map((d) => ts.flattenDiagnosticMessageText(d.messageText, " ")).join("\n"));
const moduleObject = { exports: {} };
vm.runInNewContext(transpiled.outputText, {
  module: moduleObject, exports: moduleObject.exports, require, structuredClone,
  __CATALOG__: catalog, __AUTHORITY__: authority, console,
}, { filename: "lamp-contract.generated-check.js" });
const { resolveLampNumericPreview, diffLampNumericPreview } = moduleObject.exports;
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const baseState = (testCase) => ({
  protocol: testCase.protocol, fromRna: false, matrix: "purified-nucleic-acid", preparation: "purified",
  formulation: "not-specified", readout: "not-specified", chemistry: "not-specified",
  ...(testCase.web_state || {}),
});

for (const id of authority.groups.protocols) {
  if (id === "not-selected") continue;
  assert(authority.protocols[id], `canonical LAMP protocol ${id} missing from authority protocols`);
}
for (const testCase of differential.cases) {
  const preview = resolveLampNumericPreview(baseState(testCase));
  for (const [key, expected] of Object.entries(testCase.expected_values || {})) {
    assert(Math.abs((preview.values[key] ?? Number.NaN) - expected) < 1e-9, `differential ${testCase.id}:${key} drift`);
  }
  const unresolved = new Set(preview.unresolved.map((row) => row.id));
  for (const expectedId of testCase.expected_unresolved || []) assert(unresolved.has(expectedId), `differential ${testCase.id} unresolved ${expectedId} drift`);
  const stageIds = preview.thermalStages.map((stage) => stage.id);
  assert(JSON.stringify(stageIds) === JSON.stringify(testCase.expected_thermal_stage_ids || []), `differential ${testCase.id} thermal-stage drift: ${stageIds}`);
  assert(preview.thermalStageModel === "ordered-source-backed-only", `differential ${testCase.id} thermal-stage model drift`);
  assert(preview.sequenceDecisionImpact === "none", `differential ${testCase.id} sequence-impact drift`);
}
const before = resolveLampNumericPreview(baseState({ protocol: "hyasen-hyb413", web_state: {} }));
const after = resolveLampNumericPreview(baseState({ protocol: "hyasen-hyb413", web_state: { benchValues: { lampOptTemperature: "64" } } }));
assert(diffLampNumericPreview(before, after).some((row) => row.key === "hold_temperature_c"), "LAMP recipe diff regression");
assert(after.sequenceDecisionImpact === "none", "LAMP bench override must never alter sequence ranking");
console.log("LAMP_WEB_NUMERIC_CONTRACT=PASS");
