# Performance qualification

Foundation R10 separates **measurement** from **budget setting**. `scripts/benchmark-worker.py`
records Python cold start, dependency-light Foundation imports, full worker import, peak RSS
(where the OS exposes it), and optional fully-versioned scientific IPC cases. It also preserves
backend `execution_telemetry` so candidate/tool/stage timings can be compared without logging
sequence content.

No scientific runtime threshold is invented in the source bundle. Run the harness on the
qualified Linux/native toolchain, record at least five repetitions of the accepted reference
corpus, then freeze reviewed budgets in `reference-budgets.json`. A future CI gate may compare
median wall time, peak RSS, candidate counts and external-tool durations against that baseline.

Warm worker pooling remains intentionally **not enabled** in Generation 1 until native baseline
measurements show that Python/import cold start is a material share of end-to-end latency. This
preserves the existing process isolation, crash containment and GPL/tool replacement boundary.
