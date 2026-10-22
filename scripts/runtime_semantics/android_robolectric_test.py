"""Dependency bridge regression tests; no candidate behavior is replaced."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import android_robolectric_dependencies as dependencies


class AndroidArtifactTests(unittest.TestCase):
    def test_noncanonical_cached_aar_name_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "gradle/example.group/widget/1/hash/widget-release.aar"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"immutable cached bytes")
            repository = root / "repository"
            with patch.object(dependencies, "GRADLE_CACHE", root / "gradle"), \
                    patch.object(dependencies, "MAVEN_CACHE", root / "empty"):
                dependencies.seed_repository(repository)
            result = repository / "example/group/widget/1/widget-1.aar"
            self.assertTrue(result.is_symlink())
            self.assertEqual(artifact.read_bytes(), result.read_bytes())

    def test_jvm_extraction_preserves_original_classes_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            aar = repository / "example/group/widget/1/widget-1.aar"
            aar.parent.mkdir(parents=True)
            content = io.BytesIO()
            with zipfile.ZipFile(content, "w") as jar:
                jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
            with zipfile.ZipFile(aar, "w") as archive:
                archive.writestr("classes.jar", content.getvalue())
            changed = dependencies.expose_aar_classes(repository, [("example.group", "widget", "1")])
            self.assertTrue(changed)
            self.assertEqual(content.getvalue(), aar.with_suffix(".jar").read_bytes())
            self.assertFalse(dependencies.expose_aar_classes(repository, [("example.group", "widget", "1")]))

    def test_resource_only_aar_does_not_invent_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            aar = repository / "example/group/widget/1/widget-1.aar"
            aar.parent.mkdir(parents=True)
            with zipfile.ZipFile(aar, "w") as archive:
                archive.writestr("AndroidManifest.xml", "<manifest/>")
            self.assertFalse(dependencies.expose_aar_classes(repository, [("example.group", "widget", "1")]))
            self.assertFalse(aar.with_suffix(".jar").exists())


if __name__ == "__main__":
    unittest.main()
