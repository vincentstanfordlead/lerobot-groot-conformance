"""L-series (LeRobot validity) and G-series (GR00T contract) checks, plus the verdict.

Checks run against a `DatasetView` — a file listing plus a way to read small meta files —
so the same code serves local directories (inspect_local) and HF repos (inspect_hub).

Every check runs; nothing short-circuits. A check that cannot run because its input is
missing returns passed=None ("skipped") with `blocked_by` naming the cause, rather than
double-counting the same root cause as a second failure.
"""
from __future__ import annotations

import io
import json
import string
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Protocol

from . import contract as C

# Plan §4 hard rule: never download a meta file larger than this. A file over the cap is
# SKIPPED(size), never passed and never failed.
MAX_META_BYTES = 2 * 1024 * 1024


@dataclass
class CheckResult:
    id: str
    level: str  # FAIL | WARN | INFO
    passed: Optional[bool]  # None = skipped (could not be evaluated)
    detail: str
    source: Optional[str] = None
    blocked_by: Optional[str] = None
    data: dict = field(default_factory=dict)


class DatasetView(Protocol):
    files: dict[str, int]  # posix path relative to dataset root -> size in bytes
    # Optional: False when the data/ + videos/ listing was capped (G14 then skips).
    # listing_complete: bool

    def read_text(self, rel: str) -> Optional[str]: ...


# ---------------------------------------------------------------- parsed context

class Ctx:
    """Lazily parsed meta files. Parse errors are kept, not raised."""

    def __init__(self, view: DatasetView):
        self.view = view
        self.files = view.files
        self.oversize: set[str] = set()
        self.info, self.info_err = self._json("meta/info.json")
        if self.info is not None and not isinstance(self.info, dict):
            self.info, self.info_err = None, "info.json is not a JSON object"
        self.modality, self.modality_err = self._json("meta/modality.json")
        if self.modality is not None and not isinstance(self.modality, dict):
            self.modality, self.modality_err = None, "modality.json is not a JSON object"
        self.stats, self.stats_err = self._json("meta/stats.json")
        self.episodes, self.episodes_err = self._jsonl("meta/episodes.jsonl")
        self.tasks, self.tasks_err = self._jsonl("meta/tasks.jsonl")

    def _over_cap(self, rel: str) -> Optional[str]:
        if self.files[rel] > MAX_META_BYTES:
            self.oversize.add(rel)
            return f"SKIPPED(size): {rel} is {self.files[rel]:,} B > {MAX_META_BYTES:,} B cap"
        return None

    def _json(self, rel: str) -> tuple[Any, Optional[str]]:
        if rel not in self.files:
            return None, f"{rel} not found"
        if self._over_cap(rel):
            return None, self._over_cap(rel)
        text = self.view.read_text(rel)
        if text is None:
            return None, f"{rel} not readable (size cap or fetch error)"
        try:
            return json.loads(text), None
        except json.JSONDecodeError as e:
            return None, f"{rel} does not parse: {e}"

    def _jsonl(self, rel: str) -> tuple[Optional[list], Optional[str]]:
        if rel not in self.files:
            return None, f"{rel} not found"
        if self._over_cap(rel):
            return None, self._over_cap(rel)
        text = self.view.read_text(rel)
        if text is None:
            return None, f"{rel} not readable (size cap or fetch error)"
        rows = []
        # Mirror the loader: `for line in f: json.loads(line)` — a blank line mid-file raises.
        for n, line in enumerate(io.StringIO(text), 1):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                return None, f"{rel} line {n} does not parse: {e}"
        return rows, None

    @property
    def features(self) -> dict:
        f = (self.info or {}).get("features")
        return f if isinstance(f, dict) else {}

    @property
    def video_features(self) -> list[str]:
        return [k for k, v in self.features.items() if isinstance(v, dict) and v.get("dtype") == "video"]

    def is_v3_layout(self) -> bool:
        info = self.info or {}
        pats = f"{info.get('data_path', '')} {info.get('video_path', '')}"
        return (
            str(info.get("codebase_version", "")).startswith("v3")
            or "file_index" in pats
            or "chunk_index" in pats
            or "meta/tasks.parquet" in self.files
            or any(p.startswith("meta/episodes/") for p in self.files)
        )


def _placeholders(pattern: str) -> set[str]:
    names = set()
    for _, field_name, _, _ in string.Formatter().parse(pattern):
        if field_name is not None:
            names.add(field_name.split(".")[0].split("[")[0])
    return names


