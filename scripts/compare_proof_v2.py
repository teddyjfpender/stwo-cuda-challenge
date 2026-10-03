#!/usr/bin/env python3
"""Compare two exact direct proof baskets on one backend; never rank them."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMPTY_DIFF = hashlib.sha256(b"").hexdigest()


def read_rows(path: Path, config: dict, manifest: dict, backend: str,
              *, baseline: bool) -> dict[str, dict]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    cases = {case["id"]: case for case in manifest["cases"]}
    if len(rows) != len(cases) or {row["case_id"] for row in rows} != set(cases):
        raise ValueError(f"{path}: must contain exactly the nine public jobs")
    result = {}
    for row in rows:
        case = cases[row["case_id"]]
        if (row["backend"] != backend or row["family"] != case["family"] or
                row["source_commit"] != config["sourceCommit"] or
                row["timer_digest"] != config["backends"][backend]["timerDigest"] or
                row["reference_match"] != "true"):
            raise ValueError(f"{path}: {case['id']} differs from the proof contract")
        if baseline and row["source_diff_sha256"] != EMPTY_DIFF:
            raise ValueError(f"{path}: baseline has source changes")
        if not baseline and row["source_diff_sha256"] == EMPTY_DIFF:
            raise ValueError(f"{path}: candidate has no source changes")
        seconds = float(row["stage_total_s"])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(f"{path}: {case['id']} lacks a positive proof time")
        result[case["id"]] = {**row, "seconds": seconds}
    return result


def compare(config: dict, manifest: dict, backend: str,
            baseline_path: Path, candidate_path: Path) -> dict:
    baseline = read_rows(baseline_path, config, manifest, backend, baseline=True)
    candidate = read_rows(candidate_path, config, manifest, backend, baseline=False)
    counts = {family: sum(case["family"] == family for case in manifest["cases"])
              for family in ("pie", "recursion", "pipeline")}
    per_case = []
    for case in manifest["cases"]:
        case_id = case["id"]
        ratio = candidate[case_id]["seconds"] / baseline[case_id]["seconds"]
        per_case.append({"case_id": case_id, "family": case["family"],
                         "baseline_proof_s": baseline[case_id]["seconds"],
                         "candidate_proof_s": candidate[case_id]["seconds"],
                         "candidate_over_baseline": ratio,
                         "weight": 1 / (3 * counts[case["family"]])})
    score = math.exp(-sum(row["weight"] * math.log(row["candidate_over_baseline"])
                          for row in per_case))
    return {"schema": "stwo-proof-v2-direct-comparison", "qualification": "unranked-direct",
            "backend": backend, "source_commit": config["sourceCommit"],
            "score_like_speedup": score, "per_case": per_case,
            "notice": "One direct basket per arm is research, not a paired or signed rank."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cuda", "metal", "cpu"), required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "benchmark-proof-v2.json").read_text())
    manifest = json.loads((ROOT / config["fixtureManifest"]).read_text())
    result = compare(config, manifest, args.backend, args.baseline, args.candidate)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Unranked proof-time speedup: {result['score_like_speedup']:.4f}x")


if __name__ == "__main__":
    main()
