"""Offline native importer CLI smoke test."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class NativeCorpusSmoke(unittest.TestCase):
    def test_cli_uses_explicit_manifest_and_revision(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            docs=root/'docs/goreecloud'
            docs.mkdir(parents=True)
            (docs/'ROADMAP.md').write_text('# Roadmap\nGoreeCloud native indexing.')
            manifest=root/'allow.json'
            manifest.write_text(json.dumps({'repository':'GoreeCloud/search',
                   'approved_paths':['docs/goreecloud/ROADMAP.md']}))
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args],
                   check=True,capture_output=True,text=True).stdout.strip()
            git('init','-q')
            git('add','docs')
            git('-c','user.name=Dev','-c','user.email=dev@example.invalid','commit','-qm','Fixture')
            command=[sys.executable,'-m','native_search','import-approved-repo',
                     '--db',str(root/'idx.db'),'--repo-root',str(root),
                     '--manifest',str(manifest),'--revision',git('rev-parse','HEAD')]
            output=subprocess.run(command,check=True,capture_output=True,text=True)
            self.assertEqual(1,json.loads(output.stdout)['imported'])
