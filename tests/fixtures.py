"""Phase 1 control fixtures.

`build_cube(dest, source=None)` produces the positive control `cube_to_bowl_5`.
  - source=<real demo_data/cube_to_bowl_5>: hardlink-copies NVIDIA's real fixture (preferred).
  - source=None: SYNTHETIC stand-in built from the vendored info.json + modality.json, with
    empty placeholder parquet/mp4 files. The linter only inspects names and meta, so this
    exercises every check, but it is NOT the upstream fixture — see NOTES.md.
Variants are made by copying then mutating.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "groot_51d4c89"
STAT_TYPES = ("mean", "std", "min", "max", "q01", "q99")


def _link_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_cube(dest: Path, source: Path | None = None) -> Path:
    dest = Path(dest)
    if source is not None:
        shutil.copytree(source, dest, copy_function=_link_or_copy)
        return dest
    meta = dest / "meta"
    meta.mkdir(parents=True)
    info = json.loads((VENDOR / "demo_data_cube_to_bowl_5_meta_info.json").read_text())
    shutil.copy(VENDOR / "demo_data_cube_to_bowl_5_meta_modality.json", meta / "modality.json")
    (meta / "info.json").write_text(json.dumps(info, indent=2))
    n = info["total_episodes"]
    lens = [info["total_frames"] // n] * (n - 1) + [info["total_frames"] - info["total_frames"] // n * (n - 1)]
    (meta / "episodes.jsonl").write_text(
        "".join(json.dumps({"episode_index": i, "tasks": ["t"], "length": l}) + "\n" for i, l in enumerate(lens)))
    (meta / "tasks.jsonl").write_text(
        "".join(json.dumps({"task_index": i, "task": f"task {i}"}) + "\n" for i in range(info["total_tasks"])))
    stats = {}
    for k, v in info["features"].items():
        if v["dtype"].startswith(("float", "int")):
            d = v["shape"][0]
            stats[k] = {t: [0.0] * d for t in STAT_TYPES}
    (meta / "stats.json").write_text(json.dumps(stats))
    video_keys = [k for k, v in info["features"].items() if v["dtype"] == "video"]
    for ep in range(n):
        p = dest / info["data_path"].format(episode_chunk=0, episode_index=ep)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        for vk in video_keys:
            v = dest / info["video_path"].format(episode_chunk=0, video_key=vk, episode_index=ep)
            v.parent.mkdir(parents=True, exist_ok=True)
            v.write_bytes(b"")
    return dest


def variant(base: Path, dest: Path, mutate) -> Path:
    shutil.copytree(base, dest, copy_function=_link_or_copy)
    mutate(dest)
    return dest


def edit_json(path: Path, fn):
    """Rewrite atomically so hardlinked source files are not mutated in place."""
    d = json.loads(path.read_text())
    fn(d)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    os.replace(tmp, path)
