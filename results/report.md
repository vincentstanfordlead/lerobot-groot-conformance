# Conformance report: public LeRobot datasets vs Isaac-GR00T's dataset loader

GR00T pin `51d4c89` · audit dates 2026-09-29 · huggingface_hub 2.0.0 · audited **562** · excluded (fetch failures, outside the denominator) **0**

**Every rate below is per stratum with its own n. There is no pooled pass rate.** S-curated is a census; S-popular and S-recent are purposive top-100 sets; only S-tail is a random sample (seed 20260928), so only S-tail carries a confidence interval. Verdicts are from **static metadata checks only**: no dataset was loaded with GR00T's loader, so `READY` means *passes all static checks*, not *GR00T-ready*. Individual datasets are not named in this report; ids are in `summary.csv`.

## 1. Distance-to-ready, per stratum (headline)

| verdict | S-curated (n=162) | S-popular (n=100) | S-recent (n=100) | S-tail (n=200) | who fixes it |
|---|---|---|---|---|---|
| `READY` | 0 (0%) | 0 (0%) | 4 (4%) | 0 (0%) | passes all static checks |
| `READY†` | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) | passes, but G2/G3/G14 not checkable under 2 MB cap |
| `NEEDS_REPAIR` | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | converter (lossy: drops episodes) |
| `NEEDS_MODALITY` | 35 (22%) | 58 (58%) | 3 (3%) | 61 (30%) | add `meta/modality.json`: someone who knows the robot (no tool) |
| `NEEDS_DOWNCONVERT` | 127 (78%) | 30 (30%) | 92 (92%) | 116 (58%) | `convert_v3_to_v2.py`, then add `modality.json` (2 steps) |
| `INCONSISTENT_MODALITY` | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) | producer: fix `modality.json` (can fail silently) |
| `BLOCKED` | 0 (0%) | 2 (2%) | 0 (0%) | 22 (11%) | no episode data, or a structural failure outside the v3.0 gap; no tool |
| `NOT_LEROBOT: container` | 0 (0%) | 7 (7%) | 1 (1%) | 0 (0%) | n/a - audit-unit mismatch, sub-datasets not audited |
| `NOT_LEROBOT: other` | 0 (0%) | 1 (1%) | 0 (0%) | 1 (<1%) | n/a - different format / malformed layout |
| *…of which † unverified_size (G2/G3/G14 not checkable)* | *6* | *18* | *0* | *0* |  |


**† unverified.** A FAIL-level check that could not run because its input exceeded the 2 MB cap (`episodes.jsonl` / `tasks.jsonl`) or the file listing was capped is reported as skipped, not passed. `READY†` is therefore *not* a clean pass, and the † count on every other row means that row's distance is a **lower bound** (an unverified check can only add steps, never remove them). Unverified datasets stay in their verdict row; none are moved or dropped.

**NOT_LEROBOT: container** = 8 multi-dataset repos whose LeRobot datasets sit in subfolders (50 sub-datasets found in total; a lower bound wherever the scan was incomplete). Each is one row; **sub-datasets were not audited**, because that would change the sampling unit from repo to dataset directory. `NOT_LEROBOT: other` are genuinely non-conforming.

Stacked `REPAIR` step (G14 fails on top of another verdict): 3 dataset(s).

S-tail (random sample) NEEDS_DOWNCONVERT: 116/200 = 58.0%, 95% Wilson CI [51.1%, 64.6%]. No interval for the other strata: they are not random samples.

S-tail passing every FAIL-level static check except `modality.json` (READY or NEEDS_MODALITY, no REPAIR): 61/200 = 30.5%, 95% Wilson CI [24.5%, 37.2%].

### Fix-cost for NEEDS_DOWNCONVERT

| stratum | n | NEEDS_DOWNCONVERT | median GB | max GB | sum TB |
|---|---|---|---|---|---|
| S-curated | 162 | 127 | 1.9 | 3428 | 5.7 |
| S-popular | 100 | 30 | 32.9 | 5558 | 19.9 |
| S-recent | 100 | 92 | 0.6 | 27 | 0.2 |
| S-tail | 200 | 116 | 0.2 | 18 | 0.1 |


