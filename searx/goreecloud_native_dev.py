# SPDX-License-Identifier: AGPL-3.0-or-later
"""Opt-in, read-only native Search browser adapter. Disabled unless explicitly enabled.

This path never dispatches a federated engine, changes browser preferences,
or reads query parameters from a URL. The approved index is local only.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from flask import Response
from searx import settings
from searx.goreecloud_policy import safe_primary_result_url


def native_dev_available() -> bool:
    if not settings['goreecloud']['private_search']:
        return False
    if os.environ.get('GOREECLOUD_NATIVE_SOURCE_ENABLED') != '1':
        return False
    value = os.environ.get('GOREECLOUD_NATIVE_INDEX_PATH', '')
    if not value or len(value) > 1024:
        return False
    path = Path(value)
    return path.is_absolute() and not path.is_symlink() and path.is_file()


def serve_native_development(request, render):
    if request.method != 'POST' or request.args:
        return Response('Native Search requires private POST without URL parameters.', status=405)
    if request.mimetype != 'application/x-www-form-urlencoded':
        return Response('Form POST is required.', status=415)
    if request.form.get('native_source') != 'goreecloud-native-index':
        return Response('Native Search requires explicit source selection.', status=422)
    if any(request.form.get('category_' + name) for name in ('images', 'videos', 'news')):
        return Response('Only Web documents are indexed in Development.', status=422)
    if request.content_length is not None and request.content_length > 65536:
        return Response('Native Search request exceeds the size limit.', status=413)
    query = request.form.get('q')
    try:
        from native_search.readonly import read_native_results
        hits = read_native_results(os.environ['GOREECLOUD_NATIVE_INDEX_PATH'], query, limit=10)
    except (ValueError, TypeError, UnicodeError):
        return Response('Invalid native search query.', status=422)
    except (OSError, sqlite3.Error):
        return Response('Native index is temporarily unavailable.', status=503)
    # Only render safe, approved repository destinations.
    results = []
    for hit in hits:
        if not safe_primary_result_url(hit.url):
            continue
        parsed = urlsplit(hit.url)
        if parsed.scheme == 'https' and parsed.hostname == 'github.com' and parsed.path.startswith('/GoreeCloud/search/blob/'):
            results.append(hit)
    response = Response(render('goreecloud_native_results.html', native_query=query,
                               native_results=results, selected_categories=['general']),
                        mimetype='text/html')
    response.headers['Cache-Control'] = 'private, no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response
