# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sealed, local-only adapter for GoreeCloud's owned SQLite FTS5 index.

This adapter cannot fetch a network resource. An upstream network adapter must
never acquire first-party admission merely by claiming an `owned_index` right.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fusion import SourceResult
from .index import SearchIndex


OWNED_INDEX_SOURCE = 'goreecloud_index'
OWNED_INDEX_EVIDENCE = 'goreecloud-local-sqlite-fts5'


@dataclass(frozen=True)
class OwnedIndexAdapter:
    index: SearchIndex

    def __post_init__(self) -> None:
        if type(self.index) is not SearchIndex:
            raise TypeError('Owned source must use the native SQLite index')

    async def __call__(self, query: str, category: str, limit: int) -> list[SourceResult]:
        # Only Web has an owned FTS index. Images and other categories must
        # not inherit a fictitious source-success or a borrowed provider.
        if category != 'web':
            return []
        hits = self.index.search(query, limit=min(limit, 20))
        return [SourceResult(OWNED_INDEX_SOURCE, 'web', n, hit.url, hit.title,
                             hit.excerpt) for n, hit in enumerate(hits, 1)]
