#!/usr/bin/env python3
"""Run a verified, unranked H200 A/B smoke before an optional full basket.

Both arms use cold processes and canonical proof checks. The driver writes a
JSONL row after every completed run, so failed experiments retain their exact
source/build identity and the last successful proof. It never issues scores.
"""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.run_arm import Nvml, candidate_env, sha
from scripts.h200_preflight import check_host_idle, preflight
from scripts.qualify_direct_h200 import qualify_case

PIE_STAGES = frozenset({"ingress_ns", "proof_execute_and_decode_ns",
                        "adapted_input_until_publication_ns", "paths_ns", "runtime_ns",
                        "source_ns", "controllers_ns", "twiddles_ns", "allocation_ns",
                        "binding_ns", "static_ns", "writers_ns",
                        "statement_and_session_ns"})
CIRCUIT_STAGES = frozenset({"circuit_resident_ns", "circuit_verify_ns",
                            "circuit_convert_ns"})


def validate_stage(family: str, stage: str) -> None:
    allowed = {"full-command"}
    if family == "pie":
        allowed.update(PIE_STAGES)
    elif family in ("recursion", "pipeline"):
        allowed.update(CIRCUIT_STAGES)
        if family == "pipeline":
            allowed.update(f"cairo_leaf_{key}_sum" for key in
                            ("ingress_ns", "proof_execute_and_decode_ns",
                            "adapted_input_until_publication_ns"))
    if stage not in allowed:
        raise ValueError(f"stage {stage} is unavailable for {family}; choose from {sorted(allowed)}")


