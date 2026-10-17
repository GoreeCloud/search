# SPDX-License-Identifier: AGPL-3.0-or-later
"""Image Search fork integration contract, independent from the private web profile."""
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
IMAGE_PROFILE = ROOT / "configs/goreecloud/image-search-settings.yml"
WEB_PROFILE = ROOT / "configs/goreecloud/settings.yml"


def test_image_profile_has_separate_bounded_image_engines():
    image = yaml.safe_load(IMAGE_PROFILE.read_text(encoding="utf-8"))
    web = yaml.safe_load(WEB_PROFILE.read_text(encoding="utf-8"))
    enabled = image["use_default_settings"]["engines"]["keep_only"]
    assert enabled == ["brave.images", "bing images", "duckduckgo images"]
    assert web["use_default_settings"]["engines"]["keep_only"] == ["brave", "startpage"]
    assert image["search"]["formats"] == ["html", "json"]
    assert "images" in image["categories_as_tabs"]
    assert "general" not in image["categories_as_tabs"]


def test_image_profile_is_private_until_release_hardening():
    image = yaml.safe_load(IMAGE_PROFILE.read_text(encoding="utf-8"))
    assert image["server"]["bind_address"] == "127.0.0.1"
    assert image["server"]["public_instance"] is False
    assert image["server"]["method"] == "POST"
    assert image["server"]["image_proxy"] is True
    assert image["general"]["enable_metrics"] is False
    runner = (ROOT / "scripts/run-images-private.sh").read_text(encoding="utf-8")
    assert "SEARXNG_SECRET" in runner and "SEARXNG_SETTINGS_PATH" in runner
    assert "127.0.0.1" in runner
