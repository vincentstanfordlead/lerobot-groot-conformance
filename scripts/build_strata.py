"""Build the four-stratum sampling frame from results/dataset_list.json (plan §6 Phase 2, step 2).

Strata are disjoint and assigned in priority order, so every enumerated id lands in exactly
one frame:

  1. S-curated  author (case-insensitive) in CURATED_AUTHORS. Census: all of them, unless
                --curated-cap is set, in which case a seeded random subset of that size.
  2. S-popular  top N by 30-day `downloads` among ids not in S-curated.
                Ties: downloads_all_time desc, then id asc.
  3. S-recent   top N by `last_modified` among ids not in 1-2. Ties: id asc.
  4. S-tail     everything else is the frame; sample = first N non-gated ids of
                random.Random(seed).sample(frame sorted by id, len(frame)).

Gated repos are never sampled: each stratum takes the next non-gated id in its own order
instead (decision 2026-09-29, NOTES.md). Skipped ids stay in their frame, listed in
meta.gated_skipped.

Deterministic given (dataset_list.json, seed, sizes, allowlist). Everything needed to redraw
is written to results/strata.json:meta.

    .venv/bin/python scripts/build_strata.py [--seed 20260928]
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random

# Orgs that maintain or institutionally republish LeRobot-format benchmarks. Chosen by
# publisher, not by name match: a regex on droid|libero|robocasa|oxe|... hits 2,501 ids,
# mostly personal re-uploads (1,342 "libero" alone), which are tail, not curation.
CURATED_AUTHORS = {
    "lerobot",                # HF LeRobot team
    "nvidia",                 # GR00T's own publisher
    "ipec-community",         # OXE + DROID + LIBERO ports used by openpi/GR00T fine-tunes
    "huggingfacevla",         # HF LIBERO / MetaWorld ports
    "physical-intelligence",  # openpi's LIBERO port
}

STRATA = ["S-curated", "S-popular", "S-recent", "S-tail"]


def sha256_ids(ids):
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="results/dataset_list.json")
    ap.add_argument("--out", default="results/strata.json")
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--curated-cap", type=int, default=None,
                    help="default: census (take every curated id)")
    ap.add_argument("--n-popular", type=int, default=100)
    ap.add_argument("--n-recent", type=int, default=100)
    ap.add_argument("--n-tail", type=int, default=200)
    args = ap.parse_args()

    with open(args.inp) as f:
        doc = json.load(f)
    rows = doc["datasets"]
    by_id = {r["id"]: r for r in rows}
    rng = random.Random(args.seed)

    def take(ordered_ids, n):
        """First n non-gated ids in order; plus the gated ids passed over (plan: option b)."""
        picked, skipped = [], []
        for i in ordered_ids:
            if n is not None and len(picked) == n:
                break
            (skipped if by_id[i]["gated"] else picked).append(i)
        return picked, skipped

    frame, sample, gated_skipped = {}, {}, {}

    curated = sorted(r["id"] for r in rows if r["author"].lower() in CURATED_AUTHORS)
    order = curated if args.curated_cap is None else rng.sample(curated, len(curated))
    picked, gated_skipped["S-curated"] = take(order, args.curated_cap)
    frame["S-curated"] = curated
    sample["S-curated"] = sorted(picked)
    taken = set(curated)
    rest = [r for r in rows if r["id"] not in taken]

    popular = sorted(rest, key=lambda r: (-(r["downloads"] or 0),
                                          -(r["downloads_all_time"] or 0), r["id"]))
    picked, gated_skipped["S-popular"] = take([r["id"] for r in popular], args.n_popular)
    frame["S-popular"] = picked + gated_skipped["S-popular"]  # ranks down to the last pick
    sample["S-popular"] = picked
    taken |= set(frame["S-popular"])
    rest = [r for r in rest if r["id"] not in taken]

    recent = sorted(rest, key=lambda r: r["id"])
    recent = sorted(recent, key=lambda r: r["last_modified"] or "", reverse=True)
    picked, gated_skipped["S-recent"] = take([r["id"] for r in recent], args.n_recent)
    frame["S-recent"] = picked + gated_skipped["S-recent"]
    sample["S-recent"] = picked
    taken |= set(frame["S-recent"])

    frame["S-tail"] = sorted(r["id"] for r in rows if r["id"] not in taken)
    # Tail: walk a full seeded permutation of the frame, take the first n non-gated. Own RNG
    # instance so changing --curated-cap doesn't reshuffle it.
    perm = random.Random(args.seed).sample(frame["S-tail"], len(frame["S-tail"]))
    picked, gated_skipped["S-tail"] = take(perm, args.n_tail)
    sample["S-tail"] = sorted(picked)

    assert sum(len(v) for v in frame.values()) == len(rows)
    in_sample = {i: s for s, ids in sample.items() for i in ids}
    assert len(in_sample) == sum(len(v) for v in sample.values())  # disjoint

    # Annotate the enumeration in place: every id gets its frame, and whether it was drawn.
    stratum_of = {i: s for s, ids in frame.items() for i in ids}
    for r in rows:
        r["stratum"] = stratum_of[r["id"]]
        r["in_sample"] = r["id"] in in_sample
    tmp = args.inp + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, args.inp)

    def brief(i):
        r = by_id[i]
        return {k: r[k] for k in ("id", "author", "downloads", "downloads_all_time", "likes",
                                   "last_modified", "created_at", "gated")}

    out = {
        "meta": {
            "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "input": args.inp,
            "input_snapshot_started_utc": doc["meta"]["snapshot_started_utc"],
            "input_n": len(rows),
            "seed": args.seed,
            "rng": "python random.Random(seed).sample(frame_sorted_by_id, len(frame)); take first n non-gated",
            "curated_authors": sorted(CURATED_AUTHORS),
            "curated_cap": args.curated_cap,
            "sizes_requested": {"S-popular": args.n_popular, "S-recent": args.n_recent,
                                "S-tail": args.n_tail},
            "rules": {
                "S-curated": "author.lower() in curated_authors, non-gated; census unless curated_cap",
                "S-popular": "top n non-gated by downloads (30d) excl. S-curated; ties downloads_all_time desc, id asc",
                "S-recent": "top n non-gated by last_modified excl. S-curated/S-popular; ties id asc",
                "S-tail": "first n non-gated of a seeded permutation of all ids not in the three frames above",
            },
            "frame_sizes": {s: len(frame[s]) for s in STRATA},
            "sample_sizes": {s: len(sample[s]) for s in STRATA},
            "sample_total": len(in_sample),
            "frame_sha256": {s: sha256_ids(frame[s]) for s in STRATA},
            "sample_sha256": {s: sha256_ids(sample[s]) for s in STRATA},
            "gated_policy": "excluded from every sample and replaced by the next non-gated id "
                            "in that stratum's order (rank or seeded permutation); skipped "
                            "ids stay in the frame, listed in gated_skipped",
            "gated_skipped": {s: gated_skipped[s] for s in STRATA},
            "gated_in_sample": {s: sum(bool(by_id[i]["gated"]) for i in sample[s])
                                for s in STRATA},
        },
        "samples": {s: [brief(i) for i in sample[s]] for s in STRATA},
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out["meta"], indent=1))


if __name__ == "__main__":
    main()
