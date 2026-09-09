# Current security exceptions

## SEC-EXC-2026-09-MFEPRIMER-451

Status: **accepted temporarily**. Review by **2026-10-09**.

The exact MFEprimer 4.5.1 Linux executable remains required by the current
validator contract. Its runtime SHA-256 is
`248e69da75a1a0f71f5314975e9faaf4c50cc95331d6b37068c9b93ebe27a205`; the
provision archive remains pinned separately in `contracts/tools.toml`. The
upstream public distribution currently provides the binary release rather than
buildable source, so PCRStudio cannot safely rebuild it while retaining the
same production identity and behavior.

The exception is intentionally narrower than a scanner ignore rule. Trivy
still reports every HIGH/CRITICAL finding, including unfixed findings. The
validator allows only the explicitly listed Go standard-library findings when
the target path, executable hash, package name, installed version, severity and
CVE identifier all match. A changed binary, new finding, different severity or
finding in any other component fails closed. Accepted findings remain visible as
warnings in the Actions summary and annotations.

The exception is removed as soon as an upstream-fixed MFEprimer artifact is
available and requalified. It is a release-visible security condition, not a
claim that the binary is vulnerability-free.
