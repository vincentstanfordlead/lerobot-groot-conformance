# CONTRACT — what LeRobot and openpi require of a LeRobot dataset

Companion to [`CONTRACT.md`](CONTRACT.md) (Isaac-GR00T). Written 2026-10-02. Two more columns for
the same audit, so the question becomes "how much of this data can each open model load today",
not only GR00T.

| column | pinned code | reads |
|---|---|---|
| **LeRobot** (native policies: ACT, Diffusion, SmolVLA, …) | lerobot [`ff71cae`](https://github.com/huggingface/lerobot/tree/ff71cae1ae2d09fd035553c35da65888ed6c8304), main on 2026-10-02 — [`vendor/lerobot_ff71cae/`](vendor/lerobot_ff71cae/) | v3.0 only |
| **openpi** (π0, π0.5) | openpi [`215abfb`](https://github.com/Physical-Intelligence/openpi/tree/215abfb217dbac7d5f1273282331b9b1866c0479), main on 2026-10-02 — [`vendor/openpi_215abfb/`](vendor/openpi_215abfb/); it loads data through lerobot [`0cf8648`](https://github.com/huggingface/lerobot/tree/0cf864870cf29f4738d3ade893e6fd13fbd7cdb5) (2025-05-28), pinned in `pyproject.toml:70` — [`vendor/lerobot_0cf8648/`](vendor/lerobot_0cf8648/) | v2.0 / v2.1 only |

Line numbers refer to the vendored copies. Failure classes are the ones in `CONTRACT.md` §0:
**LOUD** raises, **SILENT** loads but is wrong, **REPAIRED** fixed by the loader.

**Scope: loading by Hub `repo_id`.** Both columns are judged for `LeRobotDataset("<org>/<name>")`
with no `root=`, which is how openpi's training config names data (`data_loader.py:140-146`) and how
the LeRobot docs load Hub datasets. A user who downloads the files and passes `root=` skips §1;
that path is noted, not scored.

---

## 1. Hub revision: the repo needs a version-named branch or tag (both columns)

Neither loader reads `codebase_version` from `info.json` to decide *which revision to download*.
Both list the repo's branches and tags, keep the names that parse as versions, and pick one
(`get_safe_version`). The default target is the loader's own `CODEBASE_VERSION`.

| | LeRobot `ff71cae` | openpi → lerobot `0cf8648` |
|---|---|---|
| target | `v3.0` (`src_lerobot_datasets_dataset_metadata.py:63,117`) | `v2.1` (`lerobot_common_datasets_lerobot_dataset.py:77,89`) |
| ref listing | `src_lerobot_datasets_utils.py:387-407` | `lerobot_common_datasets_utils.py:306-316` |
| selection | `src_lerobot_datasets_utils.py:410-453` | `lerobot_common_datasets_utils.py:319-360` |
| called from | metadata `dataset_metadata.py:144-150`; data `lerobot_dataset.py:335-341` | metadata `lerobot_dataset.py:96-102`; data `lerobot_dataset.py:500-503` |

Selection rule (identical in both): exact target ref → use it; else the highest ref with the same
major and minor ≤ target; else raise.

| repo refs | LeRobot (target v3.0) | openpi (target v2.1) |
|---|---|---|
| no version-named ref | **LOUD** `RuntimeError` (`utils.py:439-440`) | **LOUD** `RevisionNotFoundError` (`utils.py:327-337`) |
| `v3.0` | ok | **LOUD** `ForwardCompatibilityError` |
| `v2.1` | **LOUD** `BackwardCompatibilityError`, message gives the v2.1→v3.0 converter (`utils.py:69-72`) | ok |
| `v2.0` only | **LOUD** `NotImplementedError` "Contact the maintainer" — no converter named (`utils.py:73-76`) | ok (v2.0 ≤ v2.1) |
| both `v2.1` and `v3.0` | ok (takes `v3.0`) | ok (takes `v2.1`) |

The last row is the only way one repo serves both columns without conversion.

## 2. `info.json` version gate

`check_version_compatibility` runs on the *downloaded* `info.json`:
LeRobot `src_lerobot_datasets_utils.py:353-384` (called at `dataset_metadata.py:219`);
openpi's lerobot `lerobot_common_datasets_utils.py:284-303` (called at `lerobot_dataset.py:106`).
It raises only when the dataset's **major** is *below* the loader's; a lower minor logs a warning.
A higher major is not caught here — e.g. a v3.0 `info.json` under a `v2.1` tag passes this gate
in openpi and fails later on missing v2 files (§3). The audit reports a tag/`info.json`
mismatch as its own finding.

## 3. Files read

**LeRobot `ff71cae` (v3.0 layout)**, `dataset_metadata.py:217-222`:
- `meta/info.json` — **LOUD** if missing (`io_utils.py:125-135`; path `utils.py:93`)
- `meta/tasks.parquet` — read only when `total_tasks > 0` (`dataset_metadata.py:220`; path `utils.py:144`)
- `meta/episodes/chunk-*/file-*.parquet` — read only when `total_episodes > 0` (`dataset_metadata.py:221`; `io_utils.py:213-219`)
- `meta/stats.json` — optional; `None` if absent (`io_utils.py:162-176`)
- data `data/chunk-XXX/file-XXX.parquet`, video `videos/<key>/chunk-XXX/file-XXX.mp4` (`utils.py:146-147`)

**openpi → lerobot `0cf8648` (v2 layout)**, `lerobot_dataset.py:104-115`:
- `meta/info.json`, `meta/tasks.jsonl`, `meta/episodes.jsonl` — all **LOUD** if missing (`utils.py:177-223`)
- `meta/stats.json` if `codebase_version < v2.1`, else `meta/episodes_stats.jsonl` — **LOUD** if the one it wants is missing (`lerobot_dataset.py:108-114`)
- one parquet per episode, `data/chunk-XXX/episode_XXXXXX.parquet` (`utils.py:56`); before loading it checks every episode file exists and downloads the missing ones (`lerobot_dataset.py:495-503`)

## 4. Data-level checks (not covered by the static audit)

- **openpi only — timestamp sync.** Every frame must sit at `k/fps` within `tolerance_s = 1e-4`
  s, checked over the whole dataset at load (`lerobot_dataset.py:362,505-511`;
  `utils.py:469-539`). **LOUD.** LeRobot `ff71cae` no longer runs this check (no
  `check_timestamps_sync` anywhere in `src/lerobot`). Needs the parquet, so the metadata-only
  audit cannot see it.
- `delta_timestamps` must be multiples of `1/fps` (openpi's lerobot `utils.py:542-569`;
  LeRobot `feature_utils.py:174`). openpi builds them from `fps` (`data_loader.py:143-145`),
  so this holds whenever `fps` is declared.

## 5. openpi needs per-dataset code, always

Unlike GR00T, where the missing piece is one data file (`meta/modality.json`), openpi's mapping
from dataset columns to model inputs lives in Python:

- a `DataConfigFactory` subclass per dataset, with `repack_transforms` that rename dataset keys
  to model keys (`config.py:65-91`, e.g. `LeRobotAlohaDataConfig` `config.py:229-279`);
- `action_sequence_keys` naming the action column — default `("actions",)` (`config.py:88`),
  while LeRobot datasets usually call it `action`, so configs override it (`config.py:255`);
- normalization stats computed by `scripts/compute_norm_stats.py` and stored under the config's
  `asset_id`; training raises without them (`data_loader.py:175-181`) — **LOUD**;
- with `prompt_from_task=True`, every frame needs a `task_index` present in the task table, or
  `PromptFromLeRobotTask` raises (`transforms.py:310-322`; `data_loader.py:148-149`).

So no dataset is "load as is" for openpi. The best a dataset can be is **NEEDS_CONFIG**: the files
load (§1-3), and what remains is writing the config and running the stats script.

## 6. Verdict ladder for the two new columns

| verdict | LeRobot | openpi |
|---|---|---|
| **PASS** | §1 picks `v3.0`, §2 major 3, §3 files present | — (not reachable, see §5) |
| **NEEDS_CONFIG** | — | §1 picks `v2.x`, §2 major 2, §3 files present |
| **NEEDS_TAG** | data is v3.0 but no version-named ref | data is v2.x but no version-named ref |
| **NEEDS_CONVERT** | data is v2.1 (converter exists); v2.0 also needs v2.0→v2.1 first | data is v3.0 (back-conversion, e.g. GR00T's `convert_v3_to_v2.py`) |
| **BLOCKED** | no episodes, not LeRobot, or unreadable `info.json` | same |

NEEDS_TAG is the cheapest fix there is: one `create_tag` call, which LeRobot's own error message
prints (`utils.py:54-63`).

## 7. π0.5 model fit

Added 2026-10-23. §1–6 ask whether openpi can *load* the files. This asks whether what is in them
fits **π0.5**, the openpi model people use most (`pi05_base`: 172k all-time downloads of the LeRobot port
`lerobot/pi05_base` vs 135k for `lerobot/pi0_base`, Hugging Face API, 2026-10-23), as openpi
ships it: `Pi0Config(pi05=True)`. Judged from `info.json` only; independent of the §6 verdict.
Files: `vendor/openpi_215abfb/src_openpi_models_*.py`, `..._transforms.py`, `..._training_config.py`.

| id | requirement | source | if not met |
|---|---|---|---|
| P1 | actions are one float vector (`action`/`actions`, else `action.*` sub-keys) | `data_loader.py:143-145` builds the chunk from `action_sequence_keys` | sub-keys: **ADAPT** (concatenate in the repack); none / not float: **FAIL** |
| P2 | action dim ≤ 32 | `pi0_config.py:25`; `pad_to_dim` pads, never truncates (`transforms.py:423-430`) | **FAIL** |
| P3 | state is one float vector (`observation.state` or `state`, else `observation.state.*` sub-keys), dim ≤ 32 | state input is `[batch, action_dim]` (`pi0_config.py:80`); π0.5 writes it into the prompt as 256-bin tokens (`tokenizer.py:22-28`), and raises "State is required" without it (`transforms.py:256-258`) | > 32: **FAIL**; missing: **ADAPT** (`discrete_state_input=False`, as `pi05_libero` does, `config.py:745`); split: **ADAPT** |
| P4 | 1–3 RGB cameras | three image slots `base_0_rgb`, `left_wrist_0_rgb`, `right_wrist_0_rgb`, all required (`model.py:39-43,156-157`); policies fill missing ones with zeros (`libero_policy.py:61-62`) | > 3: **ADAPT** (choose); 0 RGB (none, or depth only): **FAIL** |
| P5 | camera size | resized with padding to 224×224 (`model.py:47,163-165`; `image_tools.py:13-38`) | below 224 or aspect ≥ 1.5: **NOTE** |
| P6 | fps vs the 50-step chunk | `action_horizon=50` (`pi0_config.py:26`); openpi's own low-rate π0.5 configs shorten it: `pi05_libero` 10 (`config.py:745`), `pi05_droid` 15 (`config.py:631`) | no fps: **FAIL**; ≤ 15 Hz: **ADAPT** |
| P7 | mean episode length ≥ 50 frames | chunk steps past an episode's end are padding | **NOTE** |
| P8 | task strings for the prompt | "Prompt is required" (`transforms.py:252-254`); `prompt_from_task` (`config.py:91`) or `default_prompt` (`config.py:111`) | **ADAPT** |

Verdict: **NO_FIT** if any FAIL, else **ADAPT** if any ADAPT, else **FIT** (NOTE never lowers it).
FIT still means a data config and norm stats (§5), so `NEEDS_CONFIG` + `FIT` is the best a dataset gets.
π0.5 normalises with quantiles (`config.py:187`), which `compute_norm_stats.py` writes (`normalize.py:85-86`),
so P-checks add no step there. Thresholds for P5 (aspect 1.5) and P6 (15 Hz) are judgement calls, approved 2026-10-23 (NOTES).
