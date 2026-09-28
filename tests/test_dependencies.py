"""Exercise dependency bootstrap without touching system packages."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires POSIX shell')
class DependencyBootstrapTests(unittest.TestCase):
    def run_bootstrap(self, manager='apt-get', consent='1', ready=False,
                      package_failure=False, old_python=False, sudo=True):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def stub(name, body):
                path = root / name
                path.write_text('#!/bin/sh\n' + body + '\n')
                path.chmod(0o755)
            stub('uname', 'echo Linux')
            stub('id', 'echo 1000')
            for name in ('bash', 'curl'):
                stub(name, ':')
            stub('python3', 'exit 1' if old_python else '[ -f "$FIXTURE/ready" ]')
            if sudo:
                stub('sudo', 'printf "%s\\n" "$*" >> "$FIXTURE/calls"\nexec "$@"')
            if manager:
                stub(manager, 'exit 42' if package_failure else ': > "$FIXTURE/ready"')
            if ready:
                (root / 'ready').touch()
            script = Path(__file__).resolve().parents[1] / 'scripts/install-python.sh'
            bootstrap = script.read_text().split('release_dir=', 1)[0]
            result = subprocess.run(['/bin/sh', '-c', bootstrap],
                                    env={**os.environ, 'PATH': str(root), 'FIXTURE': str(root),
                                         'LINSAIL_INSTALL_DEPS': consent},
                                    capture_output=True, text=True, start_new_session=True)
            calls = (root / 'calls').read_text() if (root / 'calls').exists() else ''
            return result, calls

    def test_existing_dependencies_need_no_sudo(self):
        result, calls = self.run_bootstrap(ready=True, sudo=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, '')

    def test_apt_installs_only_missing_dependencies(self):
        result, calls = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.splitlines(), ['apt-get update', 'apt-get install -y --no-install-recommends python3 ca-certificates'])

    def test_dnf_install(self):
        result, calls = self.run_bootstrap(manager='dnf')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.strip(), 'dnf install -y python3 ca-certificates')

    def test_opt_out_and_noninteractive_default_make_no_changes(self):
        for consent in ('0', 'ask'):
            with self.subTest(consent=consent):
                result, calls = self.run_bootstrap(consent=consent)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, '')

    def test_missing_manager_or_sudo_make_no_changes(self):
        for kwargs in ({'manager': None}, {'sudo': False}):
            with self.subTest(kwargs=kwargs):
                result, calls = self.run_bootstrap(**kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, '')

    def test_package_failure_stops_immediately(self):
        result, calls = self.run_bootstrap(package_failure=True)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(calls.strip(), 'apt-get update')

    def test_old_python_is_rejected_after_install(self):
        result, _ = self.run_bootstrap(old_python=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.10+', result.stderr)

