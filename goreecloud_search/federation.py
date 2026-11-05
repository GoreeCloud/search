"""First-party aggregation with concurrent opt-in provider calls and attribution."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from . import providers


@dataclass(frozen=True)
class FederatedResult:
    results: list[dict[str, str]]
    warnings: list[dict[str, str]]


def _dedupe_key(url: str) -> str:
    parts = urlsplit(url)
    netloc = (parts.hostname or "").lower()
    if parts.port not in (None, 443):
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip("/") or "/", parts.query, ""))


def search(query: str, limit: int, sources: list[str], config: providers.ProviderConfig,
           local_search, external_fetch=providers.fetch) -> FederatedResult:
    """No blanket exception swallowing: failures return bounded provider code only."""
    if not sources or any(name not in ("local", *providers.PROVIDER_IDS) for name in sources):
        raise ValueError("Invalid provider list")
    results_by_source: dict[str, list[dict[str, str]]] = {}
    warnings: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        future_map = {}
        for name in sources:
            if name == "local":
                future_map[name] = pool.submit(local_search, query, limit)
            else:
                future_map[name] = pool.submit(external_fetch, name, query, limit, config)
        for name, future in future_map.items():
            try:
                results_by_source[name] = future.result()
            except Exception:
                # Never leak provider stack traces, credentials, or query in output.
                results_by_source[name] = []
                warnings.append({"provider": name, "code": "unavailable"})
    seen: set[str] = set()
    combined: list[dict[str, str]] = []
    # Consistent source order is deterministic even though work ran in parallel.
    for name in sources:
        for item in results_by_source[name]:
            key = _dedupe_key(item["url"])
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)
            if len(combined) >= limit:
                return FederatedResult(combined, warnings)
    return FederatedResult(combined, warnings)
