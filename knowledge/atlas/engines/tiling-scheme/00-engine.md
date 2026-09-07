# Tiling Scheme Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `tiling-scheme` |
| Scope | an ordered multiplex primer scheme covering a long target by overlapping amplicons |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns coverage topology, pool assignment, overlap accounting and claim boundary. The tiled-scheme module owns target class, scheme values and readout/validation constraints.

## Scope

Tiled amplicon sequencing uses neighbouring overlapping amplicons to cover a long target, commonly dividing primers into alternating pools to reduce short overlap products and primer interactions ([ARTIC primer-scheme specification](https://artic-network.github.io/primerscheme-specs/pdf/primerscheme.pdf), [Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/)).

The engine must preserve amplicon order, strand, overlap, pool identity, primer interaction state, variant coverage and versioned scheme provenance. Complete nominal coverage does not guarantee uniform depth or variant recovery ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/), [Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)).

## Shared execution contract

```text
request → typed target/scheme intake → coverage window generation → primer candidates
        → overlap/pool/interactions → variant-risk review → ordered scheme,
          coverage report, sequencing handoff and provenance
```

**Internal execution invariant.** The engine refuses uncovered intervals, duplicate pool identity or ambiguous amplicon order instead of silently claiming complete coverage.

## Claim boundary

The result may report nominal sequence coverage and predicted interactions. It must not claim uniform sequencing depth, unbiased variant detection, consensus accuracy or clinical performance without run-level data ([Itokawa et al.](https://pubmed.ncbi.nlm.nih.gov/32946527/), [Olivar](https://pubmed.ncbi.nlm.nih.gov/39060254/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | coverage, overlap and pool contract | module-specific scheme values |
| `01-tools.md` | tiling, pool and sequencing vocabulary | numeric defaults or platform claims |
| numbered module records | module-specific scheme, evidence and validation | duplicate shared rules |
