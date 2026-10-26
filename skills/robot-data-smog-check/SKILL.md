---
name: robot-data-smog-check
description: Check whether a robot dataset in LeRobot format is ready to fine-tune NVIDIA Isaac GR00T and Physical Intelligence's pi0.5 (openpi), locally and from metadata only. Explains what's missing and how to fix it, drafts GR00T's meta/modality.json and a pi0.5 config plan, and writes or verifies a conformance manifest. Use when someone asks if their robot, teleop or demonstration data is GR00T-ready or pi0.5/openpi-ready, before uploading or training on a dataset, or when sending or accepting a dataset delivery.
---

# Robot Data Smog Check

Answers, for one dataset: **can each model's data loader read it, does its shape fit the model, and
what is the shortest path to yes?**

- **GR00T:** 28 checks, each tied to a line of Isaac-GR00T's loader (commit `51d4c89`).
- **pi0.5 (openpi):** whether openpi's pinned LeRobot can load the files (openpi `215abfb`, LeRobot
  `0cf8648`), and eight fit checks against pi0.5 as openpi ships it (`pi05_base`): action and state
  at most 32 wide, one to three RGB cameras, fps against the 50-step action chunk, task prompts.

**Privacy is the point.** It reads only `meta/*.json(l)` and the file listing (names and sizes).
It never opens episode parquet or video, and it uploads nothing. Say this to the user when it
matters: private or vendor data never has to leave their machine.

## When to use it

- "Is my dataset GR00T-ready?", "Can I fine-tune pi0.5 / openpi on this?", "Why won't it load?"
- Before uploading a LeRobot dataset, or before spending GPU time on fine-tuning.
- A data vendor is about to deliver, or a buyer has just received, a dataset: use the manifest workflow below.
- Not for RLDS, HDF5 or rosbag directly: those come back `NOT_LEROBOT`; they need converting to LeRobot first.

## How to run it

Python 3.9+, nothing to install for a local folder. Run from anywhere:

```bash
python3 <skill-dir>/scripts/smog_check.py check <dataset-folder> --draft
```

- `<dataset-folder>` is one LeRobot dataset root, the folder that contains `meta/info.json`.
  If the user points at a parent folder, look for subfolders with `meta/info.json` and check each.
- `--model groot` or `--model pi05` limits the check to one model. The default checks both; if the
  user asked about only one, pass that one and report only that one.
- A Hugging Face id (`user/dataset` or its URL) also works, but needs `pip install huggingface_hub`
  and network. Prefer a local folder when the user has one.
- `--draft` writes proposals at the dataset root, never into `meta/`: `modality.draft.json` when GR00T
  is missing that file, and `pi05_config_plan.md` for pi0.5.
- `--details` prints the full report (every check, step-by-step fixes); `--all` adds a table of every
  GR00T check. `--json` gives machine-readable output, for when you need to reason over details; it is
  not for showing the user.
- Exit code is 0 whenever the check ran, whatever the verdict; 2 means it could not run. The verdict is
  in the report. (`--strict` makes a not-ready dataset or a manifest mismatch exit 1, for CI; don't
  use it here.)

## How to report the result

By default the script prints a short **diagnostic summary** in Markdown: a dataset table, then for each
model its verdict, a checkbox per area (✅ / 🟡 / ❌) and the next step. The summary is the answer, and
every run should look the same:

- **Always write in English**, whatever language the user writes in and whatever other language
  preference applies (memory, CLAUDE.md). The report is a shareable artifact; it is never translated.
- **Show the summary exactly as printed**: same headings, checkboxes and wording. Do not summarize,
  reorder, re-word, translate, or wrap it in a code block. Do not add text before it.
