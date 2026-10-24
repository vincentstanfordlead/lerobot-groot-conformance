# LeRobot and openpi columns

Companion to `report.md`. Same audited datasets and strata; judged by [`CONTRACT_lerobot_openpi.md`](../CONTRACT_lerobot_openpi.md) for loading by Hub `repo_id`. LeRobot `ff71cae` (reads v3.0), openpi `215abfb` via lerobot `0cf8648` (reads v2.x). Metadata only: nothing was loaded through either model. **Every rate is per stratum with its own n; there is no pooled rate.** Individual datasets are not named here; ids are in `models.csv`.

9 audited dataset(s) are excluded as UNASSESSED: the repo is gone or private since the audit, so its Hub refs could not be read. They are not in any n below.

## 1. LeRobot native (v3.0)

| verdict | S-curated (n=162) | S-popular (n=100) | S-recent (n=91) | S-tail (n=200) | meaning |
|---|---|---|---|---|---|
| `PASS` | 127 (78%) | 20 (20%) | 80 (88%) | 112 (56%) | loader picks a v3.0 ref and the v3 meta files are there |
| `NEEDS_TAG` | 0 (0%) | 8 (8%) | 3 (3%) | 3 (2%) | right layout, but no version-named ref the loader accepts: one `create_tag` |
| `NEEDS_CONVERT` | 35 (22%) | 60 (60%) | 7 (8%) | 60 (30%) | data is in the other layout (v2 for LeRobot, v3 for openpi) |
| `BLOCKED` | 0 (0%) | 12 (12%) | 1 (1%) | 25 (12%) | no episodes, not LeRobot, a required meta file missing, or no tool for the version |
| *…of which judged on a ref snapshot that is not `main` (checked, `verify_refs.py`)* | *7* | *6* | *5* | *5* | the file listing and meta were read at that exact commit |


## 2. openpi (v2.x)

| verdict | S-curated (n=162) | S-popular (n=100) | S-recent (n=91) | S-tail (n=200) | meaning |
|---|---|---|---|---|---|
| `NEEDS_CONFIG` | 144 (89%) | 13 (13%) | 7 (8%) | 59 (30%) | files load; a data config and norm stats are still to be written (never PASS) |
| `NEEDS_TAG` | 1 (1%) | 46 (46%) | 0 (0%) | 1 (<1%) | right layout, but no version-named ref the loader accepts: one `create_tag` |
| `NEEDS_CONVERT` | 17 (10%) | 28 (28%) | 83 (91%) | 114 (57%) | data is in the other layout (v2 for LeRobot, v3 for openpi) |
| `BLOCKED` | 0 (0%) | 13 (13%) | 1 (1%) | 26 (13%) | no episodes, not LeRobot, a required meta file missing, or no tool for the version |
| *…of which judged on a ref snapshot that is not `main` (checked, `verify_refs.py`)* | *114* | *8* | *0* | *3* | the file listing and meta were read at that exact commit |
| *…of which `NEEDS_CONFIG` through an older `v2.x` ref whose files were NOT inspected* | *0* | *0* | *0* | *0* | would be a lower bound on doubt; 0 once `verify_refs.py` has run |


openpi has no `PASS`: every dataset needs a per-dataset Python data config and a `compute_norm_stats.py` run (contract §5). Timestamp sync (every frame within 1e-4 s of k/fps, contract §4) needs the parquet and was **not** checked, so `NEEDS_CONFIG` is an upper bound.

## 3. π0.5 model fit (openpi `pi05_base`)

Whether the *contents* fit π0.5 as openpi ships it (contract §7), independent of whether the files load (§2 above). From `info.json` at the audited sha; nothing was loaded. A dataset without a readable `info.json` is not in these n.

| verdict | S-curated (n=162) | S-popular (n=92) | S-recent (n=90) | S-tail (n=199) | meaning |
|---|---|---|---|---|---|
| `FIT` | 49 (30%) | 25 (27%) | 58 (64%) | 135 (68%) | fits π0.5 defaults: the data config only renames keys |
| `ADAPT` | 100 (62%) | 36 (39%) | 29 (32%) | 57 (29%) | fits once the config (or one model setting) does more: see the checks below |
| `NO_FIT` | 13 (8%) | 31 (34%) | 3 (3%) | 7 (4%) | π0.5 as shipped cannot train on it (too-wide action/state, no action, no RGB camera, no fps) |


