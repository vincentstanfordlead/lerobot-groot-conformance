#!/usr/bin/env python3
"""robot-data-smog-check: is this robot dataset ready to fine-tune NVIDIA Isaac GR00T, and pi0.5 (openpi)?

Runs the metadata checks from lerobot-groot-conformance where the data lives: the 28 GR00T loader
checks, openpi's loading rules, and the pi0.5 model-fit checks (P1-P8). Reads only meta/*.json(l)
and the file listing; never opens episode data or video; uploads nothing.

  smog_check.py check  <dataset-dir | hf-user/dataset>  [--model groot|pi05|all] [--draft] [--manifest] [--all] [--json | --plain]

The default output is a short Markdown diagnostic summary (always in English); --details gives the full
report with every check, --plain the older terminal text.
  smog_check.py verify <dataset-dir> [--manifest FILE] [--json]

Exit codes: 0 when the check ran, whatever the verdict (agents and shells read non-zero as "the command
failed"); 2 could not run. With --strict, for CI: check -> 1 unless every selected model is at its best state
(GR00T READY; pi0.5: files load and the data fits, so only the per-dataset config is left); verify -> 1 on a mismatch.
Python 3.9+. Local folders need only the standard library (and `packaging`, bundled in the packaged
skill, for pi0.5); a Hugging Face id also needs `pip install huggingface_hub`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _cand in (HERE, HERE.parent.parent.parent):  # bundled skill: scripts/conformance ; repo: <root>/conformance
    if (_cand / "conformance" / "checks.py").is_file():
        sys.path.insert(0, str(_cand))
        break
else:
    sys.exit("robot-data-smog-check: cannot find the conformance package next to this script")

from conformance import contract as C  # noqa: E402
from conformance import manifest as M  # noqa: E402
from conformance.checks import run_all  # noqa: E402
from conformance.draft import draft_modality, format_modality  # noqa: E402
from conformance.embodiment import classify  # noqa: E402
from conformance.explain import CHECKS, CONVERT, GROUPS, PI05_CHECKS, TONES, VERDICTS  # noqa: E402
from conformance.inspect_local import LocalView  # noqa: E402

try:  # pi0.5 needs `packaging` (version parsing, as openpi's LeRobot does)
    from conformance import models as Mo  # noqa: E402
    from conformance import pi05 as P  # noqa: E402
    PI05_ERR = None
except ImportError as e:  # pragma: no cover - depends on the environment
    Mo = P = None
    PI05_ERR = f"pi0.5 checks need the `packaging` module ({e}); run `pip install packaging`"

HF_ID = re.compile(r"^(?:https?://huggingface\.co/datasets/)?([\w.-]+/[\w.-]+?)/?$")
WIDTH = 96

PI05_LOAD = {
    "NEEDS_CONFIG": ("LOADS, NEEDS A CONFIG", "The files load in openpi. Like every dataset, it still needs a data config and norm stats."),
    "NEEDS_CONVERT": ("NEEDS CONVERTING", "It uses the LeRobot v3.0 layout; openpi's pinned LeRobot reads v2.x."),
    "NEEDS_TAG": ("NEEDS A VERSION TAG", "The files are in the right layout, but the repo has no version tag openpi's loader accepts."),
    "BLOCKED": ("BLOCKED", "Something in the files stops openpi's loader."),
    "UNASSESSED": ("NOT ASSESSED", "The repo's version tags could not be read."),
}
PI05_FIT = {"FIT": "fits pi0.5 defaults", "ADAPT": "fits with config changes", "NO_FIT": "does not fit pi0.5 as shipped",
            "UNASSESSED": "fit not assessed"}
PI05_STEPS = {
    "CONVERT": "Convert from LeRobot v3.0 to v2.1. GR00T's convert_v3_to_v2.py is the one converter known to do "
               "this; it has not been tested with openpi.",
    "STATS": "Add meta/episodes_stats.jsonl. openpi's LeRobot reads per-episode stats for v2.1 datasets; LeRobot's "
             "convert_dataset_v20_to_v21.py is the tool that writes them.",
    "TAG": 'Tag the repo with its codebase version, e.g. HfApi().create_tag(repo_id, tag="v2.1", repo_type="dataset"), '
           "or copy the dataset into LeRobot's cache and load it locally.",
    "REPAIR": "Some episode files listed in the metadata are missing; openpi's LeRobot would try to download them from the Hub.",
    "CONFIG": "Write an openpi data config and train config for this dataset.",
    "NORM_STATS": "Run openpi's scripts/compute_norm_stats.py for that config; training stops without the stats.",
}


class CountingView:
    """Wraps a DatasetView and records which files were read, so the report can say so."""

    def __init__(self, inner):
        self.inner, self.files = inner, inner.files
        self.listing_complete = getattr(inner, "listing_complete", True)
        self.read_log: dict[str, int] = {}

    def read_text(self, rel):
        text = self.inner.read_text(rel)
        if text is not None:
            self.read_log[rel] = len(text.encode())
        return text


def _info(view) -> dict | None:
    if "meta/info.json" not in view.files:
        return None
    try:
        t = view.read_text("meta/info.json")
        j = json.loads(t) if t else None
        return j if isinstance(j, dict) else None
    except ValueError:
        return None


def open_view(target: str):
    p = Path(target).expanduser()
    if p.is_dir():
        return CountingView(LocalView(p)), p, p.resolve().name, "local"
    m = HF_ID.match(target)
    if not m:
        raise SystemExit(f"robot-data-smog-check: {target!r} is not a directory or a Hugging Face dataset id")
    try:
        from conformance.inspect_hub import FetchError, HubView
    except ImportError:
        raise SystemExit("robot-data-smog-check: checking a Hugging Face id needs `pip install huggingface_hub`; "
                         "a local folder needs nothing")
    try:
        view = HubView(m.group(1), token=os.environ.get("HF_TOKEN"))
    except FetchError as e:
        raise SystemExit(f"robot-data-smog-check: could not read {m.group(1)} ({e.kind}): {e.detail}")
    return CountingView(view), None, m.group(1), "hub"


def hub_refs(repo_id: str) -> dict:
    try:
        from huggingface_hub import HfApi
        r = HfApi(token=os.environ.get("HF_TOKEN")).list_repo_refs(repo_id, repo_type="dataset")
        return {"branches": [[b.name, b.target_commit] for b in r.branches],
                "tags": [[t.name, t.target_commit] for t in r.tags]}
    except Exception as e:  # noqa: BLE001 - any failure means "could not read the refs"
        return {"error": str(e).splitlines()[0]}


# ---------------------------------------------------------------- assessments

def assess_pi05(report, info, name, mode) -> dict:
    fit = Mo.pi05_fit(info)
    load = P.local_load_verdict(report, info) if mode == "local" else P.hub_load_verdict(report, info, hub_refs(name))
    plan = P.plan(info, name, name if mode == "hub" else None, fit)
    return {"load": load, "fit": {k: fit[k] for k in ("verdict", "checks", "issues", "reason") if k in fit}, "plan": plan}


def groot_steps(report: dict, draft: dict | None, draft_path: Path | None) -> list[str]:
    by = {c["id"]: c for c in report["checks"]}
    failed = lambda ids: [i for i in ids if i in by and by[i]["passed"] is False]  # noqa: E731
    out: list[str] = []
    steps = report["steps"]
    if "BLOCKED" in steps:
        seen = set()
        for i in failed(["L3"] + [f"G{n}" for n in range(1, 17) if n not in (4, 5, 6, 10, 11, 12, 13, 14)]):
            fix = CHECKS[i][1]
            if fix not in seen:
                seen.add(fix)
                out.append(f"{CHECKS[i][0]} ({i}): {by[i]['detail']}\n{fix}")
    if "DOWNCONVERT" in steps:
        out.append("Convert from the LeRobot v3.0 layout to v2, which GR00T reads today.\n" + CONVERT)
    if "MODALITY" in steps:
        s = "Add meta/modality.json: which numbers in state/action are the arm, the gripper, and so on."
        if draft and draft.get("ok"):
            gs = "; ".join(f"{sec}: " + ", ".join(f"{g['name']} [{g['start']}:{g['end']}]" for g in draft["groups"][sec])
                           for sec in ("state", "action"))
            where = f"saved to {draft_path}" if draft_path else "printed below"
            s += (f"\nA draft is ready ({where}). Groups: {gs}."
                  "\nConfirm the gripper index against the robot before copying it to meta/modality.json; "
                  "a wrong index trains silently on the wrong joints.")
        elif draft:
            s += f"\nCan't draft it automatically. {draft['reason']}"
        else:
            s += "\nRun again with --draft to have one proposed from the dimension names."
        out.append(s)
    if "INCONSISTENT_MODALITY" in steps:
        for i in failed(["G10", "G11", "G12", "G13"]):
            out.append(f"{CHECKS[i][0]} ({i}): {by[i]['detail']}\n{CHECKS[i][1]}")
    if "REPAIR" in steps:
        out.append(f"{CHECKS['G14'][0]} (G14): {by['G14']['detail']}\n{CHECKS['G14'][1]}")
    return out


def pi05_steps(pi: dict, plan_path: Path | None) -> list[str]:
    load, fit = pi["load"], pi["fit"]
    out = []
    if load["verdict"] == "BLOCKED" and not load["steps"]:
        out.append(f"Fix first: {load['reason']}.")
    for s in load["steps"]:
        text = PI05_STEPS[s]
        if s == "CONFIG":
            if pi["plan"] and plan_path:
                text += f"\nA plan is ready ({plan_path}): camera slots, keys, action horizon and the commands."
            elif pi["plan"]:
                text += "\nRun again with --draft for a plan drafted from info.json."
        out.append(text)
    if fit["verdict"] in ("ADAPT", "NO_FIT"):
        by = {c["id"]: c for c in fit["checks"]}
        word = "Change in the config" if fit["verdict"] == "ADAPT" else "Blocks pi0.5 as shipped"
        out.append(f"{word}:\n" + "\n".join(f"  - {by[i]['detail']}" for i in fit["issues"]))
    return out


def pi05_best(pi: dict) -> bool:
    return pi["load"]["verdict"] == "NEEDS_CONFIG" and pi["fit"]["verdict"] == "FIT"


# ---------------------------------------------------------------- report

def _wrap(s, first="    ", rest=None):
    return textwrap.fill(s, WIDTH, initial_indent=first, subsequent_indent=rest if rest is not None else " " * len(first))


def _numbered(lines, steps):
    for n, s in enumerate(steps, 1):
        first, *rest = s.split("\n")
        lines.append(_wrap(first, f"  {n}. "))
        for r in rest:
            lines.append(("     " + r) if r.startswith("  ") else _wrap(r, "     "))


def render(report, info, read_log, name, mode, models, draft, draft_path, pi, plan_path, manifest_path, show_all) -> str:
    checks = report["checks"]
    emb = classify(info, name) if info else None
    lines = []
    if info:
        feats = info.get("features") if isinstance(info.get("features"), dict) else {}
        cams = sum(isinstance(f, dict) and f.get("dtype") == "video" for f in feats.values())
        bits = [f"{info.get('total_episodes', '?')} episodes", f"{info.get('fps', '?')} fps",
                f"{cams} camera{'s' if cams != 1 else ''}", f"LeRobot {info.get('codebase_version', '?')}"]
        lines.append(f"Dataset   {name} · " + " · ".join(bits))
        fit = {"fits": "a fit for these models", "outside": "LIKELY OUTSIDE what these models are built for",
               "unclear": "can't tell"}[emb["fit"]]
        lines.append(f"Robot     {emb['label']}: {fit} ({emb['evidence']})")
    else:
        lines.append(f"Dataset   {name}")
    kb = sum(read_log.values()) / 1024
    where = "on this machine; nothing was uploaded" if mode == "local" else "from the Hugging Face Hub (metadata only)"
    lines.append(f"Read      {len(read_log)} metadata file{'s' if len(read_log) != 1 else ''} ({kb:.1f} KB) {where}. "
                 "No episode data or video was opened.")

    if "groot" in models:
        v = report["verdict"]
        tag, headline, sub = VERDICTS[v]
        n_pass = sum(c["passed"] is True for c in checks)
        n_fail = sum(c["passed"] is False for c in checks)
        n_skip = sum(c["passed"] is None for c in checks)
        lines.append("")
        lines.append(f"GR00T: {tag}" + ("" if tag == v else f"  [{v}]") + f"  {headline}")
        lines.append(_wrap(sub, "  "))
        lines.append(f"  {len(checks)} loader checks against Isaac-GR00T @{C.GROOT_SHA[:7]}: "
                     f"{n_pass} pass, {n_fail} fail, {n_skip} skipped")
        steps = groot_steps(report, draft, draft_path)
        if steps:
            lines.append("  Next steps")
            _numbered(lines, steps)
        in_steps = {c["id"] for c in checks if c["passed"] is False and c["level"] == "FAIL"}
        warns = [c for c in checks if c["passed"] is False and c["level"] == "WARN" and c["id"] not in in_steps]
        if warns:
            lines.append("  Warnings (won't stop training)")
            for c in warns:
                lines.append(_wrap(f"{c['id']} {CHECKS[c['id']][0]}: {CHECKS[c['id']][1]}", "  - "))
        if report.get("unverified_size"):
            lines.append(_wrap(f"Not verified (a metadata file is over the 2 MB read cap): "
                               f"{', '.join(report['unverified_size'])}. The verdict is a lower bound on the work left.", "  "))

    if "pi05" in models:
        lines.append("")
        if pi is None:
            lines.append(f"pi0.5 (openpi): not checked. {PI05_ERR}")
        else:
            lv, fv = pi["load"]["verdict"], pi["fit"]["verdict"]
            label, sub = PI05_LOAD[lv]
            lines.append(f"pi0.5 (openpi): {label} · {PI05_FIT[fv]}  [{lv} / {fv}]")
            lines.append(_wrap(sub if lv != "BLOCKED" else f"{sub} {pi['load']['reason']}.", "  "))
            lines.append(f"  openpi @{Mo.OPENPI_SHA[:7]} via LeRobot @{Mo.OPENPI_LEROBOT_SHA[:7]}; "
                         + ("loaded locally, so no Hub version tag is needed" if mode == "local" else "loaded from the Hub by repo id"))
            steps = pi05_steps(pi, plan_path)
            if steps:
                lines.append("  Next steps")
                _numbered(lines, steps)

    if any(c["id"] == "L9" and c["passed"] is False for c in checks):
        lines.append("\nTip")
        lines.append(_wrap(CHECKS["L9"][1], "  "))
    if emb and emb["fit"] == "outside":
        lines.append("\nNote: the files may load, but this does not look like robot manipulation data, "
                     "which is what these models are built for.")
    if draft and draft.get("ok") and not draft_path:
        lines.append("\nDraft meta/modality.json (proposal; confirm before using)")
        lines.append(textwrap.indent(format_modality(draft["draft"]).rstrip(), "  "))
    if pi and pi.get("plan") and pi.get("plan_text") and not plan_path:
        lines.append("\n" + pi["plan_text"].rstrip())
    if manifest_path:
        lines.append(f"\nManifest  wrote {manifest_path}. Ship it with the dataset; the receiver runs "
                     f"`smog_check.py verify <dataset>` to confirm what arrived matches.")
    if show_all:
        lines.append("\nAll GR00T checks")
        for c in checks:
            mark = {True: "pass", False: c["level"], None: "skip"}[c["passed"]]
            lines.append(f"  {c['id']:<4}{mark:<5} {CHECKS[c['id']][0]}: {c['detail']}")
            if c.get("source"):
                lines.append(f"            source: Isaac-GR00T @{C.GROOT_SHA[:7]} {c['source']}")
        if pi:
            lines.append("\nAll pi0.5 fit checks")
            for c in pi["fit"]["checks"]:
                lines.append(f"  {c['id']:<4}{c['status']:<6} {c['detail']}")
    lines.append("")
    lines.append(_wrap("Static checks only: passing means the loader can read the data and its shape fits the model, "
                       "not that it trains well. Only training on it tells you that.", ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- Markdown report (the default)

ICON = {"good": "✅", "close": "🟡", "bad": "❌", "skip": "⚪"}
PI05_LOAD_MD = {
    "NEEDS_CONFIG": ("good", "Loads", "the files load; like every dataset, it needs an openpi config and norm stats"),
    "NEEDS_CONVERT": ("bad", "Needs converting", "LeRobot v3.0 layout; openpi's pinned LeRobot reads v2.x"),
    "NEEDS_TAG": ("close", "Needs a version tag", "right layout, but no version tag openpi's loader accepts"),
    "BLOCKED": ("bad", "Blocked", None),
    "UNASSESSED": ("bad", "Not assessed", "the repo's version tags could not be read"),
}
PI05_FIT_MD = {"FIT": ("good", "Fits", "matches pi0.5's defaults; the config only renames keys"),
               "ADAPT": ("close", "Fits with config changes", "the config has to do more than rename keys"),
               "NO_FIT": ("bad", "Doesn't fit", "pi0.5 as shipped can't train on it without changing the data"),
               "UNASSESSED": ("bad", "Not assessed", "info.json could not be read")}
FIT_TONE = {"OK": "good", "NOTE": "good", "ADAPT": "close", "FAIL": "bad"}


def _md(s: str) -> str:
    """Plain step text -> Markdown: file and command names in backticks, indented command lines as code."""
    out = []
    for line in s.split("\n"):
        if line.startswith("  ") and not line.lstrip().startswith("- "):
            out.append(f"`{line.strip()}`")
        else:
            line = re.sub(r"(?<![`\w/.~-])((?:[~\w.-]*/)*[\w.-]+\.(?:json|jsonl|py|parquet|md)|scripts/[\w/.-]+|--[a-z][\w-]*)(?![`\w])",
                          r"`\1`", line)
            out.append(re.sub(r"(?<!`)\b(\w+ \[\d+:\d+\])", r"`\1`", line))  # modality groups: single_arm [0:5]
    return out


def _steps_md(steps: list[str]) -> list[str]:
    lines = []
    for n, s in enumerate(steps, 1):
        first, *rest = _md(s)
        lines.append(f"{n}. {first}")
        lines += [f"   {r}" if not r.startswith("  - ") else f"   {r.strip()}" for r in rest]
    return lines


def pi05_overall(pi: dict) -> tuple[str, str]:
    lv, fv = pi["load"]["verdict"], pi["fit"]["verdict"]
    if pi05_best(pi):
        return "good", "Ready to configure"
    if lv in ("BLOCKED", "NEEDS_CONVERT", "UNASSESSED") or fv in ("NO_FIT", "UNASSESSED"):
        return "bad", {"NEEDS_CONVERT": "Needs converting", "BLOCKED": "Blocked"}.get(lv, PI05_FIT_MD[fv][1] if fv in ("NO_FIT", "UNASSESSED") else "Not assessed")
    return "close", "Needs a version tag" if lv == "NEEDS_TAG" else "Fits with config changes"


def _first_step(steps: list[str]) -> str:
    """The first step's lead clause, short enough for a table cell."""
    if not steps:
        return "Nothing blocks training"
    s = re.split(r": |\. |; |, which ", _md(steps[0])[0])[0].rstrip(":.")
    return s + (f" (+{len(steps) - 1} more)" if len(steps) > 1 else "")


