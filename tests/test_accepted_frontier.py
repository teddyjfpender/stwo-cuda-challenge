import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from harness.accepted_frontier import apply_frontier


class AcceptedFrontierTests(unittest.TestCase):
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
