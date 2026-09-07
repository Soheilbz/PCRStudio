# ADR-0002 — Canonical coordinates are 0-based half-open
Status: Accepted (Generation 1 foundation)

All internal intervals use `[start, end)`. Strand and circular positions are
explicit typed values at contract boundaries. Human/vendor coordinates are
converted once on ingress and never mixed with internal coordinates.