def _res(id_, level, passed, detail, *, src=True, **kw) -> CheckResult:
    source = C.SOURCES.get(id_) if src else None
    return CheckResult(id_, level, passed, detail, source=source, **kw)


def _skip(id_, level, why, blocked_by) -> CheckResult:
    return _res(id_, level, None, f"skipped: {why}", blocked_by=blocked_by)


# ---------------------------------------------------------------- L-series

def run_l_checks(x: Ctx) -> list[CheckResult]:
    out: list[CheckResult] = []
    files = x.files
    has_meta = any(p.startswith("meta/") for p in files)
    out.append(CheckResult("L1", "WARN", has_meta and x.info is not None,
                           "meta/info.json present and parses" if x.info is not None
                           else (x.info_err if has_meta else "no meta/ directory")))
    if x.info is None:
        return out  # NOT_LEROBOT — the only structural failure that stops the run
    info = x.info
    ver = info.get("codebase_version")
    out.append(CheckResult("L2", "INFO", ver is not None, f"codebase_version={ver!r}", data={"codebase_version": ver}))
    has_parquet = any(p.startswith("data/") and p.endswith(".parquet") for p in files)
    out.append(CheckResult("L3", "INFO", has_parquet, "data/ contains parquet" if has_parquet else "no parquet under data/"))
    has_videos = any(p.startswith("videos/") for p in files)
    out.append(CheckResult("L4", "INFO", has_videos, "videos/ present" if has_videos else "no videos/ (state-only dataset, not a defect)"))
    ep_layout = "jsonl" if "meta/episodes.jsonl" in files else (
        "parquet" if any(p.startswith("meta/episodes/") and p.endswith(".parquet") for p in files) else None)
    out.append(CheckResult("L5", "WARN", ep_layout is not None, f"episode metadata layout: {ep_layout}", data={"layout": ep_layout}))
    task_layout = "jsonl" if "meta/tasks.jsonl" in files else ("parquet" if "meta/tasks.parquet" in files else None)
    out.append(CheckResult("L6", "WARN", task_layout is not None, f"task metadata layout: {task_layout}", data={"layout": task_layout}))
    stats_layout = "stats.json" if "meta/stats.json" in files else (
        "episodes_stats.jsonl" if "meta/episodes_stats.jsonl" in files else None)
    out.append(CheckResult("L7", "WARN", stats_layout is not None, f"stats layout: {stats_layout}", data={"layout": stats_layout}))
    feats = x.features
    def dim(k):
        s = (feats.get(k) or {}).get("shape") if isinstance(feats.get(k), dict) else None
        return s[0] if isinstance(s, list) and s else None
    out.append(CheckResult("L8", "WARN", bool(feats),
                           f"state dim={dim('observation.state')}, action dim={dim('action')}, "
                           f"cameras={len(x.video_features)}, fps={info.get('fps')}",
                           data={"state_dim": dim("observation.state"), "action_dim": dim("action"),
                                 "n_cameras": len(x.video_features), "fps": info.get("fps")}))
    named = {k: bool(isinstance(feats.get(k), dict) and feats[k].get("names")) for k in ("observation.state", "action")}
    out.append(CheckResult("L9", "INFO", all(named.values()), f"names present: {named}", data=named))
    if not x.video_features:
        out.append(CheckResult("L10", "INFO", True, "no camera features"))
    elif not has_videos:
        out.append(CheckResult("L10", "INFO", None, "videos/ absent; cannot verify camera dirs"))
    else:
        v3 = x.is_v3_layout()
        missing = []
        for k in x.video_features:
            # v2.x videos/chunk-XXX/{key}/ ; v3.0 videos/{key}/chunk-XXX/
            hit = any(f"/{k}/" in f"/{p}" and p.startswith("videos/") for p in files)
            if not hit:
                missing.append(k)
        if missing and not getattr(x.view, "listing_complete", True):
            out.append(CheckResult("L10", "INFO", None,
                                   f"layout={'v3.0' if v3 else 'v2.x'}; listing capped, not seen: {missing}"))
        else:
            out.append(CheckResult("L10", "INFO", not missing,
                                   f"layout={'v3.0' if v3 else 'v2.x'}; missing camera dirs: {missing}"))
    # L11: episode bookkeeping agrees with itself. GR00T reads episodes.jsonl, not total_episodes,
    # so a mismatch is a LeRobot-validity warning, not a GR00T blocker.
    total = info.get("total_episodes")
    if x.episodes is None:
        out.append(CheckResult("L11", "WARN", None, f"episodes.jsonl unavailable ({x.episodes_err}); "
                               "episode count not compared"))
    elif not isinstance(total, int):
        out.append(CheckResult("L11", "WARN", None, "info.json:total_episodes absent; nothing to compare"))
    else:
        out.append(CheckResult("L11", "WARN", len(x.episodes) == total,
                               f"episodes.jsonl lines={len(x.episodes)}, info.json:total_episodes={total}",
                               data={"episodes_lines": len(x.episodes), "total_episodes": total}))
    # L12: fps declared. Absent fps is not an error: the loader silently assumes 30.
    fps = info.get("fps")
    fps_ok = isinstance(fps, (int, float)) and not isinstance(fps, bool) and fps > 0
    out.append(CheckResult("L12", "WARN", fps_ok,
                           f"fps={fps!r}" if fps_ok else f"fps={fps!r}: the loader silently assumes 30",
                           source=C.OPTIONAL_SOURCES["fps"], data={"fps": fps}))
    return out


