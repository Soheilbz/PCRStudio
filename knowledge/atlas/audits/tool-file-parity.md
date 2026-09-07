# Tool-file parity and production-contract audit

Last audited: **2026-08-30**

Status: **PASS after remediation**.

This audit was triggered because `flanking-pair/01-tools.md` contained substantially deeper upstream field vocabulary than several peer engine tool files. The remediation standard is **semantic parity, not identical line count**: each of the 11 engine tool files must independently define its execution graph, engine-owned inputs, relevant tool/parameter map, normalized outputs, coordinate/chemistry rules, parser/database provenance, failure/fallback/refusal semantics, determinism/cache behavior, license/privacy/deployment boundary and regression fixtures.

## Architectural correction

Tool identity/version/artifact policy is global, but runtime role is engine-scoped. `toolchain-manifest.json` now stores catalog disposition, while `engine-tool-contracts.json` resolves the executable role per engine. This removes the prior ambiguity where, for example, PrimerPooler is a required validator in `tiling-scheme` but only optional in `nested`.

## Acceptance criteria

- all 11 `01-tools.md` inherit the shared runtime, toolchain and engine-binding contracts;
- no active compound/noncanonical role values;
- every engine has a production execution graph and normalized result contract;
- every production/validator path defines explicit error/fallback/refusal behavior;
- coordinates use the canonical 0-based half-open model and retain source-tool coordinates;
- exact tool artifact digest is required at build/install time for local production dependencies;
- database-backed validation requires a frozen database manifest and checksum;
- remote/browser/vendor tools are reference-only unless explicitly promoted by a later contract;
- every engine defines regression fixtures that exercise topology/coordinates, no-candidate/error states, tool/parser/database drift and engine-specific edge cases.

Line-count equality is not an acceptance criterion because different engines expose different upstream interfaces; completeness of required contract families is.

## Post-remediation depth check

| Engine | `01-tools.md` lines | Required contract families |
| --- | ---: | --- |
| `consensus-pair` | 283 | PASS |
| `discriminating-pair` | 224 | PASS |
| `flanking-pair` | 514 | PASS |
| `junction-primers` | 225 | PASS |
| `loop-set` | 221 | PASS |
| `mutagenic-pair` | 214 | PASS |
| `nested` | 211 | PASS |
| `outward-pair` | 207 | PASS |
| `pair-and-probe` | 233 | PASS |
| `single-primer` | 205 | PASS |
| `tiling-scheme` | 235 | PASS |

The range reflects real interface complexity, not missing contract families: `flanking-pair` retains the full Primer3 field inventory, while narrower engines document only the tool fields they can actually own or execute. All files meet the same acceptance checklist.

