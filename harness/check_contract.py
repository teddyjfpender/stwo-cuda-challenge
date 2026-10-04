#!/usr/bin/env python3
"""Check the frozen public workload and track metadata without a GPU."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.timer_owner import check_protected
from harness.source_policy import allowed
HEX = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def check_proof_frontiers(config: dict) -> None:
    for name, backend in config["backends"].items():
        directory = ROOT / "frontier/proof-v2" / name
        manifest_path, patch_path = directory / "manifest.json", directory / "changes.patch"
        if not manifest_path.exists() and not patch_path.exists():
            continue
        assert manifest_path.is_file() and patch_path.is_file()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["schema"] == "stwo-proof-v2-frontier-v1"
        assert manifest["backend"] == name
        assert manifest["sourceCommit"] == config["sourceCommit"]
        assert COMMIT.fullmatch(manifest["headSha"])
        assert isinstance(manifest["prNumber"], int) and manifest["prNumber"] > 0
        assert hashlib.sha256(patch_path.read_bytes()).hexdigest() == manifest["patchSha256"]
        evidence = Path(manifest["evidence"])
        assert not evidence.is_absolute() and ".." not in evidence.parts
        assert (ROOT / evidence).is_file()
        fields = subprocess.check_output(["git", "apply", "--numstat", "-z", str(patch_path)]).split(b"\0")
        paths = [field.split(b"\t")[2].decode() for field in fields if field]
        assert paths and len(paths) == len(set(paths))
        assert all(allowed(path, backend["editablePaths"]) and
                   path not in backend.get("protectedPaths", []) for path in paths)


def check_v2(config: dict, manifest: dict) -> None:
    assert config["schemaVersion"] == 3
    assert config["status"] in {"staging", "active"}
    assert config["contractEpoch"] == manifest["contract_epoch"] == "proof-v2"
    assert config["sourceCommit"] == manifest["source_commit"]
    assert COMMIT.fullmatch(config["sourceCommit"])
    assert {case["family"] for case in manifest["cases"]} == {"pie", "recursion", "pipeline"}
    assert len({case["id"] for case in manifest["cases"]}) == len(manifest["cases"])
    assert {track["name"] for track in config["tracks"]} == {
        "proof-cuda", "proof-metal", "proof-cpu"}
    assert {track["backend"] for track in config["tracks"]} == set(config["backends"])
    assert config["metric"]["name"] == "proof_stage_seconds"
    assert config["metric"]["memory"] == "capacity_gate_only"
    check_protected(config)
    for backend in config["backends"].values():
        assert HEX.fullmatch(backend["timerDigest"])
        assert len(backend["editablePaths"]) == len(set(backend["editablePaths"]))
    check_proof_frontiers(config)
    for case in manifest["cases"]:
        assert case["metric"] == "proof_stage_seconds"
        inputs = [case["input"]] if case["family"] == "pie" else case["inputs"]
        for item in inputs:
            assert HEX.fullmatch(item["sha256"])
            if "preimage_sha256" in item:
                assert HEX.fullmatch(item["preimage_sha256"])
        if case["family"] == "pie":
            assert HEX.fullmatch(case["expected_proof_sha256"])
        else:
            assert all(HEX.fullmatch(value) for value in case["expected_root"].values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "benchmark-proof-v2.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    manifest = json.loads((ROOT / config["fixtureManifest"]).read_text())
    if config["schemaVersion"] == 3:
        check_v2(config, manifest)
        print(f"Staged proof contract OK: {len(manifest['cases'])} cases, "
              f"manifest sha256 {hashlib.sha256((ROOT / config['fixtureManifest']).read_bytes()).hexdigest()}")
        return
    assert config["schemaVersion"] == 2
    assert config["contractEpoch"] == manifest["contract_epoch"]
    assert config["sourceCommit"] == manifest["source_commit"]
    assert COMMIT.fullmatch(config["sourceCommit"])
    assert set(case["family"] for case in manifest["cases"]) == {"pie", "recursion", "pipeline"}
    assert len({case["id"] for case in manifest["cases"]}) == len(manifest["cases"])
    assert {track["name"] for track in config["tracks"]} == {"latency", "memory", "balanced"}
    assert all(track["editablePaths"] == ["candidate"] for track in config["tracks"])
    assert config["hardware"]["deviceBytes"] - config["hardware"]["reserveBytes"] > 0
    for case in manifest["cases"]:
        inputs = [case["input"]] if case["family"] == "pie" else case["inputs"]
        for item in inputs:
            assert HEX.fullmatch(item["sha256"])
            if "preimage_sha256" in item:
                assert HEX.fullmatch(item["preimage_sha256"])
        if case["family"] == "pie":
            assert HEX.fullmatch(case["expected_proof_sha256"])
            assert (case["historical_h200"]["planned_arena_bytes"] <=
                    config["hardware"]["deviceBytes"] - config["hardware"]["reserveBytes"])
        else:
            assert all(HEX.fullmatch(value) for value in case["expected_root"].values())
    print(f"Contract OK: {len(manifest['cases'])} cases, "
          f"manifest sha256 {hashlib.sha256((ROOT / config['fixtureManifest']).read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
