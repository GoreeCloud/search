# GoreeCloud Search — Native Linux development archive

**Stage:** Source-only GTK4 development package; NOT installed, signed, published or production-ready.

The first-party `scripts/package_native.py` generates a reproducible `.tar.gz` containing the local-only Python GTK4 Search client, its private-index model, a launcher, a freedesktop desktop-entry **template**, a readme and the first-party Apache-2.0 license. It does **not** bundle Brave, SearXNG, credentials, an API account, a web service, downloaded executables, telemetry or external assets.

## Build and inspect without installing

From a trusted checkout of the active greenfield source branch:

```bash
python3 scripts/package_native.py --output /absolute/private/path/search-native-dev.tar.gz
python3 scripts/package_native.py --verify /absolute/private/path/search-native-dev.tar.gz
tar -tzf /absolute/private/path/search-native-dev.tar.gz
sha256sum /absolute/private/path/search-native-dev.tar.gz
```

The output must not already exist. The tool refuses symlinked or missing source files, refuses an existing destination archive (including dangling symlinks), and uses deterministic file ordering, modes, owner metadata and gzip timestamps. It does not install software, run installers or modify system services.

After manually extracting to an owner-controlled, isolated test directory:

```bash
python3 /absolute/test/directory/goreecloud-search-native-dev/bin/goreecloud-search-native --help
# Only with an already initialized, private catalog and GTK4/PyGObject installed:
python3 /absolute/test/directory/goreecloud-search-native-dev/bin/goreecloud-search-native --db /absolute/private/catalog.sqlite3
```

GTK4 and PyGObject must be supplied by the operating system's trusted package manager. Desktop entry `Exec=goreecloud-search-native` is only a **template**, and works only when the executable is appropriately installed on PATH in an authorized environment. This archive does not perform that installation or set PATH.

## Tests and verification

The GitHub CI no-skip suite includes six original packaging tests: deterministic archive SHA-256 equality, explicit safe file set, canonical metadata, refusal to overwrite or follow symlinks, a packaged launcher `--help` smoke, and absence of automatic installation and outbound-provider enablement. An additional native UI contract test requires explicit GTK accessible names for the search entry and results list.

An earlier authorized Linux development smoke built a seven-file archive. After the shared public-HTTPS link policy became a direct dependency of the native catalog, the archive manifest was updated to include `lib/goreecloud_search/links.py` (eight regular files in total). The packaged launcher acceptance test caught the missing dependency in GitHub Actions and subsequently passed after the manifest fix. A separate isolated GTK4/Xvfb smoke of the updated native application validated that a native window, search entry and private search result appeared, exiting 0. Nonfatal GPU and GTK focus warnings were observed and do not imply real desktop accessibility or visual acceptance.

Verify the workflow for the latest PR head before citing a definitive test count.

## Reproducible hash manifest and independent Linux verification (November 2)

The source archive now contains `MANIFEST.sha256` with the SHA-256 of each of the other **eight** allowlisted source/launcher/template/license files. The `--verify` operation is read-only and does not extract files, start GTK, install software, or contact third parties. It refuses unexpected member names (including traversal paths), duplicate members, symlinks, incorrect file modes, unexpected ownership/timestamps and oversized members, and checks the recorded hashes against the included bytes.

Four additional offline regression tests exercise the complete manifest, tampering, undeclared members and the command-line verifier. The mandatory test count is now at least 99. An independent authorized Linux laptop check at commit `14b1eb8` successfully built the archive, verified **eight files**, and produced the archive SHA-256 `51c623ceea89acc058028705e7d006c7961fb2acae562b44436c5d6591c45360` under an isolated temporary directory. This fingerprint refers only to that synthetic development archive, not a signed release or deployed package.

**Security limit:** An attacker who can replace the archive can also replace its SHA-256 manifest. These checks detect accidental corruption or inconsistency; they **do not establish publisher identity, authenticity or release signing**. The first-party code and included source must still be reviewed, with a trusted verified release signature and policy before distribution.

## Still required before release

- Safe, reversible, user-approved installation and removal behavior for system or per-user desktop packages.
- Signed reproducible release artifacts with reviewed dependencies/SBOM; first-party GC UI visual and keyboard/assistive-tech acceptance.
- Supported Linux version matrix, launchers/icons, backup/rollback, cross-platform packaging where appropriate.
- Provider account billing, privacy, and secure staging qualification before any external connection.

The original Search application remains **Development**, and the historical code-recovery PR remains excluded.
