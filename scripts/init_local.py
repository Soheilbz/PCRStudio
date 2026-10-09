"""Create local state once. Called with the host user's identity in a pinned container."""
from __future__ import annotations

import base64
import os
import secrets
import stat
from pathlib import Path


def initialize(state: Path) -> None:
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    (state / "secrets").mkdir(mode=0o700, exist_ok=True)
    (state / "artifacts").mkdir(mode=0o700, exist_ok=True)
    for name in ("django_secret_key", "mfa_encryption_key", "db_admin_password", "db_migrator_password", "db_runtime_password", "db_test_password"):
        target = state / "secrets" / name
        if not target.exists():
            # Compose preserves host ownership and modes for these individual read-only mounts.
            # API/migrate receive only the persisted host GID as a supplemental group.
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440)
            with os.fdopen(descriptor, "w") as handle:
                value = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() if name == "mfa_encryption_key" else secrets.token_urlsafe(48)
                handle.write(value + "\n")
            target.chmod(0o440)
        elif not target.read_text().strip():
            raise RuntimeError(f"Local secret {name} is empty; refusing to replace existing configuration")
        else:
            # Tighten legacy permissions without rotating data or widening an owner's restriction.
            mode = stat.S_IMODE(target.stat().st_mode)
            if mode & ~0o440:
                target.chmod(mode & 0o440)
    config = state / "compose.env"
    if not config.exists():
        config.write_text(
            f"COMPOSE_PROJECT_NAME={os.environ['PROJECT_NAMESPACE']}\n"
            f"LOCAL_UID={os.environ['LOCAL_UID']}\nLOCAL_GID={os.environ['LOCAL_GID']}\n"
        )
        config.chmod(0o600)


if __name__ == "__main__":
    initialize(Path("/state"))
