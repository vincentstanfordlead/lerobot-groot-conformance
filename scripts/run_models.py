"""LeRobot-native and openpi columns from the stored audit (no network, no re-audit).

Reads results/raw/ (audit records), results/info_cache/ (info.json at the audited sha) and
results/refs_cache/ (Hub branches/tags, fetched by scripts/fetch_refs.py), applies
conformance/models.py, and writes

    results/models.csv         one row per audited dataset: GR00T verdict + the two new columns
    results/report_models.md   per-stratum tables with n; never a pooled rate

    .venv/bin/python scripts/run_models.py [--results results]
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import models as M  # noqa: E402
from conformance.report import STRATA, load_raw, md_table, pct, verdict_label, wilson  # noqa: E402

ORDER = {
    "lerobot": ["PASS", "NEEDS_TAG", "NEEDS_CONVERT", "BLOCKED"],
    "openpi": ["NEEDS_CONFIG", "NEEDS_TAG", "NEEDS_CONVERT", "BLOCKED"],
}
MEANING = {
    "PASS": "loader picks a v3.0 ref and the v3 meta files are there",
    "NEEDS_CONFIG": "files load; a data config and norm stats are still to be written (never PASS)",
    "NEEDS_TAG": "right layout, but no version-named ref the loader accepts: one `create_tag`",
    "NEEDS_CONVERT": "data is in the other layout (v2 for LeRobot, v3 for openpi)",
    "BLOCKED": "no episodes, not LeRobot, a required meta file missing, or no tool for the version",
    "FIT": "fits π0.5 defaults: the data config only renames keys",
    "ADAPT": "fits once the config (or one model setting) does more: see the checks below",
    "NO_FIT": "π0.5 as shipped cannot train on it (too-wide action/state, no action, no RGB camera, no fps)",
}
PI05_CHECKS = {
    "P1": "action is one float vector",
    "P2": "action dim <= 32",
    "P3": "state is one float vector, dim <= 32",
    "P4": "1-3 RGB cameras (3 image slots)",
    "P5": "camera size vs 224x224 (resize with padding)",
    "P6": "fps vs the 50-step action chunk",
    "P7": "episodes at least one chunk long",
    "P8": "task strings for the prompt",
}
TAG_LANDSCAPE = ["no version ref", "v3.0 only", "v2.x only", "v2.x and v3.0", "other"]


def load_json(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def tag_landscape(refs: dict | None) -> str:
    if refs is None or "error" in refs:
        return ""
    vs = M.parse_versions([n for n, _ in refs.get("branches", []) + refs.get("tags", [])])
    majors = {v.major for v in vs}
    if not vs:
        return "no version ref"
    if majors == {3}:
        return "v3.0 only"
    if majors == {2}:
        return "v2.x only"
    if {2, 3} <= majors:
        return "v2.x and v3.0"
    return "other"


def build(results: Path) -> pd.DataFrame:
    rows = []
    for r in load_raw(results):
        rid = r["dataset"]
        info = load_json(results / "info_cache" / f"{rid}.json")
        refs = load_json(results / "refs_cache" / f"{rid}.json")
        f = M.facts(r, info, refs)
        lr, op = M.lerobot_verdict(f), M.openpi_verdict(f)
        main_only = {"lerobot": lr["verdict"], "openpi": op["verdict"]}
        # scripts/verify_refs.py: where the loader's selected ref is not main's commit, judge that snapshot
        verified = {}
        for loader, fn in (("lerobot", M.lerobot_verdict), ("openpi", M.openpi_verdict)):
            ref_rec = load_json(results / "raw_ref" / loader / f"{rid}.json")
            if ref_rec is not None:
                verified[loader] = fn(M.facts(ref_rec, None, refs))
        lr, op = verified.get("lerobot", lr), verified.get("openpi", op)
        pi = M.pi05_fit(info)  # info.json at the audited sha; features rarely change between refs
        rows.append({
            "dataset": rid, "stratum": r["stratum"], "groot": verdict_label(r),
            "lerobot": lr["verdict"], "lerobot_steps": "+".join(lr["steps"]), "lerobot_reason": lr["reason"],
            "openpi": op["verdict"], "openpi_steps": "+".join(op["steps"]), "openpi_reason": op["reason"],
            "pi05": pi["verdict"], "pi05_issues": "+".join(pi.get("issues", [])), "pi05_reason": pi["reason"],
            **{f"pi05_{c['id']}": c["status"] for c in pi["checks"]},
            "tag_landscape": tag_landscape(refs),
            "tag_info_mismatch": bool(lr.get("tag_info_mismatch")),
            "lerobot_verified_at_ref": "lerobot" in verified,
            "openpi_verified_at_ref": "openpi" in verified,
            "lerobot_main_only": main_only["lerobot"], "openpi_main_only": main_only["openpi"],
            "openpi_files_at_ref_unverified": bool(op.get("files_at_ref_unverified")),
            "lerobot_sha": M.LEROBOT_SHA[:7], "openpi_sha": M.OPENPI_SHA[:7],
            "openpi_lerobot_sha": M.OPENPI_LEROBOT_SHA[:7],
        })
    return pd.DataFrame(rows)


def column_table(df: pd.DataFrame, col: str) -> str:
    strat = {s: df[df.stratum == s] for s in STRATA}
    header = ["verdict"] + [f"{s} (n={len(d)})" for s, d in strat.items()] + ["meaning"]
    rows = [[f"`{v}`"] + [pct(int((d[col] == v).sum()), len(d)) for d in strat.values()] + [MEANING[v]]
            for v in ORDER[col]]
    rows.append([f"*…of which judged on a ref snapshot that is not `main` (checked, `verify_refs.py`)*"]
                + [f"*{int(d[col + '_verified_at_ref'].sum())}*" for d in strat.values()]
                + ["the file listing and meta were read at that exact commit"])
    if col == "openpi":
        rows.append(["*…of which `NEEDS_CONFIG` through an older `v2.x` ref whose files were NOT inspected*"]
                    + [f"*{int(d.openpi_files_at_ref_unverified.sum())}*" for d in strat.values()]
                    + ["would be a lower bound on doubt; 0 once `verify_refs.py` has run"])
    return md_table(header, rows)


def changed_table(df: pd.DataFrame) -> str:
    """How much did judging the real snapshot move the verdicts, compared with judging `main`."""
    rows = []
    for col in ("lerobot", "openpi"):
        d = df[df[col + "_verified_at_ref"]]
        moved = d[d[col] != d[col + "_main_only"]]
        rows.append([col, len(d), len(moved),
                     "; ".join(f"{a} -> {b}: {n}" for (a, b), n in
                               moved.groupby([col + "_main_only", col]).size().items()) or "-"])
    return md_table(["column", "snapshots checked", "verdict differs from judging main", "moves"], rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    args = ap.parse_args(argv)
    results = ROOT / args.results
    df = build(results)
    df.to_csv(results / "models.csv", index=False)

    un = df[df.lerobot == "UNASSESSED"]
    df = df[df.lerobot != "UNASSESSED"]
    strat = {s: df[df.stratum == s] for s in STRATA}
    out = []
    add = out.append
    add("# LeRobot and openpi columns\n")
    add("Companion to `report.md`. Same audited datasets and strata; judged by "
        "[`CONTRACT_lerobot_openpi.md`](../CONTRACT_lerobot_openpi.md) for loading by Hub `repo_id`. "
        f"LeRobot `{M.LEROBOT_SHA[:7]}` (reads v3.0), openpi `{M.OPENPI_SHA[:7]}` via lerobot "
        f"`{M.OPENPI_LEROBOT_SHA[:7]}` (reads v2.x). Metadata only: nothing was loaded through either model. "
        "**Every rate is per stratum with its own n; there is no pooled rate.** Individual datasets are not "
        "named here; ids are in `models.csv`.\n")
    add(f"{len(un)} audited dataset(s) are excluded as UNASSESSED: the repo is gone or private since the audit, "
        "so its Hub refs could not be read. They are not in any n below.\n")
    add("## 1. LeRobot native (v3.0)\n")
    add(column_table(df, "lerobot"))
    add("\n## 2. openpi (v2.x)\n")
    add(column_table(df, "openpi"))
    add("\nopenpi has no `PASS`: every dataset needs a per-dataset Python data config and a "
        "`compute_norm_stats.py` run (contract §5). Timestamp sync (every frame within 1e-4 s of k/fps, "
        "contract §4) needs the parquet and was **not** checked, so `NEEDS_CONFIG` is an upper bound.\n")
    add("## 3. π0.5 model fit (openpi `pi05_base`)\n")
    add("Whether the *contents* fit π0.5 as openpi ships it (contract §7), independent of whether the files load "
        "(§2 above). From `info.json` at the audited sha; nothing was loaded. A dataset without a readable "
        "`info.json` is not in these n.\n")
    pf = df[df.pi05 != "UNASSESSED"]
    pstrat = {s: pf[pf.stratum == s] for s in STRATA}
    header = ["verdict"] + [f"{s} (n={len(d)})" for s, d in pstrat.items()] + ["meaning"]
    add(md_table(header, [[f"`{v}`"] + [pct(int((d.pi05 == v).sum()), len(d)) for d in pstrat.values()]
                          + [MEANING[v]] for v in M.PI05_VERDICTS]))
    add("\nShare of datasets where each check is not `OK` (`ADAPT`/`FAIL`, or `NOTE` for P5 and P7):\n")
    header = ["check"] + [f"{s} (n={len(d)})" for s, d in pstrat.items()]
    rows = []
    for cid, what in PI05_CHECKS.items():
        col = f"pi05_{cid}"
        rows.append([f"{cid} {what}"] + [pct(int(d[col].isin(["NOTE", "ADAPT", "FAIL"]).sum()) if col in d else 0, len(d))
                                         for d in pstrat.values()])
    add(md_table(header, rows))
    ready = lambda d: int(((d.openpi == "NEEDS_CONFIG") & (d.pi05 == "FIT")).sum())  # noqa: E731
    add("\nopenpi `NEEDS_CONFIG` **and** π0.5 `FIT` (loads from the Hub, and the config is only key renames): "
        + ", ".join(f"{s} {pct(ready(d), len(d))}" for s, d in strat.items()) + ".\n")
    add("## 4. Hub version refs (what decides loading by `repo_id`)\n")
    header = ["version refs"] + [f"{s} (n={len(d)})" for s, d in strat.items()]
    add(md_table(header, [[t] + [pct(int((d.tag_landscape == t).sum()), len(d)) for d in strat.values()]
                          for t in TAG_LANDSCAPE]))
    add(f"\nRefs were read on the fetch date, not at the audited sha. {int(df.tag_info_mismatch.sum())} dataset(s) "
        "have an `info.json` major version that no ref carries; their verdict follows the refs.\n")
    add("### Effect of reading the real snapshot\n")
    add(changed_table(df))
    add("\n## 5. Side by side with GR00T\n")
    both = lambda d: int(((d.lerobot == "PASS") & (d.openpi == "NEEDS_CONFIG")).sum())  # noqa: E731
    add(md_table(["", *[f"{s} (n={len(d)})" for s, d in strat.items()]], [
        ["GR00T `READY` or `NEEDS_MODALITY`"] + [pct(int(d.groot.isin(["READY", "READY†", "NEEDS_MODALITY"]).sum()), len(d))
                                                  for d in strat.values()],
        ["LeRobot `PASS`"] + [pct(int((d.lerobot == "PASS").sum()), len(d)) for d in strat.values()],
        ["openpi `NEEDS_CONFIG`"] + [pct(int((d.openpi == "NEEDS_CONFIG").sum()), len(d)) for d in strat.values()],
        ["LeRobot `PASS` and openpi `NEEDS_CONFIG` (both, from the Hub, no conversion)"]
        + [pct(both(d), len(d)) for d in strat.values()],
    ]))
    add("\nThe first row is not 'loads in GR00T': GR00T reads a local copy, so its rows ignore refs.\n")
    tail = strat["S-tail"]
    if len(tail):
        for label, k in (("LeRobot `PASS`", int((tail.lerobot == "PASS").sum())),
                         ("openpi `NEEDS_CONFIG`", int((tail.openpi == "NEEDS_CONFIG").sum()))):
            lo, hi = wilson(k, len(tail))
            add(f"S-tail (random sample) {label}: {k}/{len(tail)} = {k / len(tail):.1%}, 95% Wilson CI "
                f"[{lo:.1%}, {hi:.1%}]. No interval for the other strata: they are not random samples.\n")
    (results / "report_models.md").write_text("\n".join(out))
    print(f"wrote {results / 'models.csv'} ({len(df)} datasets, {len(un)} unassessed) and report_models.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
