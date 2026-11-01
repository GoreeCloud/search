#!/usr/bin/env python3
"""Staging-only startup gate: never launch Search before Tor works via SOCKS5H.

Search's namespace must have only its designated internal bridge route.
Read /proc route tables before making *any* outbound call; reject direct or
unexpected interfaces and routes. Its loopback relay starts after Search
container creation. Then probe ONLY the fixed Tor Project attestation endpoint
through localhost SOCKS5H; fail closed unless both checks pass.
No user queries, source URLs, proxy credentials or IP addresses are logged.
"""
from __future__ import annotations

import asyncio
import os
import sys
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

from curl_cffi.requests import AsyncSession

TOR_CHECK_URL = "https://check.torproject.org/api/ip"
LOCAL_SOCKS = "socks5h://127.0.0.1:9050"
ATTEMPTS = 30
RETRY_SECONDS = 3
GRANIAN = "/usr/local/searxng/.venv/bin/granian"
# The same sole on-link subnet as the pinned isolated-staging Compose manifest.
SEARCH_STAGING_SUBNET = IPv4Network("172.29.247.0/28")


def _parse_ipv4_route_table(table: str) -> bool:
    """Fail closed unless only Search's fixed internal on-link route exists."""
    rows = table.splitlines()
    if len(rows) < 2 or not rows[0].startswith("Iface"):
        return False
    permitted_route = False
    for row in rows[1:]:
        fields = row.split()
        if len(fields) < 8:
            return False
        interface, destination, gateway, flags = fields[:4]
        mask = fields[7]
        try:
            # /proc/net/route encodes IPv4 words in host-little-endian order.
            dest = IPv4Address(int.from_bytes(bytes.fromhex(destination), "little"))
            next_hop = IPv4Address(int.from_bytes(bytes.fromhex(gateway), "little"))
            netmask = IPv4Address(int.from_bytes(bytes.fromhex(mask), "little"))
            network = IPv4Network((dest, str(netmask)), strict=False)
            enabled = bool(int(flags, 16) & 1)
        except (ValueError, OverflowError):
            return False
        if not enabled:
            continue
        if interface == "lo":
            continue
        if (interface != "eth0" or network != SEARCH_STAGING_SUBNET
                or next_hop != IPv4Address("0.0.0.0") or permitted_route):
            return False
        permitted_route = True
    return permitted_route


def _parse_ipv6_route_table(table: str) -> bool:
    """IPv6 is disabled on staging's only network: reject non-loopback routes."""
    for row in table.splitlines():
        fields = row.split()
        if len(fields) < 10 or fields[-1] != "lo":
            return False
    return True


def staging_namespace_confined() -> bool:
    """Check routing without emitting network traffic or relying on Tor itself.

    This is a guardrail, not a full proof against firewall or runtime changes.
    The network namespace must have only the staging Docker internal subnet.
    """
    try:
        return (_parse_ipv4_route_table(Path("/proc/net/route").read_text(encoding="ascii"))
                and _parse_ipv6_route_table(
                    Path("/proc/net/ipv6_route").read_text(encoding="ascii")))
    except (OSError, UnicodeError):
        return False


async def tor_is_ready() -> bool:
    try:
        async with AsyncSession(proxy=LOCAL_SOCKS) as client:
            response = await client.get(TOR_CHECK_URL, timeout=7, allow_redirects=False)
            return response.status_code == 200 and response.json().get("IsTor") is True
    except Exception:  # All malformed, network and timeout errors fail closed.
        return False


async def await_verified_tor() -> bool:
    for attempt in range(ATTEMPTS):
        if await tor_is_ready():
            return True
        if attempt != ATTEMPTS - 1:
            await asyncio.sleep(RETRY_SECONDS)
    return False


def main() -> int:
    if not staging_namespace_confined():
        print("STAGING_STARTUP_BLOCKED: unverified Search network isolation", file=sys.stderr)
        return 78
    if not asyncio.run(await_verified_tor()):
        print("STAGING_STARTUP_BLOCKED: verified private Tor path unavailable", file=sys.stderr)
        return 78
    print("STAGING_TOR_ATTESTED: starting private Search worker", flush=True)
    os.execv(GRANIAN, [GRANIAN, "searx.webapp:app"])
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
