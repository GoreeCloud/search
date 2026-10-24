"""Regression: no provider request data in adapter log calls."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ('searx/engines/brave.py', 'searx/engines/startpage.py',
             'searx/engines/duckduckgo.py')
SENSITIVE = {'query', 'params', 'args', 'headers', 'cookies', 'sc_code', 'resp', 'response'}


class ProviderLoggingPrivacyTests(unittest.TestCase):
    def test_closed_results_never_log_provider_payload(self):
        name = 'searx/results.py'
        tree = ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)
        container = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                         and node.name == 'ResultContainer')
        extend = next(node for node in container.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'extend')
        closed_branch = extend.body[0]
        self.assertIsInstance(closed_branch, ast.If)
        self.assertIsInstance(closed_branch.test, ast.Attribute)
        self.assertEqual('_closed', closed_branch.test.attr)
        self.assertTrue(any(isinstance(node, ast.Return) for node in closed_branch.body))
        for call in ast.walk(closed_branch):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if not isinstance(call.func.value, ast.Name) or call.func.value.id != 'log':
                continue
            if call.func.attr not in ('debug', 'info', 'warning', 'error', 'critical', 'exception'):
                continue
            for argument in call.args:
                self.assertFalse(any(isinstance(node, ast.Name) and node.id == 'results'
                                     for node in ast.walk(argument)),
                                 f'{name}:{call.lineno} logs the late provider results payload')

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
