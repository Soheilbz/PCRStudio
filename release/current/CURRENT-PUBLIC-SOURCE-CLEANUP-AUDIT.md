# CURRENT public-source cleanup audit

**Status:** PASS — public-source structure ready for native qualification
**Release identity:** CURRENT public source
**Audit date:** 2026-09-05

## Scope

This pass prepares the CURRENT source tree for a real public repository/archive. It
removes superseded development-process artifacts, workstation-specific residue,
stale release-control paths and invalid historical measurements while retaining
scientific provenance, generated authorities, regression baselines and the
fail-closed release gates required for reproducibility.

No native runtime, compiler/build pipeline, scientific executable or wet-lab
claim is promoted by this source-cleanup pass. Those are independent Linux
qualification and experimental-validation gates.

## Cleanup decisions

- Removed agent/workstation instruction files and converted reusable guidance to
  normal public developer documentation.
- Removed superseded release-specific prepare/promote/finalize controls while retaining the
  unified engine regression harness that CURRENT qualification consumes.
- Collapsed historical release material into the single immutable baseline
  artifact required by current release tooling.
- Removed stale POSIX performance measurements containing obsolete failure output
  and machine-local paths; performance evidence now waits for a qualified native
  baseline.
- Reworked the release index/status/public-source documentation around one current
  CURRENT source authority.
- Removed machine-specific path assumptions from project-root discovery and
  public-facing operational text.
- Reconciled the CURRENT archive identity with current release tooling and
  corrected stale promotion-text matching.
- Preserved generated projections and intentional duplicated authority artifacts;
  these are reproducibility contracts, not disposable copies.
- Preserved source-backed historical lineage where it is actively referenced by the
  CURRENT regression and release gates.

## Final static inventory

- **894** files in the current public source tree
- **184** Python files parse by AST
- **191** JSON and **21** TOML files parse successfully
- **246** TypeScript/TSX, **71** Rust and **15** Python files are retained for native qualification
- **0** symlinks, build/cache residue, merge markers, case-collision paths, broken local Markdown links or stale public release-control references
- Linux path hygiene: **0** reserved/trailing names, **0** paths over 200 characters, maximum relative path length **100**
- **30** duplicate-content groups are intentional generated projections and are retained for cross-language reproducibility
- Linux acceptance definitions remain in exact parity at **21 modules** and **22 integration scenarios**

## Public release boundary

This tree is suitable as the **current public source candidate**. It is not the
a native-qualified release until the exact prepared snapshot passes the
Linux qualification, functional acceptance, deterministic archive verification
and Final promotion/finalization sequence documented in
[`CURRENT-LINUX-QUALIFICATION.md`](CURRENT-LINUX-QUALIFICATION.md).
