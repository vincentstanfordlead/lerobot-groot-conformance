"""Conformance manifest: a small JSON file that travels with a dataset instead of the data.

A producer runs the checks where the data lives and ships `conformance.json` next to the
dataset. A receiver re-runs the same checks on what arrived (`verify`) and compares. Nobody
uploads data anywhere, but both sides can count datasets, hours and episodes that meet the
standard: the supply-side and demand-side adoption metrics.

What the fingerprint binds: the bytes of the metadata files the checks read, plus the path and
size of every file in the dataset. It does not hash episode or video payloads (that would mean
reading every byte), so a same-size payload swap is not detected. It is an integrity record, not
a signature: anyone can regenerate it. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import contract as C
from .embodiment import classify

SCHEMA = "robot-data-conformance/v0"
TOOL = {"name": "robot-data-smog-check", "version": "0.1.0"}
MANIFEST_NAME = "conformance.json"
DRAFT_NAME = "modality.draft.json"
PLAN_NAME = "pi05_config_plan.md"
HASHED = ("meta/info.json", "meta/episodes.jsonl", "meta/tasks.jsonl", "meta/modality.json", "meta/stats.json")
_EXCLUDED_NAMES = {MANIFEST_NAME, DRAFT_NAME, PLAN_NAME}


def _counted(rel: str) -> bool:
    """Files that belong to the dataset: not our own outputs, not hidden files or folders (.git, .cache, .DS_Store)."""
    parts = rel.split("/")
    return rel not in _EXCLUDED_NAMES and not any(p.startswith(".") for p in parts)


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(root: Path, files: dict[str, int]) -> dict:
    root = Path(root)
    kept = sorted((p, s) for p, s in files.items() if _counted(p))
    listing = hashlib.sha256("".join(f"{p}\t{s}\n" for p, s in kept).encode()).hexdigest()
    return {
        "algorithm": "sha256",
        "metadata_files": {rel: _sha256_file(root / rel) for rel in HASHED if rel in files},
        "file_listing": listing,
        "n_files": len(kept),
        "total_bytes": sum(s for _, s in kept),
    }


def _num(v) -> Optional[float]:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def dataset_summary(info: Optional[dict], name: str) -> dict:
    info = info if isinstance(info, dict) else {}
    feats = info.get("features") if isinstance(info.get("features"), dict) else {}
    fps, frames = _num(info.get("fps")), _num(info.get("total_frames"))
    emb = classify(info or None, name)
    return {
        "name": name,
        "codebase_version": info.get("codebase_version"),
        "robot_type": info.get("robot_type"),
        "embodiment": emb["category"],
        "fits_groot": emb["fit"],
        "fps": fps,
        "total_episodes": _num(info.get("total_episodes")),
        "total_frames": frames,
        "hours": round(frames / fps / 3600, 3) if frames and fps else None,
        "cameras": [k for k, v in feats.items() if isinstance(v, dict) and v.get("dtype") == "video"],
    }


def build(root: Path, report: dict, info: Optional[dict], files: dict[str, int], models: Optional[dict] = None) -> dict:
    """`models`: other models' verdicts to record, e.g. {"pi05": {"load": "NEEDS_CONFIG", "fit": "FIT"}}."""
    checks = report["checks"]
    out = {
        "schema": SCHEMA,
        "tool": TOOL,
        "target": {"model": "NVIDIA Isaac GR00T", "loader": "github.com/NVIDIA/Isaac-GR00T",
                   "commit": C.GROOT_SHA, "n_checks": len(checks)},
        "dataset": dataset_summary(info, Path(root).resolve().name),
        "result": {
            "verdict": report["verdict"],
            "steps": report["steps"],
            "passed": [c["id"] for c in checks if c["passed"] is True],
            "failed": [c["id"] for c in checks if c["passed"] is False],
            "skipped": [c["id"] for c in checks if c["passed"] is None],
            "unverified_size": report.get("unverified_size", []),
        },
        "fingerprint": fingerprint(root, files),
        "privacy": ("Generated locally from the metadata files listed in fingerprint.metadata_files and the "
                    "file listing (paths and sizes). No episode data or video was opened, and nothing was uploaded."),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if models:
        out["models"] = models
    return out


def compare(old: dict, new: dict) -> list[str]:
    """Differences between a shipped manifest and one rebuilt from what arrived. Empty = verified."""
    diffs = []
    if old.get("schema") != new["schema"]:
        diffs.append(f"schema: manifest says {old.get('schema')!r}, this tool writes {new['schema']!r}")
    oc, nc = (old.get("target") or {}).get("commit"), new["target"]["commit"]
    if oc != nc:
        diffs.append(f"checked against a different GR00T commit ({str(oc)[:7]} vs {nc[:7]}); re-run the check on both sides")
    of, nf = old.get("fingerprint") or {}, new["fingerprint"]
    om, nm = of.get("metadata_files") or {}, nf["metadata_files"]
    for rel in sorted(set(om) | set(nm)):
        if rel not in nm:
            diffs.append(f"{rel}: listed in the manifest but missing here")
        elif rel not in om:
            diffs.append(f"{rel}: present here but not in the manifest")
        elif om[rel] != nm[rel]:
            diffs.append(f"{rel}: contents changed")
    if of.get("file_listing") != nf["file_listing"]:
        diffs.append(f"file listing changed: {of.get('n_files')} files / {of.get('total_bytes')} bytes in the manifest, "
                     f"{nf['n_files']} / {nf['total_bytes']} here")
    ov, nv = (old.get("result") or {}).get("verdict"), new["result"]["verdict"]
    if ov != nv:
        diffs.append(f"verdict: manifest says {ov}, re-check says {nv}")
    for m, was in (old.get("models") or {}).items():
        now = (new.get("models") or {}).get(m)
        if now is None:
            diffs.append(f"{m}: in the manifest but not re-checked here")
        elif now != was:
            diffs.append(f"{m}: manifest says {was}, re-check says {now}")
    return diffs


def read(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def write(path: Path, manifest: dict) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
