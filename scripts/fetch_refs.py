"""Fetch the branches and tags of every audited dataset repo (NOTES.md, 2026-10-02).

Both LeRobot loaders pick the Hub revision from the repo's version-named branches/tags
(`get_safe_version`), not from info.json, so the LeRobot and openpi columns need the refs.
One `list_repo_refs` call per repo; ids come from results/info_cache/. Output goes to
results/refs_cache/<author>/<name>.json. Repos already cached are skipped, so the script
can be re-run after an interruption. Refs are read at fetch time, not at the audited sha.

    .venv/bin/python scripts/fetch_refs.py [--workers 2]
"""
import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from huggingface_hub import HfApi  # noqa: E402

from conformance.inspect_hub import FetchError, _retry  # noqa: E402

INFO_CACHE = ROOT / "results" / "info_cache"
OUT = ROOT / "results" / "refs_cache"


def fetch(api: HfApi, repo_id: str) -> dict:
    row = {"id": repo_id, "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        refs = _retry(lambda: api.list_repo_refs(repo_id, repo_type="dataset"), f"refs {repo_id}")
    except FetchError as e:
        row["error"] = {"kind": e.kind, "detail": e.detail}
        return row
    row["branches"] = sorted({b.name: b.target_commit for b in refs.branches}.items())
    row["tags"] = sorted({t.name: t.target_commit for t in refs.tags}.items())
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    ids = sorted(f"{p.parent.name}/{p.stem}" for p in INFO_CACHE.glob("*/*.json"))
    todo = [i for i in ids if not (OUT / f"{i}.json").exists()]
    print(f"{len(ids)} repos, {len(ids) - len(todo)} cached, {len(todo)} to fetch "
          f"(authenticated={bool(os.environ.get('HF_TOKEN'))})", file=sys.stderr)

    api = HfApi()
    errors = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for n, row in enumerate(ex.map(lambda i: fetch(api, i), todo), 1):
            if "error" in row:
                errors += 1  # not cached, so a re-run retries it
                print(f"  [{n}/{len(todo)}] {row['id']}  {row['error']['kind']}", file=sys.stderr)
                continue
            path = OUT / f"{row['id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(row, indent=1) + "\n")
            if n % 50 == 0:
                print(f"  [{n}/{len(todo)}]", file=sys.stderr)
    print(f"done: {len(todo) - errors} fetched, {errors} errors", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
