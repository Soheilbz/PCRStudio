"""Linux-native external-tool process boundary and provenance.

External executables are resolved from explicit ``PCRSTUDIO_*`` configuration
first and native POSIX ``PATH`` second. No platform-specific command shell, batch wrapper, or
platform emulation is invoked. Every request reaches tools through an argument
vector, never through a shell fragment.

Artifact hashes are part of the Generation-1 reproducibility contract. In
``strict`` toolchain mode every required local artifact must have a declared
SHA-256 and execution fails closed on any mismatch.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .process_boundary import (
    ProcessOutputLimitExceeded,
    ProcessTransportError,
    run_bounded_text,
)
from .runtime_contract import (
    ENGINE_BINDINGS,
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PARAMETER_MAP_VERSION,
    TOOLS,
    ToolSpec,
)
from .scientific_integrity import strict as scientific_strict

MAX_CAPTURE_CHARS = 2_000_000
MAX_STDOUT_BYTES = 128 * 1024 * 1024
MAX_STDERR_BYTES = 8 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 120
_TOOLCHAIN_MODES = {"compatible", "strict"}


class ToolRuntimeError(RuntimeError):
    """A configured external tool could not be executed safely."""


def require_engine_toolchain(
    engine_id: str, module_id: str = "", request: dict[str, Any] | None = None
) -> None:
    """Enforce the engine tool contract without turning OPTIONAL into required.

    ``strict`` is the reproducibility gate: every local/embedded PRIMARY and
    VALIDATOR declared for the engine must be present, version-compatible and
    reproducibly identified. ``compatible`` deliberately allows missing
    independent validators/fallbacks so the engine can still produce an honest
    computational result whose verification envelope says what did *not* run.

    OPTIONAL and REFERENCE tools are never made global prerequisites here. An
    optional feature that a user explicitly selects is responsible for checking
    its own tool at the feature boundary.
    """
    bindings = tuple(ENGINE_BINDINGS.get(engine_id, ()))
    mode = toolchain_mode()

    # In compatible mode we do not pre-empt the engine simply because an
    # independent validator is not installed. Individual adapters still fail
    # closed on an explicitly configured but wrong version/hash.
    if mode != "strict":
        return

    requested_backend = ""
    if engine_id == "tiling-scheme" and isinstance(request, dict):
        requested_backend = str(request.get("tilingBackend") or "primalscheme3").strip().lower()
    required = set()
    for binding in bindings:
        tool_id = str(binding.get("tool_id") or "")
        if tool_id not in TOOLS or binding.get("role") not in {"PRIMARY", "VALIDATOR"}:
            continue
        # PrimalScheme3 and Olivar are independent alternative PRIMARY backends.
        # Strict mode must require only the backend selected by the request;
        # compare mode intentionally requires both. Validators remain shared.
        if engine_id == "tiling-scheme" and tool_id in {"primalscheme3", "olivar"}:
            if requested_backend in {"olivar", "compare"} and tool_id == "olivar":
                required.add(tool_id)
            elif (
                requested_backend in {"primalscheme3", "compare", ""} and tool_id == "primalscheme3"
            ):
                required.add(tool_id)
            continue
        required.add(tool_id)
    missing: list[str] = []
    for tool_id in sorted(required):
        spec = TOOLS[tool_id]
        status = tool_status(tool_id)
        if spec.execution_scope in {
            "local",
            "external-managed",
            "embedded-package",
            "optional-package",
        } and not status.get("available"):
            missing.append(f"{tool_id} {spec.version}")
            continue
        if status.get("version_matches_contract") is False:
            missing.append(f"{tool_id} {spec.version} (version mismatch)")
        if (
            spec.artifact_sha256_required
            and spec.execution_scope in {"local", "external-managed"}
            and status.get("expected_artifact_sha256") is None
        ):
            missing.append(f"{tool_id} {spec.version} (artifact hash not declared)")
        if status.get("artifact_hash_matches") is False:
            missing.append(f"{tool_id} {spec.version} (artifact hash mismatch)")

    # Strict external specificity is meaningful only against an explicitly
    # versioned production/approved snapshot. The built-in smoke corpus is for
    # regression and startup checks, never for a scientific specificity claim.
    if "mfeprimer" in required:
        db = configured_database_contract("PCRSTUDIO_MFEPRIMER_DATABASES")
        if not db["paths"]:
            missing.append("PCRSTUDIO_MFEPRIMER_DATABASES")
        if not db["sha256"]:
            missing.append("PCRSTUDIO_MFEPRIMER_DATABASES_SHA256")
        if db["scope"] not in {"production", "approved-reference"}:
            missing.append("MFEprimer production/approved-reference database scope")
        if not db.get("manifest") or not db.get("manifest_contract_consistent"):
            missing.append("MFEprimer database manifest/hash contract")
        if db.get("content_hash_matches") is not True:
            missing.append("MFEprimer database content hash contract")
        if db.get("index_artifacts_match") is not True:
            missing.append("MFEprimer database index-artifact hash contract")
    if "ncbi_blast_plus" in required:
        db = configured_database_contract("PCRSTUDIO_BLAST_DATABASE")
        if not db["paths"]:
            missing.append("PCRSTUDIO_BLAST_DATABASE")
        if not db["sha256"]:
            missing.append("PCRSTUDIO_BLAST_DATABASE_SHA256")
        if db["scope"] not in {"production", "approved-reference"}:
            missing.append("BLAST production/approved-reference database scope")
        if not db.get("manifest") or not db.get("manifest_contract_consistent"):
            missing.append("BLAST database manifest/hash contract")
        if db.get("content_hash_matches") is not True:
            missing.append("BLAST source FASTA hash contract")
        if db.get("index_artifacts_match") is not True:
            missing.append("BLAST database index-artifact hash contract")

    if missing:
        scope = f" for module {module_id}" if module_id else ""
        raise ToolRuntimeError(
            "design refused: strict toolchain is incomplete"
            f"{scope}; missing or unverified: {', '.join(sorted(set(missing)))}"
        )


@dataclass(frozen=True)
class ResolvedTool:
    spec: ToolSpec
    path: Path | None
    source: str

    @property
    def available(self) -> bool:
        return self.path is not None


def _public_command_token(value: str, *, executable: bool = False) -> str:
    """Remove host filesystem layout from persisted/client-visible provenance.

    Exact tool identity is carried by configured/observed versions and SHA-256.
    Absolute or relative path-bearing command tokens add host disclosure but no
    scientific reproducibility, so keep only the final path component.
    """
    raw = str(value)
    if executable or ("://" not in raw and ("/" in raw or "\\" in raw)):
        leaf = re.split(r"[\\/]", raw.rstrip("/\\"))[-1]
        return f"<path:{leaf or 'root'}>"
    return raw


@dataclass(frozen=True)
class ToolRun:
    tool_id: str
    role: str
    operation_id: str
    configured_version: str
    observed_version: str | None
    version_matches_contract: bool | None
    executable: str
    artifact_sha256: str | None
    expected_artifact_sha256: str | None
    artifact_hash_matches: bool | None
    command: list[str]
    started_at: str
    elapsed_ms: int
    exit_status: int
    stdout_digest: str
    stderr_digest: str
    stdout: str
    stderr: str

    def record(self, *, engine_id: str, module_id: str) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_role": self.role,
            "engine_id": engine_id,
            "module_id": module_id,
            "operation_id": self.operation_id,
            "configured_version": self.configured_version,
            "observed_version": self.observed_version,
            "version_matches_contract": self.version_matches_contract,
            "executable": _public_command_token(self.executable, executable=True),
            "executable_or_package_hash": self.artifact_sha256,
            "expected_artifact_sha256": self.expected_artifact_sha256,
            "artifact_hash_matches": self.artifact_hash_matches,
            "command": [
                _public_command_token(token, executable=(index == 0))
                for index, token in enumerate(self.command)
            ],
            "started_at": self.started_at,
            "elapsed_ms": self.elapsed_ms,
            "exit_status": self.exit_status,
            "stdout_digest": self.stdout_digest,
            "stderr_digest": self.stderr_digest,
            "parameter_map_version": PARAMETER_MAP_VERSION,
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "random_seed_or_determinism": (
                "adapter deterministic; upstream behavior identified by exact version, "
                "artifact hash and database snapshot where applicable"
            ),
        }


@dataclass(frozen=True)
class ToolAdapter:
    """One typed execution adapter for a declared scientific tool operation.

    The adapter owns identity, role, engine/module provenance and timeout.  It
    does not own tool-specific argument construction; assay adapters remain
    responsible for translating scientific intent into an explicit argv.
    """

    tool_id: str
    role: str
    operation_id: str
    engine_id: str
    module_id: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def capabilities(self) -> dict[str, Any]:
        spec = TOOLS.get(self.tool_id)
        if spec is None:
            raise ToolRuntimeError(f"unknown tool contract: {self.tool_id}")
        return {
            "tool_id": self.tool_id,
            "configured_version": spec.version,
            "execution_scope": spec.execution_scope,
            "artifact_sha256_required": spec.artifact_sha256_required,
            "role": self.role,
            "operation_id": self.operation_id,
        }

    def status(self) -> dict[str, Any]:
        return tool_status(self.tool_id)

    def fingerprint(self) -> str:
        """Stable identity digest without exposing host filesystem paths."""
        status = self.status()
        parts = {
            "tool_id": self.tool_id,
            "configured_version": status.get("configured_version"),
            "observed_version": status.get("observed_version"),
            "artifact_sha256": status.get("artifact_sha256"),
            "expected_artifact_sha256": status.get("expected_artifact_sha256"),
            "operation_id": self.operation_id,
            "role": self.role,
        }
        import json

        return hashlib.sha256(
            json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def run(
        self,
        args: Iterable[str],
        *,
        stdin: str | None = None,
        cwd: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        return _run_tool_impl(
            self.tool_id,
            args,
            role=self.role,
            operation_id=self.operation_id,
            engine_id=self.engine_id,
            module_id=self.module_id,
            stdin=stdin,
            cwd=cwd,
            timeout_seconds=self.timeout_seconds,
        )


def tool_adapter(
    tool_id: str,
    *,
    role: str,
    operation_id: str,
    engine_id: str,
    module_id: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> ToolAdapter:
    """Construct an adapter only for a tool declared by the canonical registry."""
    if tool_id not in TOOLS:
        raise ToolRuntimeError(f"unknown tool contract: {tool_id}")
    return ToolAdapter(
        tool_id=tool_id,
        role=role,
        operation_id=operation_id,
        engine_id=engine_id,
        module_id=module_id,
        timeout_seconds=timeout_seconds,
    )


def toolchain_mode() -> str:
    """Resolve toolchain mode under the global scientific-integrity ceiling.

    ``PCRSTUDIO_SCIENTIFIC_POLICY=strict`` cannot be weakened by a second
    environment variable. Compatible execution exists only for explicitly
    selected development mode.
    """
    if scientific_strict():
        return "strict"
    value = os.environ.get("PCRSTUDIO_TOOLCHAIN_MODE", "strict").strip().lower()
    return value if value in _TOOLCHAIN_MODES else "strict"


def _scientific_environment_status() -> dict[str, Any]:
    """Verify the resolved scientific-Python environment against a Linux-approved freeze.

    Top-level PrimalScheme3/pydna wheels are hash-verified before installation,
    but their dependency graph is platform-resolved. Strict execution therefore
    requires the exact post-install freeze to have passed Linux qualification.
    Reprovisioning that changes any resolved dependency changes this fingerprint
    and fails closed until the new environment is approved again.
    """
    raw_path = os.environ.get("PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE", "").strip().strip('"')
    declared = _normalise_digest(os.environ.get("PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE_SHA256"))
    approved = _normalise_digest(
        os.environ.get("PCRSTUDIO_APPROVED_SCIENTIFIC_PYTHON_FREEZE_SHA256")
    )
    actual = file_sha256(Path(raw_path)) if raw_path else None
    return {
        "path": raw_path or None,
        "declared_sha256": declared,
        "actual_sha256": actual,
        "approved_sha256": approved,
        "declared_matches_actual": bool(declared and actual and declared == actual),
        "approved_matches_actual": bool(approved and actual and approved == actual),
    }


def _require_approved_scientific_environment(tool_id: str) -> None:
    if not scientific_strict() or tool_id not in {"primalscheme3", "pydna"}:
        return
    state = _scientific_environment_status()
    if not state["path"]:
        raise ToolRuntimeError(
            f"strict {tool_id} execution requires PCRSTUDIO_SCIENTIFIC_PYTHON_FREEZE"
        )
    if not state["declared_matches_actual"]:
        raise ToolRuntimeError(
            f"strict {tool_id} execution requires the scientific-Python freeze file to match its declared SHA-256"
        )
    if not state["approved_matches_actual"]:
        raise ToolRuntimeError(
            f"strict {tool_id} execution requires this exact scientific-Python freeze fingerprint to pass Linux qualification"
        )


def _scientific_database_readiness(prefix: str) -> dict[str, Any]:
    """Expose the same database evidence gate used by strict execution.

    This is intentionally a redacted status view: paths and raw manifest
    contents stay out of readiness responses.  A smoke/development corpus can
    be perfectly hashed and indexed while still being unsuitable as production
    specificity evidence, so scope is part of the readiness decision.
    """
    contract = configured_database_contract(prefix)
    production_scope = contract["scope"] in {"production", "approved-reference"}
    ready = bool(
        production_scope
        and contract.get("manifest_contract_consistent")
        and contract.get("content_hash_matches") is True
        and contract.get("index_artifacts_match") is True
    )
    return {
        "configured": bool(contract["paths"]),
        "scope": contract["scope"],
        "manifest_contract_consistent": bool(contract.get("manifest_contract_consistent")),
        "content_hash_matches": contract.get("content_hash_matches"),
        "index_artifacts_match": contract.get("index_artifacts_match"),
        "ready": ready,
    }


def _strict_execution_readiness() -> dict[str, Any]:
    """Summarise every host-owned prerequisite for a strict scientific run."""
    environment = _scientific_environment_status()
    databases = {
        "mfeprimer": _scientific_database_readiness("PCRSTUDIO_MFEPRIMER_DATABASES"),
        "blast": _scientific_database_readiness("PCRSTUDIO_BLAST_DATABASE"),
    }
    environment_ready = bool(
        environment["declared_matches_actual"] and environment["approved_matches_actual"]
    )
    ready = toolchain_mode() != "strict" or (
        environment_ready and all(item["ready"] for item in databases.values())
    )
    return {
        "ready": ready,
        "scientific_python_freeze": {
            "configured": bool(environment["path"]),
            "declared_matches_actual": environment["declared_matches_actual"],
            "approved_matches_actual": environment["approved_matches_actual"],
            "ready": environment_ready,
        },
        "specificity_databases": databases,
    }


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _normalise_digest(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip().lower()
    if token.startswith("sha256:"):
        token = token[7:]
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        return None
    return token


def file_sha256(path: str | os.PathLike[str]) -> str | None:
    """SHA-256 a local artifact without mutating it."""
    target = Path(path)
    try:
        if not target.is_file():
            return None
        h = hashlib.sha256()
        with target.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


@lru_cache(maxsize=8)
def _bundle_tree_sha256(root_value: str) -> str | None:
    """Hash a read-only extracted tool bundle including paths and modes."""
    try:
        root = Path(root_value).resolve()
        if not root.is_dir():
            return None
        h = hashlib.sha256()
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            rel = path.relative_to(root).as_posix().encode("utf-8")
            st = path.lstat()
            mode = st.st_mode & 0o7777
            if path.is_symlink():
                target = os.readlink(path)
                resolved = path.resolve()
                if resolved != root and root not in resolved.parents:
                    return None
                payload = (
                    b"L\0" + rel + b"\0" + f"{mode:o}".encode() + b"\0" + target.encode("utf-8")
                )
            elif path.is_dir():
                payload = b"D\0" + rel + b"\0" + f"{mode:o}".encode()
            elif path.is_file():
                content_hash = file_sha256(path)
                if content_hash is None:
                    return None
                payload = (
                    b"F\0" + rel + b"\0" + f"{mode:o}".encode() + b"\0" + content_hash.encode()
                )
            else:
                return None
            h.update(payload + b"\n")
        return h.hexdigest()
    except (OSError, ValueError):
        return None


def _mafft_bundle_status() -> tuple[str | None, str | None, bool | None]:
    root = os.environ.get("PCRSTUDIO_MAFFT_BUNDLE_ROOT", "").strip()
    expected = _normalise_digest(os.environ.get("PCRSTUDIO_MAFFT_BUNDLE_SHA256", ""))
    actual = _bundle_tree_sha256(root) if root else None
    return actual, expected, (actual == expected if actual and expected else None)


def resolve(tool_id: str) -> ResolvedTool:
    spec = TOOLS[tool_id]
    # Local tools may be discovered from an explicit environment override or
    # native PATH. External-managed tools are deliberately stricter: PCRStudio
    # executes only the explicitly configured, fingerprinted Linux executable.
    # Embedded/optional Python packages and reference services are handled by
    # their own provenance adapters.
    if spec.execution_scope not in {"local", "external-managed"}:
        return ResolvedTool(spec, None, spec.execution_scope)

    if spec.env_var:
        explicit = os.environ.get(spec.env_var, "").strip().strip('"')
        if explicit:
            candidate = Path(explicit).expanduser()
            if candidate.is_file():
                return ResolvedTool(spec, candidate.resolve(), f"env:{spec.env_var}")
            found = shutil.which(explicit)
            if found:
                return ResolvedTool(spec, Path(found).resolve(), f"env:{spec.env_var}")
            return ResolvedTool(spec, None, f"invalid-env:{spec.env_var}")

    if spec.execution_scope == "external-managed":
        return ResolvedTool(spec, None, f"explicit-env-required:{spec.env_var or 'unconfigured'}")

    for name in spec.executable_names:
        found = shutil.which(name)
        if found:
            return ResolvedTool(spec, Path(found).resolve(), "PATH")
    return ResolvedTool(spec, None, "not-found")


def native_command(
    tool_id: str, executable: str | os.PathLike[str], args: Iterable[str]
) -> list[str]:
    """Build a shell-free Linux command vector for one reviewed executable."""
    del tool_id  # identity is validated by the caller/tool contract.
    return [str(executable), *(str(value) for value in args)]


def _version_matches(expected: str, observed: str | None) -> bool | None:
    if not observed:
        return None
    # Exact token boundary avoids accepting 1.890 as 1.89.
    return bool(re.search(rf"(?<![0-9.]){re.escape(expected)}(?![0-9.])", observed))


def _expected_hash(spec: ToolSpec) -> tuple[str | None, bool]:
    if not spec.hash_env_var:
        return None, False
    raw = os.environ.get(spec.hash_env_var, "").strip()
    if not raw:
        return None, False
    parsed = _normalise_digest(raw)
    return parsed, parsed is None


def _artifact_state(resolved: ResolvedTool) -> dict[str, Any]:
    actual = file_sha256(resolved.path) if resolved.path else None
    expected, malformed_expected = _expected_hash(resolved.spec)
    matches = actual == expected if actual and expected else None
    return {
        "artifact_sha256": actual,
        "expected_artifact_sha256": expected,
        "expected_artifact_sha256_malformed": malformed_expected,
        "artifact_hash_matches": matches,
    }


def _distribution_identity(name: str) -> tuple[str | None, str | None, bool]:
    """Return installed version and a deterministic distribution metadata digest.

    Python wheels are not a single executable after installation. Hashing the
    installed ``RECORD`` metadata gives the run a stable package-artifact
    fingerprint while the lock file remains the installation authority.
    """
    try:
        from importlib.metadata import distribution

        dist = distribution(name)
        observed = str(dist.version)
        record = dist.read_text("RECORD") or ""
        return observed, (_digest(record) if record else None), True
    except Exception:
        return None, None, False


def _distribution_record_status(tool_id: str, spec: ToolSpec) -> dict[str, Any]:
    """Identity for Python-distribution tools without pretending they are executables."""
    if tool_id == "primer3_core":
        package_version, record_hash, package_available = _distribution_identity("primer3-py")
        try:
            from primer3.thermoanalysis import get_libprimer3_version

            observed = str(get_libprimer3_version())
            core_available = True
        except Exception:
            observed = None
            core_available = False
        warnings: list[str] = []
        if not core_available:
            warnings.append("Bundled libprimer3 version could not be inspected.")
        if not package_available:
            warnings.append(
                "The primer3-py distribution that carries libprimer3 could not be fingerprinted."
            )
        if core_available and _version_matches(spec.version, observed) is False:
            warnings.append(
                f"Observed libprimer3 version {observed!r} does not match the generation-1 pin {spec.version}."
            )
        return {
            "tool_id": tool_id,
            "configured_version": spec.version,
            "execution_scope": spec.execution_scope,
            "readiness_requirement": spec.readiness_requirement,
            "available": core_available and package_available,
            "path": None,
            "source": "bundled-with-primer3-py",
            "carrier_distribution_version": package_version,
            "artifact_sha256": record_hash,
            "artifact_identity": "sha256(primer3-py distribution RECORD metadata)"
            if record_hash
            else None,
            "expected_artifact_sha256": None,
            "expected_artifact_sha256_malformed": False,
            "artifact_hash_matches": None,
            "observed_version": observed,
            "version_matches_contract": _version_matches(spec.version, observed),
            "warnings": warnings,
        }

    distribution_names = {
        "primer3_py": "primer3-py",
        "viennarna": "ViennaRNA",
    }
    name = distribution_names.get(tool_id)
    if not name:
        return {
            "tool_id": tool_id,
            "configured_version": spec.version,
            "execution_scope": spec.execution_scope,
            "readiness_requirement": spec.readiness_requirement,
            "available": None,
            "path": None,
            "source": spec.execution_scope,
            "artifact_sha256": None,
            "expected_artifact_sha256": None,
            "expected_artifact_sha256_malformed": False,
            "artifact_hash_matches": None,
            "observed_version": None,
            "version_matches_contract": None,
            "warnings": [],
        }
    observed, record_hash, available = _distribution_identity(name)
    warnings: list[str] = []
    matches = _version_matches(spec.version, observed)
    if available and matches is False:
        warnings.append(
            f"Observed package version {observed!r} does not match the generation-1 pin {spec.version}."
        )
    if spec.execution_scope == "embedded-package" and not available:
        warnings.append(f"Required Python distribution {name} is not installed.")
    return {
        "tool_id": tool_id,
        "configured_version": spec.version,
        "execution_scope": spec.execution_scope,
        "readiness_requirement": spec.readiness_requirement,
        "available": available,
        "path": None,
        "source": f"python-distribution:{name}",
        "artifact_sha256": record_hash,
        "artifact_identity": "sha256(distribution RECORD metadata)" if record_hash else None,
        "expected_artifact_sha256": None,
        "expected_artifact_sha256_malformed": False,
        "artifact_hash_matches": None,
        "observed_version": observed,
        "version_matches_contract": matches,
        "warnings": warnings,
    }


def tool_status(tool_id: str) -> dict[str, Any]:
    spec = TOOLS[tool_id]
    if spec.execution_scope not in {"local", "external-managed"}:
        return _distribution_record_status(tool_id, spec)
    resolved = resolve(tool_id)
    observed = _observed_version(tool_id, str(resolved.path)) if resolved.path else None
    artifact = _artifact_state(resolved)
    warnings: list[str] = []
    if artifact["expected_artifact_sha256_malformed"]:
        warnings.append(f"{spec.hash_env_var} is present but is not a 64-hex SHA-256.")
    if artifact["artifact_hash_matches"] is False:
        warnings.append("The resolved executable does not match the configured artifact SHA-256.")
    if resolved.path and _version_matches(spec.version, observed) is False:
        warnings.append(
            f"Observed version {observed!r} does not match the generation-1 pin {spec.version}."
        )
    if (
        toolchain_mode() == "strict"
        and spec.execution_scope in {"local", "external-managed"}
        and spec.artifact_sha256_required
        and artifact["expected_artifact_sha256"] is None
    ):
        warnings.append(
            f"Strict mode requires {spec.hash_env_var} so the native artifact is reproducibly identified."
        )
    bundle_actual = bundle_expected = None
    bundle_matches = None
    if tool_id == "mafft":
        bundle_actual, bundle_expected, bundle_matches = _mafft_bundle_status()
        if toolchain_mode() == "strict" and bundle_expected is None:
            warnings.append(
                "Strict mode requires PCRSTUDIO_MAFFT_BUNDLE_SHA256 for the complete portable bundle."
            )
        elif bundle_matches is not True:
            warnings.append(
                "The MAFFT portable bundle tree does not match PCRSTUDIO_MAFFT_BUNDLE_SHA256."
            )
    return {
        "tool_id": tool_id,
        "configured_version": spec.version,
        "execution_scope": spec.execution_scope,
        "readiness_requirement": spec.readiness_requirement,
        "available": resolved.available,
        "path": str(resolved.path) if resolved.path else None,
        "source": resolved.source,
        **artifact,
        "observed_version": observed,
        "version_matches_contract": _version_matches(spec.version, observed),
        "bundle_sha256": bundle_actual,
        "expected_bundle_sha256": bundle_expected,
        "bundle_hash_matches": bundle_matches,
        "warnings": warnings,
    }


@lru_cache(maxsize=32)
def _observed_version(tool_id: str, executable: str) -> str | None:
    """Ask a resolved executable for its version through its reviewed adapter."""
    version_args = {
        "mfeprimer": ["version"],
        "ncbi_blast_plus": ["-version"],
        "mafft": ["--version"],
        "primerpooler": ["--version"],
        "primalscheme3": ["--version"],
        "pydna": ["-c", "import importlib.metadata as m; print(m.version('pydna'))"],
        "olivar": ["--version"],
    }.get(tool_id)
    if not version_args:
        return None
    try:
        completed = run_bounded_text(
            native_command(tool_id, executable, version_args),
            timeout=10,
            stdout_limit=64 * 1024,
            stderr_limit=64 * 1024,
            cwd=Path(executable).parent if tool_id == "mafft" else None,
        )
    except (OSError, subprocess.TimeoutExpired, ProcessOutputLimitExceeded, ProcessTransportError):
        return None
    text = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    # Some upstream wrappers may print a code
    # page banner before the actual version.  Keep the full first 300 chars so
    # contract matching sees the authoritative version token.
    return text[:300] if text else None


def _enforce_identity(
    resolved: ResolvedTool,
) -> tuple[str | None, bool | None, str | None, bool | None]:
    spec = resolved.spec
    _require_approved_scientific_environment(spec.tool_id)
    observed = _observed_version(spec.tool_id, str(resolved.path)) if resolved.path else None
    version_matches = _version_matches(spec.version, observed)
    artifact = _artifact_state(resolved)
    actual_hash = artifact["artifact_sha256"]
    expected_hash = artifact["expected_artifact_sha256"]
    hash_matches = artifact["artifact_hash_matches"]

    if artifact["expected_artifact_sha256_malformed"]:
        raise ToolRuntimeError(
            f"{spec.hash_env_var} is malformed; expected a 64-hex SHA-256 digest."
        )
    if hash_matches is False:
        raise ToolRuntimeError(
            f"{spec.tool_id} artifact hash does not match {spec.hash_env_var}; refusing to execute an unexpected binary."
        )
    if toolchain_mode() == "strict":
        if spec.tool_id == "mafft":
            bundle_actual, bundle_expected, bundle_matches = _mafft_bundle_status()
            if bundle_expected is None or bundle_actual is None or bundle_matches is not True:
                raise ToolRuntimeError(
                    "MAFFT portable bundle tree does not match PCRSTUDIO_MAFFT_BUNDLE_SHA256; refusing to execute an incomplete or modified bundle."
                )
        if version_matches is not True:
            raise ToolRuntimeError(
                f"{spec.tool_id} resolved to {observed!r}; strict generation-1 execution requires {spec.version}."
            )
        if spec.artifact_sha256_required and expected_hash is None:
            raise ToolRuntimeError(
                f"strict generation-1 execution requires {spec.hash_env_var} for {spec.tool_id}."
            )
        if spec.artifact_sha256_required and actual_hash is None:
            raise ToolRuntimeError(f"could not hash the resolved {spec.tool_id} executable.")
    return observed, version_matches, actual_hash, hash_matches


def _run_tool_impl(
    tool_id: str,
    args: Iterable[str],
    *,
    role: str,
    operation_id: str,
    engine_id: str,
    module_id: str,
    stdin: str | None = None,
    cwd: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    resolved = resolve(tool_id)
    if not resolved.path:
        env = resolved.spec.env_var or "PATH"
        raise ToolRuntimeError(
            f"{tool_id} {resolved.spec.version} is unavailable. Configure {env} with the reviewed "
            "native executable/wrapper required by its tool contract. PCRStudio never guesses an external environment."
        )

    observed_version, version_matches, artifact_sha256, hash_matches = _enforce_identity(resolved)
    expected_hash, _malformed = _expected_hash(resolved.spec)
    command = native_command(tool_id, resolved.path, args)
    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    try:
        finished = run_bounded_text(
            command,
            input_text=stdin,
            cwd=cwd,
            timeout=timeout_seconds,
            stdout_limit=MAX_STDOUT_BYTES,
            stderr_limit=MAX_STDERR_BYTES,
        )
    except ProcessOutputLimitExceeded as error:
        raise ToolRuntimeError(
            f"{tool_id} exceeded the allowed {error.stream} output ({error.limit} bytes)"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ToolRuntimeError(
            f"{tool_id} did not finish within {timeout_seconds} seconds"
        ) from error
    except ProcessTransportError as error:
        raise ToolRuntimeError(
            f"{tool_id} process transport failed during {error.phase}: {error.detail}"
        ) from error
    except OSError as error:
        raise ToolRuntimeError(f"{tool_id} could not be started: {error}") from error

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    stdout = (finished.stdout or "")[-MAX_CAPTURE_CHARS:]
    stderr = (finished.stderr or "")[-MAX_CAPTURE_CHARS:]
    run = ToolRun(
        tool_id=tool_id,
        role=role,
        operation_id=operation_id,
        configured_version=resolved.spec.version,
        observed_version=observed_version,
        version_matches_contract=version_matches,
        executable=str(resolved.path),
        artifact_sha256=artifact_sha256,
        expected_artifact_sha256=expected_hash,
        artifact_hash_matches=hash_matches,
        command=command,
        started_at=started_at,
        elapsed_ms=elapsed_ms,
        exit_status=finished.returncode,
        stdout_digest=_digest(stdout),
        stderr_digest=_digest(stderr),
        stdout=stdout,
        stderr=stderr,
    )
    record = run.record(engine_id=engine_id, module_id=module_id)
    if finished.returncode != 0:
        tail = stderr.strip().splitlines()[-1:] or stdout.strip().splitlines()[-1:]
        raise ToolRuntimeError(
            f"{tool_id} exited with {finished.returncode}: {tail[0] if tail else 'no diagnostic'}"
        )
    return finished, record


def run_tool(
    tool_id: str,
    args: Iterable[str],
    *,
    role: str,
    operation_id: str,
    engine_id: str,
    module_id: str,
    stdin: str | None = None,
    cwd: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Compatibility entry point backed by the canonical :class:`ToolAdapter`."""
    return tool_adapter(
        tool_id,
        role=role,
        operation_id=operation_id,
        engine_id=engine_id,
        module_id=module_id,
        timeout_seconds=timeout_seconds,
    ).run(args, stdin=stdin, cwd=cwd)


