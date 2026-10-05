import asyncio
import unittest
from dataclasses import replace

from goreecloud_search import (
    ExecutionPolicy,
    ProviderDescriptor,
    ProviderExecutionStatus,
    ProviderOrigin,
    QueryDisclosureBudget,
    ProviderSearchBatch,
    ResultCandidate,
    SearchAvailability,
    SearchCategory,
    SearchCore,
    SearchExecutor,
    SourceMode,
    parse_query,
    plan_sources,
)


class FakeProvider:
    def __init__(
        self,
        name: str,
        origin: ProviderOrigin,
        *,
        candidates: tuple[ResultCandidate, ...] = (),
        delay: float = 0.0,
        error: Exception | None = None,
        degraded: bool = False,
        warnings: tuple[str, ...] = (),
        tracker: dict[str, int] | None = None,
    ) -> None:
        self._descriptor = ProviderDescriptor(
            name=name,
            origin=origin,
            categories=frozenset({SearchCategory.GENERAL}),
            priority=10 if origin is not ProviderOrigin.EXTERNAL else 100,
        )
        self._candidates = candidates
        self._delay = delay
        self._error = error
        self._degraded = degraded
        self._warnings = warnings
        self._tracker = tracker
        self.calls = 0
        self.cancelled = False

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    async def search(self, query, *, limit: int) -> ProviderSearchBatch:
        self.calls += 1
        if self._tracker is not None:
            self._tracker["active"] = self._tracker.get("active", 0) + 1
            self._tracker["max"] = max(self._tracker.get("max", 0), self._tracker["active"])
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            if self._error is not None:
                raise self._error
            return ProviderSearchBatch(candidates=self._candidates[:limit], degraded=self._degraded, warnings=self._warnings)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        finally:
            if self._tracker is not None:
                self._tracker["active"] -= 1


class BatchProvider(FakeProvider):
    """Return supplied batches unchanged to exercise a broken provider boundary."""

    def __init__(
        self,
        name: str,
        origin: ProviderOrigin,
        *,
        batches: tuple[object, ...],
    ) -> None:
        super().__init__(name, origin)
        self._batches = batches
        self.requested_limits: list[int] = []

    async def search(self, query, *, limit: int) -> object:
        self.calls += 1
        self.requested_limits.append(limit)
        return self._batches[min(self.calls - 1, len(self._batches) - 1)]


