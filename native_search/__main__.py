# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded CLI: no background fetches or automatic crawl seeds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import run_loopback
from .crawler import Crawler, CrawlPlan
from .index import SearchIndex


def main() -> None:
    parser = argparse.ArgumentParser(prog='python -m native_search')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest = commands.add_parser('import-json', help='Import explicitly approved document fixtures')
    ingest.add_argument('--db', required=True)
    ingest.add_argument('--input', required=True)
    remove = commands.add_parser('remove-url', help='Remove a URL and its full-text index entries')
    remove.add_argument('--db', required=True)
    remove.add_argument('--url', required=True)
    serve = commands.add_parser('serve', help='Serve the native index on 127.0.0.1 only')
    serve.add_argument('--db', required=True)
    serve.add_argument('--port', type=int, default=8789)
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
    elif args.command == 'serve':
        with SearchIndex(args.db) as index:
            run_loopback(index, port=args.port)


if __name__ == '__main__':
    main()
