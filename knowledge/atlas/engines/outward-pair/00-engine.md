# Outward Pair Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `outward-pair` |
| Scope | outward-facing primers around a declared cut or circular-template region |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns circular topology, cut geometry, outward orientation and claim boundary. Inverse PCR owns restriction/circularization and product values.

## Scope

Inverse PCR uses primers that point away from one another on a circularized template to amplify sequence flanking a known region; restriction digestion and intramolecular ligation are part of the physical workflow, not optional naming ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/)).

The engine must preserve template topology, cut/junction identity, primer orientation, expected product span and any restriction or ligation handoff. An outward pair on a linear FASTA is not automatically an inverse-PCR experiment ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/), [Huang](https://pubmed.ncbi.nlm.nih.gov/7866865/)).

## Shared execution contract

```text
request → typed circular/cut intake → outward orientation check → candidate search
        → product and restriction-junction review → ordered pair, protocol handoff,
          validation plan and provenance
```

**Internal execution invariant.** A missing cut or circularization context is reported as an unresolved workflow input, not silently treated as ordinary inward-facing PCR.

## Claim boundary

The result may report outward geometry and sequence-level products. It cannot establish complete digest, circularization, background-fragment selection, PCR yield or junction identity without laboratory evidence ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | topology and outward-orientation contract | inverse-PCR numeric values |
| `01-tools.md` | cut, circle and outward-pair vocabulary | protocol defaults |
| numbered module records | inverse-PCR values, evidence and validation | duplicate shared rules |
