"""Linter gate: the controls must all come out right before any audit number is trusted.

Known-good public dataset (real v2.1 `tictac-bot`) -> NEEDS_MODALITY; a deliberately
corrupted copy of it -> BLOCKED; NVIDIA's own `cube_to_bowl_5` -> READY.

Stdlib unittest (no dependencies).  Run:  python3 -m unittest discover -s tests -t . -v
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from conformance.inspect_local import inspect_local
from tests.fixtures import build_cube, edit_json, variant

ROOT = Path(__file__).resolve().parent.parent
# Real fixtures, when fetched (see NOTES.md Phase 1). Absent -> those controls are skipped, never faked.
REAL_CUBE = Path(os.environ.get("GROOT_CUBE_REAL") or ROOT / "fixtures" / "cube_to_bowl_5")
REAL_V21 = ROOT / "fixtures" / "tictac-bot"
REAL_V30 = ROOT / "fixtures" / "so101_pick_red_cube_3cams"


def failed(r):
    return {c["id"] for c in r["checks"] if c["passed"] is False and c["level"] == "FAIL"}


def check(r, id_):
    return next(c for c in r["checks"] if c["id"] == id_)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.synthetic = not REAL_CUBE.is_dir()
        cls.cube = build_cube(cls.tmp / "cube", None if cls.synthetic else REAL_CUBE)
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def var(self, mutate):
        Controls.n += 1
        return inspect_local(variant(self.cube, self.tmp / f"v{Controls.n}", mutate))

    # --- the eight gate controls -------------------------------------------------
    def test_1_positive_control_ready(self):
        r = inspect_local(self.cube)
        self.assertEqual(r["verdict"], "READY", [c for c in r["checks"] if c["passed"] is False])

    def test_2_no_meta_not_lerobot(self):
        self.assertEqual(self.var(lambda d: shutil.rmtree(d / "meta"))["verdict"], "NOT_LEROBOT")

    @unittest.skipUnless(REAL_V21.is_dir(), "real v2.1 fixture not fetched")
    def test_3_v21_needs_modality_g4_warn_does_not_move_verdict(self):
        r = inspect_local(REAL_V21)
        self.assertEqual(r["verdict"], "NEEDS_MODALITY")
        self.assertIs(check(r, "G4")["passed"], False)
        self.assertEqual(check(r, "G4")["level"], "WARN")

    @unittest.skipUnless(REAL_V30.is_dir(), "real v3.0 fixture not fetched")
    def test_4_v30_needs_downconvert(self):
        self.assertEqual(inspect_local(REAL_V30)["verdict"], "NEEDS_DOWNCONVERT")

    def test_5_modality_deleted_needs_modality(self):
        r = self.var(lambda d: (d / "meta" / "modality.json").unlink())
        self.assertEqual(r["verdict"], "NEEDS_MODALITY")
        # G10-G13 are skipped (blocked_by G6), not double-counted
        self.assertEqual(failed(r), {"G6"})
        self.assertEqual(check(r, "G12")["blocked_by"], "G6")

    def test_6_gripper_end_6_to_7_inconsistent_g12(self):
        r = self.var(lambda d: edit_json(d / "meta" / "modality.json",
                                         lambda j: j["state"]["gripper"].update(end=7)))
        self.assertEqual(r["verdict"], "INCONSISTENT_MODALITY")
        self.assertEqual(failed(r), {"G12"})

    def test_7_state_emptied_inconsistent_g11(self):
        r = self.var(lambda d: edit_json(d / "meta" / "modality.json", lambda j: j.update(state={})))
        self.assertEqual(r["verdict"], "INCONSISTENT_MODALITY")
        self.assertEqual(failed(r), {"G11"})

    def test_8_episode_parquet_deleted_needs_repair(self):
        r = self.var(lambda d: next(d.glob("data/chunk-000/episode_000002.parquet")).unlink())
        self.assertEqual(r["verdict"], "NEEDS_REPAIR")
        self.assertEqual(failed(r), {"G14"})

    # --- brief gate: known-good public dataset vs a deliberately corrupted copy -------
    @unittest.skipUnless(REAL_V21.is_dir(), "real v2.1 fixture not fetched")
    def test_gate_corrupted_public_copy_blocked(self):
        def corrupt(d):
            (d / "meta" / "episodes.jsonl").unlink()
            edit_json(d / "meta" / "info.json", lambda j: j.pop("chunks_size"))
        r = inspect_local(variant(REAL_V21, self.tmp / "tictac_corrupt", corrupt))
        self.assertEqual(r["verdict"], "BLOCKED")
        self.assertEqual(r["steps"], ["BLOCKED", "MODALITY"])
        self.assertLessEqual({"G2", "G8"}, failed(r))

    @unittest.skipUnless(REAL_V30.is_dir(), "real v3.0 fixture not fetched")
    def test_v30_metadata_only_upload_blocked_not_downconvert(self):
        r = inspect_local(variant(REAL_V30, self.tmp / "so101_meta_only", lambda d: shutil.rmtree(d / "data")))
        self.assertEqual(r["verdict"], "BLOCKED")
        self.assertIs(check(r, "L3")["passed"], False)

    def test_non_float_action_blocked_g16(self):
        r = self.var(lambda d: edit_json(d / "meta" / "info.json",
                                         lambda j: j["features"]["action"].update(dtype="int64")))
        self.assertEqual(r["verdict"], "BLOCKED")
        self.assertEqual(failed(r), {"G16"})

    def test_feature_without_dtype_blocked_g15(self):
        r = self.var(lambda d: edit_json(d / "meta" / "info.json",
                                         lambda j: j["features"]["timestamp"].pop("dtype")))
        self.assertEqual(r["verdict"], "BLOCKED")
        self.assertIn("G15", failed(r))

    def test_episode_count_mismatch_and_missing_fps_are_warn_only(self):
        def m(d):
            edit_json(d / "meta" / "info.json", lambda j: (j.update(total_episodes=j["total_episodes"] + 1), j.pop("fps")))
        r = self.var(m)
        self.assertEqual(r["verdict"], "READY")
        self.assertIs(check(r, "L11")["passed"], False)
        self.assertIs(check(r, "L12")["passed"], False)

    # --- guards against "passes everything" / "fails everything for the wrong reason" ---
    def test_missing_stats_is_warn_only(self):
        r = self.var(lambda d: (d / "meta" / "stats.json").unlink())
        self.assertEqual(r["verdict"], "READY")
        self.assertIs(check(r, "G4")["passed"], False)

    def test_repair_stacks_on_semantics(self):
        def m(d):
            (d / "meta" / "modality.json").unlink()
            next(d.glob("data/chunk-000/episode_000002.parquet")).unlink()
        r = self.var(m)
        self.assertEqual(r["verdict"], "NEEDS_MODALITY")
        self.assertEqual(r["steps"], ["MODALITY", "REPAIR"])

    def test_v3_patterns_caught_from_info_alone(self):
        def m(d):
            edit_json(d / "meta" / "info.json", lambda j: j.update(
                data_path="data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet", codebase_version="v3.0"))
            (d / "meta" / "episodes.jsonl").unlink()
            (d / "meta" / "tasks.jsonl").unlink()
        r = self.var(m)
        self.assertEqual(r["verdict"], "NEEDS_DOWNCONVERT")
        self.assertLessEqual({"G2", "G3", "G7"}, failed(r))

    def test_video_key_missing_from_features_g10(self):
        r = self.var(lambda d: edit_json(d / "meta" / "modality.json",
                                         lambda j: j["video"]["front"].update(original_key="observation.images.nope")))
        self.assertEqual(r["verdict"], "INCONSISTENT_MODALITY")
        self.assertIn("G10", failed(r))

    def test_every_g_check_cites_source(self):
        for c in inspect_local(self.cube)["checks"]:
            if c["id"].startswith("G"):
                self.assertTrue(c["source"], c["id"])


if __name__ == "__main__":
    unittest.main()
