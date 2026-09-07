# ADR-0003 — Separate computational design from bench qualification
Status: Accepted (Generation 1 foundation)

A Design Run is immutable computational evidence. Wet-lab observations belong
to `AssayQualification` and attachments linked by hashes. New bench evidence
must never mutate a historical Design Run or silently alter sequence ranking.
