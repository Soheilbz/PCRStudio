# Foundation verification strategy

Use risk-based testing. P0: account takeover/CSRF, tenant or project disclosure, stale grants after removal, unauthorized recovery, lost/duplicate ownership mutations. P1: repeat bootstrap/data preservation, optimistic edit conflicts, email verification/reset/session invalidation, MFA gate, limiter outage, generated contract mismatch, deep SPA navigation and identity cache switching.

Unit tests exercise own pure policy/contract logic. PostgreSQL integration tests exercise transactions, constraints and authorization via actual HTTP services. Do not replace PostgreSQL with SQLite for acceptance. Browser tests exercise the real UI/backend and synthetic Mailpit messages; mock third-party services only. Include cross-user/project/workspace negative cases and concurrency tests. Do not test framework internals or mirror every CSS declaration.

The deterministic entry is `python3 scripts/project_gate.py deep` via the project container tools. It must include backend lint/type/security/tests, migration consistency and OpenAPI validation; frontend type/lint/build/tests; Compose/bootstrap validation; science boundary tests; and browser smoke/negative journeys. Failed/unavailable checks are reported explicitly, never marked pass by skipping them.

Architecture consistency and a fresh independent review are required for this delivery. The source prototype's optional methodology bundles, Pact and browser utility dependencies are not inherited: generated OpenAPI and integration tests qualify this jointly-deployed API/client; no Pact broker is required. Checks cover actual behavior and risk rather than compliance with a document template.

Later execution tests add crash-before/after dispatch, duplicates, stale attempt completion, cancellation races and cost reservations. Later release tests use an external open-arrival-rate k6 load generator and composite backup/restore, not a laptop benchmark claim.
