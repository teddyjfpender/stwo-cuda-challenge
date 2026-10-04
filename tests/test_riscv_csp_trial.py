"""Security and scoring boundaries for the staged RISC-V CSP track."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.riscv_csp_trial import contract, expected_cases, validate_report, compare, preflight_binary


class CspTrialTests(unittest.TestCase):
    def setUp(self):
        self.config = contract()
        self.manifest = json.loads(Path(self.config["fixtureManifest"]).read_text())
        self.cases = expected_cases(self.manifest)

    def report(self, factor=1, commit="a" * 40):
        rows = []
        pcs = {"fri_config": {"n_queries": 70}, "pow_bits": 26}
        for (target, size), case in self.cases.items():
            precompile = target == "ecdsa_secp256k1"
            evidence = {"input_sha256": case["input_sha256"],
                        "output_digest": case["expected_digest"], "status": "verified"}
            if precompile:
                evidence["precompile_manifest_sha256"] = self.config["precompileManifestSha256"]
            rows.append({"target": target, "input_size": size,
                         "cycles": 100 if precompile else case["expected_cycles"],
                         "evidence": evidence, "recursion_enabled": False,
                         "uses_precompile": precompile, "proof_duration": 1_000_000_000 // factor,
                         "protocol": {"proof_suite": "blake3", "pcs_config": pcs}})
        return {"schema": "stwo_riscv_csp_accelerated_benchmark_v1",
                "suite_manifest_sha256": self.config["fixtureManifestSha256"],
                "proof_suite": "blake3", "methodology": {"execution_mode": "precompile"},
                "run": {"backend": "cpu", "recursion_enabled": False, "complete_matrix": True},
                "security": {"pcs_config": pcs}, "measurement_commit": commit,
                "host": {"architecture": "arm64", "cpu": "Apple M5 Max", "memory_bytes": 64 << 30},
                "summary": {field: True for field in (
                    "all_outputs_match", "all_proofs_verified", "all_recursion_disabled",
                    "all_negative_proofs_verified", "all_negative_fixtures_rejected")},
                "measurements": rows}

    def test_complete_authenticated_precompile_matrix(self):
        rows = validate_report(self.report(), self.config, self.manifest,
                               backend="cpu", complete=True)
        self.assertEqual(len(rows), 16)

    def test_ecdsa_software_or_missing_case_cannot_pass(self):
        report = self.report()
        report["measurements"][-1]["uses_precompile"] = False
        with self.assertRaisesRegex(ValueError, "precompile"):
            validate_report(report, self.config, self.manifest, backend="cpu", complete=True)
        report = self.report()
        report["measurements"].pop()
        with self.assertRaisesRegex(ValueError, "case set"):
            validate_report(report, self.config, self.manifest, backend="cpu", complete=True)

    def test_security_and_output_changes_fail(self):
        report = self.report()
        report["security"]["pcs_config"]["pow_bits"] = 25
        with self.assertRaisesRegex(ValueError, "security"):
            validate_report(report, self.config, self.manifest, backend="cpu", complete=True)
        report = self.report()
        report["measurements"][0]["evidence"]["output_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "canonical"):
            validate_report(report, self.config, self.manifest, backend="cpu", complete=True)

    def test_four_targets_have_equal_weight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before, after, result = (root / name for name in ("before.json", "after.json", "result.json"))
            before.write_text(json.dumps(self.report(commit=self.config["sourceCommit"])))
            candidate = self.report(commit="b" * 40)
            for row in candidate["measurements"]:
                if row["target"] == "ecdsa_secp256k1":
                    row["proof_duration"] //= 16
            after.write_text(json.dumps(candidate))
            args = type("Args", (), {"backend": "cpu", "baseline": before,
                                      "candidate": after, "out": result})()
            compare(args, self.config)
            self.assertAlmostEqual(json.loads(result.read_text())["family_weighted_speedup"], 2.0)

    def test_stale_binary_rejected_before_full_matrix(self):
        registry = {"product": {"backend": "cpu", "optimize": "ReleaseFast",
                                "source": {"commit": "old", "dirty": False}}}
        with self.assertRaisesRegex(ValueError, "stale"):
            preflight_binary(registry, backend="cpu", commit=self.config["sourceCommit"])
        registry["product"]["source"]["commit"] = self.config["sourceCommit"]
        preflight_binary(registry, backend="cpu", commit=self.config["sourceCommit"])


if __name__ == "__main__":
    unittest.main()
