# PCRStudio Generation-1 — Intentional support boundaries

This record separates a **closed source/contract gap** from a deliberately unsupported or externally measured branch. A generation-1 refusal is acceptable only when it is typed, visible to the user, preserved in provenance, and does not silently substitute a different assay.

## Executable but externally measured boundaries

- **All modules:** computational design is not a wet-lab validation claim. Experimental/bench status stays separate from sequence-design evidence.
- **Specificity:** an organism-level specificity claim requires an approved-reference database with release/filtering/deduplication provenance and verified FASTA/index fingerprints. The bundled corpus is smoke/regression scope only.
- **qPCR / dPCR:** efficiency, Cq/thresholding, melt/cluster/rain behavior, accepted partition counts, Poisson concentration, LOD/LOQ and run QC come from the measured assay/run rather than being synthesized from primer design.
- **Colony PCR:** host, preparation and named SOP/protocol are required provenance. PCRStudio does not invent a universal colony-lysis hold, cycle count, gel observation or verified-clone status.
- **RACE:** the output is a candidate transcript-end design. Complete transcript-end identity requires product sequencing and independent experimental evidence.
- **Sanger sequencing primer:** instrument may remain explicitly unresolved at design time. Trace quality, basecalling, mixed-template review and usable read length require the actual capillary run.
- **Tiled schemes:** release/repair/panel/replacement artifacts are computational lifecycle outputs; coverage of the actual wet-lab panel and sample set remains empirical.

## Recognized but intentionally refused Generation-1 branches

- **RPA:** `twistamp-basic` / Basic-RT style primer-pair design is executable. Exo, Nfo, Fpg and SIBA/reference branches are recognized but refused until the modified-probe/nuclease topology can be represented as a typed contract; PCRStudio does not fabricate an ordinary ACGT probe.
- **KASP:** biallelic SNV/MNV-compatible designs and the junction-aware `plus-minus` presence/absence branch are executable only under their typed variant/protocol contracts. Endpoint FAM/HEX data are evidence-only: PCRStudio preserves provider/software calls and plots the declared channels but does not invent a universal cluster threshold, auto-call genotype, or claim equivalence to LGC Biosearch Technologies' proprietary Kraken design process.

- **Consensus Pair / Universal Primers:** observed inclusivity/exclusivity applies only to the supplied, versioned panel. User weights are not population prevalence; split-pool suggestions, alternative-alignment sensitivity and amplicon informativeness are diagnostic evidence unless a separate versioned decision policy explicitly promotes them.
- **Junction Primers:** Gibson E5510 and NEBuilder HiFi are separate method/protocol authorities. Numeric overlap, fragment-input and mismatch-removal capabilities must not cross-inherit. Golden Gate/type-IIS assembly remains outside this engine unless a separate executable contract is added.
- **Mutagenic Pair:** Q5/E0554, QuikChange Lightning single-site and Lightning Multi use different primer topologies and Tm/kit semantics. NEBuilder multi-site is a typed route into Junction Primers rather than an orderable mutagenic-primer result. Library diversity is theoretical sequence-space evidence, not a synthesized-abundance or clone-frequency claim.
- **Nested PCR:** Generation 1 executes explicit two-round workflows with typed transfer/cleanup. Named Msz Exonuclease I and Thermolabile Exonuclease I overlays retain their own source-backed numeric programs. Generic one-tube Nested remains fail-closed; `dUTP/UNG` without a named compatible chemistry remains strategy/reference-only rather than a fabricated bench recipe.
- **Restriction cloning:** same-enzyme cloning is supported as a nondirectional strategy with explicit controls. Golden Gate or other multi-fragment/type-IIS workflows are not silently folded into the single-pair restriction-cloning branch unless a separate named executable contract exists.
- **Remote/reference tools:** Primer-BLAST, NUPACK and other `REFERENCE` entries are not runtime prerequisites and do not silently replace local generation-1 authorities.
- **Optional validators/evidence:** pydna, ViennaRNA or PrimerPooler in an `OPTIONAL` role enrich evidence only. Their presence or absence must not change hard validity, deterministic ranking or the default selected candidate. If a tool participates in a scientific decision it must be promoted to a required role for that engine. Where a tool is bound as `VALIDATOR` or `PRIMARY` for a specific engine (for example PrimerPooler in tiled-scheme or ViennaRNA in Gibson overlap ranking), strict policy may require it.

## Future work is not a Generation-1 release blocker when

1. the unsupported branch is explicitly named;
2. the UI/API/runtime all refuse or mark it unresolved consistently;
3. no result is silently generated under a different chemistry/topology;
4. the Linux acceptance suite covers the boundary; and
5. the release notes preserve the limitation.
