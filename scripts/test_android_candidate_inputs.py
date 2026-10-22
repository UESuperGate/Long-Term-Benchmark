import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import android_candidate_inputs as inputs


class RawInputsTest(unittest.TestCase):
    def fixture(self, root):
        candidate = root / 'candidate'
        candidate.mkdir()
        (candidate / '.git').mkdir()
        (candidate / '.git/private-metadata').write_text('not a working-tree input')
        (candidate / '.gitignore').write_text('ignored.input\n')
        (candidate / 'ignored.input').write_bytes(b'actual ignored build input\x00')
        (candidate / 'source.kt').write_bytes(b'class Actual\n')
        (candidate / 'source.kt').chmod(0o640)
        (candidate / 'linked').symlink_to('source.kt')
        return candidate

    def test_raw_bytes_modes_symlinks_and_gitignored_inputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            receipt = inputs.capture(candidate, root / 'snapshot')
            inputs.verify_current(candidate, receipt)
            inventory = json.loads(inputs.read_record(receipt['before']))
            entries = {item['path']: item for item in inventory['entries']}
            self.assertEqual(0o640, entries['source.kt']['mode'])
            self.assertEqual('source.kt', entries['linked']['target'])
            self.assertIn('ignored.input', entries)
            self.assertNotIn('.git/private-metadata', entries)
            with tarfile.open(receipt['archive']['path']) as archive:
                self.assertEqual(0o640, archive.getmember('source.kt').mode)
                self.assertEqual(b'actual ignored build input\x00', archive.extractfile('ignored.input').read())
                self.assertTrue(archive.getmember('linked').issym())

    def test_mode_644_to_664_is_not_equal_and_bytes_or_link_mutations_reject(self):
        for mutation in ('mode', 'bytes', 'link', 'new-input'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                candidate = self.fixture(root)
                (candidate / 'source.kt').chmod(0o644)
                receipt = inputs.capture(candidate, root / 'snapshot')
                if mutation == 'mode':
                    (candidate / 'source.kt').chmod(0o664)
                elif mutation == 'bytes':
                    (candidate / 'source.kt').write_bytes(b'different raw bytes')
                elif mutation == 'link':
                    (candidate / 'linked').unlink()
                    (candidate / 'linked').symlink_to('ignored.input')
                else:
                    (candidate / 'new.input').write_text('untracked input')
                with self.assertRaisesRegex(inputs.InputIntegrityError, 'Actual working tree differs'):
                    inputs.verify_current(candidate, receipt)

    def test_archive_mode_mutation_is_not_normalized_to_git_executable_bit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            receipt = inputs.capture(candidate, root / 'snapshot')
            entries = json.loads(inputs.read_record(receipt['before']))['entries']
            with tarfile.open(receipt['archive']['path']) as source, tarfile.open(root / 'mutated.tar.gz', 'w:gz') as target:
                for member in source:
                    changed = copy.copy(member)
                    if member.name == 'source.kt':
                        changed.mode = 0o660
                    target.addfile(changed, source.extractfile(member) if member.isfile() else None)
            with self.assertRaisesRegex(inputs.InputIntegrityError, 'exact POSIX mode'):
                inputs.verify_archive(root / 'mutated.tar.gz', entries)

    def test_source_change_during_archive_never_creates_accepted_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            real = inputs.verify_archive
            def change(*args, **kwargs):
                result = real(*args, **kwargs)
                (candidate / 'source.kt').write_text('changed after archive')
                return result
            with patch.object(inputs, 'verify_archive', side_effect=change), \
                    self.assertRaisesRegex(inputs.InputIntegrityError, 'changed while raw snapshot'):
                inputs.capture(candidate, root / 'snapshot')
            self.assertFalse((root / 'snapshot/receipt.json').exists())

    def test_external_symlinks_hardlinks_and_in_candidate_archive_fail_closed(self):
        for mutation in ('symlink', 'hardlink', 'inside'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                candidate = self.fixture(root)
                destination = root / 'snapshot'
                if mutation == 'symlink':
                    (candidate / 'outside').symlink_to('../not-captured')
                elif mutation == 'hardlink':
                    os.link(candidate / 'source.kt', candidate / 'hardlinked')
                else:
                    destination = candidate / 'snapshot'
                with self.assertRaises(inputs.InputIntegrityError):
                    inputs.capture(candidate, destination)

    def test_snapshot_obeys_shared_deadline_and_storage_callback_without_running_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self.fixture(root)
            with self.assertRaises(TimeoutError):
                inputs.capture(candidate, root / 'expired', deadline=time.monotonic() - 1)
            class StorageStop(RuntimeError):
                pass
            with self.assertRaises(StorageStop):
                inputs.capture(candidate, root / 'low-disk', storage_check=lambda: (_ for _ in ()).throw(StorageStop()))

    def test_offline_real_lfs_hydrated_worktree_is_not_replaced_by_committed_pointer(self):
        self.assertIsNotNone(shutil.which('git-lfs'), 'Offline LFS regression requires installed git-lfs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate'
            candidate.mkdir()
            env = {**os.environ, 'GIT_LFS_SKIP_SMUDGE': '1'}
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=candidate, env=env, stderr=subprocess.PIPE)
            git('init', '-q')
            for key, value in [('filter.lfs.process', 'git-lfs filter-process'),
                               ('filter.lfs.clean', 'git-lfs clean -- %f'),
                               ('filter.lfs.smudge', 'git-lfs smudge -- %f'), ('filter.lfs.required', 'true')]:
                git('config', key, value)
            (candidate / '.gitattributes').write_text('asset.bin filter=lfs diff=lfs merge=lfs -text\n')
            hydrated = b'actual hydrated binary\x00' * 100
            (candidate / 'asset.bin').write_bytes(hydrated)
            (candidate / 'asset.bin').chmod(0o644)
            git('add', '-A')
            git('-c', 'user.name=Offline', '-c', 'user.email=offline@localhost', 'commit', '-qm', 'fixture')
            pointer = git('show', 'HEAD:asset.bin')
            self.assertTrue(pointer.startswith(b'version https://git-lfs.github.com/spec/v1\n'))
            self.assertEqual(hydrated, (candidate / 'asset.bin').read_bytes())
            git('archive', '--format=tar.gz', '--output=' + str(root / 'committed.tar.gz'), 'HEAD')
            with tarfile.open(root / 'committed.tar.gz') as archive:
                self.assertEqual(pointer, archive.extractfile('asset.bin').read())
            receipt = inputs.capture(candidate, root / 'raw')
            with tarfile.open(receipt['archive']['path']) as archive:
                self.assertEqual(hydrated, archive.extractfile('asset.bin').read())
                self.assertEqual(0o644, archive.getmember('asset.bin').mode)
            inputs.verify_current(candidate, receipt)


if __name__ == '__main__':
    unittest.main()
