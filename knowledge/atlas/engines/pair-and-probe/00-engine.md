# Pair and Probe Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `pair-and-probe` |
| Scope | primer pair plus a typed internal detection oligo |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns pair/probe topology, joint specificity and provenance. Hydrolysis-probe qPCR owns probe chemistry, readout and numeric values.

## Scope

Hydrolysis-probe assays use a fluorescently labelled probe in addition to primers, and the monitoring chemistry changes the fluorescence kinetics and interpretation relative to DNA-binding dyes ([Pavšič et al.](https://pubmed.ncbi.nlm.nih.gov/25253910/), [MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)).

The engine must evaluate the primer pair and probe together: probe placement, orientation, target coverage, secondary structure, primer–probe interactions and label/quencher identity are distinct fields. A plain primer pair cannot be promoted to a finished probe assay ([MIQE](https://pubmed.ncbi.nlm.nih.gov/19246619/)).

## Shared execution contract

```text
request → typed target and probe chemistry → pair/probe candidate generation
        → joint structure/specificity checks → readout-labelled result,
          quantitative validation plan and provenance
```

**Internal execution invariant.** A missing probe chemistry or invalid orientation is refused; the engine never fabricates labels or quencher positions.

## Claim boundary

The result may report sequence and chemistry compatibility. It must not claim efficiency, unique amplification, Cq validity, LOD/LOQ or fluorescence performance without MIQE-aligned experimental validation ([MIQE 2.0](https://pubmed.ncbi.nlm.nih.gov/40272429/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | joint pair/probe contract and claim boundary | probe-specific numeric defaults |
| `01-tools.md` | probe, primer and readout vocabulary | resolved chemistry values |
| numbered module records | module-specific probe chemistry, evidence and validation | duplicate shared rules |
