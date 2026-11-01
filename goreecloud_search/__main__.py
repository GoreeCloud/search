"""Local-only entry point: python -m goreecloud_search {init,import-jsonl,serve}."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .server import run_server
from .recovery import RecoveryError, inspect_catalog, snapshot_catalog
from .store import InvalidDocument, import_jsonl, initialize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GoreeCloud Search — greenfield development foundation")
    parser.add_argument("--db", type=Path, default=Path.home() / ".local/state/goreecloud/search.sqlite3")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("init", help="Create a local, private FTS index")
    ingest = sub.add_parser("import-jsonl", help="Replace local documents from approved JSON Lines")
    ingest.add_argument("--input", type=Path, required=True)
    serve = sub.add_parser("serve", help="Start loopback-only search UI and API")
    serve.add_argument("--port", type=int, default=8787)
    backup = sub.add_parser("backup", help="Snapshot the private index to a new file without overwriting")
    backup.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-backup", help="Read-only integrity validation of a private Search backup")
    verify.add_argument("--input", type=Path, required=True)
    recovery = sub.add_parser("restore-copy", help="Copy a verified backup into a NEW catalog path only")
    recovery.add_argument("--input", type=Path, required=True)
    recovery.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "init":
            initialize(args.db)
            print("Local index initialized")
        elif args.operation == "import-jsonl":
            count = import_jsonl(args.db, args.input)
            print(f"Imported {count} curated documents")
        elif args.operation == "backup":
            count = snapshot_catalog(args.db, args.output)
            print(f"Private snapshot created: {count} documents")
        elif args.operation == "verify-backup":
            count = inspect_catalog(args.input)
            print(f"Private Search backup valid: {count} documents")
        elif args.operation == "restore-copy":
            count = snapshot_catalog(args.input, args.output)
            print(f"New recovered catalog created: {count} documents; original untouched")
        elif args.operation == "serve":
            if not 0 <= args.port <= 65535:
                parser.error("Port must be 0–65535")
            run_server(args.db, args.port)
    except (FileNotFoundError, InvalidDocument, RecoveryError, OSError, ValueError) as exc:
        print(f"Cannot complete operation: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
