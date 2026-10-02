# CONTRACT — what Isaac-GR00T requires of a LeRobot dataset

**Pinned to Isaac-GR00T [`51d4c89f72fda44cbf77285c6a8114b52676b8a1`](https://github.com/NVIDIA/Isaac-GR00T/tree/51d4c89f72fda44cbf77285c6a8114b52676b8a1)**
(`main` on 2026-09-28 and still on 2026-10-01; committed 2026-08-20). Written 2026-09-29.
Every line number below refers to the copies in [`vendor/groot_51d4c89/`](vendor/groot_51d4c89/). Vendored
filenames are the repo path with `/` replaced by `_`.

GR00T's [data preparation guide](vendor/groot_51d4c89/getting_started_data_preparation.md)
documents the format: LeRobot v2 plus one extra file, `meta/modality.json`. This document
goes one level below the guide. It records, clause by clause, what the loader and its
entrypoints *do* with each requirement: what raises, what GR00T repairs on its own, and
what passes without an error. Each clause carries a line citation. The behaviour is spread
across **eight files** in `gr00t/data/`, `gr00t/eval/`, `gr00t/policy/` and `scripts/`.
GR00T does not read `codebase_version`, so the contract follows the code, not a version
number. Re-pin (§10) when the code moves.

The checklist for data producers, split into required / observed / open questions, is
[`CHECKLIST.md`](CHECKLIST.md).
The linter implementing the checks is [`conformance/checks.py`](conformance/checks.py), with
citations generated in [`conformance/contract.py`](conformance/contract.py).

---

## 0. Conventions

| shorthand | file @51d4c89 |
|---|---|
| **loader** | `gr00t/data/dataset/lerobot_episode_loader.py` |
| **factory** | `gr00t/data/dataset/factory.py` |
| **stats** | `gr00t/data/stats.py` |
| **single** | `gr00t/data/dataset/sharded_single_step_dataset.py` |
| **mixture** | `gr00t/data/dataset/sharded_mixture_dataset.py` |
| **eval** | `gr00t/eval/open_loop_eval.py` |
| **replay** | `gr00t/policy/replay_policy.py` |
| **repair** | `scripts/repair_lerobot_metadata.py` |
| **v3→v2** | `scripts/lerobot_conversion/convert_v3_to_v2.py` |

Every clause is classified by **how it fails**:

- **LOUD**: an exception (`FileNotFoundError`, `KeyError`, `AssertionError`, `ValueError`)
  stops the run. Annoying, but safe.
- **SILENT**: no exception. The run continues on wrong or partial data. Any warning is a
  `print()` or `logging.warning`, not an error.
- **HEALED**: GR00T repairs it automatically before the check can fire.

And by **when** it fails: at *construction* (before the first training step) or
*mid-run* (only when a particular episode is sampled).

`G1`–`G14` are the IDs used by the linter and in `results/`. `U1`–`U7` are clauses found
while writing this document that the linter does **not** check yet (§8).

---

## 1. Who reads the dataset, and in what order

The contract depends on the **entrypoint**. For example, the loader asserts that
`stats.json` exists, but the training entrypoint regenerates it first.

### 1.1 Training path (`DatasetFactory.build`)

```
factory L57-60     generate_stats(path)                         stats L251-291
                     reads meta/info.json["features"][*]["dtype"]  stats L254-256
                     globs data/*/*.parquet                        stats L51, L284
                     writes meta/stats.json (+ __fingerprints__)   stats L290-291
                   generate_rel_stats(path, tag)                stats L415-435
                     only for embodiments with RELATIVE actions;
                     builds a LeRobotEpisodeLoader                  stats L321
factory L61-69     ShardedSingleStepDataset(...)
                     LeRobotEpisodeLoader(path, modality_configs)   single L152-155
                       _load_metadata()                             loader L144-202
factory L88-96     ShardedMixtureDataset(...)
                     merge_statistics()                             mixture L242
                       ds.get_dataset_statistics()                  mixture L280
                         -> loader.get_dataset_statistics()         single L297-299, loader L500-535
training loop      loader[idx] -> __getitem__                       loader L565-621
                     _load_parquet_data / _load_video_data / _load_mask_data
```

### 1.2 Direct-loader paths (bypass the factory)

`eval` L327-330 and L147, `replay` L94-100 construct `LeRobotEpisodeLoader` and index
episodes directly. They **do not** call `generate_stats` and **do not** call
`get_dataset_statistics()`. That difference decides whether `G4` fires (§5) and whether
`G11` is loud or silent (§4.3).

### 1.3 Not covered: LeRobot's own `groot` policy

GR00T N1.7 can also be fine-tuned inside Hugging Face LeRobot via its `groot` policy type
([upstream README L262-264](vendor/groot_51d4c89/upstream_README.md)). That path reads
datasets through LeRobot's own loader, not through `LeRobotEpisodeLoader`. This contract,
the linter and the audit cover **only the Isaac-GR00T reference implementation's data path**
described above.

---

## 2. The layout GR00T expects

GR00T reads exactly one layout: the **LeRobot v2.x** layout, plus one GR00T-only file.

```
<dataset>/
├── meta/
│   ├── info.json            G1  required
│   ├── episodes.jsonl       G2  required   (v2.x; v3.0 has meta/episodes/*.parquet instead)
│   ├── tasks.jsonl          G3  required   (v2.x; v3.0 has meta/tasks.parquet instead)
│   ├── modality.json        G6  required   GR00T-only; no LeRobot tool writes it
│   ├── stats.json           G4  required by the loader, regenerated by the factory
│   └── relative_stats.json      optional   (loader L186-194)
├── data/chunk-XXX/episode_XXXXXX.parquet                 per info.json:data_path   (G7, G14)
└── videos/chunk-XXX/<video_key>/episode_XXXXXX.mp4       per info.json:video_path  (G9, G14)
```

**GR00T has no `codebase_version` check.** It does not reject v3.0 datasets. It opens
fixed filenames and crashes on the first missing one (`episodes.jsonl`,
`FileNotFoundError` at loader L163-165). v3.0 is also caught earlier, from `info.json`
alone: its `data_path` uses `{chunk_index}` / `{file_index}` placeholders, which the loader
does not supply (`G7`). The only version check in the files read is in NVIDIA's
converter, which accepts exactly the string `"v3.0"` (v3→v2 L101-108) and writes `"v2.1"`
(v3→v2 L158).

---

## 3. `meta/info.json`

| id | clause | fails | when | source @51d4c89 |
|---|---|---|---|---|
| `G1` | exists and parses as JSON | LOUD `FileNotFoundError` / `JSONDecodeError` | construction | loader L158-160 |
| `G7` | `data_path` present; its placeholders ⊆ `{episode_chunk, episode_index}` | LOUD `KeyError` (missing key, or `.format()` on an unknown placeholder) | construction (key), mid-run (format) | loader L198, L363-365 |
| `G8` | `chunks_size` present | LOUD `KeyError` | construction | loader L201 |
| `G9` | if cameras are used: `video_path` present; placeholders ⊆ `{episode_chunk, video_key, episode_index}` | placeholders: LOUD `KeyError` on `.format()`. **Absent `video_path`: SILENT at the loader**. `_load_video_data` returns no frames for any requested camera, with no warning (L416-417). I did not trace what the processor does next. | mid-run | loader L199, L434-438; L416-417 |
| `G15` (was `U1`) | `features` present, and every feature has `dtype` | LOUD `KeyError`, in `generate_stats`. The loader itself tolerates a missing `features` (`.get`, L197). | construction (training path only) | stats L254-256 |
| `G16` (was `U2`) | `observation.state` / `action` (or the group's `original_key` column) has a `dtype` containing `"float"` | LOUD `KeyError` in `get_dataset_statistics`: stats are only computed for `"float"` dtypes (stats L256), and the stats slice indexes `self.stats[stats_key]` (L527) | construction | stats L256; loader L527 |

Optional, never a failure: `video_path` (L199, `.get`), `mask_path` (L200), `fps` (L202,
default 30), `relative_stats.json` (L186-194). Masks, when used: `mask_path` is formatted
with `{episode_chunk, episode_index, mask_key, video_key}` (L489-494). Files must be
`.npy`/`.npz` (L450-472).

Chunking arithmetic is `episode_index // chunks_size` everywhere (loader L362, L419, L483;
repair L100). `chunks_size` must therefore be the value the files were actually written
with.

---

## 4. `meta/modality.json`: the GR00T-only file

This is the only file in the contract that no LeRobot tool writes and no NVIDIA tool
generates. It says which slice of the flat `observation.state` / `action` vectors is
which body part. The positive-control fixture shows the shape
([`vendor/.../demo_data_cube_to_bowl_5_meta_modality.json`](vendor/groot_51d4c89/demo_data_cube_to_bowl_5_meta_modality.json)):

```json
{
  "state":  { "single_arm": {"start": 0, "end": 5}, "gripper": {"start": 5, "end": 6} },
  "action": { "single_arm": {"start": 0, "end": 5}, "gripper": {"start": 5, "end": 6} },
  "video":  { "front": {"original_key": "observation.images.front"},
              "wrist": {"original_key": "observation.images.wrist"} },
  "annotation": { "human.task_description": {"original_key": "task_index"} }
}
```

### 4.1 Existence

| id | clause | fails | when | source |
|---|---|---|---|---|
| `G6` | exists and parses | LOUD `FileNotFoundError` | construction | loader L174-176 |

### 4.2 `state` / `action` groups: the two slicing clauses

Each group is `{start, end, original_key?}`. `original_key` names the parquet column to
slice, defaulting to `observation.state` / `action` (`DEFAULT_COLUMN_NAMES`, loader L60-63).
The **same** slice is applied in two places: to the data (L331-338) and to the stats
(L517-531).

| id | clause | fails | when | source |
|---|---|---|---|---|
| `G12` | for each group `0 ≤ start < end ≤ dim(original_key)`; the groups on a column cover `[0, dim)` | **SILENT.** `x[start:end]` past the end truncates without error (L336). The stats slice truncates identically (L527-530), so shapes stay consistent and nothing downstream in the files read can notice. Dims that no group covers are never read. | never raises | loader L60-63, L333-338, L517-531 |
| — | a non-1-D column (string, scalar) is passed through unsliced | by design | — | loader L335-338 |

### 4.3 Missing sections and missing groups (`G11`): loud or silent depending on the entrypoint

The *embodiment config* in the training recipe decides which groups are required. The
dataset does not. So a dataset-only linter can check only a necessary condition:
`state` and `action` exist and are non-empty. That is `G11`. What happens when a group
the recipe requests is missing **depends on the entrypoint**:

| path | code | result |
|---|---|---|
| **training** (factory → `ShardedMixtureDataset`) | `get_dataset_statistics()` indexes `self.modality_meta[modality][joint_key]` directly (loader L517, L524-525), called from mixture L280 during `__init__` (L242) | **LOUD `KeyError` at construction**, before step 1 |
| training, relative-action embodiments only | `RelativeActionLoader` reads `df["state.<key>"]` after the drop (stats L321-335) | LOUD `KeyError` inside `generate_rel_stats` |
| **eval / replay** (direct loader) | `_extract_joint_groups` looks the group up with `.get(..., {})` and, if absent, `print()`s a warning and drops it (loader L325-342) | **SILENT** at the loader. `replay` raises later for a missing *action* group (replay L114-124). A missing *state* group was not traced further. |

> **Note.** An earlier draft of this project described `G11` as silent everywhere. At the
> pinned commit that is true only on the direct-loader paths. On the training path a missing
> group fails loudly at construction, because `ShardedMixtureDataset` calls
> `get_dataset_statistics()`. **No measured number depends on this:** `G11` fired on 0 of
> 562 datasets. The one real silent failure in the audit (one S-popular dataset) is a `G12`
> uncovered dimension. The linter's G11 detail string still says "SILENT"; this section is the
> authoritative description.

### 4.4 `video`

| id | clause | fails | when | source |
|---|---|---|---|---|
| `G10` | every `video` entry resolves to a key in `info.json:features`: `original_key`, defaulting to `observation.images.{key}` | LOUD `AssertionError`. A missing `video` section is a LOUD `KeyError` when a camera is requested. | mid-run | loader L426-431 |
| `U3` | if the recipe's camera names differ from `modality.json:video`'s keys, the counts must match | LOUD `AssertionError` on a count mismatch. **On a count match: SILENT positional mapping** by `modality.json` key order, with only a `logging.warning`. Cameras listed in the wrong order are swapped without error. | construction | loader L278-297 |

**The loader and NVIDIA's repair tool disagree on the default `original_key`.** The loader
defaults to `observation.images.{key}` (L426-428). `repair` defaults to the bare `{key}`
(repair L109-117). A `video` entry without `original_key` therefore points at two different
directories, depending on which NVIDIA tool reads it. The NVIDIA demo sidesteps this by
always setting `original_key` explicitly. `G10` follows the loader. `G14` follows
`repair`, because `repair` is NVIDIA's own definition of "required files".

### 4.5 `annotation` (language)

| id | clause | fails | when | source |
|---|---|---|---|---|
| `G13` | every `annotation.<sub>` key the recipe requests exists under `modality.json:annotation`; its `original_key` (default `annotation.<sub>`) is a parquet column | LOUD `AssertionError` / `KeyError` | mid-run | loader L376-381 |
| `U4` | that column holds `task_index` values present in `tasks.jsonl` | LOUD `KeyError` on `tasks_map[x]` | mid-run | loader L382-384 |

The linter checks the dataset-side necessary condition of `G13` only (the entry's column
exists in `features`). Which `annotation` keys are required depends on the recipe.

---

## 5. `meta/stats.json` and `relative_stats.json`

| id | clause | fails | when | source |
|---|---|---|---|---|
| `G4` | `meta/stats.json` exists (this exact filename; `episodes_stats.jsonl` does not count) | LOUD `AssertionError`, **only on direct-loader paths** (eval, replay, deployment). **HEALED on the training path:** `factory` L57-60 runs `generate_stats` first. | construction | loader L179-182; factory L57-60 |
| `G5` | each float feature's entry has `mean, std, min, max, q01, q99` | never fails. A missing field marks the feature stale, and it is recomputed. | — | stats L201-224 |

Every shipped `stats.json` is effectively ignored for training. `_stale_features` also
requires a matching `__fingerprints__` entry, a sha256 of each feature's
`{dtype, shape}` (stats L183-198, L227-228). `__fingerprints__` is a GR00T-private
sidecar key (stats L62). No public LeRobot dataset carries it, so every feature is
recomputed from `data/*/*.parquet` on the first training run. `G4`/`G5` are
therefore `WARN` in the linter. They are reported as format divergence, not as a
distance-to-ready step.

`relative_stats.json` is optional (loader L186-194) and is generated per embodiment by
`generate_rel_stats` (stats L415-435).

---

## 6. `meta/episodes.jsonl`, `meta/tasks.jsonl`, and the episode files

| id | clause | fails | when | source |
|---|---|---|---|---|
| `G2` | `episodes.jsonl` exists, one JSON object per line, each with `length` | LOUD `FileNotFoundError` / `KeyError` | construction | loader L163-165, L204-213 |
| `U5` | each line has `episode_index` | LOUD `KeyError` | mid-run (on sampling) | loader L587; repair L187 |
| `U6` | each line has `tasks` (list), when the recipe's language key is `task` | LOUD `KeyError` | mid-run | loader L540-541 |
| `G3` | `tasks.jsonl` exists; each line has `task_index` and `task` | LOUD `FileNotFoundError` / `KeyError` | construction | loader L168-171 |
| `G14` | for every episode: the `data_path` parquet exists, plus one `video_path` mp4 per video `original_key` (and one mask per mask key) | LOUD `FileNotFoundError` **mid-run**, when that episode is sampled, possibly hours in | mid-run | repair L120-163 (NVIDIA's own definition; the linter does not check masks) |
| `U7` | each episode's video has at least `min(len(parquet), length)` decodable frames | LOUD `AssertionError` | mid-run | loader L599-611 |
| — | `length` ≠ parquet row count | **SILENT**: the episode is truncated to the shorter of the two (L600-601) | — | loader L599-601 |

---

## 7. Who can fix what: the remediation tools at the pin

| clause(s) | NVIDIA tool | automatic? | cost / caveat | source |
|---|---|---|---|---|
| `G4`, `G5` | `generate_stats` | **yes, unconditionally at train time** | reads all parquet | factory L57-60; stats L251-291 |
| `G2`, `G3`, `G7`, `G9` on a v3.0 layout | `convert_v3_to_v2.py` | yes, run by hand | **full `snapshot_download`** (L502) + per-episode `ffmpeg -c copy` cut (L336-353). Accepts only `codebase_version == "v3.0"` (L101-108). Writes `episodes.jsonl`, `tasks.jsonl`, v2 path templates, `video_path = None` when there are no cameras (L162-165). Copies v3 `stats.json` across (L471-476). **Does not write `modality.json`.** | v3→v2 |
| `G14` | `repair_lerobot_metadata.py` | yes, run by hand | needs a local copy; **drops the broken episodes** (lossy) and regenerates stats | repair L18-24 |
| `G6`, `G10`–`G13`, `U3` | — | **no tool exists** | a person who knows which state dims are the gripper, and which camera is which | — |
| `G15`, `G16`, `U5`–`U7` | — | no dedicated tool | fix whatever wrote the metadata / files | — |

**The structural fact the project rests on, now sourced:** every clause that NVIDIA
ships a fixer for is layout or bookkeeping. The clauses with no fixer are the
*semantic* ones in `modality.json`. That is also where `G12` lives, the contract's
one unconditionally silent failure.

Open question, not a claim: `ffmpeg -c copy` cuts snap to keyframes. If the source GOP
is > 1, a downconverted episode may fail `U7` (L608) or be off by frames. Testing it
needs a video download, which is out of scope.

---

## 8. Gaps: contract clauses the linter does not check yet

Found while writing this document by reading the entrypoints end to end. **Update
2026-10-01:** `U1` and `U2` are now checked as **`G15`** and **`G16`**. Their only input is
`info.json`, so they were backfilled into `results/` from `info.json` at each dataset's audited
commit. They fired on 0 of 552 LeRobot-format datasets. `U5` and `U6` need `episodes.jsonl`
content, which the audit did not store, so they would need a re-audit. `U3`, `U4` and `U7` need
a recipe or a payload download and stay out of scope.

| id | clause | fails | checkable from metadata alone? |
|---|---|---|---|
| ~~`U1`~~ | now `G15` | | |
| ~~`U2`~~ | now `G16` | | |
| `U3` | `modality.json:video` key order matches the recipe's camera order (when names differ) | **SILENT** | no, needs the recipe |
| `U4` | annotation column values ⊆ `tasks.jsonl` `task_index` | LOUD, mid-run | no, needs parquet |
| `U5` | every `episodes.jsonl` line has `episode_index` | LOUD, mid-run | yes, `episodes.jsonl` (the linter's `G14` currently falls back to line position) |
| `U6` | every `episodes.jsonl` line has `tasks` | LOUD, mid-run (recipe-dependent) | yes, `episodes.jsonl` |
| `U7` | video frame count ≥ episode length | LOUD, mid-run | no, needs video |

`U1`, `U2`, `U5` and `U6` are cheap: the audit already fetched the inputs. `U3`, `U4` and
`U7` need a recipe or a payload download, which is outside the project's rules.

---

## 9. Citation table (generated)

The `G*` citations below are produced by [`conformance/contract.py`](conformance/contract.py)
from anchor strings in the vendored files, never typed by hand. If an anchor moves, the
import fails. The §1 and `U*` citations were read off the vendored files on 2026-09-29.

| id | source @51d4c89 (generated) | earlier hand-typed draft |
|---|---|---|
| `G1` | loader L158-160 | L158-160 |
| `G2` | loader L163-165, L204-213 | L163-165, L204-213 |
| `G3` | loader L168-171 | L168-171 |
| `G4` | loader L179-182, factory L57-60 | L179-182; factory L57-60 |
| `G5` | stats L201-224 | stats L201-229 (L224) |
| `G6` | loader L174-176 | L174-176 |
| `G7` | loader L198, L363-365 | L198, L362-366 |
| `G8` | loader L201 | L201 |
| `G9` | loader L199, L434-438 | L199, L434-438 |
| `G10` | loader L426-431 | L426-431 |
| `G11` | loader L325-342 (+ L517 via mixture L280, §4.3) | L325-342 |
| `G12` | loader L60-63, L333-338, L517-531 | L60-63, L331-336, L523-530 |
| `G13` | loader L376-381 | L373-378 |
| `G14` | repair L120-163 | repair L120-193 |
| `G15` | stats L255-256 | (added 2026-10-01; was `U1`) |
| `G16` | stats L256, loader L527 | (added 2026-10-01; was `U2`) |

The upstream file did not move between the draft and the pin; the loader is
byte-identical. Every difference in the right-hand column is a transcription or
range-choice error in the draft (three off-by-ones, plus span differences where the
anchors chose slightly wider or narrower ranges). That is why citations are generated
from the vendored source rather than typed.

---

## 10. Re-pinning

1. Fetch the new commit's files (the nine in §0) into `vendor/groot_<sha7>/`. Do not edit
   the old directory.
2. Point `GROOT_SHA` in `conformance/contract.py` at it. An `ImportError`/`LookupError`
   means an anchor moved or disappeared. Re-read that clause.
3. `diff` the contract-relevant ranges between the two vendored directories. Re-read §1:
   the entrypoint chain is where earlier readings of this contract needed correcting.
4. Record what moved in `NOTES.md`. A contract diff between two pins is itself a result.
