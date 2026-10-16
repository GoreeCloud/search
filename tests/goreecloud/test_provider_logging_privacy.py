"""Regression: no provider request data in adapter log calls."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ('searx/engines/brave.py', 'searx/engines/startpage.py')
SENSITIVE = {'query', 'params', 'args', 'headers', 'cookies', 'sc_code', 'resp', 'response'}


class ProviderLoggingPrivacyTests(unittest.TestCase):
    def test_provider_logs_never_interpolate_request_data(self):
        for name in PROVIDERS:
            with self.subTest(adapter=name):
                tree = ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)
                for call in ast.walk(tree):
                    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                        continue
                    if not isinstance(call.func.value, ast.Name) or call.func.value.id != 'logger':
                        continue
                    if call.func.attr not in ('debug', 'info', 'warning', 'error', 'critical', 'exception'):
                        continue
                    for argument in call.args:
                        unsafe = {n.id for n in ast.walk(argument) if isinstance(n, ast.Name)} & SENSITIVE
                        self.assertFalse(unsafe, f'{name}:{call.lineno} logs sensitive values {unsafe}')
