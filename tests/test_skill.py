"""The robot-data-smog-check skill: CLI verdicts, metadata-only reads, modality.json drafts, manifests.

    python3 -m unittest tests.test_skill -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from conformance.draft import draft_modality, format_modality
from conformance.explain import CHECKS, VERDICTS
from tests.fixtures import edit_json, variant

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "skills" / "robot-data-smog-check" / "scripts" / "smog_check.py"
FX = ROOT / "fixtures"
NODE = shutil.which("node")


def _replace_bytes(path: Path, data: bytes) -> None:
    """Variants hard-link the fixtures, so never write in place: write a new file and rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def run(*args, cli=CLI, cwd=None):
    p = subprocess.run([sys.executable, str(cli), *map(str, args)], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def run_json(*args, cli=CLI):
    code, out, err = run(*args, "--json", cli=cli)
    return code, json.loads(out)


class Check(unittest.TestCase):
    def test_fixture_verdicts_and_exit_codes(self):
        for name, verdict, code in (("cube_to_bowl_5", "READY", 0), ("tictac-bot", "NEEDS_MODALITY", 1),
                                    ("so101_pick_red_cube_3cams", "NEEDS_DOWNCONVERT", 1)):
            with self.subTest(name):
                c, r = run_json("check", FX / name, "--model", "groot", "--strict")
                self.assertEqual((r["verdict"], c), (verdict, code))
                self.assertNotIn("pi05", r)

    def test_bare_path_means_check(self):
        self.assertEqual(run_json(FX / "cube_to_bowl_5")[1]["verdict"], "READY")

    def test_reads_metadata_only(self):
        for name in ("cube_to_bowl_5", "tictac-bot", "so101_pick_red_cube_3cams"):
            _, r = run_json("check", FX / name)
            self.assertTrue(r["metadata_files_read"], name)
            for rel in r["metadata_files_read"]:
                self.assertTrue(rel.startswith("meta/") and rel.endswith((".json", ".jsonl")), rel)

    def test_human_output_names_the_steps(self):
        _, out, _ = run("check", FX / "so101_pick_red_cube_3cams", "--plain")
        self.assertIn("TWO STEPS AWAY", out)
        self.assertIn("convert_v3_to_v2.py", out)
        self.assertIn("modality.json", out)
        self.assertIn("No episode data or video was opened", out)

    def test_not_lerobot_and_bad_target(self):
        with tempfile.TemporaryDirectory() as t:
            c, r = run_json("check", t, "--strict")
            self.assertEqual((r["verdict"], c), ("NOT_LEROBOT", 1))
            self.assertEqual(run_json("check", t)[0], 0)  # without --strict, a finished check is a success
        c, _, err = run("check", "/no/such/dir/at/all")
        self.assertEqual(c, 2)
        self.assertIn("not a directory", err)

    def test_copy_covers_every_check_and_verdict(self):
        _, r = run_json("check", FX / "cube_to_bowl_5")
        self.assertEqual({c["id"] for c in r["checks"]}, set(CHECKS))
        self.assertTrue({"READY", "NEEDS_MODALITY", "NEEDS_DOWNCONVERT", "INCONSISTENT_MODALITY",
                         "NEEDS_REPAIR", "BLOCKED", "NOT_LEROBOT"} <= set(VERDICTS))


class Draft(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_draft_written_beside_data_not_into_meta(self):
        d = variant(FX / "tictac-bot", self.tmp / "tt", lambda d: None)
        _, r = run_json("check", d, "--draft")
        dm = r["draft_modality"]
        self.assertTrue(dm["ok"], dm)
        self.assertEqual(Path(dm["path"]), d / "modality.draft.json")
        self.assertFalse((d / "meta" / "modality.json").exists())

    def test_confirmed_draft_makes_tictac_ready(self):
        d = variant(FX / "tictac-bot", self.tmp / "tt2", lambda d: None)
        run("check", d, "--draft")
        shutil.copy(d / "modality.draft.json", d / "meta" / "modality.json")
        _, r = run_json("check", d)
        self.assertEqual(r["verdict"], "READY")

    def test_reproduces_nvidia_demo_split(self):
        """On NVIDIA's own demo, the draft's state/action groups equal the hand-written file."""
        info = json.loads((FX / "cube_to_bowl_5" / "meta" / "info.json").read_text())
        real = json.loads((FX / "cube_to_bowl_5" / "meta" / "modality.json").read_text())
        r = draft_modality(info)
        self.assertTrue(r["ok"], r)
        for sec in ("state", "action"):
            self.assertEqual({k: (v["start"], v["end"]) for k, v in r["draft"][sec].items()},
                             {k: (v["start"], v["end"]) for k, v in real[sec].items()}, sec)

    def test_opaque_names_refuse_to_guess(self):
        info = {"features": {"observation.state": {"dtype": "float32", "shape": [3], "names": ["motor_0", "motor_1", "motor_2"]},
                             "action": {"dtype": "float32", "shape": [3], "names": ["motor_0", "motor_1", "motor_2"]}}}
        r = draft_modality(info)
        self.assertFalse(r["ok"])
        self.assertIn("generic", r["reason"])


@unittest.skipUnless(NODE, "node not installed")
class DraftJsParity(unittest.TestCase):
    """conformance/draft.py drafts exactly what docs/app/draft.js drafts, on every audited info.json."""

    def test_every_audited_info_json(self):
        cache = ROOT / "results" / "info_cache"
        if not cache.is_dir():
            self.skipTest("audit results not present")
        out = subprocess.run([NODE, str(ROOT / "tests" / "js_draft.mjs"), str(cache)], capture_output=True, text=True, check=True)
        js_res = json.loads(out.stdout)
        diff, n = [], 0
        for p in sorted(cache.rglob("*.json")):
            rid = p.relative_to(cache).as_posix()[:-5]
            py = draft_modality(json.loads(p.read_text()))
            py["text"] = format_modality(py["draft"]) if py["ok"] else None
            n += 1
            if json.loads(json.dumps(py)) != js_res.get(rid):
                diff.append(rid)
        self.assertGreater(n, 500)
        self.assertEqual(diff[:5], [], f"{len(diff)} of {n} differ")


class Manifest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.d = variant(FX / "cube_to_bowl_5", self.tmp / "cube", lambda d: None)
        code, self.r = run_json("check", self.d, "--manifest", "--model", "groot")
        self.assertEqual(code, 0)
        self.m = json.loads((self.d / "conformance.json").read_text())

    def tearDown(self):
        self._t.cleanup()

    def test_contents(self):
        m = self.m
        self.assertEqual(m["schema"], "robot-data-conformance/v0")
        self.assertEqual(m["result"]["verdict"], "READY")
        self.assertEqual(len(m["result"]["passed"]), 28)
        self.assertEqual(m["dataset"]["total_episodes"], 5)
        self.assertEqual(m["dataset"]["embodiment"], "arm")
        self.assertEqual(set(m["fingerprint"]["metadata_files"]),
                         {"meta/info.json", "meta/episodes.jsonl", "meta/tasks.jsonl", "meta/modality.json", "meta/stats.json"})

    def test_verify_untouched_copy(self):
        c, out, _ = run("verify", self.d)
        self.assertEqual(c, 0, out)
        self.assertIn("VERIFIED", out)

    def test_verify_survives_hidden_files_and_draft(self):
        (self.d / ".DS_Store").write_bytes(b"x")
        (self.d / "modality.draft.json").write_text("{}")
        self.assertEqual(run("verify", self.d)[0], 0)

    def test_verify_catches_changes(self):
        cases = {
            "metadata edited": lambda d: edit_json(d / "meta" / "info.json", lambda j: j.update(fps=15)),
            "episode file removed": lambda d: (d / "data" / "chunk-000" / "episode_000002.parquet").unlink(),
            "episode file resized": lambda d: _replace_bytes(d / "data" / "chunk-000" / "episode_000001.parquet", b"0" * 7),
            "modality removed": lambda d: (d / "meta" / "modality.json").unlink(),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                d = variant(self.d, self.tmp / name.replace(" ", "_"), mutate)
                c, r = run_json("verify", d, "--strict")
                self.assertEqual(c, 1)
                self.assertEqual(run_json("verify", d)[0], 0)
                self.assertFalse(r["verified"])
                self.assertTrue(r["differences"])

    def test_verify_without_manifest(self):
        d = variant(FX / "tictac-bot", self.tmp / "nomanifest", lambda d: None)
        c, _, err = run("verify", d)
        self.assertEqual(c, 2)
        self.assertIn("no manifest", err)


class Pi05(unittest.TestCase):
    """openpi loading (local: CONTRACT_lerobot_openpi.md 2-3) and pi0.5 fit (contract 7), plus the plan."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_fixture_verdicts(self):
        for name, load, fit, steps in (("tictac-bot", "NEEDS_CONFIG", "FIT", ["CONFIG", "NORM_STATS"]),
                                       ("so101_pick_red_cube_3cams", "NEEDS_CONVERT", "FIT", ["CONVERT"]),
                                       ("cube_to_bowl_5", "BLOCKED", "FIT", ["STATS"])):
            with self.subTest(name):
                c, r = run_json("check", FX / name, "--model", "pi05", "--strict")
                self.assertEqual((r["pi05"]["load"]["verdict"], r["pi05"]["fit"]["verdict"], r["pi05"]["load"]["steps"]),
                                 (load, fit, steps))
                self.assertEqual(c, 0 if (load, fit) == ("NEEDS_CONFIG", "FIT") else 1)

    def test_cube_is_missing_episode_stats(self):
        """NVIDIA's own GR00T demo is v2.1 without meta/episodes_stats.jsonl, which openpi's LeRobot reads."""
        _, r = run_json("check", FX / "cube_to_bowl_5", "--model", "pi05")
        self.assertEqual(r["pi05"]["load"]["missing"], ["meta/episodes_stats.jsonl"])

    def test_plan_for_tictac(self):
        d = variant(FX / "tictac-bot", self.tmp / "tt", lambda d: None)
        _, r = run_json("check", d, "--draft")
        plan = (d / "pi05_config_plan.md").read_text()
        self.assertEqual(Path(r["pi05"]["plan_path"]), d / "pi05_config_plan.md")
        for needle in ('"observation/image": "observation.images.webcam"', '"observation/state": "observation.state"',
                       '"actions": "action"', 'action_sequence_keys=("action",)', "prompt_from_task=True",
                       "Pi0Config(pi05=True, action_horizon=50)", "make_bool_mask(5, -1)",
                       "compute_norm_stats.py --config-name=pi05_tt", "No wrist camera"):
            self.assertIn(needle, plan)
        self.assertTrue((d / "modality.draft.json").is_file())
        self.assertFalse((d / "meta" / "modality.json").exists())

    def test_low_fps_shortens_horizon(self):
        d = variant(FX / "tictac-bot", self.tmp / "slow", lambda d: edit_json(d / "meta" / "info.json", lambda j: j.update(fps=10)))
        _, r = run_json("check", d, "--model", "pi05", "--draft")
        self.assertEqual(r["pi05"]["fit"]["verdict"], "ADAPT")
        self.assertIn("action_horizon=10", (d / "pi05_config_plan.md").read_text())

    def test_low_fps_horizon_never_below_10(self):
        d = variant(FX / "tictac-bot", self.tmp / "slower", lambda d: edit_json(d / "meta" / "info.json", lambda j: j.update(fps=8)))
        run_json("check", d, "--model", "pi05", "--draft")
        self.assertIn("action_horizon=10", (d / "pi05_config_plan.md").read_text())

    def test_stats_json_next_to_episodes_stats_still_loads_for_pi05(self):
        def add_stats(d):
            (d / "meta" / "stats.json").write_text("{}")
        d = variant(FX / "tictac-bot", self.tmp / "both_stats", add_stats)
        _, r = run_json("check", d, "--model", "pi05")
        self.assertEqual(r["pi05"]["load"]["verdict"], "NEEDS_CONFIG")

    def test_summary_is_the_default(self):
        _, out, _ = run("check", FX / "so101_pick_red_cube_3cams")
        self.assertTrue(out.startswith("# Dataset diagnostic report: so101_pick_red_cube_3cams"))
        for needle in ("### GR00T N1.7 · ❌ Two steps away", "- ✅ Dataset basics",
                       "- ❌ File layout GR00T reads — LeRobot v3.0 layout; GR00T reads v2",
                       "- ❌ GR00T's extra file: modality.json — `meta/modality.json` missing",
                       "**Next:** Convert from the LeRobot v3.0 layout to v2 (+1 more)",
                       "### π0.5 (openpi) · ❌ Needs converting", "- ❌ Loads in openpi — needs converting", "- ✅ Cameras",
                       "No episode data or video opened; nothing uploaded", "`--details`",
                       "| **Robot** | ✅ Single robot arm (`robot_type: so101_follower`): a fit for these models |",
                       "_17 of 28 loader checks pass_"):
            self.assertIn(needle, out)
        self.assertNotIn("What's needed", out)
        self.assertNotIn("<", out.replace("<user>/<dataset>", ""))  # no HTML: not every Markdown view renders it

    def test_details_report(self):
        _, out, _ = run("check", FX / "so101_pick_red_cube_3cams", "--details")
        self.assertTrue(out.startswith("# Dataset diagnostic report: so101_pick_red_cube_3cams"))
        for needle in ("## Summary", "| **GR00T N1.7** | ❌ Two steps away |", "| **π0.5** (openpi) | ❌ Needs converting |",
                       "## GR00T N1.7 · ❌ Two steps away", "**17 of 28 loader checks pass**", "| Dataset basics | 7/7 | ✅ |",
                       "**What's needed**", "`cd Isaac-GR00T/scripts/lerobot_conversion", "## π0.5 (openpi) · ❌ Needs converting",
                       "| Can openpi load the files? | ❌ **Needs converting**", "**8 of 8 model-fit checks pass**",
                       "No episode data or video opened; nothing uploaded", "_Static checks on metadata only."):
            self.assertIn(needle, out)
        self.assertNotIn("```", out)  # commands are inline code, so the report pastes cleanly

    def test_markdown_report_single_model_and_ready_to_configure(self):
        _, out, _ = run("check", FX / "tictac-bot", "--model", "pi05", "--details")
        self.assertIn("| **π0.5** (openpi) | ✅ Ready to configure |", out)
        self.assertNotIn("GR00T N1.7", out)
        _, out, _ = run("check", FX / "tictac-bot", "--model", "groot", "--details")
        self.assertIn("| **GR00T N1.7** | 🟡 One step away | Add `meta/modality.json` |", out)
        self.assertNotIn("π0.5 (openpi) ·", out)

    def test_human_output_has_both_models(self):
        _, out, _ = run("check", FX / "tictac-bot", "--plain")
        self.assertIn("GR00T: ONE STEP AWAY", out)
        self.assertIn("pi0.5 (openpi): LOADS, NEEDS A CONFIG", out)
        self.assertIn("no Hub version tag is needed", out)

    def test_manifest_records_and_verifies_pi05(self):
        d = variant(FX / "tictac-bot", self.tmp / "man", lambda d: None)
        run("check", d, "--manifest", "--draft")
        m = json.loads((d / "conformance.json").read_text())
        self.assertEqual(m["models"]["pi05"], {"load": "NEEDS_CONFIG", "fit": "FIT"})
        self.assertEqual(run("verify", d)[0], 0)
        edit_json(d / "meta" / "info.json", lambda j: j.update(fps=10))
        c, r = run_json("verify", d, "--strict")
        self.assertEqual(c, 1)
        self.assertTrue(any(x.startswith("pi05:") for x in r["differences"]), r["differences"])

    def test_local_matches_audit_when_tag_is_ideal(self):
        """Local loading = Hub loading with a v2.1 tag, on every audited v2.0/v2.1 dataset."""
        from conformance import models as Mo
        from conformance import pi05 as P
        raw, cache = ROOT / "results" / "raw", ROOT / "results" / "info_cache"
        if not raw.is_dir() or not cache.is_dir():
            self.skipTest("audit results not present")
        n, diff = 0, []
        for p in sorted(raw.rglob("*.json")):
            rec = json.loads(p.read_text())
            ip = cache / f"{rec['dataset']}.json"
            info = json.loads(ip.read_text()) if ip.is_file() else None
            f = Mo.facts(rec, info, None)
            if f["layout"] != "v2" or f["version"] is None or f["version"].major != 2 or f["version"].minor > 1:
                continue
            n += 1
            local = P.local_load_verdict(rec, info)["verdict"]
            hub = Mo.openpi_verdict(Mo.facts(rec, info, {"branches": [], "tags": [["v2.1", ""]]}))["verdict"]
            if local != hub:
                diff.append((rec["dataset"], local, hub))
        self.assertGreater(n, 100)
        self.assertEqual(diff[:5], [], f"{len(diff)} of {n} differ")


class Bundle(unittest.TestCase):
    """The packaged skill runs from its own folder with nothing else on the path."""

    def test_built_skill_runs_standalone(self):
        with tempfile.TemporaryDirectory() as t:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "build_skill.py")], check=True, capture_output=True)
            moved = Path(t) / "robot-data-smog-check"
            shutil.copytree(ROOT / "dist" / "robot-data-smog-check", moved)
            cli = moved / "scripts" / "smog_check.py"
            for name, verdict, load in (("cube_to_bowl_5", "READY", "BLOCKED"), ("tictac-bot", "NEEDS_MODALITY", "NEEDS_CONFIG")):
                p = subprocess.run([sys.executable, "-I", str(cli), "check", str(FX / name), "--json"],
                                   capture_output=True, text=True, cwd=t)
                r = json.loads(p.stdout)
                self.assertEqual((r["verdict"], r["pi05"]["load"]["verdict"]), (verdict, load), p.stderr)
            self.assertTrue((moved / "SKILL.md").is_file())
            self.assertTrue((moved / "scripts" / "packaging" / "version.py").is_file())


if __name__ == "__main__":
    unittest.main()
