"""openpi (pi0, pi0-FAST, pi0.5) readiness for one dataset, and a pi0.5 config plan.

Two questions, as in CONTRACT_lerobot_openpi.md:
  load  can openpi's pinned LeRobot (0cf8648) read the files?               (contract 1-3)
  fit   does what is in them fit pi0.5 as openpi ships it (pi05_base)?     (contract 7, models.pi05_fit)

Local datasets: openpi names data by repo_id only (data_loader.py:140-146), and LeRobot reads it from
$HF_LEROBOT_HOME/<repo_id> when the metadata is already there (lerobot_dataset.py:91-102). That path
never asks the Hub for a version tag, so the local load verdict is contract 2-3 without 1.
Hub ids use models.openpi_verdict with the repo's refs.

The plan is a PROPOSAL, like the modality.json draft: openpi keeps the dataset-to-model mapping in
Python, so the plan names the keys, slots and settings and a person writes the config.
"""
from __future__ import annotations

import re
from typing import Optional

from . import models as Mo
from .draft import draft_modality

WRIST = {"wrist", "gripper", "hand", "eef", "ee", "palm"}
BASE_PREF = ("front", "top", "high", "overhead", "base", "main", "scene", "third", "exterior", "table",
             "static", "webcam", "head", "cam")
_TOK = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------- load

def _r(verdict, steps, reason, **extra):
    return {"verdict": verdict, "steps": steps, "reason": reason, **extra}


def local_load_verdict(report: dict, info: Optional[dict]) -> dict:
    """openpi load verdict for a dataset on disk (contract 2-3; 1 does not apply)."""
    f = Mo.facts(report, info, None)
    by = {c["id"]: c for c in report["checks"]}
    note = {"unverified": ["timestamp_sync"]}
    if not f["is_lerobot"]:
        return _r("BLOCKED", [], "not a LeRobot dataset (no readable meta/info.json)", **note)
    if not f["has_data"]:
        return _r("BLOCKED", [], "no recorded episodes (no parquet under data/)", **note)
    if f["layout"] is None:
        return _r("BLOCKED", [], "episode/task metadata layout not recognised", **note)
    if f["layout"] == "v3":
        return _r("NEEDS_CONVERT", ["CONVERT"], "LeRobot v3.0 layout; openpi's pinned LeRobot reads v2.x", **note)
    ver = f["version"]
    if ver is None:
        return _r("BLOCKED", [], "info.json has no parseable codebase_version, which openpi's LeRobot reads", **note)
    if ver.major < 2:
        return _r("BLOCKED", [], f"codebase_version {f['version_str']}: older than v2, no converter", **note)
    if ver.major > 2:
        return _r("BLOCKED", [], f"codebase_version {f['version_str']} but the files are in the v2 layout", **note)
    if miss := Mo._missing_v2(f):
        return _r("BLOCKED", ["STATS"] if miss == ["meta/episodes_stats.jsonl"] else [],
                  f"missing {', '.join(miss)}", missing=miss, **note)
    steps = ["CONFIG", "NORM_STATS"]
    if (by.get("G14") or {}).get("passed") is False:
        steps = ["REPAIR"] + steps
    return _r("NEEDS_CONFIG", steps, "the files load; a data config and norm stats are still to be written", **note)


def hub_load_verdict(report: dict, info: Optional[dict], refs: Optional[dict]) -> dict:
    """openpi load verdict for a Hub repo id (contract 1-3), refs = {branches: [[name, sha]], tags: [...]}."""
    return Mo.openpi_verdict(Mo.facts(report, info, refs))


# ---------------------------------------------------------------- plan

def _toks(key: str) -> set[str]:
    return set(_TOK.findall(re.sub(r"^observation\.images?\.", "", key.lower())))


