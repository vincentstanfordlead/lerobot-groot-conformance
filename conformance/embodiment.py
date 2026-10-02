"""What kind of data is this? A metadata heuristic for embodiment, separate from loadability.

A dataset can pass every format check and still be outside what GR00T is built for: GR00T N1.7
targets arms, bimanual setups, mobile manipulators and humanoids, so a car-driving or human
motion-capture dataset in LeRobot format is well-formed but not GR00T training data.

Evidence, strongest first: info.json:robot_type (LeRobot writes it automatically), then feature and
dimension names. Mirrored in docs/app/embodiment.js; tests/test_js_parity.py keeps them equal.
"""
from __future__ import annotations

import json
import re

CATEGORIES = {
    "arm": ("Single robot arm", "fits"),
    "bimanual": ("Two-arm (bimanual) robot", "fits"),
    "humanoid": ("Humanoid / whole-body robot", "fits"),
    "mobile_manipulator": ("Mobile manipulator", "fits"),
    "vehicle": ("Vehicle / driving", "outside"),
    "human_motion": ("Human motion (no robot)", "outside"),
    "unclear": ("Couldn't tell from metadata", "unclear"),
}

# robot_type substrings -> category, checked in order (first match wins).
ROBOT_TYPES = [
    ("vehicle", r"racecar|\bcar\b|vehicle|\bkia\b|tesla|toyota|\bniro\b|driving|truck|carla"),
    ("human_motion", r"smpl|mocap|human"),
    ("humanoid", r"humanoid|unitree_?g1|\bg1\b|unitree_?h1|\bh1\b|gr1|fourier|kuavo|optimus|figure|digit|apollo|r1pro|a2d|tiangong|booster|t1\b"),
    ("mobile_manipulator", r"robocasa|stretch|lekiwi|mobile|omron|tiago|fetch|alphabot|ranger|xlerobot|aibot"),
    ("bimanual", r"^bi_|bimanual|aloha|_bi_|dual|yam_bimanual"),
    ("arm", r"so[-_]?10[01]|so_follower|so_simplified|koch|franka|panda|kuka|ur[35e]|xarm|widowx|piper|moss|omx|openarm|google_robot|metaworld|trossen|jaco|kinova|sawyer|fanuc|realman|arx|elephant|mycobot|stringman|yor|ffw|\byam\b|yam_"),
]
VEHICLE_WORDS = {"steer", "steering", "throttle", "gas_pedal", "brake", "brake_pedal", "gear", "turn_signal", "latitude", "longitude"}
HUMAN_WORDS = {"smpl", "mocap"}
_TOK = re.compile(r"[a-z0-9]+")


def _names(info: dict) -> set[str]:
    words: set[str] = set()
    feats = info.get("features") if isinstance(info.get("features"), dict) else {}
    for k, v in feats.items():
        words.add(k.lower())
        words.update(_TOK.findall(k.lower()))
        nm = v.get("names") if isinstance(v, dict) else None
        text = json.dumps(nm).lower() if nm is not None else ""
        words.update(_TOK.findall(text))
        words.update(re.findall(r"[a-z]+_[a-z_]+", text))  # keep gas_pedal, brake_pedal, turn_signal whole
    return words


def classify(info: dict | None, repo_id: str | None = None) -> dict:
    """-> {category, label, fit, evidence}. fit: fits | outside | unclear.
    repo_id is the weakest evidence: used only when robot_type and dimension names say nothing."""
    if not isinstance(info, dict):
        return _out("unclear", "info.json unavailable")
    rt = str(info.get("robot_type") or "").strip()
    rtl = rt.lower()
    words = _names(info)
    veh = sorted(VEHICLE_WORDS & words)
    hum = sorted(HUMAN_WORDS & words)
    # Feature evidence for a non-robot domain beats a generic or missing robot_type.
    if len(veh) >= 2:
        return _out("vehicle", f"vehicle controls in features: {', '.join(veh)}" + (f"; robot_type={rt!r}" if rt else ""))
    if hum:
        return _out("human_motion", f"human-motion features: {', '.join(hum)}")
    if rtl and rtl not in ("unknown", "none", "null", "robot"):
        for cat, pat in ROBOT_TYPES:
            if re.search(pat, rtl):
                return _out(cat, f"robot_type={rt!r}")
    # No usable robot_type: fall back to dimension names.
    has = lambda *ws: any(w in words for w in ws)  # noqa: E731
    sides = has("left", "right") or any(w.startswith(("left_", "right_")) for w in words)
    if has("leg", "knee", "ankle", "hip", "waist", "torso") and (has("hand", "finger", "thumb") or sides):
        return _out("humanoid", "body-part names (legs/waist with hands or two sides)")
    if has("gripper", "joint", "shoulder", "elbow", "wrist", "eef", "ee"):
        if has("base", "wheel", "odom", "chassis"):
            return _out("mobile_manipulator", "arm and mobile-base dimension names")
        if sides:
            return _out("bimanual", "left/right arm dimension names")
        return _out("arm", "arm dimension names (gripper / joints)")
    name = (repo_id or "").split("/")[-1].lower()
    if name:
        # A name only ever adds robot evidence: "human" in robocasa_..._human means human-teleoperated.
        for cat, pat in ROBOT_TYPES:
            if CATEGORIES[cat][1] != "fits":
                continue
            m = re.search(pat, name)
            if m:
                return _out(cat, f"only the dataset name ({m.group(0)!r} in {name!r}); robot_type={rt!r}")
    return _out("unclear", f"robot_type={rt!r} and no recognisable dimension names" if rt else "no robot_type and no recognisable dimension names")


def _out(cat: str, evidence: str) -> dict:
    label, fit = CATEGORIES[cat]
    return {"category": cat, "label": label, "fit": fit, "evidence": evidence}
