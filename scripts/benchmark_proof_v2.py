#!/usr/bin/env python3
"""Run a proof-only diagnostic basket on the selected backend; never rank it."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cuda", "metal", "cpu"), required=True)
    parser.add_argument("--case-id", action="append", help="one or more exact public case IDs")
    parser.add_argument("--source", type=Path, default=ROOT / "workspace/proof-v2-source")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "data/inputs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, help="M5 worker override for a capacity experiment")
    args = parser.parse_args()
    common = ["--source", str(args.source), "--fixtures", str(args.fixtures),
              "--out", str(args.out)]
    if args.backend == "cuda":
        if args.workers is not None:
            parser.error("--workers is for M5 backends only")
        command = [sys.executable, str(ROOT / "scripts/qualify_direct_h200.py"),
                   *common, "--config", str(ROOT / "benchmark-proof-v2.json")]
        for case_id in args.case_id or []:
            command.extend(("--case-id", case_id))
    else:
        if args.case_id and len(args.case_id) != 1:
            parser.error("M5 diagnostic accepts one --case-id or the full basket")
        command = [sys.executable, str(ROOT / "scripts/qualify_proof_v2.py"),
                   *common, "--backend", args.backend]
        if args.case_id:
            command.extend(("--case-id", args.case_id[0]))
        if args.workers is not None:
            command.extend(("--workers", str(args.workers)))
    raise SystemExit(subprocess.call(command, cwd=ROOT))


if __name__ == "__main__":
    main()
