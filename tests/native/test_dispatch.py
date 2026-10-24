# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic offline contract checks for fusion source dispatch."""

import asyncio
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_search.dispatch import (
    ProviderBinding, ProviderRights, dispatch_fusion as real_dispatch_fusion,
)
from native_search.fusion import SourceResult
from native_search.index import SearchIndex
from native_search.owned_index_provider import (
    OWNED_INDEX_EVIDENCE, OWNED_INDEX_SOURCE, OWNED_IMAGE_EVIDENCE,
    OWNED_IMAGE_SOURCE, OwnedIndexAdapter, OwnedImageAdapter,
)


def allowed(category='web'):
    # Synthetic fixture rights, NOT a real provider agreement.
    return ProviderRights(frozenset({category}), True, True, True,
                          'offline-fixture', 'synthetic_fixture')


async def dispatch_fusion(*args, **kwargs):
    """Exercise fixture admission explicitly; real call defaults to deny."""
    return await real_dispatch_fusion(*args, allow_synthetic_fixtures=True, **kwargs)


def binding(name, callback, rights=None):
    return ProviderBinding(name, callback, allowed() if rights is None else rights)


def hit(name, rank=1, url='https://example.com/shared', *, category='web'):
    return SourceResult(name, category, rank, url, name.title())


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_ranker_uses_validated_query_without_changing_source_votes(self):
        async def owned_synthetic(_query, _category, _limit):
            return [
                SourceResult('alpha', 'web', 1, 'https://example.org/recipe',
                             'Weeknight spaghetti recipe'),
                SourceResult('alpha', 'web', 2, 'https://example.org/orchids',
                             'Orchid growing guide', 'How to care for orchids'),
            ]

        result = await dispatch_fusion('orchid', category='web',
                                       providers=[binding('alpha', owned_synthetic)])
        self.assertEqual('ok', result.status)
        self.assertEqual('https://example.org/orchids', result.results[0].url)
        self.assertEqual((('alpha', 2),), result.results[0].source_ranks)
        self.assertEqual(2, result.providers[0].accepted)

    async def test_invalid_relevance_query_never_reaches_a_provider(self):
        calls = []

        async def should_not_run(*_args):
            calls.append(True)
            return []

        for query in ('!!!', ' '.join(f'term{number}' for number in range(17))):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    await dispatch_fusion(query, category='news',
                                          providers=[binding('alpha', should_not_run,
                                                             allowed('news'))])
        self.assertEqual([], calls)

    async def test_owned_image_source_is_explicitly_sealed_and_local_only(self):
        with tempfile.TemporaryDirectory() as directory, SearchIndex(Path(directory) / 'owned.sqlite') as index:
            index.add_image(page_url='https://example.org/photo',
                            media_url='https://cdn.example.org/photo.png',
                            title='Golden field', description='Nature photograph',
                            rights_evidence='owner/photo-001')
            rights = ProviderRights(frozenset({'images'}), True, True, True,
                                    OWNED_IMAGE_EVIDENCE, 'owned_index')
            own = ProviderBinding(OWNED_IMAGE_SOURCE, OwnedImageAdapter(index), rights)
            result = await real_dispatch_fusion('Golden', category='images', providers=[own])
            self.assertEqual('ok', result.status)
            self.assertEqual('https://cdn.example.org/photo.png', result.results[0].media_url)
            self.assertEqual((('goreecloud_images', 1),), result.results[0].source_ranks)
            blocked_web = await real_dispatch_fusion('Golden', category='web', providers=[own])
            self.assertEqual('unavailable', blocked_web.status)
            self.assertEqual('blocked', blocked_web.providers[0].status)

            calls = []

            async def forged(*_args):
                calls.append(True)
                return [hit(OWNED_IMAGE_SOURCE, category='images')]

            attempts = [
                ProviderBinding(OWNED_IMAGE_SOURCE, forged, rights),
                ProviderBinding('remote_image', forged, rights),
                ProviderBinding(OWNED_IMAGE_SOURCE, forged, ProviderRights(
                    frozenset({'images'}), True, True, True,
                    OWNED_IMAGE_EVIDENCE, 'contract_reviewed')),
                ProviderBinding(OWNED_IMAGE_SOURCE, OwnedImageAdapter(index), ProviderRights(
                    frozenset({'images'}), True, True, True,
                    'not-the-local-image-evidence', 'owned_index')),
            ]
            for candidate in attempts:
                with self.subTest(source=candidate.source, basis=candidate.rights.rights_basis):
                    response = await real_dispatch_fusion('Golden', category='images',
                                                          providers=[candidate])
                    self.assertEqual('unavailable', response.status)
                    self.assertEqual('blocked', response.providers[0].status)
            self.assertEqual([], calls)
            with self.assertRaises(TypeError):
                OwnedImageAdapter(object())

    async def test_owned_local_index_is_admitted_without_upstream_rights(self):
        with tempfile.TemporaryDirectory() as directory, SearchIndex(Path(directory) / 'owned.sqlite') as index:
            index.add(url='https://example.org/owned', title='Private orchard',
                      body='Only explicitly ingested local content is available')
            own = ProviderBinding(OWNED_INDEX_SOURCE, OwnedIndexAdapter(index), ProviderRights(
                frozenset({'web'}), True, True, True, OWNED_INDEX_EVIDENCE, 'owned_index'))
            response = await real_dispatch_fusion('orchard', category='web', providers=[own])
            self.assertEqual('ok', response.status)
            self.assertEqual((('goreecloud_index', 1),), response.results[0].source_ranks)
            self.assertEqual('https://example.org/owned', response.results[0].url)
            self.assertEqual([('goreecloud_index', 'ok', 1)], [
                (item.source, item.status, item.accepted) for item in response.providers])
            images = await real_dispatch_fusion('orchard', category='images', providers=[own])
            self.assertEqual('unavailable', images.status)
            self.assertEqual('blocked', images.providers[0].status)

    async def test_owned_index_rights_never_license_external_callbacks(self):
        calls = []

        async def fake(*_args):
            calls.append(True)
            return [hit('goreecloud_index')]

        owner_rights = ProviderRights(frozenset({'web'}), True, True, True,
                                      OWNED_INDEX_EVIDENCE, 'owned_index')
        reviewed = ProviderRights(frozenset({'web'}), True, True, True,
                                  OWNED_INDEX_EVIDENCE, 'contract_reviewed')
        attempts = [
            ProviderBinding(OWNED_INDEX_SOURCE, fake, owner_rights),
            ProviderBinding('remote', fake, owner_rights),
            ProviderBinding(OWNED_INDEX_SOURCE, fake, reviewed),
        ]
        for source in attempts:
            with self.subTest(source=source.source, basis=source.rights.rights_basis):
                reply = await real_dispatch_fusion('secret', category='web', providers=[source])
                self.assertEqual('unavailable', reply.status)
                self.assertEqual('blocked', reply.providers[0].status)
        self.assertEqual([], calls)

    async def test_owned_adapter_requires_actual_native_index_and_exact_evidence(self):
        with self.assertRaises(TypeError):
            OwnedIndexAdapter(object())
        with tempfile.TemporaryDirectory() as directory, SearchIndex(Path(directory) / 'owned.sqlite') as index:
            index.add(url='https://example.org/owned', title='Orchard', body='owned data')
            forged_evidence = ProviderBinding(
                OWNED_INDEX_SOURCE, OwnedIndexAdapter(index),
                ProviderRights(frozenset({'web'}), True, True, True,
                               'external-contract-is-not-local-proof', 'owned_index'))
            response = await real_dispatch_fusion('Orchard', category='web',
                                                  providers=[forged_evidence])
            self.assertEqual('unavailable', response.status)
            self.assertEqual('blocked', response.providers[0].status)
            for categories, basis in ((frozenset({'images'}), 'owned_index'),
                                      (frozenset({'web', 'images'}), 'owned_index'),
                                      (frozenset({'web'}), 'contract_reviewed')):
                with self.subTest(categories=categories, basis=basis):
                    invalid = ProviderBinding(OWNED_INDEX_SOURCE, OwnedIndexAdapter(index),
                                              ProviderRights(categories, True, True, True,
                                                             OWNED_INDEX_EVIDENCE, basis))
                    result = await real_dispatch_fusion('Orchard', category='web',
                                                        providers=[invalid])
                    self.assertEqual('blocked', result.providers[0].status)

    async def test_closed_owned_index_does_not_leak_internal_exception_or_query(self):
        with tempfile.TemporaryDirectory() as directory:
            index = SearchIndex(Path(directory) / 'owned.sqlite')
            adapter = OwnedIndexAdapter(index)
            index.close()
            binding = ProviderBinding(OWNED_INDEX_SOURCE, adapter, ProviderRights(
                frozenset({'web'}), True, True, True, OWNED_INDEX_EVIDENCE, 'owned_index'))
            response = await real_dispatch_fusion('private sealed query', category='web',
                                                  providers=[binding])
            self.assertEqual('unavailable', response.status)
            self.assertEqual('failed', response.providers[0].status)
            self.assertEqual([], list(response.results))
            self.assertNotIn('private sealed query', str(asdict(response)))
            self.assertNotIn('database', str(asdict(response)))

    async def test_synthetic_sources_default_deny_without_test_switch(self):
        calls = []

        async def fake(*_args):
            calls.append(True)
            return [hit('alpha')]

        reply = await real_dispatch_fusion('fixture', category='web',
                                           providers=[binding('alpha', fake)])
        self.assertEqual(reply.providers[0].status, 'blocked')
        self.assertEqual(calls, [])

    async def test_real_fanout_merges_to_one_native_result(self):
        calls = []

        async def alpha(query, category, limit):
            calls.append(('alpha', query, category, limit))
            return [hit('alpha', 3)]

        async def beta(query, category, limit):
            calls.append(('beta', query, category, limit))
            return [hit('beta', 1, 'https://EXAMPLE.com/shared#fragment')]

        reply = await dispatch_fusion('test results', category='web',
                                      providers=[binding('alpha', alpha), binding('beta', beta)],
                                      limit=10, per_provider=8)
        self.assertEqual(reply.schema_version, 1)
        self.assertEqual(reply.status, 'ok')
        self.assertEqual(len(reply.results), 1)
        self.assertEqual(reply.results[0].source_ranks, (('alpha', 3), ('beta', 1)))
        self.assertEqual(sorted(calls), [('alpha', 'test results', 'web', 8),
                                         ('beta', 'test results', 'web', 8)])
        self.assertNotIn('test results', str(asdict(reply)))

    async def test_denied_source_is_never_called_even_if_registered(self):
        calls = []

        async def would_call(*_args):
            calls.append(True)
            return [hit('brave')]

        fake_brave = ProviderBinding('brave', would_call)
        reply = await dispatch_fusion('bounded test', category='web', providers=[fake_brave])
        self.assertEqual(reply.status, 'unavailable')
        self.assertEqual(reply.providers[0].status, 'blocked')
        self.assertEqual(calls, [])

    async def test_missing_each_right_disallows_dispatch(self):
        async def forbidden(*_args):
            self.fail('Rights-closed adapter was invoked')

        for rights in (
            ProviderRights(frozenset({'web'}), False, True, True, 'evidence'),
            ProviderRights(frozenset({'web'}), True, False, True, 'evidence'),
            ProviderRights(frozenset({'web'}), True, True, False, 'evidence'),
            ProviderRights(frozenset({'web'}), True, True, True, ''),
            ProviderRights(frozenset({'images'}), True, True, True, 'evidence'),
            ProviderRights('web', True, True, True, 'evidence'),
            ProviderRights(frozenset({'web'}), 'yes', True, True, 'evidence'),
            ProviderRights(frozenset({'web'}), True, True, True, 'evidence', 'unverified'),
        ):
            with self.subTest(rights=rights):
                reply = await dispatch_fusion('fixture', category='web',
                                              providers=[binding('alpha', forbidden, rights)])
                self.assertEqual(reply.providers[0].status, 'blocked')

    async def test_degraded_state_does_not_drop_healthy_source(self):
        async def good(*_args):
            return [hit('good')]

        async def bad(*_args):
            raise RuntimeError('private query appears only in upstream failure')

        reply = await dispatch_fusion('private query', category='web',
                                      providers=[binding('good', good), binding('bad', bad)])
        self.assertEqual(reply.status, 'partial')
        self.assertEqual(len(reply.results), 1)
        self.assertEqual([p.status for p in reply.providers], ['ok', 'failed'])
        self.assertNotIn('private query', str(reply))
        self.assertNotIn('upstream failure', str(reply))

    async def test_legal_denial_does_not_trigger_hidden_fallback(self):
        async def permitted(*_args):
            return [hit('alpha')]

        async def denied(*_args):
            self.fail('Denied provider was invoked as fallback')

        reply = await dispatch_fusion('fixture', category='web', providers=[
            binding('brave', denied, ProviderRights()), binding('alpha', permitted),
        ])
        self.assertEqual(reply.status, 'partial')
        self.assertEqual([p.status for p in reply.providers], ['blocked', 'ok'])
        self.assertEqual(len(reply.results), 1)

    async def test_timeout_is_classified_without_retry(self):
        started = []

        async def slow(*_args):
            started.append(True)
            await asyncio.sleep(1)
            return [hit('slow')]

        reply = await dispatch_fusion('fixture', category='web',
                                      providers=[binding('slow', slow)],
                                      timeout_seconds=0.05)
        self.assertEqual(reply.status, 'unavailable')
        self.assertEqual(reply.providers[0].status, 'timeout')
        self.assertEqual(len(started), 1)

    async def test_queued_fast_adapters_receive_full_deadline_after_start(self):
        # Assert the *placement* of per-provider wait_for, not near-expired
        # wall-clock sleeps. Heavy parallel CI can starve even healthy adapters
        # beyond a 60-ms timer, causing a false failure unrelated to whether
        # queued providers received their own full deadline after admission.
        started = []
        first_wave_started = asyncio.Event()
        release_first_wave = asyncio.Event()
        deadlines_started = []
        native_wait_for = asyncio.wait_for

        async def observed_wait_for(awaitable, *, timeout):
            deadlines_started.append(timeout)
            return await native_wait_for(awaitable, timeout=timeout)

        def adapter(number):
            async def source(_query, _category, _limit):
                started.append(number)
                if number < 2:
                    if len(started) == 2:
                        first_wave_started.set()
                    await release_first_wave.wait()
                return []
            return source

        with patch('native_search.dispatch.asyncio.wait_for', observed_wait_for):
            task = asyncio.create_task(dispatch_fusion(
                'fixture', category='web',
                providers=[binding('p%d' % i, adapter(i)) for i in range(4)],
                timeout_seconds=3, max_concurrency=2))
            try:
                await first_wave_started.wait()
                # The queued p2/p3 adapters may not acquire a slot yet; no
                # provider deadline can start while both slots are held.
                await asyncio.sleep(0)
                self.assertEqual(2, len(deadlines_started))
            finally:
                release_first_wave.set()
            response = await task
        self.assertEqual(len(started), 4)
        self.assertEqual(4, len(deadlines_started))
        self.assertEqual([p.status for p in response.providers], ['empty'] * 4)
        self.assertEqual(response.status, 'empty')

    async def test_empty_source_is_not_provider_failure(self):
        async def empty(*_args):
            return []

        reply = await dispatch_fusion('fixture', category='web',
                                      providers=[binding('zero', empty)])
        self.assertEqual(reply.status, 'empty')
        self.assertEqual(reply.providers[0].status, 'empty')

    async def test_bad_payload_does_not_poison_other_sources(self):
        async def invalid(*_args):
            return [hit('bad', 0)]

        async def valid(*_args):
            return [hit('good')]

        reply = await dispatch_fusion('fixture', category='web',
                                      providers=[binding('bad', invalid), binding('good', valid)])
        self.assertEqual(reply.status, 'partial')
        self.assertEqual([p.status for p in reply.providers], ['failed', 'ok'])
        self.assertEqual(len(reply.results), 1)

    async def test_unpublishable_url_fails_provider_instead_of_false_ok(self):
        async def unsafe(*_args):
            return [hit('bad', url='javascript:alert(1)')]

        async def good(*_args):
            return [hit('good')]

        response = await dispatch_fusion('fixture', category='web',
                                         providers=[binding('bad', unsafe), binding('good', good)])
        self.assertEqual(response.status, 'partial')
        self.assertEqual([(p.status, p.accepted) for p in response.providers],
                         [('failed', 0), ('ok', 1)])
        self.assertEqual(len(response.results), 1)

    async def test_wrong_source_identity_and_oversized_cards_are_rejected(self):
        async def wrong(*_args):
            return [hit('different')]

        async def too_many(*_args):
            return [hit('large', n + 1) for n in range(3)]

        reply = await dispatch_fusion('fixture', category='web', per_provider=2,
                                      providers=[binding('wrong', wrong), binding('large', too_many)])
        self.assertEqual(reply.status, 'unavailable')
        self.assertEqual([p.status for p in reply.providers], ['failed', 'failed'])

    async def test_provider_inventory_and_user_request_validation(self):
        async def empty(*_args):
            return []

        good = binding('alpha', empty)
        invalid = (
            {'query': '', 'category': 'web', 'providers': [good]},
            {'query': 'a\nsecret', 'category': 'web', 'providers': [good]},
            {'query': 'x' * 513, 'category': 'web', 'providers': [good]},
            {'query': 'test', 'category': 'shopping', 'providers': [good]},
            {'query': 'test', 'category': 'web', 'providers': []},
            {'query': 'test', 'category': 'web', 'providers': [good, good]},
            {'query': 'test', 'category': 'web', 'providers': [good], 'per_provider': 41},
            {'query': 'test', 'category': 'web', 'providers': [good], 'max_concurrency': 5},
            {'query': 'test', 'category': 'web', 'providers': [good], 'timeout_seconds': 0},
            {'query': 'test', 'category': 'web', 'providers': [good], 'limit': True},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                await dispatch_fusion(**kwargs)

    async def test_max_concurrency_is_enforced(self):
        active = 0
        observed = 0

        async def make(*_args):
            nonlocal active, observed
            active += 1
            observed = max(observed, active)
            await asyncio.sleep(0.01)
            active -= 1
            return []

        reply = await dispatch_fusion('fixture', category='web',
                                      providers=[binding('p%d' % i, make) for i in range(8)],
                                      max_concurrency=2, timeout_seconds=1)
        self.assertEqual(reply.status, 'empty')
        self.assertEqual(observed, 2)

    async def test_images_supported_with_explicit_vertical_rights(self):
        async def image(*_args):
            return [SourceResult('visual', 'images', 1, 'https://example.org/page',
                                 'Image', media_url='https://example.org/pic.jpg')]

        reply = await dispatch_fusion('fixture', category='images',
                                      providers=[binding('visual', image, allowed('images'))])
        self.assertEqual(reply.status, 'ok')
        self.assertEqual(reply.results[0].media_url, 'https://example.org/pic.jpg')


if __name__ == '__main__':
    unittest.main()
