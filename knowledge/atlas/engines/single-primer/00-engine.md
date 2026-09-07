# Single Primer Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `single-primer` |
| Scope | one direction-specific primer for extension, end capture or sequencing |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns direction, target/read boundary and one-primer output. RACE and sequencing-primer records own their chemistry and read-length values.

## Scope

Single-primer workflows are not ordinary pair amplification. RACE uses a gene-specific primer with an adaptor or tail to recover an unknown transcript end, while cycle sequencing uses one primer to initiate a read from a known binding site ([Matz et al.](https://pubmed.ncbi.nlm.nih.gov/31043556/), [Primer3 manual](https://primer3.org/manual.html)).

The engine must preserve direction, known/unknown boundary, template type, read or capture purpose and ordered tail/adaptor semantics. A single primer cannot be reported as a two-sided amplicon pair without an explicit downstream method ([Matz et al.](https://pubmed.ncbi.nlm.nih.gov/31043556/)).

## Shared execution contract

```text
request → typed direction/purpose intake → target and boundary validation
        → single-primer search → structure/specificity review → direction-labelled
          oligo, protocol/validation handoff and provenance
```

**Internal execution invariant.** The engine refuses a missing direction or target boundary and never invents a second primer.

## Claim boundary

The result may report a candidate binding site and direction. It cannot establish full-length transcript recovery, read quality, processivity, sample identity or end completeness without the selected laboratory workflow ([Matz et al.](https://pubmed.ncbi.nlm.nih.gov/31043556/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | one-primer direction and claim contract | RACE/sequencing values |
| `01-tools.md` | single-primer and read vocabulary | module protocol defaults |
| numbered module records | RACE/sequencing values, evidence and validation | duplicate shared rules |
