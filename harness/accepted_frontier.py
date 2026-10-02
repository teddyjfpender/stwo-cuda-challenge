"""Apply a reviewed cumulative CUDA frontier over the immutable source pin."""

import hashlib
import json
from pathlib import Path
import subprocess

from harness.source_policy import check_patch


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(workspace), *args], text=True,
                          capture_output=True, check=False)


def apply_frontier(root: Path, workspace: Path, baseline: Path, config: dict) -> None:
    manifest_path = root / "frontier/manifest.json"
    patch = root / "frontier/changes.patch"
    if not manifest_path.is_file() and not patch.is_file():
        return
    if not manifest_path.is_file() or not patch.is_file():
        raise SystemExit("frontier manifest and patch must both exist")
    manifest = json.loads(manifest_path.read_text())
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    if (manifest.get("schema") != "stwo-cuda-frontier-v1" or
            manifest.get("sourceCommit") != config["sourceCommit"] or
            manifest.get("patchSha256") != digest):
        raise SystemExit("frontier manifest does not match the pinned source and patch")
    check_patch(patch, baseline, config)

    marker_result = _git(workspace, "rev-parse", "--git-path", "stwo-cuda-frontier.json")
    if marker_result.returncode != 0:
        raise SystemExit(marker_result.stderr.strip())
    marker = Path(marker_result.stdout.strip())
    if not marker.is_absolute():
        marker = workspace / marker
    tracked_dirty = bool(_git(workspace, "diff", "--name-only", "HEAD").stdout.strip())
    if marker.is_file() and json.loads(marker.read_text()).get("patchSha256") == digest and tracked_dirty:
        print(f"Accepted frontier PR #{manifest['prNumber']} already applied")
        return
    if _git(workspace, "apply", "--reverse", "--check", str(patch)).returncode == 0:
        marker.write_text(json.dumps({"patchSha256": digest}) + "\n")
        print(f"Accepted frontier PR #{manifest['prNumber']} already applied")
        return
    if tracked_dirty:
        raise SystemExit("editable workspace has changes; capture them or use setup --base in a fresh checkout")
    check = _git(workspace, "apply", "--check", str(patch))
    if check.returncode != 0:
        raise SystemExit(f"accepted frontier does not apply: {check.stderr.strip()}")
    result = _git(workspace, "apply", str(patch))
    if result.returncode != 0:
        raise SystemExit(f"accepted frontier failed: {result.stderr.strip()}")
    marker.write_text(json.dumps({"patchSha256": digest}) + "\n")
    print(f"Applied accepted frontier PR #{manifest['prNumber']} ({digest[:12]})")
