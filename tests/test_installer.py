import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from linsail.installer import START, configure_path, merge_block, path_block
from linsail.cli import chat


class PathTests(unittest.TestCase):
    def test_bash_preserves_config_backup_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            original = "# user config\nalias ll='ls -l'\n"
            (home / '.bashrc').write_text(original)
            configure_path(home, home / '.local/bin', 'bash')
            self.assertEqual((home / '.bashrc.linsail.bak').read_text(), original)
            self.assertEqual(configure_path(home, home / '.local/bin', 'bash'), [])
            self.assertEqual((home / '.bashrc').read_text().count(START), 1)
            configure_path(home, home / 'other bin', 'bash')
            self.assertEqual((home / '.bashrc.linsail.bak').read_text(), original)
            self.assertEqual((home / '.bashrc').read_text().count(START), 1)

    def test_existing_bash_login_file_is_used(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / '.bash_profile').write_text('# existing\n')
            configure_path(home, home / 'bin', 'bash')
            self.assertIn(START, (home / '.bash_profile').read_text())
            self.assertFalse((home / '.profile').exists())

    def test_zsh_respects_zdotdir(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            configure_path(home, home / 'bin', 'zsh', {'ZDOTDIR': str(home / 'zsh')})
            self.assertIn(START, (home / 'zsh/.zshrc').read_text())
            self.assertIn(START, (home / 'zsh/.zprofile').read_text())

    def test_fish_respects_xdg(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            configure_path(home, home / 'bin', 'fish', {'XDG_CONFIG_HOME': str(home / 'config')})
            self.assertIn('set -gx PATH', (home / 'config/fish/conf.d/linsail.fish').read_text())
            self.assertFalse((home / '.bashrc').exists())

    def test_corrupt_block_and_control_characters_rejected(self):
        with self.assertRaises(ValueError):
            merge_block(START + '\nuser text', path_block('/tmp/bin'))
        with self.assertRaises(ValueError):
            path_block('/tmp/bad\npath')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux Bash')
    def test_bash_resolves_command_with_quoted_directory_and_no_duplicate_path(self):
        with tempfile.TemporaryDirectory(prefix="linsail test '") as temp:
            home = Path(temp)
            directory = home / 'my bin'
            directory.mkdir()
            command = directory / 'linsail'
            command.write_text('#!/bin/sh\nprintf ready')
            command.chmod(0o755)
            configure_path(home, directory, 'bash')
            rc = shlex.quote(str(home / '.bashrc'))
            script = f"source {rc}; source {rc}; linsail; printf '\\n%s' \"$PATH\""
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c', script], env={**os.environ, 'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, check=True)
            self.assertTrue(result.stdout.startswith('ready\n'))
            self.assertEqual(result.stdout.splitlines()[1].split(':').count(str(directory)), 1)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires symlinks')
    def test_symlink_dotfile_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            real = home / 'real-rc'
            real.write_text('untouched')
            (home / '.bashrc').symlink_to(real)
            with self.assertRaises(ValueError):
                configure_path(home, home / 'bin', 'bash')
            self.assertEqual(real.read_text(), 'untouched')


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux installer')
class FullInstallTests(unittest.TestCase):
    def test_verified_install_reinstall_and_reject_tampering(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable, str(root / 'scripts/build.py')], check=True, capture_output=True)
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / 'home'
            home.mkdir()
            release = Path(temp) / 'release'
            release.mkdir()
            for name in ('install.sh', 'linsail.pyz', 'SHA256SUMS'):
                shutil.copyfile(root / 'dist' / name, release / name)
            env = {**os.environ, 'HOME': str(home), 'SHELL': '/bin/bash', 'LINSAIL_BIN_DIR': str(home / '.local/bin')}
            env.pop('LINSAIL_NO_PATH', None)
            for _ in range(2):
                subprocess.run(['sh', str(release / 'install.sh')], env=env, check=True, capture_output=True, text=True)
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c', 'source "$HOME/.bashrc"; linsail --version'], env=env, check=True, capture_output=True, text=True)
            self.assertIn('0.1.0a2', result.stdout)
            self.assertEqual((home / '.bashrc').read_text().count(START), 1)
            (release / 'linsail.pyz').write_bytes(b'tampered')
            result = subprocess.run(['sh', str(release / 'install.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotEqual((home / '.local/bin/linsail').read_bytes(), b'tampered')


class OnboardingTests(unittest.TestCase):
    @patch('linsail.cli.sys.platform', 'linux')
    @patch('linsail.cli.os.geteuid', return_value=1000, create=True)
    @patch('linsail.cli.sys.stdin.isatty', return_value=True)
    @patch('linsail.cli.sys.stdout.isatty', return_value=True)
    def test_first_run_configures_then_connects(self, *_):
        profile = {'model': 'test'}
        with patch('linsail.cli.load_config', side_effect=[{'profiles': {}, 'active': ''}, {'profiles': {'personal': profile}, 'active': 'personal'}]), patch('linsail.cli.configure') as configure, patch('linsail.cli.connect', return_value=None) as connect:
            chat()
            configure.assert_called_once()
            connect.assert_called_once_with(profile)

    @patch('linsail.cli.sys.platform', 'linux')
    @patch('linsail.cli.os.geteuid', return_value=1000, create=True)
    @patch('linsail.cli.sys.stdin.isatty', return_value=True)
    @patch('linsail.cli.sys.stdout.isatty', return_value=True)
    def test_named_missing_profile_does_not_replace_configuration(self, *_):
        with patch('linsail.cli.load_config', return_value={'profiles': {}, 'active': ''}), patch('linsail.cli.configure') as configure:
            with self.assertRaises(ValueError):
                chat('missing')
            configure.assert_not_called()


if __name__ == '__main__':
    unittest.main()
