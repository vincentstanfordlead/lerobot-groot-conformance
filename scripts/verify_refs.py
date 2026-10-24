"""Inspect the snapshot a loader would actually pull, where it is not `main` (NOTES.md, 2026-10-02).

run_models.py judges each repo from its audited `main`. When a loader's selected version ref points
at a different commit (e.g. a repo whose `main` is v3 but which keeps a `v2.1` ref that openpi
pulls), the files at that ref were never looked at. This script runs the same checks on that exact
commit and stores the record in results/raw_ref/<loader>/<repo>.json; run_models.py then uses it.

    .venv/bin/python scripts/verify_refs.py [--workers 2]
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import models as M  # noqa: E402
from conformance.inspect_hub import FetchError, inspect_hub  # noqa: E402

RESULTS = ROOT / "results"
TARGETS = {"lerobot": M.LEROBOT_TARGET, "openpi": M.OPENPI_TARGET}


def jobs() -> list[tuple[str, str, str, str]]:
    """(loader, repo_id, ref name, commit) for every selected ref that is not main's commit."""
    out = []
    for f in sorted((RESULTS / "refs_cache").glob("*/*.json")):
        r = json.loads(f.read_text())
        if "error" in r:
            continue
        shas = {n: s for n, s in r["branches"] + r["tags"]}
        main = shas.get("main")
        hub = M.parse_versions(list(shas))
        for loader, target in TARGETS.items():
            outcome, ref = M.select_revision(hub, target)
            if outcome == "ok" and shas[ref] != main:
                out.append((loader, r["id"], ref, shas[ref]))
    return out


def run_one(job, token):
    loader, repo, ref, sha = job
    path = RESULTS / "raw_ref" / loader / f"{repo}.json"
    if path.exists():
        return job, None
    try:
        rec = inspect_hub(repo, token=token, revision=sha)
    except FetchError as e:
        return job, f"{e.kind}: {e.detail}"
    rec["verified_ref"] = {"loader": loader, "ref": ref, "commit": sha}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1) + "\n")
    return job, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    token = os.environ.get("HF_TOKEN")
    todo = jobs()
    print(f"{len(todo)} (loader, repo) snapshots differ from main "
          f"({sum(j[0] == 'openpi' for j in todo)} openpi, {sum(j[0] == 'lerobot' for j in todo)} lerobot); "
          f"authenticated={bool(token)}", file=sys.stderr)
    errors = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for n, (job, err) in enumerate(ex.map(lambda j: run_one(j, token), todo), 1):
            if err:
                errors += 1  # not stored, so a re-run retries it
                print(f"  [{n}/{len(todo)}] {job[0]} {job[1]}  {err}", file=sys.stderr)
            elif n % 20 == 0:
                print(f"  [{n}/{len(todo)}]", file=sys.stderr)
    print(f"done: {len(todo) - errors} stored, {errors} errors", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
