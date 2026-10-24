"""LeRobot and openpi columns: the §1 selection table and the §6 verdicts of CONTRACT_lerobot_openpi.md.

Stdlib unittest (no dependencies).  Run:  python3 -m unittest discover -s tests -t . -v
"""
import unittest

from conformance import models as M

V3, V2 = M.LEROBOT_TARGET, M.OPENPI_TARGET


def hub(*names):
    return M.parse_versions(list(names))


SELECTION = [
    ([], ("none", None), ("none", None)),
    (["main"], ("none", None), ("none", None)),  # non-version refs are ignored
    (["v3.0"], ("ok", "v3.0"), ("forward", "v3.0")),
    (["v2.1"], ("backward", "v2.1"), ("ok", "v2.1")),
    (["v2.0"], ("backward", "v2.0"), ("ok", "v2.0")),
    (["v2.1", "v3.0"], ("ok", "v3.0"), ("ok", "v2.1")),
    (["v1.6", "v2.0", "v2.1", "v3.0"], ("ok", "v3.0"), ("ok", "v2.1")),
    (["v2.2"], ("backward", "v2.2"), ("forward", "v2.2")),
    (["v3"], ("ref_missing", "v3.0"), ("forward", "v3")),  # parses as 3.0, loader asks for "v3.0"
    (["v3", "v3.0"], ("ok", "v3.0"), ("forward", "v3")),
    (["v2.0rc0", "v2.1"], ("backward", "v2.1"), ("ok", "v2.1")),
]



# ---- verdicts
def rec(version="v2.1", ep="jsonl", tk="jsonl", st="episodes_stats.jsonl", l1=True, l3=True, **info):
    checks = [
        {"id": "L1", "passed": l1, "data": {}},
        {"id": "L2", "passed": True, "data": {"codebase_version": version}},
        {"id": "L3", "passed": l3, "data": {}},
        {"id": "L5", "passed": ep is not None, "data": {"layout": ep}},
        {"id": "L6", "passed": tk is not None, "data": {"layout": tk}},
        {"id": "L7", "passed": st is not None, "data": {"layout": st}},
    ]
    return {"checks": checks}, {"total_episodes": 5, "total_tasks": 1, **info}


def v3rec(**kw):
    return rec(version="v3.0", ep="parquet", tk="parquet", st="stats.json", **kw)


def verdicts(record, refs):
    r, info = record
    refs_rec = None if refs is None else {"id": "x/y", "tags": [[n, "sha"] for n in refs], "branches": [["main", "sha"]]}
    f = M.facts(r, info, refs_rec)
    return M.lerobot_verdict(f), M.openpi_verdict(f)


class SelectRevision(unittest.TestCase):
    def test_table(self):
        for refs, lerobot, openpi in SELECTION:
            with self.subTest(refs=refs):
                self.assertEqual(M.select_revision(hub(*refs), V3), lerobot)
                self.assertEqual(M.select_revision(hub(*refs), V2), openpi)


