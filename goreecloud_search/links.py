"""Shared public HTTPS result-link policy for local and optional remote sources.

This validates navigation links only. Search never downloads result URLs.
No DNS lookup, network access, or system configuration changes are performed.
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

SPECIAL_SUFFIXES = (
    ".localhost", ".local", ".lan", ".internal", ".test", ".invalid",
    ".example", ".home.arpa",
)
SPECIAL_HOSTS = {"localhost", "localhost.localdomain"}
HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\Z")
NUMERIC_LABEL = re.compile(r"(?:[0-9]+|0x[0-9a-f]+)\Z")


def public_https_url(value: object) -> str | None:
    """Return the unchanged public HTTPS link, or None if unsafe or ambiguous.

    Numeric browser shorthand hosts, special-use names, and local addresses
    are refused even if urllib.parse and a browser interpret them differently.
    """
    if (not isinstance(value, str) or not 1 <= len(value) <= 2048
            or "\\" in value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        return None
    try:
        parts = urlsplit(value)
        hostname, port = parts.hostname, parts.port
    except ValueError:
        return None
    if (parts.scheme != "https" or not hostname or parts.username is not None
            or parts.password is not None or port not in (None, 443)):
        return None
    host = hostname.casefold().rstrip(".")
    # IPv6 literals are already parsed as addresses by urlsplit. Avoid
    # applying DNS IDNA conversions to colon-bearing address syntax.
    if ":" in host or "%" in host:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return None
        return value if address.is_global else None
    try:
        ascii_host = host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return None
    # Evaluate special-use names AFTER IDNA normalization. Otherwise
    # compatibility Unicode labels such as ｌｏｃａｌ and １２７.０.０.１
    # can bypass raw-host checks yet normalize to private browser targets.
    if (ascii_host in SPECIAL_HOSTS
            or any(ascii_host.endswith(suffix) for suffix in SPECIAL_SUFFIXES)):
        return None
    try:
        address = ipaddress.ip_address(ascii_host)
    except ValueError:
        address = None
    if address is not None:
        return value if address.is_global else None
    labels = ascii_host.split(".")
    if (len(ascii_host) > 253 or len(labels) < 2
            or any(len(label) > 63 or not HOST_LABEL.fullmatch(label)
                   for label in labels)):
        return None
    # WHATWG URL parsers can reinterpret all-numeric, hex or abbreviated
    # IPv4 forms as private IPs. Numeric TLDs are not valid public DNS TLDs.
    if NUMERIC_LABEL.fullmatch(labels[-1]) or all(
        NUMERIC_LABEL.fullmatch(label) for label in labels
    ):
        return None
    return value
