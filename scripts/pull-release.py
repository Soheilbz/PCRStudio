#!/usr/bin/env python3
"""Pull and deploy an immutable PCRStudio release over HTTPS.

This is the fallback production transport for hosts that cannot accept
connections from GitHub-hosted runners.  It deliberately downloads only
assets from the PCRStudio GitHub release, verifies the tag commit and every
archive checksum, verifies loaded OCI image IDs, and then delegates startup to
the normal fail-closed bootstrap.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


DEFAULT_REPO = "Soheilbz/PCRStudio"
DEFAULT_DOMAIN = "pcrstudio.ir"
TAG_RE = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ASSET_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}


def api_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "PCRStudio-release-puller"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise SystemExit(f"GitHub release API request failed: {url}: {error}") from error


def download(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ASSET_HOSTS:
        raise SystemExit(f"refusing download from untrusted asset host: {url}")
    request = Request(url, headers={"User-Agent": "PCRStudio-release-puller"})
    try:
        with urlopen(request, timeout=60) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError) as error:
        raise SystemExit(f"release asset download failed: {url}: {error}") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, stdin=None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def release_metadata(repo: str, release_ref: str) -> dict:
    if release_ref == "latest":
        url = f"https://api.github.com/repos/{repo}/releases/latest"
    else:
        if not TAG_RE.fullmatch(release_ref):
            raise SystemExit(f"release ref must be latest or vMAJOR.MINOR.PATCH, got {release_ref!r}")
        url = f"https://api.github.com/repos/{repo}/releases/tags/{quote(release_ref, safe='')}"
    release = api_json(url)
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag) or release.get("draft") or release.get("prerelease"):
        raise SystemExit("GitHub release is not a published stable SemVer release")
    return release


def tag_commit(repo: str, tag: str) -> str:
    ref = api_json(f"https://api.github.com/repos/{repo}/git/ref/tags/{quote(tag, safe='')}")
    obj = ref.get("object") or {}
    if obj.get("type") == "commit":
        commit = obj.get("sha")
    elif obj.get("type") == "tag":
        commit = (api_json(f"https://api.github.com/repos/{repo}/git/tags/{obj.get('sha')}").get("object") or {}).get("sha")
    else:
        commit = None
    if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
        raise SystemExit(f"could not resolve immutable commit for {tag}")
    return commit


def asset_map(release: dict) -> dict[str, dict]:
    assets = {}
    for asset in release.get("assets", []):
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if isinstance(name, str) and isinstance(url, str):
            assets[name] = {"url": url, "size": asset.get("size")}
    return assets


def safe_extract(source: Path, destination: Path) -> None:
    with tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        names: set[str] = set()
        for member in members:
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise SystemExit(f"refusing non-regular source archive member: {member.name}")
            if member.name in names:
                raise SystemExit(f"refusing duplicate source archive member: {member.name}")
            names.add(member.name)
            target = (destination / member.name).resolve()
            if target != destination.resolve() and destination.resolve() not in target.parents:
                raise SystemExit(f"refusing path-traversal member in source archive: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source_stream = archive.extractfile(member)
            if source_stream is None:
                raise SystemExit(f"could not read source archive member: {member.name}")
            with source_stream, target.open("wb") as output:
                shutil.copyfileobj(source_stream, output)
            target.chmod(member.mode & 0o777)
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise SystemExit("source archive must contain exactly one top-level directory")
    root = roots[0]
    for child in root.iterdir():
        shutil.move(str(child), destination / child.name)
    root.rmdir()


def image_ids(manifest: dict) -> None:
    """Verify portable OCI config digests, not engine-local image IDs.

    Docker's inspect ``Id`` can be a storage-engine chain ID after an
    export/import boundary (notably with the containerd image store).  The
    config digest in the OCI-compatible ``docker save`` archive is portable
    and remains bound to the exact image configuration in the release
    manifest.
    """
    expected = {f"{image['name']}:{image['tag']}": image["image_id"] for image in manifest["images"]}
    with tempfile.TemporaryFile() as saved:
        subprocess.run(["docker", "save", *expected], check=True, stdout=saved)
        saved.seek(0)
        with tarfile.open(fileobj=saved, mode="r:") as archive:
            entries = json.load(archive.extractfile("manifest.json"))
            actual: dict[str, str] = {}
            for entry in entries:
                config_name = entry.get("Config")
                if not isinstance(config_name, str):
                    raise SystemExit("OCI image archive has no config descriptor")
                config_stream = archive.extractfile(config_name)
                if config_stream is None:
                    raise SystemExit(f"OCI image archive is missing config {config_name}")
                with config_stream:
                    config_digest = "sha256:" + hashlib.sha256(config_stream.read()).hexdigest()
                if Path(config_name).stem != config_digest.removeprefix("sha256:"):
                    raise SystemExit(f"OCI image config filename does not match its digest: {config_name}")
                for ref in entry.get("RepoTags", []):
                    actual[ref] = config_digest
    for ref, expected_digest in expected.items():
        actual_digest = actual.get(ref)
        if actual_digest != expected_digest:
            raise SystemExit(f"OCI image identity mismatch for {ref}: {actual_digest} != {expected_digest}")


def validate_source_version(release_dir: Path, tag: str) -> None:
    identity_path = release_dir / "release" / "release.toml"
    try:
        identity = tomllib.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SystemExit(f"release source identity is unreadable: {error}") from error
    if identity.get("versioning_scheme") != "semver-2.0.0" or identity.get("public_tag") != tag:
        raise SystemExit("release source public version does not match the GitHub release tag")


def remove_empty_path(path: Path) -> None:
    """Remove only an empty generated mount point before creating a symlink."""
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.is_dir():
        return
    descendants = sorted(path.rglob("*"), key=lambda item: len(item.parts), reverse=True)
    if any(item.is_file() or item.is_symlink() for item in descendants):
        raise SystemExit(f"refusing to replace non-empty release state path: {path}")
    for item in descendants:
        item.rmdir()
    path.rmdir()


def install_systemd() -> None:
    if os.geteuid() != 0:
        raise SystemExit("--install-systemd must run as root")
    # ReadWritePaths is applied while systemd creates the mount namespace,
    # before ExecStart/ExecStartPre can run.  Create the allow-listed root
    # during installation so a fresh host can start the timer successfully.
    Path("/srv/pcrstudio").mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve()
    target = Path("/usr/local/libexec/pcrstudio-release-pull.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source != target:
        shutil.copy2(source, target)
    target.chmod(0o755)
    Path("/etc/pcrstudio-release-pull.env").write_text(
        "PCRSTUDIO_RELEASE_REPO=Soheilbz/PCRStudio\n"
        "PCRSTUDIO_RELEASE_REF=latest\n"
        "PCRSTUDIO_PRODUCTION_DOMAIN=pcrstudio.ir\n",
        encoding="utf-8",
    )
    Path("/etc/systemd/system/pcrstudio-release-pull.service").write_text(
        """[Unit]
