"""The direct comparator must use proof time and reject mixed input baskets."""

import csv
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.compare_proof_v2 import compare


class CompareProofV2Tests(unittest.TestCase):
    def test_equal_family_weight_and_exact_case_set(self):
        cases = ([{"id": f"pie:{index}", "family": "pie"} for index in range(6)] +
                 [{"id": f"recursion:{index}", "family": "recursion"} for index in range(2)] +
                 [{"id": "pipeline:one", "family": "pipeline"}])
        config = {"sourceCommit": "a" * 40,
                  "backends": {"cpu": {"timerDigest": "b" * 64}}}
        fields = ("case_id", "family", "backend", "source_commit", "timer_digest",
                  "reference_match", "source_diff_sha256", "stage_total_s")
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / name for name in ("baseline.tsv", "candidate.tsv")]
            for path, candidate in zip(paths, (False, True)):
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fields, delimiter="\t")
                    writer.writeheader()
                    for case in cases:
                        writer.writerow({"case_id": case["id"], "family": case["family"],
                                         "backend": "cpu", "source_commit": config["sourceCommit"],
                                         "timer_digest": "b" * 64, "reference_match": "true",
                                         "source_diff_sha256": ("c" * 64 if candidate else
                                                                hashlib.sha256(b"").hexdigest()),
                                         "stage_total_s": 8 if candidate else 10})
            result = compare(config, {"cases": cases}, "cpu", *paths)
            self.assertAlmostEqual(result["score_like_speedup"], 1.25)
            paths[1].write_text(paths[1].read_text().replace("pipeline:one", "pie:0"))
            with self.assertRaisesRegex(ValueError, "exactly the nine public jobs"):
                compare(config, {"cases": cases}, "cpu", *paths)


if __name__ == "__main__":
    unittest.main()
