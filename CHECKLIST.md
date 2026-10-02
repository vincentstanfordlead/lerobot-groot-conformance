# Draft producer checklist for GR00T-readiness (v0.1)

This checklist is derived from the requirements published in NVIDIA's Isaac-GR00T repository
(code and docs at commit `51d4c89`) plus the failures observed in this project's audit of 562 public
LeRobot datasets. It is not an official or proposed standard, and feedback is welcome (open an issue).

It is meant to be read **before you start recording**. The items are in three tiers, kept
separate on purpose:

1. **Required:** GR00T's code or docs say so. Every item cites the file and lines.
2. **Observed:** the audit found it. Every item carries its count.
3. **Open questions:** these need model-side evidence. They are phrased as questions and not answered here.

Within tiers 1 and 2, **producer-side** items come first. They have to be captured at collection
time and can't be fixed later. **Converter-side** items can be fixed after the fact by a script
or by someone with the files. Format can be repaired after collection. Missing information usually
can't be.

To check a dataset against tiers 1 and 2:

```bash
.venv/bin/python -m conformance.inspect_local <dataset_dir>
```

Check IDs (`G*`, `L*`) refer to the linter ([`conformance/checks.py`](conformance/checks.py)) and
[`CONTRACT.md`](CONTRACT.md).

---

## Tier 1 — Required: GR00T's code or docs say so

