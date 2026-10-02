#!/usr/bin/env python3
"""Fail early on missing preparation, direct, or sandboxed-judge prerequisites.

This is an operator convenience check, not a qualification or ranked receipt.
It reads and hashes public assets before opening CUDA. Judge mode additionally
checks the exact local Docker image and exercises the sandbox/quota probe.
"""

import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.run_arm import Nvml, checked_file, sha
from harness.sandbox import IMAGE, RUNTIME_FILES
from harness.cuda_toolchain import cuda_build_options
from scripts.public_blobs import items
from scripts.setup import PREPROCESSED_SHA256, CAIRO_ARTIFACTS


BUILD_PROCESSES = frozenset({"zig", "nvcc", "ptxas", "cicc", "fatbinary",
                             "cc1plus", "cargo", "rustc"})


def command_output(*command: str) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT,
                                   timeout=15).strip()


def check_image(image: str) -> str:
    if not IMAGE.fullmatch(image):
        raise RuntimeError("sandbox image must be a pinned SHA-256 image ID or digest")
    if not shutil.which("docker"):
        raise RuntimeError("Docker is missing; sandboxed judge cannot run")
    command_output("docker", "info", "--format", "{{.ServerVersion}}")
    image_id = command_output("docker", "image", "inspect", "--format", "{{.Id}}", image)
    if not IMAGE.fullmatch(image_id):
        raise RuntimeError("Docker did not return a pinned image ID")
    if image.startswith("sha256:") and image_id != image:
        raise RuntimeError("local sandbox image ID differs")
    return image_id


def check_mount_capability() -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("sandboxed judge requires Linux")
    if not shutil.which("mount") or not shutil.which("mkfs.ext4"):
        raise RuntimeError("sandboxed judge requires mount and mkfs.ext4")
    if os.geteuid() == 0:
        status = Path("/proc/self/status").read_text()
        caps = next((line.split()[1] for line in status.splitlines()
                     if line.startswith("CapEff:")), "0")
        if not (int(caps, 16) & (1 << 21)):
            raise RuntimeError("CAP_SYS_ADMIN is missing; output-image mount will fail")
    elif not shutil.which("sudo") or subprocess.run(
            ["sudo", "-n", "true"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=10).returncode:
        raise RuntimeError("judge needs root or passwordless sudo for output-image mounts")


def check_no_other_builds(proc: Path = Path("/proc")) -> None:
    """Reject noisy Linux build hosts before the first measured command."""
    if not proc.is_dir():
        raise RuntimeError("H200 measurement preflight requires Linux /proc")
    own_pid = os.getpid()
    conflicts = []
    for entry in proc.iterdir():
        if not entry.name.isdecimal() or int(entry.name) == own_pid:
            continue
        try:
            raw = (entry / "cmdline").read_bytes().split(b"\0", 1)[0]
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.EACCES, errno.EPERM, errno.ESRCH):
                raise
            continue
        name = os.fsdecode(raw).rsplit("/", 1)[-1]
        if name in BUILD_PROCESSES:
            conflicts.append((int(entry.name), name))
    if conflicts:
        sample = ", ".join(f"{name} pid={pid}" for pid, name in conflicts[:5])
        raise RuntimeError(f"concurrent build processes on H200 host: {sample}")


def check_no_gpu_processes() -> None:
    """An idle-memory reading alone can miss another live CUDA context."""
    if not shutil.which("nvidia-smi"):
        raise RuntimeError("nvidia-smi is required to check GPU process exclusivity")
    output = command_output("nvidia-smi", "--query-compute-apps=pid",
                            "--format=csv,noheader,nounits")
    pids = [line.strip() for line in output.splitlines() if line.strip()]
    if pids and not (len(pids) == 1 and pids[0].startswith("No running processes")):
        raise RuntimeError(f"GPU has active compute processes: {', '.join(pids[:5])}")


def check_host_idle() -> None:
    """Call before each direct proof; preflight alone cannot reserve a host."""
    check_no_other_builds()
    check_no_gpu_processes()


def check_build_cache() -> dict:
    """Report the actual writable cache used across baseline/candidate builds."""
    paths = {"archive": Path(os.environ["STWO_CUDA_ARCHIVE_CACHE"])}
    if os.environ.get("STWO_CUDA_CCACHE", "1") != "0":
        paths["ccache"] = Path(os.environ["CCACHE_DIR"])
    resolved = {}
    for name, path in paths.items():
        if not path.is_dir() or not os.access(path, os.W_OK | os.X_OK):
            raise RuntimeError(f"CUDA {name} cache is unavailable or unwritable: {path}")
        resolved[name] = str(path.resolve())
    return resolved


