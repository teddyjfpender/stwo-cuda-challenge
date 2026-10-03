from pathlib import Path
import tempfile
import unittest

from harness.timer_owner import attest, digest


class TimerOwnerTests(unittest.TestCase):
    def test_timer_is_outside_candidate_patch_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            owner = source / "src/integrations/cairo_cuda/timer.zig"
            owner.parent.mkdir(parents=True)
            owner.write_text("trusted\n")
            config = {"backends": {"cuda": {
                "editablePaths": ["src/integrations/cairo_cuda"],
                "protectedPaths": ["src/integrations/cairo_cuda/timer.zig"],
                "timerFiles": ["src/integrations/cairo_cuda/timer.zig"],
                "timerDigest": digest(source, ["src/integrations/cairo_cuda/timer.zig"]),
            }}}
            self.assertEqual(attest(source, config, "cuda"), config["backends"]["cuda"]["timerDigest"])
            owner.write_text("candidate\n")
            with self.assertRaisesRegex(ValueError, "timer owner changed"):
                attest(source, config, "cuda")
            config["backends"]["cuda"]["protectedPaths"] = []
            with self.assertRaisesRegex(ValueError, "timer owner remains editable"):
                attest(source, config, "cuda")


if __name__ == "__main__":
    unittest.main()
