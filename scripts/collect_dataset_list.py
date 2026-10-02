"""Enumerate the full population of HF datasets tagged `LeRobot` (plan §6 Phase 2, step 1).

Metadata only: one paged listing call (1000 per page, cursor-paged by huggingface_hub).
No repo is opened. Output is sorted by id so the file is diff-able and the sampling in
build_strata.py is order-independent of the Hub's listing order.

    .venv/bin/python scripts/collect_dataset_list.py [--out results/dataset_list.json]
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

import huggingface_hub
from huggingface_hub import HfApi

FILTER = "LeRobot"
EXPAND = ["author", "downloads", "downloadsAllTime", "likes", "lastModified",
          "createdAt", "gated", "disabled", "tags"]


def iso(t):
    return t.isoformat() if t else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/dataset_list.json")
    args = ap.parse_args()

    started = dt.datetime.now(dt.timezone.utc)
    t0 = time.time()
    rows = []
    for d in HfApi().list_datasets(filter=FILTER, expand=EXPAND):
        rows.append({
            "id": d.id,
            "author": d.author or d.id.split("/")[0],
            "downloads": d.downloads,                 # last 30 days (Hub definition)
            "downloads_all_time": d.downloads_all_time,
            "likes": d.likes,
            "last_modified": iso(d.last_modified),
            "created_at": iso(d.created_at),
            "gated": d.gated,
            "disabled": d.disabled,
            "tags": d.tags or [],
        })
        if len(rows) % 5000 == 0:
            print(f"  {len(rows):>6} ids  ({time.time() - t0:.0f}s)", file=sys.stderr)
    finished = dt.datetime.now(dt.timezone.utc)

    ids = [r["id"] for r in rows]
    n_dupes = len(ids) - len(set(ids))
    rows = sorted({r["id"]: r for r in rows}.values(), key=lambda r: r["id"])

    out = {
        "meta": {
            "filter": FILTER,
            "endpoint": "HfApi().list_datasets(filter=..., expand=...)",
            "expand": EXPAND,
            "snapshot_started_utc": started.isoformat(),
            "snapshot_finished_utc": finished.isoformat(),
            "wall_clock_s": round(time.time() - t0, 1),
            "huggingface_hub_version": huggingface_hub.__version__,
            "authenticated": bool(os.environ.get("HF_TOKEN")),
            "n_listed": len(ids),
            "n_duplicate_ids_dropped": n_dupes,
            "n": len(rows),
        },
        "datasets": rows,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    os.replace(tmp, args.out)
    print(json.dumps(out["meta"], indent=1))


if __name__ == "__main__":
    main()