Share of datasets where each check is not `OK` (`ADAPT`/`FAIL`, or `NOTE` for P5 and P7):

| check | S-curated (n=162) | S-popular (n=92) | S-recent (n=90) | S-tail (n=199) |
|---|---|---|---|---|
| P1 action is one float vector | 4 (2%) | 8 (9%) | 0 (0%) | 4 (2%) |
| P2 action dim <= 32 | 6 (4%) | 27 (29%) | 1 (1%) | 1 (1%) |
| P3 state is one float vector, dim <= 32 | 7 (4%) | 33 (36%) | 2 (2%) | 6 (3%) |
| P4 1-3 RGB cameras (3 image slots) | 26 (16%) | 41 (45%) | 20 (22%) | 20 (10%) |
| P5 camera size vs 224x224 (resize with padding) | 59 (36%) | 27 (29%) | 19 (21%) | 42 (21%) |
| P6 fps vs the 50-step action chunk | 86 (53%) | 20 (22%) | 21 (23%) | 23 (12%) |
| P7 episodes at least one chunk long | 26 (16%) | 7 (8%) | 0 (0%) | 3 (2%) |
| P8 task strings for the prompt | 0 (0%) | 7 (8%) | 0 (0%) | 23 (12%) |


openpi `NEEDS_CONFIG` **and** π0.5 `FIT` (loads from the Hub, and the config is only key renames): S-curated 42 (26%), S-popular 4 (4%), S-recent 3 (3%), S-tail 42 (21%).

## 4. Hub version refs (what decides loading by `repo_id`)

| version refs | S-curated (n=162) | S-popular (n=100) | S-recent (n=91) | S-tail (n=200) |
|---|---|---|---|---|
| no version ref | 1 (1%) | 57 (57%) | 3 (3%) | 6 (3%) |
| v3.0 only | 17 (10%) | 19 (19%) | 80 (88%) | 131 (66%) |
| v2.x only | 34 (21%) | 13 (13%) | 7 (8%) | 60 (30%) |
| v2.x and v3.0 | 110 (68%) | 2 (2%) | 0 (0%) | 2 (1%) |
| other | 0 (0%) | 1 (1%) | 0 (0%) | 0 (0%) |


Refs were read on the fetch date, not at the audited sha. 0 dataset(s) have an `info.json` major version that no ref carries; their verdict follows the refs.

### Effect of reading the real snapshot

| column | snapshots checked | verdict differs from judging main | moves |
|---|---|---|---|
| lerobot | 23 | 0 | - |
| openpi | 125 | 4 | BLOCKED -> NEEDS_CONFIG: 1; NEEDS_CONFIG -> BLOCKED: 3 |


## 5. Side by side with GR00T

|  | S-curated (n=162) | S-popular (n=100) | S-recent (n=91) | S-tail (n=200) |
|---|---|---|---|---|
| GR00T `READY` or `NEEDS_MODALITY` | 35 (22%) | 59 (59%) | 7 (8%) | 61 (30%) |
| LeRobot `PASS` | 127 (78%) | 20 (20%) | 80 (88%) | 112 (56%) |
| openpi `NEEDS_CONFIG` | 144 (89%) | 13 (13%) | 7 (8%) | 59 (30%) |
| LeRobot `PASS` and openpi `NEEDS_CONFIG` (both, from the Hub, no conversion) | 110 (68%) | 1 (1%) | 0 (0%) | 1 (<1%) |


The first row is not 'loads in GR00T': GR00T reads a local copy, so its rows ignore refs.

S-tail (random sample) LeRobot `PASS`: 112/200 = 56.0%, 95% Wilson CI [49.1%, 62.7%]. No interval for the other strata: they are not random samples.

S-tail (random sample) openpi `NEEDS_CONFIG`: 59/200 = 29.5%, 95% Wilson CI [23.6%, 36.2%]. No interval for the other strata: they are not random samples.
