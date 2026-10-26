"""LeRobot-native and openpi columns (CONTRACT_lerobot_openpi.md).

Pure functions over (a stored audit record, the dataset's Hub refs, its info.json). No network.
Judged for loading by Hub `repo_id` (contract scope note): the loader picks the revision from the
repo's version-named branches/tags, so the refs decide whether a dataset can be pulled at all.

Verdicts (contract §6):
  PASS          LeRobot only: the loader picks a v3.0 ref and the v3 meta files are there.
  NEEDS_CONFIG  openpi only: files load; a data config and norm stats are still to be written.
  NEEDS_TAG     the data is in the right layout but the repo has no version-named ref the loader accepts.
  NEEDS_CONVERT the data is in the other layout (v2 for LeRobot, v3 for openpi).
  BLOCKED       no episodes, not LeRobot, a required meta file missing, or no tool exists for the version.
  UNASSESSED    refs could not be fetched (repo gone or private since the audit); excluded, not counted.
"""
from __future__ import annotations

from typing import Optional

import math

import packaging.version as V

LEROBOT_TARGET = V.Version("3.0")  # vendor/lerobot_ff71cae  dataset_metadata.py:63
OPENPI_TARGET = V.Version("2.1")  # vendor/lerobot_0cf8648  lerobot_dataset.py:77

LEROBOT_SHA = "ff71cae1ae2d09fd035553c35da65888ed6c8304"
OPENPI_SHA = "215abfb217dbac7d5f1273282331b9b1866c0479"
OPENPI_LEROBOT_SHA = "0cf864870cf29f4738d3ade893e6fd13fbd7cdb5"

COLUMNS = ("groot", "lerobot", "openpi")


def parse_versions(ref_names: list[str]) -> dict[V.Version, set[str]]:
    """Version-named refs, as `get_repo_versions` keeps them (anything `packaging` parses).

    Maps each parsed version to the ref names that carry it. A tag `v3` parses to 3.0 but the
    loader will then ask for the literal ref `v3.0`, so the names matter (see `select_revision`).
    """
    out: dict[V.Version, set[str]] = {}
    for name in ref_names:
        try:
            out.setdefault(V.parse(name), set()).add(name)
        except V.InvalidVersion:
            pass
    return out


def select_revision(hub: dict[V.Version, set[str]], target: V.Version) -> tuple[str, Optional[str]]:
    """Port of `get_safe_version` (lerobot utils.py; same logic at both pinned commits).

    Returns (outcome, ref):
      ("none", None)      no version-named ref            -> RuntimeError / RevisionNotFoundError
      ("ok", "v2.1")      loader downloads this ref
      ("ref_missing", ..) loader asks for a literal `v{version}` ref that does not exist
                          (e.g. only `v3` is tagged); the download then fails
      ("backward", "v2.1") only older majors exist        -> BackwardCompatibilityError
      ("forward", "v3.0")  only newer versions exist      -> ForwardCompatibilityError
    """
    if not hub:
        return "none", None

    def ask(v: V.Version) -> tuple[str, str]:
        want = f"v{v}"
        return ("ok", want) if want in hub[v] else ("ref_missing", want)

    if target in hub:
        return ask(target)
    compatibles = [v for v in hub if v.major == target.major and v.minor <= target.minor]
    if compatibles:
        return ask(max(compatibles))
    lower = [v for v in hub if v.major < target.major]
    if lower:
        return "backward", min(hub[max(lower)])
    return "forward", min(hub[min(v for v in hub if v > target)])


# ---------------------------------------------------------------- facts about the dataset

