"""Fail-closed outbound HTTP policy for the scientific worker.

Generation 1 has one automatic Internet dependency: NCBI E-utilities for
accession retrieval.  Keeping that host policy in one adapter prevents future
callers from accidentally turning the worker into a generic URL fetcher and
prevents urllib's default cross-origin redirect behaviour from escaping the
reviewed destination.
"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
from collections.abc import Iterable

DEFAULT_ALLOWED_HOSTS = ("eutils.ncbi.nlm.nih.gov",)


class EgressPolicyError(ValueError):
    """An outbound URL or redirect is outside PCRStudio's reviewed policy."""


def allowed_hosts() -> frozenset[str]:
    """Return the reviewed host allowlist, optionally narrowed by deployment.

    `PCRSTUDIO_EGRESS_ALLOWLIST` may only *remove* hosts from the compiled-in
    list.  It cannot add an arbitrary runtime destination without a source
    change/review. An empty value means the compiled-in default.
    """
    compiled = frozenset(DEFAULT_ALLOWED_HOSTS)
    raw = os.environ.get("PCRSTUDIO_EGRESS_ALLOWLIST", "").strip()
    if not raw:
        return compiled
    requested = frozenset(part.strip().lower() for part in raw.split(",") if part.strip())
    unknown = requested - compiled
    if unknown:
        raise EgressPolicyError(
            "deployment egress allowlist contains host(s) not compiled into this release: "
            + ", ".join(sorted(unknown))
        )
    return requested


def validate_https_url(url: str, *, hosts: Iterable[str] | None = None) -> str:
    """Validate one outbound URL and return its normalized hostname."""
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError as error:
        raise EgressPolicyError(f"invalid outbound URL: {error}") from error
    if parsed.scheme.lower() != "https":
        raise EgressPolicyError("outbound scientific HTTP is HTTPS-only")
    if parsed.username is not None or parsed.password is not None:
        raise EgressPolicyError("outbound scientific URLs may not contain credentials")
    host = (parsed.hostname or "").lower()
    permitted = frozenset(h.lower() for h in (hosts if hosts is not None else allowed_hosts()))
    if not host or host not in permitted:
        raise EgressPolicyError(f"outbound host `{host or '<missing>'}` is not allowlisted")
    # E-utilities is HTTPS on the default port. Refuse alternate ports because
    # they turn a hostname allowlist into an unexpected service allowlist.
    if parsed.port not in (None, 443):
        raise EgressPolicyError("outbound scientific HTTPS may use only port 443")
    return host


def validate_redirect(source_url: str, destination_url: str) -> str:
    """Validate a redirect and require it to remain on the exact source host."""
    source_host = validate_https_url(source_url)
    destination_host = validate_https_url(destination_url)
    if destination_host != source_host:
        raise EgressPolicyError(
            f"cross-host scientific redirect forbidden: {source_host} -> {destination_host}"
        )
    return destination_host


class _StrictRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow only HTTPS redirects that remain on the exact original host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_redirect(req.full_url, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def opener() -> urllib.request.OpenerDirector:
    """Build the reviewed URL opener.

    Environment proxy variables are ignored by default because they silently
    change the network trust path. Deployments that require a managed proxy
    must opt in explicitly; destination validation still remains in force.
    """
    handlers: list[urllib.request.BaseHandler] = [_StrictRedirectHandler()]
    if os.environ.get("PCRSTUDIO_ALLOW_SYSTEM_PROXY") == "1":
        handlers.insert(0, urllib.request.ProxyHandler())
    else:
        handlers.insert(0, urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)
