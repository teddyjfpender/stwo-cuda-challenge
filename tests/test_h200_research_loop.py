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
    def test_prepare_checks_assets_without_needing_a_gpu_or_sandbox(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = json.loads((preflight.ROOT / "benchmark.json").read_text())
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"contract_epoch": contract["contractEpoch"],
                                            "source_commit": contract["sourceCommit"],
                                            "cases": [{"id": "pie:test", "family": "pie"}]}))
            for name in ("zig-out/bin/stwo-cairo-cuda",
                         "zig-out/bin/stwo-circuit-recursion-cuda", "verifier", "registry"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"binary")
                path.chmod(0o755)
            asset = root / "asset"
            asset.write_bytes(b"asset")

            def output(*command):
                return "0.15.2" if command == ("zig", "version") else "version"

            def digest(path):
                return (preflight.PREPROCESSED_SHA256 if path == asset
                        else "a" * 64)

            with patch.object(preflight.shutil, "which", return_value="/usr/bin/tool"), \
                 patch.object(preflight, "command_output", side_effect=output), \
                 patch.object(preflight, "cuda_build_options", return_value=["-Dcuda-arch=90"]), \
                 patch.object(preflight, "check_build_cache", return_value={"archive": "/cache"}), \
                 patch.object(preflight, "check_source", return_value={"source_commit": contract["sourceCommit"]}), \
                 patch.object(preflight, "items", return_value=[]), \
                 patch.object(preflight, "sha", side_effect=digest), \
                 patch.object(preflight, "Nvml") as nvml, \
                 patch.object(preflight, "check_no_gpu_processes") as gpu_processes:
                receipt = preflight.preflight(mode="prepare", source=root, fixtures=root,
                                              manifest=manifest, preprocessed=asset,
                                              artifacts=root, verifier=root / "verifier",
                                              registry_verifier=root / "registry")
            self.assertEqual(receipt["mode"], "prepare")
            self.assertEqual(receipt["gpu_check"], "deferred to direct or judge preflight")
            nvml.assert_not_called()
            gpu_processes.assert_not_called()

    def test_concurrent_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)
            process = proc / "999999"
            process.mkdir()
            (process / "cmdline").write_bytes(b"/usr/local/cuda/bin/nvcc\0file.cu\0")
            with self.assertRaisesRegex(RuntimeError, "nvcc pid=999999"):
                preflight.check_no_other_builds(proc)

    def test_compute_context_is_rejected_even_with_low_idle_memory(self):
        with patch.object(preflight.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             patch.object(preflight, "command_output", return_value="12345"):
            with self.assertRaisesRegex(RuntimeError, "active compute processes"):
                preflight.check_no_gpu_processes()

    def test_direct_reuses_only_unchanged_fully_hashed_shared_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = json.loads((preflight.ROOT / "benchmark.json").read_text())
            fixture = root / "test.cpi"
            fixture.write_bytes(b"PIE")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"contract_epoch": config["contractEpoch"],
                                            "source_commit": config["sourceCommit"],
                                            "cases": [{"id": "pie:test", "family": "pie",
                                                       "input": {"path": "test.cpi",
                                                                 "sha256": "a" * 64}}]}))
            asset = root / "asset"
            asset.write_bytes(b"fixed")
            for name in ("zig-out/bin/stwo-cairo-cuda",
                         "zig-out/bin/stwo-circuit-recursion-cuda", "verifier", "registry"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"binary")
                path.chmod(0o755)

            def output(*command):
                return "0.15.2" if command == ("zig", "version") else "version"

            def digest(path):
                return (preflight.PREPROCESSED_SHA256 if path == asset
                        else "b" * 64)

            class FakeNvml:
                def __init__(self, _expected):
                    pass

                def read(self):
                    return type("Memory", (), {"used": 0})()

                def close(self):
                    pass

            with patch.object(preflight.shutil, "which", return_value="/usr/bin/tool"), \
                 patch.object(preflight, "command_output", side_effect=output), \
                 patch.object(preflight, "cuda_build_options", return_value=["-Dcuda-arch=90"]), \
                 patch.object(preflight, "check_build_cache", return_value={"archive": "/cache"}), \
                 patch.object(preflight, "check_source", return_value={"source_commit": config["sourceCommit"]}), \
                 patch.object(preflight, "checked_file") as checked, \
                 patch.object(preflight, "sha", side_effect=digest) as hashed, \
                 patch.object(preflight, "Nvml", FakeNvml), \
                 patch.object(preflight, "check_host_idle"):
                def run(prior=None):
                    return preflight.preflight(mode="direct", source=root, fixtures=root,
                                               manifest=manifest, preprocessed=asset,
                                               artifacts=root, verifier=root / "verifier",
                                               registry_verifier=root / "registry",
                                               shared_asset_attestation=prior)

                first = run()
                second = run(first)
                self.assertEqual(second["shared_asset_verification"],
                                 "reused-full-sha256-with-file-identity")
                self.assertEqual(checked.call_count, 1)
                self.assertEqual(sum(call.args[0] == asset for call in hashed.call_args_list), 1)
                fixture.write_bytes(b"changed PIE")
                with self.assertRaisesRegex(RuntimeError, "shared direct-run assets changed"):
                    run(first)

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
        experiment.validate_stage("pie", "source_ns")
        experiment.validate_stage("recursion", "circuit_resident_ns")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            experiment.validate_stage("recursion", "source_ns")

    def test_candidate_options_are_isolated_from_baseline_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cases": [
                {"id": "pie:test", "family": "pie"},
                {"id": "pipeline:test", "family": "pipeline", "mode": "batch_integrated"}]}))
            args = Namespace(out=root / "out", manifest=manifest,
                             baseline=root / "baseline", candidate=root / "candidate",
                             fixtures=root, preprocessed=root / "asset", artifacts=root,
                             verifier=root / "verifier", registry_verifier=root / "registry",
                             smoke_pie="pie:test", smoke_companion="pipeline:test",
                             target_case="pipeline:test", rounds=1, full_rounds=1,
                             full_if_promising=False, hypothesis="source overlap",
                             stage="full-command", min_stage_gain=0.0,
                             max_companion_regression=.05, candidate_lookahead=True)
            seen = []

            def fake_case(case, source, _fixtures, _out, _verifier, _registry, _nvml, env):
                seen.append((source.name, dict(env)))
                return {"case_id": case["id"], "time_s": 1.0,
                        "phase_seconds": {}, "peak_device_bytes": 1,
                        "proof_sha256": {}, "verified": True}

            with patch.object(experiment, "preflight", side_effect=lambda **kw: {
                    "binary_sha256": {"product": kw["source"].name}}), \
                 patch.object(experiment, "source_identity", side_effect=lambda source, _hashes: {
                    "commit": "pinned", "binary_sha256": {"product": source.name},
                    "tracked_diff_sha256": source.name}), \
                 patch.object(experiment, "qualify_case", side_effect=fake_case), \
                 patch.object(experiment, "check_host_idle"), \
                 patch.object(experiment, "Nvml") as nvml, \
                 patch.object(experiment, "sha", return_value="hash"):
                nvml.return_value.close.return_value = None
                experiment.run_experiment(args)
            for arm, env in seen:
                self.assertEqual(env.get("STWO_CAIRO_CUDA_SOURCE_LOOKAHEAD"),
                                 "1" if arm == "candidate" else None)
            args.target_case = "pie:test"
            args.out = root / "invalid"
            with patch.object(experiment, "preflight") as prepared:
                with self.assertRaisesRegex(ValueError, "batch-integrated pipeline target"):
                    experiment.run_experiment(args)
                prepared.assert_not_called()

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
            new_file = root / "src/products/cairo_cuda/experiment.zig"
            new_file.parent.mkdir(parents=True)
            new_file.write_text("candidate source\n")
            with_untracked = experiment.source_identity(root, {"binary": "a"})
            self.assertIn("src/products/cairo_cuda/experiment.zig",
                          with_untracked["untracked_source_sha256"])

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
                 patch.object(experiment, "check_host_idle"), \
                 patch.object(experiment, "Nvml", FakeNvml), \
                 patch.object(experiment, "sha", return_value="hash"):
                gate = experiment.run_experiment(args)
            self.assertFalse(gate["passes"])
            self.assertEqual(len(calls), 8)  # ABBA smoke only; never the extra case.
            self.assertFalse(any(case == "pipeline:extra" for case, _ in calls))
            self.assertEqual(len((root / "out/runs.jsonl").read_text().splitlines()), 8)
            args.out = root / "failed"
            with patch.object(experiment, "preflight", side_effect=fake_preflight), \
                 patch.object(experiment, "source_identity", side_effect=fake_identity), \
                 patch.object(experiment, "qualify_case", side_effect=RuntimeError("verifier rejected")), \
                 patch.object(experiment, "check_host_idle"), \
                 patch.object(experiment, "Nvml", FakeNvml):
                with self.assertRaisesRegex(RuntimeError, "verifier rejected"):
                    experiment.run_experiment(args)
            failed = json.loads((root / "failed/runs.jsonl").read_text().splitlines()[0])
            self.assertEqual(failed["status"], "failed")
            self.assertFalse(failed["verified"])
            self.assertEqual(failed["source"]["commit"], "pinned")
            args.out = root / "accepted"

            def improving_case(case, source, fixtures, out, verifier, registry, nvml, env):
                row = fake_case(case, source, fixtures, out, verifier, registry, nvml, env)
                if source.name == "candidate":
                    row["time_s"] = 9
                return row

            with patch.object(experiment, "preflight", side_effect=fake_preflight), \
                 patch.object(experiment, "source_identity", side_effect=fake_identity), \
                 patch.object(experiment, "qualify_case", side_effect=improving_case), \
                 patch.object(experiment, "check_host_idle"), \
                 patch.object(experiment, "Nvml", FakeNvml), \
                 patch.object(experiment, "sha", return_value="hash"):
                accepted = experiment.run_experiment(args)
            self.assertTrue(accepted["passes"])
            self.assertEqual(len((root / "accepted/runs.jsonl").read_text().splitlines()), 14)
            self.assertEqual(sum(case == "pipeline:extra" for case, _ in calls), 2)

    def test_lock_excludes_a_second_experiment(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "host.lock"
            with experiment.host_lock(lock):
                with self.assertRaisesRegex(RuntimeError, "host lock is held"):
                    with experiment.host_lock(lock):
                        pass

    def test_failure_evidence_keeps_measurement_and_unverified_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = root / "pie_test"
            case.mkdir()
            (case / "proof.json").write_bytes(b"partial proof")
            (case / "backend.json").write_text(json.dumps({"completed_trials": [{
                "ingress_ns": 2_000_000_000,
                "ingress_timings": {"source_ns": 500_000_000}}]}))
            verdict = case / "verification/official-verdict.json"
            verdict.parent.mkdir()
            verdict.write_text('{"verified": false}')
            measure = root / "_measurements/pie_test"
            measure.mkdir(parents=True)
            (measure / "measurement.json").write_text(json.dumps({
                "time_s": 3.5, "peak_device_bytes": 1234, "exit_code": 0}))
            row = experiment.failure_evidence(root, "pie:test")
            self.assertEqual(row["time_s"], 3.5)
            self.assertEqual(row["peak_device_bytes"], 1234)
            self.assertEqual(row["phase_seconds"]["backend.json:ingress_ns"], 2)
            self.assertFalse(row["verifier_results"]["official_rust_cairo"])
            self.assertEqual(row["unverified_output_sha256"]["pie_test/proof.json"],
                             experiment.sha(case / "proof.json"))


if __name__ == "__main__":
    unittest.main()
