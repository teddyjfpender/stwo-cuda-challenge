#!/usr/bin/env python3
"""Capture a backend-specific proof-v2 source patch without changing v1 submissions."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.source_policy import check_patch
from harness.timer_owner import attest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cuda", "metal", "cpu"), required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "benchmark-proof-v2.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    source = ROOT / "workspace/proof-v2-source"
    if not source.is_dir():
        parser.error("run scripts/setup_proof_v2.py first")
    attest(source, config, args.backend)
    untracked = subprocess.check_output(["git", "-C", str(source), "ls-files", "--others",
                                         "--exclude-standard", "-z"]).split(b"\0")
    if any(untracked):
        parser.error("untracked source files exist; review them and use git add -N on intended new files")
    patch = ROOT / "candidate/proof-v2-changes.patch"
    patch.parent.mkdir(parents=True, exist_ok=True)
    source_diff = subprocess.check_output(["git", "-C", str(source), "diff", "--binary", "HEAD"])
    patch.write_bytes(source_diff)
    try:
        paths = check_patch(patch, source, config, already_applied=True, backend=args.backend)
    except Exception:
        patch.unlink(missing_ok=True)
        raise
    print(f"Captured {len(paths)} {args.backend} source files in {patch}")
    for path in paths:
        print(path)
    print("Staging only: this patch is reviewable, but proof-v2 ranking is not active.")


if __name__ == "__main__":
    main()
