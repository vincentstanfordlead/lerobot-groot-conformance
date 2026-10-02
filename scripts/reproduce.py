"""Reproduce the audit with one command.

    .venv/bin/python scripts/reproduce.py              # from the committed snapshot (seconds, offline)
    .venv/bin/python scripts/reproduce.py --reaudit    # re-fetch every sampled repo's metadata (~30 min)

Default: rebuild the sample from the committed enumeration snapshot
(results/dataset_list.json.gz, 2026-09-29), check it is byte-identical to results/strata.json,
then regenerate summary.csv, report.md and the chart from the committed per-dataset results
in results/raw/. No network.

--reaudit: same sample, but every repo is audited again at its *current* commit into
results_reaudit/ (results/ is left alone), then reported there. Repos change, so expect
small differences from the 2026-09-29 numbers. Set HF_TOKEN first; the anonymous rate limit
is slow. --fresh-list additionally re-enumerates the LeRobot tag, which redraws S-popular and
S-recent (both are time-dependent by definition) and shifts S-tail with the population.
"""
import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run([PY, *args], cwd=ROOT, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reaudit", action="store_true", help="re-fetch metadata for every sampled repo")
    ap.add_argument("--fresh-list", action="store_true", help="re-enumerate the LeRobot tag (implies --reaudit)")
    args = ap.parse_args()
    reaudit = args.reaudit or args.fresh_list
    # Paths are passed relative to ROOT (the subprocess cwd) so no local path is written into results.
    res = Path("results_reaudit" if reaudit else "results")
    (ROOT / res).mkdir(exist_ok=True)

    # 1. enumeration
    snap_gz, listing = ROOT / "results/dataset_list.json.gz", res / "dataset_list.json"
    if args.fresh_list:
        run("scripts/collect_dataset_list.py", "--out", str(listing))
    elif not (ROOT / listing).exists():
        with gzip.open(snap_gz, "rb") as src, open(ROOT / listing, "wb") as dst:
            shutil.copyfileobj(src, dst)

    # 2. sample
    # Without --reaudit the rebuilt sample goes to a side file (gitignored) and must equal the
    # committed results/strata.json; with it, it becomes results_reaudit/strata.json.
    committed = json.loads((ROOT / "results/strata.json").read_text())
    strata = res / ("strata.json" if reaudit else "strata_rebuilt.json")
    run("scripts/build_strata.py", "--in", str(listing), "--out", str(strata))
    rebuilt = json.loads((ROOT / strata).read_text())
    same = (rebuilt["samples"], rebuilt["meta"]["sample_sha256"]) == (committed["samples"], committed["meta"]["sample_sha256"])
    if not args.fresh_list and not same:
        print("rebuilt sample differs from results/strata.json", file=sys.stderr)
        return 1
    print("sample matches results/strata.json" if same else "new sample drawn (--fresh-list)")

    # 3. audit (resumable; with the committed results/raw/ this is a no-op)
    if reaudit:
        run("scripts/run_audit.py", "--strata", str(strata), "--results", str(res))
    else:
        # 2026-10-01 renames + four checks added from cached info.json (idempotent; see NOTES.md)
        run("scripts/backfill_2026_10_01.py", "--offline", "--results", str(res))

    # 4. report
    run("-m", "conformance.report", "--results", str(res), *([] if reaudit else ["--offline"]))
    print(f"\ndone: {res / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
