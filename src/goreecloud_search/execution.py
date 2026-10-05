from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Iterable

from .models import ParsedQuery, SourcePlan, SourcePlanStep
from .normalization import normalize_and_deduplicate
from .providers import ProviderSearchBatch, ResultCandidate, SearchProvider


class ProviderExecutionError(RuntimeError):
    """Raised when a source plan cannot be executed safely."""


class ProviderExecutionStatus(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


class SearchAvailability(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    per_provider_timeout_seconds: float = 3.0
    max_concurrency: int = 4

    def __post_init__(self) -> None:
        if self.per_provider_timeout_seconds <= 0:
            raise ValueError("per_provider_timeout_seconds must be positive")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")


@dataclass(frozen=True, slots=True)
class ProviderAttempt:
    provider: str
    stage: str
    status: ProviderExecutionStatus
    result_count: int
    elapsed_ms: int
    warnings: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    candidates: tuple[ResultCandidate, ...]
    attempts: tuple[ProviderAttempt, ...]
    availability: SearchAvailability
    fallback_used: bool

    @property
    def degraded(self) -> bool:
        return self.availability is SearchAvailability.DEGRADED


@dataclass(frozen=True, slots=True)
class _StepResult:
    attempt: ProviderAttempt
    candidates: tuple[ResultCandidate, ...]


class SearchExecutor:
    """Execute an approved SourcePlan with bounded concurrency and failure isolation.

    The executor never selects additional providers. It executes only provider names
    already admitted by the source planner, preserving the planner's privacy boundary.
    """

    def __init__(
        self,
        providers: Iterable[SearchProvider],
        *,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self._policy = policy or ExecutionPolicy()
        provider_map: dict[str, SearchProvider] = {}
        for provider in providers:
            key = provider.descriptor.name.casefold()
            if key in provider_map:
                raise ProviderExecutionError(
                    f"duplicate execution provider name: {provider.descriptor.name!r}"
                )
            provider_map[key] = provider
        self._providers = provider_map

    async def execute(
        self,
        query: ParsedQuery,
        plan: SourcePlan,
        *,
        limit: int,
    ) -> ExecutionReport:
        if limit < 1:
            raise ValueError("limit must be positive")

        self._validate_plan(plan)
        semaphore = asyncio.Semaphore(self._policy.max_concurrency)

        primary = tuple(step for step in plan.steps if step.stage == "primary")
        fallback = tuple(step for step in plan.steps if step.stage == "fallback")
        other = tuple(step for step in plan.steps if step.stage not in {"primary", "fallback"})
        if other:
            stages = ", ".join(sorted({step.stage for step in other}))
            raise ProviderExecutionError(f"unsupported source-plan stage(s): {stages}")

        primary_results = await self._run_steps(
            query,
            primary,
            limit=limit,
            semaphore=semaphore,
        )
        candidates = [candidate for result in primary_results for candidate in result.candidates]
        attempts = [result.attempt for result in primary_results]

        fallback_used = False
        if fallback:
            if len(candidates) < limit:
                fallback_used = True
                remaining = max(limit - len(candidates), 1)
                fallback_results = await self._run_steps(
                    query,
                    fallback,
                    limit=remaining,
                    semaphore=semaphore,
                )
                candidates.extend(
                    candidate for result in fallback_results for candidate in result.candidates
                )
                attempts.extend(result.attempt for result in fallback_results)
            else:
                attempts.extend(
                    ProviderAttempt(
                        provider=step.provider,
                        stage=step.stage,
                        status=ProviderExecutionStatus.SKIPPED,
                        result_count=0,
                        elapsed_ms=0,
                        reason="primary stage satisfied requested result target",
                    )
                    for step in fallback
                )

        availability = self._availability(tuple(attempts))
        return ExecutionReport(
            candidates=tuple(candidates),
            attempts=tuple(attempts),
            availability=availability,
            fallback_used=fallback_used,
        )

    def _validate_plan(self, plan: SourcePlan) -> None:
        for step in plan.steps:
            provider = self._providers.get(step.provider.casefold())
            if provider is None:
                raise ProviderExecutionError(
                    f"source plan references unavailable provider: {step.provider!r}"
                )
            descriptor = provider.descriptor
            if descriptor.origin is not step.origin:
                raise ProviderExecutionError(
                    f"source plan origin mismatch for provider: {step.provider!r}"
                )

    async def _run_steps(
        self,
        query: ParsedQuery,
        steps: tuple[SourcePlanStep, ...],
        *,
        limit: int,
        semaphore: asyncio.Semaphore,
    ) -> tuple[_StepResult, ...]:
        if not steps:
            return ()

        tasks = [
            asyncio.create_task(
                self._run_one(query, step, limit=limit, semaphore=semaphore),
                name=f"search-provider:{step.provider}",
            )
            for step in steps
        ]
        try:
            return tuple(await asyncio.gather(*tasks))
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _run_one(
        self,
        query: ParsedQuery,
        step: SourcePlanStep,
        *,
        limit: int,
        semaphore: asyncio.Semaphore,
    ) -> _StepResult:
        provider = self._providers[step.provider.casefold()]
        started = monotonic()
        try:
            async with semaphore:
                batch = await asyncio.wait_for(
                    provider.search(query, limit=limit),
                    timeout=self._policy.per_provider_timeout_seconds,
                )
            self._validate_batch(provider, batch, limit=limit)
            elapsed_ms = max(0, round((monotonic() - started) * 1000))
            status = (
                ProviderExecutionStatus.DEGRADED
                if batch.degraded
                else ProviderExecutionStatus.SUCCESS
            )
            return _StepResult(
                attempt=ProviderAttempt(
                    provider=provider.descriptor.name,
                    stage=step.stage,
                    status=status,
                    result_count=len(batch.candidates),
                    elapsed_ms=elapsed_ms,
                    warnings=batch.warnings,
                    reason="provider reported degraded response" if batch.degraded else None,
                ),
                candidates=batch.candidates,
            )
        except TimeoutError:
            elapsed_ms = max(0, round((monotonic() - started) * 1000))
            return _StepResult(
                attempt=ProviderAttempt(
                    provider=provider.descriptor.name,
                    stage=step.stage,
                    status=ProviderExecutionStatus.TIMEOUT,
                    result_count=0,
                    elapsed_ms=elapsed_ms,
                    reason="provider execution timed out",
                ),
                candidates=(),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            elapsed_ms = max(0, round((monotonic() - started) * 1000))
            return _StepResult(
                attempt=ProviderAttempt(
                    provider=provider.descriptor.name,
                    stage=step.stage,
                    status=ProviderExecutionStatus.ERROR,
                    result_count=0,
                    elapsed_ms=elapsed_ms,
                    reason="provider execution failed",
                ),
                candidates=(),
            )

    @staticmethod
    def _validate_batch(
        provider: SearchProvider,
        batch: ProviderSearchBatch,
        *,
        limit: int,
    ) -> None:
        if not isinstance(batch, ProviderSearchBatch):
            raise ProviderExecutionError("provider returned an invalid batch type")
        if not isinstance(batch.candidates, tuple):
            raise ProviderExecutionError("provider returned an invalid candidate collection")
        # Reject rather than truncate: oversized responses must not reach
        # normalization or ranking, including when fallback requests less work.
        if len(batch.candidates) > limit:
            raise ProviderExecutionError("provider returned more candidates than requested")
        if not isinstance(batch.degraded, bool):
            raise ProviderExecutionError("provider returned an invalid degraded state")
        if not isinstance(batch.warnings, tuple) or any(
            not isinstance(warning, str) for warning in batch.warnings
        ):
            raise ProviderExecutionError("provider returned invalid warnings")

        expected = provider.descriptor.name.casefold()
        for candidate in batch.candidates:
            if not isinstance(candidate, ResultCandidate):
                raise ProviderExecutionError("provider returned an invalid candidate type")
            if any(
                not isinstance(value, str)
                for value in (
                    candidate.title,
                    candidate.url,
                    candidate.snippet,
                    candidate.provider,
                )
            ) or any(
                value is not None and not isinstance(value, str)
                for value in (
                    candidate.published_at,
                    candidate.content_type,
                    candidate.canonical_url,
                    candidate.source_id,
                    candidate.content_hash,
                    candidate.language,
                    candidate.last_crawled_at,
                    candidate.provider_contract_version,
                )
            ):
                raise ProviderExecutionError("provider returned invalid candidate text fields")
            if candidate.provider_rank is not None and (
                isinstance(candidate.provider_rank, bool)
                or not isinstance(candidate.provider_rank, int)
            ):
                raise ProviderExecutionError("provider returned an invalid candidate rank")
            if candidate.provider.casefold() != expected:
                raise ProviderExecutionError(
                    "provider returned candidate provenance for a different provider"
                )

        # Apply the shared content rules inside this provider's failure boundary.
        # The core still owns the final cross-provider deduplication and ranking.
        normalize_and_deduplicate(batch.candidates, (provider.descriptor,))

    @staticmethod
    def _availability(attempts: tuple[ProviderAttempt, ...]) -> SearchAvailability:
        executed = tuple(
            attempt for attempt in attempts
            if attempt.status is not ProviderExecutionStatus.SKIPPED
        )
        completed = tuple(
            attempt for attempt in executed
            if attempt.status in {
                ProviderExecutionStatus.SUCCESS,
                ProviderExecutionStatus.DEGRADED,
            }
        )
        if not completed:
            return SearchAvailability.UNAVAILABLE
        if any(
            attempt.status in {
                ProviderExecutionStatus.DEGRADED,
                ProviderExecutionStatus.TIMEOUT,
                ProviderExecutionStatus.ERROR,
            }
            for attempt in executed
        ):
            return SearchAvailability.DEGRADED
        return SearchAvailability.AVAILABLE