def _slots(info: dict) -> dict:
    F = info["features"]
    cams = [Mo._camera(k, ft) for k, ft in F.items() if isinstance(ft, dict) and ft.get("dtype") in ("video", "image")]
    rgb = [c["key"] for c in cams if c["rgb"]]
    wrists = [k for k in rgb if _toks(k) & WRIST]
    bases = [k for k in rgb if k not in wrists]

    def pref(k):
        t = _toks(k)
        return min((i for i, w in enumerate(BASE_PREF) if w in t), default=len(BASE_PREF))

    bases.sort(key=pref)
    left = next((k for k in wrists if _toks(k) & {"left", "l"}), None)
    right = next((k for k in wrists if _toks(k) & {"right", "r"} and k != left), None)
    rest = [k for k in wrists if k not in (left, right)]
    if left is None and rest:
        left = rest.pop(0)
    if right is None and rest and left is not None and _toks(left) & {"left", "l"}:
        right = rest.pop(0)
    slots = {"base_0_rgb": bases[0] if bases else None, "left_wrist_0_rgb": left, "right_wrist_0_rgb": right}
    used = {v for v in slots.values() if v}
    return {"slots": slots, "unused": [k for k in rgb if k not in used],
            "not_rgb": [c["key"] for c in cams if not c["rgb"]]}


def _delta_mask(info: dict) -> Optional[str]:
    """make_bool_mask(...) for openpi's DeltaActions: joints relative, grippers absolute (config.py:323-343)."""
    d = draft_modality(info)
    if not d.get("ok"):
        return None
    parts, grip, other = [], False, False
    for g in d["groups"]["action"]:
        n = g["end"] - g["start"]
        if "gripper" in g["name"] or "hand" in g["name"]:
            parts.append(-n)
            grip = True
        else:
            parts.append(n)
            other = True
    return f"make_bool_mask({', '.join(map(str, parts))})" if grip and other else None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "my_dataset"


def plan(info: Optional[dict], name: str, repo_id: Optional[str], fit: dict) -> Optional[dict]:
    """A pi0.5 config plan, or None when there is nothing to plan (no info.json, or the data cannot fit)."""
    if not isinstance(info, dict) or not isinstance(info.get("features"), dict) or fit.get("verdict") == "NO_FIT":
        return None
    F = info["features"]
    by = {c["id"]: c for c in fit["checks"]}
    act = Mo._vector_group(F, ("action", "actions"), ("action.", "actions."))
    st = Mo._vector_group(F, ("observation.state", "state"), ("observation.state.", "observation.states."))
    fps = info.get("fps")
    cams = _slots(info)
    notes = []
    if cams["slots"]["base_0_rgb"] is None:
        notes.append("No third-person camera was found, so base_0_rgb is empty: put a wrist view there or edit the inputs class.")
    if cams["slots"]["left_wrist_0_rgb"] is None:
        notes.append("No wrist camera: openpi's LiberoInputs reads one base and one wrist image, so remove the wrist "
                     "line in your copy of it and pass zeros instead, as it already does for right_wrist_0_rgb.")
    if cams["unused"]:
        notes.append(f"pi0.5 has three image slots; not used: {', '.join(cams['unused'])}.")
    if act["split"]:
        notes.append(f"Actions are split over {', '.join(act['keys'])}: concatenate them into one vector in your inputs transform.")
    if st["split"]:
        notes.append(f"State is split over {', '.join(st['keys'])}: concatenate them in your inputs transform.")
    no_state = (by.get("P3") or {}).get("status") == "ADAPT" and not st["keys"]
    mask = _delta_mask(info)
    tasks = isinstance(info.get("total_tasks"), int) and info["total_tasks"] > 0 and isinstance(F.get("task_index"), dict)
    cfg = _slug(f"pi05_{name}")
    return {
        "config_name": cfg,
        "repo_id": repo_id or f"<your-hf-user>/{name}",
        "slots": cams["slots"], "unused_cameras": cams["unused"], "not_rgb": cams["not_rgb"],
        "state_key": st["keys"][0] if st["keys"] and not st["split"] else None,
        "action_key": act["keys"][0] if act["keys"] and not act["split"] else None,
        "action_dim": act["dim"], "state_dim": st["dim"],
        "prompt_from_task": bool(tasks),
        "action_horizon": Mo.pi05_action_horizon(fps),
        "discrete_state_input": not no_state,
        "delta_mask": mask,
        "fps": fps,
        "notes": notes,
        "fit_issues": [by[i]["detail"] for i in fit.get("issues", [])],
    }


