# Discriminating Pair Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `discriminating-pair` |
| Scope | allele- or genotype-discriminating primer geometry |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |
| Scientific-documentation audit | `AUDITED-CURRENT-RUNTIME`; canonical science and executable runtime cross-checked |

**Internal ownership record.** This file owns the shared variant, allele, product and evidence contract. ARMS, tetra-primer ARMS and KASP own their chemistry and readout-specific values.

## Scope

Allele-discriminating PCR deliberately makes the primer extension outcome depend on a specified variant or allele, so the variant position, allele sequence and intended genotype interpretation are first-class inputs ([Newton et al.](https://pubmed.ncbi.nlm.nih.gov/2785681/), [Ye et al.](https://pubmed.ncbi.nlm.nih.gov/11522844/)).

The engine must distinguish a sequence match from a measured genotype call. Mismatch identity, position, polymerase, primer orientation and reaction conditions affect discrimination and cannot be collapsed into one universal terminal-mismatch rule ([Kwok et al.](https://pubmed.ncbi.nlm.nih.gov/2179874/), [Stadhouders et al.](https://pubmed.ncbi.nlm.nih.gov/19948821/)).

## Shared execution contract

```text
request → typed variant/allele intake → orientation and allele validation
        → allele-specific candidate generation → competing-allele review
        → product-size/channel separation → genotype interpretation boundary
        → validation plan and provenance
```

**Internal execution invariant.** The engine refuses missing or contradictory allele definitions and never reports an allele call from a primer score alone.

## Claim boundary

The result may report intended allele geometry and in-silico competition. Final genotyping requires positive/negative controls, representative samples, call clustering or gel interpretation and an independent confirmation strategy ([Medrano & de Oliveira](https://pubmed.ncbi.nlm.nih.gov/24519268/), [Cuppen](https://pubmed.ncbi.nlm.nih.gov/21357174/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | shared variant, competition and claim contract | chemistry-specific primer or readout values |
| `01-tools.md` | variant, primer and readout vocabulary | module defaults and numeric thresholds |
| numbered module records | ARMS/KASP-specific geometry, evidence and validation | duplicate shared rules |
