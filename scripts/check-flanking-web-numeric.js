#!/usr/bin/env node
/** Dependency-light executable regression for the browser-side Flanking numeric contract. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const ts = require(path.join(ROOT, "web/node_modules/typescript"));
const sourcePath = path.join(ROOT, "web/src/lib/flanking-contract.ts");
const catalogPath = path.join(ROOT, "web/src/lib/flanking-numeric-recipes.generated.json");
const authorityPath = path.join(ROOT, "web/src/lib/flanking-protocol-authority.generated.json");
const differentialPath = path.join(ROOT, "contracts/chemistry/flanking-differential-corpus.json");
let source = fs.readFileSync(sourcePath, "utf8");
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
const authority = JSON.parse(fs.readFileSync(authorityPath, "utf8"));
const differential = JSON.parse(fs.readFileSync(differentialPath, "utf8"));
source = source.replace(
  /import numericCatalog from "\.\/flanking-numeric-recipes\.generated\.json";\s*/,
  "const numericCatalog = __CATALOG__;\n",
);
if (!source.includes("const numericCatalog = __CATALOG__;")) {
  throw new Error("failed to substitute generated Flanking numeric catalogue import");
}
source = source.replace(
  /import protocolAuthority from "\.\/flanking-protocol-authority\.generated\.json";\s*/,
  "const protocolAuthority = __AUTHORITY__;\n",
);
if (!source.includes("const protocolAuthority = __AUTHORITY__;")) {
  throw new Error("failed to substitute generated Flanking protocol authority import");
}
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    esModuleInterop: true,
  },
  reportDiagnostics: true,
});
const errors = (transpiled.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error);
if (errors.length) {
  throw new Error(errors.map((d) => ts.flattenDiagnosticMessageText(d.messageText, " ")).join("\n"));
}
const moduleObject = { exports: {} };
vm.runInNewContext(transpiled.outputText, {
  module: moduleObject,
  exports: moduleObject.exports,
  require,
  structuredClone,
  __CATALOG__: catalog,
  __AUTHORITY__: authority,
  console,
}, { filename: "flanking-contract.generated-check.js" });

const { resolveFlankingNumericPreview, diffFlankingNumericPreview } = moduleObject.exports;
function assert(condition, message) {
  if (!condition) throw new Error(message);
}


for (const group of ["standard_pcr", "qpcr_sybr", "rpa", "long_range", "digital", "colony_protocols"]) {
  for (const id of authority.groups[group]) {
    if (id === "not-selected" || id === "custom-sop") continue;
    assert(catalog.protocol_metadata[id], `canonical Flanking protocol ${id} is missing from browser numeric metadata`);
  }
}

for (const testCase of differential.cases) {
  const preview = resolveFlankingNumericPreview({ moduleId: testCase.module, protocol: testCase.protocol, ...(testCase.web_state || {}) });
  for (const [key, expected] of Object.entries(testCase.expected_values || {})) {
    assert(Math.abs((preview.values[key] ?? Number.NaN) - expected) < 1e-9, `differential ${testCase.id}:${key} drift`);
  }
  const unresolved = new Set(preview.unresolved.map((row) => row.id));
  for (const expectedId of testCase.expected_unresolved || []) assert(unresolved.has(expectedId), `differential ${testCase.id} unresolved ${expectedId} drift`);
  assert(preview.sequenceDecisionImpact === "none", `differential ${testCase.id} sequence-impact drift`);
}

const powertrack = resolveFlankingNumericPreview({
  moduleId: "qpcr-sybr",
  protocol: "thermo-powertrack-sybr-a46xxx",
  cyclingProfile: "fast",
  reactionVolumeUl: "20",
});
assert(powertrack.values.yellow_sample_buffer_uL === undefined, "PowerTrack Yellow Sample Buffer must remain optional");
const powertrackBuffer = resolveFlankingNumericPreview({
  moduleId: "qpcr-sybr",
  protocol: "thermo-powertrack-sybr-a46xxx",
  cyclingProfile: "fast",
  reactionVolumeUl: "20",
  additive: "yellow-sample-buffer",
});
assert(powertrackBuffer.values.yellow_sample_buffer_uL === 0.5, "PowerTrack Yellow Sample Buffer stoichiometry drift");