def _label(v: str) -> str:
    """GR00T verdict as the web app says it: One step away, Two steps away, Ready, ..."""
    return VERDICTS[v][0].capitalize().replace("Modality.json", "modality.json").replace("lerobot", "LeRobot")


def _names(cs: list[dict]) -> str:
    names = [CHECKS[c["id"]][0] for c in cs]
    return ", ".join(names[:2]) + (f" (+{len(names) - 2} more)" if len(names) > 2 else "")


# π0.5's eight fit checks, grouped into areas for the summary
PI05_AREAS = [("Actions & state", ["P1", "P2", "P3"]), ("Cameras", ["P4", "P5"]),
              ("Frame rate & episode length", ["P6", "P7"]), ("Task prompt", ["P8"])]


def _problem(cs: list[dict], layout_v3: bool) -> str:
    """What is wrong in an area, short: "meta/modality.json missing", "LeRobot v3.0 layout; GR00T reads v2"."""
    if layout_v3 and any(c["id"] in ("G2", "G3", "G7", "G9") for c in cs):
        return "LeRobot v3.0 layout; GR00T reads v2"
    out = []
    for c in cs:
        t = CHECKS[c["id"]][0]
        m = re.match(r"(?:Has|Ships) (.+?)(?: with .*)?$", t)
        out.append(f"`{m.group(1)}` missing" if m and m.group(1).startswith("meta/") else
                   (f"{m.group(1)} missing" if m else f"not met: {t[0].lower() + t[1:]}"))
    return "; ".join(out[:2]) + (f" (+{len(out) - 2} more)" if len(out) > 2 else "")


