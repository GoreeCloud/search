"""Conservative public-web URL policy. Enforce network egress restrictions separately.

DNS validation is a defense in depth, not DNS pinning; see docs/security.md.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

MAX_URL_LENGTH = 2048
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".invalid", ".example", ".onion")


def normalize_url(value: str) -> str:
    """Normalize a public HTTP(S) URL without making a network request."""
    if not isinstance(value, str) or len(value) > MAX_URL_LENGTH:
        raise ValueError("URL missing or too long")
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid URL") from exc
    if parts.scheme.lower() not in {"https", "http"} or not host or parts.username or parts.password:
        raise ValueError("Unsupported URL or credentials")
    if port is not None and port != (443 if parts.scheme.lower() == "https" else 80):
        raise ValueError("Only default web ports are allowed")
    if "." not in host or host.startswith("-") or any(
        host == suffix[1:] or host.endswith(suffix) for suffix in BLOCKED_SUFFIXES
    ):
        raise ValueError("Non-public hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Direct IP requests are forbidden")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
           for label in host.split(".")):
        raise ValueError("Invalid hostname")
    scheme = parts.scheme.lower()
    path = parts.path or "/"
    normalized = urlunsplit((scheme, host, path, parts.query, ""))
    if len(normalized) > MAX_URL_LENGTH:
        raise ValueError("URL too long")
    return normalized


def public_host(url: str, *, allowed_hosts: set[str], resolve: bool = True) -> str:
    """Reject unapproved hosts and private/reserved resolved destinations."""
    canonical = normalize_url(url)
    parts = urlsplit(canonical)
    host = parts.hostname or ""
    if host not in allowed_hosts:
        raise ValueError("Host not in crawl allowlist")
    if resolve:
        try:
            records = socket.getaddrinfo(host, 443 if parts.scheme == "https" else 80, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("Host DNS unavailable") from exc
        if not records or any(
            not ipaddress.ip_address(item[4][0].split("%")[0]).is_global for item in records
        ):
            raise ValueError("Destination is not a globally routable address")
    return canonical


def hostname(url: str) -> str:
    return urlsplit(normalize_url(url)).hostname or ""
