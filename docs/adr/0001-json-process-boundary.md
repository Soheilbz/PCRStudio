# ADR-0001 — Keep the Rust ↔ Python process boundary
Status: Accepted (Generation 1 foundation)

Rust owns HTTP, persistence, policy and process supervision. Python owns the
scientific toolchain. The boundary remains an isolated process/JSON seam to
preserve crash containment, replacement freedom and license isolation. CURRENT
adds a typed/versioned IPC envelope rather than collapsing the boundary.
