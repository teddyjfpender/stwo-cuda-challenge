"""The public observation exporter must recheck artifacts, not trust a receipt alone."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_proof_v2 import export, export_cuda


class ExportProofV2Tests(unittest.TestCase):
    def test_cuda_pipeline_records_resident_leaf_verification_honestly(self):
        root_files = {"root.proof": b"root", "root_outputs.json": b"outputs",
                      "root_packed.json": b"packed"}
        expected = {key: hashlib.sha256(value).hexdigest()
                    for key, value in root_files.items()}
        config = {"sourceCommit": "a" * 40,
                  "backends": {"cuda": {"timerDigest": "b" * 64}}}
        case = {"id": "pipeline:test", "family": "pipeline", "inputs": ["a", "b"],
                "expected_root": {"proof_sha256": expected["root.proof"],
                                  "outputs_sha256": expected["root_outputs.json"],
                                  "packed_sha256": expected["root_packed.json"]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "pipeline_test" / "result"
            result.mkdir(parents=True)
            for name, value in root_files.items():
                (result / name).write_bytes(value)
            receipt = {"case_id": case["id"], "family": "pipeline",
                       "source_commit": config["sourceCommit"],
                       "source_diff_sha256": hashlib.sha256(b"").hexdigest(),
                       "timer_digest": "b" * 64,
                       "timing_boundary": "proof-execution-v2",
                       "verified": True, "canonical_output": True, "gpu_resident": True,
                       "security_profile": "canonical", "peak_device_bytes": 42,
                       "proof_stages": [{"kind": kind, "seconds": 1.0}
                                        for kind in ("cairo", "cairo", "wrap", "wrap", "fold")],
                       "proof_stage_s": 5.0, "time_s": 6.0,
                       "proof_sha256": expected,
                       "verifier_results": {"resident_cairo_leaves": "verified",
                                            "registry_rust_cairo_leaves": "not_serialized"}}
            receipt_file = root / "direct-results.json"
            receipt_file.write_text(json.dumps([receipt]))
            row = export_cuda(root, config, {"cases": [case]})[0]
            self.assertEqual(row["verification"],
                             "exact-reference-and-resident-cairo-leaves")
            self.assertEqual(row["peak_physical_footprint_bytes"], "42")
            receipt["verifier_results"]["resident_cairo_leaves"] = "missing"
            receipt_file.write_text(json.dumps([receipt]))
            with self.assertRaisesRegex(ValueError, "Cairo leaf verification missing"):
                export_cuda(root, config, {"cases": [case]})

    def test_cuda_export_requires_exact_proof_and_one_cairo_stage(self):
        proof = b"cuda canonical proof"
        digest = hashlib.sha256(proof).hexdigest()
        config = {"sourceCommit": "a" * 40,
                  "backends": {"cuda": {"timerDigest": "b" * 64}}}
        case = {"id": "pie:test", "family": "pie", "expected_proof_sha256": digest}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "pie_test"
            directory.mkdir()
            (directory / "proof.json").write_bytes(proof)
            receipt = {"case_id": case["id"], "family": "pie",
                       "source_commit": config["sourceCommit"],
                       "source_diff_sha256": hashlib.sha256(b"").hexdigest(),
                       "timer_digest": "b" * 64,
                       "timing_boundary": "proof-execution-v2",
                       "verified": True, "canonical_output": True, "gpu_resident": True,
                       "security_profile": "canonical", "peak_device_bytes": 42,
                       "proof_stages": [{"kind": "cairo", "seconds": 1.0}],
                       "proof_stage_s": 1.0, "time_s": 2.0,
                       "proof_sha256": {"proof.json": digest},
                       "verifier_results": {"official_rust_cairo": "accepted"}}
            (root / "direct-results.json").write_text(json.dumps([receipt]))
            self.assertEqual(1, len(export_cuda(root, config, {"cases": [case]})))
            receipt["proof_stages"] = [{"kind": "wrap", "seconds": 1.0}]
            (root / "direct-results.json").write_text(json.dumps([receipt]))
            with self.assertRaisesRegex(ValueError, "incomplete CUDA prover intervals"):
                export_cuda(root, config, {"cases": [case]})

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
