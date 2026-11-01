#!/usr/bin/env python3
"""Real Granian socket smoke for private Search; no search-provider requests.

Starts a disposable local development server with a generated secret, checks
the *actual* listening address and the index response, then kills the entire
owned process group. This does not certify reverse proxy or public ingress.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def main() -> None:
    granian = Path(sys.executable).parent / 'granian'
    if not granian.is_file():
        raise RuntimeError('granian==2.8.4 is required for the socket smoke')
    if shutil.which('ss') is None:
        raise RuntimeError('ss command required to verify the actual listening address')

    port = free_loopback_port()
    env = dict(os.environ)
    env.update({
        'SEARXNG_SETTINGS_PATH': str(ROOT / 'configs/goreecloud/settings.yml'),
        'SEARXNG_SECRET': secrets.token_hex(32),
        'SEARXNG_PUBLIC_INSTANCE': 'false',
        'SEARXNG_BIND_ADDRESS': '127.0.0.1',
        'SEARXNG_DEBUG': 'false',
        'GRANIAN_RELOAD': 'false',
        'GRANIAN_HOST': '127.0.0.1',
        'GRANIAN_PORT': str(port),
        'GRANIAN_INTERFACE': 'wsgi',
        'GRANIAN_WORKERS': '1',
        'GRANIAN_BLOCKING_THREADS': '4',
    })
    opener = build_opener(ProxyHandler({}))
    with tempfile.TemporaryFile(mode='w+t') as log:
        child = subprocess.Popen(
            [str(granian), 'searx.webapp:app'], cwd=ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 30
            last_error = 'server did not start'
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError('Granian exited before its local listener was ready')
                try:
                    with opener.open(
                        Request(f'http://127.0.0.1:{port}/', headers={'Host': f'127.0.0.1:{port}'}),
                        timeout=2,
                    ) as response:
                        body = response.read(120_000)
                        assert response.status == 200
                        assert b'GoreeCloud Search' in body
                        assert 'no-store' in response.headers.get('Cache-Control', '')
                    break
                except (OSError, URLError, AssertionError) as exc:
                    last_error = type(exc).__name__
                    time.sleep(0.35)
            else:
                raise RuntimeError('Granian home page failed local health check: ' + last_error)

            status = subprocess.run(
                ['ss', '-H', '-ltn', f'( sport = :{port} )'],
                text=True, capture_output=True, check=True, timeout=5,
            )
            listeners = [line.split()[3] for line in status.stdout.splitlines()
                         if len(line.split()) >= 4]
            expected = f'127.0.0.1:{port}'
            if not listeners or any(listener != expected for listener in listeners):
                raise RuntimeError('Non-loopback, missing, or unexpected listener address')
            print('PASS: real Granian private Search listener is loopback-only; home is uncached')
            print('PASS: no provider search request sent')
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=7)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
            print('PASS: disposable Granian process group terminated')


if __name__ == '__main__':
    main()