Every citation is to [NVIDIA/Isaac-GR00T @ `51d4c89`](https://github.com/NVIDIA/Isaac-GR00T/tree/51d4c89f72fda44cbf77285c6a8114b52676b8a1)
(`main` on 2026-10-01). Copies of every cited file are in [`vendor/groot_51d4c89/`](vendor/groot_51d4c89/).
Shorthand: **dataprep** = `getting_started/data_preparation.md`, **loader** =
`gr00t/data/dataset/lerobot_episode_loader.py`, **stats** = `gr00t/data/stats.py`.

### Producer-side

- [ ] **1.1 Record state and action as two separate per-frame vectors.** Parquet columns
  `observation.state` and `action` hold "a 1D concatenated array of all state [action]
  modalities", and proprioceptive state "must always be included in" `observation.state`.
  · dataprep [L51-52](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L51-L52),
  [L167](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L167);
  default column names loader [L60-63](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L60-L63).
  *Producer-side because:* if the commanded action wasn't logged separately from the measured
  state, it can't be reconstructed.

- [ ] **1.2 Record a per-frame timestamp.** A `timestamp` column, "wall-clock time of this
  observation (seconds)". · dataprep [L53](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L53),
  [L62](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L62).
  *Not checked by the linter* (it is parquet content).

- [ ] **1.3 Record the true frame rate in `info.json:fps`.** The loader reads `fps` and silently
  assumes **30** if it is absent. · loader [L202](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L202). `L12`

- [ ] **1.4 Record discrete episodes with a known length and a task description.** Each episode
  is listed with its `length` and `tasks`; each task has a `task_index` and a `task` string.
  · dataprep [L86-110](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L86-L110);
  loader [L163-171](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L163-L171),
  [L204-213](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L204-L213). `G2`, `G3`
  *Producer-side because:* episode boundaries and the instruction given are facts about the
  recording session. The file format they are written in is converter-side (1.7).

- [ ] **1.5 Store each camera as its own MP4 per episode, keyed `observation.images.<name>`.**
  · dataprep [L41-45](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L41-L45);
  the loader's default video key is `observation.images.{key}`, and it asserts that the key is a
  feature, loader [L426-431](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L426-L431). `G10`

- [ ] **1.6 Upload every episode's files.** For every episode in the metadata, the `data_path`
  parquet and one `video_path` MP4 per camera must exist. NVIDIA's repair script defines these
  as the required files, and its fix is to **drop** the episode.
  · `scripts/repair_lerobot_metadata.py` [L120-163](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/scripts/repair_lerobot_metadata.py#L120-L163). `G14`
  *Producer-side because:* a converter can make the dataset load, but only the producer can
  keep the data.

### Converter-side

- [ ] **1.7 Use the LeRobot v2 layout.** `meta/episodes.jsonl`, `meta/tasks.jsonl`,
  `meta/info.json`, `data/chunk-*/episode_*.parquet`, `videos/chunk-*/<key>/episode_*.mp4`.
  The `info.json` templates must use only the placeholders the loader supplies:
  `data_path` uses `{episode_chunk}` and `{episode_index}`; `video_path` adds `{video_key}`.
  `chunks_size` must be present. v3.0 datasets are converted with NVIDIA's script.
  The docs say native v3 support is planned.
  · dataprep [L9-39](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L9-L39)
  (v3 plan: [L15](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L15));
  loader [L198-201](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L198-L201);
  `scripts/lerobot_conversion/convert_v3_to_v2.py` (accepts only `codebase_version == "v3.0"`,
  [L101-108](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/scripts/lerobot_conversion/convert_v3_to_v2.py#L101-L108)).
  `G2` `G3` `G7` `G8` `G9`

- [ ] **1.8 Add `meta/modality.json`.** It maps slices of `observation.state` and `action` to named
  groups (`{"start": int, "end": int}`), maps video keys to `original_key`s, and lists annotation
  keys. This is the one file standard LeRobot does not have.
  · dataprep [L7](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L7),
  [L112-162](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L112-L162);
  loader [L174-176](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L174-L176). `G6` `G11`
  *Converter-side* in the sense that the file can be written after recording. Writing it
  correctly needs someone who knows which dimension is which; see 2.1.

- [ ] **1.9 Keep every `modality.json` slice inside its column.** Indices are zero-based Python
  slices `[start:end]`. The loader applies them with numpy, which silently truncates an `end` past
  the column, and applies the same slice to the stats.
  · dataprep [L162](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L162);
  loader [L333-338](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L333-L338),
  [L517-531](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L517-L531). `G12`

- [ ] **1.10 Point every `modality.json` video and annotation entry at a column that exists.**
  The loader asserts on both. Set video `original_key` explicitly: the loader defaults it to
  `observation.images.{key}`, while the repair script defaults to `{key}`.
  · loader [L376-381](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L376-L381),
  [L426-431](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L426-L431);
  `scripts/repair_lerobot_metadata.py` [L109-117](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/scripts/repair_lerobot_metadata.py#L109-L117). `G10` `G13`

- [ ] **1.11 Give every feature a `dtype`, and make state and action float.** State and action are
  "stored as concatenated float32 arrays". Stats are computed only for `float` features, and the
  stats slice indexes them directly.
  · dataprep [L119](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L119);
  stats [L254-256](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/stats.py#L254-L256);
  loader [L527](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L527). `G15` `G16`

- [ ] **1.12 `meta/stats.json` is computed by GR00T; you don't have to ship it.** "We will compute
  `meta/stats.json` and `meta/relative_stats.json`." The training entrypoint regenerates them before
  every run. Eval/replay entrypoints read the loader directly and assert that `stats.json` exists.
  · dataprep [L166](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L166);
  `gr00t/data/dataset/factory.py` [L57-60](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/factory.py#L57-L60);
  loader [L179-182](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/dataset/lerobot_episode_loader.py#L179-L182). `G4` `G5` (WARN only)

---

## Tier 2 — Observed: the audit found it

Counts are from the audit of 2026-09-29 (562 repos, re-reported 2026-10-01). Every count is **per
stratum, never pooled**, as *curated / popular / recent / tail*. The strata were drawn differently,
and only **tail** is a random sample. Denominators are LeRobot-format datasets
(**162 / 92 / 99 / 199**) unless stated. Method: [`README.md`](README.md#method-and-limitations).
Full tables: [`results/report.md`](results/report.md).

### Producer-side

- [ ] **2.1 Name every state and action dimension: body part, side, quantity.** GR00T doesn't
  read `features.*.names`. Names are what let someone other than the original team write
  `modality.json` (1.8) later.
  - No `names` at all on state and/or action: **10 / 17 / 1 / 14**.
  - Names present but opaque (`motor_0..N`, `joint_3`, `0`) for at least one dim:
    **92/162 / 8/90 / 8/95 / 10/198** of datasets lacking `modality.json`.
  - Names clean enough that a keyword heuristic drafts a contiguous partition:
    **53/162 (33%) / 59/90 (66%) / 81/95 (85%) / 167/198 (84%)**. This is a heuristic, hand-checked
    on about 50 datasets, so treat it as ± a few points.

- [ ] **2.2 Upload the episode data, not just the metadata.** Repos with an `info.json` but no
  parquet under `data/`: **0 / 1 / 0 / 22**. In tail, that is 22 of 199 (11%). Nearly all are
  0-byte v3.0 repos, many named `eval_*`. The audit cannot tell aborted recordings from
  deliberate metadata-only pushes. No converter can fix either. Verdict: `BLOCKED`.

- [ ] **2.3 Make sure every listed episode's files are uploaded.** Episodes listed in metadata
  whose parquet or MP4 is absent (1.6): **0/29 / 3/42 / 0/7 / 0/61** of v2.x datasets where this
  could be checked under the 2 MB metadata cap.

- [ ] **2.4 Record `observation.state` and `action` as features.** Datasets declaring neither
  column in `info.json:features`: **5 / 6 / 0 / 7**. (1.1 requires them. Whether these repos store
  state under another key was not checked.)

- [ ] **2.5 Declare the real fps; don't rely on the default.** `fps` was declared in all
  **552/552** LeRobot-format datasets. **255 of 552** are not 30 Hz: 10, 15, 20, 50 and 5 Hz
  are all common. A dataset that omitted `fps` (1.3) would be read at the wrong rate about
  half the time.

- [ ] **2.5a Set `info.json:robot_type` to the actual robot.** It's the one field that says what
  recorded the data. `robot_type` is missing or `"unknown"`: **75/162 / 7/92 / 0/99 / 4/199**. For the
  curated stratum (mostly older Open-X ports) that's nearly half, so neither people nor tools can tell
  what robot recorded those datasets without going back to the source paper.

- [ ] **2.5b Check that it's robot data the target model trains on.** Format and fit are separate.
  Well-formed LeRobot datasets that are vehicle driving or human motion capture, outside GR00T's arm /
  hand / humanoid scope: **1 / 2 / 0 / 2** (heuristic, `conformance/embodiment.py`). Three of these
  pass every FAIL-level check except `modality.json`.

### Converter-side

- [ ] **2.6 Ship `meta/modality.json`.** Absent: **162/162 / 90/92 / 95/99 / 198/199**. This is
  the main gap between the open LeRobot format and GR00T's training format (`NEEDS_MODALITY`).
  It is not a defect in any dataset, since standard LeRobot doesn't define the file.

- [ ] **2.7 Convert v3.0 layouts before use.** v3.0 layout, with episode data present:
  **127 / 30 / 92 / 116**. In tail that is 58%, 95% Wilson CI [51%, 65%]. The curated layer is
  mostly v3.0 because current `lerobot` writes v3.0 by default (`lerobot/*`: 124/124).
  Median repo size (an upper bound on the conversion download): **1.9 / 32.9 / 0.6 / 0.2 GB**.

- [ ] **2.8 When you do ship a `modality.json`, cover every dimension.** **1 of 7** datasets that
  ship one leaves a state dimension in no group. GR00T never reads that dimension and raises no
  error. The same file also lists annotation keys that are not columns. (1.9 and 1.10 cover only
  out-of-range slices. "Cover every dim" is this checklist's addition.)

- [ ] **2.9 Check the file layout, not the `codebase_version` string.** One `v3.0` string covers
  **8** distinct metadata layouts in this sample, and **1** dataset declares v3.0 over a v2-style
  layout. GR00T never reads `codebase_version`, and NVIDIA's converter accepts only the exact string
  `"v3.0"` (1.7).

- [ ] **2.10 Keep `total_episodes` equal to the episodes listed.** Mismatch: **0/29 / 1/44 / 0/7 /
  0/61** of datasets where both were readable. GR00T reads `episodes.jsonl`, so this is a
  LeRobot-consistency warning only.

- [ ] **2.11 One dataset per repo root.** **8 of 562** audited repos are containers with LeRobot
  datasets in subfolders (**0 / 7 / 1 / 0** of all audited repos). GR00T is pointed at one
  dataset directory at a time.

- [ ] **2.12 Shipped stats are optional (1.12).** No `meta/stats.json`: **24 / 49 / 7 / 82**.
  Shipped `stats.json` missing at least one of the six stat types GR00T uses: **122/138 / 21/43 /
  0/92 / 9/117**. Both are regenerated at training time, so neither is a blocker.

---

## Tier 3 — Open questions: these need model-side evidence

These are questions, not rules. This audit has no evidence to answer them. Answering them takes
training runs, not metadata checks.

- **3.1 Which action space should be recorded?** GR00T N1.7 "adopts a relative end-effector action
  space shared across robot and human embodiments"
  ([upstream README L90](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/README.md?plain=1#L90)).
  The fine-tuning example uses relative joint-space actions for the arm and absolute actions for the
  gripper ([finetune_new_embodiment.md L48-60](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/finetune_new_embodiment.md?plain=1#L48-L60)),
  and GR00T derives relative chunks from recorded actions itself
  ([stats L294-364](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/gr00t/data/stats.py#L294-L364)).
  Most public hobby data records absolute joint positions. Is absolute joint position plus the robot
  model enough to derive relative EEF actions after the fact? Or does EEF pose need to be logged at
  collection time? If so, this belongs in tier 1, producer-side.
- **3.2 What is the minimum useful episode count per task and embodiment?** NVIDIA's 5-episode
  demo explicitly does not set a target, and it attributes poor held-out results to "data
  scarcity" ([finetune_new_embodiment.md L166](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/finetune_new_embodiment.md?plain=1#L166),
  [L190](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/finetune_new_embodiment.md?plain=1#L190)).
- **3.3 How fine should task labels be?** One instruction per episode, or sub-task segments?
  GR00T supports several annotation channels per frame
  ([dataprep L171-175](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/getting_started/data_preparation.md?plain=1#L171-L175)),
  but nothing here says which granularity helps.
- **3.4 How much environment and operator diversity is enough?** The pretraining mixture is
  described as "diverse" ([upstream README L68](https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/README.md?plain=1#L68)).
  Is there a threshold below which a dataset adds little, for example one table, one operator,
  one lighting setup?
- **3.5 Should `modality.json` group names come from a shared vocabulary?** Group names have to
  match the embodiment config used for training (CONTRACT §4.3). A shared naming vocabulary would
  make pooling across producers mechanical. Would it constrain embodiments the vocabulary didn't
  anticipate?
- **3.6 Should evaluation rollouts be published alongside demonstrations, and how should they be
  labelled?** Many public repos are `eval_*` runs (see 2.2). Are failed or partial rollouts useful
  training data if they are labelled as such?
- **3.8 Should `robot_type` be a controlled vocabulary?** Today it's free text (`so101_follower`,
  `SO-101`, `so_follower`, `KIA Niro EV 2023`, `my_cool_robot`). A shared list of embodiment types would
  let tools route data to the right model automatically. Who would maintain it, and how fine should
  it be?
- **3.7 What calibration and unit metadata should travel with the data?** Examples: joint zero
  offsets, units, camera intrinsics. GR00T reads none of these, but they decide whether 3.1's
  conversion is possible later.
