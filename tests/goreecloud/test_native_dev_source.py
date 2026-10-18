"""Native Web source: explicit choice, private POST, no fallback."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_runtime_smoke as smoke
from native_search.index import SearchIndex

class NativeSourceTests(unittest.TestCase):
    headers = {'X-Real-IP':'127.0.0.1'}

    def test_off_by_default_and_explicit_approved_results(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory)/'native.db')
            with SearchIndex(db) as index:
                index.add(url='https://github.com/GoreeCloud/search/blob/'+'a'*40+
                          '/docs/goreecloud/ROADMAP.md', title='Native <script> Index',
                          body='Approved local GoreeCloud document search.')
            with patch.dict(os.environ, {'GOREECLOUD_NATIVE_SOURCE_ENABLED':'0',
                                         'GOREECLOUD_NATIVE_INDEX_PATH':db}):
                with smoke.app.test_client() as client:
                    self.assertNotIn(b'Search native index',client.get('/',headers=self.headers).data)
                    self.assertEqual(404, client.post('/native-search', data={
                        'q':'GoreeCloud','native_source':'goreecloud-native-index'},
                        headers=self.headers).status_code)
            with patch.dict(os.environ, {'GOREECLOUD_NATIVE_SOURCE_ENABLED':'1',
                                         'GOREECLOUD_NATIVE_INDEX_PATH':db}):
                with smoke.app.test_client() as client, patch(
                    'searx.search.SearchWithPlugins',side_effect=AssertionError('Provider dispatch')):
                    self.assertIn(b'Search native index',client.get('/',headers=self.headers).data)
                    response=client.post('/native-search',data={
                        'q':'GoreeCloud document', 'native_source':'goreecloud-native-index'
                    },headers=self.headers)
                    self.assertEqual(200,response.status_code)
                    self.assertIn(b'Approved local GoreeCloud',response.data)
                    self.assertIn(b'&lt;script&gt;',response.data)
                    self.assertIn('no-store',response.headers['Cache-Control'])
                    self.assertNotIn('Set-Cookie',response.headers)
                    self.assertEqual(405,client.get('/native-search',headers=self.headers).status_code)
                    self.assertEqual(422,client.post('/native-search',data={
                        'q':'GoreeCloud'},headers=self.headers).status_code)
                    self.assertEqual(405,client.post('/native-search?q=leak',data={
                        'q':'GoreeCloud','native_source':'goreecloud-native-index'},
                        headers=self.headers).status_code)
                    self.assertEqual(403,client.post('/native-search',data={
                        'q':'GoreeCloud','native_source':'goreecloud-native-index'},
                        headers={**self.headers,'Origin':'https://evil.example',
                                 'Sec-Fetch-Site':'cross-site'}).status_code)
            with SearchIndex(db) as index:
                self.assertEqual(1,index.count())
