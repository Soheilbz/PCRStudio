# ADR-0004 — Reproducibility requires toolchain and database fingerprints
Status: Accepted (Generation 1 foundation)

Scientific claims require exact tool identity, artifact/database hashes and a
contract version. Caches and duplicate detection include these fingerprints;
a changed BLAST/MFEprimer database cannot reuse a prior scientific result.