def facts(record: dict, info: Optional[dict], refs: Optional[dict]) -> dict:
    """What the two columns need, from a results/raw record, info.json (info_cache) and refs."""
    by = {c["id"]: c for c in record.get("checks", [])}

    def passed(i):
        return (by.get(i) or {}).get("passed")

    def data(i, k):
        return ((by.get(i) or {}).get("data") or {}).get(k)

    ver_s = data("L2", "codebase_version")
    try:
        ver = V.parse(str(ver_s)) if ver_s is not None else None
    except V.InvalidVersion:
        ver = None
    ep, tk, st = data("L5", "layout"), data("L6", "layout"), data("L7", "layout")
    # v3 layout: same signals as checks.Ctx.is_v3_layout, from the stored layouts
    v3 = (ver is not None and ver.major == 3) or ep == "parquet" or tk == "parquet"
    f = {
        "is_lerobot": passed("L1") is True,
        "has_data": passed("L3") is True,
        "version": ver,
        "version_str": ver_s,
        "layout": "v3" if v3 else ("v2" if (ep == "jsonl" or tk == "jsonl") else None),
        "episodes_layout": ep, "tasks_layout": tk, "stats_layout": st,
        # L7 "files" lists every stats file; older records stored only the preferred one in "layout"
        "stats_files": data("L7", "files") if data("L7", "files") is not None else ([st] if st else []),
        "total_episodes": (info or {}).get("total_episodes", data("L11", "total_episodes")),
        "total_tasks": (info or {}).get("total_tasks"),
        "refs": None,
    }
    if refs is not None and "error" not in refs:
        f["refs"] = parse_versions([n for n, _ in refs.get("branches", []) + refs.get("tags", [])])
    return f


def _missing_v3(f: dict) -> list[str]:
    """v3 meta the loader reads (dataset_metadata.py:217-222): tasks/episodes only when counted."""
    miss = []
    if f["total_tasks"] and f["tasks_layout"] != "parquet":
        miss.append("meta/tasks.parquet")
    if f["total_episodes"] and f["episodes_layout"] != "parquet":
        miss.append("meta/episodes/*.parquet")
    return miss


def _missing_v2(f: dict) -> list[str]:
    """v2 meta the pinned lerobot reads (lerobot_dataset.py:104-115); all LOUD when absent."""
    miss = []
    if f["tasks_layout"] != "jsonl":
        miss.append("meta/tasks.jsonl")
    if f["episodes_layout"] != "jsonl":
        miss.append("meta/episodes.jsonl")
    old = f["version"] is not None and f["version"] < V.Version("2.1")
    want = "stats.json" if old else "episodes_stats.jsonl"
    if want not in f["stats_files"]:
        miss.append(f"meta/{want}")
    return miss


def _result(verdict, steps, reason, **extra):
    return {"verdict": verdict, "steps": steps, "reason": reason, **extra}


def _common_block(f: dict):
    if not f["is_lerobot"]:
        return _result("BLOCKED", [], "not a LeRobot dataset (no readable info.json)")
    if not f["has_data"]:
        return _result("BLOCKED", [], "no parquet under data/ (metadata-only upload)")
    if f["refs"] is None:
        return _result("UNASSESSED", [], "Hub refs unavailable (repo gone or private since the audit)")
    return None


def _tag_note(f: dict, hub: dict) -> dict:
    """info.json major not among the version refs: tag and files disagree (contract §2)."""
    ver = f["version"]
    majors = {v.major for v in hub}
    return {"tag_info_mismatch": bool(hub and ver is not None and ver.major not in majors)}


# ---------------------------------------------------------------- the two verdicts

