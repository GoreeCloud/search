# SPDX-License-Identifier: AGPL-3.0-or-later
"""Loopback HTTP and packaging acceptance of the OFFLINE native fusion path."""

import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer

from native_search.api import NativeHTTPServer, make_handler
from native_search.fixture_provider import load_synthetic_fixture
from native_search.index import SearchIndex
from scripts.build_native_linux_service import build_bundle


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA = 'a' * 40


def cards():
    return {'schema_version': 1, 'sources': [
        {'source': 'alpha', 'results': [
            {'category': 'web', 'rank': 2, 'url': 'https://example.org/a',
             'title': 'Alpha result'},
            {'category': 'images', 'rank': 1, 'url': 'https://example.org/image',
             'media_url': 'https://cdn.example.org/image.jpg', 'title': 'Alpha image'},
        ]},
        {'source': 'beta', 'results': [
            {'category': 'web', 'rank': 1, 'url': 'https://EXAMPLE.org/a#same',
             'title': 'Beta result'},
        ]},
    ]}


def request(port, method, route, body=None, *, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
    try:
        connection.request(method, route, body, headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), json.loads(response.read())
    finally:
        connection.close()


class NativeFusionHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.root / 'only-synthetic-fixture.json'
        self.fixture.write_text(json.dumps(cards()), encoding='utf-8')
        self.index = SearchIndex(self.root / 'owned.sqlite')
        self.index.add(url='https://example.org/local', title='Owned Search index',
                       body='Local source for independent index regression')
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.worker.join(timeout=3)
            self.server.server_close()
        self.index.close()

    def start(self, *, providers=(), fixtures=False, bounded=False):
        server_type = NativeHTTPServer if bounded else HTTPServer
        self.server = server_type(('127.0.0.1', 0), make_handler(
            self.index, fusion_providers=providers,
            allow_synthetic_fixtures=fixtures))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        return self.server.server_port

    def post(self, port, data, *, route='/v1/fusion', headers=None):
        return request(port, 'POST', route, json.dumps(data), headers={
            'Content-Type': 'application/json', **(headers or {})})

    def test_default_native_process_has_no_provider_calls_or_results(self):
        port = self.start()
        code, head, body = self.post(port, {'query': 'sensitive query'})
        self.assertEqual(503, code)
        self.assertNotIn('sensitive query', json.dumps(body))
        self.assertNotIn('Access-Control-Allow-Origin', head)
        self.assertEqual('no-store', head['Cache-Control'])
        self.assertEqual(405, request(port, 'GET', '/v1/fusion?q=sensitive')[0])

    def test_explicit_fixture_search_has_unified_deduped_web_and_image_results(self):
        bindings = load_synthetic_fixture(self.fixture)
        port = self.start(providers=bindings, fixtures=True)
        code, head, body = self.post(port, {'query': 'secret', 'category': 'web', 'limit': 10})
        self.assertEqual(200, code)
        self.assertEqual(1, body['schema_version'])
        self.assertEqual('synthetic_fixture_preview', body['mode'])
        self.assertEqual('ok', body['status'])
        self.assertEqual(1, body['total_displayed'])
        self.assertEqual([['alpha', 2], ['beta', 1]], body['results'][0]['source_ranks'])
        self.assertNotIn('secret', json.dumps(body))
        self.assertNotIn('Access-Control-Allow-Origin', head)
        _, _, images = self.post(port, {'query': 'different private query', 'category': 'images'})
        self.assertEqual('partial', images['status'])
        self.assertEqual('https://cdn.example.org/image.jpg', images['results'][0]['media_url'])
        self.assertEqual(['ok', 'blocked'], [p['status'] for p in images['providers']])
        code, _, local = self.post(port, {'query': 'Owned Search'}, route='/v1/search')
        self.assertEqual(200, code)
        self.assertEqual('goreecloud-native-index', local['source'])

    def test_synthetic_rights_fail_closed_without_fixture_switch(self):
        port = self.start(providers=load_synthetic_fixture(self.fixture))
        code, _, body = self.post(port, {'query': 'private'})
        self.assertEqual(200, code)
        self.assertEqual('unavailable', body['status'])
        self.assertEqual([], body['results'])
        self.assertEqual(['blocked', 'blocked'], [p['status'] for p in body['providers']])

    def test_origin_preflight_and_request_budget_validation(self):
        port = self.start(providers=load_synthetic_fixture(self.fixture), fixtures=True)
        code, head, _ = request(port, 'OPTIONS', '/v1/fusion', headers={
            'Origin': 'http://tauri.localhost',
            'Access-Control-Request-Method': 'POST'})
        self.assertEqual(405, code)
        self.assertNotIn('Access-Control-Allow-Origin', head)
        invalid = (
            ({'query': 'ok', 'providers': ['brave']}, {}),
            ({'query': 'bad\nquery'}, {}),
            ({'query': 'ok', 'category': 'maps'}, {}),
            ({'query': 'ok', 'limit': True}, {}),
            ({'query': 'ok'}, {'Transfer-Encoding': 'chunked'}),
        )
        for body, headers in invalid:
            with self.subTest(body=body, headers=headers):
                self.assertEqual(422, self.post(port, body, headers=headers)[0])
        self.assertEqual(403, self.post(port, {'query': 'ok'}, headers={
            'Origin': 'http://tauri.localhost'})[0])

    def test_incomplete_json_body_times_out_and_releases_loopback_worker(self):
        port = self.start(bounded=True)
        self.server.request_idle_timeout_seconds = 0.2
        with socket.create_connection(('127.0.0.1', port), timeout=3) as client:
            client.settimeout(3)
            client.sendall((
                'POST /v1/fusion HTTP/1.1\r\n'
                f'Host: 127.0.0.1:{port}\r\n'
                'Content-Type: application/json\r\n'
                'Content-Length: 40\r\n\r\n'
                '{"query":'
            ).encode('ascii'))
            response = client.recv(4096)
            self.assertIn(b' 408 ', response)
            self.assertNotIn(b'query', response)
        self.server.request_idle_timeout_seconds = 5.0
        self.assertEqual(200, request(port, 'GET', '/healthz')[0])

    def test_strict_fixture_rejects_unreviewed_fields_and_unpublishable_cards(self):
        invalid = [
            '{"schema_version":1,"schema_version":1,"sources":[]}',
            json.dumps({'schema_version': 1, 'sources': cards()['sources'] * 5}),
            json.dumps({'schema_version': 1, 'sources': [
                {'source': 'alpha', 'results': [
                    {'category': 'web', 'rank': 1, 'url': 'http://127.0.0.1/a',
                     'title': 'Local fixture link'}]}]}),
            json.dumps({'schema_version': 1, 'sources': [
                {'source': 'alpha', 'results': [
                    {'category': 'web', 'rank': 1, 'url': 'javascript:alert(1)',
                     'title': 'Bad'}]}]}),
            json.dumps({'schema_version': 1, 'sources': [
                {'source': 'alpha', 'results': [
                    {'category': 'web', 'rank': True, 'url': 'https://example.org/a',
                     'title': 'Bad rank'}]}]}),
        ]
        for content in invalid:
            with self.subTest(content=content[:60]):
                self.fixture.write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_synthetic_fixture(self.fixture)

    def test_linux_zipapp_candidate_runs_fusion_only_with_explicit_local_fixture(self):
        artifact = self.root / 'candidate.pyz'
        artifact.write_bytes(build_bundle(ROOT, SOURCE_SHA))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        proc = subprocess.Popen([
            sys.executable, str(artifact), '--db', str(self.root / 'owned.sqlite'),
            '--port', str(port), '--fusion-fixture', str(self.fixture),
        ], cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            response = None
            for _ in range(80):
                try:
                    response = self.post(port, {'query': 'not included in response'})
                    break
                except OSError:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
            self.assertIsNotNone(response, 'candidate ZIP service failed to serve fusion')
            self.assertEqual(200, response[0])
            self.assertEqual('synthetic_fixture_preview', response[2]['mode'])
            self.assertEqual(1, response[2]['total_displayed'])
            self.assertNotIn('not included in response', json.dumps(response[2]))
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
