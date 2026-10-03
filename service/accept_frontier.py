#!/usr/bin/env python3
"""Freeze an operator-approved PR patch as the next participant starting frontier."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.source_policy import check_patch


def command(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def archive_previous_frontier(frontier_dir: Path, digest: str) -> None:
    """Keep the exact parent patch so unchanged participant workspaces can advance."""
    old_patch = frontier_dir / "changes.patch"
    if not old_patch.is_file():
        raise SystemExit("previous frontier patch is missing")
    raw = old_patch.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise SystemExit("previous frontier patch differs from its manifest")
    history = frontier_dir / "history"
    history.mkdir(exist_ok=True)
    archived = history / f"{digest}.patch"
    if archived.exists() and archived.read_bytes() != raw:
        raise SystemExit("archived parent frontier differs from the reviewed patch")
    archived.write_bytes(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--head-sha", required=True, help="reviewed immutable PR head")
    parser.add_argument("--source", type=Path, default=ROOT / "workspace/baseline")
    parser.add_argument("--replace", action="store_true", help="replace an existing cumulative frontier")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.pr < 1 or len(args.head_sha) != 40 or any(c not in "0123456789abcdef" for c in args.head_sha):
        parser.error("--pr and --head-sha must identify an exact PR commit")
    config = json.loads((ROOT / "benchmark.json").read_text())
    repository = "teddyjfpender/stwo-cuda-challenge"
    pull = json.loads(command("gh", "api", f"repos/{repository}/pulls/{args.pr}"))
    if pull["head"]["sha"] != args.head_sha or pull["base"]["repo"]["full_name"] != repository:
        raise SystemExit("PR head or target repository changed; re-review the exact commit")
    labels = {label["name"] for label in pull["labels"]}
    if not labels.intersection({"promoted-direct-h200", "accepted-frontier"}):
        raise SystemExit("PR needs an operator approval label before frontier acceptance")
    subprocess.run(["git", "fetch", "origin", f"refs/pull/{args.pr}/head"], cwd=ROOT, check=True)
    if command("git", "rev-parse", "FETCH_HEAD") != args.head_sha:
        raise SystemExit("fetched PR head changed; re-review before accepting")
    raw = subprocess.check_output(["git", "show", "FETCH_HEAD:candidate/changes.patch"], cwd=ROOT)
    if not raw:
        raise SystemExit("PR has no candidate patch")
    digest = hashlib.sha256(raw).hexdigest()

    source_manifest = json.loads((ROOT / "data/site/sources.json").read_text())
    review_path = ROOT / source_manifest["reviews"]
    with review_path.open(newline="") as source:
        reviews = list(csv.DictReader(source, delimiter="\t"))
    reviewed = next((row for row in reviews if row["pr_number"] == str(args.pr) and
                     row["head_sha"] == args.head_sha and row["patch_sha256"] == digest), None)
    if reviewed is None and "accepted-frontier" not in labels:
        raise SystemExit("patch is not bound to the reviewed PR evidence; operator must explicitly approve the frontier")
    if reviewed is not None and reviewed["review_state"] != "promoted_direct" and "accepted-frontier" not in labels:
        raise SystemExit("research-only PR cannot become the participant frontier")

    frontier_dir = ROOT / "frontier"
    if (frontier_dir / "manifest.json").exists() and not args.replace:
        raise SystemExit("frontier already exists; use --replace after reviewing cumulative composition")
    if command("git", "-C", str(args.source), "rev-parse", "HEAD") != config["sourceCommit"]:
        raise SystemExit("validation source is not the pinned prover commit")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="stwo-frontier-") as temp:
        temp_patch = Path(temp) / "changes.patch"
        temp_patch.write_bytes(raw)
        changed = check_patch(temp_patch, args.source, config)
    previous = frontier_dir / "manifest.json"
    parent_digest = json.loads(previous.read_text())["patchSha256"] if previous.exists() else None
    manifest = {
        "schema": "stwo-cuda-frontier-v1",
        "sourceCommit": config["sourceCommit"],
        "prNumber": args.pr,
        "prUrl": pull["html_url"],
        "headSha": args.head_sha,
        "patchSha256": digest,
        "parentPatchSha256": parent_digest,
        "qualification": reviewed["qualification"] if reviewed is not None else "operator-approved",
        "ranking": "unranked",
    }
    print(json.dumps({"manifest": manifest, "changedPaths": changed}, indent=2))
    if args.dry_run:
        return
    frontier_dir.mkdir(parents=True, exist_ok=True)
    if parent_digest is not None:
        archive_previous_frontier(frontier_dir, parent_digest)
    (frontier_dir / "changes.patch").write_bytes(raw)
    (frontier_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
