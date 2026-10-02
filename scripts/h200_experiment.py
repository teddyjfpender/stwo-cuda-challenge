#!/usr/bin/env python3
"""Run a verified, unranked H200 A/B smoke before an optional full basket.

Both arms use cold processes and canonical proof checks. The driver writes a
JSONL row after every completed run, so failed experiments retain their exact
source/build identity and the last successful proof. It never issues scores.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.run_arm import Nvml, candidate_env, sha
from scripts.h200_preflight import preflight
from scripts.qualify_direct_h200 import qualify_case


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
    if args.rounds < 1 or args.full_rounds < 1:
        raise ValueError("round counts must be positive")
    if not 0 <= args.min_stage_gain < 1 or args.max_companion_regression < 0:
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
    companion_case = args.smoke_companion if target_case == args.smoke_pie else args.smoke_pie
    paths = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    preflights = {arm: preflight(mode="direct", source=source, fixtures=args.fixtures.resolve(),
                                 manifest=args.manifest.resolve(), preprocessed=args.preprocessed.resolve(),
                                 artifacts=args.artifacts.resolve(), verifier=args.verifier.resolve(),
                                 registry_verifier=args.registry_verifier.resolve(),
                                 case_ids=None if arm == "baseline" and args.full_if_promising
                                 else set(smoke_ids)) for arm, source in paths.items()}
    identities = {arm: source_identity(paths[arm], preflights[arm]["binary_sha256"])
                  for arm in paths}
    if identities["baseline"]["binary_sha256"] == identities["candidate"]["binary_sha256"]:
        raise ValueError("baseline and candidate executable hashes are identical")
    out.mkdir(parents=True, exist_ok=True)
    header = {"schema": "stwo-h200-direct-experiment-v1", "qualification": "direct-unranked-unsandboxed",
              "hypothesis": args.hypothesis, "target_case": target_case,
              "target_stage": args.stage,
              "min_stage_gain": args.min_stage_gain,
              "max_companion_regression": args.max_companion_regression,
              "timing_boundaries": {
                  "preparation": "fixture/build/preflight before measured proof commands; not timed",
                  "cold_input_to_publication": "NVML-sampled fresh process from adapted CPI to published proof and exit",
                  "warm_proof": "not measured; requires a separate resident-service protocol and new epoch",
                  "internal_phases": "candidate-reported diagnostics; not trusted rank timers"},
              "sources": identities, "preflight": preflights}
    (out / "experiment.json").write_text(json.dumps(header, indent=2, sort_keys=True) + "\n")
    env = candidate_env(os.environ, args.preprocessed, args.artifacts)
    config = json.loads((ROOT / "benchmark.json").read_text())
    nvml = Nvml(config["hardware"]["deviceBytes"])
    rows = []
    try:
        with (out / "runs.jsonl").open("w") as journal:
            def one(arm: str, case_id: str, phase: str, round_number: int) -> None:
                index = len(rows)
                row = qualify_case(case_map[case_id], paths[arm], args.fixtures.resolve(),
                                   out / "proofs" / f"{index:04d}-{arm}", args.verifier.resolve(),
                                   args.registry_verifier.resolve(), nvml, env)
                row.update(arm=arm, phase=phase, round=round_number,
                           source=identities[arm], measurement_kind="cold-input-to-publication")
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
            companion_gain = paired_gain(smoke, companion_case, "full-command")
            credible = (stage_gain >= args.min_stage_gain and
                        companion_gain >= -args.max_companion_regression)
            gate = {"target_case": target_case, "target_stage_gain": stage_gain,
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
    parser.add_argument("--hypothesis", required=True,
                        help="one sentence naming expected mechanism and measured stage")
    parser.add_argument("--stage", default="full-command",
                        help="PIE phase key, ingress substage key, or full-command")
    parser.add_argument("--min-stage-gain", type=float, required=True,
                        help="minimum PIE target-stage fractional reduction, e.g. 0.05")
    parser.add_argument("--max-companion-regression", type=float, default=0.05)
    parser.add_argument("--smoke-pie", default="pie:15581148_15581148")
    parser.add_argument("--smoke-companion", default="recursion:two-leaf-wrap-fold")
    parser.add_argument("--target-case",
                        help="the smoke PIE or fold/pipeline case whose stated stage must improve")
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
