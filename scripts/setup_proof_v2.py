#!/usr/bin/env python3
"""Prepare isolated source checkouts for the staged proof-only backend epoch."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.source_policy import check_patch
from harness.timer_owner import attest


def command(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def head(source: Path) -> str:
    return subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()


def repin_clean(source: Path, commit: str) -> None:
    if head(source) == commit:
        return
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"]):
        raise ValueError(f"{source} has edits; capture them before changing the source pin")
    if subprocess.run(["git", "-C", str(source), "cat-file", "-e", commit + "^{commit}"],
                      capture_output=True, check=False).returncode != 0:
        command("git", "fetch", "origin", commit, cwd=source)
    command("git", "checkout", "--detach", commit, cwd=source)


def prepare(config: dict, backend: str, *, apply_candidate: bool = False,
            build: bool = False, build_baseline: bool = False,
            prepare_assets: bool = True) -> tuple[Path, Path]:
    if config.get("contractEpoch") != "proof-v2":
        raise ValueError("setup requires the proof-v2 contract")
    if backend not in config["backends"]:
        raise ValueError(f"unknown backend: {backend}")
    source = ROOT / "workspace/proof-v2-source"
    baseline = ROOT / "workspace/proof-v2-baseline"
    commit = config["sourceCommit"]
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        seed = ROOT / "workspace/stwo-zig"
        if seed.is_dir() and subprocess.run(["git", "-C", str(seed), "rev-parse",
                                             "--is-inside-work-tree"],
                                            capture_output=True, check=False).returncode == 0:
            if subprocess.run(["git", "-C", str(seed), "cat-file", "-e", commit + "^{commit}"],
                              capture_output=True, check=False).returncode != 0:
                command("git", "fetch", "origin", commit, cwd=seed)
            command("git", "worktree", "add", "--detach", str(source), commit, cwd=seed)
        else:
            command("git", "clone", "--filter=blob:none", "--no-checkout",
                    config["sourceRepository"], str(source))
            command("git", "fetch", "origin", commit, cwd=source)
            command("git", "checkout", "--detach", commit, cwd=source)
    repin_clean(source, commit)
    if not baseline.exists():
        command("git", "worktree", "add", "--detach", str(baseline), commit, cwd=source)
    repin_clean(baseline, commit)
    if subprocess.check_output(["git", "-C", str(baseline), "status", "--porcelain"]):
        raise ValueError("baseline checkout has source changes")
    attest(baseline, config, backend)
    if apply_candidate:
        if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"]):
            raise ValueError("candidate application requires a clean editable checkout")
        patch = ROOT / "candidate/proof-v2-changes.patch"
        check_patch(patch, source, config, backend=backend)
        command("git", "apply", str(patch), cwd=source)
    attest(source, config, backend)
    if build or build_baseline:
        if shutil.which("zig") is None:
            raise ValueError("Zig is required to build prover products")
        for tree in ((baseline, source) if build_baseline else (source,)):
            if backend == "cuda":
                if shutil.which("nvcc") is None:
                    raise ValueError("nvcc is required for CUDA builds")
                from harness.cuda_toolchain import cuda_build_options
                command("zig", "build", "stwo-cairo-cuda", "circuit-recursion-cuda-resident",
                        "-Doptimize=ReleaseFast", *cuda_build_options(), cwd=tree)
            elif backend == "metal":
                command("zig", "build", "stwo-cairo-metal", "-Doptimize=ReleaseFast", "-j2", cwd=tree)
                command("zig", "build", "-Doptimize=ReleaseFast", "-j2",
                        cwd=tree / "src/integrations/circuit_metal")
            else:
                command("zig", "build", "stwo-cairo-cpu", "stwo-circuit-recursion-cpu",
                        "-Doptimize=ReleaseFast", "-j2", cwd=tree)
        if backend == "cuda" and prepare_assets:
            from scripts.setup import prepare_judge_assets
            prepare_judge_assets(baseline, commit)
    return source, baseline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cuda", "metal", "cpu"), required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "benchmark-proof-v2.json")
    parser.add_argument("--apply-candidate", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--build-baseline", action="store_true",
                        help="also build the pinned baseline; not needed for a first smoke test")
    parser.add_argument("--skip-assets", action="store_true",
                        help="reuse previously verified CUDA fixed assets when rebuilding source")
    args = parser.parse_args()
    source, baseline = prepare(json.loads(args.config.read_text()), args.backend,
                               apply_candidate=args.apply_candidate, build=args.build,
                               build_baseline=args.build_baseline,
                               prepare_assets=not args.skip_assets)
    print(f"Proof-v2 {args.backend} source: {source}; baseline: {baseline}")
    print("Staging only: no ranked proof-only judge is active yet.")


if __name__ == "__main__":
    main()
