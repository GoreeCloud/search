"""Offline, non-installing GTK4 development packaging contracts."""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_native import PREFIX, SOURCE_PATHS, build_archive

ROOT = Path(__file__).resolve().parents[1]


class NativeArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def create(self, name="one.tar.gz", root=ROOT):
        target = self.directory / name
        build_archive(root, target)
        return target

    def test_reproducible_bytes_across_two_builds(self):
        first = self.create()
        second = self.create("two.tar.gz")
        self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                         hashlib.sha256(second.read_bytes()).digest())

    def test_explicit_members_only_and_no_symlink_entries(self):
        output = self.create()
        with tarfile.open(output, "r:gz") as archive:
            members = archive.getmembers()
            expected = {
                f"{PREFIX}/bin/goreecloud-search-native",
                f"{PREFIX}/share/applications/com.goreecloud.Search.Development.desktop",
                f"{PREFIX}/README-DEV.txt",
                f"{PREFIX}/LICENSE",
                *(f"{PREFIX}/lib/{p}" for p in SOURCE_PATHS
                  if p.startswith("goreecloud_search/")),
            }
            self.assertEqual({item.name for item in members}, expected)
            self.assertTrue(all(item.isfile() and not item.issym() for item in members))
            self.assertTrue(all(item.uid == 0 and item.gid == 0 and item.mtime == 0
                                for item in members))
            self.assertEqual(next(item.mode for item in members if item.name.endswith(
                "/bin/goreecloud-search-native")), 0o755)

    def test_reject_existing_or_symlinked_archive(self):
        existing = self.directory / "existing.tar.gz"
        existing.write_text("do not overwrite", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            build_archive(ROOT, existing)
        self.assertEqual(existing.read_text(encoding="utf-8"), "do not overwrite")
        symlink = self.directory / "symbolic.tar.gz"
        symlink.symlink_to(existing)
        with self.assertRaises(ValueError):
            build_archive(ROOT, symlink)
        self.assertEqual(existing.read_text(encoding="utf-8"), "do not overwrite")
        dangling = self.directory / "dangling.tar.gz"
        dangling.symlink_to(self.directory / "missing.tar.gz")
        with self.assertRaises(ValueError):
            build_archive(ROOT, dangling)

    def test_reject_symlinked_or_missing_source_without_creating_archive(self):
        repo = self.directory / "repo"
        for source in SOURCE_PATHS:
            target = repo / source
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / source).read_bytes())
        original = repo / "goreecloud_search/native.py"
        original.unlink()
        original.symlink_to(ROOT / "goreecloud_search/native.py")
        output = self.directory / "target.tar.gz"
        with self.assertRaises(ValueError):
            build_archive(repo, output)
        self.assertFalse(output.exists())
        original.unlink()
        with self.assertRaises(ValueError):
            build_archive(repo, output)
        self.assertFalse(output.exists())

    def test_launcher_can_show_help_without_gtk_or_install(self):
        output = self.create()
        extraction = self.directory / "unpacked"
        extraction.mkdir()
        with tarfile.open(output, "r:gz") as archive:
            for member in archive:
                self.assertTrue(member.isfile())
                destination = extraction / member.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(member).read())
        launcher = extraction / PREFIX / "bin/goreecloud-search-native"
        command = subprocess.run(
            [sys.executable, str(launcher), "--help"],
            capture_output=True, text=True, timeout=10, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertIn("--db", command.stdout)

    def test_desktop_template_does_not_auto_install_or_enable_egress(self):
        output = self.create()
        with tarfile.open(output, "r:gz") as archive:
            template = archive.extractfile(
                f"{PREFIX}/share/applications/com.goreecloud.Search.Development.desktop"
            ).read().decode("utf-8")
            launcher = archive.extractfile(
                f"{PREFIX}/bin/goreecloud-search-native"
            ).read().decode("utf-8")
        self.assertIn("Type=Application", template)
        self.assertIn("Exec=goreecloud-search-native", template)
        self.assertNotIn("sudo", template)
        self.assertNotIn("GC_SEARCH_EXTERNAL_ENABLED", template + launcher)
        self.assertNotIn("api.search.brave.com", template + launcher)
        self.assertNotIn("curl", launcher)


if __name__ == "__main__":
    unittest.main()
