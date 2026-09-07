# Site-directed mutagenesis — mutagenic-pair engine record

| Field | Value |
| --- | --- |
| Profile ID | `site-directed-mutagenesis` |
| Runtime profile status | experimental |
| Goal | `engineer` |
| Modifiers | `tails` |
| Purpose modes | `cloning` is the default and only accepted downstream-use mode |
| Executable chemistry | topology-separated Q5/E0554; QuikChange Lightning single-site; QuikChange Lightning Multi; NEBuilder multi-site route |
| Evidence status | topology-scoped computational design/routing; recovered-clone genotype remains wet-lab/sequencing evidence |
| Last cold-audited | 2026-08-31 |

## Atlas overlay

The CURRENT mutagenesis engine is topology-separated rather than a Q5-only abstraction. Q5/E0554 remains a back-to-back non-overlapping whole-plasmid branch; QuikChange Lightning single-site uses its complementary opposing-primer topology and Agilent-specific Tm formula; Lightning Multi uses one non-overlapping mutagenic primer per site on the same template strand; and NEBuilder multi-site is a typed route to the Junction Primers assembly engine. No topology borrows another kit's Tm rule or protocol numbers ([NEB Q5 Site-Directed Mutagenesis Kit](https://www.neb.com/en-us/products/e0554-q5-site-directed-mutagenesis-kit), [Agilent QuikChange Lightning manual](https://www.agilent.com/cs/library/usermanuals/public/210518.pdf), [Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf), [NEBaseChanger](https://nebasechanger.neb.com/)).

## Scope