# ---------------------------------------------------------------- G-series

def g1(x: Ctx) -> CheckResult:
    ok = x.info is not None
    return _res("G1", "FAIL", ok, "meta/info.json present and parses" if ok else x.info_err)


def g2(x: Ctx) -> CheckResult:
    if "meta/episodes.jsonl" in x.oversize:
        return _skip("G2", "FAIL", x.episodes_err + " (file exists; `length` per line unverified)", "size")
    if x.episodes is None:
        return _res("G2", "FAIL", False, x.episodes_err)
    bad = [i for i, e in enumerate(x.episodes) if not isinstance(e, dict) or "length" not in e]
    if bad:
        return _res("G2", "FAIL", False, f"{len(bad)} episode line(s) lack `length` (first: line {bad[0] + 1})")
    return _res("G2", "FAIL", True, f"{len(x.episodes)} episodes, all with `length`")


def g3(x: Ctx) -> CheckResult:
    if "meta/tasks.jsonl" in x.oversize:
        return _skip("G3", "FAIL", x.tasks_err + " (file exists; lines unverified)", "size")
    if x.tasks is None:
        return _res("G3", "FAIL", False, x.tasks_err)
    bad = [i for i, t in enumerate(x.tasks) if not isinstance(t, dict) or "task_index" not in t or "task" not in t]
    if bad:
        return _res("G3", "FAIL", False, f"{len(bad)} task line(s) lack task_index/task (first: line {bad[0] + 1})")
    return _res("G3", "FAIL", True, f"{len(x.tasks)} tasks OK")


def g4(x: Ctx) -> CheckResult:
    ok = "meta/stats.json" in x.files
    detail = "meta/stats.json present" if ok else (
        "meta/stats.json absent — asserts only for entrypoints bypassing the training factory; "
        "training regenerates it")
    if not ok and "meta/episodes_stats.jsonl" in x.files:
        detail += " (ships episodes_stats.jsonl, which GR00T does not read)"
    return _res("G4", "WARN", ok, detail)


def g5(x: Ctx) -> CheckResult:
    if x.stats is None:
        return _skip("G5", "WARN", x.stats_err, "size" if "meta/stats.json" in x.oversize else "G4")
    if not isinstance(x.stats, dict):
        return _res("G5", "WARN", False, "stats.json is not a JSON object")
    float_feats = [k for k, v in x.features.items()
                   if isinstance(v, dict) and str(v.get("dtype", "")).startswith("float")]
    stale = []
    for k in float_feats:
        s = x.stats.get(k)
        if not isinstance(s, dict) or any(t not in s for t in C.STAT_TYPES):
            stale.append(k)
    return _res("G5", "WARN", not stale,
                "all float features carry mean/std/min/max/q01/q99" if not stale
                else f"stale (GR00T will recompute): {stale}", data={"stale": stale})


def g6(x: Ctx) -> CheckResult:
    ok = x.modality is not None
    return _res("G6", "FAIL", ok, "meta/modality.json present and parses" if ok else x.modality_err)


