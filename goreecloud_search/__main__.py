"""Offline developer preview of first-party metasearch result fusion.

Usage: python3 -m goreecloud_search < providers.json
This does not fetch from providers or conduct an Internet search.
"""
import json
import sys

from . import fuse_results

MAX_INPUT_BYTES = 256 * 1024


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        print("invalid_search_preview_input", file=sys.stderr)
        return 2
    try:
        sources = json.loads(raw)
        merged = fuse_results(sources)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        print("invalid_search_preview_input", file=sys.stderr)
        return 2
    json.dump([item.as_dict() for item in merged], sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
