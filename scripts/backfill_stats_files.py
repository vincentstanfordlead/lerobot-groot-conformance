"""Backfill L7's "files" (every stats file present) into audit records that predate it (2026-10-26).

Before, L7 stored only the preferred stats file, so a v2.1 repo shipping both stats.json and
episodes_stats.jsonl looked to the openpi column as if episodes_stats.jsonl were missing. Only records
where that matters are touched: v2 layout, codebase_version >= 2.1, L7 layout stats.json, in results/raw/
and in the ref snapshots under results/raw_ref/. Their meta/ listing is read at the record's repo_sha
(one Hub request each).

    .venv/bin/python scripts/backfill_stats_files.py
"""
import json
import sys
from pathlib import Path

from huggingface_hub import HfApi
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parent.parent


def needs(rec: dict) -> bool:
    by = {c["id"]: c for c in rec.get("checks", [])}
    d = lambda i: (by.get(i) or {}).get("data") or {}  # noqa: E731
    if d("L7").get("layout") != "stats.json" or "files" in d("L7") or d("L5").get("layout") != "jsonl":
        return False
    try:
        v = Version(str(d("L2").get("codebase_version")))
    except InvalidVersion:
        return False
    return v.major == 2 and v >= Version("2.1")


def main() -> int:
    api = HfApi()
    res = ROOT / "results"
    for p in sorted(res.glob("raw/**/*.json")) + sorted(res.glob("raw_ref/**/*.json")):
        rec = json.loads(p.read_text())
        if not needs(rec):
            continue
        names = {e.path for e in api.list_repo_tree(rec["dataset"], path_in_repo="meta", repo_type="dataset",
                                                    revision=rec["repo_sha"])}
        files = [n for n in ("stats.json", "episodes_stats.jsonl") if f"meta/{n}" in names]
        l7 = next(c for c in rec["checks"] if c["id"] == "L7")
        l7["data"]["files"] = files
        rec.setdefault("backfill", {})["stats_files_2026_10_26"] = {"inputs": "meta/ listing at repo_sha", "files": files}
        p.write_text(json.dumps(rec, indent=1))
        print(f"{p.relative_to(res)}: {files}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
