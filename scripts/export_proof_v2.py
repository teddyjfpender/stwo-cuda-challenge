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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "metal"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "benchmark-proof-v2.json").read_text())
    manifest = json.loads((ROOT / config["fixtureManifest"]).read_text())
    rows = export(args.root, config, manifest, args.backend,
                  allow_partial=args.allow_partial)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Published {len(rows)} exact, unranked {args.backend} observations to {args.out}")


if __name__ == "__main__":
    main()