def lerobot_verdict(f: dict) -> dict:
    """LeRobot ff71cae: reads v3.0 only (contract §1, §3, §6)."""
    if (b := _common_block(f)) is not None:
        return b
    hub = f["refs"]
    outcome, ref = select_revision(hub, LEROBOT_TARGET)
    note = _tag_note(f, hub)
    layout = f["layout"]
    if layout is None:
        return _result("BLOCKED", [], "episode/task metadata layout not recognised", **note)
    if layout == "v3":
        if miss := _missing_v3(f):
            return _result("BLOCKED", [], f"missing {', '.join(miss)}", **note)
        if outcome == "ok":
            return _result("PASS", [], f"loader picks {ref}", ref=ref, **note)
        if outcome == "none":
            return _result("NEEDS_TAG", ["TAG"], "no version-named ref (RuntimeError)", **note)
        if outcome == "ref_missing":
            return _result("NEEDS_TAG", ["TAG"], f"loader asks for {ref}, which does not exist", **note)
        # only older refs exist although the files are v3: the tag is stale
        return _result("NEEDS_TAG", ["TAG"], f"latest ref is {ref}; v3 files need a v3.0 ref", **note)
    # v2 layout: BackwardCompatibilityError, or no ref at all
    ver = f["version"]
    if ver is not None and ver.major == 2 and ver.minor > 1:
        return _result("BLOCKED", [], f"codebase_version {ver}: loader raises NotImplementedError, "
                       "no converter named", **note)
    if ver is not None and ver.major < 2:
        return _result("BLOCKED", [], f"codebase_version {ver}: no converter", **note)
    steps = (["CONVERT_V20_V21"] if ver is not None and ver == V.Version("2.0") else []) + ["CONVERT"]
    if outcome == "none":
        steps.append("TAG")
    return _result("NEEDS_CONVERT", steps, f"v2 data; loader target is v3.0 (outcome: {outcome})", **note)


def openpi_verdict(f: dict) -> dict:
    """openpi 215abfb via lerobot 0cf8648: reads v2.x only, always needs a data config (§5)."""
    if (b := _common_block(f)) is not None:
        return b
    hub = f["refs"]
    outcome, ref = select_revision(hub, OPENPI_TARGET)
    note = {**_tag_note(f, hub), "unverified": ["timestamp_sync"]}  # needs parquet (contract §4)
    layout = f["layout"]
    if layout is None:
        return _result("BLOCKED", [], "episode/task metadata layout not recognised", **note)
    if layout == "v3":
        # The v3 files are what main holds. A v2.x ref on another commit (the dual-tag repos)
        # is what openpi would pull; its files are not inspected (NOTES, pending call 4).
        if outcome == "ok":
            return _result("NEEDS_CONFIG", ["CONFIG", "NORM_STATS"], f"loader picks older ref {ref}; "
                           "files at that ref not inspected", ref=ref, files_at_ref_unverified=True, **note)
        return _result("NEEDS_CONVERT", ["CONVERT", "TAG"] if outcome == "none" else ["CONVERT"],
                       f"v3 data; loader target is v2.1 (outcome: {outcome})", **note)
    ver = f["version"]
    if ver is not None and (ver.major != 2):
        return _result("BLOCKED", [], f"codebase_version {ver}: no converter", **note)
    if ver is not None and ver.minor > 1:
        return _result("BLOCKED", [], f"codebase_version {ver}: ForwardCompatibilityError "
                       "unless re-tagged v2.1", **note)
    if miss := _missing_v2(f):
        return _result("BLOCKED", [], f"missing {', '.join(miss)}", **note)
    if outcome == "ok":
        return _result("NEEDS_CONFIG", ["CONFIG", "NORM_STATS"], f"loader picks {ref}", ref=ref, **note)
    if outcome == "none":
        return _result("NEEDS_TAG", ["TAG", "CONFIG", "NORM_STATS"], "no version-named ref", **note)
    if outcome == "ref_missing":
        return _result("NEEDS_TAG", ["TAG", "CONFIG", "NORM_STATS"],
                       f"loader asks for {ref}, which does not exist", **note)
    return _result("BLOCKED", [], f"only {outcome} refs ({ref}) for v2 files: re-tag as v2.1", **note)


# ---------------------------------------------------------------- π0.5 model fit (contract §7)
#
# The openpi column above asks whether the files load. This asks whether what is in them fits the π0.5
# model as openpi ships it (pi0_config.Pi0Config(pi05=True), the base checkpoint `pi05_base`), from
# info.json alone. Independent of the loading verdict: a v3 dataset that needs converting can still fit.

