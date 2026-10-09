# ADR 0003 — Locked dependency artifact provenance

Status: accepted engineering implementation decision. Date: 2026-10-06.

The official PyPI index and version metadata are reachable on the development network, but the files.pythonhosted.org CDN fails DNS/TLS requests even from host-network containers with directly resolved IPv4 addresses. Identical retries do not solve it. The HTTPS Aliyun PyPI artifact mirror was tested in the isolated Python3.13 container and successfully ran the fourteen executor-contract tests.

Use a named standard uv package index and frozen uv.lock so index configuration and lock checks agree. Keep TLS verification enabled and all dependency version/security bounds. The mirror supplies bytes, not authority: `scripts/check_dependency_provenance.py` compares every locked wheel/sdist filename and SHA256 with the exact upstream release's official `https://pypi.org/pypi/{name}/{version}/json` metadata, plus size when the lock supplies it. Failure or missing primary evidence fails the gate. UV separately verifies downloaded artifact hashes. Normal vulnerability checks still apply.

Do not rewrite uv cache internals, disable scanners or insert fixed CDN IPs into the application. Container toolchains, image digests and lockfiles preserve isolation. This choice may be replaced with the primary artifact endpoint when its network route works, accompanied by an explicit lock update and the same primary qualification.