@contextmanager
def host_lock(path: Path):
    """Hold one host-wide experiment slot across preflight and all A/B runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"H200 host lock is held: {path}") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def failure_evidence(run_root: Path, case_id: str) -> dict:
    """Retain measured evidence when execution or exact verification fails."""
    case_name = case_id.replace(":", "_")
    case_dir = run_root / case_name
    measure_dir = run_root / "_measurements" / case_name
    evidence = {"phase_seconds": {}, "ingress_stage_seconds": {},
                "unverified_output_sha256": {},
                "verifier_results": {"independent_verification": "not_completed"}}
    measurement = measure_dir / "measurement.json"
    if measurement.is_file():
        measured = json.loads(measurement.read_text())
        evidence.update({key: measured[key] for key in
                         ("time_s", "peak_device_bytes", "idle_device_bytes", "nvml_samples",
                          "exit_code", "timed_out") if key in measured})
    for report in [case_dir / "backend.json", *(case_dir / "result").glob("*.cairo_report.json")]:
        if report.is_file():
            trials = json.loads(report.read_text()).get("completed_trials", [])
            if len(trials) == 1:
                trial = trials[0]
                for key in ("ingress_ns", "proof_execute_and_decode_ns",
                            "adapted_input_until_publication_ns", "source_lookahead_prepare_ns",
                            "source_lookahead_wait_ns"):
                    if key in trial:
                        evidence["phase_seconds"][f"{report.name}:{key}"] = trial[key] / 1e9
                for key, value in trial.get("ingress_timings", {}).items():
                    evidence["ingress_stage_seconds"][f"{report.name}:{key}"] = value / 1e9
    for path in (case_dir / "proof.json", case_dir / "root.proof",
                 case_dir / "result/root.proof", *(case_dir / "result").glob("*.cairo_proof.json")):
        if path.is_file():
            evidence["unverified_output_sha256"][str(path.relative_to(run_root))] = sha(path)
    official = case_dir / "verification/official-verdict.json"
    if official.is_file():
        evidence["verifier_results"]["official_rust_cairo"] = json.loads(
            official.read_text()).get("verified")
    registry_logs = sorted(case_dir.glob("cairo-verification-*/registry-verdict.log"))
    if registry_logs:
        evidence["verifier_results"]["registry_rust_cairo_leaves"] = [
            log.read_text().startswith("RUST_CAIRO_VERIFIER=accepted ") for log in registry_logs]
    return evidence


def source_identity(source: Path, binary_sha256: dict) -> dict:
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                   text=True).strip()
    patch = subprocess.check_output(["git", "-C", str(source), "diff", "--binary", "HEAD"])
    untracked = subprocess.check_output(["git", "-C", str(source), "ls-files", "--others",
                                         "--exclude-standard", "-z"]).split(b"\0")
    editable = tuple(json.loads((ROOT / "benchmark.json").read_text())["editablePaths"])
    files = {}
    for raw in untracked:
        if not raw:
            continue
        name = os.fsdecode(raw)
        if any(name == path or name.startswith(path + "/") for path in editable):
            files[name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
    return {"commit": head, "tracked_diff_sha256": hashlib.sha256(patch).hexdigest(),
            "untracked_source_sha256": files, "binary_sha256": binary_sha256}


def metric(row: dict, stage: str) -> float | None:
    if stage == "full-command":
        return row["time_s"]
    if stage in row.get("phase_seconds", {}):
        return row["phase_seconds"][stage]
    return row.get("ingress_stage_seconds", {}).get(stage)


def paired_gain(rows: list[dict], case_id: str, stage: str) -> float:
    by_arm = {arm: [metric(row, stage) for row in rows if row["case_id"] == case_id
                    and row["arm"] == arm] for arm in ("baseline", "candidate")}
    if not by_arm["baseline"] or len(by_arm["baseline"]) != len(by_arm["candidate"]):
        raise ValueError(f"unpaired case: {case_id}")
    if any(value is None or value <= 0 for values in by_arm.values() for value in values):
        raise ValueError(f"requested stage {stage} is unavailable for {case_id}")
    return 1 - statistics.median(by_arm["candidate"]) / statistics.median(by_arm["baseline"])


def run_experiment(args: argparse.Namespace) -> dict:
    lock = Path(getattr(args, "lock_file", None) or
                os.environ.get("STWO_H200_HOST_LOCK", "/tmp/stwo-h200-host.lock"))
    with host_lock(lock):
        return _run_experiment_locked(args)


def _run_experiment_locked(args: argparse.Namespace) -> dict:
    if args.rounds < 1 or args.full_rounds < 1:
        raise ValueError("round counts must be positive")
    min_command_gain = getattr(args, "min_target_command_gain", 0.0)
    if (not 0 <= args.min_stage_gain < 1 or
            not 0 <= min_command_gain < 1 or args.max_companion_regression < 0):
        raise ValueError("invalid gain or regression threshold")
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("experiment output directory must be empty")
    manifest = json.loads(args.manifest.read_text())
    case_map = {case["id"]: case for case in manifest["cases"]}
    smoke_ids = [args.smoke_pie, args.smoke_companion]
    if len(set(smoke_ids)) != 2 or any(case_id not in case_map for case_id in smoke_ids):
        raise ValueError("smoke cases must be distinct known cases")
    if case_map[args.smoke_pie]["family"] != "pie" or case_map[args.smoke_companion]["family"] not in ("recursion", "pipeline"):
        raise ValueError("smoke cases must contain one PIE and one fold/pipeline")
    target_case = getattr(args, "target_case", None) or args.smoke_pie
    if target_case not in smoke_ids:
        raise ValueError("target case must be one of the two smoke cases")
    validate_stage(case_map[target_case]["family"], args.stage)
    if getattr(args, "candidate_lookahead", False) and (
            case_map[target_case]["family"] != "pipeline" or
            case_map[target_case].get("mode") != "batch_integrated"):
        raise ValueError("candidate source lookahead requires a batch-integrated pipeline target")
    companion_case = args.smoke_companion if target_case == args.smoke_pie else args.smoke_pie
    paths = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    preparation_started = time.monotonic_ns()
    preflights = {}
    for arm, source in paths.items():
        preflights[arm] = preflight(
            mode="direct", source=source, fixtures=args.fixtures.resolve(),
            manifest=args.manifest.resolve(), preprocessed=args.preprocessed.resolve(),
            artifacts=args.artifacts.resolve(), verifier=args.verifier.resolve(),
            registry_verifier=args.registry_verifier.resolve(),
            case_ids=None if arm == "baseline" and args.full_if_promising else set(smoke_ids),
            shared_asset_attestation=preflights.get("baseline") if arm == "candidate" else None)
    identities = {arm: source_identity(paths[arm], preflights[arm]["binary_sha256"])
                  for arm in paths}
    if identities["baseline"]["binary_sha256"] == identities["candidate"]["binary_sha256"]:
        raise ValueError("baseline and candidate executable hashes are identical")
    preparation_seconds = (time.monotonic_ns() - preparation_started) / 1e9
    out.mkdir(parents=True, exist_ok=True)
    header = {"schema": "stwo-h200-direct-experiment-v1", "qualification": "direct-unranked-unsandboxed",
              "hypothesis": args.hypothesis, "target_case": target_case,
              "target_stage": args.stage,
              "preparation_seconds": preparation_seconds,
              "min_stage_gain": args.min_stage_gain,
              "min_target_command_gain": min_command_gain,
              "max_companion_regression": args.max_companion_regression,
              "candidate_options": {"source_lookahead": getattr(args, "candidate_lookahead", False)},
              "timing_boundaries": {
                  "preparation": "fixture/build/preflight before measured proof commands; not timed",
                  "cold_input_to_publication": "NVML-sampled fresh process from adapted CPI to published proof and exit",
                  "warm_proof": "not measured; requires a separate resident-service protocol and new epoch",
                  "internal_phases": "candidate-reported diagnostics; not trusted rank timers"},
              "sources": identities, "preflight": preflights}
    (out / "experiment.json").write_text(json.dumps(header, indent=2, sort_keys=True) + "\n")
    common_env = candidate_env(os.environ, args.preprocessed, args.artifacts)
    candidate_options = {}
    if getattr(args, "candidate_lookahead", False):
        candidate_options["STWO_CAIRO_CUDA_SOURCE_LOOKAHEAD"] = "1"
    envs = {"baseline": common_env, "candidate": {**common_env, **candidate_options}}
    config = json.loads((ROOT / "benchmark.json").read_text())
    nvml = Nvml(config["hardware"]["deviceBytes"])
    rows = []
    try:
        with (out / "runs.jsonl").open("w") as journal:
            def one(arm: str, case_id: str, phase: str, round_number: int) -> None:
                index = len(rows)
                run_root = out / "proofs" / f"{index:04d}-{arm}"
                try:
                    check_host_idle()
                    row = qualify_case(case_map[case_id], paths[arm], args.fixtures.resolve(),
                                       run_root, args.verifier.resolve(),
                                       args.registry_verifier.resolve(), nvml, envs[arm])
                except Exception as error:
                    row = {"case_id": case_id, "family": case_map[case_id]["family"],
                           "status": "failed", "error": f"{type(error).__name__}: {error}",
                           "qualification": "direct-unranked-unsandboxed",
                           "verified": False, "arm": arm, "phase": phase,
                           "round": round_number, "source": identities[arm],
                           "measurement_kind": "cold-input-to-publication"}
                    try:
                        row.update(failure_evidence(run_root, case_id))
                    except Exception as inspection_error:
                        row["evidence_read_error"] = str(inspection_error)
                    journal.write(json.dumps(row, sort_keys=True) + "\n")
                    journal.flush()
                    os.fsync(journal.fileno())
                    raise
                row.update(arm=arm, phase=phase, round=round_number,
                           source=identities[arm], status="passed",
                           measurement_kind="cold-input-to-publication")
                rows.append(row)
                journal.write(json.dumps(row, sort_keys=True) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                print(f"{phase} {round_number} {arm} {case_id}: {row['time_s']:.3f}s", flush=True)

            for round_number in range(args.rounds):
                order = ("baseline", "candidate", "candidate", "baseline")
                for arm in order:
                    for case_id in smoke_ids:
                        one(arm, case_id, "smoke", round_number)
            smoke = [row for row in rows if row["phase"] == "smoke"]
            stage_gain = paired_gain(smoke, target_case, args.stage)
            target_command_gain = paired_gain(smoke, target_case, "full-command")
            companion_gain = paired_gain(smoke, companion_case, "full-command")
            credible = (stage_gain >= args.min_stage_gain and
                        target_command_gain >= min_command_gain and
                        companion_gain >= -args.max_companion_regression)
            gate = {"target_case": target_case, "target_stage_gain": stage_gain,
                    "target_command_gain": target_command_gain,
                    "companion_case": companion_case, "companion_command_gain": companion_gain,
                    "passes": credible, "full_basket_requested": args.full_if_promising}
            (out / "gate.json").write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n")
            if args.full_if_promising and credible:
                for round_number in range(args.full_rounds):
                    for arm in ("baseline", "candidate") if round_number % 2 == 0 else ("candidate", "baseline"):
                        for case in manifest["cases"]:
                            one(arm, case["id"], "full", round_number)
            for arm, source in paths.items():
                hashes = {path.name: sha(path) for path in (
                    source / "zig-out/bin/stwo-cairo-cuda",
                    source / "zig-out/bin/stwo-circuit-recursion-cuda",
                    args.verifier.resolve(), args.registry_verifier.resolve())}
                if source_identity(source, hashes) != identities[arm]:
                    raise RuntimeError(f"{arm} tracked source changed during experiment")
            return gate
    finally:
        nvml.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path,
                        help="exclusive host lock (default STWO_H200_HOST_LOCK or /tmp/stwo-h200-host.lock)")
    parser.add_argument("--hypothesis", required=True,
                        help="one sentence naming expected mechanism and measured stage")
    parser.add_argument("--stage", default="full-command",
                        help="PIE phase key, ingress substage key, or full-command")
    parser.add_argument("--min-stage-gain", type=float, required=True,
                        help="minimum PIE target-stage fractional reduction, e.g. 0.05")
    parser.add_argument("--min-target-command-gain", type=float, default=0.0,
                        help="minimum cold full-command gain on target case (default: no regression)")
    parser.add_argument("--max-companion-regression", type=float, default=0.05)
    parser.add_argument("--smoke-pie", default="pie:15581148_15581148")
    parser.add_argument("--smoke-companion", default="recursion:two-leaf-wrap-fold")
    parser.add_argument("--target-case",
                        help="the smoke PIE or fold/pipeline case whose stated stage must improve")
    parser.add_argument("--candidate-lookahead", action="store_true",
                        help="enable opt-in in-command source lookahead only for the candidate")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--full-if-promising", action="store_true")
    parser.add_argument("--full-rounds", type=int, default=1)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "data/inputs")
    parser.add_argument("--manifest", type=Path, default=ROOT / "fixtures/public-v1.json")
    parser.add_argument("--preprocessed", type=Path,
                        default=ROOT / ".cache/preprocessed-canonical.bin")
    parser.add_argument("--artifacts", type=Path, default=ROOT / ".cache/cuda-artifacts")
    parser.add_argument("--verifier", type=Path,
                        default=ROOT / ".cache/rust-official/release/stwo-cairo-official-verifier")
    parser.add_argument("--registry-verifier", type=Path,
                        default=ROOT / ".cache/rust-registry/release/verify_cairo_cuda_json")
    args = parser.parse_args()
    try:
        print(json.dumps(run_experiment(args), indent=2, sort_keys=True))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"H200 experiment failed: {error}\n")


if __name__ == "__main__":
    main()
