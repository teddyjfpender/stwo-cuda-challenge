import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import challenge


class ParticipantCliTests(unittest.TestCase):
    def test_setup_forwards_build_option_from_repository_root(self):
        with patch("challenge.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(challenge.main(["setup-proof", "--backend", "metal", "--build"]), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[-4:], ["scripts/setup_proof_v2.py", "--backend", "metal", "--build"])
        self.assertEqual(run.call_args.kwargs["cwd"], challenge.ROOT)

    def test_paths_requires_a_backend_instead_of_guessing_one(self):
        with patch("challenge.subprocess.run") as run:
            self.assertEqual(challenge.main(["paths"]), 2)
        run.assert_not_called()

    def test_paths_explains_generated_checkout_and_allowed_directories(self):
        output = StringIO()
        with redirect_stdout(output), patch("challenge.subprocess.run") as run:
            self.assertEqual(challenge.main(["paths", "--backend", "metal"]), 0)
        run.assert_not_called()
        self.assertIn("workspace/proof-v2-source", output.getvalue())
        self.assertIn("src/integrations/cairo_metal", output.getvalue())
        self.assertIn("candidate/proof-v2-changes.patch", output.getvalue())


if __name__ == "__main__":
    unittest.main()
