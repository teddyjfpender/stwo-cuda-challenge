"""Small tests for unranked H200 profiling receipts; no CUDA required."""

from pathlib import Path
import tempfile
import unittest

from scripts import h200_profile


class H200ProfileTests(unittest.TestCase):
    def test_memory_peak_locates_whole_device_peak(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace = Path(temporary) / "memory_trace.tsv"
            trace.write_text("elapsed_ns\tused_device_bytes\n"
                             "10000000\t100\n20000000\t250\n30000000\t180\n")
            self.assertEqual(h200_profile.memory_peak(trace), {
                "sample_peak_at_s": 0.02,
                "sample_peak_device_bytes": 250,
                "sample_count": 3,
            })

    def test_empty_memory_trace_is_not_a_valid_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace = Path(temporary) / "memory_trace.tsv"
            trace.write_text("elapsed_ns\tused_device_bytes\n")
            with self.assertRaisesRegex(RuntimeError, "no valid samples"):
                h200_profile.memory_peak(trace)


if __name__ == "__main__":
    unittest.main()