def candidate(provider: str, slug: str, title: str | None = None) -> ResultCandidate:
    return ResultCandidate(title=title or slug.title(), url=f"https://example.com/{slug}", snippet=f"result for {slug}", provider=provider)


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_index_first_skips_fallback_when_primary_fills_target(self) -> None:
        native = FakeProvider("index", ProviderOrigin.GOREECLOUD_INDEX, candidates=(candidate("index", "one"), candidate("index", "two")))
        external = FakeProvider("external", ProviderOrigin.EXTERNAL, candidates=(candidate("external", "three"),))
        core = SearchCore(provider_adapters=(native, external))
        response = await core.search("result", mode=SourceMode.INDEX_FIRST, limit=2)
        self.assertEqual(external.calls, 0)
        self.assertFalse(response.execution.fallback_used)
        self.assertEqual(response.execution.availability, SearchAvailability.AVAILABLE)
        self.assertEqual({a.provider: a.status for a in response.execution.attempts}["external"], ProviderExecutionStatus.SKIPPED)
        self.assertEqual(len(response.results), 2)

    async def test_index_first_uses_fallback_to_fill_short_primary(self) -> None:
        native = FakeProvider("index", ProviderOrigin.GOREECLOUD_INDEX, candidates=(candidate("index", "one"),))
        external = FakeProvider("external", ProviderOrigin.EXTERNAL, candidates=(candidate("external", "two"),))
        core = SearchCore(provider_adapters=(native, external))
        response = await core.search("result", mode=SourceMode.INDEX_FIRST, limit=2)
        self.assertTrue(response.execution.fallback_used)
        self.assertEqual(external.calls, 1)
        self.assertEqual(response.execution.availability, SearchAvailability.AVAILABLE)
        self.assertEqual(len(response.results), 2)

    async def test_zero_disclosure_budget_prevents_external_fallback_execution(self) -> None:
        native = FakeProvider("index", ProviderOrigin.GOREECLOUD_INDEX, candidates=(candidate("index", "one"),))
        external = FakeProvider("external", ProviderOrigin.EXTERNAL, candidates=(candidate("external", "two"),))
        core = SearchCore(provider_adapters=(native, external))
        response = await core.search(
            "result", mode=SourceMode.INDEX_FIRST, limit=2,
            disclosure_budget=QueryDisclosureBudget(max_third_party_providers=0),
        )
        self.assertEqual(external.calls, 0)
        self.assertFalse(response.execution.fallback_used)
        self.assertEqual(response.plan.third_party_provider_count, 0)
        self.assertEqual(response.plan.third_party_providers_omitted, 1)
        self.assertEqual(len(response.results), 1)

    async def test_timeout_isolated_as_degraded_partial_result(self) -> None:
        fast = FakeProvider("fast", ProviderOrigin.GOREECLOUD_SERVICE, candidates=(candidate("fast", "fast"),))
        slow = FakeProvider("slow", ProviderOrigin.EXTERNAL, delay=0.2, candidates=(candidate("slow", "slow"),))
        core = SearchCore(provider_adapters=(fast, slow), execution_policy=ExecutionPolicy(per_provider_timeout_seconds=0.02, max_concurrency=2))
        response = await core.search("result", mode=SourceMode.FEDERATED, limit=10)
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        statuses = {a.provider: a.status for a in response.execution.attempts}
        self.assertEqual(statuses["fast"], ProviderExecutionStatus.SUCCESS)
        self.assertEqual(statuses["slow"], ProviderExecutionStatus.TIMEOUT)
        self.assertEqual(len(response.results), 1)

    async def test_provider_reported_degraded_state_is_preserved(self) -> None:
        provider = FakeProvider("index", ProviderOrigin.GOREECLOUD_INDEX, candidates=(candidate("index", "one"),), degraded=True, warnings=("partial shard availability",))
        core = SearchCore(provider_adapters=(provider,))
        response = await core.search("result", limit=10)
        attempt = response.execution.attempts[0]
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        self.assertEqual(attempt.status, ProviderExecutionStatus.DEGRADED)
        self.assertEqual(attempt.warnings, ("partial shard availability",))

    async def test_all_provider_errors_report_unavailable_without_raising(self) -> None:
        first = FakeProvider("one", ProviderOrigin.GOREECLOUD_SERVICE, error=RuntimeError("x"))
        second = FakeProvider("two", ProviderOrigin.EXTERNAL, error=RuntimeError("y"))
        core = SearchCore(provider_adapters=(first, second))
        response = await core.search("result", mode=SourceMode.FEDERATED, limit=10)
        self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
        self.assertEqual(response.results, ())
        self.assertTrue(all(a.status is ProviderExecutionStatus.ERROR for a in response.execution.attempts))

    async def test_goreecloud_only_never_executes_registered_external_provider(self) -> None:
        native = FakeProvider("native", ProviderOrigin.GOREECLOUD_SERVICE, candidates=(candidate("native", "one"),))
        external = FakeProvider("external", ProviderOrigin.EXTERNAL, candidates=(candidate("external", "two"),))
        core = SearchCore(provider_adapters=(native, external))
        response = await core.search("result", mode=SourceMode.GOREECLOUD_ONLY, limit=10)
        self.assertEqual(external.calls, 0)
        self.assertFalse(response.plan.third_party_query_disclosure)
        self.assertEqual(len(response.results), 1)

    async def test_max_concurrency_is_enforced(self) -> None:
        tracker = {"active": 0, "max": 0}
        providers = tuple(FakeProvider(f"p{i}", ProviderOrigin.GOREECLOUD_SERVICE, delay=0.03, candidates=(candidate(f"p{i}", f"r{i}"),), tracker=tracker) for i in range(4))
        query = parse_query("result")
        plan = plan_sources(query, SourceMode.FEDERATED, tuple(p.descriptor for p in providers))
        executor = SearchExecutor(providers, policy=ExecutionPolicy(per_provider_timeout_seconds=1.0, max_concurrency=2))
        report = await executor.execute(query, plan, limit=10)
        self.assertEqual(tracker["max"], 2)
        self.assertEqual(report.availability, SearchAvailability.AVAILABLE)

    async def test_outer_cancellation_propagates_and_cancels_provider_work(self) -> None:
        slow = FakeProvider("slow", ProviderOrigin.GOREECLOUD_SERVICE, delay=1.0, candidates=(candidate("slow", "one"),))
        query = parse_query("result")
        plan = plan_sources(query, SourceMode.FEDERATED, (slow.descriptor,))
        executor = SearchExecutor((slow,), policy=ExecutionPolicy(per_provider_timeout_seconds=5.0, max_concurrency=1))
        task = asyncio.create_task(executor.execute(query, plan, limit=10))
        await asyncio.sleep(0.02)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(slow.cancelled)

    async def test_spoofed_provider_provenance_is_rejected_as_failure(self) -> None:
        provider = FakeProvider("declared", ProviderOrigin.GOREECLOUD_SERVICE, candidates=(candidate("other-provider", "one"),))
        core = SearchCore(provider_adapters=(provider,))
        response = await core.search("result", mode=SourceMode.FEDERATED, limit=10)
        self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
        self.assertEqual(response.execution.attempts[0].status, ProviderExecutionStatus.ERROR)
        self.assertEqual(response.results, ())

    async def test_oversized_batch_fails_without_retaining_provider_payload(self) -> None:
        private_payload = "synthetic private provider payload"
        provider = BatchProvider(
            "oversized",
            ProviderOrigin.GOREECLOUD_SERVICE,
            batches=(
                ProviderSearchBatch(
                    candidates=(candidate("oversized", "one", private_payload),) * 1000,
                    degraded=True,
                    warnings=(private_payload,),
                ),
            ),
        )
        response = await SearchCore(provider_adapters=(provider,)).search("result", limit=1)

        self.assertEqual(provider.requested_limits, [1])
        self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
        self.assertEqual(response.execution.candidates, ())
        self.assertEqual(response.results, ())
        attempt = response.execution.attempts[0]
        self.assertEqual(attempt.status, ProviderExecutionStatus.ERROR)
        self.assertEqual(attempt.result_count, 0)
        self.assertEqual(attempt.warnings, ())
        self.assertEqual(attempt.reason, "provider execution failed")
        self.assertNotIn(private_payload, repr(response.execution))

    async def test_malformed_batch_shapes_fail_as_generic_provider_errors(self) -> None:
        item = candidate("malformed", "one")
        batches = (
            None,
            {"candidates": (item,)},
            ProviderSearchBatch(candidates=[item]),
            ProviderSearchBatch(candidates=iter((item,))),
            ProviderSearchBatch(candidates=None),
            ProviderSearchBatch(candidates=(item, object())),
            ProviderSearchBatch(candidates=(item,), degraded="false"),
            ProviderSearchBatch(candidates=(item,), degraded=1),
            ProviderSearchBatch(candidates=(item,), warnings="synthetic payload"),
            ProviderSearchBatch(candidates=(item,), warnings=["synthetic payload"]),
            ProviderSearchBatch(candidates=(item,), warnings=(None,)),
        )
        for batch in batches:
            with self.subTest(batch_type=type(batch).__name__, batch=batch):
                provider = BatchProvider(
                    "malformed", ProviderOrigin.GOREECLOUD_SERVICE, batches=(batch,)
                )
                response = await SearchCore(provider_adapters=(provider,)).search(
                    "result", limit=2
                )
                self.assertEqual(provider.calls, 1)
                self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
                self.assertEqual(response.execution.candidates, ())
                self.assertEqual(response.results, ())
                attempt = response.execution.attempts[0]
                self.assertEqual(attempt.status, ProviderExecutionStatus.ERROR)
                self.assertEqual(attempt.result_count, 0)
                self.assertEqual(attempt.warnings, ())
                self.assertEqual(attempt.reason, "provider execution failed")

    async def test_malformed_candidate_fields_fail_before_normalization_and_ranking(self) -> None:
        item = candidate("malformed", "one")
        invalid_fields = {
            "title": None,
            "url": 123,
            "snippet": ("synthetic payload",),
            "provider": None,
            "published_at": 123,
            "content_type": 123,
            "canonical_url": 123,
            "source_id": ("synthetic payload",),
            "content_hash": 123,
            "language": 123,
            "last_crawled_at": 123,
            "provider_contract_version": 123,
        }
        malformed = [
            (field, replace(item, **{field: value}))
            for field, value in invalid_fields.items()
        ]
        malformed.extend(
            ("provider_rank", replace(item, provider_rank=rank))
            for rank in (True, 1.5, "first")
        )
        for field, invalid_candidate in malformed:
            with self.subTest(field=field):
                provider = BatchProvider(
                    "malformed",
                    ProviderOrigin.GOREECLOUD_SERVICE,
                    batches=(ProviderSearchBatch(candidates=(invalid_candidate,)),),
                )
                response = await SearchCore(provider_adapters=(provider,)).search(
                    "result", limit=1
                )
                self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
                self.assertEqual(response.execution.candidates, ())
                self.assertEqual(response.results, ())
                self.assertEqual(response.execution.attempts[0].status, ProviderExecutionStatus.ERROR)
                self.assertEqual(response.execution.attempts[0].reason, "provider execution failed")

    async def test_empty_and_exact_limit_batches_remain_successful(self) -> None:
        batches = (
            ProviderSearchBatch(candidates=()),
            ProviderSearchBatch(
                candidates=(candidate("bounded", "one"), candidate("bounded", "two"))
            ),
        )
        for batch in batches:
            with self.subTest(result_count=len(batch.candidates)):
                provider = BatchProvider(
                    "bounded", ProviderOrigin.GOREECLOUD_SERVICE, batches=(batch,)
                )
                response = await SearchCore(provider_adapters=(provider,)).search(
                    "result", limit=2
                )
                self.assertEqual(provider.requested_limits, [2])
                self.assertEqual(response.execution.availability, SearchAvailability.AVAILABLE)
                self.assertEqual(response.execution.candidates, batch.candidates)
                self.assertEqual(len(response.results), len(batch.candidates))
                self.assertEqual(response.execution.attempts[0].status, ProviderExecutionStatus.SUCCESS)
                self.assertEqual(response.execution.attempts[0].result_count, len(batch.candidates))

    async def test_oversized_fallback_uses_remaining_limit_and_preserves_primary(self) -> None:
        native = FakeProvider(
            "index",
            ProviderOrigin.GOREECLOUD_INDEX,
            candidates=(candidate("index", "one"), candidate("index", "two")),
        )
        external = BatchProvider(
            "external",
            ProviderOrigin.EXTERNAL,
            batches=(
                ProviderSearchBatch(
                    candidates=(candidate("external", "three"), candidate("external", "four"))
                ),
            ),
        )
        response = await SearchCore(provider_adapters=(native, external)).search(
            "result", mode=SourceMode.INDEX_FIRST, limit=3
        )

        self.assertEqual(external.requested_limits, [1])
        self.assertTrue(response.execution.fallback_used)
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        self.assertEqual(len(response.results), 2)
        self.assertTrue(all(item.provider == "index" for item in response.execution.candidates))
        self.assertEqual(
            {attempt.provider: attempt.status for attempt in response.execution.attempts},
            {"index": ProviderExecutionStatus.SUCCESS, "external": ProviderExecutionStatus.ERROR},
        )

    async def test_malformed_primary_still_allows_successful_fallback(self) -> None:
        native = BatchProvider(
            "index",
            ProviderOrigin.GOREECLOUD_INDEX,
            batches=(ProviderSearchBatch(candidates=(candidate("index", "one"),) * 3),),
        )
        external = BatchProvider(
            "external",
            ProviderOrigin.EXTERNAL,
            batches=(ProviderSearchBatch(candidates=(candidate("external", "two"),)),),
        )
        response = await SearchCore(provider_adapters=(native, external)).search(
            "result", mode=SourceMode.INDEX_FIRST, limit=2
        )

        self.assertEqual(native.requested_limits, [2])
        self.assertEqual(external.requested_limits, [2])
        self.assertTrue(response.execution.fallback_used)
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.execution.candidates[0].provider, "external")
        self.assertEqual(
            {attempt.provider: attempt.status for attempt in response.execution.attempts},
            {"index": ProviderExecutionStatus.ERROR, "external": ProviderExecutionStatus.SUCCESS},
        )

    async def test_malformed_federated_provider_preserves_peer_success(self) -> None:
        good = FakeProvider(
            "good", ProviderOrigin.GOREECLOUD_SERVICE, candidates=(candidate("good", "one"),)
        )
        bad = BatchProvider(
            "bad", ProviderOrigin.EXTERNAL,
            batches=(ProviderSearchBatch(candidates=(candidate("bad", "two"), object())),),
        )
        response = await SearchCore(provider_adapters=(good, bad)).search(
            "result", mode=SourceMode.FEDERATED, limit=2
        )

        self.assertEqual(good.calls, 1)
        self.assertEqual(bad.calls, 1)
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.execution.candidates[0].provider, "good")
        self.assertEqual(
            {attempt.provider: attempt.status for attempt in response.execution.attempts},
            {"good": ProviderExecutionStatus.SUCCESS, "bad": ProviderExecutionStatus.ERROR},
        )

    async def test_failed_batch_does_not_prevent_later_request_from_recovering(self) -> None:
        item = candidate("recovering", "one")
        provider = BatchProvider(
            "recovering",
            ProviderOrigin.GOREECLOUD_SERVICE,
            batches=(ProviderSearchBatch(candidates=(item, item)), ProviderSearchBatch(candidates=(item,))),
        )
        core = SearchCore(provider_adapters=(provider,))
        failed = await core.search("result", limit=1)
        recovered = await core.search("result", limit=1)

        self.assertEqual(failed.execution.availability, SearchAvailability.UNAVAILABLE)
        self.assertEqual(failed.results, ())
        self.assertEqual(recovered.execution.availability, SearchAvailability.AVAILABLE)
        self.assertEqual(recovered.execution.attempts[0].status, ProviderExecutionStatus.SUCCESS)
        self.assertEqual(len(recovered.results), 1)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(provider.requested_limits, [1, 1])

    async def test_invalid_open_url_with_safe_alias_isolated_from_healthy_peer(self) -> None:
        for url in (
            "javascript:alert('synthetic-private-payload')",
            "https://synthetic:private-payload@example.com/private",
            "https://example.com/private\npath",
            "https://faß.de/private",
            "http://127.1/private",
            "https://example.com:65536/private",
        ):
            with self.subTest(url=url):
                good = FakeProvider(
                    "good", ProviderOrigin.GOREECLOUD_SERVICE,
                    candidates=(candidate("good", "good"),),
                )
                bad = FakeProvider(
                    "bad", ProviderOrigin.EXTERNAL,
                    candidates=(
                        candidate("bad", "valid-from-invalid-batch"),
                        replace(candidate("bad", "bad"), url=url, canonical_url="https://example.com/safe"),
                    ),
                    warnings=("synthetic-private-payload",),
                )
                response = await SearchCore(provider_adapters=(good, bad)).search(
                    "result", mode=SourceMode.FEDERATED, limit=2
                )

                self.assertEqual((good.calls, bad.calls), (1, 1))
                self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
                self.assertEqual(response.execution.candidates, (candidate("good", "good"),))
                self.assertEqual(len(response.results), 1)
                attempts = {attempt.provider: attempt for attempt in response.execution.attempts}
                self.assertEqual(attempts["good"].status, ProviderExecutionStatus.SUCCESS)
                self.assertEqual(attempts["bad"].status, ProviderExecutionStatus.ERROR)
                self.assertEqual(attempts["bad"].reason, "provider execution failed")
                self.assertEqual(attempts["bad"].result_count, 0)
                self.assertEqual(attempts["bad"].warnings, ())
                self.assertNotIn("private-payload", repr(response.execution))

    async def test_invalid_display_content_isolated_from_healthy_peer(self) -> None:
        for changes in (
            {"title": "\x00\n\u202e"},
            {"title": "\ud800"},
            {"snippet": "\udfff"},
        ):
            with self.subTest(changes=changes):
                good = FakeProvider(
                    "good", ProviderOrigin.GOREECLOUD_SERVICE,
                    candidates=(candidate("good", "good"),),
                )
                bad = FakeProvider(
                    "bad", ProviderOrigin.EXTERNAL,
                    candidates=(replace(candidate("bad", "bad"), **changes),),
                )
                response = await SearchCore(provider_adapters=(good, bad)).search(
                    "result", mode=SourceMode.FEDERATED, limit=2
                )

                self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
                self.assertEqual(response.execution.candidates, (candidate("good", "good"),))
                self.assertEqual(len(response.results), 1)
                attempts = {attempt.provider: attempt for attempt in response.execution.attempts}
                self.assertEqual(attempts["good"].status, ProviderExecutionStatus.SUCCESS)
                self.assertEqual(attempts["bad"].status, ProviderExecutionStatus.ERROR)
                self.assertEqual(attempts["bad"].reason, "provider execution failed")

    async def test_oversized_url_and_raw_display_source_fields_fail_cleanly(self) -> None:
        for field, value in (
            ("url", "https://example.com/" + "a" * 8192),
            ("canonical_url", "https://example.com/" + "a" * 8192),
            ("url", "https://example.com/?q=" + "é" * 2000),
            ("title", "T" * 32_769),
            ("snippet", "S" * 32_769),
        ):
            with self.subTest(field=field, source_length=len(value)):
                provider = FakeProvider(
                    "bad", ProviderOrigin.GOREECLOUD_SERVICE,
                    candidates=(replace(candidate("bad", "bad"), **{field: value}),),
                )
                response = await SearchCore(provider_adapters=(provider,)).search("result", limit=1)

                self.assertEqual(provider.calls, 1)
                self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
                self.assertEqual(response.execution.candidates, ())
                self.assertEqual(response.results, ())
                attempt = response.execution.attempts[0]
                self.assertEqual(attempt.status, ProviderExecutionStatus.ERROR)
                self.assertEqual(attempt.reason, "provider execution failed")
                self.assertEqual(attempt.result_count, 0)

    async def test_invalid_primary_content_still_allows_index_first_fallback(self) -> None:
        native = FakeProvider(
            "index", ProviderOrigin.GOREECLOUD_INDEX,
            candidates=(replace(candidate("index", "bad"), title="\x00\u202e"),),
        )
        external = BatchProvider(
            "external", ProviderOrigin.EXTERNAL,
            batches=(ProviderSearchBatch(candidates=(candidate("external", "good"),)),),
        )
        response = await SearchCore(provider_adapters=(native, external)).search(
            "result", mode=SourceMode.INDEX_FIRST, limit=1
        )

        self.assertEqual(external.requested_limits, [1])
        self.assertTrue(response.execution.fallback_used)
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        self.assertEqual(response.execution.candidates, (candidate("external", "good"),))
        self.assertEqual(len(response.results), 1)
        self.assertEqual(
            {attempt.provider: attempt.status for attempt in response.execution.attempts},
            {"index": ProviderExecutionStatus.ERROR, "external": ProviderExecutionStatus.SUCCESS},
        )

    async def test_invalid_fallback_content_preserves_healthy_primary(self) -> None:
        native = FakeProvider(
            "index", ProviderOrigin.GOREECLOUD_INDEX,
            candidates=(candidate("index", "good"),),
        )
        external = BatchProvider(
            "external", ProviderOrigin.EXTERNAL,
            batches=(ProviderSearchBatch(candidates=(
                replace(candidate("external", "bad"), url="https://user:pass@example.com/private", canonical_url="https://example.com/safe"),
            )),),
        )
        response = await SearchCore(provider_adapters=(native, external)).search(
            "result", mode=SourceMode.INDEX_FIRST, limit=2
        )

        self.assertEqual(external.requested_limits, [1])
        self.assertTrue(response.execution.fallback_used)
        self.assertEqual(response.execution.availability, SearchAvailability.DEGRADED)
        self.assertEqual(response.execution.candidates, (candidate("index", "good"),))
        self.assertEqual(len(response.results), 1)
        self.assertEqual(
            {attempt.provider: attempt.status for attempt in response.execution.attempts},
            {"index": ProviderExecutionStatus.SUCCESS, "external": ProviderExecutionStatus.ERROR},
        )

    async def test_invalid_content_never_expands_privacy_restricted_provider_plan(self) -> None:
        for mode, budget in (
            (SourceMode.GOREECLOUD_ONLY, None),
            (SourceMode.OFFLINE_LOCAL, None),
            (SourceMode.INDEX_FIRST, QueryDisclosureBudget(max_third_party_providers=0)),
        ):
            with self.subTest(mode=mode.value):
                local = FakeProvider(
                    "local", ProviderOrigin.LOCAL,
                    candidates=(replace(candidate("local", "bad"), url="javascript:alert(1)"),),
                )
                external = FakeProvider(
                    "external", ProviderOrigin.EXTERNAL,
                    candidates=(candidate("external", "good"),),
                )
                response = await SearchCore(provider_adapters=(local, external)).search(
                    "result", mode=mode, limit=1, disclosure_budget=budget
                )

                self.assertEqual(local.calls, 1)
                self.assertEqual(external.calls, 0)
                self.assertFalse(response.plan.third_party_query_disclosure)
                self.assertFalse(response.execution.fallback_used)
                self.assertEqual(response.execution.availability, SearchAvailability.UNAVAILABLE)
                self.assertEqual(response.execution.candidates, ())
                self.assertEqual(response.results, ())

    async def test_all_invalid_index_delegation_content_is_unavailable_and_later_recovers(self) -> None:
        index = FakeProvider(
            "index", ProviderOrigin.GOREECLOUD_INDEX,
            candidates=(candidate("index", "unused"),),
        )
        one = candidate("one", "one")
        two = candidate("two", "two")
        first = BatchProvider(
            "one", ProviderOrigin.EXTERNAL,
            batches=(
                ProviderSearchBatch(candidates=(replace(one, url="https://user:synthetic-payload@example.com/private", canonical_url="https://example.com/safe"),), warnings=("synthetic-payload",)),
                ProviderSearchBatch(candidates=(one,)),
            ),
        )
        second = BatchProvider(
            "two", ProviderOrigin.EXTERNAL,
            batches=(
                ProviderSearchBatch(candidates=(replace(two, title="\x00\u202e"),)),
                ProviderSearchBatch(candidates=(two,)),
            ),
        )
        core = SearchCore(provider_adapters=(index, first, second))
        failed = await core.search_from_index("result", limit=2)
        recovered = await core.search_from_index("result", limit=2)

        self.assertEqual(index.calls, 0)
        self.assertEqual(failed.plan.mode, SourceMode.EXTERNAL_ONLY)
        self.assertFalse(failed.execution.fallback_used)
        self.assertEqual(failed.execution.availability, SearchAvailability.UNAVAILABLE)
        self.assertEqual(failed.execution.candidates, ())
        self.assertEqual(failed.results, ())
        self.assertTrue(all(attempt.status is ProviderExecutionStatus.ERROR for attempt in failed.execution.attempts))
        self.assertTrue(all(attempt.reason == "provider execution failed" and not attempt.warnings for attempt in failed.execution.attempts))
        self.assertNotIn("synthetic-payload", repr(failed.execution))
        self.assertEqual(recovered.execution.availability, SearchAvailability.AVAILABLE)
        self.assertEqual(len(recovered.results), 2)
        self.assertEqual(first.requested_limits, [2, 2])
        self.assertEqual(second.requested_limits, [2, 2])

    async def test_content_prevalidation_preserves_central_sanitization_and_cross_provider_merge(self) -> None:
        native_item = ResultCandidate(
            "Result\u202e\n title", "https://example.com/shared?utm_source=index",
            " first\x00 second ", "index", content_hash="shared-hash",
        )
        external_item = ResultCandidate(
            "Other result", "https://mirror.example.com/shared", "mirror", "external",
            content_hash="SHARED-HASH",
        )
        native = FakeProvider("index", ProviderOrigin.GOREECLOUD_INDEX, candidates=(native_item,))
        external = FakeProvider("external", ProviderOrigin.EXTERNAL, candidates=(external_item,))
        response = await SearchCore(provider_adapters=(native, external)).search(
            "result", mode=SourceMode.FEDERATED, limit=2
        )

        self.assertEqual(response.execution.availability, SearchAvailability.AVAILABLE)
        self.assertEqual(response.execution.candidates, (native_item, external_item))
        self.assertEqual(len(response.results), 1)
        result = response.results[0].result
        self.assertEqual(result.title, "Result title")
        self.assertEqual(result.snippet, "first second")
        self.assertEqual(result.canonical_url, "https://example.com/shared")
        self.assertEqual(result.source_agreement, 2)
        self.assertEqual({item.provider for item in result.provenance}, {"index", "external"})


if __name__ == "__main__":
    unittest.main()
