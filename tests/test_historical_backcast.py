"""Keep modeled history distinct from verifier-qualified measurements."""

import unittest

from scripts.blend_proof_history import predict


class BackcastTest(unittest.TestCase):
    def test_prediction_interval_contains_estimate(self):
        estimate, low, high = predict([(37, 3.58), (39, 3.77), (41, 2.90), (42, 2.48)], 33)
        self.assertLess(low, estimate)
        self.assertLess(estimate, high)
        self.assertGreater(estimate, 4)

    def test_requires_multiple_verified_anchors(self):
        with self.assertRaises(ValueError):
            predict([(39, 3.78), (41, 2.92)], 33)


if __name__ == "__main__":
    unittest.main()
