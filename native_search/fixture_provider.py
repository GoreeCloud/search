# SPDX-License-Identifier: AGPL-3.0-or-later
"""Explicit operator-supplied, strictly bounded OFFLINE fusion preview data.

No network providers or search credentials are present. A fixture returns the
same synthetic cards for every query; this must never be mistaken for an
upstream result or production search quality evidence.
"""

from __future__ import annotations

import json
import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit

from .dispatch import ProviderBinding, ProviderRights
from .fusion import SourceResult, SUPPORTED_CATEGORIES, fuse_results


MAX_FIXTURE_BYTES = 131_072
_SOURCE_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')


def _public_fixture_link(value: object) -> bool:
    # These links are not fetched by the fixture adapter, but still appear in
    # user-facing native results. Keep previews away from localhost/intranet.
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname
        if (url.scheme != 'https' or not host or url.username is not None
                or url.password is not None or url.port not in (None, 443)):
            return False
        if host in ('localhost', 'localdomain') or host.endswith(
                ('.localhost', '.local', '.internal', '.test')):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return True
    except ValueError:
        return False


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    fields: dict = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError('Duplicate synthetic fixture field')
        fields[key] = value
    return fields


def _reject_nonfinite(_value: str):
    raise ValueError('Nonfinite synthetic fixture value')


def load_synthetic_fixture(path: str | Path) -> tuple[ProviderBinding, ...]:
    """Load local cards only after an operator opts in to the fixture mode.

    A normal service startup never reads a fixture and therefore has no
    installed provider adapter or external traffic route.
    """
    location = Path(path)
    if not location.is_absolute() or location.is_symlink() or not location.is_file():
        raise ValueError('Synthetic fixture must be an existing absolute regular file')
    if not 0 < location.stat().st_size <= MAX_FIXTURE_BYTES:
        raise ValueError('Synthetic fixture exceeds bounded file size')
    try:
        payload = json.loads(location.read_bytes(), object_pairs_hook=_unique_object,
                             parse_constant=_reject_nonfinite)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid UTF-8 synthetic fixture JSON') from error
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'sources'} or type(payload['schema_version']) is not int or payload['schema_version'] != 1:
        raise ValueError('Invalid synthetic fixture envelope')
    sources = payload['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
        raise ValueError('Invalid synthetic fixture source count')

    bindings: list[ProviderBinding] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'source', 'results'}:
            raise ValueError('Invalid synthetic source shape')
        name, records = source['source'], source['results']
        if (not isinstance(name, str) or not _SOURCE_ID.fullmatch(name) or name in seen
                or not isinstance(records, list) or not 1 <= len(records) <= 40):
            raise ValueError('Invalid or duplicated synthetic source')
        seen.add(name)
        cards: list[SourceResult] = []
        categories: set[str] = set()
        for item in records:
            if (not isinstance(item, dict) or not {'category', 'rank', 'url', 'title'} <= set(item)
                    or set(item) - {'category', 'rank', 'url', 'title', 'description', 'media_url'}):
                raise ValueError('Invalid synthetic card shape')
            category = item['category']
            if category not in SUPPORTED_CATEGORIES:
                raise ValueError('Unsupported synthetic category')
            card = SourceResult(name, category, item['rank'], item['url'], item['title'],
                                item.get('description', ''), item.get('media_url'))
            try:
                if (not _public_fixture_link(card.url)
                        or (card.media_url is not None
                            and not _public_fixture_link(card.media_url))):
                    raise ValueError('Nonpublic synthetic result URL')
                if not fuse_results((card,), category=category, limit=1):
                    raise ValueError('Unpublishable synthetic card')
            except (TypeError, ValueError) as error:
                raise ValueError('Invalid synthetic card') from error
            cards.append(card)
            categories.add(category)

        snapshot = tuple(cards)

        async def search(_query: str, category: str, limit: int,
                         *, data: tuple[SourceResult, ...] = snapshot):
            return [card for card in data if card.category == category][:limit]

        bindings.append(ProviderBinding(name, search, ProviderRights(
            frozenset(categories), True, True, True,
            'operator-provided-offline-synthetic-fixture', 'synthetic_fixture')))
    return tuple(bindings)
