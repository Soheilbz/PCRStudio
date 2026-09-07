# Multiplex maturity audit — R17 REV7

This review is generated/maintained against `contracts/multiplex-capabilities.json` and the source-level multiplex audit. It distinguishes endpoint multi-target PCR, spectral qPCR, digital-PCR, pooled tiling and empirical/isothermal planning. A software target bound is never a wet-lab-qualified plex claim.

- Standard PCR, Colony PCR and Species-specific PCR: executable endpoint multiplex with exact Scientific-Strict candidate selection within the evaluated candidate pools, explicit tube identities, final-panel interaction validation and cross-product specificity evidence.
- qPCR Probe: spectral multiplex validation with explicit peer forward/reverse/probe sequences, reporter/channel identity and a versioned external optical authority. Cross-assay heterodimer values are diagnostic evidence; PCRStudio does not invent a universal rejection threshold.
- Digital PCR: channel/amplitude/hybrid/probe-mix planning and measured-run evidence only. Threshold, rain, cluster classification and absolute concentration are never inferred from sequence. Higher-order bounds are platform-authority bounds, not bench qualification.
- Tiled Scheme: high-plex pooled design remains delegated to the exact upstream PrimalScheme3/Olivar backends; PrimerPooler is independent pool-interaction evidence rather than a blended replacement algorithm.
- RPA: full assay selection remains empirical. PCRStudio prepares the manufacturer-style 8–10 × 8–10 candidate matrix and typed multiplex context; final performance is not predicted from sequence.
- LAMP: modified-primer/probe multiplex is a specialized evidence/planning boundary; standard LAMP set design is not silently reused as a generic multi-target fluorescence algorithm.

All public modules remain experimental until Linux/native/scientific and wet-lab qualification gates pass.


## Global authority matrix

| Family | Built-in source authority | Source-level status |
| --- | --- | --- |
| Endpoint PCR multiplex | PCRStudio exact bounded candidate-pool selector + SADDLE Badness component + PrimerPooler handoff | source-closed; native/bench pending |
| qPCR Probe | QuantStudio 5/7 Pro, CFX96/CFX Opus 96, Rotor-Gene Q, AriaMx reviewed optical maps | source-closed; instrument calibration/bench pending |
| dPCR | QIAcuity, QX200/QX ONE/QX600/QX700/QX Continuum, Absolute Q, Digital LightCycler capacity/mode authorities | planning/evidence source-closed; run/bench pending |
| Tiled amplicon pools | PrimalScheme3, Olivar, PrimerPooler | source-closed; native/bench pending |
| RPA multiplex | empirical low-plex workflow | source-closed; empirical qualification pending |
| LAMP multiplex | modified-primer/probe empirical planning boundary | evidence/planning only; topology-specific wet-lab qualification pending |

No platform row above is a PCRStudio wet-lab qualification claim.
