from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.setup_proof_v2 import head, repin_clean


class ProofEpochSetupTests(unittest.TestCase):
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
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "second",
                            "--author=Test <test@example.com>"], check=True)
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