def format_plan(p: dict, name: str, local: bool) -> str:
    s = p["slots"]
    repack = ['    "observation/image": "%s",  # -> base_0_rgb' % (s["base_0_rgb"] or "<a camera key>")]
    if s["left_wrist_0_rgb"]:
        repack.append('    "observation/wrist_image": "%s",  # -> left_wrist_0_rgb' % s["left_wrist_0_rgb"])
    if s["right_wrist_0_rgb"]:
        repack.append('    "observation/right_wrist_image": "%s",  # -> right_wrist_0_rgb (add it to your inputs class)'
                      % s["right_wrist_0_rgb"])
    repack.append('    "observation/state": "%s",' % (p["state_key"] or "<state key>"))
    repack.append('    "actions": "%s",' % (p["action_key"] or "<action key>"))
    repack.append('    "prompt": "prompt",')
    model = f"pi0_config.Pi0Config(pi05=True, action_horizon={p['action_horizon']}"
    model += ")" if p["discrete_state_input"] else ", discrete_state_input=False)"
    base = "DataConfig(" + ("prompt_from_task=True, " if p["prompt_from_task"] else 'default_prompt="<what the robot should do>", ')
    base += f'action_sequence_keys=("{p["action_key"] or "<action key>"}",))'
    where = ("Copy the dataset to LeRobot's cache, `$HF_LEROBOT_HOME/%s` (by default under `~/.cache/huggingface/lerobot/`). "
             "openpi loads by repo_id, and when the files are already there no Hub upload or version tag is needed."
             % p["repo_id"]) if local else f"openpi will download `{p['repo_id']}` from the Hub."
    out = [f"# pi0.5 (openpi) config plan: {name}", "",
           "A proposal drafted from meta/info.json. Check every key against your data before training.", "",
           "## 1. Where the data goes", "", where, "",
           "## 2. Data config", "",
           "In `src/openpi/training/config.py`, copy `LeRobotLiberoDataConfig` and point its `RepackTransform` at your keys:", "",
           "```python", "_transforms.RepackTransform({", *repack, "})", "```", "",
           "`LiberoInputs` (openpi `policies/libero_policy.py`) then fills the image slots; an empty slot gets a zero image, masked for pi0.5."]
    if p["delta_mask"]:
        out += ["", "pi0 models train on actions relative to the current state. If these are absolute joint targets, as "
                "LeRobot teleop recordings usually are, add the delta transform with this mask "
                f"(joints relative, grippers absolute): `{p['delta_mask']}`."]
    out += ["", "## 3. Train config", "", "```python", "TrainConfig(", f'    name="{p["config_name"]}",', f"    model={model},",
            f'    data=MyDataConfig(repo_id="{p["repo_id"]}", base_config={base}),',
            '    weight_loader=weight_loaders.CheckpointWeightLoader("gs://openpi-assets/checkpoints/pi05_base/params"),',
            ")", "```", ""]
    if p["action_horizon"] != Mo.PI05_ACTION_HORIZON:
        out += [f"`action_horizon={p['action_horizon']}`: at {p['fps']:g} Hz the default 50 steps would span "
                f"{50 / p['fps']:.1f} s; openpi's own low-rate pi0.5 configs use about one second (pi05_libero: 10, pi05_droid: 15).", ""]
    if not p["discrete_state_input"]:
        out += ["`discrete_state_input=False`: there is no state vector, and pi0.5 otherwise writes the state into its prompt.", ""]
    out += ["## 4. Norm stats, then train", "", "```bash", f"uv run scripts/compute_norm_stats.py --config-name={p['config_name']}",
            "```", "", "Training raises without them. openpi also checks every frame's timestamp against fps (within 1e-4 s) "
            "when it loads the data; this metadata check cannot see that."]
    if p["notes"] or p["fit_issues"]:
        out += ["", "## Also check", ""] + [f"- {n}" for n in p["fit_issues"] + p["notes"]]
    return "\n".join(out) + "\n"
