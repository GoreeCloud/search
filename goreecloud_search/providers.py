"""Opt-in, first-party external search API adapters; all network egress disabled by default.

Brave Search and a separately managed local SearXNG instance are OPTIONAL providers.
No external engine source, plugin, API token, or deployment is bundled.
"""
from __future__ import annotations

import html
import http.client
import json
import os
from pathlib import Path
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlencode

from .links import public_https_url
from .request_budget import BudgetUnavailable, reserve_request

MAX_REPLY = 256_000
MAX_RESULTS = 20
TIMEOUT_SECONDS = 4
BRAVE_HOST = "api.search.brave.com"
BRAVE_PATH = "/res/v1/web/search"
PROVIDER_IDS = ("brave", "searxng")


class ProviderUnavailable(RuntimeError):
    """Controlled failure without disclosing provider credentials or query."""


class ProviderConfigError(ValueError):
    """Reject incomplete or unsafe optional provider configuration."""


def _bounded_config_integer(raw: str, label: str, ceiling: int) -> int:
    """Parse optional provider settings without unbounded integer conversion."""
    if (not raw or len(raw) > len(str(ceiling)) or not raw.isascii()
            or not raw.isdecimal() or (len(raw) > 1 and raw[0] == "0")):
        raise ProviderConfigError(f"{label} must be a canonical bounded decimal integer")
    value = int(raw)
    if not 1 <= value <= ceiling:
        raise ProviderConfigError(f"{label} out of range")
    return value


@dataclass(frozen=True)
class ProviderConfig:
    global_enabled: bool = False
    brave_key: str = field(default="", repr=False)
    searxng_port: int | None = None
    brave_daily_cap: int = 0
    brave_budget_db: Path | None = None

    @classmethod
    def from_environment(cls) -> "ProviderConfig":
        enabled = os.getenv("GC_SEARCH_EXTERNAL_ENABLED") == "1"
        key = os.getenv("GC_SEARCH_BRAVE_API_KEY", "")
        raw_port = os.getenv("GC_SEARCH_SEARXNG_PORT", "")
        port = None
        if raw_port:
            port = _bounded_config_integer(raw_port, "SearXNG port", 65535)
        if key and (len(key) > 256 or any(ord(ch) < 33 or ord(ch) > 126 for ch in key)):
            raise ProviderConfigError("Invalid provider credential configuration")
        raw_cap = os.getenv("GC_SEARCH_BRAVE_DAILY_CAP", "")
        cap = 0
        state_path = None
        if raw_cap:
            cap = _bounded_config_integer(raw_cap, "Brave daily request cap", 10_000)
            raw_path = os.getenv("GC_SEARCH_BRAVE_BUDGET_DB", "")
            state_path = (Path(raw_path) if raw_path
                          else Path.home() / ".local/state/goreecloud/search-brave-budget.sqlite3")
            if not state_path.is_absolute():
                raise ProviderConfigError("Brave budget state path must be absolute")
        return cls(enabled, key, port, cap, state_path)

    def availability(self) -> dict[str, bool]:
        return {
            "local": True,
            "brave": bool(
                self.global_enabled and self.brave_key
                and self.brave_daily_cap > 0 and self.brave_budget_db is not None
            ),
            "searxng": bool(self.global_enabled and self.searxng_port),
        }


class RateGate:
    """Thread-safe in-process cap; not a durable billing or account quota."""

    def __init__(self, max_requests: int = 25, period: int = 3600, gap: float = 2):
        self.max_requests = max_requests
        self.period = period
        self.gap = gap
        self.history: deque[float] = deque()
        self.lock = threading.Lock()

    def reserve(self) -> None:
        now = time.monotonic()
        with self.lock:
            while self.history and now - self.history[0] >= self.period:
                self.history.popleft()
            if len(self.history) >= self.max_requests or (
                self.history and now - self.history[-1] < self.gap
            ):
                raise ProviderUnavailable("Upstream request budget exceeded")
            self.history.append(now)


BRAVE_RATE_GATE = RateGate()


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []

    def handle_data(self, data: str) -> None:
        self.fragments.append(data)


def _plain(value: object, cap: int) -> str:
    if not isinstance(value, str):
        return ""
    parser = _PlainText()
    try:
        parser.feed(value[: cap * 4])
        parser.close()
    except ValueError:
        return ""
    return html.unescape(" ".join(" ".join(parser.fragments).split()))[:cap]


def _public_https(value: object) -> str | None:
    """Share the same validated public-navigation policy as local results."""
    return public_https_url(value)


