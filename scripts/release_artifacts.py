#!/usr/bin/env python3
"""Build metadata and verified download for fixed Rust verifier release assets."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "release-artifacts.lock.json"
REPOSITORY = "https://github.com/teddyjfpender/stwo-cuda-challenge"
TOOLS = {
    "official": ("stwo-cairo-official-verifier", ".cache/rust-official/release/stwo-cairo-official-verifier"),
    "registry": ("verify_cairo_cuda_json", ".cache/rust-registry/release/verify_cairo_cuda_json"),
}
PLATFORM = "linux-x86_64-glibc-2.39"
MAX_MANIFEST_BYTES = 65536
MAX_BINARY_BYTES = 100_000_000
MAX_PREPROCESSED_BYTES = 4_000_000_000
CHUNK_BYTES = 512 * 1024 * 1024
PREPROCESSED_SHA256 = "4d4fda06dfa3bca19554510a158f6c50abad06a74d29c17885ed4cbb88ada34d"
HEX = re.compile(r"[0-9a-f]{64}\Z")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: dict) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def platform_supported() -> bool:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        return False
    libc, version = platform.libc_ver()
    try:
        return libc == "glibc" and tuple(map(int, version.split(".")[:2])) >= (2, 39)
    except ValueError:
        return False


def validate_manifest(manifest: dict, source_commit: str) -> None:
    if manifest.get("schema") != 1 or manifest.get("source_commit") != source_commit:
        raise ValueError("release manifest source or schema differs from pinned contract")
    if manifest.get("platform") != PLATFORM or set(manifest.get("tools", {})) != set(TOOLS):
        raise ValueError("release manifest platform or tools differ")
    if not isinstance(manifest.get("toolchains"), dict) or set(manifest["toolchains"]) != set(TOOLS) | {"zig"}:
        raise ValueError("release manifest toolchains are missing")
    for tool, (asset, _) in TOOLS.items():
        item = manifest["tools"][tool]
        if item.get("asset") != asset or not HEX.fullmatch(str(item.get("sha256", ""))):
            raise ValueError(f"release manifest has invalid {tool} asset")
        if type(item.get("bytes")) is not int or not 0 < item["bytes"] <= MAX_BINARY_BYTES:
            raise ValueError(f"release manifest has invalid {tool} size")
        if not isinstance(manifest["toolchains"][tool], str) or not manifest["toolchains"][tool]:
            raise ValueError(f"release manifest has invalid {tool} toolchain")
    if not isinstance(manifest["toolchains"]["zig"], str) or not manifest["toolchains"]["zig"]:
        raise ValueError("release manifest Zig toolchain is invalid")
    preprocessed = manifest.get("preprocessed", {})
    if preprocessed.get("sha256") != PREPROCESSED_SHA256:
        raise ValueError("release preprocessing digest differs from pinned reference")
    if type(preprocessed.get("bytes")) is not int or not 0 < preprocessed["bytes"] <= MAX_PREPROCESSED_BYTES:
        raise ValueError("release preprocessing size is invalid")
    chunks = preprocessed.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("release preprocessing chunks are missing")
    size = 0
    for index, chunk in enumerate(chunks):
        if chunk.get("asset") != f"preprocessed-{index:03d}.part":
            raise ValueError("release preprocessing chunk name is invalid")
        if not HEX.fullmatch(str(chunk.get("sha256", ""))):
            raise ValueError("release preprocessing chunk digest is invalid")
        if type(chunk.get("bytes")) is not int or not 0 < chunk["bytes"] <= CHUNK_BYTES:
            raise ValueError("release preprocessing chunk size is invalid")
        size += chunk["bytes"]
    if size != preprocessed["bytes"]:
        raise ValueError("release preprocessing chunk sizes differ")


def read_url(url: str, limit: int) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"release asset exceeds {limit} bytes")
    return data


def release_url(tag: str, asset: str) -> str:
    if not re.fullmatch(r"fixed-rust-[a-z0-9_-]+", tag):
        raise ValueError("invalid fixed Rust release tag")
    if asset not in ("manifest.json", *(item[0] for item in TOOLS.values())) and not re.fullmatch(r"preprocessed-[0-9]{3}\.part", asset):
        raise ValueError("unexpected fixed Rust release asset")
    return f"{REPOSITORY}/releases/download/{tag}/{asset}"


def pinned_manifest(source_commit: str, lock_path: Path) -> tuple[str, dict] | None:
    """Return the manifest only when its hash is committed in this repository."""
    if not platform_supported() or not lock_path.is_file():
        return None
    lock = json.loads(lock_path.read_text())
    if lock["schema"] != 1 or lock["source_commit"] != source_commit:
        raise ValueError("release lock source or schema differs")
    if PLATFORM not in lock["platforms"]:
        return None
    entry = lock["platforms"][PLATFORM]
    tag, digest = entry["tag"], entry["manifest_sha256"]
    if not HEX.fullmatch(digest):
        raise ValueError("release manifest digest is invalid")
    raw = read_url(release_url(tag, "manifest.json"), MAX_MANIFEST_BYTES)
    if sha_bytes(raw) != digest:
        raise ValueError("release manifest digest differs from repository pin")
    manifest = json.loads(raw)
    validate_manifest(manifest, source_commit)
    return tag, manifest


def install(source_commit: str, root: Path = ROOT, lock_path: Path = LOCK) -> bool:
    """Install pinned release binaries. False means build from source instead."""
    try:
        pinned = pinned_manifest(source_commit, lock_path)
        if pinned is None:
            return False
        tag, manifest = pinned
        staged = []
        try:
            for tool, (_, path) in TOOLS.items():
                item = manifest["tools"][tool]
                destination = root / path
                if destination.is_file() and not destination.is_symlink() and destination.stat().st_size == item["bytes"]:
                    if sha_bytes(destination.read_bytes()) == item["sha256"]:
                        destination.chmod(destination.stat().st_mode | 0o111)
                        continue
                data = read_url(release_url(tag, item["asset"]), item["bytes"])
                if len(data) != item["bytes"] or sha_bytes(data) != item["sha256"]:
                    raise ValueError(f"release {tool} binary differs from pinned manifest")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as file:
                    file.write(data)
                    temporary = Path(file.name)
                temporary.chmod(0o755)
                staged.append((temporary, destination))
            for temporary, destination in staged:
                os.replace(temporary, destination)
            return True
        finally:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(f"Pinned Rust release unavailable ({error}); building from source", flush=True)
        return False


def install_preprocessed(source_commit: str, destination: Path, lock_path: Path = LOCK) -> bool:
    """Stream verified release chunks to the canonical asset destination."""
    try:
        pinned = pinned_manifest(source_commit, lock_path)
        if pinned is None:
            return False
        tag, manifest = pinned
        item = manifest["preprocessed"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as file:
            temporary = Path(file.name)
            whole = hashlib.sha256()
            total = 0
            try:
                for chunk in item["chunks"]:
                    digest = hashlib.sha256()
                    received = 0
                    with urllib.request.urlopen(release_url(tag, chunk["asset"]), timeout=60) as response:
                        while block := response.read(min(1 << 20, chunk["bytes"] - received + 1)):
                            received += len(block)
                            if received > chunk["bytes"]:
                                raise ValueError("release preprocessing chunk exceeds manifest size")
                            digest.update(block)
                            whole.update(block)
                            file.write(block)
                    if received != chunk["bytes"] or digest.hexdigest() != chunk["sha256"]:
                        raise ValueError("release preprocessing chunk differs from manifest")
                    total += received
                if total != item["bytes"] or whole.hexdigest() != PREPROCESSED_SHA256:
                    raise ValueError("release preprocessing asset differs from pinned reference")
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return True
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(f"Pinned preprocessing release unavailable ({error}); generating from source", flush=True)
        return False


def make_manifest(source_commit: str, output: Path, official: Path, registry: Path,
                  preprocessed: Path, official_toolchain: str, registry_toolchain: str,
                  zig_toolchain: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be a full SHA-1")
    binaries = {"official": official, "registry": registry}
    tools = {}
    for name, path in binaries.items():
        data = path.read_bytes()
        if not 0 < len(data) <= MAX_BINARY_BYTES:
            raise ValueError(f"invalid {name} binary size")
        tools[name] = {"asset": TOOLS[name][0], "bytes": len(data), "sha256": sha_bytes(data)}
    chunks = []
    whole = hashlib.sha256()
    total = 0
    with preprocessed.open("rb") as source:
        for index, data in enumerate(iter(lambda: source.read(CHUNK_BYTES), b"")):
            name = f"preprocessed-{index:03d}.part"
            (output.parent / name).write_bytes(data)
            chunks.append({"asset": name, "bytes": len(data), "sha256": sha_bytes(data)})
            whole.update(data)
            total += len(data)
    if whole.hexdigest() != PREPROCESSED_SHA256:
        raise ValueError("generated preprocessing asset differs from pinned reference")
    manifest = {"schema": 1, "source_commit": source_commit, "platform": PLATFORM,
                "toolchains": {"official": official_toolchain, "registry": registry_toolchain,
                               "zig": zig_toolchain},
                "tools": tools,
                "preprocessed": {"sha256": PREPROCESSED_SHA256, "bytes": total,
                                 "chunks": chunks}}
    validate_manifest(manifest, source_commit)
    output.write_bytes(canonical(manifest))


def make_lock(source_commit: str, tag: str, manifest_path: Path, output: Path) -> None:
    validate_manifest(json.loads(manifest_path.read_bytes()), source_commit)
    release_url(tag, "manifest.json")
    lock = {"schema": 1, "source_commit": source_commit,
            "platforms": {PLATFORM: {"tag": tag,
                                    "manifest_sha256": sha_bytes(manifest_path.read_bytes())}}}
    output.write_bytes(canonical(lock))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("--source-commit", required=True)
    manifest.add_argument("--official", type=Path, required=True)
    manifest.add_argument("--registry", type=Path, required=True)
    manifest.add_argument("--preprocessed", type=Path, required=True)
    manifest.add_argument("--official-toolchain", required=True)
    manifest.add_argument("--registry-toolchain", required=True)
    manifest.add_argument("--zig-toolchain", required=True)
    manifest.add_argument("--out", type=Path, required=True)
    lock = sub.add_parser("lock")
    lock.add_argument("--source-commit", required=True)
    lock.add_argument("--tag", required=True)
    lock.add_argument("--manifest", type=Path, required=True)
    lock.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "manifest":
        make_manifest(args.source_commit, args.out, args.official, args.registry,
                      args.preprocessed, args.official_toolchain, args.registry_toolchain,
                      args.zig_toolchain)
    else:
        make_lock(args.source_commit, args.tag, args.manifest, args.out)


if __name__ == "__main__":
    main()
