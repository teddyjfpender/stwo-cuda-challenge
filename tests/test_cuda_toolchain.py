import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.cuda_toolchain import cuda_build_options


class CudaToolchainTests(unittest.TestCase):
    def test_explicit_h200_toolchain_reaches_each_zig_build_option(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "cuda"
            (home / "lib64").mkdir(parents=True)
            files = {name: root / name for name in
                     ("nvcc", "g++", "ar", "libstdc++.so.6", "libgcc_s.so.1")}
            for path in (*files.values(), home / "lib64/libcudart.so"):
                path.touch()
            env = {
                "STWO_CUDA_NVCC": str(files["nvcc"]),
                "STWO_CUDA_HOST_CXX": str(files["g++"]),
                "STWO_CUDA_AR": str(files["ar"]),
                "STWO_CUDA_HOME": str(home),
                "STWO_CUDA_LIBRARY_DIR": str(home / "lib64"),
                "STWO_CUDA_HOST_RUNTIME": str(files["libstdc++.so.6"]),
                "STWO_CUDA_HOST_UNWIND_RUNTIME": str(files["libgcc_s.so.1"]),
                "STWO_CUDA_CCACHE": "0",
                "STWO_CUDA_BUILD_CACHE_ROOT": str(root / "cache"),
                "STWO_CUDA_NVCC_THREADS": "2",
            }
            with patch.dict(os.environ, env, clear=True):
                options = cuda_build_options()
                self.assertEqual(len(options), 9)
                self.assertIn("-Dcuda-arch=90", options)
                self.assertIn("-Dcuda-build-jobs=4", options)
                self.assertIn(f"-Dcuda-library-dir={(home / 'lib64').resolve()}", options)
                wrapper = (root / "cache/toolchain/nvcc").resolve()
                self.assertIn(f"-Dcuda-nvcc={wrapper}", options)
                self.assertIn("--threads=2", wrapper.read_text())
                self.assertEqual(os.environ["STWO_CUDA_ARCHIVE_CACHE"],
                                 str((root / "cache/cuda-archives").resolve()))
                os.environ["STWO_CUDA_ARCH"] = "80"
                with self.assertRaisesRegex(ValueError, "SM 90"):
                    cuda_build_options()

    def test_ccache_version_and_nvcc_wrapper_forward_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "cuda"
            (home / "lib64").mkdir(parents=True)
            (home / "lib64/libcudart.so").touch()
            for name in ("g++", "ar", "libstdc++.so.6", "libgcc_s.so.1"):
                (root / name).touch()
            nvcc = root / "nvcc"
            nvcc.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo nvcc-test; exit 0; fi\nprintf "%s\\n" "$@" > "$NVCC_ARGS_LOG"\n')
            nvcc.chmod(0o755)
            ccache = root / "ccache"
            ccache.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "ccache version 4.10.2"; exit 0; fi\nprintf "%s\\n" "$@" > "$CCACHE_ARGS_LOG"\nexec "$@"\n')
            ccache.chmod(0o755)
            env = {
                "STWO_CUDA_NVCC": str(nvcc),
                "STWO_CUDA_CCACHE_BIN": str(ccache),
                "STWO_CUDA_HOST_CXX": str(root / "g++"),
                "STWO_CUDA_AR": str(root / "ar"),
                "STWO_CUDA_HOME": str(home),
                "STWO_CUDA_LIBRARY_DIR": str(home / "lib64"),
                "STWO_CUDA_HOST_RUNTIME": str(root / "libstdc++.so.6"),
                "STWO_CUDA_HOST_UNWIND_RUNTIME": str(root / "libgcc_s.so.1"),
                "STWO_CUDA_BUILD_CACHE_ROOT": str(root / "cache"),
                "STWO_CUDA_NVCC_THREADS": "2",
                "NVCC_ARGS_LOG": str(root / "nvcc-args"),
                "CCACHE_ARGS_LOG": str(root / "ccache-args"),
            }
            with patch.dict(os.environ, env, clear=True):
                options = cuda_build_options()
                wrapper = Path(next(value.removeprefix("-Dcuda-nvcc=") for value in options
                                    if value.startswith("-Dcuda-nvcc=")))
                self.assertEqual(subprocess.check_output([str(wrapper), "--version"],
                                                         text=True).strip(), "nvcc-test")
                subprocess.run([str(wrapper), "-c", "kernel.cu"], check=True)
                self.assertEqual((root / "ccache-args").read_text().splitlines(),
                                 [str(nvcc.resolve()), "--threads=2", "-c", "kernel.cu"])
                self.assertEqual((root / "nvcc-args").read_text().splitlines(),
                                 ["--threads=2", "-c", "kernel.cu"])
                ccache.write_text('#!/bin/sh\necho "ccache version 3.7.12"\n')
                ccache.chmod(0o755)
                with self.assertRaisesRegex(ValueError, "4.0 or newer"):
                    cuda_build_options()


if __name__ == "__main__":
    unittest.main()