def file_identity(path: Path) -> dict:
    """Cheap invalidation key for already hash-checked, shared direct-run inputs."""
    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    if not resolved.is_file():
        raise RuntimeError(f"shared asset is not a file: {resolved}")
    return {"path": str(resolved), "device": stat.st_dev, "inode": stat.st_ino,
            "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "ctime_ns": stat.st_ctime_ns}


def shared_asset_snapshot(manifest: Path, preprocessed: Path,
                          fixtures: Path, fixture_items: list[dict]) -> dict:
    return {"manifest": file_identity(manifest),
            "preprocessed": file_identity(preprocessed),
            "fixtures": {item["path"]: file_identity(fixtures / item["path"])
                         for item in fixture_items}}


def check_source(source: Path, commit: str, artifacts: Path) -> dict:
    head = command_output("git", "-C", str(source), "rev-parse", "HEAD")
    if head != commit:
        raise RuntimeError(f"source HEAD is {head}, expected pinned {commit}")
    for name in RUNTIME_FILES:
        if not (source / name).is_file():
            raise RuntimeError(f"source runtime file missing: {source / name}")
    library = json.loads((source / "vectors/cairo/official/air_template_library_v1.json").read_text())
    names = set(CAIRO_ARTIFACTS)
    for entry in library["sources"]:
        bundle = entry["bundle"]
        name = str(Path("official") / bundle["path"])
        if Path(bundle["path"]).is_absolute() or ".." in Path(bundle["path"]).parts:
            raise RuntimeError(f"unsafe AIR bundle path: {name}")
        names.add(name)
        path = source / "vectors/cairo" / name
        if path.stat().st_size != bundle["bytes"] or sha(path) != bundle["sha256"]:
            raise RuntimeError(f"pinned AIR bundle differs: {name}")
    for name in sorted(names):
        original = source / "vectors/cairo" / name
        staged = artifacts / name
        if not original.is_file() or not staged.is_file() or sha(original) != sha(staged):
            raise RuntimeError(f"staged CUDA artifact missing or differs: {name}")
    return {"source_commit": head, "runtime_files": len(RUNTIME_FILES),
            "verified_cuda_artifacts": len(names)}


def preflight(*, mode: str, source: Path, fixtures: Path, manifest: Path,
              preprocessed: Path, artifacts: Path, verifier: Path,
              registry_verifier: Path, case_ids: set[str] | None = None,
              image: str | None = None, probe: bool = True,
              shared_asset_attestation: dict | None = None) -> dict:
    config = json.loads((ROOT / "benchmark.json").read_text())
    contract = json.loads(manifest.read_text())
    if (contract["contract_epoch"] != config["contractEpoch"] or
            contract["source_commit"] != config["sourceCommit"]):
        raise RuntimeError("fixture manifest is not bound to pinned epoch and source")
    selected = [case for case in contract["cases"] if case_ids is None or case["id"] in case_ids]
    if not selected or (case_ids and len(selected) != len(case_ids)):
        raise RuntimeError("unknown or empty case selection")
    if mode == "judge":
        if image is None:
            raise RuntimeError("judge mode requires --image with a local pinned sandbox image")
        # Check the failure seen by participants before hashing a multi-GB asset.
        image_id = check_image(image)
        check_mount_capability()
    elif mode not in ("prepare", "direct"):
        raise RuntimeError("mode must be prepare, direct, or judge")
    if shared_asset_attestation is not None and mode != "direct":
        raise RuntimeError("shared asset reuse is only allowed for direct diagnostics")
    for tool in ("git", "zig", "nvcc", "cargo"):
        if not shutil.which(tool):
            raise RuntimeError(f"required toolchain command missing: {tool}")
    if command_output("zig", "version") != "0.15.2":
        raise RuntimeError("Zig 0.15.2 is required")
    build_options = cuda_build_options()
    caches = check_build_cache()
    result = {"schema": "stwo-h200-preflight-v1", "mode": mode,
              "qualification": "prerequisites-only", "contract_epoch": config["contractEpoch"],
              "cases": [case["id"] for case in selected],
              "toolchain": {tool: command_output(tool, "--version").splitlines()[0]
                            for tool in ("nvcc", "cargo")},
              "cuda_build_options": build_options,
              "build_cache": caches,
              "sources": check_source(source, config["sourceCommit"], artifacts)}
    fixture_items = items(contract, case_ids)
    if shared_asset_attestation is None:
        if not preprocessed.is_file() or sha(preprocessed) != PREPROCESSED_SHA256:
            raise RuntimeError("canonical preprocessing asset missing or hash differs")
        for item in fixture_items:
            checked_file(fixtures, item)
        result["shared_asset_verification"] = "full-sha256"
    else:
        prior = shared_asset_attestation
        current_snapshot = shared_asset_snapshot(manifest, preprocessed, fixtures,
                                                 fixture_items)
        prior_snapshot = prior.get("shared_asset_snapshot", {})
        prior_fixtures = prior_snapshot.get("fixtures", {})
        if (prior.get("mode") != "direct" or
                prior.get("shared_asset_verification") not in
                ("full-sha256", "incremental-full-sha256-with-file-identity",
                 "reused-full-sha256-with-file-identity") or
                prior.get("contract_epoch") != config["contractEpoch"] or
                current_snapshot["manifest"] != prior_snapshot.get("manifest") or
                current_snapshot["preprocessed"] != prior_snapshot.get("preprocessed")):
            raise RuntimeError("shared direct-run assets changed or lack a full SHA-256 attestation")
        newly_hashed = 0
        for item in fixture_items:
            path = item["path"]
            identity = current_snapshot["fixtures"][path]
            if identity == prior_fixtures.get(path):
                continue
            checked_file(fixtures, item)
            if file_identity(fixtures / path) != identity:
                raise RuntimeError(f"shared direct-run asset changed during hashing: {path}")
            newly_hashed += 1
        result["shared_asset_verification"] = (
            "incremental-full-sha256-with-file-identity" if newly_hashed else
            "reused-full-sha256-with-file-identity")
        result["newly_hashed_fixture_files"] = newly_hashed
    result["shared_asset_snapshot"] = shared_asset_snapshot(manifest, preprocessed,
                                                             fixtures, fixture_items)
    for binary in (source / "zig-out/bin/stwo-cairo-cuda",
                   source / "zig-out/bin/stwo-circuit-recursion-cuda", verifier,
                   registry_verifier):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError(f"required executable missing: {binary}")
    result["binary_sha256"] = {path.name: sha(path) for path in (
        source / "zig-out/bin/stwo-cairo-cuda",
        source / "zig-out/bin/stwo-circuit-recursion-cuda", verifier, registry_verifier)}
    result["preprocessed_sha256"] = PREPROCESSED_SHA256
    result["verified_fixture_files"] = len(fixture_items)
    if mode == "judge":
        result["sandbox_image_id"] = image_id
        if probe:
            from scripts.probe_sandbox import probe as probe_sandbox
            probe_sandbox(image)
            result["sandbox_probe"] = "passed"
    if mode != "prepare":
        check_host_idle()
        nvml = Nvml(config["hardware"]["deviceBytes"])
        try:
            result["idle_device_bytes"] = nvml.read().used
        finally:
            nvml.close()
    else:
        result["gpu_check"] = "deferred to direct or judge preflight"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare", "direct", "judge"), required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "workspace/baseline")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "data/inputs")
    parser.add_argument("--manifest", type=Path, default=ROOT / "fixtures/public-v1.json")
    parser.add_argument("--preprocessed", type=Path,
                        default=ROOT / ".cache/preprocessed-canonical.bin")
    parser.add_argument("--artifacts", type=Path, default=ROOT / ".cache/cuda-artifacts")
    parser.add_argument("--verifier", type=Path,
                        default=ROOT / ".cache/rust-official/release/stwo-cairo-official-verifier")
    parser.add_argument("--registry-verifier", type=Path,
                        default=ROOT / ".cache/rust-registry/release/verify_cairo_cuda_json")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--image", help="required in judge mode; set STWO_SANDBOX_IMAGE or pass this")
    parser.add_argument("--out", type=Path, help="write preflight receipt outside Git")
    args = parser.parse_args()
    try:
        result = preflight(mode=args.mode, source=args.source.resolve(),
                           fixtures=args.fixtures.resolve(), manifest=args.manifest.resolve(),
                           preprocessed=args.preprocessed.resolve(), artifacts=args.artifacts.resolve(),
                           verifier=args.verifier.resolve(),
                           registry_verifier=args.registry_verifier.resolve(),
                           case_ids=set(args.case_id) if args.case_id else None,
                           image=args.image or os.environ.get("STWO_SANDBOX_IMAGE"))
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"H200 preflight failed: {error}\n")
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data)
    print(data, end="")


if __name__ == "__main__":
    main()
