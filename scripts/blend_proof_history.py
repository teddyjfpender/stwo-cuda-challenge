#!/usr/bin/env python3
"""Blend modeled upstream proof progress into the public-case research TSV."""

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data/reports"
RESEARCH = REPORTS / "submission-research-2026-10-03.tsv"
HISTORY = REPORTS / "historical-cairo-cuda-milestones.tsv"
BASELINE = REPORTS / "h200-direct-2026-10-02-summary.tsv"
V37 = "autoresearch/notes/2026-09-29-cairo-cuda-local/nvidia-v37-sn-pie-suite-suite.json"
ANCHORS = (37, 39, 41, 42)
T95 = {1: 12.7062047364, 2: 4.30265272975}
EXTRA = ("record_kind", "milestone", "timeline_order", "estimate_low_s",
         "estimate_high_s", "estimate_method", "source_receipts", "source_sha256s")


def read_tsv(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predict(points: list[tuple[int, float]], target: int) -> tuple[float, float, float]:
    """Log-linear OLS central estimate and two-sided 95% predictive interval."""
    if len(points) not in (3, 4):
        raise ValueError("early backcast needs three or four verified anchors")
    xs = [float(revision) for revision, _ in points]
    ys = [math.log(seconds) for _, seconds in points]
    xbar, ybar = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - xbar) ** 2 for x in xs)
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    residual = math.sqrt(sum((y - intercept - slope * x) ** 2 for x, y in
                             zip(xs, ys)) / (len(points) - 2))
    center = intercept + slope * target
    half = T95[len(points) - 2] * residual * math.sqrt(
        1 + 1 / len(points) + (target - xbar) ** 2 / sxx)
    return tuple(math.exp(value) for value in (center, center - half, center + half))


def v37_verified(source: Path, historical: list[dict]) -> dict[str, dict]:
    path = source / V37
    receipt = json.loads(path.read_text())
    if receipt.get("full_suite_verified") is not False:
        raise ValueError("v37 must be the documented partial suite")
    v39 = {row["benchmark"]: row for row in historical if row["revision"] == "v39"}
    found = {}
    security = {"query_count": 70, "query_pow_bits": 26,
                "interaction_pow_bits": 24, "log_blowup_factor": 1,
                "fri_fold_step": 1, "log_last_layer_degree_bound": 0,
                "channel_salt": 0, "preprocessed_variant": "canonical"}
    for row in receipt["results"]:
        name = row["benchmark"]
        if name == "SN PIE 1" and row["status"] == "unverified":
            continue
        trial = row["backend_trial"]
        if (name not in v39 or name in found or row["status"] != "verified" or
                row["prover_exit_code"] != 0 or row["verifier_exit_code"] != 0 or
                row["official_verification"].get("verified") is not True or
                row["official_verification"].get("proof_sha256") != row["proof_sha256"] or
                row["proof_sha256"] != v39[name]["proof_sha256"] or
                row["adapted_input_sha256"] != v39[name]["input_sha256"] or
                trial["verdict"]["provider"] != "nvidia_cuda" or
                any(trial["verdict"]["counters"][key] != 0 for key in
                    ("cpu_fallback_attempts", "cpu_fallbacks_completed")) or
                any(trial["protocol"].get(key) != value for key, value in security.items()) or
                trial["proof_execute_and_decode_ns"] <= 0):
            raise ValueError(f"v37 {name} is not a canonical verified proof")
        found[name] = row
    if set(found) != {"SN PIE 2", "SN PIE 3", "SN PIE 4"}:
        raise ValueError("v37 verified coverage changed")
    return found


def geometric(values) -> float:
    return math.exp(statistics.mean(math.log(value) for value in values))


def bootstrap_factor(ratios: list[float]) -> tuple[float, float]:
    """Exact 4^4 resample of the four source-PIE multiplicative factors."""
    values = sorted(geometric(sample) for sample in itertools.product(ratios, repeat=4))
    return values[int(0.025 * len(values))], values[int(0.975 * len(values))]


