#!/usr/bin/env python3
"""Run the staged, full-guest RISC-V CSP research track."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.source_policy import allowed, check_patch

CONFIG_PATH = ROOT / "benchmark-riscv-csp-v1.json"
SOURCE = ROOT / "workspace/csp-source"
BASELINE = ROOT / "workspace/csp-baseline"
PATCH = ROOT / "candidate/riscv-csp-changes.patch"
TARGETS = ("sha256", "keccak", "poseidon2_m31", "ecdsa_secp256k1")


def run(*command: str, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def output(*command: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def contract() -> dict:
    config = json.loads(CONFIG_PATH.read_text())
    if config["contractEpoch"] != "riscv-csp-v1" or config["status"] != "staging":
        raise ValueError("unsupported CSP challenge contract")
    for key, hash_key in (("fixtureManifest", "fixtureManifestSha256"),
                          ("precompileManifest", "precompileManifestSha256")):
        if digest(ROOT / config[key]) != config[hash_key]:
            raise ValueError(f"challenge fixture changed: {key}")
    return config


def verify_assets(tree: Path, config: dict) -> dict:
    """Bind the local checkout to the published CSP inputs and guest programs."""
    manifest_path = tree / "vectors/riscv_csp/manifest-v2.json"
    precompile_path = tree / "vectors/riscv_csp/ecdsa-precompile-v1.json"
    for path, expected in ((manifest_path, config["fixtureManifestSha256"]),
                           (precompile_path, config["precompileManifestSha256"])):
        if digest(path) != expected:
            raise ValueError(f"source fixture differs from challenge pin: {path}")
    manifest = json.loads(manifest_path.read_text())
    precompile = json.loads(precompile_path.read_text())
    if tuple(manifest["targets"]) != TARGETS:
        raise ValueError("CSP target order changed")
    assets: dict[str, str] = {}
    for target in manifest["targets"].values():
        guest = target["guest"]
        assets[guest["path"]] = guest["sha256"]
        for case in target["cases"]:
            assets[case["input_path"]] = case["input_sha256"]
    for case in manifest["negative_fixtures"]:
        assets[case["input_path"]] = case["input_sha256"]
    for guest in precompile["guests"].values():
        assets[guest["path"]] = guest["sha256"]
    for source in precompile["sources"]:
        assets[source["path"]] = source["sha256"]
    for relative, expected in assets.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or digest(tree / path) != expected:
            raise ValueError(f"CSP asset differs from manifest: {relative}")
    return manifest


def candidate_state(tree: Path, config: dict, backend: str, *, clean: bool) -> str:
    if not tree.is_dir():
        raise ValueError("run setup-csp first")
    pin = config["sourceCommit"]
    head = output("git", "rev-parse", "HEAD", cwd=tree)
    if subprocess.run(("git", "merge-base", "--is-ancestor", pin, head),
                      cwd=tree, check=False).returncode:
        raise ValueError("CSP checkout must descend from the pinned source")
    if clean and output("git", "status", "--porcelain", cwd=tree):
        raise ValueError("commit your candidate source edits before benchmarking")
    changed = output("git", "diff", "--name-only", pin, "HEAD", cwd=tree).splitlines()
    prefixes = config["backends"][backend]["editablePaths"]
    for path in changed:
        if not allowed(path, prefixes):
            raise ValueError(f"candidate commit changes a protected path: {path}")
    return head


def prepare(config: dict, backend: str, *, build: bool, build_baseline: bool) -> None:
    pin = config["sourceCommit"]
    if not SOURCE.exists():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        seed = ROOT / "workspace/stwo-zig"
        if seed.is_dir() and subprocess.run(
                ("git", "-C", str(seed), "rev-parse", "--is-inside-work-tree"),
                capture_output=True, check=False).returncode == 0:
            if subprocess.run(("git", "-C", str(seed), "cat-file", "-e", pin + "^{commit}"),
                              capture_output=True, check=False).returncode:
                run("git", "-C", str(seed), "fetch", "origin", pin)
            run("git", "-C", str(seed), "worktree", "add", "--detach", str(SOURCE), pin)
        else:
            run("git", "clone", "--filter=blob:none", "--no-checkout",
                config["sourceRepository"], str(SOURCE))
            run("git", "-C", str(SOURCE), "checkout", "--detach", pin)
    if not BASELINE.exists():
        run("git", "worktree", "add", "--detach", str(BASELINE), pin, cwd=SOURCE)
    if output("git", "rev-parse", "HEAD", cwd=BASELINE) != pin or output(
            "git", "status", "--porcelain", cwd=BASELINE):
        raise ValueError("CSP baseline must be the clean pinned source")
    candidate_state(SOURCE, config, backend, clean=False)
    verify_assets(BASELINE, config)
    verify_assets(SOURCE, config)
    for tree in ((BASELINE, SOURCE) if build_baseline else (SOURCE,) if build else ()):
        steps = ("stwo-zig-riscv-cpu", "riscv-trace-dump") if backend == "cpu" else (
            "stwo-riscv-metal", "riscv-trace-dump")
        run("zig", "build", *steps, "-Doptimize=ReleaseFast", "-j2", cwd=tree)
    print(f"CSP {backend} source: {SOURCE}; pinned baseline: {BASELINE}")


def expected_cases(manifest: dict) -> dict[tuple[str, int], dict]:
    return {(target, case["input_size"]): case
            for target, entry in manifest["targets"].items() for case in entry["cases"]}


def preflight_binary(registry: dict, *, backend: str, commit: str) -> None:
    product = registry.get("product", {})
    source = product.get("source", {})
    if (product.get("backend") != backend or product.get("optimize") != "ReleaseFast"
            or source.get("commit") != commit or source.get("dirty") is not False):
        raise ValueError("CSP binary is stale or has the wrong backend/build; run setup-csp --build")


def validate_report(report: dict, config: dict, manifest: dict, *, backend: str,
                    complete: bool, commit: str | None = None) -> dict[tuple[str, int], dict]:
    if (report.get("schema") != "stwo_riscv_csp_accelerated_benchmark_v1"
            or report.get("suite_manifest_sha256") != config["fixtureManifestSha256"]
            or report.get("proof_suite") != config["proofSuite"]
            or report.get("methodology", {}).get("execution_mode") != config["executionMode"]
            or report.get("run", {}).get("backend") != backend
            or report.get("run", {}).get("recursion_enabled") is not False
            or report.get("security", {}).get("pcs_config", {}).get("fri_config", {}).get("n_queries") != 70
            or report.get("security", {}).get("pcs_config", {}).get("pow_bits") != 26):
        raise ValueError("CSP report contract or security profile differs")
    if commit is not None and report.get("measurement_commit") != commit:
        raise ValueError("CSP report does not bind to the measured source commit")
    expected = expected_cases(manifest)
    rows: dict[tuple[str, int], dict] = {}
    for row in report.get("measurements", []):
        key = (row.get("target"), row.get("input_size"))
        if key not in expected or key in rows:
            raise ValueError(f"unexpected or duplicate CSP row: {key}")
        case = expected[key]
        evidence = row.get("evidence", {})
        precompiled = key[0] == "ecdsa_secp256k1"
        if ((not precompiled and row.get("cycles") != case["expected_cycles"])
                or (precompiled and (not isinstance(row.get("cycles"), int) or row["cycles"] <= 0))
                or evidence.get("input_sha256") != case["input_sha256"]
                or evidence.get("output_digest") != case["expected_digest"]
                or evidence.get("status") != "verified"
                or row.get("recursion_enabled") is not False
                or row.get("protocol", {}).get("proof_suite") != "blake3"
                or row.get("protocol", {}).get("pcs_config") != report["security"]["pcs_config"]
                or not isinstance(row.get("proof_duration"), int)
                or row["proof_duration"] <= 0):
            raise ValueError(f"CSP proof row failed canonical checks: {key}")
        if precompiled and (row.get("uses_precompile") is not True or
                            evidence.get("precompile_manifest_sha256") != config["precompileManifestSha256"]):
            raise ValueError("ECDSA must use the authenticated typed proved precompile")
        rows[key] = row
    if not rows or (complete and (set(rows) != set(expected) or
                                  report["run"].get("complete_matrix") is not True)):
        raise ValueError("CSP report does not cover the required case set")
    summary = report.get("summary", {})
    for field in ("all_outputs_match", "all_proofs_verified", "all_recursion_disabled",
                  "all_negative_proofs_verified", "all_negative_fixtures_rejected"):
        if summary.get(field) is not True:
            raise ValueError(f"CSP summary failed: {field}")
    return rows


def benchmark(args: argparse.Namespace, config: dict) -> None:
    tree = BASELINE if args.arm == "baseline" else SOURCE
    commit = config["sourceCommit"] if args.arm == "baseline" else candidate_state(
        SOURCE, config, args.backend, clean=True)
    manifest = verify_assets(tree, config)
    if args.case:
        target, sep, size = args.case.partition(":")
        if not sep or (target, int(size)) not in expected_cases(manifest):
            raise ValueError("--case must be a canonical TARGET:SIZE, for example sha256:128")
        targets, sizes = target, size
    else:
        targets = ",".join(TARGETS)
        sizes = ",".join(str(size) for size in sorted({size for _, size in expected_cases(manifest)}))
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    product = config["backends"][args.backend]["product"]
    cli = tree / "zig-out/bin" / product
    preflight_binary(json.loads(subprocess.check_output((str(cli), "applications"))),
                     backend=args.backend, commit=commit)
    run(sys.executable, "scripts/riscv_csp_benchmark.py", "--backend", args.backend,
        "--execution-mode", config["executionMode"], "--proof-suite", config["proofSuite"],
        "--manifest", "vectors/riscv_csp/manifest-v2.json", "--targets", targets,
        "--sizes", sizes, "--warmups", str(args.warmups), "--samples", str(args.samples),
        "--cli", str(cli),
        "--trace-cli", str(tree / "zig-out/bin/riscv-trace-dump"),
        "--report-out", str(out), cwd=tree)
    report = json.loads(out.read_text())
    rows = validate_report(report, config, manifest, backend=args.backend,
                           complete=not bool(args.case), commit=commit)
    print(f"Verified {len(rows)} full-guest CSP rows at {commit}; unranked report: {out}")


def capture(config: dict, backend: str) -> None:
    candidate_state(SOURCE, config, backend, clean=True)
    verify_assets(SOURCE, config)
    if (not BASELINE.is_dir() or
            output("git", "rev-parse", "HEAD", cwd=BASELINE) != config["sourceCommit"] or
            output("git", "status", "--porcelain", cwd=BASELINE)):
        raise ValueError("run setup-csp to restore the pinned baseline")
    raw = subprocess.check_output(("git", "diff", "--binary", config["sourceCommit"], "HEAD"), cwd=SOURCE)
    if not raw:
        raise ValueError("no committed candidate changes to capture")
    PATCH.parent.mkdir(parents=True, exist_ok=True)
    PATCH.write_bytes(raw)
    try:
        paths = check_patch(PATCH, BASELINE, config, backend=backend)
    except Exception:
        PATCH.unlink(missing_ok=True)
        raise
    print(f"Captured {len(paths)} {backend} source paths in {PATCH}")


def compare(args: argparse.Namespace, config: dict) -> None:
    manifest = json.loads((ROOT / config["fixtureManifest"]).read_text())
    baseline = json.loads(args.baseline.read_text())
    candidate = json.loads(args.candidate.read_text())
    before = validate_report(baseline, config, manifest, backend=args.backend, complete=True,
                             commit=config["sourceCommit"])
    after = validate_report(candidate, config, manifest, backend=args.backend, complete=True)
    host_keys = ("architecture", "cpu", "logical_cpu_count", "memory_bytes", "gpu")
    if any(baseline.get("host", {}).get(key) != candidate.get("host", {}).get(key)
           for key in host_keys):
        raise ValueError("CSP comparison requires the same recorded host")
    if candidate.get("measurement_commit") == config["sourceCommit"]:
        raise ValueError("candidate report measures the baseline source")
    weights = config["metric"]["targetWeights"]
    target_scores = {}
    for target in TARGETS:
        cases = [key for key in before if key[0] == target]
        ratios = [before[key]["proof_duration"] / after[key]["proof_duration"] for key in cases]
        target_scores[target] = math.exp(sum(math.log(r) for r in ratios) / len(ratios))
    total = math.exp(sum(weights[target] * math.log(target_scores[target]) for target in TARGETS))
    result = {"schema": "stwo-riscv-csp-direct-comparison-v1", "status": "unranked-research",
              "backend": args.backend, "baseline_commit": config["sourceCommit"],
              "candidate_commit": candidate["measurement_commit"], "source_manifest_sha256": config["fixtureManifestSha256"],
              "execution_mode": "precompile", "proof_suite": "blake3", "metric": config["metric"],
              "target_speedups": target_scores, "family_weighted_speedup": total,
              "baseline_report_sha256": digest(args.baseline), "candidate_report_sha256": digest(args.candidate)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Unranked CSP speedup {total:.4f}x; comparison: {args.out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "paths", "benchmark", "capture", "compare"):
        command = sub.add_parser(name)
        command.add_argument("--backend", choices=("cpu", "metal"), required=True)
        if name == "setup":
            command.add_argument("--build", action="store_true")
            command.add_argument("--build-baseline", action="store_true")
        elif name == "benchmark":
            command.add_argument("--arm", choices=("baseline", "candidate"), default="candidate")
            command.add_argument("--case", help="focused TARGET:SIZE; omit for all 16 rows")
            command.add_argument("--warmups", type=int, default=0)
            command.add_argument("--samples", type=int, default=1)
            command.add_argument("--out", type=Path, required=True)
        elif name == "compare":
            command.add_argument("--baseline", type=Path, required=True)
            command.add_argument("--candidate", type=Path, required=True)
            command.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    config = contract()
    if args.command == "setup":
        prepare(config, args.backend, build=args.build or args.build_baseline,
                build_baseline=args.build_baseline)
    elif args.command == "paths":
        print(f"Pinned source: {config['sourceCommit']}\nEditable checkout: {SOURCE}\nBaseline: {BASELINE}")
        print("Allowed source paths:")
        for path in config["backends"][args.backend]["editablePaths"]:
            print(f"  {SOURCE / path}")
        print(f"Capture: python3 challenge.py capture-csp --backend {args.backend}\nPatch: {PATCH}")
    elif args.command == "benchmark":
        if not 0 <= args.warmups <= 10 or not 1 <= args.samples <= 21:
            parser.error("warmups must be 0..10 and samples 1..21")
        benchmark(args, config)
    elif args.command == "capture":
        capture(config, args.backend)
    else:
        compare(args, config)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
