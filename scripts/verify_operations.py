"""Validate the resolved deployment and live local security boundaries."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import psycopg
import redis

ROOT = Path(__file__).resolve().parents[1]
APPLICATION_SECRETS = {"django_secret_key", "mfa_encryption_key"}
SERVICE_SECRETS = {
    "api": APPLICATION_SECRETS | {"db_runtime_password"},
    "migrate": APPLICATION_SECRETS | {"db_migrator_password"},
    "tools": APPLICATION_SECRETS | {"db_test_password"},
    "postgres": {"db_admin_password", "db_migrator_password", "db_runtime_password", "db_test_password"},
}
LOCAL_SECRETS = set().union(*SERVICE_SECRETS.values())


class ShellScripts(HTMLParser):
    """Read the actual served shell independently from the build-time CSP generator."""

    def __init__(self) -> None:
        super().__init__()
        self.inline: list[str] = []
        self.script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.script = None if any(name == "src" for name, _ in attrs) else []

    def handle_data(self, data: str) -> None:
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.script is not None:
            content = "".join(self.script)
            if content:
                self.inline.append(content)
            self.script = None


def verify_shell_policy(html: str, policy: str) -> None:
    directives = {parts[0]: parts[1:] for directive in policy.split(";") if (parts := directive.split())}
    scripts = directives.get("script-src", [])
    if "'self'" not in scripts or any(value != "'self'" and not value.startswith("'sha256-") for value in scripts):
        raise AssertionError("Served shell has an unsafe script policy")
    parser = ShellScripts()
    parser.feed(html)
    expected = {"'sha256-" + base64.b64encode(hashlib.sha256(content.encode()).digest()).decode() + "'" for content in parser.inline}
    if {value for value in scripts if value.startswith("'sha256-")} != expected:
        raise AssertionError("Served shell and immutable CSP script hashes differ")


def verify_configuration(configuration: dict) -> None:
    services = configuration["services"]
    if set(services) != {"api", "caddy", "postgres", "valkey", "migrate", "mailpit", "tools"}:
        raise AssertionError("Unexpected local service topology")
    for name, service in services.items():
        if service.get("network_mode") == "host":
            raise AssertionError(f"Runtime host networking on {name}")
        for volume in service.get("volumes", []):
            if "docker.sock" in str(volume):
                raise AssertionError(f"Docker socket mounted into {name}")
        ports = service.get("ports", [])
        if name not in {"caddy", "mailpit"} and ports:
            raise AssertionError(f"Private service {name} publishes a host port")
        for port in ports:
            if port.get("host_ip") != "127.0.0.1":
                raise AssertionError(f"Non-loopback local port on {name}")
    database_mounts = services["postgres"]["volumes"]
    if not any(v.get("type") == "volume" and v["target"] == "/var/lib/postgresql" for v in database_mounts):
        raise AssertionError("PostgreSQL18 data volume must mount the version-neutral parent")
    for name in ("api", "migrate", "caddy"):
        service = services[name]
        if not service.get("read_only") or "ALL" not in service.get("cap_drop", []):
            raise AssertionError(f"Read-only/capability boundary missing on {name}")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            raise AssertionError(f"Privilege escalation boundary missing on {name}")
    for name in ("data", "cache", "mail"):
        if not configuration["networks"][name].get("internal"):
            raise AssertionError(f"Private {name} network is not internal")
    if services["api"]["environment"]["PGUSER"] == services["migrate"]["environment"]["PGUSER"]:
        raise AssertionError("Runtime and migration database identities must differ")
    local_gid = services["tools"]["user"].split(":")[1]
    for name in ("api", "migrate", "postgres"):
        if services[name].get("group_add") != [local_gid]:
            raise AssertionError(f"Persisted local secret group missing on {name}")
    if services["postgres"].get("user") != "70:70":
        raise AssertionError("Database entrypoint must preserve its restricted supplementary group")
    for name, service in services.items():
        mounted = service.get("secrets", [])
        expected = SERVICE_SECRETS.get(name, set())
        if {secret["source"] for secret in mounted} != expected or len(mounted) != len(expected):
            raise AssertionError(f"Unexpected secret access on {name}")
        if any(secret.get("target") != f"/run/secrets/{secret['source']}" for secret in mounted):
            raise AssertionError(f"Unexpected secret mount target on {name}")
        # File-backed Compose secrets retain host permissions; uid/gid/mode overrides are ignored.
        if any({"uid", "gid", "mode"} & secret.keys() for secret in mounted):
            raise AssertionError(f"Unsupported file-backed secret permission override on {name}")
    for name in ("api", "migrate"):
        if any(volume.get("type") == "bind" for volume in services[name].get("volumes", [])):
            raise AssertionError(f"Unexpected host directory access on {name}")


def verify_secret_permissions(state: Path) -> None:
    for directory in (state, state / "secrets"):
        if stat.S_IMODE(directory.stat().st_mode) != 0o700:
            raise AssertionError("Local secret parent directory is not private")
    if stat.S_IMODE((state / "compose.env").stat().st_mode) != 0o600:
        raise AssertionError("Persisted local identity configuration is not private")
    for name in LOCAL_SECRETS:
        details = (state / "secrets" / name).stat()
        if not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) & ~0o440:
            raise AssertionError(f"Local secret permissions are too broad: {name}")
        if (details.st_uid, details.st_gid) != (os.getuid(), os.getgid()):
            raise AssertionError(f"Local secret ownership differs from the persisted tools identity: {name}")


def verify_mounted_secrets(directory: Path, expected: set[str]) -> None:
    if {path.name for path in directory.iterdir()} != expected:
        raise AssertionError("Unexpected mounted secret access")
    for name in expected:
        path = directory / name
        if stat.S_IMODE(path.stat().st_mode) != 0o440 or not path.read_text().strip():
            raise AssertionError(f"Mounted secret is not restricted and readable: {name}")


def verify_live() -> None:
    verify_secret_permissions(ROOT / ".local")
    verify_mounted_secrets(Path("/run/secrets"), SERVICE_SECRETS["tools"])
    secret = (ROOT / ".local/secrets/db_runtime_password").read_text().strip()
    with psycopg.connect(host="postgres", dbname="pcrstudio", user="pcrstudio_runtime", password=secret) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT has_database_privilege(current_user, current_database(), 'CREATE'), has_schema_privilege(current_user, 'public', 'CREATE')")
            if cursor.fetchone() != (False, False):
                raise AssertionError("Runtime database identity has DDL authority")
            cursor.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user")
            if cursor.fetchone() != (False, False, False):
                raise AssertionError("Runtime database identity has administrative authority")
            cursor.execute("SELECT count(*) FROM django_migrations")
            if cursor.fetchone()[0] == 0:
                raise AssertionError("Application migrations were not applied")
            expected_logging = {
                "log_statement": "none",
                "log_min_error_statement": "panic",
                "log_min_messages": "fatal",
                "log_error_verbosity": "terse",
                "log_parameter_max_length": "0",
                "log_parameter_max_length_on_error": "0",
                "log_min_duration_statement": "-1",
                "log_min_duration_sample": "-1",
                "log_transaction_sample_rate": "0",
            }
            for setting, expected in expected_logging.items():
                cursor.execute("SELECT current_setting(%s)", (setting,))
                if cursor.fetchone()[0] != expected:
                    raise AssertionError(f"Confidential database logging policy differs: {setting}")
    limiter = redis.Redis(host="valkey", port=6379, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    if limiter.config_get("maxmemory-policy")["maxmemory-policy"] != "noeviction":
        raise AssertionError("Auth limiter must never silently evict rate-limit state")
    for path in ("/health/edge/", "/health/live/", "/health/ready/", "/workspaces/deep-link"):
        with urlopen(f"http://caddy:8080{path}", timeout=3) as response:
            if response.status != 200:
                raise AssertionError(f"Local route failed: {path}")
            if path == "/workspaces/deep-link":
                verify_shell_policy(response.read().decode(), response.headers.get("Content-Security-Policy", ""))
    try:
        response = urlopen("http://caddy:8080/api/v1/workspaces/", timeout=3)
    except HTTPError as error:
        response = error
    with response:
        if "application/json" not in response.headers.get("Content-Type", ""):
            raise AssertionError("API prefix fell through to the SPA")


if __name__ == "__main__":
    verify_configuration(json.loads((ROOT / ".local/artifacts/compose.resolved.json").read_text()))
    verify_live()
    print("Compose isolation, restricted readable secrets, runtime DB privilege, limiter, routed readiness and served CSP verified.")
