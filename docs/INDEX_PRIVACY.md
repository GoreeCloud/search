# GoreeCloud Search — Private active index access

**Status:** Original local-only Development implementation. Part of [draft PR #2](https://github.com/GoreeCloud/search/pull/2); no deployment or live-provider activation.

## Active catalog filesystem contract

The first-party SQLite FTS5 catalog contains manually imported titles, descriptions, source labels, and user-approved public navigation links. It must reside at an **absolute path** with no lexical `..` path components or symbolic links anywhere in its directory ancestry. The immediate directory must belong to the process user and be inaccessible to group/others (normally `0700`). The file must be a regular file owned by the current user, with no group/other permissions (normally `0600`). The ordinary `connect()`, `initialize()`, search, and import paths apply this contract. They refuse unsafe paths; they do not repair or chmod user files without permission.

**Read/write separation:** Search queries use SQLite URI `mode=ro`, plus `PRAGMA query_only=ON`. Explicit imports use `mode=rw`, and initialization is the only operation that creates a previously absent catalog with owner-private permissions. Existing `mode=rw` database opens cannot silently initialize a missing catalog. Bounded JSONL imports replace indexed records transactionally. The private backup/verification subsystem has independent source `mode=ro`, non-overwrite and recovery-copy guarantees; see [catalog recovery](CATALOG_BACKUP_RECOVERY.md).

**Development quickstart:** Create a private directory before using any temporary catalog:

```bash
GC_SEARCH_DEMO_DIR="$(mktemp -d /tmp/gc-search-demo.XXXXXXXX)"
python3 -m goreecloud_search --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" init
python3 -m goreecloud_search --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" import-jsonl --input examples/catalog.jsonl
python3 -m goreecloud_search --db "$GC_SEARCH_DEMO_DIR/catalog.sqlite3" serve --port 8787
```

The example is run from the trusted repository checkout on the same device. The direct `/tmp/index.sqlite3` pattern is deliberately refused because `/tmp` is a public parent directory. Remove disposable test directories only through intentional owner action, not by Search automation.

## Transactional, bounded JSONL import

The owner-supplied JSON Lines file is read from **one opened regular file** as a bounded (2,000,000-byte maximum) UTF-8 snapshot before parsing or index mutation. This prevents a changing file or nonregular input from bypassing a pre-open size check, blocks symlinked source files, symlinked intermediate source directories, lexical `..` traversal paths and FIFOs, and keeps decoding bounded without unbounded line iteration. Legitimate relative paths such as `examples/catalog.jsonl` remain supported. Duplicate JSON keys (including inside nested objects), `NaN` and `Infinity` are rejected, as are malformed UTF-8 and any invalid document.

The imported document count must be between **1 and 1,000**. **Zero-byte and whitespace-only files fail closed**, preserving the previous catalog. Deliberately clearing a catalog is not an import operation; do not substitute an empty JSONL file for a destructive reset. All records must validate successfully before a single transactional replacement begins. The `import-jsonl` command does not read or send third-party network content.

Regression checks in `tests/test_import_security.py` exercise invalid sources, bounded reads even when a preliminary file size is misreported, strict JSON, valid UTF-8 and line endings, and failure preservation. These checks do not claim race-free protection against a malicious same-UID actor replacing an import path or guarantee that imported public links remain reachable.

## Verified offline regression evidence

`tests/test_store_security.py` covers nested symlink ancestry, public directories, owner mismatches, traversal paths, non-regular files/symlinks, URI-special filenames, read-only search connections and explicit writable imports. `tests/test_quickstart.py` checks that README uses an owner-private directory and runs the actual CLI initialization/import/local-search flow with disposable records. Mandatory GitHub Actions runs Python 3.11 and 3.12 and fails on skipped tests.

These checks do **not** provide a race-free guarantee against a malicious process already running as the same local user, full disk encryption, signed distribution, disaster recovery, or security against a compromised device. Parent-path checks and SQLite URI modes reduce accidental exposure and unsafe local file selection; OS privilege boundaries and trusted storage remain required.

The original Search implementation includes no web crawler and sends no remote query when the default local-only provider is selected.
