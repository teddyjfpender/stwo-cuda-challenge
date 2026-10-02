"""Release downloads must be pinned and must fall back to source builds."""

import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import release_artifacts as release
from scripts import setup

SOURCE = "b2873365dc28ed4bc4b27de10e01ea0beeef7c93"
TAG = "fixed-rust-b2873365dc28-linux-x86_64-glibc-2-39-v1"


class ReleaseArtifactTests(unittest.TestCase):
    def fixture(self, root: Path):
        official = root / "official"
        registry = root / "registry"
        official.write_bytes(b"official binary")
        registry.write_bytes(b"registry binary")
        preprocessed = root / "preprocessed-canonical.bin"
        preprocessed.write_bytes(b"canonical asset")
        manifest_path = root / "manifest.json"
        with patch.object(release, "PREPROCESSED_SHA256", release.sha_bytes(preprocessed.read_bytes())):
            release.make_manifest(SOURCE, manifest_path, official, registry, preprocessed,
                                  "rustc 1.96.0", "rustc nightly-2026-01-15", "0.15.2")
            lock_path = root / "release-artifacts.lock.json"
            release.make_lock(SOURCE, TAG, manifest_path, lock_path)
        responses = {"manifest.json": manifest_path.read_bytes(),
                     "stwo-cairo-official-verifier": official.read_bytes(),
                     "verify_cairo_cuda_json": registry.read_bytes(),
                     "preprocessed-000.part": preprocessed.read_bytes()}
        return lock_path, responses

    def test_install_and_repair_pinned_binaries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock, responses = self.fixture(root)
            def download(url, limit):
                result = responses[url.rsplit("/", 1)[-1]]
                self.assertLessEqual(len(result), limit)
                return result
            with patch.object(release, "PREPROCESSED_SHA256", release.sha_bytes(b"canonical asset")), \
                 patch.object(release, "platform_supported", return_value=True), \
                 patch.object(release, "read_url", side_effect=download):
                self.assertTrue(release.install(SOURCE, root, lock))
                for key, (_, name) in release.TOOLS.items():
                    self.assertEqual((root / name).read_bytes(), responses[release.TOOLS[key][0]])
                    self.assertTrue((root / name).stat().st_mode & 0o111)
                (root / release.TOOLS["official"][1]).write_bytes(b"tampered")
                self.assertTrue(release.install(SOURCE, root, lock))
                self.assertEqual((root / release.TOOLS["official"][1]).read_bytes(),
                                 responses["stwo-cairo-official-verifier"])
                with patch.object(release.urllib.request, "urlopen",
                                  side_effect=lambda url, timeout: io.BytesIO(
                                      responses[url.rsplit("/", 1)[-1]])):
                    asset = root / ".cache/preprocessed-canonical.bin"
                    self.assertTrue(release.install_preprocessed(SOURCE, asset, lock))
                    self.assertEqual(asset.read_bytes(), b"canonical asset")

    def test_rejects_unpinned_manifest_and_bad_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock, responses = self.fixture(root)
            with patch.object(release, "PREPROCESSED_SHA256", release.sha_bytes(b"canonical asset")), \
                 patch.object(release, "platform_supported", return_value=True):
                corrupted = dict(responses, **{"manifest.json": b"{}"})
                with patch.object(release, "read_url",
                                  side_effect=lambda url, _: corrupted[url.rsplit("/", 1)[-1]]):
                    self.assertFalse(release.install(SOURCE, root, lock))
                corrupted = dict(responses, **{"verify_cairo_cuda_json": b"bad"})
                with patch.object(release, "read_url",
                                  side_effect=lambda url, _: corrupted[url.rsplit("/", 1)[-1]]):
                    self.assertFalse(release.install(SOURCE, root, lock))
                self.assertFalse((root / release.TOOLS["official"][1]).exists())
                self.assertFalse((root / release.TOOLS["registry"][1]).exists())
                with patch.object(release, "read_url",
                                  side_effect=lambda url, _: responses[url.rsplit("/", 1)[-1]]), \
                     patch.object(release.urllib.request, "urlopen",
                                  return_value=io.BytesIO(b"corrupt chunk")):
                    asset = root / ".cache/preprocessed-canonical.bin"
                    self.assertFalse(release.install_preprocessed(SOURCE, asset, lock))
                    self.assertFalse(asset.exists())

    def test_no_release_pin_uses_source_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "benchmark.json").write_text(json.dumps({"sourceCommit": SOURCE}))
            (root / "release-artifacts.lock.json").write_text(json.dumps(
                {"schema": 1, "source_commit": SOURCE, "platforms": {}}))
            asset = root / ".cache/preprocessed-canonical.bin"
            asset.parent.mkdir()
            asset.write_bytes(b"present")
            official = root / release.TOOLS["official"][1]
            registry = root / release.TOOLS["registry"][1]
            official.parent.mkdir(parents=True)
            registry.parent.mkdir(parents=True)
            official.write_bytes(b"built")
            registry.write_bytes(b"built")
            calls = []
            with patch.object(setup, "ROOT", root), \
                 patch.object(setup, "install_rust_release", return_value=False), \
                 patch.object(setup.shutil, "which", return_value="/usr/bin/cargo"), \
                 patch.object(setup, "run", side_effect=lambda *args, **kw: calls.append(args)), \
                 patch.object(setup, "sha", return_value=setup.PREPROCESSED_SHA256), \
                 patch.object(setup, "prepare_cuda_artifacts"):
                setup.prepare_judge_assets(root / "baseline")
            self.assertEqual([command[0] for command in calls], ["cargo", "cargo"])
            self.assertIn("+nightly-2026-01-15", calls[1])


if __name__ == "__main__":
    unittest.main()
