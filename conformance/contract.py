"""The GR00T loading contract, pinned to one Isaac-GR00T commit.

Every G-check cites the vendored source. Citations are *generated* by locating an anchor
string in the vendored file, never hand-typed (Phase 0 found three hand-typed off-by-one
errors). If an anchor is missing or ambiguous, import fails loudly — that means the vendored
source changed and the contract needs re-verification.
"""
from __future__ import annotations

from pathlib import Path

GROOT_SHA = "51d4c89f72fda44cbf77285c6a8114b52676b8a1"
VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor" / f"groot_{GROOT_SHA[:7]}"

FILES = {
    "loader": "gr00t_data_dataset_lerobot_episode_loader.py",
    "factory": "gr00t_data_dataset_factory.py",
    "stats": "gr00t_data_stats.py",
    "repair": "scripts_repair_lerobot_metadata.py",
}
REPO_PATHS = {
    "loader": "gr00t/data/dataset/lerobot_episode_loader.py",
    "factory": "gr00t/data/dataset/factory.py",
    "stats": "gr00t/data/stats.py",
    "repair": "scripts/repair_lerobot_metadata.py",
}

_cache: dict[str, list[str]] = {}


def _lines(file_key: str) -> list[str]:
    if file_key not in _cache:
        _cache[file_key] = (VENDOR_DIR / FILES[file_key]).read_text().splitlines()
    return _cache[file_key]


def _find(file_key: str, anchor: str, after: int = 0) -> int:
    """1-indexed line of the first line >= `after` containing `anchor`; must be unique from there."""
    hits = [i + 1 for i, ln in enumerate(_lines(file_key)) if anchor in ln and i + 1 >= after]
    if not hits:
        raise LookupError(f"anchor not found in {FILES[file_key]}: {anchor!r}")
    return hits[0]


def cite(file_key: str, first: str, last: str | None = None, *, after: int = 0, extend: int = 0) -> tuple[str, int, int]:
    """(file_key, start, end) from anchor strings. `last` is searched at/after `first`'s line;
    `extend` adds trailing lines (e.g. a closing paren on its own line)."""
    start = _find(file_key, first, after)
    end = (_find(file_key, last, start) if last else start) + extend
    return file_key, start, end


def fmt(*spans: tuple[str, int, int]) -> str:
    """'path:L1-2, L3' — path repeated only when the file changes."""
    out, prev = [], None
    for key, s, e in spans:
        rng = f"L{s}" if s == e else f"L{s}-{e}"
        out.append(rng if key == prev else f"{REPO_PATHS[key]}:{rng}")
        prev = key
    return ", ".join(out)


def _build() -> dict[str, str]:
    L = "loader"
    video_fmt_start = _find(L, 'original_key = self.modality_meta["video"][meta_key].get(')
    return {
        "G1": fmt(cite(L, "info_path = meta_dir", "self.info_meta = json.load(f)")),
        "G2": fmt(
            cite(L, "episodes_path = meta_dir", "self.episodes_metadata = ["),
            cite(L, "def get_episode_lengths", 'int(ep_meta["length"])'),
        ),
        "G3": fmt(cite(L, "tasks_path = meta_dir", 'task["task_index"]: task["task"]')),
        "G4": fmt(
            cite(L, "stats_path = meta_dir", "please use gr00t/data/stats.py", extend=1),
            cite("factory", "generate_stats(", "generate_rel_stats("),
        ),
        "G5": fmt(cite("stats", "def _stale_features", 'for k in ("mean", "std", "min", "max", "q01", "q99")')),
        "G6": fmt(cite(L, "modality_path = meta_dir", "self.modality_meta = json.load(f)")),
        "G7": fmt(
            cite(L, 'self.data_path_pattern = self.info_meta["data_path"]'),
            cite(L, "parquet_filename = self.data_path_pattern.format(", "episode_index=episode_index", extend=1),
        ),
        "G8": fmt(cite(L, 'self.chunk_size = self.info_meta["chunks_size"]')),
        "G9": fmt(
            cite(L, 'self.video_path_pattern = self.info_meta.get("video_path")'),
            cite(L, "video_filename = self.video_path_pattern.format(", "episode_index=episode_index", after=video_fmt_start, extend=1),
        ),
        "G10": fmt(cite(L, 'original_key = self.modality_meta["video"][meta_key].get(', "not found in feature config", extend=1)),
        "G11": fmt(cite(L, "modality_info = self.modality_meta.get(modality_type", "Available groups:", extend=1)),
        "G12": fmt(
            cite(L, "DEFAULT_COLUMN_NAMES = {", '"action": "action"', extend=1),
            cite(L, 'group_info.get("original_key", DEFAULT_COLUMN_NAMES', "for strings and scalars"),
            cite(L, 'if self.modality_meta[modality][joint_key].get("original_key", None)', "][start_idx:end_idx]", extend=1),
        ),
        "G13": fmt(cite(L, 'assert key.startswith("annotation.")', 'original_key = self.modality_meta["annotation"]')),
        "G14": fmt(cite("repair", "def _required_episode_files", "return paths")),
        "G15": fmt(cite("stats", 'le_features = json.load(f)["features"]', "lowdim_features = [f for f in le_features")),
        "G16": fmt(
            cite("stats", "lowdim_features = [f for f in le_features"),
            cite(L, "for stat_type in self.stats[stats_key].keys():"),
        ),
    }


# Optional fields the loader tolerates being absent — never FAIL on these.
OPTIONAL_SOURCES = {
    "video_path": fmt(cite("loader", 'self.video_path_pattern = self.info_meta.get("video_path")')),
    "mask_path": fmt(cite("loader", 'self.mask_path_pattern = self.info_meta.get("mask_path")')),
    "fps": fmt(cite("loader", 'self.fps = self.info_meta.get("fps", 30)')),
    "relative_stats": fmt(cite("loader", "relative_stats_path = meta_dir", 'self.stats["relative_action"] = relative_stats')),
}

SOURCES: dict[str, str] = _build()

# Placeholders `.format()` is given by the loader, per pattern.
DATA_PATH_PLACEHOLDERS = frozenset({"episode_chunk", "episode_index"})
VIDEO_PATH_PLACEHOLDERS = frozenset({"episode_chunk", "video_key", "episode_index"})
STAT_TYPES = ("mean", "std", "min", "max", "q01", "q99")
DEFAULT_COLUMN_NAMES = {"state": "observation.state", "action": "action"}
