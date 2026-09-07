# PCRStudio Scientific Risk Register

Audit state as of: 2026-09-05

**Source release blockers open: 0.** Linux runtime/database qualification remains an explicit host gate and is not converted into a source claim.

| ID | Severity | Status | Area | Risk | Control |
|---|---|---|---|---|---|
| `R-SCI-001` | P0 | closed | scientific-policy | PRIMARY backend/tool substitution can change the scientific algorithm silently. | Scientific strict forbids PRIMARY substitution; Tiled PrimalScheme3 fails closed. |
| `R-SCI-002` | P0 | closed | specificity | Smoke/test databases could be mistaken for production specificity. | Approved-reference scope + FASTA/index fingerprints + limited-evidence semantics. |
| `R-SCI-003` | P0 | closed | optional-tools | OPTIONAL evidence could alter deterministic selection. | OPTIONAL/REFERENCE tools are advisory only; ViennaRNA accessibility removed from flanking ranking. |
| `R-SCI-004` | P0 | closed | bench-protocol | UI/backend could fabricate generic cycling or transfer one vendor recipe to another when kit/platform authority is unresolved. | Missing cycling stays unresolved; Standard/qPCR/long-range/dPCR/RPA named overlays retain assay-specific bench authority while proprietary buffer thermodynamics are not reconstructed. |
| `R-SCI-005` | P0 | closed | species-specific | A single representative target, missing panel provenance or permissive severity tuning could support an overclaimed species-specific result. | All executable modes require inclusivity + exclusion panels, panel provenance and selection rationale; exact panel contradictions and any complete unintended predicted product fail closed. |
| `R-SCI-006` | P0 | closed | supply-chain | Scientific Python tool identity could drift despite top-level version pins. | Verified wheel hashes plus Linux-approved resolved freeze fingerprint. |
| `R-SCI-007` | P1 | controlled-boundary | pydna | pydna capabilities exceed the current adapter implementation. | Current claim limited to independent PCR-product simulation; construct/digest/ligation are backlog only. |
| `R-SCI-008` | P1 | controlled-boundary | multiplex | Primer-pair multiplex engine cannot model probe channels, dPCR clusters or ARMS allele semantics. | Multiplex advertised only for Standard/Colony/Species-specific until dedicated semantics exist. |
| `R-SCI-009` | P1 | controlled-boundary | RPA/KASP | Modified-probe RPA formats or KASP plus/minus branches could be approximated with the wrong oligo/topology contract. | Exo/Nfo/Fpg/SIBA remain typed refusals. KASP plus/minus is now a distinct junction-aware CURRENT contract and must never fall back to ordinary diploid-SNV geometry or claim Kraken equivalence. |
| `R-REL-001` | P0-release-qualification | open-host-gate | Linux-runtime | Source audit cannot prove executables, builds, UI rendering or 21-module runtime behavior on the supported Linux host. | scripts/run-linux-qualification.py + canonical module acceptance matrix; release remains PUBLIC-SOURCE until passed. |
| `R-REL-002` | P0-release-qualification | open-host-gate | production-database | Source bundle cannot prove the user's chosen production reference database scope/indexes exist on Linux. | configure-specificity-database.py + approved-reference manifest/hash verification. |