def _strict_reply_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate keys anywhere inside an optional provider reply."""
    values: dict[str, object] = {}
    for key, item in pairs:
        if key in values:
            raise ValueError("Ambiguous provider JSON")
        values[key] = item
    return values


def _reject_reply_constant(_value: str) -> None:
    raise ValueError("Nonstandard provider JSON value")


def normalize(payload: object, provider: str, limit: int) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or provider not in PROVIDER_IDS:
        raise ProviderUnavailable("Unrecognized response")
    if provider == "brave":
        section = payload.get("web")
        rows = section.get("results", []) if isinstance(section, dict) else []
    else:
        rows = payload.get("results", [])
    if not isinstance(rows, list):
        raise ProviderUnavailable("Invalid results")
    result: list[dict[str, str]] = []
    for entry in rows[:MAX_RESULTS]:
        if not isinstance(entry, dict):
            continue
        title = _plain(entry.get("title"), 200)
        snippet = _plain(entry.get("description" if provider == "brave" else "content"), 1200)
        url = _public_https(entry.get("url"))
        if not title or not url:
            continue
        result.append({
            "title": title, "description": snippet or "No description available.",
            "url": url, "source": "Brave Search" if provider == "brave" else "SearXNG",
            "provider": provider,
        })
        if len(result) >= min(MAX_RESULTS, limit):
            break
    return result


def _read_json(connection: http.client.HTTPConnection, method: str, path: str,
               body: bytes | None, headers: dict[str, str]) -> object:
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        if response.status != 200:  # HTTPConnection deliberately follows no redirects.
            raise ProviderUnavailable("Provider returned non-success status")
        mime = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime != "application/json":
            raise ProviderUnavailable("Unexpected provider response type")
        raw = response.read(MAX_REPLY + 1)
        if len(raw) > MAX_REPLY:
            raise ProviderUnavailable("Provider response exceeds maximum size")
        try:
            return json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_strict_reply_object,
                parse_constant=_reject_reply_constant,
            )
        except (UnicodeError, ValueError) as exc:
            raise ProviderUnavailable("Malformed provider response") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise ProviderUnavailable("Provider transport unavailable") from exc
    finally:
        connection.close()


def fetch(provider: str, query: str, limit: int, config: ProviderConfig) -> list[dict[str, str]]:
    """One explicit call; the HTTP handler must enforce user consent separately."""
    if (provider not in PROVIDER_IDS or not config.global_enabled
            or not config.availability().get(provider)):
        raise ProviderUnavailable("Provider not enabled")
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 160:
        raise ProviderUnavailable("Invalid query")
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ProviderUnavailable("Invalid result limit")

    if provider == "brave":
        BRAVE_RATE_GATE.reserve()
        try:
            reserve_request(config.brave_budget_db, config.brave_daily_cap)
        except BudgetUnavailable as exc:
            raise ProviderUnavailable("Brave paid-request ceiling unavailable") from exc
        conn = http.client.HTTPSConnection(BRAVE_HOST, 443, timeout=TIMEOUT_SECONDS)
        target = BRAVE_PATH + "?" + urlencode({
            "q": query, "count": limit, "safesearch": "moderate",
            "text_decorations": "false",
        })
        payload = _read_json(conn, "GET", target, None, {
            "Accept": "application/json", "X-Subscription-Token": config.brave_key,
            "User-Agent": "GoreeCloudSearch/0.1",
        })
    else:
        conn = http.client.HTTPConnection("127.0.0.1", config.searxng_port, timeout=TIMEOUT_SECONDS)
        form = urlencode({"q": query, "format": "json", "safesearch": "1"}).encode("ascii")
        payload = _read_json(conn, "POST", "/search", form, {
            "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
        })
    return normalize(payload, provider, limit)


def choose_providers(value: object, consent: object, config: ProviderConfig) -> list[str]:
    """No implicit egress, even with configured credentials."""
    if value is None:
        return ["local"]
    if not isinstance(value, list) or not value or len(value) > 3:
        raise ValueError("Invalid provider selection")
    if any(type(x) is not str or x not in ("local", *PROVIDER_IDS) for x in value):
        raise ValueError("Unknown provider")
    if len(set(value)) != len(value):
        raise ValueError("Duplicate provider")
    if any(x != "local" for x in value):
        if consent is not True:
            raise ValueError("Explicit per-query consent required")
        if any(not config.availability()[x] for x in value if x != "local"):
            raise ValueError("Provider not configured")
    return value
