"""Draft a meta/modality.json from info.json:features.*.names. Python port of docs/app/draft.js.

The classifier is the heuristic behind the audit's "names clean enough to draft one" figure
(conformance/report.py classify_name / feature_tier). A draft is a PROPOSAL: a wrong gripper
index trains silently on the wrong joints, so callers must show it to a person before it is
written into meta/. tests/test_skill.py keeps this module and draft.js in agreement on every
audited info.json. Stdlib only.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

GRIPPER = {"gripper", "grip", "claw", "finger", "fingers", "grasp", "carriage"}
HAND = {"hand", "thumb", "index", "middle", "ring", "pinky", "palm"}
BODY = {"head", "neck", "torso", "leg", "hip", "knee", "ankle"}
JOINT = {"joint", "joints", "shoulder", "elbow", "wrist", "waist", "forearm", "arm", "upperarm", "flex"}
BASE = {"base", "wheel", "wheels", "vel", "velocity", "odom", "chassis"}
ROT = {"roll", "pitch", "yaw", "rx", "ry", "rz", "rw", "quat", "qx", "qy", "qz", "qw", "rot", "rotation", "axis", "euler"}
POS = {"x", "y", "z", "pos", "position", "xyz"}
NUMBERED_JOINT = re.compile(r"^(?:joint|j|motor|q|dof|servo)[_.\- ]?\d+$")
GENERIC = re.compile(r"^(?:[a-z]{0,6}[_.\- ]?)?\d+$|^(?:dim|state|action|obs|axis)[_.\- ]?\d+$")
SIDE = re.compile(r"^(?:left|right|l|r|main|aux|(?:arm|robot|agent|umi)\d+)$")

TIER_HELP = {
    "no_state_or_action_feature": "info.json declares no observation.state / action feature, so there is nothing to split.",
    "no_names": "The state/action dimensions have no names. Only someone who knows the robot can say which is which.",
    "names_unusable": "The names don't line up one-to-one with the dimensions, so they can't be used to split them.",
    "opaque_names": "Some dimension names are generic (e.g. motor_0, joint_3, 0), so which one is the gripper can't be inferred.",
    "fragmented_groups": "A body part's dimensions are not contiguous, but GR00T groups must be one start:end range.",
}


def _js_falsy(v: Any) -> bool:
    return v is None or v is False or v == "" or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0)


def classify_name(name: Any, numbered_joint_ok: bool = False) -> Optional[list]:
    n = str(name).lower().strip()
    if not n:
        return None
    if NUMBERED_JOINT.match(n):
        return ["", "joint"] if numbered_joint_ok else None
    if GENERIC.match(n):
        return None
    raw = [t for t in re.split(r"[^a-z0-9]+", n) if t]
    side_tok = next((t for t in raw if SIDE.match(t)), None)
    side = "" if side_tok is None else (side_tok[0].upper() if side_tok in ("left", "right", "l", "r") else side_tok)
    toks = [re.sub(r"(?<=[a-z])\d+$", "", t) for t in raw]
    has = lambda vocab: any(t in vocab for t in toks)  # noqa: E731
    if has(GRIPPER):
        return [side, "gripper"]
    if has(HAND):
        return [side, "hand"]
    body = next((t for t in toks if t in BODY), None)
    if body:
        return ["", "body:" + body]
    for cls, vocab in (("joint", JOINT), ("base", BASE), ("eef_rot", ROT), ("eef_pos", POS)):
        if has(vocab):
            return [side, cls]
    return None


def _flat_names(feat: dict) -> Optional[list]:
    nm = feat.get("names")
    if isinstance(nm, dict):
        vals = [v for v in nm.values() if isinstance(v, list)]
        nm = vals[0] if len(vals) == 1 else ([x for v in vals for x in v] if vals else None)
    return nm if isinstance(nm, list) and all(isinstance(x, str) for x in nm) else None


def feature_tier(feats: dict, key: str) -> dict:
    """-> {tier, runs: [[[side, cls], start, end]], names, bad}"""
    f = feats.get(key)
    if not isinstance(f, dict):
        return {"tier": "no_state_or_action_feature"}
    nm = f.get("names")
    if _js_falsy(nm) or (isinstance(nm, list) and not nm):
        return {"tier": "no_names"}
    names = _flat_names(f)
    shape = f.get("shape")
    if names is None or not isinstance(shape, list) or len(shape) != 1 or len(names) != shape[0]:
        return {"tier": "names_unusable"}
    named_gripper = any((classify_name(n) or [None, None])[1] == "gripper" for n in names)
    cls = [classify_name(n, named_gripper) for n in names]
    bad = [n for n, c in zip(names, cls) if c is None]
    if bad:
        return {"tier": "opaque_names", "bad": bad[:6], "names": names}
    runs, start = [], 0
    for i in range(1, len(cls) + 1):
        if i == len(cls) or cls[i] != cls[start]:
            runs.append([cls[start], start, i])
            start = i
    labels = ["|".join(c) for c, _, _ in runs]
    if len(set(labels)) < len(labels):
        return {"tier": "fragmented_groups", "runs": runs, "names": names}
    return {"tier": "looks_inferable", "runs": runs, "names": names}


def _side_prefix(side: str) -> str:
    return "left_" if side == "L" else "right_" if side == "R" else f"{side}_" if side else ""


def _group_name(c: list) -> str:
    side, cls = c
    if cls == "joint":
        return f"{_side_prefix(side)}arm" if side else "single_arm"
    if cls == "eef_pos":
        return f"{_side_prefix(side)}eef_position"
    if cls == "eef_rot":
        return f"{_side_prefix(side)}eef_rotation"
    if cls.startswith("body:"):
        return cls[5:]
    return f"{_side_prefix(side)}{cls}"


def _shape0(feats: dict, key: str):
    f = feats.get(key)
    s = f.get("shape") if isinstance(f, dict) else None
    return s[0] if isinstance(s, list) and s else ("<none>", key)  # distinct sentinels never compare equal


def draft_modality(info: Any) -> dict:
    """-> {ok, draft?, groups?, notes[], reason?, bad?}"""
    feats = info.get("features") if isinstance(info, dict) and isinstance(info.get("features"), dict) else {}
    notes: list[str] = []
    parts = {k: feature_tier(feats, k) for k in ("observation.state", "action")}
    st, ac = parts["observation.state"], parts["action"]
    # Common case: action has no usable names but mirrors state (same dim). Reuse state's split, flagged.
    if (st["tier"] == "looks_inferable" and ac["tier"] != "looks_inferable"
            and ac["tier"] in ("no_names", "names_unusable")
            and _shape0(feats, "action") == _shape0(feats, "observation.state")):
        parts["action"] = {**st, "mirrored": True}
        notes.append("action has no usable names; its split copies observation.state (same dimension). "
                     "Check that the action really is ordered the same way.")
    for key, p in parts.items():
        if p["tier"] != "looks_inferable":
            out = {"ok": False, "reason": f"{key}: {TIER_HELP.get(p['tier'], p['tier'])}", "notes": notes}
            if "bad" in p:
                out["bad"] = p["bad"]
            return out
    draft: dict = {"state": {}, "action": {}}
    groups: dict = {"state": [], "action": []}
    sides = {c[0] for k in ("observation.state", "action") for c, _, _ in parts[k]["runs"]}
    only = next(iter(sides)) if len(sides) == 1 else None
    drop_side = len(sides) == 1 and bool(only) and only not in ("L", "R")
    if drop_side:
        notes.append(f'Every dimension name starts with "{only}"; it was treated as the robot\'s name, not a side.')
    for section, key in (("state", "observation.state"), ("action", "action")):
        for raw_cls, s, e in parts[key]["runs"]:
            c = ["", raw_cls[1]] if drop_side else raw_cls
            name = _group_name(c)
            draft[section][name] = {"start": s, "end": e}
            groups[section].append({"name": name, "start": s, "end": e, "dims": parts[key]["names"][s:e]})
    video = [k for k, v in feats.items() if isinstance(v, dict) and v.get("dtype") == "video"]
    if video:
        draft["video"] = {re.sub(r"^observation\.images\.", "", k).replace(".", "_"): {"original_key": k} for k in video}
    if "task_index" in feats:
        draft["annotation"] = {"human.task_description": {"original_key": "task_index"}}
        notes.append("annotation points at task_index, as in NVIDIA's cube_to_bowl_5 demo. "
                     "The key must match the language key in your training recipe.")
    notes.append("Group names (single_arm, gripper, …) must match the embodiment config you train with. "
                 "NVIDIA's demo uses single_arm and gripper.")
    return {"ok": True, "draft": draft, "groups": groups, "notes": notes}


def _j(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def format_modality(m: dict) -> str:
    """Readable JSON: one line per group / video / annotation entry (same text as draft.js)."""
    def inline(v):
        if isinstance(v, dict):
            return "{" + ", ".join(f"{_j(a)}: {_j(b)}" for a, b in v.items()) + "}"
        return _j(v)

    def sec(obj):
        return "{\n" + ",\n".join(f"    {_j(k)}: {inline(v)}" for k, v in obj.items()) + "\n  }"

    return "{\n" + ",\n".join(f"  {_j(k)}: {sec(v)}" for k, v in m.items()) + "\n}\n"
