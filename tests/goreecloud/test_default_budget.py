import unittest
import test_runtime_smoke as smoke
from searx.extended_types import sxng_request
from searx.webadapter import get_search_query_from_webapp

class DefaultBudgetTest(unittest.TestCase):
    def test_general_fits_fanout_cap(self):
        with smoke.app.test_request_context('/search', method='POST', data={'q':'sample'}):
            smoke.app.preprocess_request()
            query = get_search_query_from_webapp(sxng_request.preferences, sxng_request.form)[0]
            self.assertLessEqual(len({r.name for r in query.engineref_list}), 32)
