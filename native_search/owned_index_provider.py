# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sealed, local-only Web and Images adapters for owned SQLite FTS5 indexes.

This adapter cannot fetch a network resource. An upstream network adapter must
never acquire first-party admission merely by claiming an `owned_index` right.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fusion import SourceResult
from .index import SearchIndex


OWNED_INDEX_SOURCE = 'goreecloud_index'
OWNED_INDEX_EVIDENCE = 'goreecloud-local-sqlite-fts5'
OWNED_IMAGE_SOURCE = 'goreecloud_images'
OWNED_IMAGE_EVIDENCE = 'goreecloud-local-sqlite-images-fts5'


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


@dataclass(frozen=True)
class OwnedImageAdapter:
    """Query only explicit local image metadata; no media fetch or crawler."""

    index: SearchIndex

    def __post_init__(self) -> None:
        if type(self.index) is not SearchIndex:
            raise TypeError('Owned image source must use the native SQLite index')

    async def __call__(self, query: str, category: str, limit: int) -> list[SourceResult]:
        if category != 'images':
            return []
        hits = self.index.search_images(query, limit=min(limit, 20))
        return [SourceResult(OWNED_IMAGE_SOURCE, 'images', n,
                             hit.page_url, hit.title, hit.description,
                             hit.media_url) for n, hit in enumerate(hits, 1)]
