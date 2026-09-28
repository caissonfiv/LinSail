import contextlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from linsail import maintenance as m
from linsail.installer import START, path_block


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'linsail'
        self.rc = self.root / '.bashrc'
        self.rc.write_text('# original\n' + path_block(self.root), encoding='utf-8')
        self.files = [{'path': str(self.rc), 'fish': False}]
        m.deploy(self.app, b'original', 'pyz', '0.1.0a4', self.files)
        self.addCleanup(patch.stopall)
        patch.object(m, 'current_install', return_value=self.app).start()
        patch.object(m, 'install_lock', side_effect=lambda _: contextlib.nullcontext()).start()

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}

    def test_update_then_rollback_preserves_configuration(self):
        config = self.root / 'config.json'
        config.write_text('user preferences')
        release = {'assets': [{'name': 'linsail.pyz'}]}
        with patch.object(m, 'find_release', return_value=('0.1.0a5', release)), patch.object(m, 'checked_download', return_value=b'updated'), patch.object(m, 'probe', return_value='0.1.0a5'):
            m.update()
        self.assertEqual(self.app.read_bytes(), b'updated')
        with patch.object(m, 'probe', return_value='0.1.0a4'):
            m.rollback()
        self.assertEqual(self.app.read_bytes(), b'original')
        self.assertEqual(config.read_text(), 'user preferences')
        self.assertEqual(m.read_record(self.app)['previous']['version'], '0.1.0a5')

    def test_hash_and_health_failures_leave_all_files_unchanged(self):
        before = self.snapshot()
        release = {'assets': [{'name': 'linsail.pyz'}]}
        with patch.object(m, 'find_release', return_value=('0.1.0a5', release)), patch.object(m, 'checked_download', side_effect=ValueError('hash mismatch')):
            with self.assertRaises(ValueError):
                m.update()
        self.assertEqual(before, self.snapshot())
        with patch.object(m, 'find_release', return_value=('0.1.0a5', release)), patch.object(m, 'checked_download', return_value=b'bad'), patch.object(m, 'probe', side_effect=RuntimeError('cannot start')):
            with self.assertRaises(RuntimeError):
                m.update()
        self.assertEqual(before, self.snapshot())

    def test_metadata_write_failure_restores_previous_install(self):
        before = self.snapshot()
        write = m.atomic_write
        failed = False
        def fail_once(path, content, mode):
            nonlocal failed
            if path.name == '.linsail-install.json' and not failed:
                failed = True
                raise OSError('simulated write failure')
            write(path, content, mode)
        with patch.object(m, 'atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError):
                m.deploy(self.app, b'new', 'pyz', '0.1.0a5', self.files)
        self.assertEqual(before, self.snapshot())

    def test_reinstall_keeps_previous_backup(self):
        m.deploy(self.app, b'new', 'pyz', '0.1.0a5', self.files)
        m.deploy(self.app, b'new', 'pyz', '0.1.0a5', self.files)
        self.assertEqual(m.sidecars(self.app)[1].read_bytes(), b'original')

    def test_modified_installed_file_blocks_maintenance(self):
        self.app.write_bytes(b'manual change')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            m.uninstall(yes=True)
        self.assertEqual(before, self.snapshot())

    def test_corrupt_previous_version_blocks_rollback(self):
        m.deploy(self.app, b'new', 'pyz', '0.1.0a5', self.files)
        m.sidecars(self.app)[1].write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            m.rollback()
        self.assertEqual(self.app.read_bytes(), b'new')

    def test_check_and_missing_architecture_do_not_download(self):
        with patch.object(m, 'find_release', return_value=('0.1.0a5', {'assets': []})), patch.object(m, 'checked_download') as download:
            m.update(check=True)
            download.assert_not_called()
            with self.assertRaises(RuntimeError):
                m.update()
            download.assert_not_called()

    def test_uninstall_preserves_user_rc_changes_config_and_backups(self):
        self.rc.write_text(self.rc.read_text(encoding='utf-8') + "alias ll='ls -l'\n", encoding='utf-8')
        config = self.root / 'config.json'
        config.write_text('keep')
        backup = self.root / '.bashrc.linsail.bak'
        backup.write_text('keep original backup')
        m.uninstall(yes=True)
        self.assertFalse(self.app.exists())
        self.assertFalse(m.sidecars(self.app)[0].exists())
        self.assertNotIn(START, self.rc.read_text())
        self.assertIn("alias ll='ls -l'", self.rc.read_text())
        self.assertEqual(config.read_text(), 'keep')
        self.assertTrue(backup.exists())

    def test_uninstall_retains_edited_managed_block(self):
        self.rc.write_text(self.rc.read_text(encoding='utf-8').replace('case ', '# edited\ncase '), encoding='utf-8')
        before = self.rc.read_bytes()
        m.uninstall(yes=True)
        self.assertEqual(before, self.rc.read_bytes())

    def test_cancel_uninstall_keeps_everything(self):
        before = self.snapshot()
        with patch('builtins.input', return_value='n'):
            m.uninstall()
        self.assertEqual(before, self.snapshot())


class ReleaseTests(unittest.TestCase):
    def test_channel_order_drafts_and_invalid_tags(self):
        releases = [{'tag_name': 'v0.2.0a1', 'prerelease': True}, {'tag_name': 'v0.1.9'},
                    {'tag_name': 'v99.0.0', 'draft': True}, {'tag_name': '../bad'}]
        with patch.object(m, 'fetch', return_value=json.dumps(releases).encode()):
            self.assertEqual(m.find_release('stable')[0], '0.1.9')
            self.assertEqual(m.find_release('alpha')[0], '0.2.0a1')
        self.assertGreater(m.version_key('1.0.0'), m.version_key('1.0.0rc9'))

    def test_duplicate_or_mismatched_checksum_is_rejected(self):
        line = m.digest(b'good') + '  linsail.pyz\n'
        with patch.object(m, 'fetch', return_value=(line * 2).encode()) as fetch:
            with self.assertRaises(ValueError):
                m.checked_download('0.1.0a5', 'linsail.pyz')
            self.assertEqual(fetch.call_count, 1)
        with patch.object(m, 'fetch', side_effect=[line.encode(), b'bad']):
            with self.assertRaises(ValueError):
                m.checked_download('0.1.0a5', 'linsail.pyz')

    def test_arm_asset_and_invalid_pinned_version(self):
        with patch.object(m.platform, 'machine', return_value='aarch64'):
            self.assertEqual(m.asset_name('binary'), 'linsail-linux-arm64')
        with patch.object(m, 'fetch') as fetch:
            with self.assertRaises(ValueError):
                m.find_release('alpha', '../bad')
            fetch.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Requires Linux locks')
    def test_concurrent_install_lock_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with m.install_lock(Path(temp)):
                with self.assertRaises(RuntimeError):
                    with m.install_lock(Path(temp)):
                        self.fail('second lock must not succeed')