def _area(icon_tone: str, title: str, why: str = "") -> str:
    return f"- {ICON[icon_tone]} {title}" + (f" — {why}" if why else "")


def render_summary(report, info, read_log, name, mode, models, draft, draft_path, pi, plan_path, manifest_path) -> str:
    """The default: the dataset table and, per model, its verdict, a checkbox per area and the next step."""
    checks = report["checks"]
    by = {c["id"]: c for c in checks}
    L = _head_md(info, read_log, name, mode)
    if "groot" in models:
        v = report["verdict"]
        steps = groot_steps(report, draft, draft_path)
        n_pass = sum(c["passed"] is True for c in checks)
        L += ["", f"### GR00T N1.7 · {ICON[TONES[v]]} {_label(v)}", f"_{n_pass} of {len(checks)} loader checks pass_", ""]
        for title, ids in GROUPS:
            cs = [by[i] for i in ids if i in by]
            fails = [c for c in cs if c["passed"] is False and c["level"] == "FAIL"]
            warns = [c for c in cs if c["passed"] is False and c["level"] != "FAIL"]
            v3 = "DOWNCONVERT" in report["steps"]
            if fails:
                L.append(_area("bad", title, _problem(fails, v3)))
            elif warns:
                L.append(_area("close", title, _problem(warns, v3) + " (optional)"))
            elif cs and all(c["passed"] is None for c in cs):
                L.append(_area("skip", title, "checked after the fixes above"))
            else:
                L.append(_area("good", title))
        L += ["", f"**Next:** {_first_step(steps)}" + (" · draft saved" if draft_path else "")]
    if "pi05" in models:
        if pi is None:
            L += ["", "### π0.5 (openpi) · ⚪ Not checked", PI05_ERR]
        else:
            t, label = pi05_overall(pi)
            lv = pi["load"]["verdict"]
            lt, llabel, ldetail = PI05_LOAD_MD[lv]
            fby = {c["id"]: c for c in pi["fit"]["checks"]}
            n_ok = sum(c["status"] in ("OK", "NOTE") for c in pi["fit"]["checks"])
            L += ["", f"### π0.5 (openpi) · {ICON[t]} {label}",
                  f"_{n_ok} of {len(pi['fit']['checks'])} model-fit checks pass_" if fby else "", ""]
            L.append(_area(lt, "Loads in openpi", "" if lv == "NEEDS_CONFIG" else (llabel.lower() if ldetail else pi["load"]["reason"])))
            for title, ids in PI05_AREAS:
                cs = [fby[i] for i in ids if i in fby]
                if not cs:
                    continue
                worst = max(cs, key=lambda c: {"OK": 0, "NOTE": 0, "ADAPT": 1, "FAIL": 2}[c["status"]])
                tone = FIT_TONE[worst["status"]]
                L.append(_area(tone, title, "" if tone == "good" else
                               ("change in the config" if tone == "close" else "doesn't fit as shipped")))
            steps = pi05_steps(pi, plan_path)
            L += ["", f"**Next:** {_first_step(steps)}" + (" · plan saved" if plan_path else "")]
    if manifest_path:
        L += ["", f"Manifest written: `{manifest_path}`"]
    L += ["", "---", "_Static checks on metadata only: passing means the loader can read the files and the shape fits, "
          "not that it trains well. Run with `--details` for every check and step-by-step fixes._"]
    return "\n".join(x for x in L if x is not None)


