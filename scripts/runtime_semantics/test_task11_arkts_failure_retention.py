import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.runtime_semantics.task11_arkts_failure_retention import retain_failed_artifacts


class FailureRetentionTests(unittest.TestCase):
    def test_lossless_bytes_survive_failed_child_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'temporary', root / 'retained'
            source.mkdir()
            raw = b'{"status":"not_scored","reason":"actual failure"}\r\n'
            (source / 'native-result.json').write_bytes(raw)
            (source / 'command.log').write_bytes(b'actual partial child stderr\n')
            (source / 'copied.hap').write_bytes(b'binary')
            receipt = retain_failed_artifacts(source, target)
            manifest = json.loads(Path(receipt['path']).read_text())
            shutil.rmtree(source)
            self.assertEqual(2, len(manifest['files']))
            self.assertEqual(1, len(manifest['binaryHashes']))
            native = next(item for item in manifest['files'] if item['relativePath'] == 'native-result.json')
            with gzip.open(native['gzip']['path'], 'rb') as stream:
                self.assertEqual(raw, stream.read())

    def test_refuses_overwrite_or_archive_under_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'temporary'
            source.mkdir()
            with self.assertRaises(ValueError):
                retain_failed_artifacts(source, source / 'bad')
            existing = root / 'existing'
            existing.mkdir()
            with self.assertRaises(ValueError):
                retain_failed_artifacts(source, existing)


if __name__ == '__main__':
    unittest.main()