Generation 1 implements **separate named mutagenesis topologies**, not a generic interchangeable primer recipe. Q5/E0554 supports substitutions, deletions and source-backed 5′-tail insertion handling, including split tails through `100 nt`; QuikChange Lightning single-site and Lightning Multi follow their own primer geometries and Tm/kit rules; NEBuilder multi-site emits an exact edited-construct/assembly routing plan rather than pretending to be an orderable back-to-back primer pair. Requests outside a selected topology remain explicit route/refusal states. ([NEB Q5 Site-Directed Mutagenesis Kit](https://www.neb.com/en-us/products/e0554-q5-site-directed-mutagenesis-kit), [Agilent QuikChange Lightning manual](https://www.agilent.com/cs/library/usermanuals/public/210518.pdf), [Agilent Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf))

The requested edit is first-class input and the recovered molecule is
reconstructed in silico.  Primer design does not prove clone purity, absence of
secondary changes, transformation success or the final genotype; sequencing of
the recovered clone remains required ([NEB Q5 Site-Directed Mutagenesis Kit](https://www.neb.com/en-us/products/e0554-q5-site-directed-mutagenesis-kit)).

## Executable Q5/E0554 contract

| Dimension | Scientific-Strict decision | Evidence boundary |
| --- | --- | --- |
| Topology | back-to-back, non-overlapping primers | Q5-specific; not transferable to overlapping/complementary QuikChange |
| Substitution | mutagenic primer contains the substitution with `>=10 nt` template-complementary sequence on its 3′ side; ranking prefers a central edit but centrality is not a validity law | current NEB Q5 primer-design guidance |
| Deletion | primers flank the declared deleted interval | deletion boundaries define geometry; no arbitrary sliding flank |
| Insertion `<=6 nt` | insertion is a 5′ tail on the forward primer; annealing core is stored separately | current Q5 small-insertion guidance |
| Insertion `7–100 nt` | executable Q5 split-tail branch | distribute the inserted sequence across the two 5′ tails within the source-backed per-primer tail boundary; preserve exact edited-construct reconstruction |
| Insertion `>100 nt` | route/refusal from Q5 | route to an assembly strategy such as NEBuilder/Junction Primers rather than inventing an oversized Q5 topology |
| Ordered primer length | `15–60 nt` executable Gen-1 synthesis envelope | primers above `60 nt` need a purification/ordering handoff and are not auto-returned here |
| Template size | `<=20 kb` executable Gen-1 envelope | preserves the current vendor capability boundary without claiming a universal physical maximum |
| Bench annealing temperature | **not inferred from PCRStudio screening Tm** | current Q5/NEBaseChanger guidance or an experimentally resolved gradient owns the bench decision |
| Recovery | strict branch requires named `neb-q5-e0554` | KLD/cycling belong to that named kit record |
| QuikChange Lightning single-site | executable separate topology | complementary opposing primers and Agilent-specific Tm formula; never relabel as Q5 |
| QuikChange Lightning Multi | executable separate topology | one non-overlapping mutagenic primer per site on the same template strand |
| NEBuilder multi-site | route-only | exact edited construct and fragment-routing plan are passed to Junction Primers |

## Runtime profile binding

| Profile field | Current binding |
| --- | --- |
| `polymerase` | `q5-sdm-screening` — reproducible Primer3 thermodynamic **calculation context**, not a reconstruction of the proprietary Q5 master mix |
| `defaultPurpose` / `purposes` | `cloning` / `[cloning]` |
| `chemistryFamily` | `neb-q5-e0554` |
| schema-only generic constraint keys | `tm_min`, `tm_opt`, `tm_max`, `length_min`, `length_opt`, `length_max`, `gc_min`, `gc_max`, `gc_clamp`, `max_end_gc`, `max_poly_x` |
| generic PCR `constraints` | schema-only locked placeholders; direct request overrides are refused in Scientific-Strict and do not define mutagenic validity |
| `post_amplification_protocol` | strict-required `neb-q5-e0554` |

## Parameter audit

| Parameter | Decision | Source-to-parameter record |
| --- | --- | --- |
| `edit_definition` | required and coordinate-normalized | mutation identity must be unambiguous before candidate generation |
| `Q5_MIN_3PRIME_COMPLEMENT` | `10 nt` | hard Q5 substitution geometry rule |
| `Q5_MIN_PRIMER_LENGTH` | `15 nt` | conservative executable lower bound consistent with current NEBaseChanger/Q5 design interface |
| `Q5_MAX_STANDARD_PRIMER_LENGTH` | `60 nt` | current Gen-1 auto-order boundary; longer oligos require explicit purification/ordering handling |
| `Q5_MAX_SMALL_INSERTION` | `6 nt` | upper boundary of the single-forward-tail branch |
| `Q5_MAX_SPLIT_INSERTION` | `100 nt` | source-backed split-tail envelope; larger insertions route to an assembly strategy |
| `Q5_DOCUMENTED_PLASMID_ENVELOPE` | `20,000 bp` | source-backed Gen-1 capability envelope, not a universal mutagenesis limit |
| thermodynamic screening | report template-facing, edited-product and reverse-primer values as evidence only | no screening Tm is converted into a bench cycling command |
| generic `flank` | **not executable** | removed because the former default was an unsourced tuning control |
| generic PCR Tm/GC/clamp overrides | **not executable** | Q5 topology is assay-specific; a new sourced/versioned branch is required instead of widening generic PCR constraints |
| clone validation | explicit downstream requirement | amplification/design never proves intended-only clone genotype |

## Named Q5/E0554 protocol overlay

The named E0554 record owns PCR reaction quantities, cycle structure and the
KLD recovery step.  These values remain coupled to the selected kit and are not
copied into generic mutagenesis or QuikChange.  PCRStudio's Primer3 screening
context is deliberately separate from this bench protocol: it supports
reproducible oligo thermodynamics but does not claim to recreate the proprietary
master-mix composition or to replace NEBaseChanger/current Q5 annealing
guidance ([NEB Q5 Site-Directed Mutagenesis Kit](https://www.neb.com/en-us/products/e0554-q5-site-directed-mutagenesis-kit)).

QuikChange Lightning single-site and Lightning Multi evidence below now binds to separate topology/protocol contracts. The citations remain kit-scoped evidence: Agilent-specific Tm and primer-geometry rules must not be copied into Q5/E0554 or NEBuilder routing ([Agilent QuikChange Lightning manual](https://www.agilent.com/cs/library/usermanuals/public/210518.pdf), [Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)).

## Deep-search enrichment — NEBuilder HiFi multi-site mutagenesis topology

Current NEBaseChanger explicitly provides a `Generate NEBuilder HiFi primers` path for multiple site-directed mutagenesis in a single assembly reaction, and NEB's tutorial distinguishes this from the Q5 single-site workflow. The current tool exposes a minimum primer length default of `15 nt` and minimum Tm default of `55 °C` for its primer-generation interface, but these tool settings belong to the selected NEBuilder/Q5 design mode and are not mutagenesis laws. PCRStudio should therefore route multi-site NEBuilder designs as an overlap-assembly mutagenesis topology with a distinct chemistry/protocol identifier rather than presenting them as ordinary back-to-back Q5 primers ([NEBaseChanger](https://nebasechanger.neb.com/), [NEBaseChanger tutorial](https://www.neb.com/en-gb/tools-and-resources/video-library/nebasechanger-primer-design-tool-tutorial)).

### Deep-search numeric evidence addendum

| Parameter ID | Exact value or rule | Scope / condition | Operational role | Evidence boundary |
| --- | --- | --- | --- | --- |
| `nebasechanger_nebuilder_multisite_branch` | current tool default minimum primer length `15 nt`; default minimum Tm `55 °C`; option generates NEBuilder HiFi primers for multiple site-directed mutagenesis in a single reaction | NEBaseChanger current multi-site/NEBuilder path | `adjacent mutagenesis topology`; require NEBuilder chemistry/protocol identity | Tool UI defaults are version-specific and must not replace Q5 or QuikChange rules. Sources: [NEBaseChanger](https://nebasechanger.neb.com/), [NEB tutorial](https://www.neb.com/en-gb/tools-and-resources/video-library/nebasechanger-primer-design-tool-tutorial) |

## Numeric evidence register

The following records preserve the named mutagenesis topology/protocol families as separate authorities. Their values are coupled to primer topology, template length, polymerase/kit and post-amplification treatment; they must not be merged into a generic mutagenesis recipe ([NEB Q5 Site-Directed Mutagenesis Kit E0554 manual](https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf?hash=F6C8A6A1AE8596E87A53D5474A8BB04C&lang=en&rev=685c2daead0a4c2986da6dbd32e3b685), [Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)).

| Parameter ID | Exact value or rule | Scope / condition | Operational role | Evidence boundary |
| --- | --- | --- | --- | --- |
| `q5_e0554_reaction` | NEB E0554 uses a `25 µL` PCR with `12.5 µL` 2X Q5 Master Mix, `1.25 µL` of each `10 µM` primer (`0.5 µM` final each), `1 µL` template at `1–25 ng/µL` (`1–25 ng` total) and `9.0 µL` water ([NEB Q5 E0554 manual](https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf?hash=F6C8A6A1AE8596E87A53D5474A8BB04C&lang=en&rev=685c2daead0a4c2986da6dbd32e3b685)). | NEB Q5 back-to-back exponential mutagenesis branch. | `kit-specific reaction record`; retain stock, final and total quantities. | These inputs do not apply to overlapping QuikChange or inverse-PCR workflows. |
| `q5_e0554_cycling_and_kld` | E0554 cycling: `98 °C/30 s`, then `25` cycles of `98 °C/10 s`, `50–72 °C/10–30 s` annealing and `72 °C/20–30 s/kb`, followed by `72 °C/2 min` and `4–10 °C` hold. KLD uses `1 µL` PCR product, `5 µL` 2X KLD buffer, `1 µL` 10X KLD mix and `3 µL` water, held `5 min` at room temperature ([NEB Q5 E0554 manual](https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf?hash=F6C8A6A1AE8596E87A53D5474A8BB04C&lang=en&rev=685c2daead0a4c2986da6dbd32e3b685)). | Named Q5/E0554 post-PCR recovery path. | `cycle and recovery overlay`; preserve both PCR and KLD stages. | The `50–72 °C` annealing range is protocol-resolved and must not be treated as a universal mutagenic-primer Tm rule. |
| `quikchange_multi_topology` | Agilent QuikChange Lightning Multi supports up to `5` simultaneous sites and a general method for plasmids up to `8 kb`; its supplied control is a `4 kb` plasmid with `3` independent reversion sites and reports `>55%` control efficiency ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Agilent multi-site same-strand, non-overlapping mutagenesis. | `vendor topology/capability record`; retain control design and efficiency context. | `>55%` is a supplied control observation, not a universal mutation success probability. |
| `quikchange_multi_primer_rules` | Primers are `25–45 bases`, Tm `≥75 °C`, mutation at least `10 bases` from either end, maximum `3` consecutive mismatch bases or `2` separated by at most `9` bases, minimum GC `40%`, and preferably a 3′ C/G; hairpins are reviewed at `≥55 °C` ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Agilent Multi primer-design contract. | `kit-specific primer constraints`; retain each rule independently. | These rules do not apply to Q5/E0554 or other mutagenesis topologies. |
| `quikchange_multi_reaction_and_template` | Standard Agilent Multi reaction is `25 µL`: `2.5 µL` 10X buffer, `50 ng` dsDNA for templates `≤5 kb` or `100 ng` for `>5 kb`, `100 ng` each primer for `1–3` primers or `50 ng` each for `4–5`, `1 µL` dNTP mix, `1 µL` enzyme and water to volume; QuikSolution is `0–0.75 µL` for `>5 kb` templates ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Agilent standard multi-site synthesis. | `template/primer loading overlay`; preserve site-count branch and size branch. | The quantities are not interchangeable with Q5's molar primer and template ranges. |
| `quikchange_multi_cycling_and_dpni` | Agilent uses `95 °C/2 min`, then `30` cycles of `95 °C/20 s`, `55 °C/30 s`, `65 °C/30 s/kb`, then `65 °C/5 min`; cool on ice for `2 min` to `≤37 °C`, add `1 µL` DpnI and incubate `37 °C/5 min`, then transfer `1.5 µL` into `45 µL` XL10-Gold cells ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Agilent standard Multi recovery path. | `cycle/DpnI/transformation overlay`; preserve order and volumes. | DpnI effectiveness depends on parental-template methylation and host history; the sequence engine cannot prove either. |
| `quikchange_multi_library_optimization` | Agilent's library optimization compares `25 µL` with `50–100 µL`, QuikSolution `0–3%` with `0–10%`, template `50–100 ng` with `100–500 ng`, and DpnI `5 min` with `1 h`; primer tuning may range from `2-` to `10-fold`, long-template QuikSolution `0–1.5 µL` with `≤0.75 µL` typical, and transformation may use up to `4 µL` treated reaction ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Agilent mutant-library optimization branch. | `optimization matrix`; retain each comparison rather than collapsing to one value. | These are library/optimization settings, not standard reaction defaults. |
| `quikchange_multi_control_readout` | The Agilent blue/white control uses `37 °C` for at least `16 h`, `80 µg/mL` X-gal and `20 mM` IPTG, or `100 µL` of `10 mM` IPTG plus `100 µL` of `2%` X-gal applied `30 min` before plating ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Control readout for the named manual. | `control-only record`; preserve as downstream validation metadata. | These numbers do not validate the user's mutation or replace sequencing of the recovered clone. |
| `q5_mutagenesis_annealing_offset` | For the NEB Q5 back-to-back arrangement, the annealing-temperature starting point is the calculated primer Tm plus `3 °C` ([NEB Q5 mutagenesis FAQ](https://www.neb.com/faqs/what-should-i-use-for-an-annealing-temperature-with-the-q5-site-directed-mutagenesis-kit)). | Named Q5 mutagenesis primer arrangement. | `kit-specific starting heuristic`; preserve arrangement and Tm model with the offset. | The deliberate mismatch is not represented by an ordinary Tm calculation, and the `+3 °C` value must not be copied to overlapping or inverse-PCR branches. |
| `quikchange_multi_structure_and_balance` | Agilent's Multi manual asks for hairpin review at annealing temperatures at or above `55 °C`, gives a primer-dimer threshold of ΔG greater than `−9 kcal/mol` while also printing `−9 kJ` in one unit presentation, and calls for amount adjustment when primer lengths differ by more than `20%` ([Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)). | Agilent QuikChange Lightning Multi primer-structure and balancing rules. | `vendor-specific design/QC record`; retain the printed unit ambiguity and length-balance trigger rather than correcting or averaging it. | These thresholds are not universal mutagenesis or thermodynamic laws; the conflicting energy units require confirmation against the exact manual revision before executable enforcement. |
| `q5_current_primer_design_limits` | `≥10 nt` complementary at the `3′` end; large changes `7–50 bases` per primer at the `5′` end; insertion `>6 nt` may be split; routine insertion up to `100 nt` as up to `50 nt` at each primer `5′` end; primers `>60 nt` recommended HPLC/PAGE purified | Current NEB Q5/NEBaseChanger design guidance | `kit-specific design overlay`; preserve edit type and primer architecture | Oligo synthesis quality and template context remain limiting; values are not transferable to QuikChange or assembly-based multi-site mutagenesis. Source: [NEB Q5 primer-design FAQ](https://www.neb.com/en-us/faqs/how-do-i-design-primers-to-use-with-the-q5-site-directed-mutagenesis-kit) |
| `q5_current_plasmid_capability` | robust results with plasmids up to at least `20 kb`; KLD `5 min` at room temperature | Current NEB Q5 E0554 product state | `current product capability/protocol record`; retain wording “at least” | This is vendor capability, not a universal mutagenesis maximum or guaranteed clone yield. Source: [NEB Q5 E0554 product page](https://www.neb.com/en-gb/products/e0554-q5-site-directed-mutagenesis-kit) |
| `quikchange_multi_current_product_range` | plasmid `4–8 kb`; `30` cycles; Dam-methylated, supercoiled template; `1` single-stranded primer per site; linear amplification | Current Agilent QuikChange Lightning Multi product specification | `current product-state record`; retain separately from manual reaction branches | Product capability does not replace the manual’s template-loading, DpnI and transformation instructions. Source: [Agilent QuikChange Lightning Multi product page](https://www.agilent.com/store/en_US/Prod-210514/210514) |

The register keeps Q5's `25` cycles and `5 min` KLD hold separate from QuikChange Multi's `30` cycles, DpnI treatment and transformation quantities. The difference is a protocol boundary, not a contradiction to be averaged or silently resolved ([NEB Q5 E0554 manual](https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf?hash=F6C8A6A1AE8596E87A53D5474A8BB04C&lang=en&rev=685c2daead0a4c2986da6dbd32e3b685), [Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf)).

## Source-to-parameter map

| Source | Parameters or claims supported |
| --- | --- |
| [Zheng et al., mutagenesis insights](https://pubmed.ncbi.nlm.nih.gov/25399421/) | workflow alternatives, primer geometry and enzyme dependence |
| [A/T-rich mutagenesis](https://pmc.ncbi.nlm.nih.gov/articles/PMC7351327/) | difficult-template handling and validation boundary |
| [NEB Q5 mutagenesis FAQ](https://www.neb.com/faqs/what-should-i-use-for-an-annealing-temperature-with-the-q5-site-directed-mutagenesis-kit) | named back-to-back primer annealing-temperature starting rule and optimization boundary |
| [NEB Q5 Site-Directed Mutagenesis Kit E0554 manual](https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf?hash=F6C8A6A1AE8596E87A53D5474A8BB04C&lang=en&rev=685c2daead0a4c2986da6dbd32e3b685) | kit-specific non-overlapping geometry and post-amplification hold |
| [Agilent QuikChange Lightning Multi manual](https://www.agilent.com/Library/usermanuals/Public/210514.pdf) (`Revision E1`, `2023`) | Multi-site topology, primer geometry, mismatch/GC/Tm rules, methylation and purification requirements, reaction quantities, cycling, DpnI, transformation and library-control overlays |
| [NEB Q5 primer-design FAQ](https://www.neb.com/en-us/faqs/how-do-i-design-primers-to-use-with-the-q5-site-directed-mutagenesis-kit) | current back-to-back substitution/deletion/insertion geometry; `≥10 nt` 3′ complement, `7–50`-base 5′ changes, `>6 nt` split insertion, `100 nt` routine insertion and `>60 nt` purification guidance |
| [NEB Q5 E0554 product page](https://www.neb.com/en-gb/products/e0554-q5-site-directed-mutagenesis-kit) | current Q5 product capability to at least `20 kb` and `5 min` room-temperature KLD step |
| [Agilent QuikChange Lightning Multi product page](https://www.agilent.com/store/en_US/Prod-210514/210514) | current `4–8 kb`, `30`-cycle, Dam-methylated/supercoiled, single-stranded-primer, linear-amplification product specification |

## Evidence

The evidence supports treating mutagenesis as a protocol-specific engineering workflow rather than an ordinary flanking pair with one changed base. It does not justify a universal overlap, cycle count or success probability across enzymes and template topologies ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)).

## Verification record

**Implementation:** validate edit coordinates, frame translation where applicable, strand normalization, primer-to-edit placement, template topology and selected protocol compatibility. The post-amplification protocol is explicit and absent by default; it is never inferred from the presence of an edit ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/), [NEB Q5 E0554 manual](https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf?hash=F6C8A6A1AE8596E87A53D5474A8BB04C&lang=en&rev=685c2daead0a4c2986da6dbd32e3b685)).

**Test:** cover substitutions, multi-base edits, reverse-strand input, frame-changing edits, circular-template boundaries and refusal when clone validation is omitted ([A/T-rich mutagenesis study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7351327/)).

**Limitation:** this profile is `limited`; the output is a design and validation plan, not proof of a pure intended clone ([Zheng et al.](https://pubmed.ncbi.nlm.nih.gov/25399421/)).

## CURRENT implementation contract

The canonical topology/protocol authority is `contracts/chemistry/mutagenesis-protocols.json`. Q5/E0554, QuikChange Lightning single-site and QuikChange Lightning Multi are separate executable computational topologies; NEBuilder multi-site is a route to Junction Primers ([NEB Q5 Site-Directed Mutagenesis Kit](https://www.neb.com/en-us/products/e0554-q5-site-directed-mutagenesis-kit)).

- Q5 small insertions use the named 5′-tail rule; `7–100 nt` insertions use the source-backed split-tail branch; larger insertions route to assembly rather than receiving fabricated Q5 primers.
- QuikChange single-site uses complementary opposing primers and its Agilent-specific Tm formula; that value is never relabelled as Primer3 Tm.
- Lightning Multi retains one non-overlapping mutagenic primer per edit on the same template strand and its own kit-specific constraints.
- exact edited constructs are reconstructed before reporting; overlapping/ambiguous edits fail closed;
- amino-acid edits preserve the DNA/codon decision policy; host-codon-usage mode requires caller-supplied usage evidence;
- NNK/NNS/custom IUPAC library outputs report theoretical sequence space only, not synthesized abundance or clone distribution;
- PCR/KLD/DpnI/transformation/Sanger/NGS evidence remains separate from design ranking and clone genotype is not inferred computationally.