def _head_md(info, read_log, name, mode) -> list[str]:
    emb = classify(info, name) if info else None
    L = [f"# Dataset diagnostic report: {name}", "", "| | |", "|---|---|"]
    if info:
        feats = info.get("features") if isinstance(info.get("features"), dict) else {}
        cams = sum(isinstance(f, dict) and f.get("dtype") == "video" for f in feats.values())
        L.append(f"| **Dataset** | `{name}` · LeRobot {info.get('codebase_version', '?')} · {info.get('total_episodes', '?')} episodes · "
                 f"{info.get('fps', '?')} fps · {cams} camera{'s' if cams != 1 else ''} |")
        icon, verdict = {"fits": ("✅", ": a fit for these models"), "unclear": ("⚪", ""),
                         "outside": ("❌", ": likely outside what these models are built for")}[emb["fit"]]
        # robot_type='so100' -> `robot_type: so100`; other evidence (feature or dimension names) stays as text
        ev = re.sub(r"robot_type=(['\"])(.*?)\1", r"`robot_type: \2`", emb["evidence"])
        L.append(f"| **Robot** | {icon} {emb['label']} ({ev}){verdict} |")
    else:
        L.append(f"| **Dataset** | `{name}` |")
    kb = sum(read_log.values()) / 1024
    where = "on this machine" if mode == "local" else "from the Hugging Face Hub"
    L.append(f"| **Privacy** | Read {len(read_log)} metadata file{'s' if len(read_log) != 1 else ''} ({kb:.1f} KB) {where}. "
             f"No episode data or video opened{'; nothing uploaded' if mode == 'local' else ''}. |")
    return L


