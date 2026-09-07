"""Cross-repository CURRENT architecture integrity checks.

These checks protect dependency direction and cross-layer contracts rather than
assay-specific science. They are intentionally dependency-free so they can run
before Node/Python scientific environments are provisioned.
"""
from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path

from .common import *  # noqa: F403


def _text(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        error(f"missing architecture artifact: {rel}")
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _toml(rel: str) -> dict:
    path = ROOT / rel
    if not path.is_file():
        error(f"missing architecture TOML: {rel}")
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def walk(node: str) -> list[str] | None:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for nxt in sorted(graph.get(node, set())):
            found = walk(nxt)
            if found:
                return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(graph):
        found = walk(node)
        if found:
            return found
    return None


def audit_architecture_integrity() -> None:
    policy = _toml("contracts/architecture.toml")
    foundation = _toml("contracts/foundation.toml")
    if policy.get("architecture") != "layered-modular-monolith":
        error("architecture policy no longer declares the layered modular monolith")

    persistence = policy.get("persistence") or {}
    for key, expected in (
        ("request_schema_version", foundation.get("request_schema_version")),
        ("result_schema_version", foundation.get("result_schema_version")),
        ("module_contract_version", foundation.get("module_contract_version")),
    ):
        if persistence.get(key) != expected:
            error(f"architecture/foundation persistence version drift: {key}")

    # Rust domain dependency direction.
    cargo_root = _toml("Cargo.toml")
    workspace_deps = ((cargo_root.get("workspace") or {}).get("dependencies") or {})
    if "pcr-security" not in workspace_deps:
        error("workspace lost pcr-security shared primitive crate")
    workspace_lints = ((cargo_root.get("workspace") or {}).get("lints") or {}).get("clippy") or {}
    if workspace_lints.get("all") != "warn":
        error("Rust Clippy baseline is no longer centralized at workspace level")

    crate_dirs = sorted(path.parent for path in (ROOT / "crates").glob("*/Cargo.toml"))
    crate_names: set[str] = set()
    runtime_graph: dict[str, set[str]] = {}
    for crate_dir in crate_dirs:
        data = _toml(crate_dir.relative_to(ROOT).joinpath("Cargo.toml").as_posix())
        name = str((data.get("package") or {}).get("name") or crate_dir.name)
        crate_names.add(name)
        deps = set((data.get("dependencies") or {}).keys())
        runtime_graph[name] = {dep for dep in deps if dep.startswith("pcr-")}
        if (data.get("lints") or {}).get("workspace") is not True:
            error(f"{name}: crate no longer inherits workspace lint policy")

    forbidden = set(runtime_graph.get("pcr-projects", set())) & {"pcr-accounts"}
    if forbidden:
        error("pcr-projects regained runtime dependency on pcr-accounts; use pcr-security")
    if "pcr-security" not in runtime_graph.get("pcr-projects", set()):
        error("pcr-projects lost shared bearer-token primitive dependency")
    if "pcr-security" not in runtime_graph.get("pcr-accounts", set()):
        error("pcr-accounts lost shared bearer-token primitive dependency")
    if "pcr-worker-client" in runtime_graph.get("pcr-core", set()):
        error("pcr-core regained concrete worker-process infrastructure; depend on the scientific execution port only")
    worker_client_source = _text("crates/pcr-worker-client/src/lib.rs")
    if re.search(r"\b(?:eprintln|println|dbg)!\s*\(", worker_client_source):
        error("pcr-worker-client regained ad-hoc stdout/stderr logging; process-boundary events must use structured tracing")
    unexpected_core = runtime_graph.get("pcr-core", set()) - {"pcr-contracts"}
    if unexpected_core:
        error(f"pcr-core gained unexpected runtime infrastructure dependencies: {sorted(unexpected_core)}")
    if "pcr-application" not in runtime_graph.get("pcr-server", set()):
        error("pcr-server lost the transport-neutral application boundary")
    if "pcr-server" in runtime_graph.get("pcr-application", set()) or "pcr-server" in runtime_graph.get("pcr-runner", set()):
        error("application/runner regained dependency on the HTTP server composition root")
    if "pcr-application" not in runtime_graph.get("pcr-runner", set()):
        error("pcr-runner no longer executes through the canonical application layer")
    allowed_application = {
        "pcr-accounts", "pcr-contracts", "pcr-core", "pcr-projects", "pcr-storage", "pcr-worker-client"
    }
    unexpected_application = runtime_graph.get("pcr-application", set()) - allowed_application
    if unexpected_application:
        error(f"pcr-application gained unexpected runtime domain dependencies: {sorted(unexpected_application)}")
    allowed_runner = {"pcr-accounts", "pcr-application", "pcr-core", "pcr-security", "pcr-storage"}
    unexpected_runner = runtime_graph.get("pcr-runner", set()) - allowed_runner
    if unexpected_runner:
        error(f"pcr-runner gained unexpected runtime domain dependencies: {sorted(unexpected_runner)}")
    found_cycle = _cycle(runtime_graph)
    if found_cycle:
        error("Rust workspace dependency cycle: " + " -> ".join(found_cycle))

    lock = _text("Cargo.lock")
    lock_crates = set(re.findall(r'^name = "(pcr-[^"]+)"$', lock, re.MULTILINE))
    missing_lock = sorted(crate_names - lock_crates)
    if missing_lock:
        error(f"Cargo.lock omits workspace crates: {missing_lock}")
    package_json = _text("package.json")
    for marker in (
        'cargo clippy --locked --workspace --all-targets -- -D warnings',
        'cargo test --locked --workspace',
    ):
        if marker not in package_json:
            error(f"Rust locked qualification marker missing: {marker}")

    # A production build must type-check its application code. Next supports
    # opting out of that check, but this repository already has a pinned,
    # independently runnable TypeScript gate, so opting out would hide a real
    # release failure instead of fixing it.
    next_config = _text("web/next.config.ts")
    if re.search(r"\bignoreBuildErrors\s*:\s*true\b", next_config):
        error("Next production build must not opt out of TypeScript errors")

    # One evidence contract across all engine generations.
    evidence_py = _text("tools/src/pcr_tools/workflow_evidence.py")
    for marker in ("validate_evidence_fields", '"observed": cleaned', '"decision_impact": "none"'):
        if marker not in evidence_py:
            error(f"shared Python workflow evidence contract lost marker: {marker}")
    if (ROOT / "web/src/components/design/workflow-evidence-card.tsx").exists():
        error("duplicate Web workflow evidence component returned")
    evidence_web = _text("web/src/components/design/workflow-evidence.tsx")
    for marker in ("evidence.observed ?? evidence.fields", "decision impact = none"):
        if marker not in evidence_web:
            error(f"Web evidence read-migration/decision boundary lost: {marker}")
    for rel in ("tools/src/pcr_tools/pipeline.py", "tools/src/pcr_tools/loop_set.py"):
        source = _text(rel)
        if '"fields": workflow_evidence' in source:
            error(f"current engine still emits legacy workflow evidence shape: {rel}")
        if '"observed": workflow_evidence' not in source:
            error(f"current engine lost canonical workflow evidence output: {rel}")

    # Versioned, non-destructive persistence contract.
    if foundation.get("result_schema_version") != 4:
        error("CURRENT architecture contract requires result schema v4")
    if foundation.get("module_contract_version") != "2.2.0":
        error("CURRENT architecture contract requires module contract 2.2.0")
    schema = _text("crates/pcr-projects/src/schema.rs")
    for marker in ("3 => migrate_workflow_evidence_v4(view)", 'evidence.remove("fields")', 'evidence.insert("observed"'):
        if marker not in schema:
            error(f"non-destructive result-v3 evidence migration lost marker: {marker}")
    result_migration = _text("crates/pcr-storage/migrations/0009_r16_architecture_contract.sql")
    if "SET DEFAULT 4" not in result_migration:
        error("future result-schema default migration lost v4 marker")
    contract_migration = _text("crates/pcr-storage/migrations/0010_r17_wire_context_contract.sql")
    if "SET DEFAULT '2.2.0'" not in contract_migration:
        error("future module-contract default migration lost 2.2.0 marker")

    # Rust HTTP error metadata must survive the Web parser.
    rust_error = _text("crates/pcr-server/src/error.rs")
    web_types = _text("web/src/lib/api/types.ts")
    web_error = _text("web/src/lib/api/error.ts")
    for rust_marker in ("pub code:", "pub field_path:", "pub stage:", "pub retryable:", "pub request_id:", '"cancelled"'):
        if rust_marker not in rust_error:
            error(f"Rust error envelope lost marker: {rust_marker}")
    for web_marker in ("apiErrorEnvelopeMetaShape", "fieldPath", "retryable", "requestId", 'z.literal("cancelled")'):
        if web_marker not in web_types:
            error(f"Web error schema lost Rust-envelope marker: {web_marker}")
    for getter in ("get code()", "get fieldPath()", "get stage()", "get retryable()", "get requestId()"):
        if getter not in web_error:
            error(f"PcrStudioError lost envelope accessor: {getter}")

    # Browser design traffic goes through one transport. File streaming/import
    # proxy routes are intentional exceptions and are explicitly enumerated.
    allowed_fetch = {
        "web/src/lib/api/http.ts",
        "web/src/app/(app)/account/data/export/route.ts",
        "web/src/app/(app)/account/data/import/route.ts",
        "web/src/components/account/account-forms.tsx",
        "web/src/lib/api/runtime-results.test.ts",
    }
    for path in (ROOT / "web/src").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if "fetch(" in source:
            rel = path.relative_to(ROOT).as_posix()
            if rel not in allowed_fetch:
                error(f"direct Web fetch bypasses canonical transport/proxy allow-list: {rel}")

    # Production TypeScript must not escape the contract graph with explicit
    # `any` or compiler-suppression directives. Tests may use targeted escapes
    # to exercise malformed historical payloads; runtime UI/transport code may
    # not.
    ts_escape = re.compile(r"(?:\bas[ \t]+any\b|:[ \t]*any\b|<any>|@ts-ignore|@ts-expect-error|eslint-disable)")
    for path in (ROOT / "web/src").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if ".test." in path.name or "/__fixtures__/" in f"/{rel}" or path.name.endswith(".generated.ts"):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        match = ts_escape.search(source)
        if match:
            error(f"production TypeScript regained an explicit type/suppression escape: {rel}: {match.group(0)}")

    # Python package relative-import cycles are a strong fragmentation signal.
    package = ROOT / "tools/src/pcr_tools"
    py_graph: dict[str, set[str]] = {}
    for path in package.glob("*.py"):
        module = path.stem
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            error(f"Python syntax prevents architecture import audit: {path.relative_to(ROOT)}: {exc}")
            continue
        deps: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                target = node.module.split(".")[0]
                if (package / f"{target}.py").is_file():
                    deps.add(target)
        py_graph[module] = deps
    py_cycle = _cycle(py_graph)
    if py_cycle:
        error("Python pcr_tools relative-import cycle: " + " -> ".join(py_cycle))

    # Review thresholds are intentionally lower than known debt. Existing
    # hotspots must be explicitly named in the no-growth budget; an unbudgeted
    # file cannot become a new monolith merely because the global threshold was
    # tuned high enough to accommodate an old one.
    thresholds = policy.get("hotspots") or {}
    extensions = {
        ".py": int(thresholds.get("python_file_review_lines") or 2200),
        ".rs": int(thresholds.get("rust_file_review_lines") or 1800),
        ".ts": int(thresholds.get("typescript_file_review_lines") or 1800),
        ".tsx": int(thresholds.get("tsx_file_review_lines") or 1600),
    }
    budget_path = ROOT / "contracts/maintainability-budget.json"
    try:
        maintainability = json.loads(budget_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"maintainability budget cannot support architecture hotspot review: {exc}")
        maintainability = {}
    budgeted_files = set((maintainability.get("max_lines") or {}).keys())
    roots = (ROOT / "tools/src", ROOT / "crates", ROOT / "web/src")
    for base in roots:
        for path in base.rglob("*"):
            limit = extensions.get(path.suffix)
            if not limit or not path.is_file():
                continue
            lines = sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
            relative = path.relative_to(ROOT).as_posix()
            if lines > limit and relative not in budgeted_files:
                error(f"unbudgeted architecture hotspot: {relative} has {lines} lines (review threshold {limit})")

    function_limit = int(thresholds.get("python_function_review_lines") or 600)
    budgeted_functions = set((maintainability.get("max_function_lines") or {}).keys())
    for path in (ROOT / "tools/src").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.end_lineno is None:
                continue
            lines = node.end_lineno - node.lineno + 1
            key = f"{relative}::{node.name}"
            if lines > function_limit and key not in budgeted_functions:
                error(f"unbudgeted Python function hotspot: {key} has {lines} lines (review threshold {function_limit})")
