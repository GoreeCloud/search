"""Guard the loopback-only development launcher against network exposure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MANAGE = ROOT / 'manage'
WRAPPER = ROOT / 'scripts' / 'run-private.sh'


class PrivateLauncherTests(unittest.TestCase):
    def test_manage_uses_safe_environment_for_private_mode(self):
        managed = MANAGE.read_text(encoding='utf-8').split('webapp.run() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('GRANIAN_HOST="${SEARXNG_BIND_ADDRESS:-::}"', managed)
        self.assertNotIn('GRANIAN_HOST="::"', managed)
        self.assertIn('SEARXNG_DEBUG="${SEARXNG_DEBUG:-1}"', managed)
        self.assertIn('GRANIAN_RELOAD="${GRANIAN_RELOAD:-true}"', managed)

    def test_private_wrapper_rejects_unsafe_bind(self):
        env = dict(os.environ, SEARXNG_SECRET='x' * 48, SEARXNG_BIND_ADDRESS='0.0.0.0')
        result = subprocess.run(['bash', str(WRAPPER)], env=env, text=True,
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(64, result.returncode)
        self.assertIn('insecure or public-facing', result.stderr)

    def test_private_wrapper_rejects_weak_secret(self):
        result = subprocess.run(['bash', str(WRAPPER)], env=dict(os.environ, SEARXNG_SECRET='weak'),
                                text=True, capture_output=True, timeout=10, check=False)
        self.assertEqual(64, result.returncode)

    def test_wrapper_execs_only_safe_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            copied = scripts / 'run-private.sh'
            shutil.copyfile(WRAPPER, copied)
            manage = root / 'manage'
            manage.write_text(
                '#!/usr/bin/env python3\n'
                'import json,os\n'
                "names=('SEARXNG_BIND_ADDRESS','SEARXNG_DEBUG','GRANIAN_RELOAD',"
                "'SEARXNG_PUBLIC_INSTANCE','SEARXNG_METHOD','SEARXNG_IMAGE_PROXY',"
                "'SEARXNG_SETTINGS_PATH')\n"
                'print(json.dumps({name:os.environ.get(name) for name in names}))\n',
                encoding='utf-8')
            manage.chmod(0o700)
            env = dict(os.environ, SEARXNG_SECRET='development-not-a-secret-' + 'x' * 36,
                       SEARXNG_DEBUG='true', GRANIAN_RELOAD='true')
            result = subprocess.run(['bash', str(copied)], env=env,
                                    text=True, capture_output=True, timeout=10, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            values = json.loads(result.stdout)
            self.assertEqual('127.0.0.1', values['SEARXNG_BIND_ADDRESS'])
            self.assertEqual('false', values['SEARXNG_DEBUG'])
            self.assertEqual('false', values['GRANIAN_RELOAD'])
            self.assertEqual('false', values['SEARXNG_PUBLIC_INSTANCE'])
            self.assertEqual('POST', values['SEARXNG_METHOD'])
            self.assertEqual('true', values['SEARXNG_IMAGE_PROXY'])
            self.assertEqual(str(root / 'configs/goreecloud/settings.yml'), values['SEARXNG_SETTINGS_PATH'])