def render_md(report, info, read_log, name, mode, models, draft, draft_path, pi, plan_path, manifest_path, show_all) -> str:
    checks = report["checks"]
    by = {c["id"]: c for c in checks}
    emb = classify(info, name) if info else None
    L = _head_md(info, read_log, name, mode)

    g_steps = groot_steps(report, draft, draft_path) if "groot" in models else []
    p_steps = pi05_steps(pi, plan_path) if pi else []

    # ---- summary: one row per model, like the web app's overview
    L += ["", "## Summary", "", "| Model | Result | First thing to do |", "|---|---|---|"]
    if "groot" in models:
        v = report["verdict"]
        L.append(f"| **GR00T N1.7** | {ICON[TONES[v]]} {_label(v)} | {_first_step(g_steps)} |")
    if "pi05" in models:
        if pi is None:
            L.append(f"| **π0.5** (openpi) | ⚪ Not checked | {PI05_ERR} |")
        else:
            t, label = pi05_overall(pi)
            L.append(f"| **π0.5** (openpi) | {ICON[t]} {label} | {_first_step(p_steps)} |")

    # ---- GR00T
    if "groot" in models:
        v = report["verdict"]
        n_pass = sum(c["passed"] is True for c in checks)
        L += ["", "---", "", f"## GR00T N1.7 · {ICON[TONES[v]]} {_label(v)}", "", f"**{VERDICTS[v][1]}.** " + " ".join(_md(VERDICTS[v][2])), ""]
        L += [f"**{n_pass} of {len(checks)} loader checks pass** (Isaac-GR00T @`{C.GROOT_SHA[:7]}`)", "",
              "| Area | Passed | Status |", "|---|---|---|"]
        for title, ids in GROUPS:
            cs = [by[i] for i in ids if i in by]
            ok = sum(c["passed"] is True for c in cs)
            fails = [c for c in cs if c["passed"] is False and c["level"] == "FAIL"]
            warns = [c for c in cs if c["passed"] is False and c["level"] != "FAIL"]
            skips = sum(c["passed"] is None for c in cs)
            if fails:
                status = "❌ " + _names(fails)
            elif warns:
                status = "🟡 " + _names(warns)
            elif ok == 0 and skips:
                status = "⚪ skipped until the above is fixed"
            else:
                status = "✅"
            L.append(f"| {title} | {ok}/{len(cs)}{f' · {skips} skipped' if skips else ''} | {status} |")
        if g_steps:
            L += ["", "**What's needed**", ""] + _steps_md(g_steps)
        in_steps = {c["id"] for c in checks if c["passed"] is False and c["level"] == "FAIL"}
        warns = [c for c in checks if c["passed"] is False and c["level"] == "WARN" and c["id"] not in in_steps]
        if warns:
            L += ["", "**Optional** (won't stop training)", ""]
            L += [f"- {CHECKS[c['id']][0]}: " + " ".join(_md(CHECKS[c["id"]][1])) for c in warns]
        if report.get("unverified_size"):
            L += ["", f"> Not verified: {', '.join(report['unverified_size'])} is over the 2 MB read cap, "
                      "so there may be more to fix."]

    # ---- π0.5
    if "pi05" in models and pi is not None:
        lv, fv = pi["load"]["verdict"], pi["fit"]["verdict"]
        t, label = pi05_overall(pi)
        lt, llabel, ldetail = PI05_LOAD_MD[lv]
        ft, flabel, fdetail = PI05_FIT_MD[fv]
        ldetail = ldetail or pi["load"]["reason"]
        src = "loaded locally, so no Hub version tag is needed" if mode == "local" else "loaded from the Hub by repo id"
        L += ["", "---", "", f"## π0.5 (openpi) · {ICON[t]} {label}", "",
              "| Question | Result |", "|---|---|",
              f"| Can openpi load the files? | {ICON[lt]} **{llabel}**: {ldetail} |",
              f"| Does the data fit π0.5? | {ICON[ft]} **{flabel}**: {fdetail} |", ""]
        if pi["fit"]["checks"]:
            n_ok = sum(c["status"] in ("OK", "NOTE") for c in pi["fit"]["checks"])
            L += [f"**{n_ok} of {len(pi['fit']['checks'])} model-fit checks pass** (openpi @`{Mo.OPENPI_SHA[:7]}`, {src})", "",
                  "| Check | Status | Detail |", "|---|---|---|"]
            for c in pi["fit"]["checks"]:
                L.append(f"| {PI05_CHECKS.get(c['id'], c['id'])} | {ICON[FIT_TONE[c['status']]]} | {c['detail']} |")
        if p_steps:
            L += ["", "**What's needed**", ""] + _steps_md(p_steps)

    # ---- extras
    if any(c["id"] == "L9" and c["passed"] is False for c in checks):
        L += ["", f"> **Tip:** {CHECKS['L9'][1]}"]
    if emb and emb["fit"] == "outside":
        L += ["", "> **Note:** the files may load, but this does not look like robot manipulation data, "
                  "which is what these models are built for."]
    if draft and draft.get("ok") and not draft_path:
        L += ["", "**Draft `meta/modality.json`** (a proposal: confirm before using)", "", "```json",
              format_modality(draft["draft"]).rstrip(), "```"]
    if pi and pi.get("plan") and pi.get("plan_text") and not plan_path:
        L += ["", pi["plan_text"].rstrip()]
    if manifest_path:
        L += ["", f"> **Manifest written:** `{manifest_path}`. Ship it with the dataset; the receiver runs "
                  "`smog_check.py verify <dataset>` to confirm what arrived matches."]
    if show_all:
        L += ["", "<details><summary>All GR00T checks</summary>", "", "| ID | Check | Result | Detail |", "|---|---|---|---|"]
        for c in checks:
            mark = {True: "✅", False: "❌" if c["level"] == "FAIL" else "🟡", None: "⚪"}[c["passed"]]
            L.append(f"| {c['id']} | {CHECKS[c['id']][0]} | {mark} | {c['detail']} |")
        L += ["", "</details>"]
    L += ["", "---", "",
          "_Static checks on metadata only. Passing means the loader can read the files and the data's shape fits the model, "
          "not that it trains well._"]
    return "\n".join(L)


