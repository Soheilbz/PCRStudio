"""Application static-audit checks."""
from __future__ import annotations

import math

from .common import *  # noqa: F403

def audit_application_foundation() -> None:
    """Keep full-application hardening from drifting behind scientific source."""
    def text(rel: str) -> str:
        path = ROOT / rel
        if not path.is_file():
            error(f"missing application-foundation artifact: {rel}")
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    # Current tree must not regain the dead duplicate transport module.
    if (ROOT / "web/src/lib/actions.ts").exists():
        error("dead duplicate web/src/lib/actions.ts returned; use web/src/lib/sequences/actions.ts")

    limits = text("web/src/lib/limits.ts")
    generated_limits = text("web/src/lib/contracts/limits.generated.ts")
    server = text("crates/pcr-server/src/lib.rs")
    projects = text("crates/pcr-projects/src/lib.rs")
    foundation = tomllib.loads(text("contracts/foundation.toml"))
    canonical_limits = foundation.get("limits", {})
    required_limit_keys = {
        "account_import_bytes",
        "http_body_bytes",
        "account_project_data_bytes",
        "backup_document_bytes",
    }
    if not required_limit_keys.issubset(canonical_limits):
        error("canonical foundation limits are incomplete")
    else:
        if int(canonical_limits["http_body_bytes"]) < int(canonical_limits["account_import_bytes"]):
            error("canonical HTTP body ceiling is below the account-import transport ceiling")
        if int(canonical_limits["backup_document_bytes"]) < int(canonical_limits["account_project_data_bytes"]):
            error("canonical backup ceiling is below the live project-data ceiling")
    for marker in (
        "MAX_ACCOUNT_IMPORT_BYTES",
        "MAX_HTTP_BODY_BYTES",
        "MAX_BACKUP_DOCUMENT_BYTES",
        "MAX_PROJECT_SETTINGS_BYTES",
        "MAX_RUN_DOCUMENT_BYTES",
    ):
        if marker not in limits or marker not in generated_limits:
            error(f"Web canonical limit projection lost {marker}")
    if "MAX_BODY_BYTES: usize = pcr_contracts::MAX_HTTP_BODY_BYTES" not in server:
        error("Rust HTTP body ceiling bypassed the canonical foundation limit")
    if "MAX_ACCOUNT_DATA_BYTES: i64 = pcr_contracts::MAX_ACCOUNT_PROJECT_DATA_BYTES as i64" not in projects:
        error("project live-data ceiling bypassed the canonical foundation limit")

    for rel in (
        "web/src/app/(app)/account/data/export/route.ts",
        "web/src/app/(app)/account/data/import/route.ts",
    ):
        route = text(rel)
        if "upstream.body" not in route:
            error(f"account backup route is no longer streaming upstream body: {rel}")

    auth_store = text("crates/pcr-accounts/src/lib.rs")
    auth_routes = text("crates/pcr-server/src/auth.rs")
    auth_web = text("web/src/lib/auth/actions.ts")

    # Browser-origin and redirect validation are security boundaries. Keep the
    # import route fail-closed and keep return destinations normalized by URL
    # origin rather than by a slash-only regular expression.
    import_route_security = text("web/src/app/(app)/account/data/import/route.ts")
    origin_helper = text("web/src/lib/http/origin.ts")
    public_origin = text("web/src/lib/http/public-origin.ts")
    proxy_source = text("web/src/proxy.ts")
    destination = text("web/src/lib/auth/destination.ts")
    destination_tests = text("web/src/lib/auth/destination.test.ts")
    if "hasExpectedBrowserOrigin" not in import_route_security or 'request.headers.get("origin")' not in import_route_security:
        error("account import route lost same-origin browser enforcement")
    for marker in ("parseSerializedOrigin(originHeader)", "parsePublicOrigin(configured)"):
        if marker not in origin_helper:
            error(f"browser-origin authority lost canonical parser marker: {marker}")
    for marker in ("url.pathname !== \"/\"", "url.username || url.password", "value === parsed.origin"):
        if marker not in public_origin:
            error(f"public-origin parser lost strict serialized-origin marker: {marker}")
    for marker in ("shouldRejectBrowserMutationOrigin", 'request.headers.get("origin")'):
        if marker not in proxy_source:
            error(f"early browser-mutation origin guard lost marker: {marker}")
    for marker in ("UNSAFE_URL_CHARACTERS", "new URL(raw, INTERNAL_ORIGIN).origin === INTERNAL_ORIGIN"):
        if marker not in destination:
            error(f"auth return-destination validation lost hardened marker: {marker}")
    if "\\n//example.org/" not in destination_tests or "\\r//example.org/" not in destination_tests:
        error("auth return-destination regression tests lost control-character redirect coverage")

    # Public authentication endpoints must cap request bodies before JSON/Argon2
    # work, and verification paths must cheaply reject absurd credentials.
    password_source = text("crates/pcr-accounts/src/password.rs")
    if "AUTH_BODY_BYTES: usize = 64 * 1024" not in auth_routes:
        error("auth router body ceiling drifted from 64 KiB")
    for marker in ("DefaultBodyLimit::max(AUTH_BODY_BYTES)", "RequestBodyLimitLayer::new(AUTH_BODY_BYTES)"):
        if marker not in auth_routes:
            error(f"auth router lost early body-limit layer: {marker}")
    if "MAX_VERIFICATION_PASSWORD_BYTES" not in password_source or "password.len() > MAX_VERIFICATION_PASSWORD_BYTES" not in password_source:
        error("password verification lost its pre-Argon2 size bound")
    if "recovery::looks_like_a_code(code)" not in auth_store:
        error("recovery verification lost cheap code-shape validation")

    # Raw HTML is a narrow, audited boundary. The application currently needs
    # it only for JSON-LD script elements, and every payload must pass through
    # jsonLd(), which escapes HTML-significant characters before insertion.
    dangerous_html = []
    for path in (ROOT / "web/src").rglob("*.tsx"):
        source = path.read_text(encoding="utf-8", errors="replace")
        if "dangerouslySetInnerHTML" in source:
            dangerous_html.append((path.relative_to(ROOT).as_posix(), source))
    expected_dangerous_html = {
        "web/src/app/(app)/page.tsx",
        "web/src/app/(app)/modules/[moduleId]/page.tsx",
    }
    actual_dangerous_html = {rel for rel, _ in dangerous_html}
    if actual_dangerous_html != expected_dangerous_html:
        error(
            "dangerouslySetInnerHTML boundary drifted: "
            f"expected {sorted(expected_dangerous_html)}, got {sorted(actual_dangerous_html)}"
        )
    for rel, source in dangerous_html:
        if "__html: jsonLd(" not in source:
            error(f"raw HTML insertion bypassed jsonLd() escaping: {rel}")
    site_source = text("web/src/lib/site.ts")
    for marker in (
        r'.replace(/</g, "\\u003c")',
        r'.replace(/>/g, "\\u003e")',
        r'.replace(/\u2028/g, "\\u2028")',
        r'.replace(/\u2029/g, "\\u2029")',
    ):
        if marker not in site_source:
            error(f"jsonLd() HTML/script escaping lost marker: {marker}")
    recovery_update = re.search(r'UPDATE users\s+SET recovery_attempts.*?fetch_optional', auth_store, re.DOTALL)
    if recovery_update is None or "recovery_hash = $4" not in recovery_update.group(0):
        error("recovery failure accounting no longer compares the hash that was actually verified")

    # Deployment configuration contains database/operator/upstream credentials.
    # Keep Debug useful for non-secret topology while requiring a manual redacted
    # implementation rather than a derived implementation that can leak values.
    server_source = text("crates/pcr-server/src/lib.rs")
    config_derive = re.search(r"#\[derive\(([^)]*)\)\]\s*pub struct Config\b", server_source)
    if config_derive is None or "Debug" in {part.strip() for part in config_derive.group(1).split(",")}:
        error("server Config must use a manual redacted Debug implementation")
    config_debug = re.search(r"impl std::fmt::Debug for Config\s*\{(.*?)\n\}", server_source, re.DOTALL)
    if config_debug is None or config_debug.group(1).count("[REDACTED]") < 3:
        error("server Config redacted Debug implementation is missing credential redaction")

    # HTTP auth DTOs carry raw passwords, recovery codes, and bearer tokens.
    # They must never regain a derived Debug implementation: a harmless-looking
    # tracing statement would otherwise become a credential disclosure.
    auth_source = text("crates/pcr-server/src/auth.rs")
    for struct_name in (
        "RegisterRequest",
        "LoginRequest",
        "ChangeEmailRequest",
        "ChangePasswordRequest",
        "DeleteAccountRequest",
        "SessionResponse",
        "RecoverRequest",
        "ReissueRequest",
        "RecoveryResponse",
    ):
        match = re.search(
            rf"#\[derive\(([^)]*)\)\]\s*(?:#\[[^\]]+\]\s*)*pub struct {struct_name}\b",
            auth_source,
        )
        if match is None:
            error(f"cannot locate auth DTO derive for {struct_name}")
        elif "Debug" in {part.strip() for part in match.group(1).split(",")}:
            error(f"secret-bearing auth DTO must not derive Debug: {struct_name}")


    # Queue polling must hydrate only work that can actually enter this runner.
    # Each durable request can be MiBs, so a fixed large SQL LIMIT is a memory
    # amplification bug rather than a harmless prefetch optimization.
    storage_source = text("crates/pcr-storage/src/lib.rs")
    queue_method = re.search(
        r"pub async fn queued_run_jobs\(&self, dispatch_capacity: usize\).*?\n    \}",
        storage_source,
        re.DOTALL,
    )
    if queue_method is None or "LIMIT $1" not in queue_method.group(0) or ".bind(limit)" not in queue_method.group(0):
        error("durable queue polling must remain bounded by current dispatch capacity")

    recovery_method = re.search(
        r"pub async fn recover_stale_run_jobs\(&self\).*?\n    \}",
        storage_source,
        re.DOTALL,
    )
    if recovery_method is None:
        error("cannot locate durable stale-job recovery method")
    elif "RETURNING" in recovery_method.group(0) or "query_as::<_, RunJob>" in recovery_method.group(0):
        error("stale-job recovery must mutate by count without hydrating multi-MiB job requests")

    # Durable run jobs are project-owned by schema after the canonical migration
    # audit. Carry that invariant through Rust and Web types instead of keeping
    # impossible nullable branches alive above the database boundary.
    storage_source = text("crates/pcr-storage/src/lib.rs")
    if not re.search(r"pub struct RunJob\s*\{.*?pub project_id: String,", storage_source, re.DOTALL):
        error("RunJob.project_id must remain non-null in the Rust storage model")
    run_job_derive = re.search(r"#\[derive\(([^]]+)\)\]\s*pub struct RunJob\s*\{", storage_source)
    if run_job_derive is None:
        error("RunJob must keep an explicit derive boundary")
    else:
        for forbidden_trait in ("Debug", "Serialize", "Deserialize"):
            if forbidden_trait in run_job_derive.group(1):
                error(f"RunJob must stay persistence-only and must not derive {forbidden_trait}")
    web_types_source = text("web/src/lib/api/types.ts")
    run_job_schema = re.search(r"export const runJobSchema = z\.object\(\{(.*?)\n\}\);", web_types_source, re.DOTALL)
    if run_job_schema is None or "projectId: z.string()," not in run_job_schema.group(1):
        error("Web RunJob.projectId must remain non-null with the database invariant")

    # Persistence-only execution inputs must never leak back through the polling
    # API. A job request can be several MiB and is already durably stored for the
    # executor; returning it on every status poll is both a memory/bandwidth
    # amplification and an unnecessary expansion of the public data surface.
    server_projects_source = text("crates/pcr-server/src/projects.rs")
    public_job = re.search(r"struct RunJobAnswer\s*\{(.*?)\n\}", server_projects_source, re.DOTALL)
    if public_job is None:
        error("durable jobs must expose an explicit RunJobAnswer transport projection")
    else:
        forbidden_rust_fields = ("user_id", "idempotency_key", "request")
        for field in forbidden_rust_fields:
            if re.search(rf"(?m)^\s*{field}\s*:", public_job.group(1)):
                error(f"RunJobAnswer must not expose persistence-only field {field}")
    if run_job_schema is not None:
        forbidden_web_fields = ("userId", "idempotencyKey", "request")
        for field in forbidden_web_fields:
            if re.search(rf"(?m)^\s*{field}\s*:", run_job_schema.group(1)):
                error(f"Web RunJob schema must not expose persistence-only field {field}")


    control_state = re.search(r"pub struct RunJobState\s*\{(.*?)\n\}", storage_source, re.DOTALL)
    if control_state is None:
        error("storage must keep a lightweight RunJobState control-plane projection")
    else:
        for field in ("user_id", "idempotency_key", "request"):
            if re.search(rf"(?m)^\s*pub\s+{field}\s*:", control_state.group(1)):
                error(f"RunJobState must not hydrate persistence-only field {field}")
    if "pub async fn run_job(&self" in storage_source:
        error("control-plane status reads must use RunJobState rather than hydrating full RunJob")

    # Keep the TypeScript seam and its concrete HTTP implementation in lockstep.
    # This is intentionally syntax-light so the dependency-free auditor can run
    # before node_modules exist.
    transport_interface = text("web/src/lib/api/transport.ts")
    http_transport = text("web/src/lib/api/http.ts")
    http_contract = json.loads(text("contracts/http-api.generated.json") or "{}")
    stable_api_prefix = str(http_contract.get("stable_prefix") or "/api/v1")
    http_operations = {
        str(row["id"]): (str(row["method"]), stable_api_prefix + str(row["api_path"]))
        for row in http_contract.get("endpoints", [])
        if str(row.get("id")) not in {"health", "ready", "scientific_ready", "operator_diagnostics", "operator_metrics"}
    }
    interface_methods = set(re.findall(r"^  ([A-Za-z][A-Za-z0-9_]*)\(", transport_interface, re.MULTILINE))
    implementation_methods = set(re.findall(r"^    ([A-Za-z][A-Za-z0-9_]*):", http_transport, re.MULTILINE))
    if interface_methods != implementation_methods:
        missing = sorted(interface_methods - implementation_methods)
        extra = sorted(implementation_methods - interface_methods)
        error(f"Web Transport/HTTP method parity drifted: missing={missing}, extra={extra}")

    # Every API path used by the concrete Web transport must still be routable
    # by the Rust application. Dynamic path segments are compared by shape.
    def normalized_route(path: str) -> str:
        path = re.sub(r"\$\{[^{}]*\}", "{}", path)
        return re.sub(r"\{[^/{}]+\}", "{}", path).rstrip("/") or "/"

    route_constant_source = text("crates/pcr-server/src/http_routes.generated.rs")
    route_constants = dict(re.findall(r'pub const ([A-Z0-9_]+): &str = "([^"]+)";', route_constant_source))

    def rust_routes(rel: str, prefix: str) -> set[str]:
        source = text(rel)
        found: set[str] = set()
        pattern = re.compile(r'\.route\(\s*(?:http_routes::([A-Z0-9_]+)|"([^"]+)")')
        for constant, literal in pattern.findall(source):
            route = route_constants.get(constant) if constant else literal
            if not route:
                error(f"unknown generated HTTP route constant in {rel}: {constant}")
                continue
            if route == "/":
                full = prefix.rstrip("/") or "/"
            else:
                full = prefix.rstrip("/") + route
            found.add(normalized_route(full))
        return found

    rust_api_paths = set()
    rust_api_paths |= rust_routes("crates/pcr-server/src/lib.rs", "/api")
    rust_api_paths |= rust_routes("crates/pcr-server/src/bench.rs", "/api")
    rust_api_paths |= rust_routes("crates/pcr-server/src/sequences.rs", "/api/sequences")
    rust_api_paths |= rust_routes("crates/pcr-server/src/auth.rs", "/api/auth")
    rust_api_paths |= rust_routes("crates/pcr-server/src/projects.rs", "/api/projects")
    # `shared_routes()` lives in projects.rs but is merged at `/api`, not nested
    # beneath `/api/projects`. Keep that deliberate public capability explicit.
    rust_api_paths.add("/api/shared/{}")
    # Generation 1 foundation mounts the exact same API router under `/api/v1` while
    # retaining `/api` as a legacy compatibility alias. Model that Router clone
    # explicitly so the auditor verifies the versioned boundary without
    # requiring a second copy of every Rust route declaration.
    rust_api_paths |= {
        "/api/v1" + path[len("/api"):]
        for path in tuple(rust_api_paths)
        if path == "/api" or path.startswith("/api/")
    }

    web_route_ids = set(re.findall(r'\brequest\(\s*"([a-z][a-z0-9_]*)"', http_transport))
    unknown_web_routes = sorted(web_route_ids - set(http_operations))
    if unknown_web_routes:
        error(f"Web HTTP transport references unknown canonical route ids: {unknown_web_routes}")
    web_api_paths = {
        normalized_route(http_operations[route_id][1])
        for route_id in web_route_ids
        if route_id in http_operations
    }
    missing_paths = sorted(web_api_paths - rust_api_paths)
    if missing_paths:
        error(f"Web HTTP transport references unroutable Rust API paths: {missing_paths}")

    # Path parity alone misses a real class of regressions: a client can call
    # an existing path with a verb that the Rust router never exposes. Parse
    # the concrete request/route calls with a small balanced-parenthesis
    # scanner so this gate remains dependency-free.
    def balanced_calls(source: str, marker: str) -> list[str]:
        calls: list[str] = []
        cursor = 0
        while True:
            start = source.find(marker, cursor)
            if start < 0:
                break
            index = start + len(marker)
            depth = 1
            quote: str | None = None
            escaped = False
            while index < len(source) and depth:
                char = source[index]
                if quote is not None:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == quote:
                        quote = None
                else:
                    if char in ('"', "'", "`"):
                        quote = char
                    elif char == "(":
                        depth += 1
                    elif char == ")":
                        depth -= 1
                index += 1
            if depth == 0:
                calls.append(source[start + len(marker):index - 1])
            cursor = max(index, start + len(marker))
        return calls

    def web_request_method_paths(source: str) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for body in balanced_calls(source, "request("):
            first = re.match(r'\s*"([a-z][a-z0-9_]*)"', body)
            if first is None:
                continue
            route_id = first.group(1)
            operation = http_operations.get(route_id)
            if operation is None:
                continue
            canonical_method, canonical_path = operation
            method_match = re.search(r'\bmethod\s*:\s*"(GET|POST|PUT|PATCH|DELETE)"', body)
            if method_match is not None and method_match.group(1) != canonical_method:
                error(
                    f"Web HTTP route {route_id} overrides canonical method "
                    f"{canonical_method} with {method_match.group(1)}"
                )
            found.add((canonical_method, normalized_route(canonical_path)))
        return found

    def rust_route_method_paths(source: str, prefix: str) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for body in balanced_calls(source, ".route("):
            route_match = re.match(
                r'\s*(?:http_routes::([A-Z0-9_]+)|"([^"]+)")\s*,(.*)',
                body,
                re.DOTALL,
            )
            if route_match is None:
                continue
            constant, literal, router = route_match.groups()
            route = route_constants.get(constant) if constant else literal
            if not route:
                error(f"unknown generated HTTP route constant: {constant}")
                continue
            full = prefix.rstrip("/") if route == "/" else prefix.rstrip("/") + route
            for verb in re.findall(r'(?<![A-Za-z_])(get|post|put|patch|delete)\s*\(', router):
                found.add((verb.upper(), normalized_route(full)))
        return found

    rust_method_paths: set[tuple[str, str]] = set()
    rust_method_paths |= rust_route_method_paths(text("crates/pcr-server/src/lib.rs"), "/api")
    rust_method_paths |= rust_route_method_paths(text("crates/pcr-server/src/bench.rs"), "/api")
    rust_method_paths |= rust_route_method_paths(text("crates/pcr-server/src/sequences.rs"), "/api/sequences")
    rust_method_paths |= rust_route_method_paths(text("crates/pcr-server/src/auth.rs"), "/api/auth")
    project_source = text("crates/pcr-server/src/projects.rs")
    shared_start = project_source.find("pub fn shared_routes")
    personal_start = project_source.find("pub fn routes")
    if shared_start < 0 or personal_start < 0 or personal_start <= shared_start:
        error("project route sections could not be identified for method/path parity")
    else:
        rust_method_paths |= rust_route_method_paths(project_source[shared_start:personal_start], "/api")
        rust_method_paths |= rust_route_method_paths(project_source[personal_start:], "/api/projects")

    rust_method_paths |= {
        (method, "/api/v1" + path[len("/api"):])
        for method, path in tuple(rust_method_paths)
        if path == "/api" or path.startswith("/api/")
    }

    web_method_paths = web_request_method_paths(http_transport)
    missing_method_paths = sorted(web_method_paths - rust_method_paths)
    if missing_method_paths:
        error(f"Web HTTP transport method/path parity drifted: missing={missing_method_paths}")

    # If browser-facing cross-origin mode is enabled, every routed HTTP verb
    # must survive preflight. This specifically prevents PUT-style contracts
    # from existing in the router but being impossible from the browser.
    cors_match = re.search(r'\.allow_methods\(\[([^\]]+)\]\)', server, re.DOTALL)
    if cors_match is None:
        error("CORS method allow-list is missing")
    else:
        cors_methods = set(re.findall(r"Method::(GET|POST|PUT|PATCH|DELETE)", cors_match.group(1)))
        routed_methods = {method for method, _ in rust_method_paths}
        missing_cors = sorted(routed_methods - cors_methods)
        if missing_cors:
            error(f"CORS method allow-list is narrower than the Rust router: {missing_cors}")

    # Streaming account backup routes bypass the Transport object by design;
    # they still have to point at the canonical Rust export/import endpoints.
    export_route = text("web/src/app/(app)/account/data/export/route.ts")
    import_route = text("web/src/app/(app)/account/data/import/route.ts")
    if 'httpRoute("projects_export")' not in export_route or 'httpRoute("projects_import")' not in import_route:
        error("streaming account backup routes drifted from canonical project export/import endpoints")

    # CI is allowed to observe scientific readiness as ready (200) or honestly
    # unqualified (503), but it must validate the complete public component shape.
    ci = text(".github/workflows/ci.yml")
    readiness_markers = (
        "/ready/scientific",
        "200|503",
        '"ready","database","designWorker","runner","scientificToolchain"',
        'typeof j.ready !== "boolean"',
        'typeof j[key].ok !== "boolean"',
    )
    for marker in readiness_markers:
        if marker not in ci:
            error(f"CI scientific-readiness contract lost marker: {marker}")
    for marker in (
        "with_runner_requirement",
        "active_runner_status",
        '"runner": { "ok": runner.is_ok(), "required": state.require_runner }',
        "RUNNER_HEARTBEAT_FRESH_SECONDS",
    ):
        if marker not in text("crates/pcr-server/src/readiness.rs"):
            error(f"external-runner readiness contract lost marker: {marker}")

    # Operator telemetry must stay low-cardinality and retain the scheduler,
    # HTTP and database saturation signals needed to diagnose production load
    # without exposing project/user/sequence labels.
    diagnostics_source = text("crates/pcr-server/src/diagnostics.rs")
    gate_source = text("crates/pcr-application/src/gate.rs")
    for marker in (
        "pcrstudio_worker_failed_jobs_total",
        "pcrstudio_worker_cancelled_jobs_total",
        "pcrstudio_worker_runtime_milliseconds_total",
        "pcrstudio_http_requests_total",
        "pcrstudio_http_server_errors_total",
        "pcrstudio_database_pool_in_use",
        '"privacy": "no-user-or-sequence-data"',
    ):
        if marker not in diagnostics_source:
            error(f"operator metrics lost low-cardinality marker: {marker}")
    for marker in (
        "queue_wait_milliseconds_total",
        "worker_runtime_milliseconds_total",
        "a_heavy_cancellable_waiter_keeps_fifo_priority_over_later_light_jobs",
        "operator_metrics_count_success_and_failure_without_request_data",
    ):
        if marker not in gate_source:
            error(f"worker scheduler observability/fairness guard lost marker: {marker}")

    # Foundation request paths must fail closed rather than terminate the
    # process. Tests may use expect/unwrap to state their fixtures, but active
    # account/project/server code may not regain those shortcuts.
    panicish = re.compile(r"\b(?:unwrap|expect)\s*\(|\b(?:panic|todo|unimplemented)!\s*\(")
    for base in ("crates/pcr-accounts/src", "crates/pcr-projects/src", "crates/pcr-server/src"):
        for path in (ROOT / base).rglob("*.rs"):
            source = path.read_text(encoding="utf-8")
            production = source.split("#[cfg(test)]", 1)[0]
            if panicish.search(production):
                error(f"production foundation panic/unwrap/expect returned: {path.relative_to(ROOT)}")

            # A mutation may not commit and only then perform a fallible row
            # decode or database read to construct the response. That pattern
            # can turn a successful durable write into an HTTP failure and
            # induce retries/duplicates.
            lines = production.splitlines()
            for index, line in enumerate(lines):
                if ".commit().await" not in line:
                    continue
                tail = "\n".join(lines[index + 1:index + 13])
                if "try_get(" in tail or re.search(r"\.(?:fetch_|execute)\w*\(", tail):
                    error(
                        f"post-COMMIT fallible materialization/read returned: "
                        f"{path.relative_to(ROOT)}:{index + 1}"
                    )

    if "create_session.then(SessionToken::generate)" in auth_store:
        error("registration/recovery session token ownership regressed to an optional post-commit invariant")
    if "pub async fn change_email" not in auth_store or '.route(http_routes::AUTH_EMAIL, patch(change_email))' not in auth_routes:
        error("full-stack sign-in email change contract is incomplete")
    if "endAllSessionsAction" not in auth_web or "await api.endAllSessions(token)" not in auth_web:
        error("sign-out-everywhere no longer waits for server-side revocation")

    workspace = text("web/src/components/project/workspace.tsx")
    autosave = text("web/src/components/project/use-draft-autosave.ts")
    project_routes = text("crates/pcr-server/src/projects.rs")
    if "serverUpdatedAt" not in autosave or "blockedByConflict" not in autosave:
        error("project autosave lost optimistic-concurrency/conflict blocking")
    if "ProjectError::Conflict" not in project_routes:
        error("project API no longer maps optimistic-concurrency conflicts explicitly")
    if "pg_advisory_xact_lock" not in projects:
        error("project store lost transaction-scoped advisory locking")
    if "project_in_transaction" not in projects or "run_in_transaction" not in projects:
        error("project mutations no longer materialize their response before COMMIT")
    if re.search(r"transaction\.commit\(\)\.await\.map_err\(store\)\?;\s*self\.(?:get|run)\(", projects):
        error("project mutation regained a post-COMMIT read that can report false failure after a committed write")
    if "save_run_with_project" not in projects:
        error("run-save transaction no longer materializes both Run and Project before COMMIT")
    run_and_save_match = re.search(r"async fn run_and_save\b(.*?)(?=\nasync fn |\nfn |\Z)", project_routes, re.DOTALL)
    if run_and_save_match is None or "save_run_with_project" not in run_and_save_match.group(1):
        error("Run & Save handler no longer uses the pre-COMMIT Run+Project transaction result")
    else:
        run_and_save_body = run_and_save_match.group(1)
        save_call = run_and_save_body.find("save_run_with_project")
        if save_call >= 0 and re.search(r"projects\.(?:get|run)\(", run_and_save_body[save_call:]):
            error("Run & Save handler regained a post-save project-store read")

    shared_struct = re.search(r"struct SharedRunAnswer\s*\{(.*?)\n\}", project_routes, re.DOTALL)
    if shared_struct is None:
        error("public shared-run response DTO is missing")
    elif "project_id" in shared_struct.group(1) or "projectId" in shared_struct.group(1):
        error("public shared-run DTO exposes a private project identifier")
    if 'body.remove("projectId")' in project_routes or "serde_json::to_value(run)" in project_routes:
        error("public shared-run response regressed to serialize-then-redact behavior")

    shared_loader = text("web/src/lib/projects/load.ts")
    if 'status: "unreachable"' not in shared_loader:
        error("shared/public project loaders no longer distinguish outage from missing data")

    # Generic UI primitives should be safe inside forms by default, preserve
    # existing accessible descriptions, and never reintroduce raw native
    # buttons whose browser-default submit behavior is ambiguous.
    button_source = text("web/src/components/ui/button.tsx")
    form_parts = text("web/src/components/form-parts.tsx")
    if 'type={isNative ? (type ?? "button") : type}' not in button_source:
        error("shared Button lost default type=button protection")
    if 'children.props["aria-describedby"]' not in form_parts or 'filter(Boolean).join(" ")' not in form_parts:
        error("WrappedField no longer preserves existing aria-describedby values")
    if '<fieldset className={cn("min-w-0 space-y-1.5", className)}' not in form_parts or '<legend className="text-sm font-medium">{label}</legend>' not in form_parts:
        error("FieldGroup lost semantic fieldset/legend grouping")

    # UI/UX closure: visible labels must stay programmatically associated, data
    # tables must retain header/caption semantics, and interactive composites
    # must use native controls instead of partial ARIA patterns.
    production_tsx = [
        path for path in (ROOT / "web/src").rglob("*.tsx")
        if not path.name.endswith(".test.tsx") and path.name != "label.tsx"
    ]
    for path in production_tsx:
        source = path.read_text(encoding="utf-8")
        for tag in re.finditer(r"<Label\b([^>]*)>", source, re.DOTALL):
            if re.search(r"\bhtmlFor\s*=", tag.group(1)) is None:
                line = source.count("\n", 0, tag.start()) + 1
                error(f"visible Label lacks htmlFor association: {path.relative_to(ROOT)}:{line}")
        tables = len(re.findall(r"<table\b", source))
        captions = len(re.findall(r"<caption\b", source))
        if tables != captions:
            error(f"data-table caption parity drifted: {path.relative_to(ROOT)} tables={tables} captions={captions}")
        for th in re.finditer(r"<th\b([^>]*)>", source, re.DOTALL):
            if re.search(r"\bscope\s*=", th.group(1)) is None:
                line = source.count("\n", 0, th.start()) + 1
                error(f"table header lacks scope: {path.relative_to(ROOT)}:{line}")
        for button in re.finditer(r"<button\b([^>]*)>", source, re.DOTALL):
            attrs = button.group(1)
            if ("p-0.5" in attrs or "py-0.5" in attrs) and not any(
                marker in attrs for marker in ("size-6", "min-h-6", "h-6", "h-7", "h-8", "h-9", "min-h-9", "p-2", "p-3")
            ):
                line = source.count("\n", 0, button.start()) + 1
                error(f"raw button may fall below 24px target size: {path.relative_to(ROOT)}:{line}")
        # Arbitrary sub-12px type is too easy to proliferate across the dense
        # workbench. Two SVG renderers retain 10px geometry labels because their
        # font size is part of the drawing scale rather than document typography.
        typography_scale_exceptions = {
            "web/src/components/design/sequence-map.tsx",
            "web/src/components/design/gel-simulator.tsx",
        }
        rel = path.relative_to(ROOT).as_posix()
        if rel not in typography_scale_exceptions and re.search(r"text-\[(?:9|10|11)px\]", source):
            error(f"sub-12px document typography bypasses the shared text scale: {rel}")

    primer_matrix = text("web/src/components/design/primer-matrix.tsx")
    if re.search(r"<th\b[^>]*\bonClick=", primer_matrix, re.DOTALL):
        error("sortable primer-matrix header regressed to interactive <th>; keep a native button inside the columnheader")
    if '<button\n                    type="button"\n                    onClick={() => handleSort("rank")}' not in primer_matrix:
        error("primer-matrix sortable header lost native button semantics")
    sequence_input = text("web/src/components/design/sequence-input.tsx")
    if 'role="tablist"' in sequence_input or 'role="tab"' in sequence_input:
        error("sequence intake modes regressed to an incomplete custom ARIA tab pattern")
    if 'aria-label={`${label} file`}' not in sequence_input:
        error("sequence upload control lost its accessible file-input name")
    lamp_fields = text("web/src/components/design/engine-fields/lamp-fields.tsx")
    if 'role="listbox"' in lamp_fields or 'role="option"' in lamp_fields:
        error("LAMP protocol search regressed to an incomplete custom listbox pattern")
    run_comparison = text("web/src/components/project/run-comparison.tsx")
    if 'overflow-x-auto' not in run_comparison or 'min-w-[36rem]' not in run_comparison:
        error("run comparison lost bounded horizontal table scrolling")
    if 'workspace-step-heading' not in text("web/src/components/project/workspace-parts.tsx") or 'getElementById("workspace-step-heading")?.focus' not in workspace:
        error("workspace step changes no longer move focus to the new step heading")
    app_loading = text("web/src/app/(app)/loading.tsx")
    for marker in ('role="status"', 'aria-live="polite"', 'aria-busy="true"', 'Loading page…'):
        if marker not in app_loading:
            error(f"authenticated route loading boundary lost accessible progress marker: {marker}")

    critical_journey = text("web/e2e/critical-journey.spec.ts")
    for ui_marker in ("visibleControlAccessibilityProblems", "width: 390", "workspace-step-heading"):
        if ui_marker not in critical_journey:
            error(f"authenticated workbench accessibility regression coverage lost marker: {ui_marker}")
    module_matrix = text("web/e2e/all-module-workspaces.spec.ts")
    for matrix_marker in ("Object.keys(MODULE_BINDINGS)", "toHaveLength(21)", 'input[name="moduleId"]'):
        if matrix_marker not in module_matrix:
            error(f"catalogue-wide workspace E2E coverage lost marker: {matrix_marker}")
    for path in (ROOT / "web/src").rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        for tag in re.finditer(r"<button\b([^>]*)>", source, re.DOTALL):
            line_start = source.rfind("\n", 0, tag.start()) + 1
            if source[line_start:tag.start()].lstrip().startswith("//"):
                continue
            if re.search(r"\btype\s*=", tag.group(1)) is None:
                line = source.count("\n", 0, tag.start()) + 1
                error(f"native button without explicit type: {path.relative_to(ROOT)}:{line}")
        for tag in re.finditer(r"<[^>]+\btarget\s*=\s*[\"']_blank[\"'][^>]*>", source, re.IGNORECASE | re.DOTALL):
            attrs = tag.group(0)
            rel = re.search(r"\brel\s*=\s*[\"']([^\"']*)[\"']", attrs, re.IGNORECASE)
            if rel is None or "noopener" not in rel.group(1).lower().split():
                line = source.count("\n", 0, tag.start()) + 1
                error(f"target=_blank link lacks noopener: {path.relative_to(ROOT)}:{line}")

    # UI/UX closure invariants: design-system semantics, mobile ergonomics, and
    # accessible naming must not depend on visual proximity or accidental browser defaults.
    web_sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in (ROOT / "web/src").rglob("*.tsx")
    }
    for rel, source in web_sources.items():
        if "amber-" in source and rel != "web/src/components/design/gel-simulator.tsx":
            error(f"UI semantic warning styling bypasses design tokens with amber palette classes: {rel}")
        for tag in re.finditer(r"<div\b([^>]*)>", source, re.DOTALL):
            attrs = tag.group(1)
            if "aria-label=" in attrs and "role=" not in attrs:
                line = source.count("\n", 0, tag.start()) + 1
                error(f"generic div has aria-label without an accessibility role: {rel}:{line}")
    if 'className="lg:sticky lg:top-4 lg:col-span-4"' not in workspace:
        error("workspace parameter sidebar regained mobile sticky positioning")
    bench_tools = text("web/src/components/design/bench-tools.tsx")
    if bench_tools.count("inline-flex min-h-6 items-center rounded px-1 text-xs") < 2:
        error("bench-tools disclosure controls lost the 24px minimum interactive target")
    if primer_matrix.count("min-h-6") < 5:
        error("primer-matrix sortable controls lost the 24px minimum interactive target")
    global_error = text("web/src/app/global-error.tsx")
    if "minHeight: 40" not in global_error:
        error("global error recovery control lost a robust standalone target size")

    # Key semantic color pairs must retain WCAG AA normal-text contrast in both
    # light and dark themes. This is intentionally computed from the canonical
    # OKLCH tokens rather than asserted by visual inspection: small palette
    # adjustments should not silently turn warning/status text unreadable.
    globals_css = text("web/src/app/globals.css")
    theme_blocks = {
        "light": re.search(r":root\s*\{(.*?)\n\}", globals_css, re.DOTALL),
        "dark": re.search(r"\.dark\s*\{(.*?)\n\}", globals_css, re.DOTALL),
    }

    def oklch_tokens(block: str) -> dict[str, tuple[float, float, float]]:
        return {
            match.group(1): tuple(float(value) for value in match.groups()[1:])
            for match in re.finditer(
                r"--([\w-]+):\s*oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)",
                block,
            )
        }

    def oklch_to_linear_srgb(value: tuple[float, float, float]) -> tuple[float, float, float]:
        lightness, chroma, hue_degrees = value
        hue = math.radians(hue_degrees)
        a = chroma * math.cos(hue)
        b = chroma * math.sin(hue)
        l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
        m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
        s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
        l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
        return (
            min(1.0, max(0.0, +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s)),
            min(1.0, max(0.0, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s)),
            min(1.0, max(0.0, -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)),
        )

    def relative_luminance(rgb: tuple[float, float, float]) -> float:
        red, green, blue = rgb
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    def contrast_ratio(foreground: tuple[float, float, float], background: tuple[float, float, float]) -> float:
        fg = relative_luminance(oklch_to_linear_srgb(foreground))
        bg = relative_luminance(oklch_to_linear_srgb(background))
        high, low = max(fg, bg), min(fg, bg)
        return (high + 0.05) / (low + 0.05)

    semantic_pairs = (
        ("foreground", "background"),
        ("primary-foreground", "primary"),
        ("secondary-foreground", "secondary"),
        ("muted-foreground", "muted"),
        ("success-foreground", "success"),
        ("warning-foreground", "warning"),
        ("destructive-foreground", "destructive"),
    )
    for theme, match in theme_blocks.items():
        if match is None:
            error(f"{theme} theme token block is missing from globals.css")
            continue
        tokens = oklch_tokens(match.group(1))
        for foreground, background in semantic_pairs:
            if foreground not in tokens or background not in tokens:
                error(f"{theme} theme lost semantic color token pair {foreground}/{background}")
                continue
            ratio = contrast_ratio(tokens[foreground], tokens[background])
            if ratio < 4.5:
                error(
                    f"{theme} semantic contrast fails WCAG AA normal text: "
                    f"{foreground} on {background} = {ratio:.2f}:1"
                )

    for rel in ("web/src/app/(app)/error.tsx", "web/src/app/error.tsx", "web/src/app/global-error.tsx"):
        boundary = text(rel)
        if "error.message" in boundary:
            error(f"unexpected-error boundary reflects raw error.message: {rel}")
        if "No project data was changed" in boundary:
            error(f"unexpected-error boundary makes an unverifiable mutation claim: {rel}")

    # Keep the Next runtime above the August 2026 critical-RCE security floor.
    package = json.loads(text("web/package.json") or "{}")
    next_version = str(package.get("dependencies", {}).get("next", ""))
    version_match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", next_version)
    if version_match is None:
        error("Next runtime must remain exact-pinned to a concrete semver")
    else:
        version = tuple(int(part) for part in version_match.groups())
        if version[0] == 16 and version < (16, 3, 3):
            error(f"Next runtime regressed below the 16.3.3 critical-RCE security floor: {next_version}")
        if version[0] < 16:
            error(f"Next runtime regressed to an unsupported/older major for this release line: {next_version}")
    lockfile = text("pnpm-lock.yaml")
    if next_version and f"next:\n        specifier: {next_version}" not in lockfile:
        error("pnpm lockfile importer drifted from the exact-pinned Next runtime")

    # React Server Components/Functions have had several security releases in
    # this release line. Keep the framework runtime trio exact-pinned instead
    # of relying only on the frozen lockfile to hold a safe patch.
    react_version = str(package.get("dependencies", {}).get("react", ""))
    react_dom_version = str(package.get("dependencies", {}).get("react-dom", ""))
    for dependency, version in (("react", react_version), ("react-dom", react_dom_version)):
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
        if match is None:
            error(f"{dependency} runtime must remain exact-pinned to a concrete semver")
            continue
        parsed = tuple(int(part) for part in match.groups())
        if parsed < (19, 2, 8):
            error(f"{dependency} regressed below the current 19.2.8 RSC security floor: {version}")
        if f"{dependency}:\n        specifier: {version}" not in lockfile:
            error(f"pnpm lockfile importer drifted from exact-pinned {dependency} runtime")
    if react_version != react_dom_version:
        error(f"React/ReactDOM runtime patch mismatch: react={react_version}, react-dom={react_dom_version}")

    rate = text("crates/pcr-server/src/rate_limit.rs")
    if "with_shared_store" not in rate or "rate_limit_bucket" not in auth_store:
        error("shared PostgreSQL rate-limit contract is incomplete")

    readiness = text("crates/pcr-server/src/readiness.rs")
    if "pub async fn scientific_ready" not in readiness or "scientificToolchain" not in readiness:
        error("application/scientific readiness split is missing")
    if re.search(r"\.route\(\s*http_routes::SCIENTIFIC_READY", server) is None:
        error("scientific readiness endpoint is not routed")

    # Omnibus test/config invariants: a unit contract must not silently turn
    # green merely because a live API/worker was unavailable, and explicit
    # production resource overrides must fail fast instead of being clamped or
    # ignored into a different deployment than the operator requested.
    page_plan_test = text("web/src/components/design/page-plan.test.ts")
    if "describe.skipIf" in page_plan_test or "127.0.0.1:8080/api/modules" in page_plan_test:
        error("page-plan registry coverage regained a live-API green skip")
    if "module-contracts.json" not in page_plan_test:
        error("page-plan registry coverage is no longer pinned to the canonical module contract")

    rust_tests = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "crates").rglob("*.rs")
        if "/tests/" in path.as_posix() or "#[cfg(test)]" in path.read_text(encoding="utf-8")
    )
    if "std::env::set_var(" in rust_tests or "std::env::remove_var(" in rust_tests:
        error("parallel Rust tests regained process-global environment mutation")

    # Engine validation is an external-input boundary. Validation drift must
    # return an InvalidRequest rather than turning a previously impossible
    # branch into a process panic. Test-only assertions remain allowed.
    for path in (ROOT / "crates/pcr-core/src/engines").glob("*.rs"):
        source = path.read_text(encoding="utf-8", errors="replace")
        production = source.split("#[cfg(test)]", 1)[0]
        if "unreachable!(" in production:
            error(f"production engine validation regained unreachable! panic: {path.name}")

    export_tests = text("crates/pcr-server/tests/export.rs")
    if 'std::env::var("PCR_PYTHON").is_ok_and' not in export_tests or "the configured design worker must save a run" not in export_tests:
        error("configured-worker integration failures can silently skip share/run tests again")

    worker_source = text("crates/pcr-worker-client/src/lib.rs")
    if "unwrap_or(120)" not in worker_source:
        error("worker default timeout drifted from the documented 120-second request-deadline contract")
    for marker in (
        "InvalidWorkerTimeout",
        "InvalidWorkerConcurrency",
        "InvalidWorkerQueue",
        "InvalidTrustedProxy",
        "validate_worker_timeout(&raw)?",
        "validate_worker_count(&raw, false)?",
        "validate_worker_count(&raw, true)?",
        "validate_trusted_proxies(&raw)?",
    ):
        if marker not in server:
            error(f"startup configuration fail-fast contract lost marker: {marker}")

    gate_source = text("crates/pcr-application/src/gate.rs")
    if "capacity: usize" not in gate_source or "self.capacity" not in gate_source:
        error("worker-ceiling observability drifted back to transient available permits")
    main_source = text("crates/pcr-server/src/main.rs")
    if "Gate::shared()" not in main_source or ".run(move || Ok(pcr_server::routes::catalogue(&warm_registry)))" not in main_source:
        error("startup catalogue warming no longer respects the shared request-worker gate")
    if "reserved operational probe" not in gate_source or "sequentially" not in readiness:
        error("worker-capacity documentation/readiness serialization contract drifted")

    readme = text("README.md")
    for marker in (
        "PCR_MAX_QUEUED_WORKERS",
        "PCR_CORS_ORIGINS",
        "1–299 seconds",
        "malformed origins are rejected",
    ):
        if marker not in readme:
            error(f"deployment configuration documentation lost marker: {marker}")

    # Build-toolchain declarations are one contract. SQLx 0.9's supported Rust
    # floor is 1.94, so an older workspace/CI/container pin is a guaranteed
    # clean-runner build failure rather than a preference.
    cargo_toml = text("Cargo.toml")
    api_dockerfile = text("docker/api.Dockerfile")
    if 'sqlx = { version = "0.9"' in cargo_toml:
        for marker, where in ((
            'rust-version = "1.94"', cargo_toml
        ), (
            'rustup toolchain install 1.94', ci
        ), (
            'FROM rust:1.94-bookworm', api_dockerfile
        )):
            if marker not in where:
                error(f"Rust toolchain drifted below the SQLx 0.9 MSRV contract: missing {marker}")

    # CI-only quality/security tools must be exact-pinned explicitly. They are
    # intentionally not scientific-worker dependencies and therefore do not
    # belong in tools/uv.lock.
    for marker in (
        "uvx --from ruff==0.16.5 ruff check .",
        "uvx --from ruff==0.16.5 ruff format --check .",
        "uvx --from pip-audit==2.10.1 pip-audit",
    ):
        if marker not in ci:
            error(f"CI quality/security tool pin drifted: {marker}")
    if ci.count('uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9') < 3 or ci.count('version: "0.12.8"') < 3:
        error("CI uv installer/version pin drifted from the release toolchain contract")
    if 'uv export --frozen --extra folding --no-emit-project' not in ci:
        error("Python dependency audit no longer covers the production folding extra")
    if "NEXT_PUBLIC_SITE_URL: http://localhost:3000" not in ci or "NEXT_PUBLIC_SITE_URL: http://localhost:3100" not in ci:
        error("CI frontend builds no longer set the public-origin variable the Web source actually reads")
    if re.search(r"(?m)^\s+SITE_URL:\s+http://localhost:", ci):
        error("CI frontend build regressed to the unused SITE_URL variable")
    for marker in (
        "docker compose -f compose.yaml config -q",
        "docker compose -f compose.yaml -f compose.vm.yaml config -q",
    ):
        if marker not in ci:
            error(f"CI deployment configuration validation lost marker: {marker}")
    for marker in (
        "uv==0.12.8",
        "uv sync --project tools --frozen --extra folding --no-dev --no-editable",
    ):
        if marker not in api_dockerfile:
            error(f"API image worker no longer reproduces the frozen CI environment: {marker}")
    if "cached_probe(&self.worker" not in readiness or "cached_probe(&self.toolchain" not in readiness:
        error("readiness probes lost single-flight protection against overlapping subprocesses")
    for marker in (
        "use tokio::sync::{watch, Mutex};",
        "struct ProbeCache",
        "in_flight: bool",
        "cache.generation.subscribe()",
        "tokio::spawn(async move",
        "tokio::task::spawn_blocking(probe)",
        "send_modify(|value| *value = value.wrapping_add(1))",
        "let database = state.database().await;",
        "tokio::join!(state.database(), state.runner(), scientific)",
        '"scientificReadiness": "/ready/scientific"',
        "concurrent_readiness_checks_share_one_in_flight_probe",
        "cancelled_caller_does_not_spawn_a_second_probe",
    ):
        if marker not in readiness:
            error(f"readiness async single-flight contract lost marker: {marker}")

    profile_defaults_test = text("crates/pcr-core/tests/profile_defaults.rs")
    enzymes_test = text("crates/pcr-server/tests/enzymes.rs")
    if "PCR_PYTHON" not in profile_defaults_test or "worker vocabulary contract must run" not in profile_defaults_test or "panic!" not in profile_defaults_test:
        error("profile-defaults worker contract can silently skip despite a configured worker")
    if "PCR_PYTHON" not in enzymes_test or "configured" not in enzymes_test.lower() or "panic!" not in enzymes_test:
        error("enzyme worker contract can silently skip despite a configured worker")

    # Configuration validation must agree with the consumers that read the same
    # environment. In particular, accepting a whitespace-padded value at
    # startup and then silently falling back while constructing a Worker/Gate
    # is configuration drift, not a harmless parse detail. Database-pool
    # overrides follow the same fail-fast rule as worker capacity.
    accounts_source = text("crates/pcr-accounts/src/lib.rs")
    for marker in (
        "fn parse_pool_setting(",
        "explicit_pool_settings_fail_instead_of_clamping_or_falling_back",
        'pool_setting("PCR_DB_MIN_CONNECTIONS", 2, 0, max_connections)?',
        'pool_setting("PCR_DB_ACQUIRE_TIMEOUT_SECONDS", 5, 1, 60)?',
    ):
        if marker not in accounts_source:
            error(f"database-pool fail-fast contract lost marker: {marker}")
    if ".map_or(default, |value| value.clamp" in accounts_source:
        error("database-pool overrides are silently clamped/fallback again")
    if '.and_then(|v| v.trim().parse().ok())' not in worker_source:
        error("worker timeout consumer no longer parses the same trimmed value startup validates")
    if gate_source.count('.and_then(|value| value.trim().parse::<usize>().ok())') < 2:
        error("worker gate consumers no longer parse the same trimmed values startup validates")
    storage_source = text("crates/pcr-storage/src/lib.rs")
    security_source = text("crates/pcr-security/src/lib.rs")
    for marker in (
        'env_utf8("PCR_BIND")?',
        'pcr_storage::database_url_from_environment()',
        'env_utf8("PCR_WORKER_TIMEOUT_SECONDS")?',
        'env_utf8("PCR_MAX_CONCURRENT_WORKERS")?',
        'env_utf8("PCR_MAX_QUEUED_WORKERS")?',
        'env_utf8("PCR_TRUSTED_PROXIES")?',
        'env_utf8("PCR_PYTHON")?',
    ):
        if marker not in server:
            error(f"startup environment encoding validation lost marker: {marker}")
    for marker in (
        'pub fn secret_from_environment(',
        'SecretSourceError::ConflictingSources',
        'std::fs::read_to_string(&path)',
    ):
        if marker not in security_source:
            error(f"canonical deployment secret-source authority lost marker: {marker}")
    database_secret = re.search(
        r"pub fn database_url_from_environment\s*\([^)]*\)\s*->.*?\{(.*?)\n\}",
        storage_source,
        re.DOTALL,
    )
    if database_secret is None:
        error("database URL secret resolver is missing")
    else:
        body = database_secret.group(1)
        for marker in (
            "pcr_security::secret_from_environment(",
            '"PCR_DATABASE_URL"',
            '"PCR_DATABASE_URL_FILE"',
            "normalize_database_url_secret(value)",
        ):
            if marker not in body:
                error(f"database URL secret resolver lost canonical marker: {marker}")
    if 'pcr_security::secret_from_environment(name, file_name)' not in server:
        error("server optional secrets no longer delegate to canonical deployment secret-source authority")
    if "fn env_or_file_utf8(" in server or "std::fs::read_to_string(&path)" in server:
        error("deployment secret-source parsing was duplicated back into pcr-server")
    sequence_source = text("crates/pcr-server/src/sequences.rs")
    for marker in (
        "fn validate_operator_token(",
        "fn validate_ncbi_api_key(",
        "validate_ncbi_api_key(value)?;",
    ):
        if marker not in server:
            error(f"header/external credential validation lost marker: {marker}")
    for marker in (
        "api_key: Option<String>",
        "fn fetch_unavailable_reason(",
        "if let Some(reason) = fetch_unavailable_reason(&state.email)",
        "reserve_external_service_slot(",
        "MAX_NCBI_RESERVATION_WAIT",
    ):
        if marker not in sequence_source:
            error(f"NCBI availability/quota authority lost marker: {marker}")
    contact_index = sequence_source.find("if let Some(reason) = fetch_unavailable_reason(&state.email)")
    reserve_index = sequence_source.find(".reserve_external_service_slot(")
    if contact_index < 0 or reserve_index < 0 or contact_index > reserve_index:
        error("NCBI fetch reserves shared quota before validating contact availability")
    for marker in (
        "WHERE NOT c.convalidated",
        "migration left unvalidated relational constraints in the active schema",
    ):
        if marker not in storage_source:
            error(f"canonical migration full-validation invariant lost marker: {marker}")
    if "type LastProbe = std::sync::Arc<ProbeCache>;" not in readiness:
        error("readiness single-flight cache type drifted")
    for marker in (
        "PCR_DB_MAX_CONNECTIONS",
        "PCR_DB_MIN_CONNECTIONS",
        "PCR_DB_ACQUIRE_TIMEOUT_SECONDS",
        "fail startup",
    ):
        if marker not in readme:
            error(f"database-pool deployment documentation lost marker: {marker}")

    cookie = text("web/src/lib/auth/session-cookie.ts")
    proxy = text("web/src/proxy.ts")
    next_config = text("web/next.config.ts")
    for marker in ("SECURE_SESSION_COOKIES", "NEXT_PUBLIC_SITE_URL"):
        if marker not in cookie:
            error(f"session cookie public-origin authority missing {marker}")
    if "SECURE_SESSION_COOKIES" not in proxy:
        error("CSP upgrade-insecure-requests no longer follows actual public-origin TLS state")
    if "PUBLIC_ORIGIN_IS_HTTPS" not in next_config:
        error("HSTS no longer follows the configured public-origin TLS state")

    compose = text("compose.yaml")
    env_example = text(".env.example")
    for marker in (
        "POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password",
        "PCR_DATABASE_URL_FILE: /run/secrets/database_url",
        "PCR_POSTGRES_PASSWORD_FILE",
        "PCR_DATABASE_URL_FILE_HOST",
    ):
        if marker not in compose and marker not in env_example:
            error(f"file-backed deployment secret contract lost marker: {marker}")
    if "PCR_DATABASE_URL: postgres://" in compose or "POSTGRES_PASSWORD: ${" in compose:
        error("stock Compose regressed to exposing the database credential through environment interpolation")
    for marker in ("file-backed deployment secrets", "/run/secrets/postgres_password", "/run/secrets/database_url"):
        if marker not in readme:
            error(f"file-backed deployment secret documentation lost marker: {marker}")
    for marker in ("data:", "app:", "egress:", "edge:"):
        if marker not in compose:
            error(f"deployment network segmentation missing {marker.rstrip(':')} network")
    if "172.29.0.0/24" not in compose:
        error("trusted app-network subnet drifted from deployment proxy contract")

    atlas_probe = text("knowledge/atlas/engines/pair-and-probe/02-qpcr-probe.md")
    profiles = text("crates/pcr-core/profiles.toml")
    qpcr_profile = profiles.split('id = "qpcr-probe"', 1)[1].split("[[profile]]", 1)[0] if 'id = "qpcr-probe"' in profiles else ""
    if "| Runtime profile status | experimental |" not in atlas_probe or 'status = "experimental"' not in qpcr_profile:
        error("qPCR-probe current experimental status documentation/profile binding is incomplete")
    if "external-authority-required" not in atlas_probe or "candidate_set_sha256" not in atlas_probe or "does not substitute ordinary-DNA Primer3 thermodynamics" not in atlas_probe:
        error("qPCR-probe Atlas lost the typed hash-bound external MGB authority boundary")
