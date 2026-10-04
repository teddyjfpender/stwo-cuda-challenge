from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.setup_proof_v2 import clear_other_frontier, head, repin_clean


class ProofEpochSetupTests(unittest.TestCase):
    def test_switching_backends_reverses_only_the_exact_accepted_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "source"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            target = repo / "src/backends/metal/example.zig"
            target.parent.mkdir(parents=True)
            target.write_text("base\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qm", "base"], check=True)
            target.write_text("frontier\n")
            raw = subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", "HEAD"])
            frontier = root / "frontier/proof-v2/metal"
            frontier.mkdir(parents=True)
            (frontier / "changes.patch").write_bytes(raw)
            with patch("scripts.setup_proof_v2.ROOT", root):
                clear_other_frontier(repo, "cpu")
                self.assertEqual(target.read_text(), "base\n")
                subprocess.run(["git", "-C", str(repo), "apply", str(frontier / "changes.patch")],
                               check=True)
                target.write_text("participant edit\n")
                clear_other_frontier(repo, "cpu")
                self.assertEqual(target.read_text(), "participant edit\n")

    def test_repin_preserves_edits_and_moves_clean_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            file = repo / "source.zig"
            file.write_text("first\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qm", "first"], check=True)
            first = head(repo)
            file.write_text("second\n")
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "-qam", "second"], check=True)
            second = head(repo)
            repin_clean(repo, first)
            self.assertEqual(head(repo), first)
            file.write_text("participant edit\n")
            with self.assertRaisesRegex(ValueError, "capture them"):
                repin_clean(repo, second)
            self.assertEqual(file.read_text(), "participant edit\n")
            file.write_text("first\n")
            repin_clean(repo, second)
            self.assertEqual(head(repo), second)


if __name__ == "__main__":
    unittest.main()
