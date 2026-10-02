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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GR00T-loadability linter for a local LeRobot dataset")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true", help="emit the full JSON report")
    args = ap.parse_args(argv)
    r = inspect_local(args.path)
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"verdict: {r['verdict']}   steps: {r['steps']}   (GR00T @{C.GROOT_SHA[:7]})")
        for c in r["checks"]:
            mark = {True: "pass", False: "FAIL" if c["level"] == "FAIL" else c["level"], None: "skip"}[c["passed"]]
            print(f"  {c['id']:<4}{mark:<5} {c['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
