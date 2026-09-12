"""Read portable image-config digests from a compressed ``docker save`` archive."""

from __future__ import annotations

import gzip
import hashlib
import json
import tarfile
from pathlib import Path


def docker_save_config_digests(image_archive: Path) -> dict[str, str]:
    """Return image tag -> config digest without seeking in the tar stream.

    ``docker save`` bundles are gzip-compressed tar streams.  They can be large,
    so this walks the archive once and hashes only manifest-referenced config
    members as they pass rather than expanding the bundle to disk or asking
    ``tarfile`` to seek backwards. Docker versions have used both legacy
    ``<sha256>.json`` config names and content-addressed
    ``blobs/sha256/<sha256>`` names. The manifest is resolved after the walk,
    which also avoids depending on tar member ordering.
    """
    entries: list[object] | None = None
    config_names: set[str] = set()
    config_digests: dict[str, str] = {}
    with (
        image_archive.open("rb") as compressed,
        gzip.GzipFile(fileobj=compressed, mode="rb") as stream,
        tarfile.open(fileobj=stream, mode="r|") as archive,
    ):
        for member in archive:
            if not member.isfile():
                continue
            if member.name == "manifest.json":
                if entries is not None:
                    raise SystemExit(
                        "OCI image archive has duplicate manifest.json entries"
                    )
                manifest_stream = archive.extractfile(member)
                if manifest_stream is None:
                    raise SystemExit("OCI image archive manifest cannot be read")
                with manifest_stream:
                    try:
                        parsed = json.loads(manifest_stream.read())
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise SystemExit(
                            f"OCI image archive manifest is invalid: {error}"
                        ) from error
                if not isinstance(parsed, list):
                    raise SystemExit("OCI image archive manifest must be a list")
                entries = parsed
                config_names = {
                    entry["Config"]
                    for entry in parsed
                    if isinstance(entry, dict) and isinstance(entry.get("Config"), str)
                }
            else:
                member_digest = _config_member_sha256(member.name)
                if member_digest is None or (entries is not None and member.name not in config_names):
                    continue
                if member.name in config_digests:
                    raise SystemExit(
                        f"OCI image archive has duplicate config member {member.name}"
                    )
                member_stream = archive.extractfile(member)
                if member_stream is None:
                    raise SystemExit(
                        f"OCI image archive member cannot be read: {member.name}"
                    )
                digest = hashlib.sha256()
                with member_stream:
                    while chunk := member_stream.read(1024 * 1024):
                        digest.update(chunk)
                actual_digest = digest.hexdigest()
                if actual_digest != member_digest:
                    raise SystemExit(
                        f"OCI image archive content-addressed member digest mismatch: {member.name}"
                    )
                config_digests[member.name] = actual_digest

    if entries is None:
        raise SystemExit("OCI image archive has no manifest.json")

    image_digests: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(
                "OCI image archive manifest contains an invalid image entry"
            )
        config_name = entry.get("Config")
        if not isinstance(config_name, str):
            raise SystemExit("OCI image archive has no config descriptor")
        config_digest = config_digests.get(config_name)
        if config_digest is None:
            raise SystemExit(f"OCI image archive is missing config {config_name}")
        if Path(config_name).stem != config_digest:
            raise SystemExit(
                f"OCI image config filename does not match its digest: {config_name}"
            )
        tags = entry.get("RepoTags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise SystemExit(
                f"OCI image archive has invalid tags for config {config_name}"
            )
        for tag in tags:
            if tag in image_digests:
                raise SystemExit(f"OCI image archive contains duplicate image tag {tag}")
            image_digests[tag] = "sha256:" + config_digest
    return image_digests


def _config_member_sha256(member_name: str) -> str | None:
    """Return the SHA-256 encoded by a supported docker-save config path."""
    basename = member_name.rsplit("/", 1)[-1]
    if basename.endswith(".json"):
        basename = basename[:-5]
    if len(basename) != 64 or any(char not in "0123456789abcdef" for char in basename):
        return None
    return basename