`used_storage_bytes` covers the whole repo including LFS history, so it **overstates** what `convert_v3_to_v2.py`'s `snapshot_download` pulls. Converter cost = full download + per-episode ffmpeg cut; it does not produce `modality.json`.

### Sensitivity: producer concentration

| stratum | n | distinct authors | datasets from the 3 largest authors |
|---|---|---|---|
| S-curated | 162 | 5 | 124, 32, 3 |
| S-popular | 100 | 50 | 32, 6, 3 |
| S-recent | 100 | 51 | 15, 7, 4 |
| S-tail | 200 | 179 | 3, 3, 3 |


S-popular with and without RoboCOIN (one producer's converter accounts for 32 of 100):

| verdict | S-popular (n=100) | S-popular excl. RoboCOIN (n=68) | who fixes it |
|---|---|---|---|
| `READY` | 0 (0%) | 0 (0%) | passes all static checks |
| `READY†` | 1 (1%) | 1 (1%) | passes, but G2/G3/G14 not checkable under 2 MB cap |
| `NEEDS_REPAIR` | 0 (0%) | 0 (0%) | converter (lossy: drops episodes) |
| `NEEDS_MODALITY` | 58 (58%) | 26 (38%) | add `meta/modality.json`: someone who knows the robot (no tool) |
| `NEEDS_DOWNCONVERT` | 30 (30%) | 30 (44%) | `convert_v3_to_v2.py`, then add `modality.json` (2 steps) |
| `INCONSISTENT_MODALITY` | 1 (1%) | 1 (1%) | producer: fix `modality.json` (can fail silently) |
| `BLOCKED` | 2 (2%) | 2 (3%) | no episode data, or a structural failure outside the v3.0 gap; no tool |
| `NOT_LEROBOT: container` | 7 (7%) | 7 (10%) | n/a - audit-unit mismatch, sub-datasets not audited |
| `NOT_LEROBOT: other` | 1 (1%) | 1 (1%) | n/a - different format / malformed layout |
| *…of which † unverified_size (G2/G3/G14 not checkable)* | *18* | *18* |  |

## 2. What fails besides the missing `modality.json`

`modality.json` is a GR00T-specific file that the LeRobot format does not define, so its absence is a gap between two formats rather than a dataset defect. This section sets it aside. Denominator: LeRobot-format datasets (NOT_LEROBOT excluded). Root causes are not exclusive; a dataset can have several.

### 2a. By root cause

| root cause | level | who fixes it | S-curated (n=162) | S-popular (n=92) | S-recent (n=99) | S-tail (n=199) |
|---|---|---|---|---|---|---|
| **passes every FAIL-level check except `modality.json`** |  |  | **35 (22%)** | **56 (61%)** | **7 (7%)** | **61 (31%)** |
| v3.0 layout: GR00T reads v2.x (G2/G3/G7/G8/G9) | FAIL | converter: `convert_v3_to_v2.py` | 127 (78%) | 30 (33%) | 92 (93%) | 116 (58%) |
| no episode data: no parquet under `data/` (metadata-only upload or other storage format) (L3) | FAIL | producer: upload the data | 0 (0%) | 1 (1%) | 0 (0%) | 22 (11%) |
| other structural failure on a v2.x layout (G2/G3/G7/G8/G9/G15/G16) | FAIL | unknown; no tool | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |
| episode files listed in metadata but absent (G14) | FAIL | converter: `repair_lerobot_metadata.py` (lossy) | 0 (0%) | 3 (3%) | 0 (0%) | 0 (0%) |
| `modality.json` shipped but inconsistent (G10-G13) | FAIL | producer | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |
| no `meta/stats.json` (G4) | WARN | auto: regenerated at train time | 24 (15%) | 49 (53%) | 7 (7%) | 82 (41%) |
| `stats.json` lacks some of mean/std/min/max/q01/q99 (G5) | WARN | auto: regenerated at train time | 122 (75%) | 21 (23%) | 0 (0%) | 9 (5%) |
| episodes.jsonl line count != `total_episodes` (L11) | WARN | converter | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |
| a camera feature has no `videos/` directory (L10) | INFO | producer (re-upload) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| no `names` on state and/or action (L9) | INFO | producer | 10 (6%) | 17 (18%) | 1 (1%) | 14 (7%) |
| `fps` not declared (L12) | WARN | producer | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |


### 2b. By check (every check except G6 and the checks that only run once `modality.json` exists), ranked by S-tail

| rank | check | level | what fails | S-curated (n=162) | S-popular (n=92) | S-recent (n=99) | S-tail (n=199) |
|---|---|---|---|---|---|---|---|
| 1 | `G2` | FAIL | no `meta/episodes.jsonl` with `length` (v2.x file) | 127 (78%) | 30 (33%) | 92 (93%) | 138 (69%) |
| 2 | `G3` | FAIL | no `meta/tasks.jsonl` (v2.x file) | 127 (78%) | 30 (33%) | 92 (93%) | 138 (69%) |
| 3 | `G7` | FAIL | `data_path` uses placeholders the loader does not supply | 127 (78%) | 30 (33%) | 92 (93%) | 136 (68%) |
| 4 | `G9` | FAIL | `video_path` missing or uses unsupported placeholders | 105 (65%) | 30 (33%) | 91 (92%) | 131 (66%) |
| 5 | `G4` | WARN | no `meta/stats.json` | 24 (15%) | 49 (53%) | 7 (7%) | 82 (41%) |
| 6 | `L4` | INFO | no `videos/` (state-only) | 26 (16%) | 6 (7%) | 1 (1%) | 34 (17%) |
| 7 | `L5` | WARN | no episode metadata | 0 (0%) | 1 (1%) | 0 (0%) | 23 (12%) |
| 8 | `L3` | INFO | no parquet under `data/` | 0 (0%) | 1 (1%) | 0 (0%) | 22 (11%) |
| 9 | `L6` | WARN | no task metadata | 0 (0%) | 1 (1%) | 0 (0%) | 22 (11%) |
| 10 | `L7` | WARN | no stats file of any kind | 0 (0%) | 1 (1%) | 0 (0%) | 22 (11%) |
| 11 | `L9` | INFO | no `names` on state/action | 10 (6%) | 17 (18%) | 1 (1%) | 14 (7%) |
| 12 | `G5` | WARN | stats.json lacks a stat type | 122 (75%) | 21 (23%) | 0 (0%) | 9 (5%) |
| 13 | `G14` | FAIL | episode file listed but absent | 0 (0%) | 3 (3%) | 0 (0%) | 0 (0%) |
| 14 | `L11` | WARN | episodes.jsonl lines != `total_episodes` | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |
| 15 | `G8` | FAIL | no `chunks_size` | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |
| 16 | `G12` | FAIL | group slices out of range / dims uncovered | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |
| 17 | `G13` | FAIL | annotation column not in features | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |


### 2c. Is it the kind of robot data GR00T targets?

Loading and fit are different questions. A dataset can pass every format check and still not be GR00T training data: GR00T N1.7 targets arms, bimanual setups, mobile manipulators and humanoids, so a well-formed car-driving or human-motion dataset is outside its scope. **Heuristic** (`conformance/embodiment.py`): `info.json:robot_type` first, then vehicle / human-motion feature names, then arm/body dimension names, then (weakest, robot categories only) the dataset name. It does not change any verdict. Denominator: LeRobot-format datasets.

| what the data is | fit | S-curated (n=162) | S-popular (n=92) | S-recent (n=99) | S-tail (n=199) |
|---|---|---|---|---|---|
| Single robot arm | fits GR00T's embodiments | 84 (52%) | 29 (32%) | 83 (84%) | 160 (80%) |
| Two-arm (bimanual) robot | fits GR00T's embodiments | 36 (22%) | 19 (21%) | 8 (8%) | 25 (13%) |
| Humanoid / whole-body robot | fits GR00T's embodiments | 5 (3%) | 25 (27%) | 2 (2%) | 2 (1%) |
| Mobile manipulator | fits GR00T's embodiments | 5 (3%) | 16 (17%) | 5 (5%) | 6 (3%) |
| Vehicle / driving | **likely outside GR00T's scope** | 0 (0%) | 1 (1%) | 0 (0%) | 2 (1%) |
| Human motion (no robot) | **likely outside GR00T's scope** | 1 (1%) | 1 (1%) | 0 (0%) | 0 (0%) |
| Couldn't tell from metadata | unclear | 31 (19%) | 1 (1%) | 1 (1%) | 4 (2%) |
| **of which: well-formed but outside scope** | passes every FAIL-level check except modality.json | 0 | 1 | 0 | 2 |


### 2d. Top 5 FAIL-level failures overall (including `modality.json`), per stratum

**S-curated** - 162 LeRobot-format datasets (of 162 audited; NOT_LEROBOT excluded because it trivially fails G1/G2/G3/G6)

| rank | check | failed | of which v3-style data_path | skipped (blocked/size) |
|---|---|---|---|---|
| 1 | `G6` | 162 (100%) | 127 | 0 |
| 2 | `G2` | 127 (78%) | 127 | 6 |
| 3 | `G3` | 127 (78%) | 127 | 2 |
| 4 | `G7` | 127 (78%) | 127 | 0 |
| 5 | `G9` | 105 (65%) | 105 | 0 |

**S-popular** - 92 LeRobot-format datasets (of 100 audited; NOT_LEROBOT excluded because it trivially fails G1/G2/G3/G6)

| rank | check | failed | of which v3-style data_path | skipped (blocked/size) |
|---|---|---|---|---|
| 1 | `G6` | 90 (98%) | 30 | 0 |
| 2 | `G2` | 30 (33%) | 28 | 18 |
| 3 | `G3` | 30 (33%) | 28 | 6 |
| 4 | `G7` | 30 (33%) | 30 | 0 |
| 5 | `G9` | 30 (33%) | 30 | 0 |

**S-recent** - 99 LeRobot-format datasets (of 100 audited; NOT_LEROBOT excluded because it trivially fails G1/G2/G3/G6)

| rank | check | failed | of which v3-style data_path | skipped (blocked/size) |
|---|---|---|---|---|
| 1 | `G6` | 95 (96%) | 92 | 0 |
| 2 | `G2` | 92 (93%) | 92 | 0 |
| 3 | `G3` | 92 (93%) | 92 | 0 |
| 4 | `G7` | 92 (93%) | 92 | 0 |
| 5 | `G9` | 91 (92%) | 91 | 0 |

**S-tail** - 199 LeRobot-format datasets (of 200 audited; NOT_LEROBOT excluded because it trivially fails G1/G2/G3/G6)

| rank | check | failed | of which v3-style data_path | skipped (blocked/size) |
|---|---|---|---|---|
| 1 | `G6` | 198 (99%) | 135 | 0 |
| 2 | `G2` | 138 (69%) | 136 | 0 |
| 3 | `G3` | 138 (69%) | 136 | 0 |
| 4 | `G7` | 136 (68%) | 136 | 0 |
| 5 | `G9` | 131 (66%) | 131 | 0 |


`G2/G3/G7/G8/G9` share **one root cause** on a v3.0 layout (episodes.parquet / tasks.parquet / file-indexed paths), so they rank together; the `v3-style` column shows how much of each count is that. The independent non-v3 failure is `G6` (`modality.json` absent).

**Silent failures** (G11/G12 fail while modality.json exists): 1 dataset(s) (S-popular).

Stats are reported separately because GR00T regenerates them at train time (WARN, not a verdict step):

| stratum | n (LeRobot-format) | ships stats.json (G4) | ships episodes_stats.jsonl only | of stats.json holders: all six stat types (G5) |
|---|---|---|---|---|
| S-curated | 162 | 138 (85%) | 24 (15%) | 16 (12%) |
| S-popular | 92 | 43 (47%) | 48 (52%) | 22 (51%) |
| S-recent | 99 | 92 (93%) | 7 (7%) | 92 (100%) |
| S-tail | 199 | 117 (59%) | 60 (30%) | 108 (92%) |

## 3. codebase_version cross-tab and within-version schema drift

**codebase_version by stratum**

| version | S-curated (n=162) | S-popular (n=100) | S-recent (n=100) | S-tail (n=200) |
|---|---|---|---|---|
| `(none)` | 0 (0%) | 8 (8%) | 1 (1%) | 1 (<1%) |
| `v2.0` | 11 (7%) | 9 (9%) | 0 (0%) | 1 (<1%) |
| `v2.1` | 24 (15%) | 52 (52%) | 7 (7%) | 61 (30%) |
| `v2.2` | 0 (0%) | 0 (0%) | 0 (0%) | 1 (<1%) |
| `v3.0` | 127 (78%) | 31 (31%) | 92 (92%) | 136 (68%) |

**S-curated: verdict by codebase_version** (n=162)

| version | n | NEEDS_MODALITY | NEEDS_DOWNCONVERT |
|---|---|---|---|
| `v2.0` | 11 | 11 | 0 |
| `v2.1` | 24 | 24 | 0 |
| `v3.0` | 127 | 0 | 127 |

**S-popular: verdict by codebase_version** (n=100)

| version | n | READY† | NEEDS_MODALITY | NEEDS_DOWNCONVERT | INCONSISTENT_MODALITY | BLOCKED | NOT_LEROBOT: container | NOT_LEROBOT: other |
|---|---|---|---|---|---|---|---|---|
| `(none)` | 8 | 0 | 0 | 0 | 0 | 0 | 7 | 1 |
| `v2.0` | 9 | 1 | 8 | 0 | 0 | 0 | 0 | 0 |
| `v2.1` | 52 | 0 | 50 | 0 | 1 | 1 | 0 | 0 |
| `v3.0` | 31 | 0 | 0 | 30 | 0 | 1 | 0 | 0 |

**S-recent: verdict by codebase_version** (n=100)

| version | n | READY | NEEDS_MODALITY | NEEDS_DOWNCONVERT | NOT_LEROBOT: container |
|---|---|---|---|---|---|
| `(none)` | 1 | 0 | 0 | 0 | 1 |
| `v2.1` | 7 | 4 | 3 | 0 | 0 |
| `v3.0` | 92 | 0 | 0 | 92 | 0 |

**S-tail: verdict by codebase_version** (n=200)

| version | n | NEEDS_MODALITY | NEEDS_DOWNCONVERT | BLOCKED | NOT_LEROBOT: other |
|---|---|---|---|---|---|
| `(none)` | 1 | 0 | 0 | 0 | 1 |
| `v2.0` | 1 | 1 | 0 | 0 | 0 |
| `v2.1` | 61 | 59 | 0 | 2 | 0 |
| `v2.2` | 1 | 1 | 0 | 0 | 0 |
| `v3.0` | 136 | 0 | 116 | 20 | 0 |


**S-curated split** (does the maintainer's own namespace clear the contract?)

| verdict | lerobot/* (n=124) | other curated orgs (n=38) | who fixes it |
|---|---|---|---|
| `READY` | 0 (0%) | 0 (0%) | passes all static checks |
| `READY†` | 0 (0%) | 0 (0%) | passes, but G2/G3/G14 not checkable under 2 MB cap |
| `NEEDS_REPAIR` | 0 (0%) | 0 (0%) | converter (lossy: drops episodes) |
| `NEEDS_MODALITY` | 0 (0%) | 35 (92%) | add `meta/modality.json`: someone who knows the robot (no tool) |
| `NEEDS_DOWNCONVERT` | 124 (100%) | 3 (8%) | `convert_v3_to_v2.py`, then add `modality.json` (2 steps) |
| `INCONSISTENT_MODALITY` | 0 (0%) | 0 (0%) | producer: fix `modality.json` (can fail silently) |
| `BLOCKED` | 0 (0%) | 0 (0%) | no episode data, or a structural failure outside the v3.0 gap; no tool |
| `NOT_LEROBOT: container` | 0 (0%) | 0 (0%) | n/a - audit-unit mismatch, sub-datasets not audited |
| `NOT_LEROBOT: other` | 0 (0%) | 0 (0%) | n/a - different format / malformed layout |
| *…of which † unverified_size (G2/G3/G14 not checkable)* | *0* | *6* |  |

Curated publishers in the sample: lerobot (124), IPEC-COMMUNITY (32), HuggingFaceVLA (3), physical-intelligence (2), nvidia (1)


**Within-version drift.** Same `codebase_version` string, different schema. Listed: attributes with >1 variant inside a version (data_path style always). Counts are datasets, not rates.

| version string | n | attribute | variants (count) | n per stratum curated/popular/recent/tail |
|---|---|---|---|---|
| `v2.0` | 21 | data_path style (G7) | v2-style: 21 | 11 / 9 / 0 / 1 |
| `v2.0` | 21 | video_path style (G9) | v2-style: 19; missing/none: 2 | 11 / 9 / 0 / 1 |
| `v2.0` | 21 | quantile stats present (G5, stats.json holders only) | fail: 20; pass: 1 |  |
| `v2.0` | 21 | **distinct full signatures** | **3** |  |
| `v2.1` | 144 | episode metadata (L5) | jsonl: 141; none: 3 | 24 / 52 / 7 / 61 |
| `v2.1` | 144 | task metadata (L6) | jsonl: 141; none: 3 | 24 / 52 / 7 / 61 |
| `v2.1` | 144 | stats file (L7) | episodes_stats.jsonl: 138; none: 3; stats.json: 3 | 24 / 52 / 7 / 61 |
| `v2.1` | 144 | data_path style (G7) | v2-style: 142; other: 2 | 24 / 52 / 7 / 61 |
| `v2.1` | 144 | video_path style (G9) | v2-style: 132; missing/none: 12 | 24 / 52 / 7 / 61 |
| `v2.1` | 144 | quantile stats present (G5, stats.json holders only) | fail: 2; pass: 1 |  |
| `v2.1` | 144 | **distinct full signatures** | **7** |  |
| `v2.2` | 1 | data_path style (G7) | v2-style: 1 | 0 / 0 / 0 / 1 |
| `v2.2` | 1 | **distinct full signatures** | **1** |  |
| `v3.0` | 386 | episode metadata (L5) | parquet: 363; none: 21; jsonl: 2 | 127 / 31 / 92 / 136 |
| `v3.0` | 386 | task metadata (L6) | parquet: 364; none: 20; jsonl: 2 | 127 / 31 / 92 / 136 |
| `v3.0` | 386 | stats file (L7) | stats.json: 366; none: 20 | 127 / 31 / 92 / 136 |
| `v3.0` | 386 | data_path style (G7) | v3-style: 385; v2-style: 1 | 127 / 31 / 92 / 136 |
| `v3.0` | 386 | video_path style (G9) | v3-style: 357; missing/none: 28; v2-style: 1 | 127 / 31 / 92 / 136 |
| `v3.0` | 386 | quantile stats present (G5, stats.json holders only) | pass: 236; fail: 130 |  |
| `v3.0` | 386 | **distinct full signatures** | **8** |  |

Version string vs actual layout disagree: 1 dataset(s): S-popular (v3.0 string, v2-style data_path)

## 4. Goal 6 - could `modality.json` be generated mechanically from `features.*.names`?

Population: LeRobot-format datasets **without** `modality.json` (G6 fails). `meta/info.json` re-read at each audited commit sha (cached in `results/info_cache/`). **Heuristic, not ground truth**: a dim name is recognised by a fixed keyword vocabulary (gripper / hand / joint / eef pos / eef rot / base / body, with left/right side); generic names like `joint_0`, `motor_3`, `0` count as opaque; `looks_inferable` also requires every group to be one contiguous range. Even `looks_inferable` yields only a *partition* - choosing group names that match an embodiment config still needs someone who knows the recipe. The generator is not built. Per-dataset tier and parsed partition: `results/goal6_inferability.csv`.

| tier | meaning | S-curated (n=162) | S-popular (n=90) | S-recent (n=95) | S-tail (n=198) |
|---|---|---|---|---|---|
| `no_state_or_action_feature` | features lack observation.state and/or action | 7 (4%) | 9 (10%) | 1 (1%) | 8 (4%) |
| `no_names` | no `names` on state and/or action - needs a human | 3 (2%) | 8 (9%) | 0 (0%) | 5 (3%) |
| `names_unusable` | names present but not a flat list matching the feature dim | 7 (4%) | 6 (7%) | 2 (2%) | 5 (3%) |
| `opaque_names` | names present, but >=1 dim unrecognised or generic (joint_0, motor_3, 0, 1...) - needs a human | 92 (57%) | 8 (9%) | 8 (8%) | 10 (5%) |
| `fragmented_groups` | all dims recognised, but a semantic group is not one contiguous range (GR00T groups are start:end) | 0 (0%) | 0 (0%) | 3 (3%) | 3 (2%) |
| `looks_inferable` | all dims recognised AND every group is one contiguous range | 53 (33%) | 59 (66%) | 81 (85%) | 167 (84%) |
| `info_unavailable` | meta/info.json could not be fetched (counted, not dropped) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |

| stratum | n lacking modality.json | strict: looks_inferable | upper bound: names usable at all |
|---|---|---|---|
| S-curated | 162 | 53 (33%) | 145 (90%) |
| S-popular | 90 | 59 (66%) | 67 (74%) |
| S-recent | 95 | 81 (85%) | 92 (97%) |
| S-tail | 198 | 167 (84%) | 180 (91%) |

## 5. Individual cases (repo ids omitted; see `summary.csv`)

**READY / READY†** (pass all static checks)

| stratum | version | steps | unverified | failed FAIL-level | state_dim | action_dim |
|---|---|---|---|---|---|---|
| S-popular | v2.0 | - | G2,G14 | - | 44 | 44 |
| S-recent | v2.1 | - | - | - | 17 | 17 |
| S-recent | v2.1 | - | - | - | 17 | 17 |
| S-recent | v2.1 | - | - | - | 17 | 17 |
| S-recent | v2.1 | - | - | - | 17 | 17 |


**INCONSISTENT_MODALITY**

| stratum | version | steps | unverified | failed FAIL-level | silent_failure |
|---|---|---|---|---|---|
| S-popular | v2.1 | INCONSISTENT_MODALITY | G2,G3,G14 | G12,G13 | True |

- S-popular, v2.1: G12: state: groups leave dims [6] of 'observation.state' (dim 8) uncovered; G13: annotation entries whose column is not in features: [('human.action.task_name', 'annotation.human.action.task_name'), ('human.validity', 'annotation.human.validity')]

**BLOCKED**. Most have no parquet under `data/` (metadata-only uploads: 0 bytes stored, often `eval_*` recording runs; one stores episodes in a different columnar format). Whether these are aborted recordings or deliberate is not established; the listed bytes are the discriminating facts.

| stratum | version | steps | unverified | failed FAIL-level | parquet_gb_listed | video_gb_listed | repo_last_modified |
|---|---|---|---|---|---|---|---|
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-04-24T21:25:15+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-05-06T06:55:39+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-04-17T11:17:03+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-02-27T14:39:32+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-02-16T18:06:04+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-03-21T09:11:28+00:00 |
| S-tail | v2.1 | BLOCKED+MODALITY | - | G2,G3,G6 | 0.001 | 0.0 | 2026-08-20T12:44:17+00:00 |
| S-tail | v2.1 | BLOCKED+MODALITY | - | G2,G3,G6 | 0.001 | 0.0 | 2026-08-21T05:18:33+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-03-05T00:09:07+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-05-03T08:56:28+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-04-23T16:16:33+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-02-17T11:44:29+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-09-10T10:53:49+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-03-05T22:23:19+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-02-16T17:21:36+00:00 |
| S-popular | v2.1 | BLOCKED+MODALITY | - | G2,G3,G6,G8 | 75.922 | 50.633 | 2025-10-05T08:43:57+00:00 |
| S-popular | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-09-03T09:53:56+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-02-09T16:49:11+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-01-16T16:38:12+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-09-24T07:32:41+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-05-20T17:06:13+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-01-03T04:00:21+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-03-10T00:26:23+00:00 |
| S-tail | v3.0 | BLOCKED+MODALITY | - | G2,G3,G6,G7,G9 | 0.0 | 0.0 | 2026-06-23T08:32:28+00:00 |


**NOT_LEROBOT: container**

| stratum | sub-datasets found | scan complete | repo GB |
|---|---|---|---|
| S-popular | 5 | yes | 264 |
| S-popular | 7 | yes | 358 |
| S-popular | 24 | **no (lower bound)** | 813 |
| S-popular | 3 | yes | 112 |
| S-popular | 2 | yes | 250 |
| S-popular | 1 | **no (lower bound)** | 32 |
| S-popular | 4 | **no (lower bound)** | 198 |
| S-recent | 4 | **no (lower bound)** | 79 |

## Reproduce

`.venv/bin/python scripts/reproduce.py` (or `.venv/bin/python -m conformance.report --offline` for this step alone). Inputs: `results/raw/**/*.json` and `results/errors/`. Only `meta/info.json` (<2 MB cap, pinned to the audited repo sha) is fetched, for goal 6.
