"""The public observation exporter must recheck artifacts, not trust a receipt alone."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_proof_v2 import export


class ExportProofV2Tests(unittest.TestCase):
    def test_rejects_a_changed_proof_after_a_valid_receipt(self):
        proof = b"canonical proof bytes"
        digest = hashlib.sha256(proof).hexdigest()
        config = {"sourceCommit": "a" * 40,
                  "backends": {"cpu": {"timerDigest": "b" * 64}}}
        case = {"id": "pie:test", "family": "pie", "expected_proof_sha256": digest}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "pie_test"
            directory.mkdir()
            (directory / "proof.json").write_bytes(proof)
            (directory / "receipt.json").write_text(json.dumps({
                "schema": "stwo-m5-proof-v2-diagnostic", "backend": "cpu",
                "case_id": "pie:test", "source_commit": config["sourceCommit"],
                "source_diff_sha256": "c" * 64, "timer_digest": "b" * 64,
                "stage_scope": "shared-cairo-product-prove-ns",
                "proof_stage_s": 1.0, "command_wall_s": 2.0,
                "proof_sha256": digest,
            }))
            self.assertEqual(1, len(export(root, config, {"cases": [case]}, "cpu")))
            (directory / "proof.json").write_bytes(b"different proof bytes")
            with self.assertRaisesRegex(ValueError, "Cairo proof digest differs"):
                export(root, config, {"cases": [case]}, "cpu")


if __name__ == "__main__":
    unittest.main()
