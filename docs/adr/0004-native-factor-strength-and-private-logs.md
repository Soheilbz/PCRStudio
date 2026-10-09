# ADR 0004 — Native factor strength and confidential operations

Status: accepted implementation correction. Date: 2026-10-09.

MFA enrollment is not proof that a particular session authenticated with that factor. Keep allauth as the identity authority and use its native authentication records. Organization owners/operators require current-session factor proof; orphan recovery and existing-factor credential management additionally require recent proof. Neutral account metadata, initial factor enrollment and the native confirmation endpoint remain available so the user can complete setup.

The identity provider's generic recent-authentication check can be satisfied by a password record. It therefore cannot authorize export/regeneration of recovery codes for an existing-factor account on its own. The narrow platform middleware guards those credential endpoints while preserving native verification, recovery-code validation and replay prevention. The account UI confirms enrollment through the native MFA endpoint before code retrieval and refreshes identity after any successful enrollment commit.

Confidentiality applies to the complete runtime, including PostgreSQL and Gunicorn, rather than just Django logging. PostgreSQL suppresses ordinary failed statements/details/parameters; the server logger emits fixed operational events without raw URI or traceback content. Application request correlation retains route templates, status and elapsed time without user content.

These are implemented protections with regression evidence; they are not a claim of legal compliance or production incident readiness. Future provider/key-custody, hosting, retention and recovery obligations are recorded separately in the release gates.
