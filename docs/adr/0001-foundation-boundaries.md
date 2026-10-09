# ADR 0001 — Confidential platform foundation

Status: accepted. Date: 2026-10-05.

The user authorized a fresh build and the selected Django/static React stack. Preserve the prototype archive, do not migrate accounts or scientific modules. Use a modular monolith and containerized tooling. Implement accounts/workspaces/private projects first; files/jobs/payments/deployment follow independent acceptance slices.

Organization ownership grants membership/billing control, not routine scientific-content access. User approved explicit audited recovery of orphaned organization projects. Forced revocation is immediate, while voluntary exit requires handover. Scientific engine interfaces are versioned and neutral to specific engines.

Current official compatibility sources: https://www.djangoproject.com/download/ ; https://docs.allauth.org/en/latest/headless/ ; https://docs.allauth.org/en/latest/common/rate_limits.html ; https://reactrouter.com/how-to/spa ; https://docs.docker.com/compose/ . Registry-resolved lockfiles and build evidence select exact supported patches, never unsupported advertised versions. Delivery methodology was superseded by ADR0002 at the user's explicit request; application boundaries are unchanged.

Consequences: ready-made identity flows, one authoritative transactional data store and no permanent frontend Node runtime. More operational components are added only when required by an implemented feature. No medical registry, clinical functions, generic scientific form builder or claims of compliance are introduced.
