from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import tempfile
import json
import zipfile

spec = importlib.util.spec_from_file_location('uploadingman_release', Path(__file__).resolve().parent.parent / 'release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_versioned_zip_matches_sources_and_omits_runtime_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'UploadingMan'
            root.mkdir()
            (root / 'VERSION.json').write_text(json.dumps({'version': '1.0.0'}), encoding='utf-8')
            (root / 'README.md').write_text('release fixture', encoding='utf-8')
            source = root / 'koita_stage1'
            source.mkdir()
            (source / 'app.py').write_text('print("fixture")', encoding='utf-8')
            (source / 'private.hwpx').write_bytes(b'private fixture')
            with patch.object(release, 'ROOT', root):
                output = release.package_release('1.0.0')
                self.assertEqual(output.name, 'UploadingMan-v1.0.0.zip')
                with zipfile.ZipFile(output) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(json.loads(archive.read('UploadingMan-v1.0.0/VERSION.json'))['version'], '1.0.0')
                    self.assertFalse(any(name.endswith('.hwpx') for name in archive.namelist()))
                with self.assertRaises(ValueError):
                    release.package_release('1.0.0')

    def test_semantic_version_rules(self):
        for current, bump, expected in ((None, 'initial', '1.0.0'), ('1.0.0', 'patch', '1.0.1'),
                                         ('1.2.9', 'minor', '1.3.0'), ('1.9.8', 'major', '2.0.0')):
            self.assertEqual(release.next_version(current, bump), expected)
        with self.assertRaises(ValueError):
            release.next_version('1.0.0', 'initial')
        with self.assertRaises(ValueError):
            release.next_version(None, 'patch')

    def test_preview_never_invokes_git_or_changes_metadata(self):
        before = release.VERSION.read_bytes()
        import json
        current = json.loads(before)['version']
        args = SimpleNamespace(bump='initial' if current is None else 'patch', summary='', approve=False, push_only=False)
        with patch.object(release, 'git') as git, patch.object(release.subprocess, 'run') as run:
            release.publish(args)
        git.assert_not_called()
        run.assert_not_called()
        self.assertEqual(before, release.VERSION.read_bytes())

    def test_source_allowlist_excludes_private_runtime_data(self):
        paths = release.release_files()
        self.assertIn('koita_stage1/app.py', paths)
        self.assertIn('VERSION.json', paths)
        for path in paths:
            self.assertNotIn('.venv', path)
            self.assertNotIn('generated/', path)
            self.assertFalse(path.endswith(('.hwpx', '.jpg', '.png', '.sqlite', '.csv', '.log')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
