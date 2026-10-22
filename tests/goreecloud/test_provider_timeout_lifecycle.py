"""Timeout ownership stays with the coordinator after its response deadline.

Tests are offline: no real providers, network access, or retained query data.
"""
import threading
from timeit import default_timer
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from searx.results import ResultContainer
from searx.search import Search
from searx.search.processors.abstract import EngineProcessor


class LateProviderTests(TestCase):
    def setUp(self):
        self.processor = SimpleNamespace(
            engine=SimpleNamespace(name='synthetic-timeout'),
            suspended_status=SimpleNamespace(resume=MagicMock(), suspend=MagicMock()),
            _extend_container_basic=MagicMock(),
            logger=SimpleNamespace(error=MagicMock()),
        )

    def test_late_exception_does_not_change_closed_results_or_metrics(self):
        result = ResultContainer()
        result.close()
        with patch('searx.search.processors.abstract.threading.current_thread',
                   return_value=SimpleNamespace(_timeout=True)), patch(
                   'searx.search.processors.abstract.counter_inc') as metric:
            EngineProcessor.handle_exception(self.processor, result, RuntimeError('late failure'), True)
            EngineProcessor.extend_container(self.processor, result, default_timer(), [])
            metric.assert_not_called()
        self.assertFalse(result.unresponsive_engines)
        self.processor.suspended_status.suspend.assert_not_called()
        self.processor.suspended_status.resume.assert_not_called()
        self.processor._extend_container_basic.assert_not_called()

    def test_closed_container_drops_late_results_without_logging_payload(self):
        result = ResultContainer()
        result.close()
        sensitive_result = {
            'url': 'https://example.invalid/search/private-query-marker',
            'title': 'private-query-marker',
            'content': 'private-query-marker',
        }

        with patch('searx.results.log') as logger:
            result.extend('synthetic-timeout', [sensitive_result])

        logger.debug.assert_called_once_with('container is closed, ignoring late provider results')
        self.assertNotIn('private-query-marker', repr(logger.mock_calls))
        self.assertEqual({}, result.main_results_map)
        self.assertFalse(result.suggestions)
        self.assertEqual({}, result.engine_data)
        self.assertNotIn('engine', sensitive_result)

    def test_coordinator_records_exactly_one_timeout_after_deadline(self):
        started = threading.Event()
        resume = threading.Event()
        done = threading.Event()

        def fake_search(query, params, container, start, limit):
            started.set()
            if not resume.wait(2):
                return
            try:
                EngineProcessor.handle_exception(self.processor, container, RuntimeError('late'), False)
                EngineProcessor.extend_container(self.processor, container, default_timer(), [])
            finally:
                done.set()

        self.processor.search = fake_search
        query = SimpleNamespace()
        search = Search(query)
        search.actual_timeout = 0.05
        search.start_time = default_timer()
        with patch('searx.search.copy_current_request_context', side_effect=lambda f: f), patch(
                'searx.search.PROCESSORS', {'synthetic-timeout': self.processor}), patch.dict(
                'searx.engines.engines',
                {'synthetic-timeout': SimpleNamespace(display_error_messages=True)}), patch(
                'searx.search.processors.abstract.counter_inc') as metric:
            search.search_multiple_requests([('synthetic-timeout', 'synthetic', {})])
            self.assertTrue(started.is_set())
            self.assertEqual(['timeout'], sorted(x.error_type for x in search.result_container.unresponsive_engines))
            search.result_container.close()
            resume.set()
            self.assertTrue(done.wait(2), 'late worker did not exit')
            self.assertEqual(['timeout'], sorted(x.error_type for x in search.result_container.unresponsive_engines))
            metric.assert_not_called()
        self.processor._extend_container_basic.assert_not_called()
        self.processor.suspended_status.resume.assert_not_called()

    def test_on_time_provider_error_is_still_recorded(self):
        result = ResultContainer()
        with patch('searx.search.processors.abstract.threading.current_thread',
                   return_value=SimpleNamespace(_timeout=False)), patch(
                   'searx.search.processors.abstract.counter_inc'), patch(
                   'searx.search.processors.abstract.count_error'), patch.dict(
                   'searx.engines.engines',
                   {'synthetic-timeout': SimpleNamespace(display_error_messages=True)}):
            EngineProcessor.handle_exception(self.processor, result, 'access denied', False)
        self.assertEqual(['access denied'], [x.error_type for x in result.unresponsive_engines])