def _fmt_ok(pattern: Any, allowed: frozenset, sample: dict) -> tuple[bool, str]:
    if not isinstance(pattern, str):
        return False, f"pattern is {type(pattern).__name__}, not a string"
    ph = _placeholders(pattern)
    extra = ph - allowed
    if extra:
        return False, f"placeholders {sorted(extra)} not supplied by the loader (has {sorted(allowed)}); would KeyError"
    try:
        pattern.format(**sample)
    except (KeyError, IndexError, ValueError) as e:
        return False, f".format() raises {type(e).__name__}: {e}"
    return True, f"placeholders {sorted(ph)}"


def g7(x: Ctx) -> CheckResult:
    if x.info is None:
        return _skip("G7", "FAIL", "info.json unavailable", "G1")
    if "data_path" not in x.info:
        return _res("G7", "FAIL", False, "info.json:data_path missing (KeyError)")
    ok, why = _fmt_ok(x.info["data_path"], C.DATA_PATH_PLACEHOLDERS, {"episode_chunk": 0, "episode_index": 0})
    return _res("G7", "FAIL", ok, f"data_path={x.info['data_path']!r}: {why}")


def g8(x: Ctx) -> CheckResult:
    if x.info is None:
        return _skip("G8", "FAIL", "info.json unavailable", "G1")
    ok = "chunks_size" in x.info
    return _res("G8", "FAIL", ok, "chunks_size present" if ok else "info.json:chunks_size missing (KeyError)")


def _uses_video(x: Ctx) -> bool:
    if x.video_features:
        return True
    v = (x.modality or {}).get("video")
    return isinstance(v, dict) and bool(v)


def g9(x: Ctx) -> CheckResult:
    if x.info is None:
        return _skip("G9", "FAIL", "info.json unavailable", "G1")
    if not _uses_video(x):
        return _res("G9", "FAIL", True, "no video used; video_path not required")
    pat = x.info.get("video_path")
    if pat is None:
        return _res("G9", "FAIL", False, "videos are used but info.json:video_path is missing")
    ok, why = _fmt_ok(pat, C.VIDEO_PATH_PLACEHOLDERS,
                      {"episode_chunk": 0, "video_key": "k", "episode_index": 0})
    return _res("G9", "FAIL", ok, f"video_path={pat!r}: {why}")


def _video_entries(x: Ctx):
    """(meta_key, original_key or None-if-malformed) per modality.json video entry."""
    v = x.modality.get("video")
    for k, e in v.items():
        if isinstance(e, dict):
            yield k, e.get("original_key", f"observation.images.{k}")
        else:
            yield k, None


def g10(x: Ctx) -> CheckResult:
    if x.modality is None:
        return _skip("G10", "FAIL", "modality.json unavailable", "G6")
    v = x.modality.get("video")
    if not isinstance(v, dict) or not v:
        if x.video_features:
            return _res("G10", "FAIL", False,
                        f"modality.json has no `video` section but features declare cameras {x.video_features} (KeyError)")
        return _res("G10", "FAIL", True, "no cameras declared; no video section needed")
    bad = [(k, ok_) for k, ok_ in _video_entries(x) if ok_ is None or ok_ not in x.features]
    if bad:
        return _res("G10", "FAIL", False, f"video entries whose original_key is not in features: {bad}")
    return _res("G10", "FAIL", True, f"{len(v)} video entries resolve to features")


def g11(x: Ctx) -> CheckResult:
    if x.modality is None:
        return _skip("G11", "FAIL", "modality.json unavailable", "G6")
    empty = [s for s in ("state", "action")
             if not isinstance(x.modality.get(s), dict) or not x.modality.get(s)]
    if empty:
        return _res("G11", "FAIL", False,
                    f"modality.json sections missing/empty: {empty}. SILENT: requested groups are dropped "
                    f"with a print() and training continues with fewer dims",
                    data={"silent": True})
    return _res("G11", "FAIL", True,
                "non-empty state and action sections (necessary condition only; sufficiency depends on the recipe)")


