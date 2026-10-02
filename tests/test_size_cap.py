"""Phase 3 guard: an over-cap meta file is SKIPPED(size), never passed and never failed (plan §4, §5.2 G14)."""
import unittest

from conformance.checks import MAX_META_BYTES, run_all
from tests.test_controls import REAL_CUBE, check
from conformance.inspect_local import LocalView


class OversizeView(LocalView):
    """The cube fixture, but pretending episodes.jsonl is over the 2 MB cap."""

    def __init__(self, root, listing_complete=True):
        super().__init__(root)
        self.files["meta/episodes.jsonl"] = MAX_META_BYTES + 1
        self.listing_complete = listing_complete


@unittest.skipUnless(REAL_CUBE.is_dir(), "needs fixtures/cube_to_bowl_5")
class SizeCap(unittest.TestCase):
    def test_oversize_episodes_skips_not_fails(self):
        r = run_all(OversizeView(REAL_CUBE))
        self.assertIsNone(check(r, "G2")["passed"])
        self.assertIn("SKIPPED(size)", check(r, "G2")["detail"])
        self.assertIsNone(check(r, "G14")["passed"])
        self.assertEqual(r["verdict"], "READY")  # a skip must not move the verdict...
        self.assertEqual(r["unverified_size"], ["G2", "G14"])  # ...but must be declared

    def test_capped_listing_skips_g14(self):
        v = LocalView(REAL_CUBE)
        v.listing_complete = False
        r = run_all(v)
        self.assertIsNone(check(r, "G14")["passed"])
        self.assertEqual(check(r, "G14")["blocked_by"], "size")


if __name__ == "__main__":
    unittest.main()
