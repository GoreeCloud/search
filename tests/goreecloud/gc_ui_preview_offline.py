"""Private preflight test harness: load the actual engines without network startup.

This is deliberately confined to tests: both Flask rendering and form parsing
run as shipped, while no SearXNG HTTP network/client initialization is allowed.
"""

_TEST_CACHE_DIRECTORY = None


def offline_preview_app():
    global _TEST_CACHE_DIRECTORY

    import atexit
    import os
    from pathlib import Path
    import tempfile
    from unittest.mock import patch

    repo = Path(__file__).resolve().parents[2]
    os.environ.setdefault("SEARXNG_SETTINGS_PATH", str(repo / "configs/goreecloud/settings.yml"))
    os.environ.setdefault("SEARXNG_SECRET", "goreecloud-preview-offline-fixture-only-secret")
    if _TEST_CACHE_DIRECTORY is None:
        _TEST_CACHE_DIRECTORY = tempfile.TemporaryDirectory(
            prefix="gc-ui-preview-offline-", dir=repo.parent
        )
    tempfile.tempdir = _TEST_CACHE_DIRECTORY.name  # prevent SQLite test cache from entering the checkout

    import searx
    import searx.search
    from searx.engines import load_engines
    from searx.network.network import done as network_done

    # No network clients are initialized; its atexit loop cleanup would block
    # in the restricted offline browser/Flask test environment.
    atexit.unregister(network_done)
    load_engines(searx.settings["engines"])
    with patch("searx.search.initialize"):
        from searx.webapp import app
    return app
