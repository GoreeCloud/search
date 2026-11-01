"""Offline regression: no bundled YouTube credential or unqualified pagination."""
import ast
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / "searx" / "engines" / "youtube_noapi.py"

class YouTubeCredentialGuard(unittest.TestCase):
    def test_no_embedded_google_key(self):
        source = PATH.read_text(encoding="utf-8")
        self.assertNotIn("AIza", source)
        module = ast.parse(source)
        self.assertTrue(any(isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == "paging"
                                    for target in node.targets)
                            and ast.literal_eval(node.value) is False
                            for node in module.body))

    def test_next_page_refuses_unqualified_api(self):
        source = PATH.read_text(encoding="utf-8")
        self.assertIn("if next_page_url is None:", source)
        self.assertIn("raise SearxEngineAPIException", source)
        self.assertIn("next_page_url = None", source)

if __name__ == "__main__":
    unittest.main()
