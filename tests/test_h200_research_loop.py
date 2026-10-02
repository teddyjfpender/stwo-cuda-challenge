"""The H200 loop must reject missing prerequisites before paid proof work."""

import json
from argparse import Namespace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import h200_experiment as experiment
from scripts import h200_preflight as preflight


class H200PreflightTests(unittest.TestCase):
    def test_judge_requires_image_before_toolchain_or_asset_hashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            contract = json.loads((preflight.ROOT / "benchmark.json").read_text())
            manifest.write_text(json.dumps({"contract_epoch": contract["contractEpoch"],
                                            "source_commit": contract["sourceCommit"],
                                            "cases": [{"id": "pie:test", "family": "pie"}]}))
            with patch.object(preflight, "check_source") as check_source:
                with self.assertRaisesRegex(RuntimeError, "requires --image"):
                    preflight.preflight(mode="judge", source=root, fixtures=root,
                                        manifest=manifest, preprocessed=root / "asset",
                                        artifacts=root, verifier=root / "verifier",
                                        registry_verifier=root / "registry")
                check_source.assert_not_called()

    def test_image_must_be_pinned_and_locally_present(self):
        with self.assertRaisesRegex(RuntimeError, "pinned SHA-256"):
            preflight.check_image("stwo-judge:latest")
        with patch.object(preflight.shutil, "which", return_value="/usr/bin/docker"), \
             patch.object(preflight, "command_output", side_effect=["27.0", "sha256:" + "b" * 64]):
            with self.assertRaisesRegex(RuntimeError, "image ID differs"):
                preflight.check_image("sha256:" + "a" * 64)

    def test_missing_mount_capability_is_explicit(self):
        with patch.object(preflight.sys, "platform", "linux"), \
             patch.object(preflight.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(preflight.os, "geteuid", return_value=0), \
             patch.object(Path, "read_text", return_value="Name: python\nCapEff: 0000000000000000\n"):
            with self.assertRaisesRegex(RuntimeError, "CAP_SYS_ADMIN"):
                preflight.check_mount_capability()


class H200ExperimentTests(unittest.TestCase):
    def test_stage_gate_separates_internal_phase_from_full_command(self):
        rows = []
        for arm, times in (("baseline", (10.0, 5.0)), ("candidate", (9.0, 4.0))):
            for _ in range(2):
                rows.append({"arm": arm, "case_id": "pie:test", "time_s": times[0],
                             "phase_seconds": {"ingress_ns": times[1]}})
        self.assertAlmostEqual(experiment.paired_gain(rows, "pie:test", "ingress_ns"), .2)
        self.assertAlmostEqual(experiment.paired_gain(rows, "pie:test", "full-command"), .1)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            experiment.paired_gain(rows, "pie:test", "proof_execute_and_decode_ns")

    def test_source_identity_captures_dirty_patch_and_binary_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.email=test@example.com",
                            "-c", "user.name=Test", "commit", "--allow-empty", "-qm", "base"],
                           check=True)
            file = root / "kernel.cu"
            file.write_text("first\n")
            subprocess.run(["git", "-C", str(root), "add", "kernel.cu"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.email=test@example.com",
                            "-c", "user.name=Test", "commit", "-qm", "kernel"], check=True)
            before = experiment.source_identity(root, {"binary": "a"})
            file.write_text("second\n")
            after = experiment.source_identity(root, {"binary": "a"})
            self.assertEqual(before["commit"], after["commit"])
            self.assertNotEqual(before["tracked_diff_sha256"], after["tracked_diff_sha256"])

    def test_full_basket_only_runs_after_smoke_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cases": [
                {"id": "pie:test", "family": "pie"},
                {"id": "recursion:test", "family": "recursion"},
                {"id": "pipeline:extra", "family": "pipeline"}]}))
            args = Namespace(out=root / "out", manifest=manifest,
                             baseline=root / "baseline", candidate=root / "candidate",
                             fixtures=root, preprocessed=root / "preprocessed", artifacts=root,
                             verifier=root / "verifier", registry_verifier=root / "registry",
                             smoke_pie="pie:test", smoke_companion="recursion:test",
                             rounds=1, full_rounds=1, full_if_promising=True,
                             hypothesis="test source stage", stage="ingress_ns",
                             min_stage_gain=.1, max_companion_regression=.05)
            calls = []

            def fake_preflight(*, source, **_kwargs):
                return {"binary_sha256": {"product": source.name}}

            def fake_identity(source, _binary_sha256):
                return {"commit": "pinned", "binary_sha256": {"product": source.name},
                        "tracked_diff_sha256": source.name}

            def fake_case(case, source, _fixtures, _out, _verifier, _registry, _nvml, _env):
                calls.append((case["id"], source.name))
                is_candidate = source.name == "candidate"
                return {"case_id": case["id"], "time_s": 11 if is_candidate else 10,
                        "phase_seconds": {"ingress_ns": 4 if is_candidate else 5},
                        "peak_device_bytes": 1, "proof_sha256": {"proof": "hash"},
                        "verified": True}

            class FakeNvml:
                def __init__(self, _bytes):
                    pass

                def close(self):
                    pass

            with patch.object(experiment, "preflight", side_effect=fake_preflight), \
                 patch.object(experiment, "source_identity", side_effect=fake_identity), \
                 patch.object(experiment, "qualify_case", side_effect=fake_case), \
                 patch.object(experiment, "Nvml", FakeNvml), \
                 patch.object(experiment, "sha", return_value="hash"):
                gate = experiment.run_experiment(args)
            self.assertFalse(gate["passes"])
            self.assertEqual(len(calls), 8)  # ABBA smoke only; never the extra case.
            self.assertFalse(any(case == "pipeline:extra" for case, _ in calls))
            self.assertEqual(len((root / "out/runs.jsonl").read_text().splitlines()), 8)


if __name__ == "__main__":
    unittest.main()
