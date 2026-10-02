"""Audit report: aggregate results/raw/**/*.json -> CSV + markdown + chart.

    .venv/bin/python -m conformance.report               # fetches meta/info.json for goal 6 if not cached
    .venv/bin/python -m conformance.report --offline     # never touch the network

Outputs (all under results/):
    summary.csv               one row per audited dataset, one column per check
    report.md                 every table below, with n per stratum and footnotes
    goal6_inferability.csv    per-dataset modality.json inferability tier (goal 6)
    conformance_chart.png     stacked distance-to-ready by stratum
    info_cache/<id>.json      meta/info.json copies (goal 6 only; pinned to the audited repo sha)

Rules this file enforces (plan §6/§7, NOTES.md Phase 3 "Things Phase 4 must handle"):
  * never a pooled pass rate: every table is per stratum and carries its n;
  * multi-dataset containers (not_lerobot_reason=nested_datasets) are their own row, and
    their sub-datasets are NOT audited (that would change the sampling unit);
  * `unverified_size` results are footnoted; a READY with any unverified FAIL-level check is
    reported as READY†, never as a clean READY;
  * only S-tail is a random sample, so only S-tail gets a confidence interval. S-curated is a
    census; S-popular / S-recent are purposive (top-100 by a criterion) - an interval would
    imply a sampling process that does not exist.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STRATA = ["S-curated", "S-popular", "S-recent", "S-tail"]
DAGGER = "†"

L_IDS = [f"L{i}" for i in range(1, 13)]
G_IDS = [f"G{i}" for i in range(1, 17)]
FAIL_LEVEL_G = ["G1", "G2", "G3", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13", "G14", "G15", "G16"]
# G6 (modality.json absent) and the checks that only run once it exists.
MODALITY_IDS = {"G6", "G10", "G11", "G12", "G13"}

VERDICT_ORDER = ["READY", "READY" + DAGGER, "NEEDS_REPAIR", "NEEDS_MODALITY", "NEEDS_DOWNCONVERT",
                 "INCONSISTENT_MODALITY", "BLOCKED",
                 "NOT_LEROBOT: container", "NOT_LEROBOT: other"]
WHO_FIXES = {
    "READY": "passes all static checks", "READY" + DAGGER: "passes, but G2/G3/G14 not checkable under 2 MB cap",
    "NEEDS_REPAIR": "converter (lossy: drops episodes)",
    "NEEDS_MODALITY": "add `meta/modality.json`: someone who knows the robot (no tool)",
    "NEEDS_DOWNCONVERT": "`convert_v3_to_v2.py`, then add `modality.json` (2 steps)",
    "INCONSISTENT_MODALITY": "producer: fix `modality.json` (can fail silently)",
    "BLOCKED": "no episode data, or a structural failure outside the v3.0 gap; no tool",
    "NOT_LEROBOT: container": "n/a - audit-unit mismatch, sub-datasets not audited",
    "NOT_LEROBOT: other": "n/a - different format / malformed layout",
}
# Steps from the dataviz reference palette (light surface).
COLORS = {
    "READY": "#86b6ef", "READY" + DAGGER: "#86b6ef", "NEEDS_REPAIR": "#5598e7",
    "NEEDS_MODALITY": "#2a78d6", "NEEDS_DOWNCONVERT": "#184f95",
    "INCONSISTENT_MODALITY": "#eb6834", "BLOCKED": "#898781",
    "NOT_LEROBOT: container": "#c3c2b7", "NOT_LEROBOT: other": "#e1e0d9",
}
HATCH = {"READY" + DAGGER: "///", "NOT_LEROBOT: container": "\\\\\\"}
WHITE_TEXT = {"NEEDS_MODALITY", "NEEDS_DOWNCONVERT", "INCONSISTENT_MODALITY", "BLOCKED"}
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


# ================================================================ loading

def load_raw(results: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((results / "raw").rglob("*.json"))]


def load_errors(results: Path) -> list[dict]:
    d = results / "errors"
    return [json.loads(p.read_text()) for p in sorted(d.rglob("*.json"))] if d.exists() else []


def verdict_label(r: dict) -> str:
    v = r["verdict"]
    if v == "NOT_LEROBOT":
        return "NOT_LEROBOT: container" if r.get("not_lerobot_reason") == "nested_datasets" else "NOT_LEROBOT: other"
    if v == "READY" and r.get("unverified_size"):
        return "READY" + DAGGER
    return v


def _cell(c: dict | None) -> str:
    if c is None:
        return ""  # check did not run (NOT_LEROBOT stops the L-series after L1)
    if c["passed"] is True:
        return "pass"
    if c["passed"] is False:
        return "fail"
    return f"skip:{c.get('blocked_by') or '?'}"


_DP = re.compile(r"data_path='([^']*)'")
_VP = re.compile(r"video_path='([^']*)'")


def _path_family(detail: str, rx: re.Pattern) -> str:
    m = rx.search(detail or "")
    if not m:
        return "missing/none"
    p = m.group(1)
    if "file_index" in p or "chunk_index" in p:
        return "v3-style"
    if "episode_index" in p:
        return "v2-style"
    return "other"


def build_frame(raw: list[dict]) -> pd.DataFrame:
    rows = []
    for r in raw:
        c = {k["id"]: k for k in r["checks"]}
        l2 = (c.get("L2") or {}).get("data", {})
        l8 = (c.get("L8") or {}).get("data", {})
        l9 = (c.get("L9") or {}).get("data", {})
        row = {
            "dataset": r["dataset"], "author": r["dataset"].split("/")[0], "stratum": r["stratum"],
            "verdict": r["verdict"], "verdict_label": verdict_label(r), "steps": "+".join(r["steps"]),
            "n_steps": len(r["steps"]), "failed_fail_level": ",".join(r["failed_fail_level"]),
            "not_lerobot_reason": r.get("not_lerobot_reason", ""),
            "n_nested_found": (r.get("nested_datasets") or {}).get("n_found", ""),
            "nested_scan_complete": (r.get("nested_datasets") or {}).get("scan_complete", ""),
            "codebase_version": l2.get("codebase_version") or "(none)",
            "ep_layout": (c.get("L5") or {}).get("data", {}).get("layout") or "",
            "task_layout": (c.get("L6") or {}).get("data", {}).get("layout") or "",
            "stats_layout": (c.get("L7") or {}).get("data", {}).get("layout") or "",
            "state_dim": l8.get("state_dim", ""), "action_dim": l8.get("action_dim", ""),
            "n_cameras": l8.get("n_cameras", ""), "fps": l8.get("fps", ""),
            "names_state": l9.get("observation.state", ""), "names_action": l9.get("action", ""),
            "data_path_family": _path_family(c["G7"]["detail"], _DP) if "G7" in c else "",
            "video_path_family": _path_family(c["G9"]["detail"], _VP) if "G9" in c else "",
            "stats_usable_as_is": r["stats_usable_as_is"],
            "unverified_size": ",".join(r.get("unverified_size", [])),
            "clean_except_modality": r["verdict"] in ("READY", "NEEDS_MODALITY") and "REPAIR" not in r["steps"],
            "silent_failure": any(c[i]["data"].get("silent") and c[i]["passed"] is False
                                  for i in ("G11", "G12") if i in c),
            "used_storage_gb": round((r["size"].get("used_storage_bytes") or 0) / 1e9, 3),
            "parquet_gb_listed": round(r["size"]["parquet_bytes_listed"] / 1e9, 3),
            "video_gb_listed": round(r["size"]["video_bytes_listed"] / 1e9, 3),
            "listing_complete": r["fetch"]["listing_complete"],
            "repo_sha": r["repo_sha"], "repo_last_modified": r["repo_last_modified"],
            "audit_date": r["audit_date"], "groot_sha": r["groot_sha"],
            "huggingface_hub_version": r["huggingface_hub_version"],
        }
        for i in L_IDS + G_IDS:
            row[i] = _cell(c.get(i))
        rows.append(row)
    return pd.DataFrame(rows)


# ================================================================ formatting helpers

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def pct(k: int, n: int) -> str:
    if not n:
        return "0"
    share = k / n
    return f"{k} (<1%)" if k and f"{share:.0%}" == "0%" else f"{k} ({share:.0%})"


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


# ================================================================ tables

def verdict_table(cols: dict[str, pd.DataFrame]) -> str:
    """Distance-to-ready, per column (stratum). Never pooled."""
    header = ["verdict"] + [f"{name} (n={len(d)})" for name, d in cols.items()] + ["who fixes it"]
    rows = []
    for v in VERDICT_ORDER:
        cells = [pct(int((d.verdict_label == v).sum()), len(d)) for d in cols.values()]
        if all(c == "0" for c in cells):
            continue
        rows.append([f"`{v}`"] + cells + [WHO_FIXES[v]])
    rows.append([f"*…of which {DAGGER} unverified_size (G2/G3/G14 not checkable)*"]
                + [f"*{int((d.unverified_size != '').sum())}*" for d in cols.values()] + [""])
    return md_table(header, rows)


def fixcost_table(strat: dict[str, pd.DataFrame]) -> str:
    rows = []
    for s, d in strat.items():
        x = d[d.verdict == "NEEDS_DOWNCONVERT"]
        if x.empty:
            rows.append([s, len(d), 0, "-", "-", "-"])
        else:
            rows.append([s, len(d), len(x), f"{statistics.median(x.used_storage_gb):.1f}",
                         f"{x.used_storage_gb.max():.0f}", f"{x.used_storage_gb.sum() / 1000:.1f}"])
    return md_table(["stratum", "n", "NEEDS_DOWNCONVERT", "median GB", "max GB", "sum TB"], rows)


def top_failures(strat: dict[str, pd.DataFrame]) -> str:
    """Top 5 FAIL-level G-checks per stratum, over LeRobot-format datasets only."""
    parts = []
    for s, d in strat.items():
        lr = d[d.verdict != "NOT_LEROBOT"]
        rows = []
        for i in FAIL_LEVEL_G:
            failed = lr[lr[i] == "fail"]
            if not failed.empty:
                rows.append((i, len(failed), int((failed.data_path_family == "v3-style").sum()),
                             int(lr[i].str.startswith("skip").sum())))
        rows.sort(key=lambda t: -t[1])
        body = [[k + 1, f"`{i}`", pct(f, len(lr)), v3, sk] for k, (i, f, v3, sk) in enumerate(rows[:5])]
        parts.append(f"**{s}** - {len(lr)} LeRobot-format datasets (of {len(d)} audited; NOT_LEROBOT excluded "
                     f"because it trivially fails G1/G2/G3/G6)\n\n"
                     + md_table(["rank", "check", "failed", "of which v3-style data_path",
                                 "skipped (blocked/size)"], body))
    return "\n".join(parts)


ROOT_CAUSES = [  # (label, level, who fixes, predicate over a LeRobot-format row)
    ("v3.0 layout: GR00T reads v2.x (G2/G3/G7/G8/G9)", "FAIL", "converter: `convert_v3_to_v2.py`",
     lambda d: d.steps.str.contains("DOWNCONVERT")),
    ("no episode data: no parquet under `data/` (metadata-only upload or other storage format) (L3)", "FAIL",
     "producer: upload the data", lambda d: d.steps.str.contains("BLOCKED") & (d.L3 == "fail")),
    ("other structural failure on a v2.x layout (G2/G3/G7/G8/G9/G15/G16)", "FAIL", "unknown; no tool",
     lambda d: d.steps.str.contains("BLOCKED") & (d.L3 != "fail")),
    ("episode files listed in metadata but absent (G14)", "FAIL", "converter: `repair_lerobot_metadata.py` (lossy)",
     lambda d: d.steps.str.contains("REPAIR")),
    ("`modality.json` shipped but inconsistent (G10-G13)", "FAIL", "producer",
     lambda d: d.verdict == "INCONSISTENT_MODALITY"),
    ("no `meta/stats.json` (G4)", "WARN", "auto: regenerated at train time",
     lambda d: d.G4 == "fail"),
    ("`stats.json` lacks some of mean/std/min/max/q01/q99 (G5)", "WARN", "auto: regenerated at train time",
     lambda d: d.G5 == "fail"),
    ("episodes.jsonl line count != `total_episodes` (L11)", "WARN", "converter",
     lambda d: d.L11 == "fail"),
    ("a camera feature has no `videos/` directory (L10)", "INFO", "producer (re-upload)",
     lambda d: d.L10 == "fail"),
    ("no `names` on state and/or action (L9)", "INFO", "producer",
     lambda d: d.L9 == "fail"),
    ("`fps` not declared (L12)", "WARN", "producer",
     lambda d: d.L12 == "fail"),
]


def beyond_modality(strat: dict[str, pd.DataFrame]) -> str:
    """What fails once the missing modality.json is set aside, by root cause. Not exclusive."""
    lrs = {s: d[d.verdict != "NOT_LEROBOT"] for s, d in strat.items()}
    header = ["root cause", "level", "who fixes it"] + [f"{s} (n={len(d)})" for s, d in lrs.items()]
    rows = [[f"**passes every FAIL-level check except `modality.json`**", "", ""]
            + [f"**{pct(int(d.clean_except_modality.sum()), len(d))}**" for d in lrs.values()]]
    for label, level, who, pred in ROOT_CAUSES:
        rows.append([label, level, who] + [pct(int(pred(d).sum()), len(d)) for d in lrs.values()])
    return md_table(header, rows)


def failures_excluding_modality(strat: dict[str, pd.DataFrame]) -> str:
    """Every L/G check except G6 and the checks blocked behind it, ranked by S-tail (the random sample)."""
    lrs = {s: d[d.verdict != "NOT_LEROBOT"] for s, d in strat.items()}
    levels = {}
    for d in lrs.values():
        for i in L_IDS + G_IDS:
            levels.setdefault(i, None)
    rows = []
    for i in L_IDS + G_IDS:
        if i == "G6":
            continue
        counts = [int((d[i] == "fail").sum()) for d in lrs.values()]
        if not any(counts):
            continue
        rows.append((counts[-1], i, counts))
    rows.sort(key=lambda t: (-t[0], -sum(t[2])))
    body = [[k + 1, f"`{i}`", CHECK_LEVEL.get(i, ""), CHECK_TEXT.get(i, "")]
            + [pct(c, len(d)) for c, d in zip(counts, lrs.values())]
            for k, (_, i, counts) in enumerate(rows)]
    return md_table(["rank", "check", "level", "what fails"] + [f"{s} (n={len(d)})" for s, d in lrs.items()], body)


CHECK_LEVEL = {**{f"L{i}": "INFO" for i in (2, 3, 4, 9, 10)}, **{f"L{i}": "WARN" for i in (1, 5, 6, 7, 8, 11, 12)},
               **{i: "FAIL" for i in FAIL_LEVEL_G}, "G4": "WARN", "G5": "WARN"}
CHECK_TEXT = {
    "L2": "no `codebase_version`", "L3": "no parquet under `data/`", "L4": "no `videos/` (state-only)",
    "L5": "no episode metadata", "L6": "no task metadata", "L7": "no stats file of any kind",
    "L8": "no `features`", "L9": "no `names` on state/action", "L10": "camera feature without a `videos/` dir",
    "L11": "episodes.jsonl lines != `total_episodes`", "L12": "`fps` not declared",
    "G2": "no `meta/episodes.jsonl` with `length` (v2.x file)", "G3": "no `meta/tasks.jsonl` (v2.x file)",
    "G4": "no `meta/stats.json`", "G5": "stats.json lacks a stat type",
    "G7": "`data_path` uses placeholders the loader does not supply", "G8": "no `chunks_size`",
    "G9": "`video_path` missing or uses unsupported placeholders", "G10": "video `original_key` not in features",
    "G11": "`modality.json` state/action section empty", "G12": "group slices out of range / dims uncovered",
    "G13": "annotation column not in features", "G14": "episode file listed but absent",
    "G15": "feature without `dtype`", "G16": "non-float state/action",
}


def add_embodiment(df: pd.DataFrame, results: Path) -> None:
    """embodiment / embodiment_fit / embodiment_evidence from info.json at the audited sha (info_cache)."""
    from .embodiment import classify
    cats, fits, evs = [], [], []
    for r in df.itertuples():
        p = results / "info_cache" / f"{r.dataset}.json"
        if r.verdict == "NOT_LEROBOT" or not p.exists():
            cats.append(""); fits.append(""); evs.append("")
            continue
        e = classify(json.loads(p.read_text()), r.dataset)
        cats.append(e["category"]); fits.append(e["fit"]); evs.append(e["evidence"])
    df["embodiment"], df["embodiment_fit"], df["embodiment_evidence"] = cats, fits, evs


def embodiment_table(strat: dict[str, pd.DataFrame]) -> str:
    from .embodiment import CATEGORIES
    lrs = {s: d[d.verdict != "NOT_LEROBOT"] for s, d in strat.items()}
    rows = []
    for cat, (label, fit) in CATEGORIES.items():
        cells = [pct(int((d.embodiment == cat).sum()), len(d)) for d in lrs.values()]
        if all(c == "0" for c in cells):
            continue
        rows.append([label, {"fits": "fits GR00T's embodiments", "outside": "**likely outside GR00T's scope**",
                             "unclear": "unclear"}[fit]] + cells)
    rows.append(["**of which: well-formed but outside scope**", "passes every FAIL-level check except modality.json"]
                + [str(int(((d.embodiment_fit == "outside") & d.clean_except_modality).sum())) for d in lrs.values()])
    return md_table(["what the data is", "fit"] + [f"{s} (n={len(d)})" for s, d in lrs.items()], rows)


def stats_table(strat: dict[str, pd.DataFrame]) -> str:
    rows = []
    for s, d in strat.items():
        lr = d[d.verdict != "NOT_LEROBOT"]
        has = lr[lr.G4 == "pass"]
        rows.append([s, len(lr), pct(len(has), len(lr)),
                     pct(int((lr.stats_layout == "episodes_stats.jsonl").sum()), len(lr)),
                     pct(int((has.G5 == "pass").sum()), len(has)) if len(has) else "-"])
    return md_table(["stratum", "n (LeRobot-format)", "ships stats.json (G4)", "ships episodes_stats.jsonl only",
                     "of stats.json holders: all six stat types (G5)"], rows)


def version_crosstabs(df: pd.DataFrame, strat: dict[str, pd.DataFrame]) -> str:
    out = ["**codebase_version by stratum**\n",
           md_table(["version"] + [f"{s} (n={len(d)})" for s, d in strat.items()],
                    [[f"`{v}`"] + [pct(int((d.codebase_version == v).sum()), len(d)) for d in strat.values()]
                     for v in sorted(df.codebase_version.unique())])]
    for s, d in strat.items():
        labs = [v for v in VERDICT_ORDER if (d.verdict_label == v).any()]
        rows = [[f"`{v}`", int((d.codebase_version == v).sum())]
                + [int(((d.codebase_version == v) & (d.verdict_label == lab)).sum()) for lab in labs]
                for v in sorted(d.codebase_version.unique())]
        out.append(f"**{s}: verdict by codebase_version** (n={len(d)})\n")
        out.append(md_table(["version", "n"] + labs, rows))
    return "\n".join(out)


def curated_split(df: pd.DataFrame) -> str:
    cur = df[df.stratum == "S-curated"]
    is_lr = cur.author.str.lower() == "lerobot"
    by_author = cur.groupby("author").size().sort_values(ascending=False)
    return (verdict_table({"lerobot/*": cur[is_lr], "other curated orgs": cur[~is_lr]})
            + f"\nCurated publishers in the sample: {', '.join(f'{a} ({n})' for a, n in by_author.items())}\n")


def drift_table(df: pd.DataFrame) -> str:
    """Within a single codebase_version string: which schema variants coexist?"""
    lr = df[df.verdict != "NOT_LEROBOT"]
    attrs = [("episode metadata (L5)", "ep_layout"), ("task metadata (L6)", "task_layout"),
             ("stats file (L7)", "stats_layout"), ("data_path style (G7)", "data_path_family"),
             ("video_path style (G9)", "video_path_family")]
    rows = []
    for v in sorted(lr.codebase_version.unique()):
        d = lr[lr.codebase_version == v]
        per_s = " / ".join(str(int((d.stratum == s).sum())) for s in STRATA)
        for label, col in attrs:
            if d[col].nunique() > 1 or label.startswith("data_path"):
                rows.append([f"`{v}`", len(d), label,
                             "; ".join(f"{k or 'none'}: {n}" for k, n in d[col].value_counts().items()), per_s])
        g5 = d[d.G4 == "pass"].G5.value_counts()
        if g5.size > 1:
            rows.append([f"`{v}`", len(d), "quantile stats present (G5, stats.json holders only)",
                         "; ".join(f"{k}: {n}" for k, n in g5.items()), ""])
        sig = d[[c for _, c in attrs] + ["G5"]].astype(str).drop_duplicates()
        rows.append([f"`{v}`", len(d), "**distinct full signatures**", f"**{len(sig)}**", ""])
    v3 = lr.codebase_version.str.startswith("v3")
    v2 = lr.codebase_version.str.startswith("v2")
    mism = lr[(v3 & (lr.data_path_family == "v2-style")) | (v2 & (lr.data_path_family == "v3-style"))]
    tab = md_table(["version string", "n", "attribute", "variants (count)",
                    "n per stratum curated/popular/recent/tail"], rows)
    tab += (f"\nVersion string vs actual layout disagree: {len(mism)} dataset(s)"
            + (": " + ", ".join(f"{r.stratum} ({r.codebase_version} string, {r.data_path_family} data_path)"
                                for r in mism.itertuples()) if len(mism) else "") + "\n")
    return tab


def concentration(strat: dict[str, pd.DataFrame]) -> str:
    rows = [[s, len(d), d.author.nunique(),
             ", ".join(str(n) for n in d.author.value_counts().head(3))] for s, d in strat.items()]
    return md_table(["stratum", "n", "distinct authors", "datasets from the 3 largest authors"], rows)


def containers(df: pd.DataFrame) -> str:
    c = df[df.verdict_label == "NOT_LEROBOT: container"]
    return md_table(["stratum", "sub-datasets found", "scan complete", "repo GB"],
                    [[r.stratum, r.n_nested_found,
                      "yes" if r.nested_scan_complete else "**no (lower bound)**", f"{r.used_storage_gb:.0f}"]
                     for r in c.itertuples()])


def listing(d: pd.DataFrame, extra: list[str]) -> str:
    """Individual cases without repo ids (ids are in summary.csv)."""
    return md_table(["stratum", "version", "steps", "unverified", "failed FAIL-level"] + extra,
                    [[r.stratum, r.codebase_version, r.steps or "-", r.unverified_size or "-",
                      r.failed_fail_level or "-"] + [str(getattr(r, e)) for e in extra] for r in d.itertuples()])


# ================================================================ goal 6: modality.json inferability

TIERS = ["no_state_or_action_feature", "no_names", "names_unusable", "opaque_names", "fragmented_groups",
         "looks_inferable"]  # index 0 = furthest from inferable
TIER_TEXT = {
    "no_state_or_action_feature": "features lack observation.state and/or action",
    "no_names": "no `names` on state and/or action - needs a human",
    "names_unusable": "names present but not a flat list matching the feature dim",
    "opaque_names": "names present, but >=1 dim unrecognised or generic (joint_0, motor_3, 0, 1...) - needs a human",
    "fragmented_groups": "all dims recognised, but a semantic group is not one contiguous range (GR00T groups are start:end)",
    "looks_inferable": "all dims recognised AND every group is one contiguous range",
}
_GRIPPER = {"gripper", "grip", "claw", "finger", "fingers", "grasp", "carriage"}
_HAND = {"hand", "thumb", "index", "middle", "ring", "pinky", "palm"}
_BODY = {"head", "neck", "torso", "leg", "hip", "knee", "ankle"}  # each token is its own group
_JOINT = {"joint", "joints", "shoulder", "elbow", "wrist", "waist", "forearm", "arm", "upperarm", "flex"}
_BASE = {"base", "wheel", "wheels", "vel", "velocity", "odom", "chassis"}
_ROT = {"roll", "pitch", "yaw", "rx", "ry", "rz", "rw", "quat", "qx", "qy", "qz", "qw", "rot", "rotation", "axis", "euler"}
_POS = {"x", "y", "z", "pos", "position", "xyz"}
# Numbered-but-unnamed joints. Only opaque when nothing in the feature is a named gripper: with a named
# gripper the rest is "the arm" by elimination; without one, the gripper's index is unknowable (motor_0..5).
_NUMBERED_JOINT = re.compile(r"^(?:joint|j|motor|q|dof|servo)[_.\- ]?\d+$")
_GENERIC = re.compile(r"^(?:[a-z]{0,6}[_.\- ]?)?\d+$|^(?:dim|state|action|obs|axis)[_.\- ]?\d+$")
_SIDE = re.compile(r"^(?:left|right|l|r|main|aux|(?:arm|robot|agent|umi)\d+)$")


def classify_name(name: str, numbered_joint_ok: bool = False) -> tuple[str, str] | None:
    """(side, semantic class) for a dim name, or None if opaque/generic. First matching class wins:
    `wrist_roll` is a joint (not a rotation), `gripper.pos` a gripper (not a position), `chassis_pos_1` a
    base (not an eef position), `head_yaw` a body group (not a rotation). Side = first left/right/armN token."""
    n = str(name).lower().strip()
    if not n:
        return None
    if _NUMBERED_JOINT.match(n):  # before _GENERIC, which would swallow "joint1" / "joint_0"
        return ("", "joint") if numbered_joint_ok else None
    if _GENERIC.match(n):
        return None
    raw = [t for t in re.split(r"[^a-z0-9]+", n) if t]
    side = next((t[0].upper() if t in ("left", "right", "l", "r") else t for t in raw if _SIDE.match(t)), "")
    toks = [re.sub(r"(?<=[a-z])\d+$", "", t) for t in raw]  # "Joint1" -> "joint"; "arm1" stays a side token
    ts = set(toks)
    for cls, vocab in (("gripper", _GRIPPER), ("hand", _HAND)):
        if ts & vocab:
            return side, cls
    body = [t for t in toks if t in _BODY]
    if body:
        return "", "body:" + body[0]
    for cls, vocab in (("joint", _JOINT), ("base", _BASE), ("eef_rot", _ROT), ("eef_pos", _POS)):
        if ts & vocab:
            return side, cls
    return None


def _flat_names(feat: dict) -> list | None:
    nm = feat.get("names")
    if isinstance(nm, dict):
        vals = [v for v in nm.values() if isinstance(v, list)]
        nm = vals[0] if len(vals) == 1 else (sum(vals, []) if vals else None)
    return nm if isinstance(nm, list) and all(isinstance(x, str) for x in nm) else None


def feature_tier(feats: dict, key: str) -> tuple[str, list[str]]:
    f = feats.get(key)
    if not isinstance(f, dict):
        return "no_state_or_action_feature", []
    if not f.get("names"):
        return "no_names", []
    names, shape = _flat_names(f), f.get("shape")
    if names is None or not isinstance(shape, list) or len(shape) != 1 or len(names) != shape[0]:
        return "names_unusable", []
    has_named_gripper = any((c := classify_name(n)) and c[1] == "gripper" for n in names)
    cls = [classify_name(n, numbered_joint_ok=has_named_gripper) for n in names]
    bad = [n for n, c in zip(names, cls) if c is None]
    if bad:
        return "opaque_names", bad[:6]
    runs, start = [], 0
    for i in range(1, len(cls) + 1):
        if i == len(cls) or cls[i] != cls[start]:
            runs.append((cls[start], start, i))
            start = i
    labels = [c for c, _, _ in runs]
    if len(set(labels)) < len(labels):
        return "fragmented_groups", [f"{c[0]}{c[1]}[{a}:{b}]" for c, a, b in runs]
    return "looks_inferable", [f"{c[0]}{c[1]}[{a}:{b}]" for c, a, b in runs]


def dataset_tier(info: dict) -> tuple[str, str]:
    feats = info.get("features") if isinstance(info.get("features"), dict) else {}
    res = [(k, *feature_tier(feats, k)) for k in ("observation.state", "action")]
    worst = min((t for _, t, _ in res), key=TIERS.index)
    return worst, " | ".join(f"{k}: {t} {n}" for k, t, n in res)


def fetch_info(repo_id: str, sha: str, cache: Path, token: str | None) -> dict | None:
    """meta/info.json at the audited commit; 2 MB cap enforced on content-length and body."""
    from huggingface_hub import hf_hub_url

    from .checks import MAX_META_BYTES
    from .inspect_hub import UA, FetchError, _retry

    p = cache / f"{repo_id}.json"
    if p.exists():
        return json.loads(p.read_text())
    url = hf_hub_url(repo_id, "meta/info.json", repo_type="dataset", revision=sha)
    headers = {"User-Agent": UA, **({"Authorization": f"Bearer {token}"} if token else {})}

    def go():
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
            cl = r.headers.get("content-length")
            if cl is not None and int(cl) > MAX_META_BYTES:
                raise FetchError("oversize_body", "info.json over cap")
            body = r.read(MAX_META_BYTES + 1)
            if len(body) > MAX_META_BYTES:
                raise FetchError("oversize_body", "info.json over cap")
            return body
    try:
        info = json.loads(_retry(go, "info.json"))
    except (FetchError, ValueError, OSError) as e:
        print(f"  info.json unavailable for {repo_id}: {e}", file=sys.stderr)
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(info))
    time.sleep(0.2)
    return info


def goal6(df: pd.DataFrame, results: Path, offline: bool) -> tuple[str, pd.DataFrame]:
    lacking = df[(df.verdict != "NOT_LEROBOT") & (df.G6 == "fail")]
    cache, token = results / "info_cache", os.environ.get("HF_TOKEN")
    recs = []
    for r in lacking.itertuples():
        cached = (cache / f"{r.dataset}.json").exists()
        info = fetch_info(r.dataset, r.repo_sha, cache, token) if (cached or not offline) else None
        if info is None:
            recs.append({"dataset": r.dataset, "stratum": r.stratum, "tier": "info_unavailable", "notes": ""})
        else:
            tier, notes = dataset_tier(info)
            recs.append({"dataset": r.dataset, "stratum": r.stratum, "tier": tier, "notes": notes})
    g6 = pd.DataFrame(recs, columns=["dataset", "stratum", "tier", "notes"])
    g6.to_csv(results / "goal6_inferability.csv", index=False)

    rows = []
    for t in TIERS + ["info_unavailable"]:
        cells = [pct(int(((g6.stratum == s) & (g6.tier == t)).sum()), int((g6.stratum == s).sum())) for s in STRATA]
        if any(c != "0" for c in cells):
            rows.append([f"`{t}`", TIER_TEXT.get(t, "meta/info.json could not be fetched (counted, not dropped)")] + cells)
    tab = md_table(["tier", "meaning"] + [f"{s} (n={int((g6.stratum == s).sum())})" for s in STRATA], rows)
    bounds = []
    for s in STRATA:
        d = g6[(g6.stratum == s) & (g6.tier != "info_unavailable")]
        if len(d):
            bounds.append([s, len(d), pct(int((d.tier == "looks_inferable").sum()), len(d)),
                           pct(int(d.tier.isin(["opaque_names", "fragmented_groups", "looks_inferable"]).sum()), len(d))])
    tab2 = md_table(["stratum", "n lacking modality.json", "strict: looks_inferable",
                     "upper bound: names usable at all"], bounds)
    return tab + "\n" + tab2, g6


# ================================================================ chart

def chart(strat: dict[str, pd.DataFrame], path: Path, meta: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    xs = list(range(len(strat)))
    bottoms = [0.0] * len(strat)
    for v in VERDICT_ORDER:
        counts = [int((d.verdict_label == v).sum()) for d in strat.values()]
        if not any(counts):
            continue
        shares = [c / len(d) for c, d in zip(counts, strat.values())]
        ax.bar(xs, shares, 0.62, bottom=bottoms, color=COLORS[v], edgecolor=SURFACE, linewidth=2,
               hatch=HATCH.get(v), label=v)
        for x, sh, c, b in zip(xs, shares, counts, bottoms):
            if sh >= 0.035:
                ax.text(x, b + sh / 2, str(c), ha="center", va="center", fontsize=11, fontweight="bold",
                        color="#ffffff" if v in WHITE_TEXT else INK)
        bottoms = [b + s for b, s in zip(bottoms, shares)]
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{s}\nn={len(d)}" for s, d in strat.items()], color=INK, fontsize=12)
    ax.set_ylim(0, 1)
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], color=INK2, fontsize=11)
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(length=0)
    ax.set_title("Static conformance to Isaac-GR00T's dataset loader, by stratum\n(share of audited datasets; labels are counts)",
                 loc="left", color=INK, fontsize=14, pad=14)
    h, lab = ax.get_legend_handles_labels()
    ax.legend(h[::-1], lab[::-1], loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False,
              fontsize=11.5, labelcolor=INK2)
    fig.text(0.01, 0.01, meta, fontsize=9.5, color=INK2, ha="left", va="bottom")
    fig.subplots_adjust(left=0.07, right=0.70, bottom=0.25, top=0.86)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# ================================================================ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 4 report: results/raw -> summary.csv, report.md, chart")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--offline", action="store_true", help="goal 6: use only cached info.json")
    args = ap.parse_args(argv)
    results = Path(args.results)

    raw, errors = load_raw(results), load_errors(results)
    df = build_frame(raw)
    add_embodiment(df, results)
    strat = {s: df[df.stratum == s] for s in STRATA}
    shas = sorted(df.groot_sha.unique())
    assert len(shas) == 1, f"mixed GR00T pins in results/raw: {shas}"
    assert df.dataset.is_unique, "duplicate dataset rows"
    df.to_csv(results / "summary.csv", index=False)

    cont = df[df.verdict_label == "NOT_LEROBOT: container"]
    md: list[str] = []
    add = md.append
    add("# Conformance report: public LeRobot datasets vs Isaac-GR00T's dataset loader\n")
    add(f"GR00T pin `{shas[0][:7]}` · audit dates {', '.join(sorted(df.audit_date.unique()))} · "
        f"huggingface_hub {', '.join(sorted(df.huggingface_hub_version.unique()))} · "
        f"audited **{len(df)}** · excluded (fetch failures, outside the denominator) **{len(errors)}**"
        + (f" ({dict(collections.Counter(e['kind'] for e in errors))})" if errors else "") + "\n")
    add("**Every rate below is per stratum with its own n. There is no pooled pass rate.** "
        "S-curated is a census; S-popular and S-recent are purposive top-100 sets; only S-tail is a random "
        "sample (seed 20260928), so only S-tail carries a confidence interval. Verdicts are from **static metadata "
        "checks only**: no dataset was loaded with GR00T's loader, so `READY` means *passes all static checks*, "
        "not *GR00T-ready*. Individual datasets are not named in this report; ids are in `summary.csv`.\n")

    add("## 1. Distance-to-ready, per stratum (headline)\n")
    add(verdict_table(strat))
    add(f"\n**{DAGGER} unverified.** A FAIL-level check that could not run because its input exceeded the 2 MB cap "
        f"(`episodes.jsonl` / `tasks.jsonl`) or the file listing was capped is reported as skipped, not passed. "
        f"`READY{DAGGER}` is therefore *not* a clean pass, and the {DAGGER} count on every other row means that "
        f"row's distance is a **lower bound** (an unverified check can only add steps, never remove them). "
        f"Unverified datasets stay in their verdict row; none are moved or dropped.\n")
    add(f"**NOT_LEROBOT: container** = {len(cont)} multi-dataset repos whose LeRobot datasets sit in subfolders "
        f"({int(pd.to_numeric(cont.n_nested_found).sum())} sub-datasets found in total; a lower bound wherever the scan "
        f"was incomplete). Each is one row; **sub-datasets were not audited**, because that would change the sampling "
        f"unit from repo to dataset directory. `NOT_LEROBOT: other` are genuinely non-conforming.\n")
    add(f"Stacked `REPAIR` step (G14 fails on top of another verdict): {int(df.steps.str.contains('REPAIR').sum())} dataset(s).\n")
    tail = strat["S-tail"]
    k = int((tail.verdict == "NEEDS_DOWNCONVERT").sum())
    lo, hi = wilson(k, len(tail))
    add(f"S-tail (random sample) NEEDS_DOWNCONVERT: {k}/{len(tail)} = {k / len(tail):.1%}, 95% Wilson CI "
        f"[{lo:.1%}, {hi:.1%}]. No interval for the other strata: they are not random samples.\n")
    k2 = int(tail.clean_except_modality.sum())
    lo2, hi2 = wilson(k2, len(tail))
    add(f"S-tail passing every FAIL-level static check except `modality.json` (READY or NEEDS_MODALITY, no REPAIR): "
        f"{k2}/{len(tail)} = {k2 / len(tail):.1%}, 95% Wilson CI [{lo2:.1%}, {hi2:.1%}].\n")

    add("### Fix-cost for NEEDS_DOWNCONVERT\n")
    add(fixcost_table(strat))
    add("\n`used_storage_bytes` covers the whole repo including LFS history, so it **overstates** what "
        "`convert_v3_to_v2.py`'s `snapshot_download` pulls. Converter cost = full download + per-episode ffmpeg cut; "
        "it does not produce `modality.json`.\n")

    add("### Sensitivity: producer concentration\n")
    add(concentration(strat))
    pop = strat["S-popular"]
    rc = pop[pop.author.str.lower() != "robocoin"]
    add(f"\nS-popular with and without RoboCOIN (one producer's converter accounts for {len(pop) - len(rc)} of {len(pop)}):\n")
    add(verdict_table({"S-popular": pop, "S-popular excl. RoboCOIN": rc}))

    add("## 2. What fails besides the missing `modality.json`\n")
    add("`modality.json` is a GR00T-specific file that the LeRobot format does not define, so its absence is a gap "
        "between two formats rather than a dataset defect. This section sets it aside. Denominator: LeRobot-format "
        "datasets (NOT_LEROBOT excluded). Root causes are not exclusive; a dataset can have several.\n")
    add("### 2a. By root cause\n")
    add(beyond_modality(strat))
    add("\n### 2b. By check (every check except G6 and the checks that only run once `modality.json` exists), "
        "ranked by S-tail\n")
    add(failures_excluding_modality(strat))
    add("\n### 2c. Is it the kind of robot data GR00T targets?\n")
    add("Loading and fit are different questions. A dataset can pass every format check and still not be "
        "GR00T training data: GR00T N1.7 targets arms, bimanual setups, mobile manipulators and humanoids, so a "
        "well-formed car-driving or human-motion dataset is outside its scope. **Heuristic** "
        "(`conformance/embodiment.py`): `info.json:robot_type` first, then vehicle / human-motion feature names, "
        "then arm/body dimension names, then (weakest, robot categories only) the dataset name. It does not "
        "change any verdict. Denominator: LeRobot-format datasets.\n")
    add(embodiment_table(strat))
    add("\n### 2d. Top 5 FAIL-level failures overall (including `modality.json`), per stratum\n")
    add(top_failures(strat))
    add("\n`G2/G3/G7/G8/G9` share **one root cause** on a v3.0 layout (episodes.parquet / tasks.parquet / "
        "file-indexed paths), so they rank together; the `v3-style` column shows how much of each count is that. "
        "The independent non-v3 failure is `G6` (`modality.json` absent).\n")
    silent = df[df.silent_failure]
    add(f"**Silent failures** (G11/G12 fail while modality.json exists): {len(silent)} dataset(s)"
        + (" (" + ", ".join(r.stratum for r in silent.itertuples()) + ")" if len(silent) else "") + ".\n")
    add("Stats are reported separately because GR00T regenerates them at train time (WARN, not a verdict step):\n")
    add(stats_table(strat))

    add("## 3. codebase_version cross-tab and within-version schema drift\n")
    add(version_crosstabs(df, strat))
    add("\n**S-curated split** (does the maintainer's own namespace clear the contract?)\n")
    add(curated_split(df))
    add("\n**Within-version drift.** Same `codebase_version` string, different schema. Listed: attributes with >1 "
        "variant inside a version (data_path style always). Counts are datasets, not rates.\n")
    add(drift_table(df))

    add("## 4. Goal 6 - could `modality.json` be generated mechanically from `features.*.names`?\n")
    g6tab, g6 = goal6(df, results, args.offline)
    add("Population: LeRobot-format datasets **without** `modality.json` (G6 fails). `meta/info.json` re-read at each "
        "audited commit sha (cached in `results/info_cache/`). **Heuristic, not ground truth**: a dim name is "
        "recognised by a fixed keyword vocabulary (gripper / hand / joint / eef pos / eef rot / base / body, with "
        "left/right side); generic names like `joint_0`, `motor_3`, `0` count as opaque; `looks_inferable` also "
        "requires every group to be one contiguous range. Even `looks_inferable` yields only a *partition* - "
        "choosing group names that match an embodiment config still needs someone who knows the recipe. The "
        "generator is not built. Per-dataset tier and parsed partition: `results/goal6_inferability.csv`.\n")
    add(g6tab)

    add("## 5. Individual cases (repo ids omitted; see `summary.csv`)\n")
    add("**READY / READY†** (pass all static checks)\n")
    add(listing(df[df.verdict == "READY"], ["state_dim", "action_dim"]))
    add("\n**INCONSISTENT_MODALITY**\n")
    incon = df[df.verdict == "INCONSISTENT_MODALITY"]
    add(listing(incon, ["silent_failure"]))
    by_ds = {x["dataset"]: {c["id"]: c["detail"] for c in x["checks"]} for x in raw}
    for r in incon.itertuples():
        add(f"- {r.stratum}, {r.codebase_version}: G12: {by_ds[r.dataset]['G12']}; G13: {by_ds[r.dataset]['G13']}")
    add("\n**BLOCKED**. Most have no parquet under `data/` (metadata-only uploads: 0 bytes stored, often `eval_*` "
        "recording runs; one stores episodes in a different columnar format). Whether these are aborted recordings "
        "or deliberate is not established; the listed bytes are the discriminating facts.\n")
    add(listing(df[df.verdict == "BLOCKED"], ["parquet_gb_listed", "video_gb_listed", "repo_last_modified"]))
    add("\n**NOT_LEROBOT: container**\n")
    add(containers(df))

    add("## Reproduce\n")
    add("`.venv/bin/python scripts/reproduce.py` (or `.venv/bin/python -m conformance.report --offline` for this "
        "step alone). Inputs: "
        "`results/raw/**/*.json` and `results/errors/`. Only `meta/info.json` (<2 MB cap, pinned to the audited repo "
        "sha) is fetched, for goal 6.\n")
    (results / "report.md").write_text("\n".join(md))

    meta = (f"GR00T {shas[0][:7]} · audited {len(df)}, excluded {len(errors)} · {DAGGER} (hatched light blue) = READY but "
            f"G2/G3/G14 unverified (2 MB cap)\nhatched grey = multi-dataset containers, sub-datasets not audited · "
            f"S-curated = census; S-popular / S-recent = top-100 sets;\nS-tail = random sample. No pooled rate.")
    chart(strat, results / "conformance_chart.png", meta)
    print(f"wrote summary.csv ({len(df)} rows), report.md, goal6_inferability.csv ({len(g6)} rows), conformance_chart.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