def g12(x: Ctx) -> CheckResult:
    if x.modality is None:
        return _skip("G12", "FAIL", "modality.json unavailable", "G6")
    problems, checked = [], 0
    for section in ("state", "action"):
        groups = x.modality.get(section)
        if not isinstance(groups, dict) or not groups:
            continue  # G11's job
        by_col: dict[str, list[tuple[str, int, int]]] = {}
        for name, g in groups.items():
            if not isinstance(g, dict) or not isinstance(g.get("start"), int) or not isinstance(g.get("end"), int) \
                    or isinstance(g.get("start"), bool) or isinstance(g.get("end"), bool):
                problems.append(f"{section}.{name}: start/end missing or not integers")
                continue
            col = g.get("original_key", C.DEFAULT_COLUMN_NAMES[section])
            by_col.setdefault(col, []).append((name, g["start"], g["end"]))
        for col, gs in by_col.items():
            feat = x.features.get(col)
            shape = feat.get("shape") if isinstance(feat, dict) else None
            if not isinstance(shape, list) or len(shape) != 1:
                if feat is None:
                    problems.append(f"{section}: column {col!r} not in features")
                continue  # scalar/multi-dim column: loader skips slicing (L335-338)
            d = shape[0]
            checked += 1
            covered = set()
            for name, s, e in gs:
                if not (0 <= s < e <= d):
                    problems.append(f"{section}.{name}: [{s},{e}) outside [0,{d}) of {col!r} — numpy truncates silently")
                else:
                    covered.update(range(s, e))
            gaps = sorted(set(range(d)) - covered)
            if gaps and not any("outside" in p for p in problems if p.startswith(f"{section}.")):
                problems.append(f"{section}: groups leave dims {gaps} of {col!r} (dim {d}) uncovered")
    if problems:
        return _res("G12", "FAIL", False, "; ".join(problems), data={"silent": True})
    if not checked:
        return _skip("G12", "FAIL", "no state/action groups to check", "G11")
    return _res("G12", "FAIL", True, "all groups in range and cover their columns")


def g13(x: Ctx) -> CheckResult:
    if x.modality is None:
        return _skip("G13", "FAIL", "modality.json unavailable", "G6")
    ann = x.modality.get("annotation")
    if ann is None:
        return _res("G13", "FAIL", True, "no annotation section (which annotations are required depends on the recipe)")
    if not isinstance(ann, dict):
        return _res("G13", "FAIL", False, "annotation section is not an object")
    bad = []
    for sub, e in ann.items():
        key = e.get("original_key", f"annotation.{sub}") if isinstance(e, dict) else None
        if key is None or key not in x.features:
            bad.append((sub, key))
    return _res("G13", "FAIL", not bad,
                "annotation original_keys all in features" if not bad
                else f"annotation entries whose column is not in features: {bad}")


def _video_keys_for_g14(x: Ctx) -> list[str]:
    v = (x.modality or {}).get("video")
    if isinstance(v, dict) and v:
        return [str((e.get("original_key") or k)) if isinstance(e, dict) else str(k) for k, e in v.items()]
    return x.video_features


