#!/usr/bin/env python3
"""Score one backend's trusted proof-stage evidence for the staged v2 epoch."""

import json
import math
from pathlib import Path
import random
import statistics


FAMILIES = ("pie", "recursion", "pipeline")
REQUIRED_ROUNDS = 3


class InvalidProofEvidence(ValueError):
    pass


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidProofEvidence(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise InvalidProofEvidence(f"{label} must be finite and positive")
    return number


def expected_stages(case):
    leaves = len(case.get("inputs", []))
    if case["family"] == "pie":
        return {"cairo": 1}
    if case["family"] == "recursion":
        return {"fold": leaves - 1}
    return {"cairo": leaves, "wrap": leaves, "fold": leaves - 1}


def bind_rows(rows, cases, backend, hardware, timer_digest, host_id, label):
    grouped = {case_id: {} for case_id in cases}
    for row in rows:
        if not isinstance(row, dict) or row.get("case_id") not in grouped:
            raise InvalidProofEvidence(f"{label} contains an unknown case")
        case_id = row["case_id"]
        round_id = row.get("round")
        if isinstance(round_id, bool) or not isinstance(round_id, int) or round_id < 0:
            raise InvalidProofEvidence(f"{label} {case_id} has an invalid round")
        if round_id in grouped[case_id]:
            raise InvalidProofEvidence(f"{label} repeats {case_id} round {round_id}")
        if (row.get("backend") != backend or row.get("timer_digest") != timer_digest or
                row.get("host_id") != host_id or row.get("timer_scope") != "proof-execution-v2"):
            raise InvalidProofEvidence(f"{label} {case_id} is not bound to the timer and host")
        for flag in ("verified", "profile_ok", "statement_ok", "input_hash_ok", "memory_admitted"):
            if row.get(flag) is not True:
                raise InvalidProofEvidence(f"{label} {case_id} failed {flag}")
        stages = row.get("stages")
        if not isinstance(stages, list):
            raise InvalidProofEvidence(f"{label} {case_id} lacks stages")
        actual = {}
        total = 0.0
        for stage in stages:
            if not isinstance(stage, dict) or stage.get("kind") not in ("cairo", "wrap", "fold"):
                raise InvalidProofEvidence(f"{label} {case_id} has an unknown stage")
            kind = stage["kind"]
            actual[kind] = actual.get(kind, 0) + 1
            total += positive(stage.get("seconds"), f"{label} {case_id} stage")
        if actual != expected_stages(cases[case_id]):
            raise InvalidProofEvidence(f"{label} {case_id} has incomplete circuit stages")
        proof_time = positive(row.get("proof_time_s"), f"{label} {case_id} proof time")
        if not math.isclose(total, proof_time, rel_tol=0, abs_tol=1e-6):
            raise InvalidProofEvidence(f"{label} {case_id} stage sum differs from proof time")
        command_time = positive(row.get("command_time_s"), f"{label} {case_id} command time")
        if proof_time > command_time + 1e-6:
            raise InvalidProofEvidence(f"{label} {case_id} proof exceeds whole command")
        if backend == "cuda":
            peak = positive(row.get("peak_bytes"), f"{label} {case_id} memory peak")
            plan = positive(row.get("planned_arena_bytes"), f"{label} {case_id} arena plan")
            if peak >= hardware["deviceBytes"] or plan > hardware["deviceBytes"] - hardware["reserveBytes"]:
                raise InvalidProofEvidence(f"{label} {case_id} exceeds H200 capacity")
        elif row.get("peak_bytes") is not None:
            # macOS physical footprint can exceed installed unified memory when compression
            # and swap are active. Completion and the host watchdog own its capacity gate.
            positive(row["peak_bytes"], f"{label} {case_id} memory peak")
        grouped[case_id][round_id] = row
    return grouped


def aggregate(config, manifest, manifest_hash, evidence):
    if config.get("contractEpoch") != "proof-v2" or manifest.get("contract_epoch") != "proof-v2":
        raise InvalidProofEvidence("proof epoch differs")
    if manifest.get("source_commit") != config.get("sourceCommit"):
        raise InvalidProofEvidence("fixture source differs")
    backend = evidence.get("backend")
    hardware = config.get("backends", {}).get(backend)
    if hardware is None:
        raise InvalidProofEvidence("unknown backend")
    timer_digest = hardware.get("timerDigest")
    if not isinstance(timer_digest, str) or len(timer_digest) != 64:
        raise InvalidProofEvidence("timer owner has not been qualified")
    cases = {case["id"]: case for case in manifest["cases"]}
    if len(cases) != len(manifest["cases"]) or {case["family"] for case in cases.values()} != set(FAMILIES):
        raise InvalidProofEvidence("invalid case family or duplicate case")
    if (evidence.get("schema") != "stwo-proof-paired-evidence-v2" or
            evidence.get("contract_epoch") != "proof-v2" or
            evidence.get("source_commit") != config["sourceCommit"] or
            evidence.get("manifest_sha256") != manifest_hash):
        raise InvalidProofEvidence("evidence is not bound to the fixture manifest")
    host_id = evidence.get("host_id")
    if not isinstance(host_id, str) or not host_id:
        raise InvalidProofEvidence("host identity missing")
    baseline = bind_rows(evidence.get("baseline", []), cases, backend, hardware, timer_digest, host_id, "baseline")
    candidate = bind_rows(evidence.get("candidate", []), cases, backend, hardware, timer_digest, host_id, "candidate")
    counts = {family: sum(case["family"] == family for case in cases.values()) for family in FAMILIES}
    log_score = 0.0
    per_case = []
    rounds = None
    for case_id, case in cases.items():
        paired = sorted(set(baseline[case_id]) & set(candidate[case_id]))
        if len(paired) < REQUIRED_ROUNDS or (rounds is not None and paired != rounds):
            raise InvalidProofEvidence("fewer than three common, identical paired rounds")
        rounds = paired
        ratios = [candidate[case_id][index]["proof_time_s"] /
                  baseline[case_id][index]["proof_time_s"] for index in paired]
        ratio = statistics.median(ratios)
        weight = 1 / (len(FAMILIES) * counts[case["family"]])
        log_score -= weight * math.log(ratio)
        per_case.append({"id": case_id, "family": case["family"],
                         "proof_time_ratio": ratio, "paired_ratios": ratios,
                         "weight": weight})
    score = math.exp(log_score)
    random_source = random.Random(20261003)
    draws = []
    for _ in range(2000):
        indices = [random_source.randrange(len(rounds)) for _ in rounds]
        draws.append(math.exp(-sum(case["weight"] * math.log(statistics.median(
            case["paired_ratios"][index] for index in indices)) for case in per_case)))
    draws.sort()
    confidence = [draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws))]]
    rankable = config.get("status") == "active" and evidence.get("tier") == "rank"
    if rankable:
        aa = evidence.get("aa_time_log_ratios")
        if not isinstance(aa, list) or len(aa) < REQUIRED_ROUNDS:
            raise InvalidProofEvidence("ranked evidence lacks baseline A/A calibration")
        dispersion = statistics.median(abs(positive_or_zero(value)) for value in aa)
        threshold = max(0.01, math.expm1(2 * dispersion))
    else:
        threshold = None
    return {"schema": "stwo-proof-scorecard-v2", "backend": backend,
            "contract_epoch": "proof-v2", "source_commit": config["sourceCommit"],
            "host_id": host_id, "score": score, "confidence_95": confidence,
            "per_case": per_case, "rankable": rankable,
            "promotion_threshold": threshold,
            "promotable": rankable and confidence[0] > 1 + threshold}


def positive_or_zero(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InvalidProofEvidence("invalid A/A log ratio")
    return float(value)


def write_ranked(result, target: Path):
    if not result["rankable"]:
        raise InvalidProofEvidence("staged or unranked evidence cannot publish a score")
    target.write_text(json.dumps({"score": result["score"], "metrics": {
        "backend": result["backend"], "contract_epoch": result["contract_epoch"],
        "host_id": result["host_id"]}}, indent=2) + "\n")
