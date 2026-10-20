#!/usr/bin/env python3
"""Staging-only startup gate: never launch Search before Tor works via SOCKS5H.

Search's namespace is internal-only, while its loopback relay starts after the
Search container is created. Probe ONLY the public Tor attestation endpoint
through localhost SOCKS5H; exit closed if the relay/Tor cannot be verified.
No user queries, source URLs, proxy credentials or IP addresses are logged.
"""
from __future__ import annotations

import asyncio
import os
import sys

from curl_cffi.requests import AsyncSession

TOR_CHECK_URL = "https://check.torproject.org/api/ip"
LOCAL_SOCKS = "socks5h://127.0.0.1:9050"
ATTEMPTS = 30
RETRY_SECONDS = 3
GRANIAN = "/usr/local/searxng/.venv/bin/granian"


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
    if not asyncio.run(await_verified_tor()):
        print("STAGING_STARTUP_BLOCKED: verified private Tor path unavailable", file=sys.stderr)
        return 78
    print("STAGING_TOR_ATTESTED: starting private Search worker", flush=True)
    os.execv(GRANIAN, [GRANIAN, "searx.webapp:app"])
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
