# Consensus Pair Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `consensus-pair` |
| Scope | an alignment-derived degenerate primer pair for a declared sequence family |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns only the contract shared by consensus-derived pair designs. The module record owns alignment curation, degeneracy limits, coverage targets, chemistry branches, numeric evidence and validation values.

## Scope

Consensus-primer design starts from multiple related sequences, identifies conserved regions and represents tolerated variation with degenerate bases. It is therefore a family-coverage problem rather than a single-template pair problem ([Campos & Quesada](https://pubmed.ncbi.nlm.nih.gov/28540700/), [FAS-DPD](https://pmc.ncbi.nlm.nih.gov/articles/PMC3600133/)).

The engine must keep alignment provenance, represented records, ambiguity policy, primer degeneracy, physical oligo formulation and target-coverage evidence separate. A consensus pair that matches a declared alignment is not automatically universal for unsampled taxa or variants; the National Academies BioWatch PCR framework, hosted on NCBI Bookshelf, likewise separates assay design evidence from empirical inclusivity/exclusivity and performance validation ([BioWatch PCR assay framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/)).

A single multiple-sequence alignment must not be treated as uncertainty-free. When candidate primer sites are sensitive to alignment method or parameterization, the engine must preserve the exact aligner/version/parameters and either compare alternative alignments or report an alignment-uncertainty warning. MUSCLE5 explicitly supports alignment ensembles for assessing sensitivity to alignment error, and the current MAFFT distribution documents strategy- and version-specific behavior ([MUSCLE5](https://pubmed.ncbi.nlm.nih.gov/36379955/), [MAFFT current software page](https://mafft.ddbj.nig.ac.jp/alignment/software/)).

## Shared execution contract

```text
request → typed alignment intake → record/provenance curation → orientation and alignment QC
        → conserved-window search → explicit ambiguity/degeneracy construction
        → concrete-member thermodynamic and interaction checks within declared computational bounds
        → completed-pair represented-record coverage → bounded non-target review
        → role-labelled pair, physical-formulation metadata, coverage report and provenance
```

**Internal execution invariant.** The engine refuses malformed or ambiguously scoped alignments and never silently replaces an alignment with one representative sequence. Gaps, unresolved source characters and explicit mixed-base output are distinct states and must not be silently converted into one another.

**Thermodynamic invariant.** A degenerate IUPAC string is not one concrete oligonucleotide for nearest-neighbour calculations. The engine must either expand concrete members within its declared computational boundary or state that thermodynamic/interaction evaluation was bounded. Per-oligo member count, forward×reverse member-pair interactions and self-interaction counts are distinct combinatorial quantities.

## Claim boundary

The result may report exact or explicitly mismatch-modelled coverage against the supplied alignment, bounded specificity against named background resources and sequence-level warnings. It must not claim population-wide universality, taxonomic completeness, equal amplification of all members, measured sensitivity, measured specificity or clean wet-lab amplification without a defined panel and experimental validation ([Campos & Quesada](https://pubmed.ncbi.nlm.nih.gov/28540700/), [BioWatch PCR assay framework](https://www.ncbi.nlm.nih.gov/books/NBK305487/), [FDA nucleic-acid sequence validation guidance](https://www.fda.gov/media/121751/download)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | shared alignment, coverage, provenance, physical-mixture, computational-boundary and claim contract | module-specific degeneracy or numeric values |
| `01-tools.md` | alignment, consensus, degenerate-design and pair-search tool vocabulary | resolved ranges, thresholds or module defaults |
| numbered module records | module-specific values, evidence, implementation, current database/tool branches and validation boundary | a second copy of this shared contract |
