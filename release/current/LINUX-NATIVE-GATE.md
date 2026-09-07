# Linux native qualification gate — CURRENT

Source qualification proves deterministic source/contracts only. Native release claims require the canonical Linux x86_64 gate:

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

The gate executes Python, Rust and Web builds/tests; targeted engine/module integration acceptance; LAMP qualification; exact scientific-tool readiness; optional Olivar verification; and optional live-stack probes. Evidence is bound to `release/FILE-MANIFEST.json` and `release/release.toml`.

A missing production specificity database is a release failure for strict scientific execution, not a condition that silently downgrades the runtime.
