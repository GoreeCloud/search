"""Offline source-level regression gate for opt-in Pexels credentials."""
import ast
from pathlib import Path
import unittest

ENGINE = Path(__file__).resolve().parents[2] / "searx" / "engines" / "pexels.py"

class PexelsCredentialSafety(unittest.TestCase):
    def test_no_bundled_api_key(self):
        module = ast.parse(ENGINE.read_text(encoding="utf-8"))
        assignments = [
            node.value for node in module.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "api_key"
                    for target in node.targets)
        ]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(ast.literal_eval(assignments[0]), "")

    def test_missing_key_fails_closed(self):
        source = ENGINE.read_text(encoding="utf-8")
        self.assertIn("if not api_key:", source)
        self.assertIn('raise SearxEngineAPIException(', source)
        self.assertIn('logger = logging.getLogger(__name__)', source)

if __name__ == "__main__":
    unittest.main()
