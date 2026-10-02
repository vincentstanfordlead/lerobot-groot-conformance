"""One-off migration of results/raw/ for the 2026-10-01 linter changes (NOTES.md, 2026-10-01).

1. Verdict / step renames:  NEEDS_SEMANTICS -> NEEDS_MODALITY, SEMANTICS -> MODALITY,
                            UNCLASSIFIED_STRUCTURE -> BLOCKED.
2. Adds the four checks introduced that day, computed from the same inputs the audit saw,
   without a re-audit:
     L11  episodes.jsonl line count == info.json:total_episodes   (count from the stored G2 detail)
     L12  fps declared                                             (info.json)
     G15  every feature has a dtype                                (info.json)
     G16  state/action columns are float                           (info.json + modality.json)
   info.json / modality.json are read at the audited repo sha (`repo_sha`), 2 MB cap, cached
   under results/info_cache/ (modality.json under results/modality_cache/).
3. Recomputes the verdict with the current `checks.verdict` from the stored check results.
   The only verdict change allowed besides the renames is the 2026-10-01 rule that a dataset
   with no parquet under data/ (L3 fails; metadata-only upload) is BLOCKED, not
   NEEDS_DOWNCONVERT. Any other move aborts without writing. Idempotent.

    .venv/bin/python scripts/backfill_2026_10_01.py [--offline]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import checks as K  # noqa: E402
from conformance.report import fetch_info  # noqa: E402

RENAME_VERDICT = {"NEEDS_SEMANTICS": "NEEDS_MODALITY", "UNCLASSIFIED_STRUCTURE": "BLOCKED"}
RENAME_STEP = {"SEMANTICS": "MODALITY", "UNCLASSIFIED_STRUCTURE": "BLOCKED"}
NEW_IDS = ("L11", "L12", "G15", "G16")


class MetaView:
    """Just info.json (+ modality.json when the dataset ships one)."""

    def __init__(self, info: dict, modality: dict | None):
        self._text = {"meta/info.json": json.dumps(info)}
        if modality is not None:
            self._text["meta/modality.json"] = json.dumps(modality)
        self.files = {k: len(v) for k, v in self._text.items()}

    def read_text(self, rel):
        return self._text.get(rel)


def l11_from_g2(g2: dict, info: dict) -> dict:
    m = re.match(r"(\d+) episodes, all with", g2.get("detail") or "")
    total = info.get("total_episodes")
    if g2.get("passed") is not True or not m:
        return dict(id="L11", level="WARN", passed=None, source=None, blocked_by="G2", data={},
                    detail=f"episodes.jsonl not parsed by G2 ({g2.get('detail')}); episode count not compared")
    n = int(m.group(1))
    if not isinstance(total, int):
        return dict(id="L11", level="WARN", passed=None, source=None, blocked_by=None, data={},
                    detail="info.json:total_episodes absent; nothing to compare")
    return dict(id="L11", level="WARN", passed=n == total, source=None, blocked_by=None,
                detail=f"episodes.jsonl lines={n}, info.json:total_episodes={total}",
                data={"episodes_lines": n, "total_episodes": total})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    results = Path(args.results)
    token = None if args.offline else os.environ.get("HF_TOKEN")
    info_cache, mod_cache = results / "info_cache", results / "modality_cache"

    pending, moved, done, rederived = [], [], 0, []
    for p in sorted((results / "raw").rglob("*.json")):
        r = json.loads(p.read_text())
        if "backfill" in r:
            done += 1
            change = rederive(r)
            if change:
                rederived.append((r["dataset"], *change))
                pending.append((p, r))
            continue
        old_v, old_steps = r["verdict"], r["steps"]
        r["verdict"] = RENAME_VERDICT.get(old_v, old_v)
        r["steps"] = [RENAME_STEP.get(s, s) for s in old_steps]
        new = []
        if r["verdict"] != "NOT_LEROBOT":
            sha = r["repo_sha"]
            if args.offline and not (info_cache / f"{r['dataset']}.json").exists():
                raise SystemExit(f"--offline but no cached info.json for {r['dataset']}")
            info = fetch_info(r["dataset"], sha, info_cache, token)
            if info is None:
                raise SystemExit(f"info.json unavailable for {r['dataset']}; not writing a partial backfill")
            modality = None
            g6 = next(c for c in r["checks"] if c["id"] == "G6")
            if g6["passed"]:
                modality = _fetch_modality(r["dataset"], sha, mod_cache, token, args.offline)
            x = K.Ctx(MetaView(info, modality))
            l12 = next(c for c in K.run_l_checks(x) if c.id == "L12")
            by = {c["id"]: c for c in r["checks"]}
            new = [l11_from_g2(by["G2"], info), K.asdict(l12), K.asdict(K.g15(x)), K.asdict(K.g16(x))]
            newly_failed = [c["id"] for c in new if c["level"] == "FAIL" and c["passed"] is False]
            if newly_failed:
                moved.append((r["dataset"], newly_failed))
        r["checks"] = [c for c in r["checks"] if c["id"] not in NEW_IDS] + new
        r["checks"].sort(key=lambda c: (c["id"][0] != "L", int(c["id"][1:])))
        r["backfill"] = {"date": "2026-10-01", "renamed_from": old_v if old_v != r["verdict"] else None,
                         "added_checks": [c["id"] for c in new],
                         "inputs": "meta/info.json (+ modality.json) at repo_sha; L11 count from stored G2"}
        change = rederive(r)
        if change:
            rederived.append((r["dataset"], *change))
        pending.append((p, r))

    bad = [c for c in rederived if not c[3]]
    if moved or bad:
        print("Refusing to write: new FAIL-level checks would move these verdicts:", file=sys.stderr)
        for d, ids in moved:
            print(f"  {d}: {ids}", file=sys.stderr)
        for d, a, b, _ in bad:
            print(f"  {d}: {a} -> {b} for a reason other than the no-data rule", file=sys.stderr)
        return 1
    for p, r in pending:
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(r, indent=1))
        os.replace(tmp, p)
    for d, a, b, _ in rederived:
        print(f"  re-derived {d}: {a} -> {b} (no parquet under data/)")
    print(f"wrote {len(pending)} file(s) ({done} already backfilled); {len(rederived)} verdict(s) re-derived")
    return 0


class _StoredCtx:
    """Just enough of checks.Ctx for checks.verdict(): the v3 decision the audit already made."""

    def __init__(self, v3: bool):
        self._v3 = v3

    def is_v3_layout(self) -> bool:
        return self._v3


def rederive(r: dict):
    """Re-run checks.verdict() on stored results. Returns (old, new, allowed) or None."""
    if r["verdict"] == "NOT_LEROBOT":
        return None
    results = [K.CheckResult(**{k: c[k] for k in ("id", "level", "passed", "detail", "source", "blocked_by", "data")})
               for c in r["checks"]]
    v3 = "DOWNCONVERT" in r["steps"] or r["backfill"].get("v3_layout", False)
    v = K.verdict(results, _StoredCtx(v3))
    if (v["verdict"], v["steps"]) == (r["verdict"], r["steps"]):
        return None
    l3 = next(c for c in r["checks"] if c["id"] == "L3")
    allowed = l3["passed"] is False and v["verdict"] == "BLOCKED"
    old = r["verdict"]
    r["backfill"]["v3_layout"] = v3
    r["backfill"]["verdict_before_no_data_rule"] = old
    r["verdict"], r["steps"], r["failed_fail_level"] = v["verdict"], v["steps"], v["failed_fail_level"]
    return old, v["verdict"], allowed


def _fetch_modality(repo_id, sha, cache: Path, token, offline) -> dict | None:
    p = cache / f"{repo_id}.json"
    if p.exists():
        return json.loads(p.read_text())
    if offline:
        raise SystemExit(f"--offline but no cached modality.json for {repo_id}")
    import urllib.request

    from huggingface_hub import hf_hub_url

    from conformance.inspect_hub import UA, _retry
    url = hf_hub_url(repo_id, "meta/modality.json", repo_type="dataset", revision=sha)
    headers = {"User-Agent": UA, **({"Authorization": f"Bearer {token}"} if token else {})}

    def go():
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
            body = r.read(K.MAX_META_BYTES + 1)
            if len(body) > K.MAX_META_BYTES:
                raise ValueError("modality.json over cap")
            return body
    m = json.loads(_retry(go, "modality.json"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m))
    return m


if __name__ == "__main__":
    sys.exit(main())
