# Scientific computation cache policy

PCRStudio Generation 1 does not enable a shared scientific-result cache. If a cache is added,
its key MUST include the canonical request, module-contract version, request/result schema
versions, toolchain fingerprint and every database/reference fingerprint that can influence the
answer. A database/toolchain change therefore invalidates prior scientific cache entries.

UI/readiness memoization is not a scientific-result cache and must never be reused as evidence of
scientific equivalence. `run_fingerprint` remains the canonical duplicate/reproducibility identity.
