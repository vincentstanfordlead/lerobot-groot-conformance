"""Audit an HF dataset repo by id — metadata only, no parquet/video payload (plan §4).

Requests per dataset (all pinned to the repo commit sha resolved in step 1):
  1. dataset_info(expand=sha, gated, private, disabled, lastModified, usedStorage)
  2. tree /            (non-recursive: which of meta/, data/, videos/ exist; empty repo?)
  3. tree meta/        (recursive, with sizes)
  4. tree data/, videos/ (recursive, with sizes, capped per directory)
  5. resolve meta/{info.json, episodes.jsonl, tasks.jsonl, modality.json, stats.json}
     — only the ones present in the listing, only if ≤ 2 MB by the listing size, and the
     body read is capped again at 2 MB in case the listing lied.

Anything that stops the audit from observing the repo (gated, private, 404, disabled,
empty, rate-limited, network) raises `FetchError`; the batch driver files those in a
separate exclusion bucket that never enters the denominator (plan §6 Phase 3).

    .venv/bin/python -m conformance.inspect_hub youliangtan/tictac-bot [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Optional, TypeVar

import huggingface_hub
from huggingface_hub import HfApi, hf_hub_url
from huggingface_hub.errors import (DisabledRepoError, GatedRepoError, HfHubHTTPError,
                                    RemoteEntryNotFoundError, RepositoryNotFoundError)

from . import contract as C
from .checks import MAX_META_BYTES, run_all

META_FILES = ["meta/info.json", "meta/episodes.jsonl", "meta/tasks.jsonl",
              "meta/modality.json", "meta/stats.json"]
LIST_CAP = 200_000       # entries per data/ and videos/; enough for ~50k episodes x 3 cameras
LIST_CAP_NO_G14 = 5_000  # when G14 can't run anyway (no/oversize episodes.jsonl): L3/L4/L10 only
NESTED_SCAN_REQUESTS = 25  # non-recursive listings spent looking for nested */meta/
NESTED_SCAN_DEPTH = 6      # e.g. zero-latency/<robot>/dagger/<policy>/<run>/<round>/lerobot
NESTED_FALLBACK_FOLDERS = 5
NESTED_FALLBACK_ENTRIES = 3_000
RETRIES = 5
RATE_LIMIT_MIN_WAIT = 60.0  # s; grows linearly per attempt → up to ~10 min total before giving up
UA = "lerobot-groot-conformance/phase3 (metadata-only audit)"

T = TypeVar("T")


class FetchError(Exception):
    """The repo could not be observed. `kind` is the exclusion-bucket label."""

    def __init__(self, kind: str, detail: str):
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail = kind, detail


def _status(e: Exception) -> Optional[int]:
    r = getattr(e, "response", None)
    return getattr(r, "status_code", None) or getattr(e, "code", None)


def _retry(fn: Callable[[], T], what: str) -> T:
    """Retry 429/5xx/network with exponential backoff; classify everything else."""
    delay = 2.0
    for attempt in range(RETRIES):
        try:
            return fn()
        except GatedRepoError as e:
            raise FetchError("gated", f"{what}: {e}".splitlines()[0])
        except DisabledRepoError as e:
            raise FetchError("disabled", f"{what}: {e}".splitlines()[0])
        except RepositoryNotFoundError as e:
            raise FetchError("not_found_or_private", f"{what}: {e}".splitlines()[0])
        except (HfHubHTTPError, urllib.error.HTTPError) as e:
            code = _status(e)
            if code in (401, 403):
                raise FetchError("gated", f"{what}: HTTP {code}")
            if code == 404:
                raise
            if code != 429 and not (code and code >= 500):
                raise FetchError("http_error", f"{what}: HTTP {code}")
            retry_after = getattr(getattr(e, "response", None), "headers", None) or getattr(e, "headers", None) or {}
            wait = float(retry_after.get("Retry-After", delay)) if hasattr(retry_after, "get") else delay
            kind = "rate_limited" if code == 429 else "server_error"
            if code == 429:
                # HF's anonymous window is ~5 min; short backoffs just burn the retries.
                wait = max(wait, RATE_LIMIT_MIN_WAIT * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            wait, kind = delay, "network"
            code = type(e).__name__
        if attempt == RETRIES - 1:
            raise FetchError(kind, f"{what}: gave up after {RETRIES} tries ({code})")
        time.sleep(min(wait, 300))
        delay *= 2
    raise AssertionError("unreachable")


class HubView:
    """DatasetView over an HF dataset repo: file listing with sizes + capped meta reads."""

    def __init__(self, repo_id: str, token: Optional[str] = None, api: Optional[HfApi] = None):
        self.repo_id = repo_id
        self.token = token
        self.api = api or HfApi(token=token)
        self.n_requests = 0
        self.bytes_downloaded = 0
        self.files: dict[str, int] = {}
        self.listing_complete = True
        self._text: dict[str, Optional[str]] = {}

        self.n_requests += 1
        info = _retry(lambda: self.api.dataset_info(
            repo_id, expand=["sha", "gated", "private", "disabled", "lastModified", "usedStorage"]),
            "dataset_info")
        if info.disabled:
            raise FetchError("disabled", "repo disabled")
        self.sha = info.sha
        self.gated = info.gated
        self.last_modified = info.last_modified.isoformat() if info.last_modified else None
        self.used_storage = info.used_storage

        root = self._tree(None, recursive=False, folders=True)
        if not root:
            raise FetchError("empty_repo", "no files at the repo root")
        top = {e.path for e in root}
        for e in root:
            if getattr(e, "size", None) is not None:
                self.files[e.path] = e.size
        if "meta" in top:
            for e in self._tree("meta", recursive=True):
                self.files[e.path] = e.size

        ep = self.files.get("meta/episodes.jsonl")
        cap = LIST_CAP if ep is not None and ep <= MAX_META_BYTES else LIST_CAP_NO_G14
        # Cap per directory, so a huge data/ can't hide videos/ from L4/L10.
        seen = 0
        for d in ("data", "videos"):
            if d not in top:
                continue
            entries = self._tree(d, recursive=True, stop_after=cap)
            if len(entries) > cap:
                self.listing_complete = False
            for e in entries[:cap]:
                self.files[e.path] = e.size
            seen += min(len(entries), cap)
        self.listing_entries = seen

        # No root meta/: is this a container of LeRobot datasets in subfolders (Kai0/Task_A/...)?
        # Report-only; the root is still NOT_LEROBOT, because GR00T is pointed at one dataset dir.
        self.nested_roots: list[str] = []
        self.nested_scan_complete = True
        if "meta" not in top:
            # Breadth-first over non-recursive listings: a recursive listing of Task_A/ burns its
            # cap on Task_A/data/ before it ever reaches Task_A/meta/.
            queue = [(e.path, 1) for e in sorted(root, key=lambda e: e.path) if not hasattr(e, "size")]
            budget = NESTED_SCAN_REQUESTS
            while queue:
                if budget == 0:
                    self.nested_scan_complete = False
                    break
                folder, depth = queue.pop(0)
                budget -= 1
                kids = self._tree(folder, recursive=False, folders=True)
                names = {e.path.rsplit("/", 1)[-1]: e for e in kids}
                if "meta" in names and not hasattr(names["meta"], "size"):
                    self.nested_roots.append(folder)  # a LeRobot root; don't descend further
                    continue
                if depth < NESTED_SCAN_DEPTH:
                    queue += [(e.path, depth + 1) for e in sorted(kids, key=lambda e: e.path)
                              if not hasattr(e, "size")]
            if not self.nested_roots:
                # Fallback for deep/wide trees BFS runs out of budget on: recursive listing of the
                # first few top folders, looking for .../meta/info.json at any depth.
                for f in [e.path for e in sorted(root, key=lambda e: e.path)
                          if not hasattr(e, "size")][:NESTED_FALLBACK_FOLDERS]:
                    entries = self._tree(f, recursive=True, stop_after=NESTED_FALLBACK_ENTRIES)
                    self.nested_roots += [e.path[:-len("/meta/info.json")] for e in entries
                                          if e.path.endswith("/meta/info.json")]
            self.nested_roots.sort()

        # Prefetch the meta files inside the size cap, so fetch errors surface here (and go to
        # the exclusion bucket) rather than as a check failure inside run_all.
        for rel in META_FILES:
            if rel in self.files and self.files[rel] <= MAX_META_BYTES:
                self._text[rel] = self._get(rel)

    def _tree(self, path: Optional[str], recursive: bool, stop_after: Optional[int] = None,
              folders: bool = False) -> list:
        def go():
            out = []
            it = self.api.list_repo_tree(self.repo_id, path_in_repo=path, recursive=recursive,
                                         repo_type="dataset", revision=self.sha)
            for e in it:
                if not folders and not hasattr(e, "size"):
                    continue  # RepoFolder
                out.append(e)
                if stop_after is not None and len(out) >= stop_after + 1:
                    break
            return out
        try:
            out = _retry(go, f"tree {path or '/'}")
        except (RemoteEntryNotFoundError, HfHubHTTPError) as e:
            if _status(e) == 404:
                return []
            raise FetchError("http_error", f"tree {path}: {e}".splitlines()[0])
        # Paging cost ≈ one request per 1000 entries.
        self.n_requests += 1 + len(out) // 1000
        return out

    def _get(self, rel: str) -> str:
        url = hf_hub_url(self.repo_id, rel, repo_type="dataset", revision=self.sha)
        headers = {"User-Agent": UA}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        def go():
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                cl = r.headers.get("content-length")
                if cl is not None and int(cl) > MAX_META_BYTES:
                    raise FetchError("oversize_body", f"{rel}: content-length {cl} > cap despite listing size")
                body = r.read(MAX_META_BYTES + 1)
                if len(body) > MAX_META_BYTES:
                    raise FetchError("oversize_body", f"{rel}: body exceeds cap despite listing size")
                return body
        try:
            body = _retry(go, rel)
        except urllib.error.HTTPError as e:  # 404 on a file the listing claimed
            raise FetchError("http_error", f"{rel}: HTTP {e.code} on a listed file")
        self.n_requests += 1
        self.bytes_downloaded += len(body)
        return body.decode("utf-8", errors="replace")

    def read_text(self, rel: str) -> Optional[str]:
        if self.files.get(rel, 0) > MAX_META_BYTES:
            return None
        if rel not in self._text:
            self._text[rel] = self._get(rel)
        return self._text[rel]


def _sizes(files: dict[str, int]) -> dict:
    return {
        "parquet_bytes_listed": sum(s for p, s in files.items() if p.startswith("data/")),
        "video_bytes_listed": sum(s for p, s in files.items() if p.startswith("videos/")),
    }


def inspect_hub(repo_id: str, token: Optional[str] = None, api: Optional[HfApi] = None) -> dict:
    t0 = time.time()
    view = HubView(repo_id, token=token, api=api)
    report = run_all(view)
    now = datetime.now(timezone.utc)
    report.update(
        dataset=repo_id,
        audit_utc=now.isoformat(timespec="seconds"),
        audit_date=now.date().isoformat(),
        groot_sha=C.GROOT_SHA,
        huggingface_hub_version=huggingface_hub.__version__,
        repo_sha=view.sha,
        repo_last_modified=view.last_modified,
        repo_gated=view.gated,
        fetch={
            "n_requests": view.n_requests,
            "bytes_downloaded": view.bytes_downloaded,
            "listing_entries_data_videos": view.listing_entries,
            "listing_complete": view.listing_complete,
            "oversize_meta": sorted(p for p in META_FILES if view.files.get(p, 0) > MAX_META_BYTES),
            "wall_s": round(time.time() - t0, 2),
            "authenticated": bool(token),
        },
        # Fix-cost inputs (plan §5.3): usedStorage is the repo total incl. LFS history.
        size={"used_storage_bytes": view.used_storage, **_sizes(view.files)},
    )
    if report["verdict"] == "NOT_LEROBOT":
        # nested_datasets: LeRobot datasets in subfolders (audit unit mismatch, not a format defect)
        # other: no meta/info.json anywhere we looked (another format, or a malformed layout)
        report["not_lerobot_reason"] = "nested_datasets" if view.nested_roots else "other"
        report["nested_datasets"] = {
            "n_found": len(view.nested_roots), "scan_complete": view.nested_scan_complete,
            "examples": view.nested_roots[:5]}
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GR00T-loadability linter for an HF dataset repo (metadata only)")
    ap.add_argument("repo_id")
    ap.add_argument("--json", action="store_true", help="emit the full JSON report")
    args = ap.parse_args(argv)
    try:
        r = inspect_hub(args.repo_id, token=os.environ.get("HF_TOKEN"))
    except FetchError as e:
        print(f"EXCLUDED ({e.kind}): {e.detail}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"verdict: {r['verdict']}   steps: {r['steps']}   (GR00T @{C.GROOT_SHA[:7]}, "
              f"repo @{r['repo_sha'][:7]}, {r['fetch']['n_requests']} requests)")
        for c in r["checks"]:
            mark = {True: "pass", False: "FAIL" if c["level"] == "FAIL" else c["level"], None: "skip"}[c["passed"]]
            print(f"  {c['id']:<4}{mark:<5} {c['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