- After it, add **one line only**, asking whether they want the details, e.g.
  "Want the full details: every check and step-by-step fixes?"
  If something would actually stop training that the report can't see, put one `> **Note:**` line
  before that question (for example, openpi checks every frame's timestamp against fps when it loads).
- **If they say yes**, run again with `--details` (keep `--model` and `--draft` as before) and show that
  report the same way, exactly as printed, then offer the obvious next action in one question (e.g.
  copying the modality.json draft into `meta/` once they've confirmed the gripper index).
- If the user asked about one model, pass `--model groot` or `--model pi05`; the output then covers
  only that model.

Icons: ✅ passes or ready, 🟡 close (one fix or a config away), ❌ not yet, ⚪ skipped or not checked.

**What the verdicts mean** (for follow-up questions; the report already says this in plain words)

**GR00T verdicts**

| verdict | say | typical fix |
|---|---|---|
| `READY` | Nothing in the files blocks GR00T's loader. | none |
| `NEEDS_MODALITY` | One file away: `meta/modality.json` is missing. | review the draft, then add it |
| `NEEDS_DOWNCONVERT` | Uses LeRobot v3.0; GR00T reads v2 today. | NVIDIA's `convert_v3_to_v2.py`, then modality.json |
| `INCONSISTENT_MODALITY` | Ships modality.json, but it disagrees with the data. | fix the groups the tool names |
| `NEEDS_REPAIR` | Some listed episodes' files are missing. | add them, or GR00T's repair script drops them |
| `BLOCKED` | Something no converter fixes, usually metadata with no episodes. | the producer has to supply data |
| `NOT_LEROBOT` | No `meta/info.json` at this level. | point at a dataset root, or convert the format |

**pi0.5 loading** (openpi never loads a dataset with no code: its best state is `NEEDS_CONFIG`)

| verdict | say | typical fix |
|---|---|---|
| `NEEDS_CONFIG` | The files load; like every dataset, it needs a data config and norm stats. | follow the plan |
| `NEEDS_CONVERT` | Uses LeRobot v3.0; openpi's pinned LeRobot reads v2.x. | convert v3.0 to v2.1 first (untested with openpi; say so) |
| `NEEDS_TAG` | Hub only: the repo has no version tag openpi's loader accepts. | tag it, or copy it locally |
| `BLOCKED` | A file openpi's LeRobot reads is missing, or no episodes. | the reason the script gives |

**pi0.5 fit:** `FIT` (defaults work), `ADAPT` (fits once the config changes what the script lists,
such as a shorter `action_horizon` below 15 Hz), `NO_FIT` (pi0.5 as shipped can't train on it, such
as an action vector wider than 32 or no RGB camera).

If the data looks like vehicle or human-motion data, the report's Robot row and a note already say so.

## The modality.json draft (GR00T)

`meta/modality.json` says which slice of the state and action vectors is the arm, the gripper, and so
on. It is the one file GR00T needs that standard LeRobot does not define.

- The report shows the drafted groups; ask the user to confirm them against their robot. **A wrong gripper
  index does not raise an error; GR00T trains on the wrong joints.**
- Only after they confirm, copy `modality.draft.json` to `meta/modality.json`, then re-run the check.
- Group names must match the embodiment config they will train with. NVIDIA's demo uses `single_arm` and `gripper`.
- If no draft is possible (generic names like `motor_0`), say so and ask which dimension is which.

## The pi0.5 config plan

openpi keeps the mapping from dataset columns to model inputs in Python, so every dataset needs a
data config, a train config, and norm stats. `pi05_config_plan.md` drafts all three from `info.json`:
which camera goes in which of pi0.5's three image slots, the state and action keys, the
`RepackTransform`, `action_horizon`, the delta-action mask (joints relative, grippers absolute), and
the `compute_norm_stats.py` command.

- The report points to the file. Don't paste the plan unless asked.
- It is a proposal. Never edit the user's openpi checkout without their go-ahead, and tell them to
  check the camera-to-slot choice and whether their actions are absolute or delta.
- For a local dataset, openpi loads by repo id from LeRobot's cache (`$HF_LEROBOT_HOME/<repo_id>`),
  so no Hub upload or version tag is needed once the files are there.
- openpi also checks every frame's timestamp against fps when it loads the parquet; this check can't
  see that, so mention it if the user is about to train.

## Manifest workflow: shipping and receiving datasets

The manifest lets two parties agree a dataset meets the standard without either one uploading it.

**Producer (vendor, lab, or anyone sending data):**

```bash
python3 <skill-dir>/scripts/smog_check.py check <dataset-folder> --manifest
```

This writes `conformance.json` at the dataset root: the GR00T verdict and the checks that passed, the
pi0.5 loading and fit verdicts, dataset size (episodes, hours, cameras), and a SHA-256 fingerprint of
the metadata files and the file listing. Ship it alongside the data.

**Receiver (buyer, training team):**

```bash
python3 <skill-dir>/scripts/smog_check.py verify <dataset-folder>
```

`VERIFIED` means what arrived has the same metadata, the same files at the same sizes, and the same
verdicts as what was checked at the source. `NOT VERIFIED` lists exactly what differs.

Be accurate about what it proves: it is an integrity record, not a signature (anyone can regenerate
it), and it does not hash episode or video payloads, so it cannot detect a same-size payload swap.

## Rules

- Never upload, copy elsewhere or open the episode/video payload to "check more". The tool's guarantee is metadata only.
- Never write into the user's `meta/` folder or their openpi code without their explicit confirmation.
- A v3 to v2 conversion rewrites the whole dataset; say so before suggesting it, and suggest working on a copy.
- Don't overclaim: say "passes the loader's static checks", not "compatible" or "good data".

## Background

The checks come from an audit of 562 public LeRobot datasets on Hugging Face against GR00T, LeRobot
and openpi. In a random sample of 200, none passed GR00T's checks as is, 30.5% were one file
(`modality.json`) away, and 58% needed converting from LeRobot v3.0 first; 30% were in a state
openpi could load once given a config. Method, per-check citations and the browser version (Robot
Data Smog Check) are in the source repo: https://github.com/vincentstanfordlead/lerobot-groot-conformance.
Independent project, not affiliated with NVIDIA, Physical Intelligence or Hugging Face.
