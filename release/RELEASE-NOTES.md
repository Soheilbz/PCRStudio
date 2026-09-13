# CURRENT public source — release notes

## v1.0.6

Fixes a production startup issue in the restricted server runtime. A release is
now published only after its production images pass final startup checks.
Every deployment also refreshes the 20 GiB host storage guard before image
operations, preventing stale reserve settings from disrupting the server.
Existing user data and pinned dependencies remain unchanged.
