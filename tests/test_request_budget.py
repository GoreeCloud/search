"""Offline, source-independent tests for the paid-provider durable request ceiling."""
from __future__ import annotations

import os
import sqlite3
import stat
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from goreecloud_search import providers
from goreecloud_search.request_budget import (
    BudgetExhausted, BudgetUnavailable, reserve_request,
)


def _reserve_from_process(args):
    ledger, cap = args
    try:
        reserve_request(Path(ledger), cap)
        return True
    except BudgetExhausted:
        return False


class _Response:
    status = 200

    def getheader(self, name, default=None):
        if name == "Content-Type":
            return "application/json"
        return default

    def read(self, limit=-1):
        return b'{"web":{"results":[]}}'[:limit]


class _Connection:
    def __init__(self):
        self.calls = 0
    def request(self, *args, **kwargs):
        self.calls += 1
    def getresponse(self):
        return _Response()
    def close(self):
        pass


class DurableRequestBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private" / "paid-requests.sqlite3"

    def test_cap_persists_across_reopen_and_does_not_refund_errors(self):
        for _ in range(3):
            reserve_request(self.path, 3)
        with self.assertRaises(BudgetExhausted):
            reserve_request(self.path, 3)
        with sqlite3.connect(self.path) as db:
            count = db.execute("SELECT reserved FROM daily_requests").fetchone()[0]
        self.assertEqual(count, 3)

    def test_multithreaded_requests_cannot_exceed_single_cap(self):
        def try_reserve(_):
            try:
                reserve_request(self.path, 4)
                return True
            except BudgetExhausted:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcomes = list(pool.map(try_reserve, range(20)))
        self.assertEqual(sum(outcomes), 4)

    def test_multiple_processes_observe_one_daily_cap(self):
        with ProcessPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(_reserve_from_process, [(str(self.path), 3)] * 12))
        self.assertEqual(sum(outcomes), 3)

    def test_utc_day_accounting(self):
        day = datetime(2026, 11, 1, 23, 55, tzinfo=timezone.utc)
        reserve_request(self.path, 1, now=day)
        with self.assertRaises(BudgetExhausted):
            reserve_request(self.path, 1, now=day)
        reserve_request(self.path, 1, now=day + timedelta(minutes=10))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT SUM(reserved) FROM daily_requests").fetchone()[0], 2)

    def test_private_permissions_and_no_query_storage(self):
        reserve_request(self.path, 2)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(
                [row[1] for row in db.execute("PRAGMA table_info(daily_requests)")],
                ["day", "reserved"],
            )

    def test_symlinked_file_and_directory_rejected(self):
        reserve_request(self.path, 3)
        alias = self.path.parent / "alias.sqlite3"
        alias.symlink_to(self.path)
        with self.assertRaises(BudgetUnavailable):
            reserve_request(alias, 3)
        via_dir = Path(self.temp.name) / "alias-dir"
        via_dir.symlink_to(self.path.parent, target_is_directory=True)
        with self.assertRaises(BudgetUnavailable):
            reserve_request(via_dir / "unused.sqlite3", 3)

    def test_symlinked_nonimmediate_ancestor_fails_closed(self):
        owned = Path(self.temp.name) / "owned"
        nested = owned / "state"
        nested.mkdir(parents=True, mode=0o700)
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(owned, target_is_directory=True)
        ledger = alias / "state" / "requests.sqlite3"
        self.assertFalse(ledger.parent.is_symlink())
        with self.assertRaises(BudgetUnavailable):
            reserve_request(ledger, 2)
        self.assertFalse((nested / "requests.sqlite3").exists())

    def test_wide_permissions_and_corrupt_ledger_fail_closed(self):
        reserve_request(self.path, 2)
        self.path.chmod(0o644)
        with self.assertRaises(BudgetUnavailable):
            reserve_request(self.path, 2)
        self.path.chmod(0o600)
        self.path.write_bytes(b"not an SQLite ledger")
        with self.assertRaises(BudgetUnavailable):
            reserve_request(self.path, 2)

    def test_invalid_limit_and_relative_path_rejected(self):
        for value in (0, 10001, True, "2"):
            with self.subTest(value=value), self.assertRaises(BudgetUnavailable):
                reserve_request(self.path, value)
        with self.assertRaises(BudgetUnavailable):
            reserve_request(Path("relative.sqlite3"), 1)

    def test_environment_requires_explicit_cap_for_brave(self):
        with patch.dict(os.environ, {
            "GC_SEARCH_EXTERNAL_ENABLED": "1",
            "GC_SEARCH_BRAVE_API_KEY": "dummy-not-a-secret",
        }, clear=True):
            config = providers.ProviderConfig.from_environment()
        self.assertFalse(config.availability()["brave"])
        with patch.dict(os.environ, {
            "GC_SEARCH_EXTERNAL_ENABLED": "1",
            "GC_SEARCH_BRAVE_API_KEY": "dummy-not-a-secret",
            "GC_SEARCH_BRAVE_DAILY_CAP": "7",
            "GC_SEARCH_BRAVE_BUDGET_DB": str(self.path),
        }, clear=True):
            config = providers.ProviderConfig.from_environment()
        self.assertTrue(config.availability()["brave"])
        self.assertEqual(config.brave_daily_cap, 7)
        self.assertEqual(config.brave_budget_db, self.path)

    def test_invalid_env_cap_and_relative_state_fail_closed(self):
        for value in ("0", "-1", "10001", "12.5", "no", "１２"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"GC_SEARCH_BRAVE_DAILY_CAP": value}, clear=True):
                    with self.assertRaises(providers.ProviderConfigError):
                        providers.ProviderConfig.from_environment()
        with patch.dict(os.environ, {
            "GC_SEARCH_BRAVE_DAILY_CAP": "2",
            "GC_SEARCH_BRAVE_BUDGET_DB": "relative.sqlite3",
        }, clear=True):
            with self.assertRaises(providers.ProviderConfigError):
                providers.ProviderConfig.from_environment()

    def test_oversized_brave_cap_fails_closed_before_integer_conversion(self):
        for value in ("9" * 5000, "1" * 5000):
            with self.subTest(prefix=value[:10]):
                with patch.dict(os.environ, {
                    "GC_SEARCH_EXTERNAL_ENABLED": "1",
                    "GC_SEARCH_BRAVE_API_KEY": "dummy-not-a-secret",
                    "GC_SEARCH_BRAVE_DAILY_CAP": value,
                    "GC_SEARCH_BRAVE_BUDGET_DB": str(self.path),
                }, clear=True):
                    with self.assertRaises(providers.ProviderConfigError):
                        providers.ProviderConfig.from_environment()
        self.assertFalse(self.path.exists())

    def test_oversized_searxng_port_fails_closed_without_network(self):
        for value in ("9" * 5000, "65536", "１２３４"):
            with self.subTest(value_prefix=value[:8]):
                with patch.dict(os.environ, {
                    "GC_SEARCH_EXTERNAL_ENABLED": "1",
                    "GC_SEARCH_SEARXNG_PORT": value,
                }, clear=True):
                    with self.assertRaises(providers.ProviderConfigError):
                        providers.ProviderConfig.from_environment()
        with patch.object(providers.http.client, "HTTPConnection") as outgoing:
            self.assertFalse(providers.ProviderConfig().availability()["searxng"])
            outgoing.assert_not_called()

    def test_leading_zero_provider_numbers_rejected_while_boundaries_work(self):
        for key, number in (
            ("GC_SEARCH_BRAVE_DAILY_CAP", "0001"),
            ("GC_SEARCH_SEARXNG_PORT", "08080"),
        ):
            with self.subTest(key=key):
                with patch.dict(os.environ, {key: number}, clear=True):
                    with self.assertRaises(providers.ProviderConfigError):
                        providers.ProviderConfig.from_environment()
        with patch.dict(os.environ, {
            "GC_SEARCH_BRAVE_DAILY_CAP": "10000",
            "GC_SEARCH_SEARXNG_PORT": "65535",
            "GC_SEARCH_EXTERNAL_ENABLED": "0",
        }, clear=True):
            config = providers.ProviderConfig.from_environment()
        self.assertEqual(config.brave_daily_cap, 10000)
        self.assertEqual(config.searxng_port, 65535)
        self.assertFalse(config.availability()["brave"])
        self.assertFalse(config.availability()["searxng"])

    def test_successful_mocked_brave_request_reserves_before_transport(self):
        config = providers.ProviderConfig(True, "dummy-not-a-secret", None, 1, self.path)
        with patch.object(providers.BRAVE_RATE_GATE, "reserve"):
            with patch.object(providers.http.client, "HTTPSConnection", return_value=_Connection()) as factory:
                self.assertEqual(providers.fetch("brave", "example", 2, config), [])
                self.assertEqual(factory.call_count, 1)
                with self.assertRaises(providers.ProviderUnavailable):
                    providers.fetch("brave", "example", 2, config)
                self.assertEqual(factory.call_count, 1)

    def test_paid_transport_never_opens_without_reservation(self):
        config = providers.ProviderConfig(True, "dummy-not-a-secret", None, 1, self.path)
        self.path.parent.mkdir(mode=0o700)
        self.path.write_bytes(b"corrupt budget state")
        self.path.chmod(0o600)
        with patch.object(providers.BRAVE_RATE_GATE, "reserve"):
            with patch.object(providers.http.client, "HTTPSConnection") as outgoing:
                with self.assertRaises(providers.ProviderUnavailable):
                    providers.fetch("brave", "example", 2, config)
                outgoing.assert_not_called()


if __name__ == "__main__":
    unittest.main()
