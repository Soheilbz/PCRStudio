# CURRENT static consistency audit

**Status:** **PASS**
**Public release:** **v1.0.1** (SemVer 1.0.1)
**Platform authority:** Linux x86_64
**Scope:** deterministic current-tree source/static consistency. Native dependency-backed and container/scientific execution is an explicit separate gate.

## Current Linux snapshot

- Source files represented: **1061**
- Python: **241**
- Rust: **91**
- TypeScript/TSX: **284**
- JSON: **223**
- TOML: **25**
- YAML: **13**
- Shell: **14**
- Public engines/modules: **11 / 21**
- Experimental/stable modules: **21 / 0**
- Active PowerShell/CMD/BAT files: **0**
- Symlinks: **0**
- Case-only collisions: **0**
- Cache/build residue: **0**
- CRLF text files: **0**
- Shebang scripts missing executable bit: **0**

## Architecture-hardening markers

- Transport-neutral application layer: **PASS**
- External PostgreSQL-backed scientific runner: **PASS**
- One-shot migration binary: **PASS**
- Read-only Linux doctor: **PASS**
- One-command Linux bootstrap: **PASS**
- Runner/Linux release-boundary ADR: **PASS**

## Qualification boundary

`scripts/qualify-source.py` is the source qualification authority and currently records **PASS** in `release/current/SOURCE-QUALIFICATION.json`. The source/static report does not convert unexecuted native work into a PASS. Rust/Cargo builds, dependency-backed Web tests/builds, production Docker topology, migrations, native scientific binaries and approved specificity-database execution belong to:

```bash
python3 scripts/run-linux-qualification.py --full --require-functional-acceptance
```

The public modules remain computationally experimental until the explicit native and scientific qualification/promotion gates pass.