const kod = resolveFlankingNumericPreview({
  moduleId: "long-range-pcr",
  protocol: "toyobo-kod-long-kml101",
  targetLengthKb: "20",
});
assert(kod.values.extension_seconds_per_kb === 10 && kod.values.extension_time_sec === 200, "KOD Long length-conditioned extension drift");

const qiacuity = resolveFlankingNumericPreview({ moduleId: "digital-pcr", protocol: "qiagen-qiacuity-eg" });
assert(qiacuity.unresolved.some((entry) => entry.id === "qiacuity-nanoplate-format"), "QIAcuity must fail closed without Nanoplate context");
const incompatibleConsumable = resolveFlankingNumericPreview({
  moduleId: "digital-pcr",
  protocol: "bio-rad-qx700-naica-evagreen",
  digitalPlatformId: "bio-rad-qx700",
  digitalConsumableId: "qiacuity-26k",
});
assert(incompatibleConsumable.issues.some((entry) => entry.field === "digitalConsumableId"), "browser must reject dPCR platform/consumable cross-product drift");
const nioNaica = resolveFlankingNumericPreview({
  moduleId: "digital-pcr",
  protocol: "bio-rad-qx700-naica-evagreen",
  digitalPlatformId: "bio-rad-nio",
  digitalConsumableId: "qx700-rdg16",
});
assert(!nioNaica.issues.some((entry) => entry.field === "digitalPlatformId" || entry.field === "digitalConsumableId"), "Nio + RDG16 + naica EvaGreen must remain source-backed");
const nioWrongChemistry = resolveFlankingNumericPreview({
  moduleId: "digital-pcr",
  protocol: "bio-rad-qx700-evagreen-supermix",
  digitalPlatformId: "bio-rad-nio",
  digitalConsumableId: "qx700-rdg16",
});
assert(nioWrongChemistry.issues.some((entry) => entry.field === "digitalPlatformId"), "dedicated QX700 EvaGreen Supermix must fail closed on Nio");
const absoluteQ = resolveFlankingNumericPreview({
  moduleId: "digital-pcr",
  protocol: "not-selected",
  digitalPlatformId: "thermo-absolute-q",
  digitalConsumableId: "absolute-q-map16",
});
assert(absoluteQ.issues.some((entry) => entry.field === "digitalPlatformId" && String(entry.message).includes("Pair+Probe")), "Absolute Q must route to Pair+Probe in dye Flanking");

const rpa = resolveFlankingNumericPreview({
  moduleId: "rpa",
  protocol: "thermo-lyo-ready-rpa",
  rpaMultiplex: true,
  rpaTemperatureC: "40",
  rpaTimeMin: "25",
  rpaBstUnitsPerUl: "0.05",
  fromRna: true,
});
assert(rpa.values.primer_each_nM === 100, "RPA multiplex primer starting point drift");
assert(rpa.values.reverse_transcriptase_U_per_uL === 2, "RT-RPA component projection drift");
assert(rpa.issues.length === 0, "valid RPA source-conditioned scenario must not produce numeric issues");

const colonyUnresolved = resolveFlankingNumericPreview({
  moduleId: "colony-pcr",
  protocol: "neb-onetaq-hotstart-m0488-colony",
  preparation: "direct-transfer",
});
assert(colonyUnresolved.unresolved.some((entry) => entry.id === "m0488-colony-lysis-time"), "M0488 must not invent a 2–5 minute colony lysis duration");

const before = resolveFlankingNumericPreview({ moduleId: "standard-pcr", protocol: "neb-onetaq-hot-start-m0484", reactionVolumeUl: "25" });
const after = resolveFlankingNumericPreview({ moduleId: "standard-pcr", protocol: "neb-onetaq-hot-start-m0484", reactionVolumeUl: "50" });
assert(diffFlankingNumericPreview(before, after).some((change) => change.key === "reaction_volume_uL"), "Flanking recipe-diff regression");
assert(after.sequenceDecisionImpact === "none", "bench numeric recipe must not silently alter sequence ranking");

console.log("FLANKING_WEB_NUMERIC_CONTRACT=PASS");
