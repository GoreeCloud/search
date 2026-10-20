"""Offline, no-provider-network tests for isolated staging Tor startup gate."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "goreecloud_staging_gate", ROOT / "scripts/staging_start_search.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class StagingGateTests(unittest.TestCase):
    def test_rejected_tor_never_starts_search(self):
        output = io.StringIO()
        def reject(coroutine):
            coroutine.close()
            return False
        with patch.object(gate.asyncio, "run", side_effect=reject), patch.object(
            gate.os, "execv"
        ) as execv, contextlib.redirect_stderr(output):
            self.assertEqual(78, gate.main())
        execv.assert_not_called()
        self.assertIn("STAGING_STARTUP_BLOCKED", output.getvalue())
        self.assertNotIn("socks5h://", output.getvalue())

    def test_valid_tor_execs_exact_granian_only(self):
        def accept(coroutine):
            coroutine.close()
            return True
        with patch.object(gate.asyncio, "run", side_effect=accept), patch.object(
            gate.os, "execv"
        ) as execv, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(78, gate.main())
        execv.assert_called_once_with(gate.GRANIAN, [gate.GRANIAN, "searx.webapp:app"])

    def test_gate_uses_strict_loopback_proxy_and_fixed_tor_endpoint(self):
        self.assertEqual("socks5h://127.0.0.1:9050", gate.LOCAL_SOCKS)
        self.assertEqual("https://check.torproject.org/api/ip", gate.TOR_CHECK_URL)
        self.assertLessEqual(gate.ATTEMPTS, 30)
        self.assertGreater(gate.ATTEMPTS, 1)


class StagingAsyncGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_before_accepting_verified_tor(self):
        with patch.object(gate, "tor_is_ready", new_callable=AsyncMock) as attested:
            with patch.object(gate.asyncio, "sleep", new_callable=AsyncMock) as sleep:
                attested.side_effect = [False, False, True]
                self.assertIs(True, await gate.await_verified_tor())
                self.assertEqual(3, attested.await_count)
                self.assertEqual(2, sleep.await_count)

    async def test_all_attempts_fail_without_fallback(self):
        with patch.object(gate, "tor_is_ready", new_callable=AsyncMock) as attested:
            with patch.object(gate.asyncio, "sleep", new_callable=AsyncMock):
                attested.return_value = False
                self.assertIs(False, await gate.await_verified_tor())
                self.assertEqual(gate.ATTEMPTS, attested.await_count)


if __name__ == "__main__":
    unittest.main()
