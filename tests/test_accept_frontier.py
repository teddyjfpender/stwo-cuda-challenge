import hashlib
from pathlib import Path
import tempfile
import unittest

from service.accept_frontier import archive_previous_frontier


class AcceptFrontierTests(unittest.TestCase):
    def test_archives_exact_parent_patch_for_workspace_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            frontier = Path(temp)
            raw = b"reviewed cumulative source patch\n"
            digest = hashlib.sha256(raw).hexdigest()
            (frontier / "changes.patch").write_bytes(raw)
            archive_previous_frontier(frontier, digest)
            archive_previous_frontier(frontier, digest)
            self.assertEqual((frontier / "history" / f"{digest}.patch").read_bytes(), raw)
            with self.assertRaisesRegex(SystemExit, "differs from its manifest"):
                archive_previous_frontier(frontier, "0" * 64)


if __name__ == "__main__":
    unittest.main()
