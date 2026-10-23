# SPDX-License-Identifier: AGPL-3.0-or-later
"""GoreeCloud-owned, fail-closed provider orchestration for native fusion.

No provider SDK, credentials, network transport or web route is bundled here.
Only explicitly admitted asynchronous adapters are invoked. The caller owns
transport egress and must enforce socket deadlines and provider agreements.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from typing import Awaitable, Callable, Sequence

from .fusion import FusedResult, SourceResult, SUPPORTED_CATEGORIES, fuse_results


_SOURCE_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')
_QUERY_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_MAX_PROVIDERS = 8
_MAX_PER_PROVIDER = 40


@dataclass(frozen=True)
class ProviderRights:
    """Reviewed upstream permissions; **no** grants are presumed by default.

    Evidence is an operator-controlled reference, never an API key or token.
    These booleans document a separate human/provider licensing decision; they
    do not constitute independent verification of contractual permission.
    """

    categories: frozenset[str] = frozenset()
    allow_request: bool = False
    allow_fusion: bool = False
    allow_display: bool = False
    evidence_reference: str = ''
    rights_basis: str = 'unverified'  # unverified | synthetic_fixture | contract_reviewed

    def admits(self, category: str, *, allow_synthetic_fixtures: bool = False) -> bool:
        return (isinstance(self.categories, frozenset)
                and self.categories.issubset(SUPPORTED_CATEGORIES)
                and category in self.categories and type(self.allow_request) is bool
                and type(self.allow_fusion) is bool and type(self.allow_display) is bool
                and self.allow_request and self.allow_fusion and self.allow_display
                and isinstance(self.evidence_reference, str)
                and 0 < len(self.evidence_reference.strip()) <= 256
                and (self.rights_basis == 'contract_reviewed'
                     or (self.rights_basis == 'synthetic_fixture' and allow_synthetic_fixtures)))


# Each adapter must implement cooperative cancellation, its own bounded HTTPS
# transport timeout and applicable upstream rate/traffic/usage restrictions.
SearchAdapter = Callable[[str, str, int], Awaitable[Sequence[SourceResult]]]


@dataclass(frozen=True)
class ProviderBinding:
    source: str
    search: SearchAdapter
    rights: ProviderRights = ProviderRights()


@dataclass(frozen=True)
class ProviderOutcome:
    source: str
    status: str  # blocked | ok | empty | timeout | failed
    accepted: int = 0


@dataclass(frozen=True)
class FusionResponse:
    """Query-free, native versioned response; no provider picker required."""

    schema_version: int
    category: str
    status: str  # ok | partial | empty | unavailable
    results: tuple[FusedResult, ...]
    providers: tuple[ProviderOutcome, ...]


async def dispatch_fusion(
    query: str,
    *,
    category: str,
    providers: Sequence[ProviderBinding],
    limit: int = 20,
    per_provider: int = 30,
    timeout_seconds: float = 3.0,
    max_concurrency: int = 4,
    allow_synthetic_fixtures: bool = False,
) -> FusionResponse:
    """Fan out only admitted sources, isolate failures, and fuse results.

    No retries or hidden fallbacks. The timeout is a *cooperative* adapter
    deadline, not a way to interrupt a blocking synchronous socket; only
    nonblocking adapters that honor cancellation can be safely registered.
    Never log or include query text or raw provider exceptions in diagnostics.
    """
    if not isinstance(query, str) or not 0 < len(query.strip()) <= 512 or _QUERY_CONTROL.search(query):
        raise ValueError('Invalid bounded query')
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError('Unsupported category')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid output limit')
    if type(per_provider) is not int or not 1 <= per_provider <= _MAX_PER_PROVIDER:
        raise ValueError('Invalid per-provider limit')
    if type(max_concurrency) is not int or not 1 <= max_concurrency <= 4:
        raise ValueError('Invalid concurrency limit')
    if type(allow_synthetic_fixtures) is not bool:
        raise ValueError('Invalid test fixture switch')
    if (type(timeout_seconds) not in (float, int) or not 0.05 <= timeout_seconds <= 10):
        raise ValueError('Invalid provider deadline')
    if (not isinstance(providers, (list, tuple)) or not 1 <= len(providers) <= _MAX_PROVIDERS):
        raise ValueError('Invalid provider inventory')

    seen: set[str] = set()
    admitted: list[ProviderBinding] = []
    blocked: dict[str, ProviderOutcome] = {}
    for binding in providers:
        if (not isinstance(binding, ProviderBinding) or not isinstance(binding.source, str)
                or not _SOURCE_ID.fullmatch(binding.source)
                or binding.source in seen or not callable(binding.search)
                or not isinstance(binding.rights, ProviderRights)):
            raise ValueError('Invalid or duplicated provider binding')
        seen.add(binding.source)
        if binding.rights.admits(category, allow_synthetic_fixtures=allow_synthetic_fixtures):
            admitted.append(binding)
        else:
            blocked[binding.source] = ProviderOutcome(binding.source, 'blocked')

    semaphore = asyncio.Semaphore(max_concurrency)

    async def get_one(binding: ProviderBinding) -> tuple[ProviderOutcome, tuple[SourceResult, ...]]:
        try:
            async with semaphore:
                # Start the source deadline only after its execution slot is
                # acquired. Queued, healthy sources must not expire before
                # their async transport has ever been invoked.
                try:
                    records = await asyncio.wait_for(
                        binding.search(query, category, per_provider),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    return ProviderOutcome(binding.source, 'timeout'), ()
                if (not isinstance(records, (list, tuple))
                        or len(records) > per_provider
                        or any(not isinstance(card, SourceResult)
                               or card.source != binding.source
                               or card.category != category for card in records)):
                    raise ValueError('Invalid adapter result contract')
                # One malformed provider's rank/card must not collapse
                # otherwise valid providers after the fan-in operation. The
                # fusion helper silently filters unsafe destinations, so a
                # provider must also prove EVERY card is publishable before
                # its raw accepted count or status may be called successful.
                for card in records:
                    if not fuse_results((card,), category=category, limit=1):
                        raise ValueError('Unpublishable adapter card')
                return (ProviderOutcome(binding.source, 'ok' if records else 'empty', len(records)),
                        tuple(records))
        except asyncio.CancelledError:
            raise
        except Exception:
            # A malformed adapter and a provider outage must not leak
            # query-bearing transport exceptions through the native boundary.
            return ProviderOutcome(binding.source, 'failed'), ()

    completed = await asyncio.gather(*(get_one(binding) for binding in admitted))
    outcomes = {name: outcome for name, outcome in blocked.items()}
    cards: list[SourceResult] = []
    for outcome, source_cards in completed:
        outcomes[outcome.source] = outcome
        cards.extend(source_cards)
    # Validated fusion exceptions mean an adapter's result is malformed. As
    # admitted cards are bounded, this must be treated as a failed response,
    # not an arbitrary uncaught exception carrying provider data.
    try:
        fused = tuple(fuse_results(cards, category=category, limit=limit))
    except ValueError:
        fused = ()
        for outcome, _ in completed:
            if outcome.status == 'ok':
                outcomes[outcome.source] = ProviderOutcome(outcome.source, 'failed')

    ordered_outcomes = tuple(outcomes[binding.source] for binding in providers)
    successful = sum(outcome.status in ('ok', 'empty') for outcome in ordered_outcomes)
    failures = sum(outcome.status in ('failed', 'timeout') for outcome in ordered_outcomes)
    if not successful:
        status = 'unavailable'
    elif failures or len(admitted) != len(providers):
        status = 'partial'
    elif fused:
        status = 'ok'
    else:
        status = 'empty'
    return FusionResponse(1, category, status, fused, ordered_outcomes)