class Verdicts(unittest.TestCase):
    def test_v3_data_with_v3_tag_passes_lerobot_and_needs_convert_for_openpi(self):
        lr, op = verdicts(v3rec(), ["v3.0"])
        self.assertEqual(lr["verdict"], "PASS")
        self.assertEqual((op["verdict"], op["steps"]), ("NEEDS_CONVERT", ["CONVERT"]))

    def test_v3_data_without_tag_needs_tag_for_lerobot(self):
        lr, op = verdicts(v3rec(), [])
        self.assertEqual((lr["verdict"], lr["steps"]), ("NEEDS_TAG", ["TAG"]))
        self.assertEqual((op["verdict"], op["steps"]), ("NEEDS_CONVERT", ["CONVERT", "TAG"]))

    def test_v2_data_with_v21_tag_needs_convert_for_lerobot_and_config_for_openpi(self):
        lr, op = verdicts(rec(), ["v2.1"])
        self.assertEqual((lr["verdict"], lr["steps"]), ("NEEDS_CONVERT", ["CONVERT"]))
        self.assertEqual((op["verdict"], op["steps"]), ("NEEDS_CONFIG", ["CONFIG", "NORM_STATS"]))

    def test_v2_data_without_tag(self):
        lr, op = verdicts(rec(), [])
        self.assertEqual((lr["verdict"], lr["steps"]), ("NEEDS_CONVERT", ["CONVERT", "TAG"]))
        self.assertEqual((op["verdict"], op["steps"]), ("NEEDS_TAG", ["TAG", "CONFIG", "NORM_STATS"]))

    def test_v20_data_needs_the_extra_converter_step_for_lerobot_and_stats_json_for_openpi(self):
        ok = rec(version="v2.0", st="stats.json")
        lr, op = verdicts(ok, ["v2.0"])
        self.assertEqual(lr["steps"], ["CONVERT_V20_V21", "CONVERT"])
        self.assertEqual(op["verdict"], "NEEDS_CONFIG")
        # v2.0 wants stats.json, so episodes_stats.jsonl alone is not enough
        _, op = verdicts(rec(version="v2.0"), ["v2.0"])
        self.assertEqual((op["verdict"], op["reason"]), ("BLOCKED", "missing meta/stats.json"))

    def test_dual_tag_repo_is_loadable_by_both_but_openpi_files_are_unverified(self):
        lr, op = verdicts(v3rec(), ["v2.1", "v3.0"])
        self.assertEqual(lr["verdict"], "PASS")
        self.assertEqual(op["verdict"], "NEEDS_CONFIG")
        self.assertTrue(op["files_at_ref_unverified"])

    def test_v2_data_missing_required_v2_meta_is_blocked_for_openpi(self):
        _, op = verdicts(rec(tk=None), ["v2.1"])
        self.assertEqual((op["verdict"], op["reason"]), ("BLOCKED", "missing meta/tasks.jsonl"))

    def test_v3_tasks_parquet_is_only_required_when_there_are_tasks(self):
        lr, _ = verdicts(rec(version="v3.0", ep="parquet", tk=None, total_tasks=0), ["v3.0"])
        self.assertEqual(lr["verdict"], "PASS")
        lr, _ = verdicts(rec(version="v3.0", ep="parquet", tk=None, total_tasks=2), ["v3.0"])
        self.assertEqual((lr["verdict"], lr["reason"]), ("BLOCKED", "missing meta/tasks.parquet"))

    def test_v22_is_blocked_for_both(self):
        lr, op = verdicts(rec(version="v2.2"), ["v2.2"])
        self.assertEqual(lr["verdict"], "BLOCKED")
        self.assertIn("NotImplementedError", lr["reason"])
        self.assertEqual(op["verdict"], "BLOCKED")

    def test_tag_v3_without_v30_ref_needs_tag(self):
        lr, _ = verdicts(v3rec(), ["v3"])
        self.assertEqual(lr["verdict"], "NEEDS_TAG")
        self.assertIn("does not exist", lr["reason"])

    def test_tag_and_info_disagreeing_is_flagged(self):
        lr, _ = verdicts(rec(version="v2.0", st="stats.json"), ["v2.1"])
        self.assertFalse(lr["tag_info_mismatch"])  # same major
        lr, _ = verdicts(v3rec(), ["v2.1"])
        self.assertTrue(lr["tag_info_mismatch"])

    def test_blocked_and_unassessed_paths(self):
        for lr_or_op in verdicts(rec(l1=False), ["v2.1"]):
            self.assertEqual(lr_or_op["verdict"], "BLOCKED")
        for lr_or_op in verdicts(rec(l3=False), ["v2.1"]):
            self.assertEqual(lr_or_op["verdict"], "BLOCKED")
        for lr_or_op in verdicts(rec(), None):
            self.assertEqual(lr_or_op["verdict"], "UNASSESSED")

    def test_openpi_always_lists_timestamp_sync_as_unverified(self):
        _, op = verdicts(rec(), ["v2.1"])
        self.assertEqual(op["unverified"], ["timestamp_sync"])
        self.assertNotIn("unverified", verdicts(rec(), ["v2.1"])[0])


