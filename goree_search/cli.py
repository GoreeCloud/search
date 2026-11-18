"""CLI for queue initialization, explicit seeding, crawls and local serving."""
from __future__ import annotations

import argparse

from .crawler import crawl
from .frontier import Frontier
from .security import normalize_url


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="goree-search")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create PostgreSQL frontier tables")
    seed = sub.add_parser("seed", help="Enqueue curated public URLs")
    seed.add_argument("urls", nargs="+")
    run = sub.add_parser("crawl", help="Fetch queued or explicit public URLs")
    run.add_argument("--url", action="append", default=[], help="One approved seed URL")
    run.add_argument("--claim", type=int, default=20)
    run.add_argument("--max-pages", type=int, default=200)
    args = parser.parse_args(argv)
    if args.command == "init":
        Frontier().init()
    elif args.command == "seed":
        frontier = Frontier()
        frontier.enqueue(args.urls)
    elif args.command == "crawl":
        if args.url:
            urls = [normalize_url(u) for u in args.url]
            crawl(urls, max_pages=args.max_pages)
        else:
            frontier = Frontier()
            urls = frontier.claim(limit=args.claim)
            if urls:
                crawl(urls, frontier=frontier, max_pages=args.max_pages)
            else:
                print("No due URLs in frontier")
    else:
        parser.error("Unknown command")
