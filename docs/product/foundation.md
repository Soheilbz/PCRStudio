# Foundation acceptance contract

Status: accepted user plan, implementation in progress. Date: 2026-10-05.

PCRStudio is a confidential primer-design workspace. This slice builds accounts, personal/organization workspaces and private collaborative projects; scientific algorithms, file upload, durable execution, billing and cloud release are later slices. No patient registry or clinical workflow is introduced.

## Required behavior

- Email-based verified accounts, cookie authentication, CSRF, password reset, MFA enrollment/recovery and session management through allauth. Operators and organization owners must enroll MFA before privileged access. Ordinary users may opt in.
- One personal workspace per user. Organization creation is explicit. Workspace roles: owner and member. Project roles: owner, editor and viewer. Organization membership/ownership does not confer routine content access.
- List only accessible projects. Check active membership and current grants on reads/mutations. Viewer reads; editor reads/edits; project owner also manages access and archive. No cross-workspace moves.
- Forced removal is immediate. A removed membership never becomes active again; rejoining creates a new identity, so old grants cannot revive. Voluntary departure requires handover of ownership; suspension/security revocation cannot be blocked by ownership.
- Ownerless organization projects remain readable by existing authorized members but cannot be mutated. Workspace owner can explicitly recover management to an active member after recent authentication, with reason, audit and neutral notification. Recovery does not grant the recovering actor content access implicitly. Personal projects cannot use this recovery.
- If the final workspace owner is inactive, freeze workspace administration and preserve records. No automatic reassignment to an arbitrary member.
- Create/rename/describe/archive projects, with optimistic version checks and a visible conflict message. Preserve unsaved edits in memory on errors; never silently overwrite another change.
- Email invitations are single-use, expire in seven days, bind to the verified target email, and are rechecked against current inviter authority. Organization invitations grant membership only. Project grants are separate.
- Sensitive content, filenames, titles, secrets and query strings never enter operational logs, telemetry or email. Audit records contain opaque subject IDs and bounded operational metadata. Fixture data is synthetic.
- API `/api/v1/`; allauth browser API `/_allauth/browser/v1/`. Generate the TypeScript API types/client from exported OpenAPI, not a second handwritten API schema.

## Acceptance evidence

Clean bootstrap and repeat bootstrap preserve data/secrets; stop preserves data; all tools run in containers. Only Caddy is exposed to the browser, on loopback in local mode. PostgreSQL and Valkey are private. Mailpit is development-only.

Real PostgreSQL integration tests must exercise private lists/details, viewer/editor/owner rules, cross-workspace denial, forced removal, rejoining, orphan recovery and concurrent stale edits. Authentication tests cover CSRF, verification, password reset, session invalidation, MFA gates and limiter failure. Browser tests cover core flows, direct SPA navigation, workspace switching, both themes and mobile/keyboard behavior. The user explicitly removed BMAD from the delivery workflow on 2026-10-06; standard architecture/ADRs, risk-based tests and independent review remain required.

The current delivery is not a claim of live payment, cloud deployment, WCAG certification or 100k-DAU capacity. GitHub run evidence requires a configured remote. Later release prerequisites are in `docs/operations/release-gates.md`.
