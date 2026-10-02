#!/usr/bin/env python3
"""Capture a verified, unranked Nsight CPU/GPU timeline for one public case."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.run_arm import Nvml, candidate_env, sha
from scripts.h200_experiment import host_lock, source_identity
from scripts.h200_preflight import check_host_idle, preflight
from scripts.qualify_direct_h200 import qualify_case

REPORTS = ("cuda_gpu_trace", "cuda_gpu_kern_sum", "cuda_api_sum", "nvtx_sum")


def profile_prefix(out: Path) -> list[str]:
    return ["nsys", "profile", "--trace=cuda,nvtx,osrt", "--sample=none",
            "--cpuctxsw=none", "--force-overwrite=true", "--output",
            str(out / "timeline")]


def memory_peak(trace: Path) -> dict:
    """Locate the observed whole-device peak on the command clock."""
    rows = trace.read_text().splitlines()
    if not rows or rows[0] != "elapsed_ns\tused_device_bytes" or len(rows) < 2:
        raise RuntimeError("NVML memory trace has no valid samples")
    peak_ns, peak_bytes = max((tuple(map(int, line.split("\t"))) for line in rows[1:]),
                              key=lambda sample: sample[1])
    return {"sample_peak_at_s": peak_ns / 1e9, "sample_peak_device_bytes": peak_bytes,
            "sample_count": len(rows) - 1}


def run_profile(args: argparse.Namespace) -> dict:
    lock = args.lock_file or Path(os.environ.get("STWO_H200_HOST_LOCK", "/tmp/stwo-h200-host.lock"))
    with host_lock(lock):
        return _run_profile_locked(args)


def _run_profile_locked(args: argparse.Namespace) -> dict:
    if not shutil.which("nsys"):
        raise RuntimeError("Nsight Systems CLI (nsys) is required for a timeline")
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("profile output directory must be empty")
    manifest = json.loads(args.manifest.read_text())
    case = next((item for item in manifest["cases"] if item["id"] == args.case_id), None)
    if case is None:
        raise ValueError("unknown public case ID")
    source = args.source.resolve()
    start = time.monotonic()
    prepared = preflight(mode="direct", source=source, fixtures=args.fixtures.resolve(),
                         manifest=args.manifest.resolve(), preprocessed=args.preprocessed.resolve(),
                         artifacts=args.artifacts.resolve(), verifier=args.verifier.resolve(),
                         registry_verifier=args.registry_verifier.resolve(),
                         case_ids={args.case_id})
    preparation_s = time.monotonic() - start
    identity = source_identity(source, prepared["binary_sha256"])
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "benchmark.json").read_text())
    env = candidate_env(os.environ, args.preprocessed, args.artifacts)
    if getattr(args, "lookahead", False):
        env["STWO_CAIRO_CUDA_SOURCE_LOOKAHEAD"] = "1"
    if getattr(args, "retain_fixed_host", False):
        env["STWO_CAIRO_CUDA_RETAIN_FIXED_HOST"] = "1"
    check_host_idle()
    nvml = Nvml(config["hardware"]["deviceBytes"])
    try:
        try:
            row = qualify_case(case, source, args.fixtures.resolve(), out / "proof",
                               args.verifier.resolve(), args.registry_verifier.resolve(), nvml,
                               env, command_prefix=profile_prefix(out), capture_memory_trace=True)
        except Exception as error:
            failure = {"schema": "stwo-h200-profile-error-v1", "case_id": args.case_id,
                       "source": identity, "preparation_s": preparation_s,
                       "error": f"{type(error).__name__}: {error}",
                       "partial_artifacts": [str(path.relative_to(out)) for path in
                                             sorted(out.rglob("*")) if path.is_file()]}
            (out / "profile-error.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
            raise
    finally:
        nvml.close()
    report = out / "timeline.nsys-rep"
    if not report.is_file():
        raise RuntimeError("Nsight did not publish timeline.nsys-rep")
    stats = {}
    for name in REPORTS:
        result = subprocess.run(["nsys", "stats", "--report", name, "--format", "csv",
                                 str(report)], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            path = out / f"{name}.csv"
            path.write_text(result.stdout)
            stats[name] = {"path": path.name, "sha256": sha(path)}
        else:
            stats[name] = {"error": result.stderr.strip()[-1000:]}
    if "path" not in stats["cuda_gpu_trace"]:
        raise RuntimeError("Nsight did not provide a CUDA GPU trace; inspect the .nsys-rep")
    trace = out / "proof/_measurements" / args.case_id.replace(":", "_") / "memory_trace.tsv"
    if not trace.is_file():
        raise RuntimeError("NVML memory timeline was not captured")
    memory = memory_peak(trace)
    receipt = {"schema": "stwo-h200-profile-v1", "qualification": "unranked-profiler-diagnostic",
               "case_id": args.case_id, "source": identity, "preflight": prepared,
               "source_options": {"lookahead": getattr(args, "lookahead", False),
                                  "retain_fixed_host": getattr(args, "retain_fixed_host", False)},
               "preparation_s": preparation_s,
               "profiled_command_s": row["time_s"],
               "profile_overhead_warning": "Nsight collection and export alter command time; use unprofiled paired runs for performance claims",
               "warm_proof_s": None,
               "peak_device_bytes": row["peak_device_bytes"],
               "idle_device_bytes": row["idle_device_bytes"],
               "planned_arena_bytes": row["planned_arena_bytes"],
               "memory_trace_summary": memory,
               "phase_seconds": row["phase_seconds"],
               "ingress_stage_seconds": row["ingress_stage_seconds"],
               "proof_sha256": row["proof_sha256"],
               "verifier_results": row["verifier_results"],
               "timeline_sha256": sha(report),
               "memory_trace": {"path": str(trace.relative_to(out)), "sha256": sha(trace)},
               "statistics": stats}
    (out / "profile.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "workspace/stwo-zig")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path,
                        help="exclusive host lock shared with h200_experiment.py")
    parser.add_argument("--lookahead", action="store_true",
                        help="profile the source-lookahead candidate option")
    parser.add_argument("--retain-fixed-host", action="store_true",
                        help="profile retained fixed host data across campaign roots")
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
        print(json.dumps(run_profile(args), indent=2, sort_keys=True))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"H200 profile failed: {error}\n")


if __name__ == "__main__":
    main()
