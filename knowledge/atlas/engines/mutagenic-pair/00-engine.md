# Mutagenic Pair Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `mutagenic-pair` |
| Scope | primers that encode a declared sequence change during amplification |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns edit identity, reference/edited sequence comparison, orientation and claim boundary. Site-directed mutagenesis owns its primer geometry and post-PCR treatment.

## Scope

Site-directed mutagenesis uses primers that deliberately encode a substitution, insertion or deletion and requires comparison against the parental template; the resulting product is not an ordinary amplicon claim ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/), [Qi et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7351327/)).

The engine must preserve the exact edit, reference sequence, edited sequence, primer orientation, plasmid/circle topology and polymerase/post-PCR workflow. A primer containing the requested letters is not proof that the recovered clone carries only that edit ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)).

## Shared execution contract

```text
request → typed reference/edit intake → edited-sequence construction
        → mutagenic-primer geometry → whole-product and structure review
        → parental-template removal handoff → clone confirmation plan and provenance
```

**Internal execution invariant.** The engine refuses an edit that is absent, ambiguous or outside the declared template and never silently changes a substitution into an indel.

## Claim boundary

The result may report the intended edit geometry and sequence-level checks. PCR completion, parental-template depletion, transformation and clone sequence confirmation remain experimental ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/), [Qi et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7351327/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | edit and claim contract | method-specific primer values |
| `01-tools.md` | edit, topology and validation vocabulary | numeric defaults or kit instructions |
| numbered module records | mutagenesis-specific geometry, chemistry and evidence | duplicate shared rules |
