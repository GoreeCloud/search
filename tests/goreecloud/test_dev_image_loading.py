"""Image-gallery loading and compact Development source UX regressions.

Visual/browser screenshots still require device validation. These contracts
keep thumbnail requests within the signed same-origin proxy and avoid
automatic Tor relay floods of offscreen images.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
THEMES = ROOT / 'searx/static/themes/simple'


class GoreeCloudImageUXTests(unittest.TestCase):
    def test_proxy_is_preserved_and_initial_previews_have_priority(self):
        template = (ROOT / 'searx/templates/simple/result_templates/images.html').read_text()
        self.assertIn('image_proxify(result.thumbnail_src)', template)
        self.assertIn('image_proxify(result.img_src)', template)
        self.assertIn('index|default(99) <= 12', template)
        self.assertIn('decoding="async"', template)
        self.assertIn('lazy{% endif %}', template)

    def test_manual_load_all_is_limited_to_image_results(self):
        template = (ROOT / 'searx/templates/simple/results.html').read_text()
        self.assertIn("preferences.get_value('image_proxy') and 'images' in selected_categories and results|length > 12", template)
        self.assertIn('id="goreecloud-image-load-all"', template)
        self.assertIn('More previews load as you scroll.', template)
        js = (THEMES / 'goreecloud-image-previews.js').read_text()
        self.assertIn('url.origin === location.origin', js)
        self.assertIn('url.pathname === "/image_proxy"', js)
        self.assertIn('url.searchParams.get("h")', js)
        self.assertIn('image.getAttribute("src")', js)
        self.assertIn('image.hasAttribute("srcset")', js)
        self.assertIn('active < 4', js)
        self.assertIn('button.addEventListener("click"', js)
        self.assertNotIn('fetch(', js)

    def test_gallery_accessibility_and_homepage_native_ux(self):
        gallery = (THEMES / 'goreecloud-settings-categories.css').read_text()
        self.assertIn('goreecloud-thumbnail-unavailable', gallery)
        self.assertIn('Preview unavailable', gallery)
        template = (ROOT / 'searx/templates/simple/simple_search.html').read_text()
        self.assertIn('Native index <span class="goreecloud-native-dev-label">Dev</span>', template)
        self.assertIn('name="native_source" value="goreecloud-native-index"', template)
        self.assertIn('formmethod="post"', template)
        self.assertIn('formaction="{{ url_for(\'goreecloud_native_search\') }}"', template)
        self.assertNotIn('Search native index <span>(Development', template)


if __name__ == '__main__':
    unittest.main()