def source_series(source: Path) -> list[dict]:
    historical = read_tsv(HISTORY)
    if len(historical) != 48 or any(row["verified"] != "true" for row in historical):
        raise ValueError("the imported historical 48-row verified series changed")
    by_revision: dict[str, dict[str, tuple[float, float, float]]] = {}
    receipts: dict[str, set[str]] = {}
    for row in historical:
        path = row["source_path"]
        if sha(source / path) != row["source_sha256"]:
            raise ValueError(f"historical receipt digest differs: {path}")
        revision = row["revision"]
        seconds = float(row["proof_stage_median_s"])
        by_revision.setdefault(revision, {})[row["benchmark"]] = (seconds, seconds, seconds)
        receipts.setdefault(revision, set()).add(path)
    partial = v37_verified(source, historical)
    by_revision["v37"] = {name: (row["backend_trial"]["proof_execute_and_decode_ns"] / 1e9,) * 3
                           for name, row in partial.items()}
    receipts["v37"] = {V37}
    for name in (f"SN PIE {n}" for n in range(1, 5)):
        points = [(revision, by_revision[f"v{revision}"][name][0]) for revision in ANCHORS
                  if name in by_revision[f"v{revision}"]]
        for revision in (33, 35, 37):
            if revision == 37 and name in partial:
                continue
            by_revision.setdefault(f"v{revision}", {})[name] = predict(points, revision)
            for anchor, _ in points:
                receipts.setdefault(f"v{revision}", set()).update(receipts[f"v{anchor}"])
    ordered = ["v33", "v35", "v37", *dict.fromkeys(row["revision"] for row in historical)]
    reference = by_revision["hopper-v18"]
    result = []
    for ordinal, revision in enumerate(ordered):
        observed = by_revision[revision]
        if set(observed) != set(reference):
            raise ValueError(f"historical milestone has incomplete source PIEs: {revision}")
        ratios = [observed[name][0] / reference[name][0] for name in sorted(reference)]
        factor = geometric(ratios)
        if revision in ("v33", "v35", "v37"):
            low = geometric(observed[name][1] / reference[name][0] for name in sorted(reference))
            high = geometric(observed[name][2] / reference[name][0] for name in sorted(reference))
            method = "source_ols_backcast_and_multiplicative_transfer"
        else:
            low, high = bootstrap_factor(ratios)
            method = "verified_source_ratio_and_multiplicative_transfer"
        paths = sorted(receipts[revision] | receipts["hopper-v18"])
        result.append({"revision": revision, "ordinal": ordinal, "factor": factor,
                       "low": low, "high": high, "method": method,
                       "paths": paths, "sha256s": [sha(source / path) for path in paths]})
    return result


def blend(source: Path) -> list[dict]:
    existing = read_tsv(RESEARCH)
    if not existing or not all(row.get("pr_number") for row in existing
                               if row.get("record_kind", "submission") == "submission"):
        raise ValueError("submission research rows are malformed")
    submissions = [row for row in existing if row.get("record_kind", "submission") == "submission"]
    for row in submissions:
        row.update(record_kind="submission", milestone=f"PR #{row['pr_number']}",
                   timeline_order=str(100 + int(row["pr_number"])))
    baseline = {row["case_id"]: row for row in read_tsv(BASELINE) if
                row["family"] == "pie" and row["proof_stage_s"]}
    if len(baseline) != 6:
        raise ValueError("six measured public PIE proof stages are required")
    modeled = []
    for stage in source_series(source):
        for case_id, anchor in baseline.items():
            base = float(anchor["proof_stage_s"])
            modeled.append({
                "case_id": case_id, "family": "pie", "qualification": "statistical_extrapolation",
                "samples_per_arm": "0", "time_scope": "modelled_proof_stage",
                "proof_scope": "cairo_execute_finish", "baseline_proof_s": f"{base:.9f}",
                "candidate_proof_s": f"{base * stage['factor']:.9f}",
                "record_kind": "historical_model", "milestone": stage["revision"],
                "timeline_order": str(stage["ordinal"]),
                "estimate_low_s": f"{base * stage['low']:.9f}",
                "estimate_high_s": f"{base * stage['high']:.9f}",
                "estimate_method": stage["method"],
                "source_receipts": ";".join(stage["paths"]),
                "source_sha256s": ";".join(stage["sha256s"]),
            })
    for case_id, anchor in baseline.items():
        base = float(anchor["proof_stage_s"])
        modeled.append({"case_id": case_id, "family": "pie",
                        "qualification": "direct-unranked-unsandboxed",
                        "samples_per_arm": "2", "time_scope": "cairo_execute_finish",
                        "proof_scope": "cairo_execute_finish", "baseline_proof_s": f"{base:.9f}",
                        "candidate_proof_s": f"{base:.9f}",
                        "record_kind": "challenge_baseline", "milestone": "challenge start",
                        "timeline_order": "50", "estimate_method": "measured_public_baseline",
                        "source_receipts": "data/reports/h200-direct-2026-10-02.json",
                        "source_sha256s": sha(REPORTS / "h200-direct-2026-10-02.json")})
    return modeled + submissions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path,
                        help="stwo-zig checkout containing the pinned autoresearch receipts")
    columns = list(dict.fromkeys([*read_tsv(RESEARCH)[0].keys(), *EXTRA]))
    rows = blend(parser.parse_args().source.resolve())
    with tempfile.NamedTemporaryFile("w", newline="", dir=REPORTS,
                                     prefix=".proof-history-", delete=False) as handle:
        temporary = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t",
                                lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, RESEARCH)


if __name__ == "__main__":
    main()