# ---------------------------------------------------------------- commands

def _models(arg: str) -> tuple[str, ...]:
    return ("groot", "pi05") if arg == "all" else (arg,)


def cmd_check(a) -> int:
    models = _models(a.model)
    view, root, name, mode = open_view(a.target)
    report = run_all(view)
    info = _info(view)
    pi = assess_pi05(report, info, name, mode) if "pi05" in models and P is not None else None
    draft = draft_path = plan_path = manifest_path = None
    if a.draft and "groot" in models and "MODALITY" in report["steps"]:
        draft = draft_modality(info)
        if draft["ok"] and (a.draft_out or root is not None):
            draft_path = Path(a.draft_out) if a.draft_out else root / M.DRAFT_NAME
            draft_path.write_text(format_modality(draft["draft"]))
    if a.draft and pi and pi["plan"]:
        pi["plan_text"] = P.format_plan(pi["plan"], name, mode == "local")
        if root is not None:
            plan_path = root / M.PLAN_NAME
            plan_path.write_text(pi["plan_text"])
    man = None
    if a.manifest:
        if root is None:
            raise SystemExit("robot-data-smog-check: --manifest needs a local dataset folder (a Hub repo is already pinned by its commit)")
        extra = {"pi05": {"load": pi["load"]["verdict"], "fit": pi["fit"]["verdict"]}} if pi else {}
        man = M.build(root, report, info, view.files, models=extra)
        manifest_path = Path(a.manifest_out) if a.manifest_out else root / M.MANIFEST_NAME
        M.write(manifest_path, man)
    best = all(report["verdict"] == "READY" if m == "groot" else (pi is not None and pi05_best(pi)) for m in models)
    if a.json:
        out = {"dataset": name, "mode": mode, "models": list(models), "groot_commit": C.GROOT_SHA, **report,
               "metadata_files_read": dict(sorted(view.read_log.items())),
               "next_steps": groot_steps(report, draft, draft_path) if "groot" in models else []}
        if "pi05" in models:
            out["pi05"] = None if pi is None else {**{k: v for k, v in pi.items() if k != "plan_text"},
                                                   "next_steps": pi05_steps(pi, plan_path),
                                                   "plan_path": str(plan_path) if plan_path else None,
                                                   "openpi_commit": Mo.OPENPI_SHA}
            if pi is None:
                out["pi05_error"] = PI05_ERR
        if draft is not None:
            out["draft_modality"] = {**draft, "path": str(draft_path) if draft_path else None}
        if man is not None:
            out["manifest"] = {"path": str(manifest_path), **man}
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    else:
        args = (report, info, view.read_log, name, mode, models, draft, draft_path, pi, plan_path, manifest_path)
        if a.plain:
            print(render(*args, a.all))
        elif a.details or a.all:
            print(render_md(*args, a.all))
        else:
            print(render_summary(*args))
    return 0 if best or not a.strict else 1


