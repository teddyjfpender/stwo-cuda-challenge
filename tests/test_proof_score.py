"""The staged proof epoch scores complete proof stages, never command or memory."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from harness.proof_score import InvalidProofEvidence, aggregate, expected_stages, write_ranked
from harness.timer_owner import check_protected, digest


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "benchmark-proof-v2.json"
MANIFEST_PATH = ROOT / "fixtures/public-proof-v2.json"


class ProofEpochTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG_PATH.read_text())
        self.manifest = json.loads(MANIFEST_PATH.read_text())
        self.manifest_hash = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()

    def evidence(self, backend="cpu", ratio=0.8):
        timer = self.config["backends"][backend]["timerDigest"]
        common = {"backend": backend, "timer_digest": timer, "host_id": "m5-max-fixed-host",
                  "timer_scope": "proof-execution-v2", "verified": True, "profile_ok": True,
                  "statement_ok": True, "input_hash_ok": True, "memory_admitted": True,
                  "peak_bytes": 50_000_000_000, "planned_arena_bytes": 50_000_000_000}
        baseline, candidate = [], []
        for case in self.manifest["cases"]:
            kinds = [kind for kind, count in expected_stages(case).items() for _ in range(count)]
            for round_id in range(3):
                for arm, target, factor in (("baseline", baseline, 1), ("candidate", candidate, ratio)):
                    stages = [{"kind": kind, "seconds": 10 * factor / len(kinds)} for kind in kinds]
                    target.append({**common, "case_id": case["id"], "round": round_id,
                                   "stages": stages, "proof_time_s": 10 * factor,
                                   "command_time_s": 100 if arm == "baseline" else 200})
        return {"schema": "stwo-proof-paired-evidence-v2", "contract_epoch": "proof-v2",
                "source_commit": self.config["sourceCommit"],
                "manifest_sha256": self.manifest_hash, "backend": backend,
                "host_id": "m5-max-fixed-host", "tier": "rank",
                "aa_time_log_ratios": [0.0, 0.001, -0.001],
                "baseline": baseline, "candidate": candidate}

    def test_same_inputs_and_exact_outputs_from_previous_epoch(self):
        old = json.loads((ROOT / "fixtures/public-v1.json").read_text())
        original = {case["id"]: case for case in old["cases"]}
        self.assertEqual(len(self.manifest["cases"]), 9)
        self.assertEqual(set(original) - {case["id"] for case in self.manifest["cases"]},
                         {"pipeline:two-leaf-batch-integrated"})
        for case in self.manifest["cases"]:
            self.assertEqual(case["metric"], "proof_stage_seconds")
            previous = dict(original[case["id"]])
            previous.pop("metric", None)
            current = dict(case)
            current.pop("metric")
            self.assertEqual(current, previous)

    def test_all_backend_timer_owners_are_outside_the_edit_surface(self):
        check_protected(self.config)
        source = ROOT / "workspace/proof-v2-source"
        if source.is_dir() and subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() == self.config["sourceCommit"]:
            for backend, item in self.config["backends"].items():
                self.assertEqual(item["timerDigest"], digest(source, item["timerFiles"]), backend)

    def test_only_proof_stages_affect_score(self):
        evidence = self.evidence()
        result = aggregate(self.config, self.manifest, self.manifest_hash, evidence)
        self.assertAlmostEqual(result["score"], 1.25)
        self.assertFalse(result["rankable"])
        self.assertEqual(len(result["per_case"]), 9)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(InvalidProofEvidence):
                write_ranked(result, Path(temporary) / "score.json")

    def test_missing_fold_and_forged_timer_are_rejected(self):
        evidence = self.evidence()
        row = next(row for row in evidence["candidate"] if row["case_id"] ==
                   "recursion:eight-distinct-pie-fold")
        row["stages"].pop()
        with self.assertRaisesRegex(InvalidProofEvidence, "incomplete circuit stages"):
            aggregate(self.config, self.manifest, self.manifest_hash, evidence)
        evidence = self.evidence()
        evidence["candidate"][0]["timer_digest"] = "0" * 64
        with self.assertRaisesRegex(InvalidProofEvidence, "timer and host"):
            aggregate(self.config, self.manifest, self.manifest_hash, evidence)

    def test_rank_gate_uses_only_proof_noise(self):
        config = copy.deepcopy(self.config)
        config["status"] = "active"
        result = aggregate(config, self.manifest, self.manifest_hash, self.evidence())
        self.assertTrue(result["rankable"])
        self.assertTrue(result["promotable"])
        self.assertAlmostEqual(result["score"], 1.25)

    def test_unified_memory_peak_is_optional_but_cuda_peak_is_required(self):
        m5 = self.evidence("metal")
        for row in m5["baseline"] + m5["candidate"]:
            row.pop("peak_bytes")
        self.assertAlmostEqual(aggregate(self.config, self.manifest,
                                         self.manifest_hash, m5)["score"], 1.25)
        cuda = self.evidence("cuda")
        cuda["candidate"][0].pop("peak_bytes")
        with self.assertRaisesRegex(InvalidProofEvidence, "memory peak"):
            aggregate(self.config, self.manifest, self.manifest_hash, cuda)


if __name__ == "__main__":
    unittest.main()
