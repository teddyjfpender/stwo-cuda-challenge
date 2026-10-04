"""Apply a reviewed cumulative frontier over the immutable source pin."""

import hashlib
import json
from pathlib import Path
import subprocess

from harness.source_policy import check_patch


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(workspace), *args], text=True,
                          capture_output=True, check=False)


def _migrate_unchanged_frontier(root: Path, workspace: Path, marker: Path,
                                previous_digest: str, current_patch: Path,
                                current_digest: str, history: Path) -> bool:
    """Advance a prior frontier only when its removal leaves a clean checkout."""
    old_patch = history / f"{previous_digest}.patch"
    # `challenge.py capture` uses intent-to-add for files introduced by a
    # frontier. Reversing the patch removes the worktree file but leaves that
    # empty index placeholder, which would otherwise look like participant work.
    old_added = _git(workspace, "diff", "--name-only", "--diff-filter=A", "HEAD").stdout.splitlines()
    if (not old_patch.is_file() or
            hashlib.sha256(old_patch.read_bytes()).hexdigest() != previous_digest or
            _git(workspace, "apply", "--reverse", "--check", str(old_patch)).returncode != 0):
        return False
    if _git(workspace, "apply", "--reverse", str(old_patch)).returncode != 0:
        return False
    for name in old_added:
        if (workspace / name).exists():
            continue
        staged = _git(workspace, "ls-files", "--stage", "--", name).stdout.rstrip("\n")
        if staged == f"100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0\t{name}":
            cleared = _git(workspace, "update-index", "--force-remove", "--", name)
            if cleared.returncode != 0:
                raise SystemExit(f"could not clear old frontier index placeholder: {cleared.stderr.strip()}")
    if _git(workspace, "status", "--porcelain", "--untracked-files=normal").stdout.strip():
        restored = _git(workspace, "apply", str(old_patch))
        if restored.returncode != 0:
            raise SystemExit(f"could not restore previous frontier: {restored.stderr.strip()}")
        return False
    applied = _git(workspace, "apply", str(current_patch))
    if applied.returncode != 0:
        restored = _git(workspace, "apply", str(old_patch))
        if restored.returncode != 0:
            raise SystemExit(f"could not restore previous frontier: {restored.stderr.strip()}")
        raise SystemExit(f"new frontier failed after clean migration: {applied.stderr.strip()}")
    marker.write_text(json.dumps({"patchSha256": current_digest}) + "\n")
    return True


def apply_frontier(root: Path, workspace: Path, baseline: Path, config: dict,
                   *, backend: str | None = None) -> None:
    frontier_dir = (root / "frontier" if backend is None else
                    root / "frontier/proof-v2" / backend)
    manifest_path = frontier_dir / "manifest.json"
    patch = frontier_dir / "changes.patch"
    if not manifest_path.is_file() and not patch.is_file():
        return
    if not manifest_path.is_file() or not patch.is_file():
        raise SystemExit("frontier manifest and patch must both exist")
    manifest = json.loads(manifest_path.read_text())
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    expected_schema = ("stwo-cuda-frontier-v1" if backend is None else
                       "stwo-proof-v2-frontier-v1")
    if (manifest.get("schema") != expected_schema or
            (backend is not None and manifest.get("backend") != backend) or
            manifest.get("sourceCommit") != config["sourceCommit"] or
            manifest.get("patchSha256") != digest):
        raise SystemExit("frontier manifest does not match the pinned source and patch")
    check_patch(patch, baseline, config, backend=backend)

    marker_name = ("stwo-cuda-frontier.json" if backend is None else
                   f"stwo-proof-v2-{backend}-frontier.json")
    marker_result = _git(workspace, "rev-parse", "--git-path", marker_name)
    if marker_result.returncode != 0:
        raise SystemExit(marker_result.stderr.strip())
    marker = Path(marker_result.stdout.strip())
    if not marker.is_absolute():
        marker = workspace / marker
    tracked_dirty = bool(_git(workspace, "diff", "--name-only", "HEAD").stdout.strip())
    if marker.is_file():
        previous_digest = json.loads(marker.read_text()).get("patchSha256")
        if previous_digest == digest and tracked_dirty:
            current_diff = subprocess.check_output(
                ["git", "-C", str(workspace), "diff", "--binary", "HEAD"])
            if hashlib.sha256(current_diff).hexdigest() != digest:
                raise SystemExit("editable workspace has changes beyond the accepted frontier; capture them before setup")
            print(f"Accepted frontier PR #{manifest['prNumber']} already applied")
            return
        if (previous_digest != digest and previous_digest == manifest.get("parentPatchSha256")
                and _migrate_unchanged_frontier(root, workspace, marker, previous_digest,
                                                patch, digest, frontier_dir / "history")):
            print(f"Advanced accepted frontier to PR #{manifest['prNumber']} ({digest[:12]})")
            return
    if _git(workspace, "apply", "--reverse", "--check", str(patch)).returncode == 0:
        marker.write_text(json.dumps({"patchSha256": digest}) + "\n")
        print(f"Accepted frontier PR #{manifest['prNumber']} already applied")
        return
    if tracked_dirty:
        raise SystemExit("editable workspace has changes beyond the accepted frontier; capture them before starting a fresh checkout")
    check = _git(workspace, "apply", "--check", str(patch))
    if check.returncode != 0:
        raise SystemExit(f"accepted frontier does not apply: {check.stderr.strip()}")
    result = _git(workspace, "apply", str(patch))
    if result.returncode != 0:
        raise SystemExit(f"accepted frontier failed: {result.stderr.strip()}")
    marker.write_text(json.dumps({"patchSha256": digest}) + "\n")
    print(f"Applied accepted frontier PR #{manifest['prNumber']} ({digest[:12]})")