# ---- π0.5 fit (contract §7)
def so100(**over):
    """A typical single-arm dataset: 6-dim action/state, two 480x640 cameras, 30 fps, one task."""
    cam = {"dtype": "video", "shape": [480, 640, 3], "names": ["height", "width", "channels"]}
    info = {"fps": 30, "total_episodes": 50, "total_frames": 15000, "total_tasks": 1, "features": {
        "action": {"dtype": "float32", "shape": [6]}, "observation.state": {"dtype": "float32", "shape": [6]},
        "observation.images.top": dict(cam), "observation.images.wrist": dict(cam),
        "task_index": {"dtype": "int64", "shape": [1]}}}
    for k, v in over.items():
        if k == "features":
            info["features"].update(v)
        else:
            info[k] = v
    return info


def status(info):
    return {c["id"]: c["status"] for c in M.pi05_fit(info)["checks"]}


class Pi05Fit(unittest.TestCase):
    def test_typical_dataset_fits(self):
        r = M.pi05_fit(so100())
        self.assertEqual(r["verdict"], "FIT")
        self.assertEqual(r["issues"], [])
        self.assertEqual(status(so100())["P5"], "OK")  # 4:3 is under the 1.5 aspect threshold

    def test_wide_action_or_state_does_not_fit(self):
        self.assertEqual(M.pi05_fit(so100(features={"action": {"dtype": "float32", "shape": [33]}}))["verdict"], "NO_FIT")
        self.assertEqual(status(so100(features={"action": {"dtype": "float32", "shape": [32]}}))["P2"], "OK")
        self.assertEqual(status(so100(features={"observation.state": {"dtype": "float32", "shape": [40]}}))["P3"], "FAIL")

    def test_split_vectors_need_concatenating(self):
        info = so100()
        del info["features"]["action"], info["features"]["observation.state"]
        info["features"].update({"action.arm": {"dtype": "float32", "shape": [6]}, "action.gripper": {"dtype": "float32", "shape": [1]},
                                 "observation.state.arm": {"dtype": "float32", "shape": [6]}})
        r = M.pi05_fit(info)
        self.assertEqual((status(info)["P1"], status(info)["P3"], r["verdict"]), ("ADAPT", "ADAPT", "ADAPT"))
        self.assertEqual(r["checks"][1]["data"]["dim"], 7)

    def test_cameras(self):
        cam = {"dtype": "video", "shape": [3, 224, 224], "names": ["channels", "height", "width"]}
        four = so100(features={"observation.images.a": cam, "observation.images.b": cam})
        self.assertEqual(status(four)["P4"], "ADAPT")
        depth = {"dtype": "video", "shape": [480, 640, 3], "names": ["height", "width", "depth"]}
        info = so100()
        info["features"] = {k: v for k, v in info["features"].items() if "images" not in k}
        self.assertEqual(status(info)["P4"], "FAIL")  # no camera at all
        info["features"]["observation.images.depth"] = depth
        self.assertEqual(status(info)["P4"], "FAIL")  # only a depth stream
        small_wide = so100(features={"observation.images.top": {"dtype": "video", "shape": [120, 320, 3]}})
        self.assertEqual(status(small_wide)["P5"], "NOTE")

    def test_fps_episode_length_and_prompt(self):
        self.assertEqual(status(so100(fps=10))["P6"], "ADAPT")
        self.assertEqual(status(so100(fps=20))["P6"], "OK")
        self.assertEqual(status(so100(fps=None))["P6"], "FAIL")
        self.assertEqual(status(so100(total_frames=40 * 50))["P7"], "NOTE")
        self.assertEqual(status(so100(total_tasks=0))["P8"], "ADAPT")

    def test_state_named_state(self):  # physical-intelligence/libero names it `state`
        info = so100()
        info["features"]["state"] = info["features"].pop("observation.state")
        self.assertEqual(status(info)["P3"], "OK")

    def test_no_info(self):
        self.assertEqual(M.pi05_fit(None)["verdict"], "UNASSESSED")


if __name__ == "__main__":
    unittest.main()
