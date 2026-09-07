# ADR-0007 — Persist raw historical runs; migrate interpretation, not evidence
Status: Accepted (Generation 1 foundation)

Draft/request/result/module-contract schema versions are stored independently.
Old raw Run JSON is immutable. Compatibility migrations construct current view
models without rewriting the historical scientific evidence.
