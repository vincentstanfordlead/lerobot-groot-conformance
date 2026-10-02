"""Audit a local LeRobot dataset directory."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from . import contract as C
from .checks import MAX_META_BYTES, run_all


class LocalView:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.files: dict[str, int] = {}
        for p in self.root.rglob("*"):
            if p.is_file():
                self.files[p.relative_to(self.root).as_posix()] = p.stat().st_size

    def read_text(self, rel: str) -> Optional[str]:
        if self.files.get(rel, 0) > MAX_META_BYTES:
            return None
        return (self.root / rel).read_text()


def inspect_local(path) -> dict:
    report = run_all(LocalView(Path(path)))
    report.update(dataset=str(path), audit_date=date.today().isoformat(), groot_sha=C.GROOT_SHA)
    return report


def print_report(r: dict, header: str, brief: bool = False) -> None:
    """Human-readable report. brief=True lists only checks that did not pass, plus a tally."""
    print(f"verdict: {r['verdict']}   steps: {r['steps']}   ({header})")
    shown = [c for c in r["checks"] if not brief or c["passed"] is False]
    for c in shown:
        mark = {True: "pass", False: "FAIL" if c["level"] == "FAIL" else c["level"], None: "skip"}[c["passed"]]
        print(f"  {c['id']:<4}{mark:<5} {c['detail']}")
    if brief:
        n_pass = sum(c["passed"] is True for c in r["checks"])
        n_skip = sum(c["passed"] is None for c in r["checks"])
        print(f"  ({n_pass} of {len(r['checks'])} checks pass, {n_skip} skipped; --json or no flag for all)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GR00T-loadability linter for a local LeRobot dataset")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true", help="emit the full JSON report")
    ap.add_argument("--brief", action="store_true", help="show only checks that do not pass")
    args = ap.parse_args(argv)
    r = inspect_local(args.path)
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print_report(r, f"GR00T @{C.GROOT_SHA[:7]}", args.brief)
    return 0


if __name__ == "__main__":
    sys.exit(main())