PI05_ACTION_DIM = 32  # vendor/openpi_215abfb  src_openpi_models_pi0_config.py:25 (state shares it, :80)
PI05_ACTION_HORIZON = 50  # src_openpi_models_pi0_config.py:26
PI05_IMAGE_SLOTS = ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")  # src_openpi_models_model.py:39-43
PI05_IMAGE_RESOLUTION = (224, 224)  # src_openpi_models_model.py:47
PI05_LOW_FPS = 15  # openpi's own π0.5 configs at <=15 Hz shorten the horizon: pi05_libero 10, pi05_droid 15

# Status of one check, best first. FAIL: π0.5 as shipped cannot train on it; ADAPT: the data config
# (or one model setting) has to do more than rename keys; NOTE: works, worth knowing.
PI05_STATUS = ("OK", "NOTE", "ADAPT", "FAIL")
PI05_VERDICTS = ("FIT", "ADAPT", "NO_FIT")


def pi05_action_horizon(fps) -> int:
    """At <= PI05_LOW_FPS, about one second of actions but no fewer than pi05_libero's 10; else the default."""
    if isinstance(fps, (int, float)) and not isinstance(fps, bool) and 0 < fps <= PI05_LOW_FPS:
        return max(10, int(_half_up(fps, 0)))
    return PI05_ACTION_HORIZON


def _half_up(x: float, n: int) -> float:
    """Round half away from zero (x >= 0), so the JS port rounds the same; Python's round() is half-even."""
    return math.floor(x * 10 ** n + 0.5) / 10 ** n


def _is_float(ft: dict) -> bool:
    return str(ft.get("dtype", "")).startswith("float")


def _vec_dim(ft: dict) -> Optional[int]:
    """Length of a 1-D vector feature (shape [n] or [1, n]); None if it is not one."""
    s = ft.get("shape")
    if not isinstance(s, list) or not s or not all(isinstance(n, int) for n in s):
        return None
    if len(s) == 1 or (len(s) == 2 and s[0] == 1):
        return s[-1]
    return None


def _vector_group(features: dict, whole: tuple[str, ...], prefixes: tuple[str, ...]) -> dict:
    """The action (or state) vector: the whole-vector key if there is one, else its float sub-keys concatenated."""
    for k in whole:
        ft = features.get(k)
        if isinstance(ft, dict):
            return {"keys": [k], "dim": _vec_dim(ft), "float": _is_float(ft), "split": False}
    parts = sorted(k for k, ft in features.items()
                   if isinstance(ft, dict) and k.startswith(prefixes) and _is_float(ft) and _vec_dim(ft))
    if not parts:
        return {"keys": [], "dim": None, "float": False, "split": False}
    return {"keys": parts, "dim": sum(_vec_dim(features[k]) for k in parts), "float": True, "split": True}


def _camera(key: str, ft: dict) -> dict:
    """Height, width and channel count of an image/video feature, from `names` if given, else the shape."""
    s = ft.get("shape") if isinstance(ft.get("shape"), list) else []
    names = [str(n).lower() for n in ft.get("names")] if isinstance(ft.get("names"), list) else []
    h = w = c = None
    if len(s) == 3 and len(names) == 3 and "height" in names and "width" in names:
        h, w = s[names.index("height")], s[names.index("width")]
        c = s[[i for i in range(3) if names[i] not in ("height", "width")][0]]
    elif len(s) == 3:
        if s[-1] in (1, 3, 4):
            h, w, c = s
        elif s[0] in (1, 3, 4):
            c, h, w = s
    rgb = c == 3 and "depth" not in key.lower() and "depth" not in names
    return {"key": key, "height": h, "width": w, "channels": c, "rgb": rgb}


