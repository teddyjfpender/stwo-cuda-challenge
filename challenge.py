#!/usr/bin/env python3
"""Participant entry point for the proof-only CUDA, Metal, and CPU challenge."""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
COMMANDS = {
    "check-data": ([sys.executable, "scripts/check_data.py"], "Check public input and reference-output hashes."),
    "setup-proof": ([sys.executable, "scripts/setup_proof_v2.py"], "Create one proof-v2 backend checkout; pass --backend cuda|metal|cpu."),
    "paths": ([], "Show the selected backend's checkout and editable paths; pass --backend cuda|metal|cpu."),
    "benchmark-proof": ([sys.executable, "scripts/benchmark_proof_v2.py"], "Run exact proof-stage diagnostics for cuda, metal, or cpu."),
    "compare-proof": ([sys.executable, "scripts/compare_proof_v2.py"], "Compare two exact public baskets; research only, never ranked."),
    "capture-proof": ([sys.executable, "scripts/capture_proof_v2.py"], "Capture a proof-v2 backend patch for a review PR."),
    "setup-csp": ([sys.executable, "scripts/riscv_csp_trial.py", "setup"], "Create the RISC-V CSP CPU or Metal checkout."),
    "paths-csp": ([sys.executable, "scripts/riscv_csp_trial.py", "paths"], "Show the RISC-V CSP edit surface."),
    "benchmark-csp": ([sys.executable, "scripts/riscv_csp_trial.py", "benchmark"], "Run canonical full-guest CSP proof measurements."),
    "compare-csp": ([sys.executable, "scripts/riscv_csp_trial.py", "compare"], "Compare complete CSP reports on one backend and host."),
    "capture-csp": ([sys.executable, "scripts/riscv_csp_trial.py", "capture"], "Capture a committed RISC-V CSP candidate patch."),
}
def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage: python3 challenge.py COMMAND [COMMAND OPTIONS]\n")
        for name, (_, description) in COMMANDS.items():
            print(f"  {name:<12} {description}")
        print("\nRead TASK.md and the track-specific spec before editing or benchmarking.")
        print("Direct trials are unranked; see spec/PROOF_STAGE_EPOCH.md or spec/RISCV_CSP.md.")
        return 0 if argv else 2
    command, *options = argv
    if command not in COMMANDS:
        print(f"Unknown command: {command}. Run python3 challenge.py --help.", file=sys.stderr)
        return 2
    if command == "paths":
        if len(options) != 2 or options[0] != "--backend" or options[1] not in ("cuda", "metal", "cpu"):
            print("paths requires --backend cuda|metal|cpu", file=sys.stderr)
            return 2
        backend = options[1]
        config = json.loads((ROOT / "benchmark-proof-v2.json").read_text())
        source = ROOT / "workspace/proof-v2-source"
        print(f"Challenge root: {ROOT}")
        print(f"Editable prover checkout: {source}")
        print(f"Pinned source commit: {config['sourceCommit']}")
        print(f"Checkout exists: {'yes' if source.is_dir() else 'no; run python3 challenge.py setup-proof'}")
        for relative in config["backends"][backend]["editablePaths"]:
            print(f"  {source / relative}")
        print("Submit: python3 challenge.py capture-proof --backend", backend)
        print("Captured patch: candidate/proof-v2-changes.patch")
        return 0
    return subprocess.run([*COMMANDS[command][0], *options], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