def g14(x: Ctx) -> CheckResult:
    blockers = [(i, r) for i, r in (("G2", g2(x)), ("G7", g7(x)), ("G8", g8(x))) if r.passed is not True]
    if blockers:
        why = "SKIPPED(size): episodes.jsonl over cap" if "meta/episodes.jsonl" in x.oversize else \
            f"needs episodes.jsonl, data_path, chunks_size ({blockers[0][0]} unresolved)"
        return _skip("G14", "FAIL", why, blockers[0][0])
    if not getattr(x.view, "listing_complete", True):
        return _skip("G14", "FAIL", "SKIPPED(size): data/ + videos/ listing capped; cannot prove files present", "size")
    info = x.info
    try:
        chunk = int(info["chunks_size"])
        idxs = [int(e.get("episode_index", i)) for i, e in enumerate(x.episodes)]
    except (TypeError, ValueError, AttributeError):
        return _res("G14", "FAIL", False, "chunks_size or episode_index not an integer")
    vkeys = _video_keys_for_g14(x) if info.get("video_path") else []
    missing = []
    for ep in idxs:
        want = [info["data_path"].format(episode_chunk=ep // chunk, episode_index=ep)]
        for vk in vkeys:
            want.append(info["video_path"].format(episode_chunk=ep // chunk, video_key=vk, episode_index=ep))
        missing.extend(p for p in want if p not in x.files)
    if missing:
        eps = sorted({i for i in idxs if any(f"{i:06d}" in m for m in missing)})
        return _res("G14", "FAIL", False, f"{len(missing)} required file(s) absent across {len(eps)} episode(s); e.g. {missing[0]}",
                    data={"episodes_affected": eps, "n_missing": len(missing)})
    return _res("G14", "FAIL", True, f"all required files present for {len(idxs)} episodes")


def g15(x: Ctx) -> CheckResult:
    if x.info is None:
        return _skip("G15", "FAIL", "info.json unavailable", "G1")
    feats = x.info.get("features")
    if not isinstance(feats, dict):
        return _res("G15", "FAIL", False, "info.json:features missing; generate_stats raises KeyError")
    bad = [k for k, v in feats.items() if not isinstance(v, dict) or "dtype" not in v]
    return _res("G15", "FAIL", not bad, f"{len(feats)} features, all with dtype" if not bad
                else f"features without dtype (generate_stats raises KeyError): {bad}")


def g16(x: Ctx) -> CheckResult:
    if x.info is None:
        return _skip("G16", "FAIL", "info.json unavailable", "G1")
    cols = set(C.DEFAULT_COLUMN_NAMES.values())
    for section in ("state", "action"):
        groups = (x.modality or {}).get(section)
        if isinstance(groups, dict):
            cols |= {g["original_key"] for g in groups.values() if isinstance(g, dict) and g.get("original_key")}
    present = {c: x.features[c] for c in sorted(cols) if isinstance(x.features.get(c), dict)}
    if not present:
        return _skip("G16", "FAIL", f"none of {sorted(cols)} in features", "features")
    bad = {c: f.get("dtype") for c, f in present.items() if "float" not in str(f.get("dtype", ""))}
    return _res("G16", "FAIL", not bad, f"float dtype: {sorted(present)}" if not bad
                else f"non-float state/action columns get no stats, so the stats lookup raises KeyError: {bad}")


G_CHECKS = [g1, g2, g3, g4, g5, g6, g7, g8, g9, g10, g11, g12, g13, g14, g15, g16]


# ---------------------------------------------------------------- verdict

def verdict(results: list[CheckResult], x: Ctx) -> dict:
    by = {r.id: r for r in results}
    failed = {i for i, r in by.items() if r.id.startswith("G") and r.level == "FAIL" and r.passed is False}
    if by["L1"].passed is not True:
        return {"verdict": "NOT_LEROBOT", "steps": [], "failed_fail_level": sorted(failed)}
    structural = failed & {"G2", "G3", "G7", "G8", "G9"}
    modality_bad = bool(failed & {"G10", "G11", "G12", "G13"})
    steps: list[str] = []
    # A v3.0 layout is a known format gap with an NVIDIA converter (DOWNCONVERT). No episode
    # data at all (no parquet under data/: metadata-only uploads), any other structural failure,
    # or a dtype the stats code cannot handle has no tool (BLOCKED).
    no_data = by["L3"].passed is False if "L3" in by else False
    if no_data or (structural and not x.is_v3_layout()) or failed & {"G15", "G16"}:
        steps.append("BLOCKED")
    elif structural:
        steps.append("DOWNCONVERT")
    if "G6" in failed:
        steps.append("MODALITY")
    elif modality_bad:
        steps.append("INCONSISTENT_MODALITY")
    primary = {"DOWNCONVERT": "NEEDS_DOWNCONVERT", "BLOCKED": "BLOCKED",
               "MODALITY": "NEEDS_MODALITY", "INCONSISTENT_MODALITY": "INCONSISTENT_MODALITY"}
    if steps:
        v = primary[steps[0]]
    else:
        v = "READY"
    if "G14" in failed:
        steps.append("REPAIR")  # stacks with any other verdict
        if v == "READY":
            v = "NEEDS_REPAIR"
    return {"verdict": v, "steps": steps, "failed_fail_level": sorted(failed)}


def run_all(view: DatasetView) -> dict:
    x = Ctx(view)
    results = run_l_checks(x)
    for fn in G_CHECKS:
        results.append(fn(x))
    v = verdict(results, x)
    # FAIL-level checks that could not run because of the 2 MB cap or a capped listing: the
    # verdict ignores them, so the report must say so rather than imply they passed.
    v["unverified_size"] = [r.id for r in results
                            if r.level == "FAIL" and r.passed is None and r.blocked_by == "size"
                            or (r.id == "G14" and r.passed is None and "SKIPPED(size)" in r.detail)]
    return {**v, "checks": [asdict(r) for r in results],
            "stats_usable_as_is": bool(next(r for r in results if r.id == "G5").passed),
            "groot_sha": C.GROOT_SHA}
