# ADR 0002 — Standard engineering workflow

Status: accepted by explicit user instruction. Date: 2026-10-06.

The user clarified that the new source must not create a `_bmad` directory or depend on BMAD. This is an explicit migration away from the prototype's methodology; it supersedes the conditional BMAD-only workspace rule for the new platform.

Use a small accepted product specification, architecture documentation, ADRs for substantial decisions, risk-based automated tests, reproducible locked dependencies, one deterministic quality gate and an independent adversarial review. Research current primary sources when behavior depends on changing libraries/security standards. No framework-specific agent bundles, memory writers or document-template linters belong in the application repository.

The previously created metadata-only helpers were moved outside the project. User data and the source archive were not modified. This change removes workflow coupling and ceremony; it does not remove authorization, security, typing, test, deployment or review requirements.