def cmd_verify(a) -> int:
    root = Path(a.target).expanduser()
    if not root.is_dir():
        raise SystemExit(f"robot-data-smog-check: {a.target!r} is not a directory")
    mpath = Path(a.manifest) if a.manifest else root / M.MANIFEST_NAME
    if not mpath.is_file():
        raise SystemExit(f"robot-data-smog-check: no manifest at {mpath}")
    try:
        old = M.read(mpath)
    except ValueError as e:
        raise SystemExit(f"robot-data-smog-check: {mpath} does not parse: {e}")
    view = CountingView(LocalView(root))
    report = run_all(view)
    info = _info(view)
    extra = {}
    if "pi05" in (old.get("models") or {}) and P is not None:
        pi = assess_pi05(report, info, root.resolve().name, "local")
        extra = {"pi05": {"load": pi["load"]["verdict"], "fit": pi["fit"]["verdict"]}}
    new = M.build(root, report, info, view.files, models=extra)
    diffs = M.compare(old, new)
    d = new["dataset"]
    if a.json:
        print(json.dumps({"verified": not diffs, "differences": diffs, "manifest": str(mpath),
                          "verdict": new["result"]["verdict"], "models": new.get("models", {}), "dataset": d},
                         indent=2, ensure_ascii=False))
    else:
        hours = f" · {d['hours']} h" if d.get("hours") else ""
        if diffs:
            print(f"NOT VERIFIED: {root.name} does not match {mpath.name}")
            for x in diffs:
                print(f"  - {x}")
        else:
            print(f"VERIFIED: {root.name} matches {mpath.name}")
        pi_s = f" · pi0.5 {new['models']['pi05']['load']}/{new['models']['pi05']['fit']}" if "pi05" in new.get("models", {}) else ""
        print(f"  GR00T {new['result']['verdict']}{pi_s} · {d.get('total_episodes')} episodes{hours} · "
              f"{new['fingerprint']['n_files']} files")
        print("  Checked here from metadata and the file listing; episode and video payloads are not hashed.")
    return 1 if diffs and a.strict else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="smog_check.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check a local dataset folder or a Hugging Face dataset id")
    c.add_argument("target")
    c.add_argument("--model", choices=("all", "groot", "pi05"), default="all",
                   help="which model to check for: GR00T, pi0.5 (openpi), or both (default)")
    c.add_argument("--draft", action="store_true",
                   help=f"propose GR00T's meta/modality.json and a pi0.5 config plan "
                        f"(saved as <dataset>/{M.DRAFT_NAME} and <dataset>/{M.PLAN_NAME})")
    c.add_argument("--draft-out", help="where to save the modality.json draft")
    c.add_argument("--manifest", action="store_true", help=f"write a conformance manifest (default: <dataset>/{M.MANIFEST_NAME})")
    c.add_argument("--manifest-out", help="where to write the manifest")
    c.add_argument("--all", action="store_true", help="list every check with its source")
    c.add_argument("--json", action="store_true", help="machine-readable output")
    c.add_argument("--details", action="store_true", help="the full report: every check and step-by-step fixes")
    c.add_argument("--plain", action="store_true", help="plain terminal text instead of the Markdown report")
    c.add_argument("--strict", action="store_true", help="exit 1 unless every selected model is at its best state (for CI)")
    v = sub.add_parser("verify", help="re-check a dataset folder against the manifest that came with it")
    v.add_argument("target")
    v.add_argument("--manifest", help=f"manifest file (default: <dataset>/{M.MANIFEST_NAME})")
    v.add_argument("--json", action="store_true")
    v.add_argument("--strict", action="store_true", help="exit 1 on a mismatch (for CI)")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("check", "verify", "-h", "--help"):
        argv = ["check"] + argv  # `smog_check.py <path>` means check
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    try:
        return cmd_check(a) if a.cmd == "check" else cmd_verify(a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
