# PCRStudio UX/HCI review — current public source

**Audit state:** 2026-09-05. This review describes the current source surface;
native browser acceptance remains part of the Linux qualification gate.

## Interaction principles

- Module-specific controls use one shared workbench grammar rather than a generic
  one-size-fits-all form.
- Scientific status and typed refusals are visible to the user; unsupported
  chemistry is not silently approximated.
- Recommendation, independent validation, and measured wet-lab evidence are
  visually and semantically distinct.
- Selection state drives every dependent result visualization to avoid mixed
  rank/result displays.
- Accessibility obligations include labelled controls, keyboard-reachable
  selection, meaningful status text, and non-colour-only state communication.
- Empty/unavailable backend states render explicitly rather than inventing
  registry or result data.

## Native acceptance

Browser interaction, responsive layout, accessibility, and full-stack journeys
must be verified on the supported qualification host. See
`knowledge/runtime/LINUX-ACCEPTANCE-RUNBOOK.md` and
`release/current/CURRENT-LINUX-QUALIFICATION.md`.
