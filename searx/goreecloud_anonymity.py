"""Fail-closed anonymous-egress route validation for private GoreeCloud Search.

A SOCKS5h *route* prevents direct fallback and requests proxy-side DNS resolution.
It is not by itself proof of a trustworthy relay or query anonymity; the runtime
must additionally confirm that the exit is Tor before sending provider requests.
"""
from urllib.parse import urlsplit


class AnonymousEgressError(ValueError):
    """Private outbound Search must never silently use direct networking."""


def require_tor_route(proxies: dict, *, using_tor_proxy: bool) -> str:
    """Validate a single local SOCKS5h route and mandatory Tor verification.

    Provider- or image-specific networks cannot substitute a direct or external
    relay. A URI with credentials, hostname DNS, or SOCKS5 (without h) is refused.
    Never include the supplied proxy URL in exception messages.
    """
    if not using_tor_proxy or not isinstance(proxies, dict) or set(proxies) != {"all://"}:
        raise AnonymousEgressError("Anonymous egress requires one verified Tor SOCKS5h route.")
    raw = proxies["all://"]
    if not isinstance(raw, str) or raw != raw.strip() or not raw:
        raise AnonymousEgressError("Anonymous egress requires a local SOCKS5h relay.")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise AnonymousEgressError("Anonymous egress proxy URL is invalid.") from None
    if (
        parsed.scheme != "socks5h"
        or parsed.hostname not in ("127.0.0.1", "::1")
        or not port
        or parsed.username is not None or parsed.password is not None
        or parsed.path or parsed.query or parsed.fragment
        or "?" in raw or "#" in raw
    ):
        raise AnonymousEgressError("Anonymous egress requires a local SOCKS5h relay.")
    return raw
