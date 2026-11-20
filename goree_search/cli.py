"""Operator CLI for durable seeding, guarded crawling and intentional removals."""
from __future__ import annotations

import argparse

from .crawler import crawl
from .frontier import Frontier, _https_url
from .indexing import delete_document, make_client
from .sitemaps import read_sitemap_file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="goree-search")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize/additively migrate PostgreSQL frontier tables")
    seed = sub.add_parser("seed", help="Enqueue curated HTTPS URLs")
    seed.add_argument("urls", nargs="+")
    sitemap = sub.add_parser("import-sitemap", help="Import a bounded local HTTPS URLSET XML file")
    sitemap.add_argument("file_path")
    sitemap.add_argument("--host", required=True, help="Exact approved public hostname")
    run = sub.add_parser("crawl", help="Fetch claimed URLs via localhost pinned-IP HTTPS proxy")
    run.add_argument("--url", action="append", default=[], help="One curated HTTPS seed URL")
    run.add_argument("--claim", type=int, default=20)
    run.add_argument("--host-delay", type=int, default=5, help="Global minimum seconds between host claims")
    run.add_argument("--max-pages", type=int, default=50)
    removal = sub.add_parser("remove", help="Operator exclusion and indexed-document purge")
    removal.add_argument("url", type=_https_url)
    removal.add_argument("--reason", required=True, help="Verified operator decision; 3-300 characters")
    args = parser.parse_args(argv)

    if args.command == "init":
        Frontier().init()
    elif args.command == "seed":
        count = Frontier().enqueue(args.urls)
        print(f"New URLs queued: {count}")
    elif args.command == "import-sitemap":
        urls = read_sitemap_file(args.file_path, host=args.host)
        count = Frontier().enqueue(urls)
        print(f"Sitemap URLs queued: {count}")
    elif args.command == "crawl":
        if args.url:
            urls = [_https_url(url) for url in args.url]
            crawl(urls, max_pages=args.max_pages)
        else:
            frontier = Frontier()
            urls = frontier.claim(limit=args.claim, delay_seconds=args.host_delay)
            if urls:
                crawl(urls, frontier=frontier, max_pages=args.max_pages)
            else:
                print("No due HTTPS URLs under host scheduling policy")
    elif args.command == "remove":
        # Stop crawl workers first for a strong deletion guarantee. The exclusion
        # is committed before the index delete; retry is idempotent if unavailable.
        frontier = Frontier()
        frontier.exclude_url(args.url, args.reason)
        delete_document(make_client(), args.url)
        print("Exclusion stored and OpenSearch deletion acknowledged")
    else:
        parser.error("Unknown command")
