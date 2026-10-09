"""Qualify locked Python artifacts against primary PyPI metadata, not a mirror."""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "backend/uv.lock"
REPORT = ROOT / ".local/artifacts/dependency-provenance.json"


def compare_artifacts(package: dict, metadata: dict) -> int:
    """Require exact upstream filename/hash/size for every locked distribution."""
    primary = {item["filename"]: item for item in metadata["urls"]}
    artifacts = list(package.get("wheels", []))
    if package.get("sdist"):
        artifacts.append(package["sdist"])
    if not artifacts:
        raise ValueError(f"No auditable distribution for {package['name']}.")
    for artifact in artifacts:
        filename = unquote(Path(urlparse(artifact["url"]).path).name)
        upstream = primary.get(filename)
        if not upstream:
            raise ValueError(f"Distribution absent from primary PyPI: {filename}")
        expected = "sha256:" + upstream["digests"]["sha256"]
        # PEP503 mirror entries can omit size in uv.lock. The full content hash
        # remains mandatory; if the lock includes a size it must also match.
        if artifact["hash"] != expected or (
            "size" in artifact and artifact["size"] != upstream["size"]
        ):
            raise ValueError(f"Primary artifact hash/size mismatch: {filename}")
    return len(artifacts)


def qualify_package(package: dict) -> dict:
    name, version = package["name"], package["version"]
    url = f"https://pypi.org/pypi/{quote(name, safe='')}/{quote(version, safe='')}/json"
    request = Request(url, headers={"User-Agent": "PCRStudio-dependency-provenance/1"})
    error: Exception | None = None
    for _ in range(2):
        try:
            with urlopen(request, timeout=15) as response:  # nosec B310: fixed HTTPS PyPI origin
                metadata = json.load(response)
            count = compare_artifacts(package, metadata)
            return {"name": name, "version": version, "artifacts": count, "primary": url}
        except (URLError, TimeoutError) as failure:
            error = failure
    raise RuntimeError(f"Primary metadata unavailable for {name}: {type(error).__name__}")


def main() -> int:
    raw = LOCK.read_bytes()
    lock = tomllib.loads(raw.decode())
    packages = []
    for package in lock["package"]:
        source = package.get("source", {})
        if source.get("virtual") == ".":
            continue
        if not source.get("registry", "").startswith("https://"):
            raise ValueError(f"Unqualified non-registry dependency: {package['name']}")
        packages.append(package)
    if not packages:
        raise ValueError("The dependency lock contains no auditable registry packages.")
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(qualify_package, packages))
    report = {
        "verified": True,
        "lock_sha256": hashlib.sha256(raw).hexdigest(),
        "packages": sorted(results, key=lambda item: item["name"]),
        "artifact_count": sum(item["artifacts"] for item in results),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Primary PyPI qualification passed: {len(results)} packages, {report['artifact_count']} artifacts.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, KeyError, OSError) as failure:
        print(f"Dependency provenance failed: {failure}", file=sys.stderr)
        sys.exit(1)