_DATABASE_SCOPES = {
    "smoke-regression",
    "development",
    "production",
    "approved-reference",
    "unresolved",
}


def configured_database_contract(prefix: str) -> dict[str, Any]:
    """Return a versioned host-owned specificity database contract.

    Database creation/update remains deployment work. ``scope`` is deliberately
    separate from the hash: a perfectly reproducible regression corpus is still
    not a production specificity database. ``manifest`` may point to a JSON file
    describing release/taxonomy/filtering/deduplication; its own hash is recorded
    when present.
    """
    raw = os.environ.get(prefix, "").strip()
    paths = [entry.strip().strip('"') for entry in raw.split(os.pathsep) if entry.strip()]
    digest = _normalise_digest(os.environ.get(f"{prefix}_SHA256", "").strip())
    scope = os.environ.get(f"{prefix}_SCOPE", "unresolved").strip().lower() or "unresolved"
    if scope not in _DATABASE_SCOPES:
        scope = "unresolved"
    manifest_raw = os.environ.get(f"{prefix}_MANIFEST", "").strip().strip('"')
    manifest = Path(manifest_raw).expanduser() if manifest_raw else None
    manifest_hash = file_sha256(manifest) if manifest and manifest.is_file() else None
    manifest_data: dict[str, Any] = {}
    manifest_error: str | None = None
    if manifest and manifest.is_file():
        try:
            import json

            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("database manifest root must be an object")
            manifest_data = loaded
        except Exception as error:
            manifest_error = str(error)

    manifest_scope = str(manifest_data.get("scope") or "").strip().lower() or None
    manifest_schema = str(manifest_data.get("schema_version") or "").strip() or None
    manifest_fasta_hash = _normalise_digest(str(manifest_data.get("fasta_sha256") or ""))
    manifest_database_id = str(manifest_data.get("database_id") or "").strip() or None
    manifest_sequence_release = str(manifest_data.get("sequence_release") or "").strip() or None
    manifest_filtering = str(manifest_data.get("filtering") or "").strip() or None
    manifest_deduplication = str(manifest_data.get("deduplication") or "").strip() or None
    raw_mfe_k = manifest_data.get("mfeprimer_index_k")
    manifest_mfeprimer_index_k = (
        raw_mfe_k
        if isinstance(raw_mfe_k, int) and not isinstance(raw_mfe_k, bool) and 1 <= raw_mfe_k <= 15
        else None
    )
    manifest_mfeprimer_query_k_policy = (
        str(manifest_data.get("mfeprimer_query_k_policy") or "").strip() or None
    )
    manifest_contract_consistent = bool(
        manifest_data
        and not manifest_error
        and manifest_schema == "1.1.0"
        and manifest_scope == scope
        and manifest_fasta_hash is not None
        and digest is not None
        and manifest_fasta_hash == digest
        and manifest_database_id
        and manifest_sequence_release
        and manifest_filtering
        and manifest_deduplication
    )
    # MFEprimer is configured with its indexed FASTA path whereas BLAST is
    # configured by database prefix. Recompute the reviewed FASTA identity in
    # both cases: for BLAST use the manifest's project-local ``indexed_fasta``
    # basename. This prevents a valid-looking manifest/index set from masking a
    # replaced FASTA and lets the common evidence contract distinguish verified
    # content from an unverifiable prefix.
    concrete_file: Path | None = None
    if len(paths) == 1 and Path(paths[0]).is_file():
        concrete_file = Path(paths[0])
    elif manifest is not None:
        indexed_name = str(manifest_data.get("indexed_fasta") or "").strip()
        candidate = (manifest.resolve().parent / indexed_name).resolve() if indexed_name else None
        if (
            candidate
            and candidate.parent == manifest.resolve().parent
            and candidate.name == indexed_name
            and candidate.is_file()
        ):
            concrete_file = candidate
    concrete_file_hash = file_sha256(concrete_file) if concrete_file else None
    content_hash_matches = concrete_file_hash == digest if concrete_file_hash and digest else None

    # Production manifests generated by configure-specificity-database.py
    # fingerprint every generated index artifact.  This matters especially for
    # BLAST, whose runtime handle is a database prefix rather than a concrete
    # file: a source FASTA hash alone cannot detect a stale or partially copied
    # index.  Relative names are resolved only inside the manifest directory.
    index_artifacts = manifest_data.get("index_artifacts")
    index_artifact_status: list[dict[str, Any]] = []
    index_artifacts_match: bool | None = None
    if isinstance(index_artifacts, list) and manifest is not None:
        index_artifacts_match = bool(index_artifacts)
        manifest_dir = manifest.resolve().parent
        for entry in index_artifacts:
            if not isinstance(entry, dict):
                index_artifact_status.append({"name": None, "status": "malformed"})
                index_artifacts_match = False
                continue
            name = str(entry.get("name") or "").strip()
            expected = _normalise_digest(str(entry.get("sha256") or ""))
            candidate = (manifest_dir / name).resolve() if name else None
            safe = bool(candidate and candidate.parent == manifest_dir and candidate.name == name)
            actual = file_sha256(candidate) if safe and candidate and candidate.is_file() else None
            matches = bool(expected and actual and expected == actual)
            index_artifact_status.append(
                {
                    "name": name or None,
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "status": "verified" if matches else "missing-or-mismatched",
                }
            )
            if not matches:
                index_artifacts_match = False

    return {
        "paths": paths,
        "sha256": digest,
        "scope": scope,
        "claim_capability": (
            "production-specificity-evidence"
            if scope in {"production", "approved-reference"}
            else "smoke-or-development-evidence-only"
        ),
        "manifest": str(manifest.resolve()) if manifest and manifest.is_file() else None,
        "manifest_sha256": manifest_hash,
        "manifest_error": manifest_error,
        "manifest_contract_consistent": manifest_contract_consistent,
        "manifest_schema_version": manifest_schema,
        "database_id": manifest_data.get("database_id"),
        "sequence_release": manifest_data.get("sequence_release"),
        "taxonomy_release": manifest_data.get("taxonomy_release"),
        "filtering": manifest_data.get("filtering"),
        "deduplication": manifest_data.get("deduplication"),
        "mfeprimer_index_k": manifest_mfeprimer_index_k,
        "mfeprimer_query_k_policy": manifest_mfeprimer_query_k_policy,
        "manifest_fasta_sha256": manifest_fasta_hash,
        "concrete_file_sha256": concrete_file_hash,
        "content_hash_matches": content_hash_matches,
        "index_artifacts_declared": len(index_artifact_status),
        "index_artifacts": index_artifact_status,
        "index_artifacts_match": index_artifacts_match,
    }


def configured_database(prefix: str) -> tuple[list[str], str | None]:
    """Backwards-compatible paths/hash view of :func:`configured_database_contract`."""
    contract = configured_database_contract(prefix)
    return list(contract["paths"]), contract["sha256"]


def toolchain_snapshot() -> dict[str, Any]:
    """Deployment preflight state for local/optional/reference tool identities."""
    return {
        "mode": toolchain_mode(),
        "tools": {tool_id: tool_status(tool_id) for tool_id in TOOLS},
        "strict_execution": _strict_execution_readiness(),
    }
