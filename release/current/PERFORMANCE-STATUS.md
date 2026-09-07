# Performance status

`scripts/benchmark-worker.py` is the maintained measurement harness for cold-start,
Foundation import, full-worker import, peak RSS when available, and optional
scientific IPC telemetry.

No historical POSIX/workstation measurement is shipped in the current public
source tree. Performance measurements and `knowledge/performance/reference-budgets.json`
remain intentionally unpopulated until a qualified native Linux baseline is
captured, reviewed, and bound to the release snapshot.
