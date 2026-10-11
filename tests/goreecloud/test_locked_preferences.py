import unittest
import test_runtime_smoke as smoke
from searx.extended_types import sxng_request

class LockedPrivacySettingsTests(unittest.TestCase):
    def test_private_preferences_cannot_be_weakened_by_query(self):
        params = {'method': 'GET', 'query_in_title': 'true', 'autocomplete': 'bing', 'image_proxy': 'false'}
        with smoke.app.test_request_context('/', query_string=params):
            smoke.app.preprocess_request()
            prefs = sxng_request.preferences
            self.assertEqual('POST', prefs.get_value('method'))
            self.assertFalse(prefs.get_value('query_in_title'))
            self.assertEqual('', prefs.get_value('autocomplete'))
            self.assertTrue(prefs.get_value('image_proxy'))
