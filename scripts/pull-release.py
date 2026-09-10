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
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


DEFAULT_REPO = "Soheilbz/PCRStudio"
DEFAULT_DOMAIN = "pcrstudio.ir"
TAG_RE = re.compile(r"^CURRENT-[0-9]+$")
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
            raise SystemExit(f"release ref must be latest or CURRENT-N, got {release_ref!r}")
        url = f"https://api.github.com/repos/{repo}/releases/tags/{quote(release_ref, safe='')}"
    release = api_json(url)
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag) or release.get("draft") or release.get("prerelease"):
        raise SystemExit("GitHub release is not a published CURRENT-N release")
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
    for image in manifest["images"]:
        name = image["name"]
        tag = image["tag"]
        expected = image["image_id"]
        actual = json.loads(run(["docker", "image", "inspect", f"{name}:{tag}"]).stdout)[0]["Id"]
        if actual != expected:
            raise SystemExit(f"OCI image identity mismatch for {name}:{tag}: {actual} != {expected}")


def install_systemd() -> None:
    if os.geteuid() != 0:
        raise SystemExit("--install-systemd must run as root")
    source = Path(__file__).resolve()
    target = Path("/usr/local/libexec/pcrstudio-release-pull.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(0o755)
    Path("/etc/pcrstudio-release-pull.env").write_text(
        "PCRSTUDIO_RELEASE_REPO=Soheilbz/PCRStudio\n"
        "PCRSTUDIO_RELEASE_REF=latest\n"
        "PCRSTUDIO_PRODUCTION_DOMAIN=pcrstudio.ir\n",
        encoding="utf-8",
    )
    Path("/etc/pcrstudio-release-pull.service").write_text(
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
        with gzip.open(image_path, "rb") as image_stream:
            subprocess.run(["docker", "load"], check=True, stdin=image_stream, text=False)
        image_ids(manifest)
        state = Path(args.state_dir)
        (release_dir / ".local").unlink(missing_ok=True)
        (release_dir / ".env").unlink(missing_ok=True)
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
