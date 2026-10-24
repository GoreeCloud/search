# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded CLI: no background fetches or automatic crawl seeds."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

from .api import run_loopback
from .crawler import Crawler, CrawlPlan
from .index import SearchIndex
from .repo_corpus import import_approved_repo_docs, load_approved_manifest


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    values: dict = {}
    for key, value in pairs:
        if key in values:
            raise ValueError('Duplicate operator image manifest field')
        values[key] = value
    return values


def _reject_nonfinite(_value: str):
    raise ValueError('Nonfinite operator image manifest value')


def load_approved_image_manifest(path: str | Path) -> list[tuple[str, str, str, str, str]]:
    """Read ONLY a bounded, explicit operator manifest; never visit its URLs."""
    location = Path(path)
    if (not location.is_absolute() or location.is_symlink()
            or not location.is_file() or not 0 < location.stat().st_size <= 262_144):
        raise ValueError('Operator image manifest must be a bounded local file')
    try:
        payload = json.loads(location.read_bytes().decode('utf-8', errors='strict'),
                             object_pairs_hook=_unique_fields,
                             parse_constant=_reject_nonfinite)
    except (UnicodeError, ValueError) as error:
        raise ValueError('Invalid UTF-8 operator image manifest') from error
    if (not isinstance(payload, dict) or set(payload) != {'schema_version', 'images'}
            or type(payload['schema_version']) is not int or payload['schema_version'] != 1
            or not isinstance(payload['images'], list)
            or not 1 <= len(payload['images']) <= 100):
        raise ValueError('Expected v1 approved Images metadata list')
    batch: list[tuple[str, str, str, str, str]] = []
    seen: set[str] = set()
    required = {'page_url', 'media_url', 'title', 'description', 'rights_evidence'}
    for row in payload['images']:
        if (not isinstance(row, dict) or set(row) != required
                or not all(isinstance(row[key], str) for key in required)
                or row['media_url'] in seen):
            raise ValueError('Invalid or duplicate approved image metadata')
        seen.add(row['media_url'])
        batch.append(tuple(row[key] for key in (
            'page_url', 'media_url', 'title', 'description', 'rights_evidence')))
    return batch


def main() -> None:
    parser = argparse.ArgumentParser(prog='python -m native_search')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest = commands.add_parser('import-json', help='Import explicitly approved document fixtures')
    ingest.add_argument('--db', required=True)
    ingest.add_argument('--input', required=True)
    images = commands.add_parser(
        'import-images-json', help='Import operator-approved LOCAL image metadata (no fetch)')
    images.add_argument('--db', required=True)
    images.add_argument('--input', required=True, type=Path)
    takedown = commands.add_parser(
        'remove-image', help='Remove one owned Images media URL and its FTS entries (no fetch)')
    takedown.add_argument('--db', required=True, type=Path)
    takedown.add_argument('--media-url', required=True)
    approved = commands.add_parser('import-approved-repo')
    approved.add_argument('--db', required=True)
    approved.add_argument('--repo-root', required=True)
    approved.add_argument('--manifest', required=True)
    approved.add_argument('--revision', required=True)
    remove = commands.add_parser('remove-url', help='Remove a URL and its full-text index entries')
    remove.add_argument('--db', required=True)
    remove.add_argument('--url', required=True)
    serve = commands.add_parser('serve', help='Serve the native index on 127.0.0.1 only')
    serve.add_argument('--db', required=True)
    serve.add_argument('--port', type=int, default=8789)
    serve.add_argument('--fusion-fixture', type=Path,
                       help='Explicit offline synthetic fusion preview (never live provider results)')
    crawl = commands.add_parser('crawl', help='Explicitly enable bounded, policy-respecting HTTPS crawling')
    crawl.add_argument('--db', required=True)
    crawl.add_argument('--allow-network', action='store_true', required=True)
    crawl.add_argument('--allow-host', action='append', required=True)
    crawl.add_argument('--seed', action='append', required=True)
    crawl.add_argument('--max-pages', type=int, default=5)
    crawl.add_argument('--max-depth', type=int, default=1)
    args = parser.parse_args()
    if args.command == 'crawl':
        if not args.allow_network:
            parser.error('Networking is disabled by default: pass --allow-network explicitly')
        plan = CrawlPlan(allowed_hosts=frozenset(args.allow_host),
                         max_pages=args.max_pages, max_depth=args.max_depth)
        with SearchIndex(args.db) as index:
            print(json.dumps(Crawler(index, plan).crawl(args.seed)))
    elif args.command == 'import-approved-repo':
        paths = load_approved_manifest(args.manifest)
        with SearchIndex(args.db) as index:
            print(json.dumps(import_approved_repo_docs(index, args.repo_root, revision=args.revision,
                                                approved_paths=paths)))
    elif args.command == 'remove-url':
        with SearchIndex(args.db) as index:
            print(json.dumps({'removed': index.remove(args.url)}))
    elif args.command == 'import-json':
        content = Path(args.input).read_text(encoding='utf-8')
        if len(content) > 2_000_000:
            parser.error('Input fixture exceeds the import budget')
        documents = json.loads(content)
        if not isinstance(documents, list) or len(documents) > 100:
            parser.error('Input must be a list of up to 100 approved documents')
        with SearchIndex(args.db) as index:
            for doc in documents:
                index.add(url=doc['url'], title=doc['title'], body=doc['body'])
            print(json.dumps({'indexed': index.count()}))
    elif args.command == 'import-images-json':
        try:
            approved_images = load_approved_image_manifest(args.input)
            with SearchIndex(args.db) as index:
                count = index.add_images(approved_images)
                print(json.dumps({'images_imported': count, 'owned_images': index.count_images()}))
        except (OSError, TypeError, ValueError) as error:
            # Do not print image URLs or rights references from rejected data.
            parser.error(str(error))
    elif args.command == 'remove-image':
        # A misspelled database path must never create a new empty index and
        # falsely appear to have completed a rights takedown.
        if (not args.db.is_file() or args.db.is_symlink()
                or not 0 < len(args.media_url) <= 2000
                or any(ord(char) < 33 or ord(char) == 127 for char in args.media_url)):
            parser.error('Existing owned index and bounded media identity required')
        # Likewise, never bootstrap native-search tables inside an unrelated
        # SQLite database just because the operator supplied a valid path.
        probe_uri = 'file:' + quote(str(args.db.absolute()), safe='/') + '?mode=ro'
        try:
            probe = sqlite3.connect(probe_uri, uri=True)
            try:
                names = {row[0] for row in probe.execute('''
                  SELECT name FROM sqlite_master WHERE type IN ('table', 'view')
                    AND name IN ('pages', 'pages_fts', 'images', 'images_fts')
                ''')}
            finally:
                probe.close()
        except sqlite3.Error:
            parser.error('Unable to inspect existing owned Images index')
        if names != {'pages', 'pages_fts', 'images', 'images_fts'}:
            parser.error('An existing GoreeCloud Images index is required')
        with SearchIndex(args.db) as index:
            removed = index.remove_image(args.media_url)
            print(json.dumps({'removed': removed, 'owned_images': index.count_images()}))
    elif args.command == 'serve':
        from .fixture_provider import load_synthetic_fixture

        providers = load_synthetic_fixture(args.fusion_fixture) if args.fusion_fixture else ()
        with SearchIndex(args.db) as index:
            run_loopback(index, port=args.port, fusion_providers=providers,
                         allow_synthetic_fixtures=bool(args.fusion_fixture))


if __name__ == '__main__':
    main()
