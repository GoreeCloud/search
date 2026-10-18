# SPDX-License-Identifier: AGPL-3.0-or-later
import http.client
import json
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

from native_search.api import make_handler
from native_search.index import SearchIndex


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SearchIndex(Path(self.temp.name) / 'api.sqlite')
        self.store.add(url='https://example.org/guide', title='GoreeCloud native Search',
                       body='Privacy-first native indexing with full text search')
        self.server = HTTPServer(('127.0.0.1', 0), make_handler(self.store))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(timeout=3)
        self.server.server_close()
        self.store.close()
        self.temp.cleanup()

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        conn.request(method, path, body, headers or {})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        code = resp.status
        header = dict(resp.getheaders())
        conn.close()
        return code, header, data

    def test_private_post_search_returns_only_owned_index_results(self):
        status, head, body = self.req('POST', '/v1/search',
                                     json.dumps({'query':'native search'}),
                                     {'Content-Type':'application/json'})
        self.assertEqual(200, status)
        self.assertEqual('goreecloud-native-index', body['source'])
        self.assertEqual(1, body['total_displayed'])
        self.assertEqual('https://example.org/guide', body['results'][0]['url'])
        self.assertNotIn('query', body)
        self.assertEqual('no-store', head['Cache-Control'])
        self.assertEqual('no-referrer', head['Referrer-Policy'])

    def test_reject_get_query_unknown_fields_origin_and_oversized(self):
        self.assertEqual(405, self.req('GET', '/v1/search?q=private')[0])
        self.assertEqual(405, self.req('GET', '/v1/search')[0])
        self.assertEqual(403, self.req('POST','/v1/search','{}',
                                    {'Content-Type':'application/json','Origin':'https://untrusted.org'})[0])
        self.assertEqual(422, self.req('POST','/v1/search','{"query":"ok","secret":true}',
                                    {'Content-Type':'application/json'})[0])
        self.assertEqual(422, self.req('POST','/v1/search','x' * 5000,
                                    {'Content-Type':'application/json'})[0])

    def test_rejects_dns_rebinding_hosts_for_search_and_health(self):
        hostnames = ('evil.example.org', 'localhost:1', 'user@127.0.0.1',
                     '127.0.0.1.evil.test')
        for host in hostnames:
            with self.subTest(host=host):
                self.assertEqual(403, self.req('GET', '/healthz',
                    headers={'Host': host})[0])
                self.assertEqual(403, self.req('POST', '/v1/search',
                    json.dumps({'query': 'private marker'}),
                    {'Host': host, 'Content-Type': 'application/json'})[0])

    def test_health_is_low_information_and_api_has_no_cors(self):
        code, head, data = self.req('GET','/healthz')
        self.assertEqual(200, code)
        self.assertEqual('native-development',data['mode'])
        self.assertNotIn('Access-Control-Allow-Origin',head)


if __name__ == '__main__':
    unittest.main()
