"""CLI input flow is mocked; never reaches a real database or network."""
from unittest.mock import MagicMock

from goree_search.cli import main


def test_offline_sitemap_import_enqueues_only_checked_urls(monkeypatch, capsys):
    f = MagicMock()
    f.enqueue.return_value = 2
    monkeypatch.setattr("goree_search.cli.Frontier", lambda: f)
    parser = MagicMock(return_value=["https://example.org/a", "https://example.org/b"])
    monkeypatch.setattr("goree_search.cli.read_sitemap_file", parser)
    main(["import-sitemap", "./allowed.xml", "--host", "example.org"])
    parser.assert_called_once_with("./allowed.xml", host="example.org")
    f.enqueue.assert_called_once_with(["https://example.org/a", "https://example.org/b"])
    assert "Sitemap URLs queued: 2" in capsys.readouterr().out
