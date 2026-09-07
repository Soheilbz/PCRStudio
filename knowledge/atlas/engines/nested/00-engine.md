# Nested PCR Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `nested` |
| Scope | coupled outer and inner primer pairs |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns round identity, nesting relation, transfer topology and claim boundary. Nested PCR owns round-specific values and the executable two-tube workflow; one-tube literature variants are reference-only in Generation-1.

## Scope

Nested PCR performs a first amplification followed by a second amplification inside the first product; the inner pair therefore changes specificity and contamination risks rather than merely adding two primers ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/), [Snounou et al.](https://pubmed.ncbi.nlm.nih.gov/8264734/)).

The engine must preserve outer/inner labels, product containment, explicit two-tube transfer assumptions, cross-round interactions and validation state; a one-tube request is a typed non-executable boundary ([Shatleh-Rantisi et al.](https://doi.org/10.1016/j.heliyon.2020.e03246)).

## Shared execution contract

```text
request → typed two-round/two-tube intake → outer candidate search → inner search inside outer
        → containment and interaction checks → round-labelled scheme,
          cycling/transfer handoff and provenance
```

**Internal execution invariant.** No inner pair means no nested result; the engine never falls back to a single pair.

## Claim boundary

Nested geometry may support an in-silico specificity rationale, but it does not establish contamination-free handling, transfer efficiency, yield, false-positive rate or clinical performance ([Green & Sambrook](https://pubmed.ncbi.nlm.nih.gov/30710023/), [Longo et al.](https://doi.org/10.1016/0378-1119(90)90145-h)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | round topology and claim contract | nested-PCR numeric values |
| `01-tools.md` | round, transfer and interaction vocabulary | module defaults or protocol values |
| numbered module records | nested-PCR values, evidence and validation | duplicate shared rules |
