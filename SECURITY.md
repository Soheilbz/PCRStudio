# Security policy

## Supported source

Security fixes target the current controlled source and the most recent
authorized distributable release. Historical source snapshots are not
maintained as independent support branches unless a release notice says
otherwise.

## Reporting a vulnerability

Do not publish exploit details, credentials, private datasets, or unredacted
logs in a public issue. Prefer the repository host's private security-reporting
mechanism (for example, GitHub Security Advisories) when available. If private
reporting is not available, open a minimal public issue requesting a private
contact channel without including sensitive technical details.

A useful report includes the affected component/version, reproduction conditions,
impact, and any proposed mitigation. Remove personal data and secrets from logs.

## Deployment notes

Production deployments should use unique database credentials, a stable secret
for Next.js Server Actions when required, TLS at the edge, and an operator token
only when operator diagnostics are intentionally enabled. PostgreSQL and the API
should remain on private networks as described by the production Compose files.
