# 21 module pipelines

Every design request follows the same system-level stages:

`UI → API validation → module profile → engine identity → input normalization → parameter resolution → candidate generation → assay hard filters → internal thermodynamics/background/inclusivity → deterministic ranking → independent mature-tool evidence → verification envelope → API schema → result UI/export`

The engine owns assay-specific candidate generation. The orchestration layer owns identity,
coordinates, tool roles, provenance and verification status. No validator is allowed to turn
"not run" into "passed".

| Module | Engine | Candidate authority | Assay-specific gates | Independent generation-1 evidence |
|---|---|---|---|---|
| standard-pcr | flanking-pair | Primer3 | product geometry, Tm/GC, structures, supplied background | MFEprimer + BLAST; PrimerPooler when multi-oligo |
| long-range-pcr | flanking-pair | Primer3 | long-product geometry, polymerase capability, extension constraints | MFEprimer + BLAST |
| colony-pcr | flanking-pair | Primer3 | short screen products, lysate/host/vector context | MFEprimer + BLAST |
| nested-pcr | nested | Primer3 outer then inner | containment, round-specific limits, cross-round interactions | MFEprimer + BLAST + optional PrimerPooler |
| inverse-pcr | outward-pair | Primer3 through topology wrapper | cut/circle reconstruction, outward orientation | MFEprimer + BLAST |
| qpcr-sybr | flanking-pair | Primer3 | short qPCR product, dye-compatible quality gates | MFEprimer + BLAST |
| qpcr-probe | pair-and-probe | Primer3 + internal probe wrapper | probe between primers, probe Tm/5′-G/structure, primer-probe interactions | MFEprimer + BLAST; optional ViennaRNA |
| digital-pcr | flanking-pair | Primer3 | short product, digital-PCR reaction constraints | MFEprimer + BLAST |
| arms-pcr | discriminating-pair | Primer3 + allele wrapper | 3′ allele identity, deliberate mismatch logic, differential extension | MFEprimer + BLAST |
| tetra-primer-arms | discriminating-pair | Primer3 + tetra wrapper | four-primer geometry and diagnostic band separation | MFEprimer + BLAST + multi-oligo interaction audit |
| kasp | discriminating-pair | Primer3 + KASP wrapper | KASP empirical profile, allele tails, allele/common-primer geometry | MFEprimer + BLAST |
| species-specific-pcr | flanking-pair | Primer3 | required exclusion background + target inclusivity | MFEprimer + BLAST, target-aware interpretation required |
| lamp | loop-set | internal LAMP role enumerator + Primer3 thermodynamics | F3/F2/F1c/B1c/B2/B3 and LF/LB geometry, set interactions | MFEprimer + BLAST |
| rpa | flanking-pair | Primer3 | RPA-compatible chemistry and long-primer profile | MFEprimer + BLAST |
| universal-primers | consensus-pair | MAFFT → consensus resolver → Primer3 | conservation, degeneracy, member coverage | MFEprimer + BLAST |
| tiled-scheme | tiling-scheme | pinned PrimalScheme3 3.3.0 PRIMARY backend | coverage, overlap, pool separation, variant risk, interaction audit, repairability | PrimerPooler + MFEprimer + BLAST |
| race | single-primer | Primer3 + boundary/adaptor wrapper | direction/read-boundary geometry | MFEprimer + BLAST |
| sequencing-primer | single-primer | Primer3 | readable distance and direction | MFEprimer + BLAST |
| gibson-assembly | junction-primers | Primer3 annealing cores + junction composer | overlap/junction reconstruction, whole-oligo structure | MFEprimer + BLAST; optional pydna simulation |
| restriction-cloning | flanking-pair | Primer3 + restriction/tail layer | enzyme sites, 5′ additions, translated product | MFEprimer + BLAST |
| site-directed-mutagenesis | mutagenic-pair | Primer3 + edit wrapper | edit normalization, overlap/edit placement, edited-product verification | MFEprimer + BLAST; optional pydna simulation |

## Selection semantics

A result is ranked only after engine hard constraints and the background/inclusivity evidence that
can be interpreted unambiguously from the request. External database tools are independent
validators. A BLAST hit by itself is not automatically an off-target PCR product: target identity,
orientation and pairing are required for that claim. When that context is absent the UI reports
`verification-incomplete` rather than inventing a PASS or rejection.

## Fallback semantics

Release execution is fail-closed. A PRIMARY scientific backend is never silently substituted after failure. Tiled-scheme release execution uses pinned PrimalScheme3 3.3.0; PCRStudio's deterministic internal walker is an explicitly selected development backend only and cannot inherit release-grade verification status. Independent VALIDATOR tools/databases are likewise mandatory under strict scientific policy. OPTIONAL evidence may be absent without changing candidate validity, but the absence is recorded.

## Runtime timing

Independent MFEprimer, BLAST and PrimerPooler validators run in separate native subprocess workspaces and are scheduled concurrently. Their completion order is normalized before serialization, so concurrency does not make the JSON nondeterministic. The Rust worker default deadline is 120 s and the accepted `PCR_WORKER_TIMEOUT_SECONDS` range is 1–299 s; the parent HTTP request deadline is about 300 s and must remain larger than the worker deadline. Values such as the historical 420/450 s pair are no longer valid in R17.

## Ordered molecule versus annealing core

Specificity and interaction are deliberately not computed on the same sequence when an assay adds a 5' extension. `order_sheet.sequence` is what is purchased. `order_sheet.annealing_sequence` is what is searched against the original template/background. `order_sheet.tail_sequence` records the non-template 5' extension. MFEprimer/BLAST specificity use the annealing core; MFEprimer dimer/hairpin and PrimerPooler use the full ordered molecule.
