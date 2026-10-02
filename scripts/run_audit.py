"""Batch audit driver (plan §6 Phase 3). Resumable, metadata-only, polite.

Reads the sample from results/strata.json and writes one JSON per dataset:
  results/raw/<author>/<name>.json      audited: enters the denominator
  results/errors/<author>/<name>.json   could not be observed: exclusion bucket, never
                                        in the denominator (gated, 404, private, empty,
                                        rate-limited, network...)
Ids already in results/raw/ are skipped, so an interrupted run resumes where it stopped.
Ids in results/errors/ are retried on the next run (most errors are transient) unless
--no-retry-errors is passed. Each run appends one summary line to results/run_log.jsonl.

    .venv/bin/python scripts/run_audit.py                      # the full 562
    .venv/bin/python scripts/run_audit.py --stratum S-curated --limit 5   # smoke test
"""
import argparse
import collections
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import huggingface_hub  # noqa: E402
from huggingface_hub import HfApi  # noqa: E402

from conformance import contract as C  # noqa: E402
from conformance.inspect_hub import FetchError, inspect_hub  # noqa: E402

STRATA = ["S-curated", "S-popular", "S-recent", "S-tail"]


def out_path(base: Path, repo_id: str) -> Path:
    return base / f"{repo_id}.json"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strata", default=str(ROOT / "results/strata.json"))
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--stratum", action="append", choices=STRATA, help="repeatable; default all")
    ap.add_argument("--ids", nargs="*", help="audit these ids only (must be in the sample)")
    ap.add_argument("--limit", type=int, help="at most N pending ids per stratum (smoke tests)")
    ap.add_argument("--workers", type=int, default=2, help="concurrent datasets (be polite)")
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds each worker waits between datasets")
    ap.add_argument("--no-retry-errors", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-audit ids already in raw/")
    args = ap.parse_args()

    strata = json.load(open(args.strata))
    raw_dir, err_dir = Path(args.results) / "raw", Path(args.results) / "errors"
    wanted = set(args.stratum or STRATA)
    todo = []
    for s in STRATA:
        if s not in wanted:
            continue
        pending = []
        for row in strata["samples"][s]:
            rid = row["id"]
            if args.ids and rid not in args.ids:
                continue
            if not args.force and out_path(raw_dir, rid).exists():
                continue
            if args.no_retry_errors and out_path(err_dir, rid).exists():
                continue
            pending.append((s, rid))
        todo += pending[:args.limit] if args.limit else pending

    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    started = datetime.now(timezone.utc)
    t0 = time.time()
    print(f"{len(todo)} to audit (workers={args.workers}, authenticated={bool(token)}, "
          f"GR00T @{C.GROOT_SHA[:7]}, huggingface_hub {huggingface_hub.__version__})", flush=True)

    tally = collections.Counter()
    errors = collections.Counter()
    n_req = n_bytes = 0
    lock = threading.Lock()
    done = 0

    def one(stratum: str, rid: str):
        try:
            r = inspect_hub(rid, token=token, api=api)
            r["stratum"] = stratum
            write_json(out_path(raw_dir, rid), r)
            e = out_path(err_dir, rid)
            if e.exists():
                e.unlink()
            return "ok", r
        except FetchError as e:
            rec = {"dataset": rid, "stratum": stratum, "kind": e.kind, "detail": e.detail}
        except Exception as e:  # a linter bug must not kill a 500-dataset run; it is logged, not hidden
            rec = {"dataset": rid, "stratum": stratum, "kind": "linter_exception",
                   "detail": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        rec.update(audit_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), groot_sha=C.GROOT_SHA)
        write_json(out_path(err_dir, rid), rec)
        return "error", rec

    def job(stratum, rid):
        res = one(stratum, rid)
        time.sleep(args.sleep)
        return stratum, rid, res

    ex = ThreadPoolExecutor(max_workers=args.workers)
    try:
        futs = [ex.submit(job, s, rid) for s, rid in todo]
        for f in as_completed(futs):
            s, rid, (status, r) = f.result()
            with lock:
                done += 1
                if status == "ok":
                    tally[(s, r["verdict"])] += 1
                    n_req += r["fetch"]["n_requests"]
                    n_bytes += r["fetch"]["bytes_downloaded"]
                    msg = f"{r['verdict']:<24}{'+'.join(r['steps']) or '-'}"
                    if r.get("unverified_size"):
                        msg += f"  (unverified: {','.join(r['unverified_size'])})"
                else:
                    errors[(s, r["kind"])] += 1
                    msg = f"EXCLUDED {r['kind']}: {r['detail'][:80]}"
                print(f"[{done:>4}/{len(todo)}] {s:<10} {rid:<60} {msg}", flush=True)
    except KeyboardInterrupt:
        # Drop queued jobs; in-flight ones finish (each is a few seconds) and are saved.
        ex.shutdown(wait=True, cancel_futures=True)
        print("\ninterrupted: finished datasets are saved; rerun the same command to resume.", flush=True)
    else:
        ex.shutdown()

    wall = time.time() - t0
    # Totals over everything on disk for the sample, not just this run.
    on_disk = collections.Counter()
    excl = collections.Counter()
    for s in STRATA:
        for row in strata["samples"][s]:
            p, e = out_path(raw_dir, row["id"]), out_path(err_dir, row["id"])
            if p.exists():
                on_disk[(s, json.loads(p.read_text())["verdict"])] += 1
            elif e.exists():
                excl[(s, json.loads(e.read_text())["kind"])] += 1

    print(f"\nthis run: {done} datasets, {n_req} requests, {n_bytes / 1e6:.1f} MB downloaded, {wall / 60:.1f} min")
    print("\ncumulative, per stratum (audited n / sample n) — never pooled:")
    for s in STRATA:
        n_s = len(strata["samples"][s])
        aud = {v: c for (st, v), c in on_disk.items() if st == s}
        ex_ = {k: c for (st, k), c in excl.items() if st == s}
        n_a = sum(aud.values())
        print(f"  {s:<10} audited {n_a:>3}/{n_s}  excluded {sum(ex_.values()):>3}  pending {n_s - n_a - sum(ex_.values()):>3}")
        for v, c in sorted(aud.items(), key=lambda x: -x[1]):
            print(f"      {v:<26}{c:>4}  ({c / n_a:.0%} of audited)")
        for k, c in sorted(ex_.items(), key=lambda x: -x[1]):
            print(f"      excluded:{k:<17}{c:>4}")

    log = {
        "run_started_utc": started.isoformat(timespec="seconds"), "wall_s": round(wall, 1),
        "groot_sha": C.GROOT_SHA, "huggingface_hub_version": huggingface_hub.__version__,
        "authenticated": bool(token), "workers": args.workers, "strata_filter": sorted(wanted),
        "limit": args.limit, "attempted": done, "requests": n_req, "bytes_downloaded": n_bytes,
        "this_run_verdicts": {f"{s}|{v}": c for (s, v), c in tally.items()},
        "this_run_errors": {f"{s}|{k}": c for (s, k), c in errors.items()},
    }
    with open(Path(args.results) / "run_log.jsonl", "a") as f:
        f.write(json.dumps(log) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
