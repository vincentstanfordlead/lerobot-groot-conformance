"""The browser checker (docs/app/checks.js) must agree with conformance/checks.py.

Runs both on every control fixture and corrupted variant from test_controls and compares the
verdict, steps, and each check's (level, passed, blocked_by). Skipped when node is absent.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from conformance.inspect_local import inspect_local
from tests.fixtures import build_cube, edit_json, variant

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
FIXTURES = [ROOT / "fixtures" / n for n in ("cube_to_bowl_5", "tictac-bot", "so101_pick_red_cube_3cams")]


def js(path: Path) -> dict:
    out = subprocess.run([NODE, str(ROOT / "tests" / "js_local.mjs"), str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def key(r: dict):
    return (r["verdict"], r["steps"], sorted(r["unverified_size"]),
            [(c["id"], c["level"], c["passed"], c["blocked_by"]) for c in r["checks"]])


def _replace_text(path: Path, fn) -> None:
    """Variants hard-link the source fixture, so never write in place: write a new file and rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(fn(path.read_text()))
    tmp.replace(path)


MUTATIONS = {
    "no_modality": lambda d: (d / "meta" / "modality.json").unlink(),
    "gripper_end_7": lambda d: edit_json(d / "meta" / "modality.json", lambda j: j["state"]["gripper"].update(end=7)),
    "state_empty": lambda d: edit_json(d / "meta" / "modality.json", lambda j: j.update(state={})),
    "parquet_deleted": lambda d: next(d.glob("data/chunk-000/episode_000002.parquet")).unlink(),
    "no_stats": lambda d: (d / "meta" / "stats.json").unlink(),
    "bad_video_key": lambda d: edit_json(d / "meta" / "modality.json",
                                         lambda j: j["video"]["front"].update(original_key="observation.images.nope")),
    "int_action": lambda d: edit_json(d / "meta" / "info.json", lambda j: j["features"]["action"].update(dtype="int64")),
    "no_dtype": lambda d: edit_json(d / "meta" / "info.json", lambda j: j["features"]["timestamp"].pop("dtype")),
    "count_and_fps": lambda d: edit_json(d / "meta" / "info.json",
                                         lambda j: (j.update(total_episodes=j["total_episodes"] + 1), j.pop("fps"))),
    "v3_paths": lambda d: (edit_json(d / "meta" / "info.json", lambda j: j.update(
        data_path="data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet", codebase_version="v3.0")),
        (d / "meta" / "episodes.jsonl").unlink(), (d / "meta" / "tasks.jsonl").unlink()),
    "no_meta": lambda d: shutil.rmtree(d / "meta"),
    "no_data": lambda d: shutil.rmtree(d / "data"),
    "blank_line_episodes": lambda d: _replace_text(d / "meta" / "episodes.jsonl",
                                                   lambda t: t.replace("\n", "\n\n", 1)),
}


@unittest.skipUnless(NODE, "node not installed")
class JsParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        real = ROOT / "fixtures" / "cube_to_bowl_5"
        cls.cube = build_cube(cls.tmp / "cube", real if real.is_dir() else None)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def same(self, path: Path):
        self.assertEqual(key(js(path)), key(inspect_local(path)), path.name)

    def test_fixtures(self):
        for f in FIXTURES:
            if f.is_dir():
                with self.subTest(f.name):
                    self.same(f)

    def test_mutations(self):
        for name, m in MUTATIONS.items():
            with self.subTest(name):
                self.same(variant(self.cube, self.tmp / name, m))

    def test_mutations_on_public_v21(self):
        src = ROOT / "fixtures" / "tictac-bot"
        for name in ("no_data",):
            with self.subTest(name):
                self.same(variant(src, self.tmp / f"tictac_{name}", MUTATIONS[name]))
        self.same(variant(src, self.tmp / "tictac_corrupt", lambda d: (
            (d / "meta" / "episodes.jsonl").unlink(), edit_json(d / "meta" / "info.json", lambda j: j.pop("chunks_size")))))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(NODE, "node not installed")
class JsDraftParity(unittest.TestCase):
    """docs/app/draft.js tiers every audited info.json exactly as conformance/report.py did."""

    def test_goal6_tiers_match(self):
        cache, csv = ROOT / "results" / "info_cache", ROOT / "results" / "goal6_inferability.csv"
        if not cache.is_dir() or not csv.exists():
            self.skipTest("audit results not present")
        import csv as csvmod
        out = subprocess.run([NODE, str(ROOT / "tests" / "js_goal6.mjs"), str(cache)], capture_output=True, text=True, check=True)
        js_tiers = json.loads(out.stdout)
        rows = list(csvmod.DictReader(csv.open()))
        diff = [(r["dataset"], r["tier"], js_tiers.get(r["dataset"])) for r in rows if js_tiers.get(r["dataset"]) != r["tier"]]
        self.assertEqual(diff, [], f"{len(diff)} of {len(rows)} differ")


