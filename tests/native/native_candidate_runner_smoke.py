#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run an exact-built, uninstalled GoreeCloud-owned service over loopback.

This is a disposable Linux CI acceptance probe. It does not install or start
the systemd unit, authenticate real clients, contact providers, or deploy.
"""

from __future__ import annotations

import argparse
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

# A directly executed test script has tests/native as sys.path[0], not the
# repository root. Import only the checked-out modules at that known root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from native_search.index import SearchIndex
from scripts.build_native_linux_service import MANIFEST_NAME, SERVICE_FILES


def request(port: int, method: str, path: str, payload: bytes | None = None,
            headers: dict | None = None):
    client = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
    try:
        actual_headers = {'Host': f'127.0.0.1:{port}', **(headers or {})}
        client.request(method, path, body=payload, headers=actual_headers)
        response = client.getresponse()
        return response.status, response.headers, response.read()
    finally:
        client.close()


def verify(archive: Path, expected_sha: str) -> None:
    with ZipFile(archive) as bundle:
        required = {*SERVICE_FILES, '__main__.py', MANIFEST_NAME}
        actual = bundle.namelist()
        if len(actual) != len(required) or set(actual) != required:
            raise ValueError('candidate contains unexpected service files')
        manifest = json.loads(bundle.read(MANIFEST_NAME))
        if manifest.get('source_commit') != expected_sha:
            raise ValueError('candidate archive is not bound to the exact checkout')

    with tempfile.TemporaryDirectory(prefix='gc-search-linux-disposable-') as directory:
        scratch = Path(directory)
        database = scratch / 'index.sqlite'
        with SearchIndex(database) as index:
            index.add(url='https://example.org/approved', title='Synthetic owned fixture',
                      body='A permitted isolated GoreeCloud Search native fixture')

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]

        # The only process launched is the candidate's owned local API. Its
        # subprocess working directory is a disposable temporary directory.
        process = subprocess.Popen(
            [sys.executable, '-I', '-B', str(archive.resolve()),
             '--db', str(database), '--port', str(port)],
            cwd=scratch, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError('native candidate exited before accepting localhost')
                try:
                    health, headers, payload = request(port, 'GET', '/healthz')
                    if health == 200:
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise RuntimeError('native candidate never accepted a loopback request')

            if json.loads(payload) != {'status': 'ok', 'mode': 'native-development'}:
                raise AssertionError('health response was not the bounded development contract')
            if headers.get('Cache-Control') != 'no-store':
                raise AssertionError('native response must not be cached')

            status, _, _ = request(port, 'GET', '/v1/search')
            if status != 405:
                raise AssertionError('query-bearing GET must be rejected')
            status, _, _ = request(port, 'POST', '/v1/search', b'{"query":"fixture"}',
                                   {'Content-Type': 'application/json', 'Host': 'evil.example'})
            if status != 403:
                raise AssertionError('DNS-rebinding Host header must be rejected')
            status, _, _ = request(port, 'POST', '/v1/search', b'{"query":"fixture"}',
                                   {'Content-Type': 'application/json',
                                    'Origin': 'https://evil.example'})
            if status != 403:
                raise AssertionError('browser Origin request must be rejected')
            status, headers, raw = request(port, 'POST', '/v1/search',
                                           b'{"query":"fixture"}',
                                           {'Content-Type': 'application/json'})
            if status != 200 or headers.get('Cache-Control') != 'no-store':
                raise AssertionError('approved private POST did not complete')
            body = json.loads(raw)
            if (body.get('source') != 'goreecloud-native-index'
                    or body.get('total_displayed') != 1
                    or body['results'][0]['url'] != 'https://example.org/approved'):
                raise AssertionError('unexpected isolated owned-search result')
        finally:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
        if process.returncode not in (-15, -2, 0):
            raise RuntimeError('native candidate did not stop cleanly')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--expected-sha', required=True)
    args = parser.parse_args()
    verify(args.archive, args.expected_sha)
    print('NATIVE_LINUX_DISPOSABLE_PASS: source-pinned uninstalled loopback service; no systemd/release')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
