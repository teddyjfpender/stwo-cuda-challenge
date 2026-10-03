#!/usr/bin/env python3
"""Validate direct proof-v2 receipts and publish an unranked observation TSV."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("backend", "case_id", "family", "source_commit", "source_diff_sha256",
          "stage_total_s", "stage_scope", "command_wall_s",
          "peak_physical_footprint_bytes", "reference_match", "verification",
          "proof_sha256", "outputs_sha256", "packed_sha256", "timer_digest",
          "receipt_sha256")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def stages(case: dict, receipt: dict) -> list[dict]:
    """Accept new explicit stages and reconstruct earlier exact-timer smoke receipts."""
    if "stages" in receipt:
        return receipt["stages"]
    if case["family"] == "pie":
        return [{"kind": "cairo", "seconds": receipt["proof_stage_s"]}]
    folds = [{"kind": "fold", "seconds": ns / 1e9}
             for ns in receipt["fold_prove_ns"]]
    if case["family"] == "recursion":
        return folds
    leaves = receipt["leaf_timing_diagnostics"]
    return [stage for leaf in leaves for stage in (
        {"kind": "cairo", "seconds": leaf["cairo_proof_s"]},
        {"kind": "wrap", "seconds": leaf["wrap_proof_s"]})] + folds


def checked_row(root: Path, case: dict, config: dict, backend: str) -> dict[str, str]:
    directory = root / case["id"].replace(":", "_")
    receipt_path = directory / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    expected = {"pie": "shared-cairo-product-prove-ns",
                "recursion": "exact-fold-call-boundaries",
                "pipeline": "exact-cairo-wrap-fold-call-boundaries"}[case["family"]]
    if (receipt.get("schema") != "stwo-m5-proof-v2-diagnostic" or
            receipt.get("backend") != backend or receipt.get("case_id") != case["id"] or
            receipt.get("source_commit") != config["sourceCommit"] or
            receipt.get("timer_digest") != config["backends"][backend]["timerDigest"] or
            receipt.get("stage_scope") != expected):
        raise ValueError(f"{case['id']}: source, timer, or stage scope differs")
    proof_seconds = receipt.get("proof_stage_s")
    if (isinstance(proof_seconds, bool) or not isinstance(proof_seconds, (int, float)) or
            not math.isfinite(proof_seconds) or proof_seconds <= 0):
        raise ValueError(f"{case['id']}: missing exact proof time")
    intervals = stages(case, receipt)
    counts = {kind: sum(stage["kind"] == kind for stage in intervals)
              for kind in ("cairo", "wrap", "fold")}
    leaves = len(case.get("inputs", []))
    required = ({"cairo": 1, "wrap": 0, "fold": 0} if case["family"] == "pie" else
                {"cairo": 0, "wrap": 0, "fold": leaves - 1} if case["family"] == "recursion" else
                {"cairo": leaves, "wrap": leaves, "fold": leaves - 1})
    if counts != required or not math.isclose(
            sum(stage["seconds"] for stage in intervals), proof_seconds, abs_tol=1e-6):
        raise ValueError(f"{case['id']}: incomplete or inconsistent prover intervals")
    if case["family"] == "pie":
        actual = sha(directory / "proof.json")
        if actual != case["expected_proof_sha256"] or actual != receipt["proof_sha256"]:
            raise ValueError(f"{case['id']}: Cairo proof digest differs")
        hashes = {"proof_sha256": actual, "outputs_sha256": "", "packed_sha256": ""}
        verification = "exact-reference-and-product-verify"
    else:
        hashes = {key: sha(directory / filename) for key, filename in (
            ("proof_sha256", "root.proof"), ("outputs_sha256", "root_outputs.json"),
            ("packed_sha256", "root_packed.json"))}
        if hashes != case["expected_root"] or hashes != receipt["root"]:
            raise ValueError(f"{case['id']}: recursive root digest differs")
        verification = "exact-reference"
    command_seconds = receipt["command_wall_s"]
    if case["family"] == "pipeline" and "fold_command_wall_s" not in receipt:
        command_seconds += sum(leaf["command_wall_s"] for leaf in
                               receipt["leaf_timing_diagnostics"])
    if not math.isfinite(command_seconds) or proof_seconds > command_seconds + 1e-6:
        raise ValueError(f"{case['id']}: prover time exceeds whole command")
    return {"backend": backend, "case_id": case["id"], "family": case["family"],
            "source_commit": receipt["source_commit"],
            "source_diff_sha256": receipt["source_diff_sha256"],
            "stage_total_s": f"{proof_seconds:.9f}", "stage_scope": expected,
            "command_wall_s": f"{command_seconds:.9f}",
            "peak_physical_footprint_bytes": str(receipt.get(
                "physical_footprint_peak_bytes") or ""),
            "reference_match": "true", "verification": verification,
            **hashes, "timer_digest": receipt["timer_digest"],
            "receipt_sha256": sha(receipt_path)}


def export(root: Path, config: dict, manifest: dict, backend: str,
           *, allow_partial: bool = False) -> list[dict[str, str]]:
    if backend not in ("cpu", "metal"):
        raise ValueError("this exporter accepts M5 CPU or Metal receipts")
    rows = []
    for case in manifest["cases"]:
        if not (root / case["id"].replace(":", "_") / "receipt.json").exists():
            if allow_partial:
                continue
            raise ValueError(f"{case['id']}: receipt missing from full basket")
        rows.append(checked_row(root, case, config, backend))
    if not rows:
        raise ValueError("no exact proof-v2 receipts found")
    return rows


def export_cuda(root: Path, config: dict, manifest: dict,
                *, allow_partial: bool = False) -> list[dict[str, str]]:
    """Rehash CUDA artifacts and enforce complete per-call stage telemetry."""
    receipt_path = root / "direct-results.json"
    receipts = json.loads(receipt_path.read_text())
    if not isinstance(receipts, list):
        raise ValueError("CUDA direct results must be a list")
    cases = {case["id"]: case for case in manifest["cases"]}
    if len(cases) != len(manifest["cases"]):
        raise ValueError("duplicate public case IDs")
    if len(receipts) != len({row.get("case_id") for row in receipts}) or any(
            row.get("case_id") not in cases for row in receipts):
        raise ValueError("duplicate or unknown CUDA case")
    if not allow_partial and {row["case_id"] for row in receipts} != set(cases):
        raise ValueError("CUDA receipt is missing public jobs")
    rows = []
    for receipt in receipts:
        case = cases[receipt["case_id"]]
        directory = root / case["id"].replace(":", "_")
        if (receipt.get("family") != case["family"] or
                receipt.get("source_commit") != config["sourceCommit"] or
                receipt.get("timer_digest") != config["backends"]["cuda"]["timerDigest"] or
                receipt.get("timing_boundary") != "proof-execution-v2" or
                receipt.get("verified") is not True or
                receipt.get("canonical_output") is not True or
                receipt.get("gpu_resident") is not True):
            raise ValueError(f"{case['id']}: CUDA source, timer, or output differs")
        stages = receipt.get("proof_stages")
        if not isinstance(stages, list):
            raise ValueError(f"{case['id']}: missing CUDA proof stages")
        expected = ({"cairo": 1, "wrap": 0, "fold": 0} if case["family"] == "pie" else
                    {"cairo": 0, "wrap": 0, "fold": len(case["inputs"]) - 1}
                    if case["family"] == "recursion" else
                    {"cairo": len(case["inputs"]), "wrap": len(case["inputs"]),
                     "fold": len(case["inputs"]) - 1})
        counts = {kind: sum(stage.get("kind") == kind for stage in stages)
                  for kind in expected}
        if (counts != expected or any(stage.get("kind") not in expected or
                isinstance(stage.get("seconds"), bool) or
                not isinstance(stage.get("seconds"), (int, float)) or
                not math.isfinite(stage["seconds"]) or stage["seconds"] <= 0
                for stage in stages)):
            raise ValueError(f"{case['id']}: incomplete CUDA prover intervals")
        proof_seconds = receipt.get("proof_stage_s")
        command_seconds = receipt.get("time_s")
        if (not isinstance(proof_seconds, (int, float)) or
                not isinstance(command_seconds, (int, float)) or
                not math.isclose(sum(stage["seconds"] for stage in stages),
                                 proof_seconds, abs_tol=1e-6) or
                not math.isfinite(command_seconds) or proof_seconds > command_seconds):
            raise ValueError(f"{case['id']}: CUDA proof and command times differ")
        location = directory if case["family"] != "pipeline" else directory / "result"
        if case["family"] == "pie":
            hashes = {"proof_sha256": sha(location / "proof.json"),
                      "outputs_sha256": "", "packed_sha256": ""}
            expected_hashes = {"proof_sha256": case["expected_proof_sha256"],
                               "outputs_sha256": "", "packed_sha256": ""}
            verification = "exact-reference-and-rust-cairo"
            if receipt.get("verifier_results", {}).get("official_rust_cairo") != "accepted":
                raise ValueError(f"{case['id']}: Rust Cairo verification missing")
        else:
            hashes = {key: sha(location / name) for key, name in (
                ("proof_sha256", "root.proof"), ("outputs_sha256", "root_outputs.json"),
                ("packed_sha256", "root_packed.json"))}
            expected_hashes = case["expected_root"]
            verification = ("exact-reference-and-rust-cairo-leaves" if case["family"] == "pipeline"
                            else "exact-reference")
            if (case["family"] == "pipeline" and receipt.get("verifier_results", {}).get(
                    "registry_rust_cairo_leaves") != "accepted"):
                raise ValueError(f"{case['id']}: Rust Cairo leaf verification missing")
        if hashes != expected_hashes:
            raise ValueError(f"{case['id']}: CUDA artifact digest differs")
        reported_hashes = receipt.get("proof_sha256", {})
        if any(reported_hashes.get(name) != digest for name, digest in (
                (("proof.json", hashes["proof_sha256"]),) if case["family"] == "pie" else
                (("root.proof", hashes["proof_sha256"]),
                 ("root_outputs.json", hashes["outputs_sha256"]),
                 ("root_packed.json", hashes["packed_sha256"])))):
            raise ValueError(f"{case['id']}: CUDA receipt artifact digest differs")
        rows.append({"backend": "cuda", "case_id": case["id"], "family": case["family"],
                     "source_commit": receipt["source_commit"],
                     "source_diff_sha256": receipt["source_diff_sha256"],
                     "stage_total_s": f"{proof_seconds:.9f}",
                     "stage_scope": "exact-cuda-cairo-wrap-fold-call-boundaries",
                     "command_wall_s": f"{command_seconds:.9f}",
                     "peak_physical_footprint_bytes": "", "reference_match": "true",
                     "verification": verification, **hashes,
                     "timer_digest": receipt["timer_digest"],
                     "receipt_sha256": sha(receipt_path)})
    if not rows:
        raise ValueError("no exact CUDA proof-v2 receipts found")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "metal", "cuda"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "benchmark-proof-v2.json").read_text())
    manifest = json.loads((ROOT / config["fixtureManifest"]).read_text())
    rows = (export_cuda(args.root, config, manifest, allow_partial=args.allow_partial)
            if args.backend == "cuda" else
            export(args.root, config, manifest, args.backend,
                   allow_partial=args.allow_partial))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Published {len(rows)} exact, unranked {args.backend} observations to {args.out}")


if __name__ == "__main__":
    main()
