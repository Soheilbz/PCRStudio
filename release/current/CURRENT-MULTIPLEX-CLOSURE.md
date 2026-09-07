# CURRENT CURRENT multiplex closure

Canonical source: `contracts/multiplex-capabilities.json`.

CURRENT treats multiplex as modality-specific rather than a single generic switch. Generic endpoint multiplex is limited to Standard PCR, Colony PCR and Species-specific PCR. qPCR Probe, dPCR, tiled schemes, RPA and LAMP have separate authority/evidence boundaries. Scientific-Strict never substitutes the development local optimiser for the exact bounded endpoint selector, never calls the SADDLE Badness component the SADDLE simulated-annealing optimiser, and never turns sequence-derived diagnostics into dPCR thresholds, LAMP target-specific signal calls or RPA empirical validation.

Source closure is not a native or bench claim. `wet_lab_qualified_plex` remains null until explicit qualification evidence exists.
## Reviewed global instrument authority coverage

### qPCR Probe optical profiles

The built-in profile library is a reporter/channel compatibility authority, not a substitute for the actual instrument calibration or compensation state. Reviewed profiles now cover:

- Applied Biosystems QuantStudio 5 96-well — 6 channels.
- Applied Biosystems QuantStudio 7 Pro — 6-by-6 filter set / 6 channels.
- Bio-Rad CFX96 — 5 channels.
- Bio-Rad CFX Opus 96 — 5-target optical multiplex.
- QIAGEN Rotor-Gene Q six-channel configuration — six reviewed optical channels.
- Agilent AriaMx with all six optical modules installed.

Roche LightCycler PRO is recognized as a seven-channel multiplex platform, but PCRStudio intentionally does not ship a built-in channel/reporter map until an exact reviewed map is bound; a caller may supply a versioned external `pcrstudio.qpcr-optical-profile.v1` authority instead.

### dPCR platform capability authorities

The canonical dPCR matrix records only manufacturer-published planning bounds and allowed multiplex modes. It covers QIAcuity One 2plex/5plex, Four and Eight; Bio-Rad QX200, QX ONE, QX600, QX700 and QX Continuum; Thermo Fisher QuantStudio Absolute Q; and Roche Digital LightCycler. Platform-specific mode restrictions are enforced (for example, the reviewed Digital LightCycler authority is channel-only because its documented software does not support amplitude/radius analysis).

These limits are never promoted to bench qualification. Thresholds, rain, amplitude clusters, partition-volume corrections, compensation and assay-specific concentration balancing remain measured-run or external authority evidence.

## Gen-1 multiplex completion boundary

- Endpoint PCR: exact bounded candidate-pool selection in Scientific-Strict, content-addressed panel identity, explicit tubes, cross-product specificity, final-panel interaction evidence and external PrimerPooler proposal/validation. The published SADDLE Badness component is retained, while the unavailable exact SADDLE simulated-annealing optimiser remains an external-authority boundary rather than being guessed.
- qPCR Probe: full peer forward/reverse/probe transport, optical hard gates from a versioned profile, all-vs-all oligo interaction diagnostics, panel identity and MIQE evidence transport.
- dPCR: typed channel/amplitude/hybrid/probe-mix planning where source-backed, platform capacity/mode enforcement, panel identity and measured-run evidence boundaries. Peer assay design is not fabricated by the dye-flanking engine; probe-oriented platforms remain a Pair+Probe/vendor-authority handoff.
- Tiled Scheme: upstream PrimalScheme3/Olivar execution contracts plus PrimerPooler validation/proposal and pool-aware interaction/depth/repair/version evidence.
- RPA: low-plex empirical panel workflow with 8–10 × 8–10 candidate-matrix preparation and empirical evidence; no sequence-only validated-RPA claim.
- LAMP: specialized modified-primer/probe multiplex planning/evidence only; no generic multi-target LAMP algorithm is invented.

The remaining work is Linux/native/scientific/wet-lab qualification, not a hidden source claim.

