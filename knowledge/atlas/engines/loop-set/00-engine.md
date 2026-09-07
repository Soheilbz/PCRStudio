# Loop Set Engine — shared contract

| Field | Value |
| --- | --- |
| Engine ID | `loop-set` |
| Scope | coordinated isothermal primer sets with named structural roles |
| Status | implemented; bounded in-silico scope |
| Last reviewed | 2026-09-02 |

**Internal ownership record.** This file owns role identity, set topology, feasibility, provenance and claim boundaries. LAMP owns role-specific chemistry and values.

## Scope

Loop-mediated amplification uses multiple primers that recognize several regions and relies on a strand-displacing polymerase; the set must therefore be designed and judged as a coordinated geometry, not as an ordinary pair ([Notomi et al.](https://doi.org/10.1093/nar/28.12.e63), [Nagamine et al.](https://doi.org/10.1006/meth.2002.1264)).

The engine must preserve role labels, orientation, region order, loop relationships, set-level interactions and readout identity. A set that has the right count but the wrong role geometry is invalid ([Notomi et al.](https://doi.org/10.1093/nar/28.12.e63)).

## Shared execution contract

```text
request → typed target/geometry intake → role-window feasibility → role candidates
        → set assembly → bounded evidence-aware ranking
        → target-inclusivity review when a homologous target panel is supplied
        → finite or indexed six-region background-topology review
        → ordered set, protocol, validation plan and provenance
```

**Internal execution invariant.** Impossible geometry is refused by naming the missing relation; roles are never silently dropped.

## Generation-1 advanced LAMP invariants

- Whole-locus orientation is not assumed. Background specificity must detect the six required target-derived regions on either genomic orientation; a reverse-complement copy is canonicalized before geometry is evaluated.
- FIP/BIP ordered molecules are distinct from their genomic query regions. Synthetic junction linker sequence is part of whole-oligo structure/ordering evidence but is excluded from target/background genomic searches.
- A missing external validator result is `unresolved`, never evidence of a clean background. Finite pasted backgrounds and indexed database validation are distinct scopes and expose their own completeness/cap state. A pasted exclusion background above the direct LAMP limit is refused rather than silently substituted by a separately configured indexed database; genome-scale validation therefore requires an explicit approved indexed scope.
- Hairpin, self-dimer, cross-dimer and directed 3′-extendability are set-level risk/ranking evidence. They are not universal wet-lab pass/fail gates unless a future assay-specific validated rule explicitly says otherwise.
- Computational search budgets are provenance, not chemistry thresholds. If a half/core/outer/topology search is truncated, the result cannot claim global optimality or exhaustive specificity.

## Claim boundary

The result may report role geometry and sequence-level checks. It must not claim time-to-positive, clinical sensitivity, clean readout or non-target exclusion without chemistry- and matrix-specific validation ([Soroka et al.](https://doi.org/10.3390/cells10081931)).

## Document ownership

| Document | Owns | Must not own |
| --- | --- | --- |
| `00-engine.md` | role topology, set contract and claim boundary | LAMP-specific values |
| `01-tools.md` | role, set and readout vocabulary | numeric defaults or chemistry presets |
| numbered module records | module-specific geometry, chemistry and evidence | duplicate shared rules |
