import unittest

from scripts.qualify_proof_v2 import exact_stage_ns


class ProofStageTelemetryTests(unittest.TestCase):
    def test_exact_stage_count_and_no_duplicate_lines(self):
        log = ("circuit-proof-stage kind=cairo ns=100\n"
               "circuit-proof-stage kind=wrap ns=200\n")
        self.assertEqual(exact_stage_ns(log, ["cairo", "wrap"]), [100, 200])
        with self.assertRaisesRegex(ValueError, "telemetry differs"):
            exact_stage_ns(log + "circuit-proof-stage kind=wrap ns=1\n",
                           ["cairo", "wrap"])
        self.assertEqual(exact_stage_ns("old prover log\n", ["cairo", "wrap"]), [])


if __name__ == "__main__":
    unittest.main()
