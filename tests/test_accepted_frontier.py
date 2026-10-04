import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from harness.accepted_frontier import apply_frontier


class AcceptedFrontierTests(unittest.TestCase):
    def test_proof_v2_frontier_applies_only_to_selected_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            metal = source / "src/backends/metal/example.zig"
            metal.parent.mkdir(parents=True)
            metal.write_text("base\n")
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qm", "base"],
                           check=True)
            commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                             text=True).strip()
            baseline = root / "baseline"
            subprocess.run(["git", "-C", str(source), "worktree", "add", "-q", "--detach",
                            str(baseline), commit], check=True)
            metal.write_text("accepted\n")
            raw = subprocess.check_output(["git", "-C", str(source), "diff", "HEAD"])
            metal.write_text("base\n")
            frontier = root / "frontier/proof-v2/metal"
            frontier.mkdir(parents=True)
            (frontier / "changes.patch").write_bytes(raw)
            (frontier / "manifest.json").write_text(json.dumps({
                "schema": "stwo-proof-v2-frontier-v1", "backend": "metal",
                "sourceCommit": commit, "patchSha256": hashlib.sha256(raw).hexdigest(),
                "prNumber": 22}) + "\n")
            config = {"sourceCommit": commit, "backends": {
                "metal": {"editablePaths": ["src/backends/metal"]},
                "cpu": {"editablePaths": ["src/backends/cpu_scalar"]}}}
            apply_frontier(root, source, baseline, config, backend="cpu")
            self.assertEqual(metal.read_text(), "base\n")
            apply_frontier(root, source, baseline, config, backend="metal")
            apply_frontier(root, source, baseline, config, backend="metal")
            self.assertEqual(metal.read_text(), "accepted\n")
            self.assertEqual((baseline / "src/backends/metal/example.zig").read_text(), "base\n")
            metal.write_text("participant edit\n")
            with self.assertRaisesRegex(SystemExit, "changes beyond the accepted frontier"):
                apply_frontier(root, source, baseline, config, backend="metal")

    def test_migration_clears_capture_intent_to_add_for_old_frontier_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "source"
            workspace.mkdir()
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            original = workspace / "src/backends/cuda/example.zig"
            original.parent.mkdir(parents=True)
            original.write_text("base\n")
            subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
            subprocess.run(["git", "-C", str(workspace), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qm", "base"], check=True)
            commit = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"],
                                             text=True).strip()
            baseline = root / "baseline"
            subprocess.run(["git", "-C", str(workspace), "worktree", "add", "-q", "--detach",
                            str(baseline), commit], check=True)
            added = workspace / "src/backends/cuda/ingress.zig"
            added.write_text("old\n")
            subprocess.run(["git", "-C", str(workspace), "add", "-N", str(added)], check=True)
            old_raw = subprocess.check_output(["git", "-C", str(workspace), "diff", "HEAD"])
            added.write_text("new\n")
            new_raw = subprocess.check_output(["git", "-C", str(workspace), "diff", "HEAD"])
            added.write_text("old\n")
            frontier = root / "frontier"
            history = frontier / "history"
            history.mkdir(parents=True)
            old_digest = hashlib.sha256(old_raw).hexdigest()
            new_digest = hashlib.sha256(new_raw).hexdigest()
            (history / f"{old_digest}.patch").write_bytes(old_raw)
            (frontier / "changes.patch").write_bytes(new_raw)
            (frontier / "manifest.json").write_text(json.dumps({
                "schema": "stwo-cuda-frontier-v1", "sourceCommit": commit,
                "patchSha256": new_digest, "parentPatchSha256": old_digest,
                "prNumber": 17}) + "\n")
            marker = Path(subprocess.check_output([
                "git", "-C", str(workspace), "rev-parse", "--git-path", "stwo-cuda-frontier.json"],
                text=True).strip())
            if not marker.is_absolute():
                marker = workspace / marker
            marker.write_text(json.dumps({"patchSha256": old_digest}) + "\n")
            apply_frontier(root, workspace, baseline,
                           {"sourceCommit": commit, "editablePaths": ["src/backends/cuda"]})
            self.assertEqual(added.read_text(), "new\n")
            self.assertEqual(json.loads(marker.read_text())["patchSha256"], new_digest)

    def test_setup_advances_only_an_unmodified_previous_frontier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "source"
            workspace.mkdir()
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            target = workspace / "src/backends/cuda/example.zig"
            target.parent.mkdir(parents=True)
            target.write_text("base\n")
            subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
            subprocess.run(["git", "-C", str(workspace), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qm", "base"], check=True)
            commit = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"],
                                             text=True).strip()
            baseline = root / "baseline"
            subprocess.run(["git", "-C", str(workspace), "worktree", "add", "-q", "--detach",
                            str(baseline), commit], check=True)
            target.write_text("first\n")
            old_raw = subprocess.check_output(["git", "-C", str(workspace), "diff", "HEAD"])
            target.write_text("second\n")
            new_raw = subprocess.check_output(["git", "-C", str(workspace), "diff", "HEAD"])
            target.write_text("base\n")
            frontier = root / "frontier"
            history = frontier / "history"
            history.mkdir(parents=True)
            old_digest = hashlib.sha256(old_raw).hexdigest()
            new_digest = hashlib.sha256(new_raw).hexdigest()
            (history / f"{old_digest}.patch").write_bytes(old_raw)
            (frontier / "changes.patch").write_bytes(new_raw)
            (frontier / "manifest.json").write_text(json.dumps({
                "schema": "stwo-cuda-frontier-v1", "sourceCommit": commit,
                "patchSha256": new_digest, "parentPatchSha256": old_digest,
                "prNumber": 205}) + "\n")
            marker = Path(subprocess.check_output([
                "git", "-C", str(workspace), "rev-parse", "--git-path", "stwo-cuda-frontier.json"],
                text=True).strip())
            if not marker.is_absolute():
                marker = workspace / marker
            marker.write_text(json.dumps({"patchSha256": old_digest}) + "\n")
            subprocess.run(["git", "-C", str(workspace), "apply", str(history / f"{old_digest}.patch")],
                           check=True)
            config = {"sourceCommit": commit, "editablePaths": ["src/backends/cuda"]}
            target.write_text("participant change\n")
            with self.assertRaisesRegex(SystemExit, "capture them"):
                apply_frontier(root, workspace, baseline, config)
            self.assertEqual(target.read_text(), "participant change\n")
            target.write_text("first\n")
            apply_frontier(root, workspace, baseline, config)
            self.assertEqual(target.read_text(), "second\n")
            self.assertEqual(json.loads(marker.read_text())["patchSha256"], new_digest)
            apply_frontier(root, workspace, baseline, config)
            self.assertEqual(target.read_text(), "second\n")

    def test_apply_is_idempotent_and_refuses_tampered_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "source"
            workspace.mkdir()
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            target = workspace / "src/backends/cuda/example.zig"
            target.parent.mkdir(parents=True)
            target.write_text("old\n")
            subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
            subprocess.run(["git", "-C", str(workspace), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qm", "base"], check=True)
            commit = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"],
                                             text=True).strip()
            target.write_text("new\n")
            raw = subprocess.check_output(["git", "-C", str(workspace), "diff", "HEAD"])
            target.write_text("old\n")
            baseline = root / "baseline"
            subprocess.run(["git", "-C", str(workspace), "worktree", "add", "-q", "--detach",
                            str(baseline), commit], check=True)
            frontier = root / "frontier"
            frontier.mkdir()
            patch = frontier / "changes.patch"
            patch.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            (frontier / "manifest.json").write_text(json.dumps({
                "schema": "stwo-cuda-frontier-v1", "sourceCommit": commit,
                "patchSha256": digest, "prNumber": 6}) + "\n")
            config = {"sourceCommit": commit, "editablePaths": ["src/backends/cuda"]}
            apply_frontier(root, workspace, baseline, config)
            self.assertEqual(target.read_text(), "new\n")
            apply_frontier(root, workspace, baseline, config)
            self.assertEqual(target.read_text(), "new\n")
            patch.write_bytes(raw + b"\n")
            with self.assertRaises(SystemExit):
                apply_frontier(root, workspace, baseline, config)


if __name__ == "__main__":
    unittest.main()