def _check(id_: str, status: str, detail: str, **data) -> dict:
    return {"id": id_, "status": status, "detail": detail, **({"data": data} if data else {})}


def pi05_fit(info: Optional[dict]) -> dict:
    """π0.5 (openpi, pi05_base) fit from info.json. -> {verdict, checks: [{id, status, detail}], ...}."""
    if not isinstance(info, dict) or not isinstance(info.get("features"), dict):
        return {"verdict": "UNASSESSED", "checks": [], "reason": "no readable info.json"}
    F = info["features"]
    out = []

    # P1/P2 actions: a float vector, at most 32 wide (pad_to_dim pads, never truncates: transforms.py:423-430)
    act = _vector_group(F, ("action", "actions"), ("action.", "actions."))
    if not act["keys"]:
        out.append(_check("P1", "FAIL", "no action feature: π0.5 trains on action chunks"))
    elif not act["float"] or act["dim"] is None:
        out.append(_check("P1", "FAIL", f"`{act['keys'][0]}` is not a float vector "
                          f"(dtype {F[act['keys'][0]].get('dtype')!r}, shape {F[act['keys'][0]].get('shape')!r})"))
    else:
        if act["split"]:
            out.append(_check("P1", "ADAPT", f"actions split over {len(act['keys'])} keys; the config must "
                              "concatenate them into one vector", keys=act["keys"]))
        else:
            out.append(_check("P1", "OK", f"`{act['keys'][0]}` (float vector)"))
        d = act["dim"]
        out.append(_check("P2", "FAIL" if d > PI05_ACTION_DIM else "OK",
                          f"action dim {d} > {PI05_ACTION_DIM}: openpi pads but never truncates, and pi05_base "
                          f"is {PI05_ACTION_DIM}-wide" if d > PI05_ACTION_DIM
                          else f"action dim {d}, zero-padded to {PI05_ACTION_DIM}", dim=d))

    # P3 state: π0.5 writes it into the prompt as 256-bin tokens (discrete_state_input, tokenizer.py:26)
    st = _vector_group(F, ("observation.state", "state"), ("observation.state.", "observation.states."))
    if not st["keys"] or not st["float"] or st["dim"] is None:
        out.append(_check("P3", "ADAPT", "no float state vector: π0.5 puts the state in its prompt and raises "
                          "'State is required' (transforms.py:256-258); set discrete_state_input=False or feed zeros"))
    elif st["dim"] > PI05_ACTION_DIM:
        out.append(_check("P3", "FAIL", f"state dim {st['dim']} > {PI05_ACTION_DIM}: the model's state input is "
                          f"{PI05_ACTION_DIM}-wide (pi0_config.py:80)", dim=st["dim"]))
    elif st["split"]:
        out.append(_check("P3", "ADAPT", f"state split over {len(st['keys'])} keys (dim {st['dim']}); the config "
                          "must concatenate them", keys=st["keys"], dim=st["dim"]))
    else:
        out.append(_check("P3", "OK", f"state dim {st['dim']}, quantile-normalised then tokenised into the prompt",
                          dim=st["dim"]))

    # P4/P5 cameras: three RGB slots, each resized with padding to 224x224 (model.py:156-166)
    cams = [_camera(k, ft) for k, ft in F.items()
            if isinstance(ft, dict) and ft.get("dtype") in ("video", "image")]
    rgb = [c for c in cams if c["rgb"]]
    other = [c["key"] for c in cams if not c["rgb"]]
    skip = f"; not RGB, unusable as is: {', '.join(other)}" if other else ""
    n = len(rgb)
    if n == 0:
        out.append(_check("P4", "FAIL", "no RGB camera: π0.5 is a vision-language-action model and every image "
                          "slot would be blank" + skip, n_rgb=0))
    elif n > len(PI05_IMAGE_SLOTS):
        out.append(_check("P4", "ADAPT", f"{n} RGB cameras for {len(PI05_IMAGE_SLOTS)} slots (one base, two "
                          "wrist); the config must choose which to keep" + skip, n_rgb=n))
    else:
        out.append(_check("P4", "OK", f"{n} RGB camera(s) for {len(PI05_IMAGE_SLOTS)} slots; empty slots are "
                          "zero images, masked" + skip, n_rgb=n))
    if rgb:
        H, W = PI05_IMAGE_RESOLUTION
        sized = [c for c in rgb if c["height"] and c["width"]]
        small = [c["key"] for c in sized if c["height"] < H or c["width"] < W]
        wide = [c["key"] for c in sized if max(c["height"], c["width"]) >= 1.5 * min(c["height"], c["width"])]
        bits = []
        if small:
            bits.append(f"below {H}x{W}, upscaled: {', '.join(small)}")
        if wide:
            bits.append(f"aspect >= 1.5, so a third or more of the {H}x{W} input is black padding: {', '.join(wide)}")
        out.append(_check("P5", "NOTE" if bits else "OK", "; ".join(bits) if bits else
                          f"all RGB cameras resize to {H}x{W} with little padding"))

    # P6 fps and the action chunk: delta_timestamps are built from fps (data_loader.py:143-145)
    fps = info.get("fps")
    if not isinstance(fps, (int, float)) or fps <= 0:
        out.append(_check("P6", "FAIL", "no fps in info.json: openpi builds the action chunk's timestamps from it"))
    else:
        secs = PI05_ACTION_HORIZON / fps
        if fps <= PI05_LOW_FPS:
            out.append(_check("P6", "ADAPT", f"{fps:g} Hz: the default {PI05_ACTION_HORIZON}-step chunk spans "
                              f"{_half_up(secs, 1):.1f} s; openpi's own low-rate π0.5 configs shorten action_horizon "
                              "(pi05_libero 10, pi05_droid 15)", fps=fps, chunk_s=_half_up(secs, 2)))
        else:
            out.append(_check("P6", "OK", f"{fps:g} Hz: a {PI05_ACTION_HORIZON}-step chunk spans {_half_up(secs, 1):.1f} s",
                              fps=fps, chunk_s=_half_up(secs, 2)))
        # P7 short episodes: chunks past an episode's end are padding
        eps, frames = info.get("total_episodes"), info.get("total_frames")
        if isinstance(eps, int) and isinstance(frames, int) and eps > 0:
            mean = frames / eps
            out.append(_check("P7", "NOTE" if mean < PI05_ACTION_HORIZON else "OK",
                              f"episodes average {_half_up(mean, 0):.0f} frames, shorter than one {PI05_ACTION_HORIZON}-step "
                              "chunk: most targets are padding" if mean < PI05_ACTION_HORIZON
                              else f"episodes average {_half_up(mean, 0):.0f} frames", mean_frames=_half_up(mean, 1)))

    # P8 language: π0.5 raises without a prompt (transforms.py:252-254)
    tasks = info.get("total_tasks")
    has_ti = isinstance(F.get("task_index"), dict)
    if isinstance(tasks, int) and tasks > 0 and has_ti:
        out.append(_check("P8", "OK", f"{tasks} task string(s); prompt_from_task=True gives each frame its prompt",
                          tasks=tasks))
    else:
        out.append(_check("P8", "ADAPT", "no task strings to use as prompts: set default_prompt in the config, "
                          "or π0.5 raises 'Prompt is required'", tasks=tasks))

    worst = max((PI05_STATUS.index(c["status"]) for c in out), default=0)
    verdict = "NO_FIT" if worst == 3 else "ADAPT" if worst == 2 else "FIT"
    issues = [c["id"] for c in out if c["status"] in ("ADAPT", "FAIL")]
    return {"verdict": verdict, "checks": out, "issues": issues,
            "reason": "; ".join(c["detail"] for c in out if c["status"] in ("ADAPT", "FAIL")) or "fits π0.5 defaults"}
