#!/usr/bin/env python3
"""Run exact public proof-v2 cases on the M5; emit unranked stage diagnostics."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.run_arm import checked_file, sha
from harness.run_pipeline import leaf_input
from harness.timer_owner import attest

MIN_FREE_BYTES = 6_000_000_000
MAX_SECONDS = 900
FOLD = re.compile(r"reduce layer \d+ pair \d+(?: \(root\))?: build \d+ ms, prove (\d+) ms")
LEAF = re.compile(r"leaf-wrap: load ([\d.]+) s, cairo prove ([\d.]+) s, wrap ([\d.]+) s")
EXACT = re.compile(r"circuit-proof-stage kind=(cairo|wrap|fold) ns=(\d+)")


def exact_stage_ns(log: str, expected: list[str]) -> list[int]:
    entries = EXACT.findall(log)
    if entries and sorted(kind for kind, _ in entries) != sorted(expected):
        raise ValueError(f"proof-stage telemetry differs: expected {expected}, got {entries}")
    return [int(ns) for _, ns in entries]


def run(command: list[str], output: Path, environment: dict[str, str], cwd: Path) -> float:
    started = time.monotonic()
    with output.open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=environment, cwd=cwd, start_new_session=True)
        while process.poll() is None:
            if shutil.disk_usage(output.parent).free < MIN_FREE_BYTES:
                process.terminate()
                process.wait(timeout=20)
                raise RuntimeError("qualification stopped before disk space fell below 6 GB")
            if time.monotonic() - started > MAX_SECONDS:
                process.terminate()
                process.wait(timeout=20)
                raise RuntimeError(f"qualification exceeded {MAX_SECONDS} seconds")
            time.sleep(0.5)
    if process.returncode != 0:
        raise RuntimeError(f"prover exited {process.returncode}; inspect {output}")
    return time.monotonic() - started


def exact_root(case: dict, proof: Path, outputs: Path, packed: Path) -> dict:
    actual = {"proof_sha256": sha(proof), "outputs_sha256": sha(outputs),
              "packed_sha256": sha(packed)}
    if actual != case["expected_root"]:
        raise ValueError(f"{case['id']} root differs from the pinned reference: {actual}")
    return actual


def fold(source: Path, circuit: Path, fixtures: Path, case: dict, leaves: list[Path],
         out: Path, environment: dict[str, str]) -> dict:
    manifest = out / "leaves.json"
    manifest.write_text(json.dumps({"leaves": [str(path) for path in leaves]}) + "\n")
    proof, outputs, packed = (out / name for name in ("root.proof", "root_outputs.json", "root_packed.json"))
    registry = source / "vectors/circuit/official/registries/production.json"
    wall = run([str(circuit), "fold-tree", "--circuit_registry_json", str(registry),
                "--program_input", str(manifest), "--proof_path", str(proof),
                "--program_output", str(outputs), "--packed_output_path", str(packed)],
               out / "fold.log", environment, source)
    log = (out / "fold.log").read_text()
    matches = [int(value) for value in FOLD.findall(log)]
    if len(matches) != len(leaves) - 1:
        raise ValueError(f"{case['id']} fold log has {len(matches)} proof intervals")
    exact = exact_stage_ns(log, ["fold"] * (len(leaves) - 1))
    return {"root": exact_root(case, proof, outputs, packed), "command_wall_s": wall,
            "fold_prove_ms_diagnostic": matches, "fold_prove_ns": exact,
            "fold_proof_s": sum(exact) / 1e9 if exact else None}


def qualify_case(source: Path, fixtures: Path, case: dict, backend: str, out: Path,
                 timer_digest: str, binary_hashes: dict[str, str], workers: int | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    worker_count = workers if workers is not None else (4 if case.get("os_steps", 0) >= 30_000_000 else 18)
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG",
                                                  "LC_ALL", "DYLD_LIBRARY_PATH") if key in os.environ}
    environment.update({"STWO_CAIRO_COMPACT_POLYNOMIALS": "1",
                        "STWO_ZIG_WORKERS": str(worker_count), "STWO_CIRCUIT_FOLD_JOBS": "1"})
    cairo = source / f"zig-out/bin/stwo-cairo-{backend}"
    circuit = (source / "src/integrations/circuit_metal/zig-out/bin/stwo-circuit-recursion-metal"
               if backend == "metal" else source / "zig-out/bin/stwo-circuit-recursion-cpu")
    if not cairo.is_file() or not circuit.is_file():
        raise FileNotFoundError("build Cairo and circuit recursion products for this backend first")
    source_diff = subprocess.check_output(["git", "-C", str(source), "diff", "--binary", "HEAD"])
    receipt = {"schema": "stwo-m5-proof-v2-diagnostic", "backend": backend,
               "case_id": case["id"], "timer_digest": timer_digest,
               "source_commit": subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                                        text=True).strip(),
               "source_diff_sha256": hashlib.sha256(source_diff).hexdigest(),
               "cairo_binary_sha256": binary_hashes["cairo"],
               "circuit_binary_sha256": binary_hashes["circuit"],
               "input_sha256": [], "preimage_sha256": [], "worker_count": worker_count,
               "qualified_for_ranking": False}
    if case["family"] == "pie":
        cpi = checked_file(fixtures, case["input"])
        receipt["input_sha256"].append(case["input"]["sha256"])
        proof, report = out / "proof.json", out / "report.json"
        wall = run([str(cairo), "prove", "--prover-input", str(cpi), "--proof", str(proof),
                    "--report-out", str(report), "--verify"], out / "prover.log", environment, source)
        actual = sha(proof)
        if actual != case["expected_proof_sha256"]:
            raise ValueError(f"{case['id']} proof differs: {actual}")
        data = json.loads(report.read_text())
        if data["input"]["sha256"] != case["input"]["sha256"] or data["backend"] != backend:
            raise ValueError("backend report input or backend differs")
        receipt.update(proof_sha256=actual, proof_stage_s=data["timing"]["prove_ns"] / 1e9,
                       stages=[{"kind": "cairo", "seconds": data["timing"]["prove_ns"] / 1e9}],
                       command_wall_s=wall, report_sha256=sha(report),
                       physical_footprint_peak_bytes=data["prover_process_usage"].get(
                           "lifetime_peak_physical_footprint_bytes"),
                       stage_scope="shared-cairo-product-prove-ns")
    else:
        leaves = []
        if case["family"] == "recursion":
            for item in case["inputs"]:
                leaves.append(checked_file(fixtures, item))
                receipt["input_sha256"].append(item["sha256"])
        else:
            registry = source / "vectors/circuit/official/registries/production.json"
            program = source / "vectors/circuit/official/programs/leaf_simple_bootloader_compiled.json"
            leaf_timings = []
            for index, item in enumerate(case["inputs"]):
                cpi = checked_file(fixtures, item)
                preimage = checked_file(fixtures, {"path": item["preimage_path"],
                                                    "sha256": item["preimage_sha256"]})
                receipt["input_sha256"].append(item["sha256"])
                receipt["preimage_sha256"].append(item["preimage_sha256"])
                wrapped, leaf = out / f"leaf-{index}.wrapped.json", out / f"leaf-{index}.json"
                wall = run([str(circuit), "leaf-wrap", "--registry", str(registry),
                            "--program", str(program), "--prover-input", str(cpi),
                            "--output", str(wrapped), "--cairo-proof", str(out / f"leaf-{index}.cairo.json"),
                            "--assets", str(source)],
                           out / f"leaf-{index}.log", environment, source)
                leaf_input(wrapped, preimage, leaf)
                log = (out / f"leaf-{index}.log").read_text()
                match = LEAF.search(log)
                if match is None:
                    raise ValueError(f"leaf-{index} timings missing")
                exact = exact_stage_ns(log, ["cairo", "wrap"])
                intervals = {kind: int(ns) for kind, ns in EXACT.findall(log)} if exact else {}
                item_timings = {"command_wall_s": wall,
                                "cairo_plus_assets_s": float(match.group(2)),
                                "wrap_plus_setup_s": float(match.group(3))}
                if "cairo" in intervals and "wrap" in intervals:
                    item_timings.update(cairo_proof_s=intervals["cairo"] / 1e9,
                                        wrap_proof_s=intervals["wrap"] / 1e9)
                leaf_timings.append(item_timings)
                leaves.append(leaf)
            receipt["leaf_timing_diagnostics"] = leaf_timings
        fold_result = fold(source, circuit, fixtures, case, leaves, out, environment)
        receipt.update(fold_result)
        if case["family"] == "recursion" and fold_result["fold_proof_s"] is not None:
            receipt["proof_stage_s"] = fold_result["fold_proof_s"]
            receipt["stages"] = [{"kind": "fold", "seconds": ns / 1e9}
                                  for ns in fold_result["fold_prove_ns"]]
            receipt["stage_scope"] = "exact-fold-call-boundaries"
        elif case["family"] == "pipeline" and fold_result["fold_proof_s"] is not None and all(
                "cairo_proof_s" in item and "wrap_proof_s" in item for item in leaf_timings):
            receipt["fold_command_wall_s"] = fold_result["command_wall_s"]
            receipt["command_wall_s"] += sum(item["command_wall_s"] for item in leaf_timings)
            receipt["proof_stage_s"] = fold_result["fold_proof_s"] + sum(
                item["cairo_proof_s"] + item["wrap_proof_s"] for item in leaf_timings)
            receipt["stages"] = [stage for item in leaf_timings for stage in (
                {"kind": "cairo", "seconds": item["cairo_proof_s"]},
                {"kind": "wrap", "seconds": item["wrap_proof_s"]})] + [
                    {"kind": "fold", "seconds": ns / 1e9}
                    for ns in fold_result["fold_prove_ns"]]
            receipt["stage_scope"] = "exact-cairo-wrap-fold-call-boundaries"
        else:
            receipt["stage_scope"] = "incomplete-stage-diagnostics"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "metal"), required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--source", type=Path, default=ROOT / "workspace/proof-v2-baseline")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "data/inputs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, help="override the M5 worker count for every selected case")
    args = parser.parse_args()
    if args.workers is not None and not 1 <= args.workers <= 18:
        parser.error("--workers must be between 1 and 18")
    config = json.loads((ROOT / "benchmark-proof-v2.json").read_text())
    manifest = json.loads((ROOT / config["fixtureManifest"]).read_text())
    timer_digest = attest(args.source, config, args.backend)
    cases = [case for case in manifest["cases"] if args.case_id in (None, case["id"])]
    if not cases:
        parser.error("case ID is absent from proof-v2 manifest")
    args.out.mkdir(parents=True, exist_ok=True)
    source = args.source.resolve()
    binary_hashes = {"cairo": sha(source / f"zig-out/bin/stwo-cairo-{args.backend}"),
                     "circuit": sha(source / ("src/integrations/circuit_metal/zig-out/bin/stwo-circuit-recursion-metal"
                                               if args.backend == "metal" else
                                               "zig-out/bin/stwo-circuit-recursion-cpu"))}
    for case in cases:
        directory = args.out / case["id"].replace(":", "_")
        receipt = qualify_case(source, args.fixtures.resolve(), case,
                               args.backend, directory, timer_digest, binary_hashes, args.workers)
        print(f"{case['id']}: {receipt['stage_scope']} exact output OK", flush=True)


if __name__ == "__main__":
    main()