Description=Pull and deploy the latest verified PCRStudio release
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
EnvironmentFile=-/etc/pcrstudio-release-pull.env
ExecStart=/usr/local/libexec/pcrstudio-release-pull.py
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ReadWritePaths=/srv/pcrstudio
""",
        encoding="utf-8",
    )
    Path("/etc/systemd/system/pcrstudio-release-pull.timer").write_text(
        """[Unit]
Description=Check for verified PCRStudio releases

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
RandomizedDelaySec=90s
Persistent=true

[Install]
WantedBy=timers.target
""",
        encoding="utf-8",
    )
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "pcrstudio-release-pull.timer"])
    print("installed pcrstudio-release-pull.timer")


def deploy(args: argparse.Namespace) -> None:
    repo = args.repo
    release = release_metadata(repo, args.release_ref)
    tag = release["tag_name"]
    assets = asset_map(release)
    manifest_names = sorted(name for name in assets if name.startswith("pcrstudio-deploy-manifest-") and name.endswith(".json"))
    if len(manifest_names) != 1:
        raise SystemExit("release must contain exactly one deployment manifest asset")
    staging_root = Path(args.state_dir) / ".local" / "release-pull"
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="current-", dir=staging_root) as temp_name:
        staging = Path(temp_name)
        manifest_path = staging / manifest_names[0]
        download(assets[manifest_names[0]]["url"], manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_sha = manifest.get("source_sha")
        if not isinstance(source_sha, str) or not SHA_RE.fullmatch(source_sha):
            raise SystemExit("deployment manifest has invalid source_sha")
        if manifest.get("release_ref") != tag or tag_commit(repo, tag) != source_sha:
            raise SystemExit("release tag does not match deployment manifest commit")
        for key in ("source_archive", "image_archive", "images"):
            if key not in manifest:
                raise SystemExit(f"deployment manifest missing {key}")
        source_name = manifest["source_archive"]["name"]
        image_name = manifest["image_archive"]["name"]
        if source_name not in assets or image_name not in assets:
            raise SystemExit("deployment manifest refers to an asset absent from the release")
        source_path = staging / source_name
        image_path = staging / image_name
        download(assets[source_name]["url"], source_path)
        download(assets[image_name]["url"], image_path)
        for key, path in (("source_archive", source_path), ("image_archive", image_path)):
            expected = manifest[key].get("sha256")
            if expected != sha256(path):
                raise SystemExit(f"{key} SHA-256 mismatch")
        release_dir = Path(args.release_root) / source_sha
        current_pointer = Path(args.state_dir) / "current-release"
        if release_dir.exists() and current_pointer.is_file() and current_pointer.read_text(encoding="utf-8").strip() == source_sha:
            print(f"release {tag} already active")
            return
        release_dir.parent.mkdir(parents=True, exist_ok=True)
        if not release_dir.exists():
            source_stage = staging / "source"
            source_stage.mkdir()
            safe_extract(source_path, source_stage)
            shutil.move(str(source_stage), str(release_dir))
        elif not release_dir.is_dir():
            raise SystemExit(f"release path exists but is not a directory: {release_dir}")
        validate_source_version(release_dir, tag)
        with gzip.open(image_path, "rb") as image_stream:
            subprocess.run(["docker", "load"], check=True, stdin=image_stream, text=False)
        image_ids(manifest)
        state = Path(args.state_dir)
        remove_empty_path(release_dir / ".local")
        remove_empty_path(release_dir / ".env")
        (release_dir / ".local").symlink_to(state / ".local")
        (release_dir / ".env").symlink_to(state / ".env")
        run(
            [
                str(release_dir / "bootstrap.sh"),
                "--domain",
                args.domain,
                "--control-plane-only",
                "--prebuilt-images",
                "--offline-pinned-images",
                "--image-tag",
                source_sha,
            ]
        )
        (state / "current-release.tmp").write_text(source_sha + "\n", encoding="utf-8")
        os.replace(state / "current-release.tmp", state / "current-release")
        print(f"deployed {tag} ({source_sha})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("PCRSTUDIO_RELEASE_REPO", DEFAULT_REPO))
    parser.add_argument("--release-ref", default=os.environ.get("PCRSTUDIO_RELEASE_REF", "latest"))
    parser.add_argument("--domain", default=os.environ.get("PCRSTUDIO_PRODUCTION_DOMAIN", DEFAULT_DOMAIN))
    parser.add_argument("--state-dir", default="/srv/pcrstudio/state")
    parser.add_argument("--release-root", default="/srv/pcrstudio/releases")
    parser.add_argument("--install-systemd", action="store_true")
    args = parser.parse_args()
    if args.install_systemd:
        install_systemd()
    else:
        deploy(args)


if __name__ == "__main__":
    main()
