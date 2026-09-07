# ADR-0006 — Numeric recipes are source-conditioned and fail closed
Status: Accepted (Generation 1 foundation)

Recipes resolve baseline values, conditional overlays, source ranges, bounded
user overrides and derived stoichiometry through the generic numeric core.
Units and provenance are explicit. A dependency without source-backed numeric
authority remains unresolved; the application does not invent a value.
