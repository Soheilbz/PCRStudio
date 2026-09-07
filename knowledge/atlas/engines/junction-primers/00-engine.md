# Junction Primers Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `junction-primers` |
| Scope | primers that create or interrogate sequence junctions between declared fragments |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-08-30 |

**Internal ownership record.** This file owns fragment order, junction identity, overlap accounting and provenance. Gibson Assembly owns overlap and reaction values.

## Scope

Junction-primer design is an assembly problem: fragments are ordered and joined through designed homology, not merely amplified as one target. Gibson et al. describe a one-pot assembly in which exonuclease exposes complementary ends followed by polymerase fill-in and ligation ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)).

The engine must keep the input fragment graph, junction sequences, orientation, overlap identity, fragment-generation method and assembly validation separate. A syntactically complementary junction does not establish correct multi-fragment assembly or clone identity, and chemistry-specific end-processing capabilities must never be inferred from the generic junction graph ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)).

## Shared execution contract

```text
request → typed fragment intake → order/orientation validation → junction extraction
        → overlap candidate checks → interaction and uniqueness review
        → assembled-order report, protocol handoff and provenance
```

**Internal execution invariant.** Missing fragment order or an ambiguous junction is refused; the engine never invents an order from file order.

## Claim boundary

The result may report the designed junctions and sequence-level compatibility. Assembly efficiency, full-length product, transformation and clone correctness require a named reaction and laboratory validation ([Gibson et al.](https://pubmed.ncbi.nlm.nih.gov/19363495/)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | fragment graph, junction and claim contract | Gibson-specific overlap values |
| `01-tools.md` | fragment, overlap and assembly tool vocabulary | numeric defaults or protocol values |
| numbered module records | module-specific assembly chemistry and evidence | duplicate shared rules |