@unittest.skipUnless(NODE, "node not installed")
class JsEmbodimentParity(unittest.TestCase):
    """docs/app/embodiment.js classifies every audited info.json exactly as conformance/embodiment.py."""

    def test_embodiment_matches(self):
        from conformance.embodiment import classify
        cache = ROOT / "results" / "info_cache"
        if not cache.is_dir():
            self.skipTest("audit results not present")
        out = subprocess.run([NODE, str(ROOT / "tests" / "js_embodiment.mjs"), str(cache)], capture_output=True, text=True, check=True)
        js_res = json.loads(out.stdout)
        diff = []
        for p in sorted(cache.rglob("*.json")):
            rid = p.relative_to(cache).as_posix()[:-5]
            py = classify(json.loads(p.read_text()), rid)
            if py != js_res.get(rid):
                diff.append((rid, py, js_res.get(rid)))
        self.assertEqual(diff, [], f"{len(diff)} differ")


@unittest.skipUnless(NODE, "node not installed")
class JsModelsParity(unittest.TestCase):
    """docs/app/models.js gives the LeRobot and openpi verdicts and the π0.5 fit conformance/models.py gives, on every
    audited dataset (main snapshot and the verified ref snapshots), and selects the same revision for every ref set."""

    def test_models_match(self):
        from conformance import models as M
        res = ROOT / "results"
        if not (res / "refs_cache").is_dir():
            self.skipTest("refs cache not present")

        def load(p):
            try:
                return json.loads(p.read_text())
            except (OSError, ValueError):
                return None

        cases, py, selections = [], [], []
        for p in sorted((res / "raw").rglob("*.json")):
            rec = json.loads(p.read_text())
            rid = rec["dataset"]
            info, refs = load(res / "info_cache" / f"{rid}.json"), load(res / "refs_cache" / f"{rid}.json")
            names = None if refs is None or "error" in refs else [n for n, _ in refs["branches"] + refs["tags"]]
            variants = [rec] + [r for r in (load(res / "raw_ref" / loader / f"{rid}.json") for loader in ("lerobot", "openpi")) if r]
            for r in variants:
                ref_info = info if r is rec else None
                cases.append({"checks": r["checks"], "info": ref_info, "refNames": names})
                f = M.facts(r, ref_info, refs)
                py.append({"lerobot": M.lerobot_verdict(f), "openpi": M.openpi_verdict(f), "pi05": M.pi05_fit(ref_info)})
            if names is not None:
                selections.append(names)
        selections += [[], ["main"], ["v3"], ["v3", "v3.0"], ["v2.0rc0", "v2.1"], ["v2.2"], ["1.0.0-rc1", "v2.1.post1"]]
        py_sel = []
        for names in selections:
            hub = M.parse_versions(names)
            py_sel.append([list(M.select_revision(hub, M.LEROBOT_TARGET)), list(M.select_revision(hub, M.OPENPI_TARGET))])

        # the pi0.5 config draft's action_horizon: every audited fps plus the edges
        fps_list = sorted({c["info"]["fps"] for c in cases if isinstance((c["info"] or {}).get("fps"), (int, float))}
                          | {1, 7.5, 8, 9.5, 10, 12.5, 14.5, 15, 15.5, 30})
        cases.append({"checks": [{"id": "L5", "data": {"layout": "jsonl"}}, {"id": "L6", "data": {"layout": "jsonl"}},
                                 {"id": "L1", "passed": True}, {"id": "L3", "passed": True},
                                 {"id": "L2", "data": {"codebase_version": "v2.1"}},
                                 {"id": "L7", "data": {"layout": "stats.json", "files": ["stats.json", "episodes_stats.jsonl"]}}],
                      "info": None, "refNames": ["v2.1"]})
        f = M.facts({"checks": cases[-1]["checks"]}, None, {"branches": [], "tags": [["v2.1", "x"]]})
        py.append({"lerobot": M.lerobot_verdict(f), "openpi": M.openpi_verdict(f), "pi05": M.pi05_fit(None)})
        self.assertEqual(py[-1]["openpi"]["verdict"], "NEEDS_CONFIG")
        inp = ROOT / "results" / ".js_models_in.json"
        try:
            inp.write_text(json.dumps({"cases": cases, "selections": selections, "fpsList": fps_list}))
            out = subprocess.run([NODE, str(ROOT / "tests" / "js_models.mjs"), str(inp)], capture_output=True, text=True, check=True)
        finally:
            inp.unlink(missing_ok=True)
        js_res = json.loads(out.stdout)

        diff = [(i, a, b) for i, (a, b) in enumerate(zip(py, js_res["verdicts"])) if a != b]
        self.assertEqual(len(py), len(js_res["verdicts"]))
        self.assertEqual(diff[:3], [], f"{len(diff)} of {len(py)} verdict pairs differ")
        self.assertEqual(js_res["horizons"], [M.pi05_action_horizon(x) for x in fps_list])
        sel_diff = [(n, a, b) for n, a, b in zip(selections, py_sel, js_res["selections"]) if a != b]
        self.assertEqual(sel_diff[:3], [], f"{len(sel_diff)} of {len(selections)} selections differ")
