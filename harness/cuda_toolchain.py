"""Resolve the explicit Linux CUDA toolchain required by pinned stwo-zig."""

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def _executable(name: str, setting: str) -> Path:
    value = os.environ.get(setting) or shutil.which(name)
    if not value:
        raise ValueError(f"{setting} or executable {name} is required for the CUDA build")
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f"CUDA build executable is missing: {path}")
    return path


def _runtime(compiler: Path, library: str, setting: str) -> Path:
    value = os.environ.get(setting)
    if not value:
        value = subprocess.check_output([str(compiler), f"-print-file-name={library}"],
                                        text=True).strip()
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f"CUDA host runtime is missing: {path}")
    return path


def _ccache() -> tuple[Path, str] | None:
    setting = os.environ.get("STWO_CUDA_CCACHE", "1")
    if setting not in ("0", "1"):
        raise ValueError("STWO_CUDA_CCACHE must be 0 or 1")
    if setting == "0":
        return None
    path = _executable("ccache", "STWO_CUDA_CCACHE_BIN")
    output = subprocess.check_output([str(path), "--version"], text=True)
    match = re.search(r"ccache version (\d+)\.(\d+)(?:\.(\d+))?", output)
    if match is None or (int(match[1]), int(match[2])) < (4, 0):
        raise ValueError("H200 CUDA builds require ccache version 4.0 or newer")
    return path, match.group(0)


def _nvcc_wrapper(nvcc: Path, cache: tuple[Path, str] | None,
                  threads: int, root: Path) -> Path:
    """Give Zig's single executable-path option a stable nvcc command wrapper."""
    directory = root / "toolchain"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "nvcc"
    compiler = shlex.quote(str(nvcc))
    command = (f"{shlex.quote(str(cache[0]))} {compiler}"
               if cache is not None else compiler)
    script = (
        "#!/bin/sh\nset -eu\n"
        f"# {cache[1] if cache is not None else 'ccache disabled'}\n"
        'if [ "$#" -eq 1 ] && [ "$1" = "--version" ]; then\n'
        f'  exec {compiler} "$@"\n'
        "fi\n"
        f'exec {command} --threads={threads} "$@"\n'
    )
    if not path.is_file() or path.read_text() != script:
        staged = directory / f".nvcc-{os.getpid()}"
        staged.write_text(script)
        staged.chmod(0o755)
        os.replace(staged, path)
    path.chmod(0o755)
    return path


def cuda_build_options() -> list[str]:
    nvcc = _executable("nvcc", "STWO_CUDA_NVCC")
    cxx = _executable("g++", "STWO_CUDA_HOST_CXX")
    ar = _executable("ar", "STWO_CUDA_AR")
    home = Path(os.environ.get("STWO_CUDA_HOME") or nvcc.parent.parent).resolve()
    library_dir = Path(os.environ.get("STWO_CUDA_LIBRARY_DIR") or home / "lib64").resolve()
    if not (home.is_dir() and library_dir.is_dir() and
            (library_dir / "libcudart.so").exists()):
        raise ValueError("CUDA toolkit root or runtime library directory is missing")
    arch = os.environ.get("STWO_CUDA_ARCH", "90")
    if arch != "90":
        raise ValueError("H200 (SM 90) challenge builds require STWO_CUDA_ARCH=90")
    jobs = os.environ.get("STWO_CUDA_BUILD_JOBS", "4")
    if not jobs.isdecimal() or not 1 <= int(jobs) <= 16:
        raise ValueError("STWO_CUDA_BUILD_JOBS must be between 1 and 16")
    default_threads = max(1, min(2, (os.cpu_count() or 1) // int(jobs)))
    threads = os.environ.get("STWO_CUDA_NVCC_THREADS", str(default_threads))
    if not threads.isdecimal() or not 1 <= int(threads) <= 16:
        raise ValueError("STWO_CUDA_NVCC_THREADS must be between 1 and 16")
    cache_setting = os.environ.get("STWO_CUDA_BUILD_CACHE_ROOT")
    if cache_setting is not None and not Path(cache_setting).is_absolute():
        raise ValueError("STWO_CUDA_BUILD_CACHE_ROOT must be absolute")
    cache_root = Path(cache_setting or ROOT / ".cache").resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    archive_cache = cache_root / "cuda-archives"
    archive_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("STWO_CUDA_ARCHIVE_CACHE", str(archive_cache))
    cache = _ccache()
    if cache is not None:
        ccache_dir = cache_root / "ccache"
        ccache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("CCACHE_DIR", str(ccache_dir))
        os.environ.setdefault("CCACHE_BASEDIR", str(ROOT.parent))
        os.environ.setdefault("CCACHE_MAXSIZE", "20G")
    wrapper = _nvcc_wrapper(nvcc, cache, int(threads), cache_root)
    return [
        f"-Dcuda-nvcc={wrapper}",
        f"-Dcuda-host-cxx={cxx}",
        f"-Dcuda-host-runtime={_runtime(cxx, 'libstdc++.so.6', 'STWO_CUDA_HOST_RUNTIME')}",
        f"-Dcuda-host-unwind-runtime={_runtime(cxx, 'libgcc_s.so.1', 'STWO_CUDA_HOST_UNWIND_RUNTIME')}",
        f"-Dcuda-ar={ar}",
        f"-Dcuda-home={home}",
        f"-Dcuda-library-dir={library_dir}",
        f"-Dcuda-arch={arch}",
        f"-Dcuda-build-jobs={jobs}",
    ]
