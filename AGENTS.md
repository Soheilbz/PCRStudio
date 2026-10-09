# PCRStudio generation 2 engineering contract

User instructions take precedence. The source archive in the parent directory is a preserved prototype, not implementation authority.

This is a fresh modular-monolith build using ordinary software engineering practices. The user explicitly migrated away from BMAD on 2026-10-06: do not create `_bmad`, install a methodology bundle or depend on its tools. Read `docs/product/foundation.md` and `docs/architecture/architecture.md` before substantial changes. Record architecture changes as ADRs. Use risk-based acceptance tests and a fresh read-only independent reviewer for substantial changes.

The only quality entry point is `python3 scripts/project_gate.py` (invoked inside the tools container by `./bootstrap check`). Do not weaken tests, typing, security checks or boundaries to obtain a pass. Never commit `.local`, credentials, user scientific data, or real patient data. Fixtures are synthetic.

Own data mutations in explicit transactional services. Check current membership and project permission at the server on every operation. Do not substitute UI visibility, UUIDs, cached roles or organization membership for authorization. Do not delete organization projects when a user leaves. Keep scientific computation out of the platform runtime.

Limit Docker operations to this project's Compose namespace. No global cleanup or pruning. No cloud purchases, deployment or live charges in this foundation slice. Report verification limitations honestly.
