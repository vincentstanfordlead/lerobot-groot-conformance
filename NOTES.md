# NOTES — lerobot-groot-conformance

Running log of discrepancies, surprises, decisions, and open questions. Newest entry at
the top. Dates are absolute. "The plan" means the project's working plan (not shipped);
every decision it drove is recorded here. `pilot/` scripts referenced in the oldest entries
were exploratory and are not shipped either. Individual datasets that fail a check are
not named here (ids are in `results/summary.csv`); public fixtures and publisher orgs are.

---

## 2026-10-02 — README: dataset mosaic and web app screenshot

- **Mosaic** (`docs/img/mosaic.jpg`, top of the README above the KPI row). 24 tiles, 6×4. Each tile is frame 45 of
  episode 0, first non-wrist camera, decoded from the video at the dataset's audited `repo_sha`
  (`scripts/fetch_mosaic_frames.py`, network, needs `pip install av`; only the start of each video is streamed).
  Thumbnails and `sources.json` (dataset, sha, camera, license) are committed, so `make_figures.py` rebuilds the
  mosaic offline. Badges are not typed: `make_figures.mosaic_kind()` reads `verdict` and `embodiment_fit` from
  `summary.csv`. All 24 sources are Apache-2.0 (from each card at the audited sha).
- **Selection** is hand-picked for visual variety, one dataset per author: 7 one file away, 16 needs conversion,
  1 outside scope (a race-car sim). The caption says the mix is illustrative and points to the scorecard.
- **Web app GIF** (`docs/img/webapp.gif`, ~15 s, under the "Try it in your browser" callout, linked to the site;
  replaces a two-screenshot PNG from earlier the same day). `scripts/record_webapp_gif.py` (Playwright driving the
  installed Chrome, network) types `lerobot/aloha_sim_transfer_cube_human` on the home page, shows its "Two steps
  away" report, closes it, and opens the Model Validation preview, ending on the "Coming soon / made-up sample
  data" banner so the mock-up is never shown unlabelled. The example is an official `lerobot` dataset and already
  the home page's own red example chip.

**Pending approval:**
1. Red badge means "not robot manipulation" (embodiment), while green/amber are format verdicts. The race-car
   dataset itself is format-wise one file away. The legend states the meaning; an alternative is no red tile.
2. Real datasets are recognisable in the mosaic even though no names are shown on it; `sources.json` names them
   (needed for Apache-2.0 attribution) but does not say which tile carries which badge beyond the tile number.
3. The GIF shows a Model Validation result for made-up data next to a real dataset's report; the banner and
   "sample data" label are on screen for the final ~4 s.

---

## 2026-10-01 — Preview pages: Leaderboard and Model Validation (`docs/app/preview.js`, `preview.css`)

Two new sections in the web app, reachable from the landing nav and a section-tab bar under the header. Both are
**mock-ups of future features**: all names and numbers are made-up sample data, nothing is fetched, saved or sent,
and a yellow "Coming soon" banner and "coming soon" tags say so on every page.

- **Leaderboard** (`#leaderboard`), three tabs. *Datasets*: ranked by the change in loss on a fixed reference set
  when the dataset is added, not by episode count; the sample data includes a 5,000-episode near-duplicate dataset
  that ranks 4th and a dataset that makes the model worse. *Builders*: towers of bricks (one brick per 50 clean
  episodes, colour bonuses for new task / robot / scene, orange for Model Validation gains, flat grey plates for
  near-duplicates that add no height). *Wanted*: a bounty board of data requests.
- **Model Validation** (`#validation`): request form (dataset, one of four open models, what to measure), a fake run that
  steps through four stages, and a sample result: loss with vs without the dataset, a data-scaling readout
  (25/50/100% of episodes) and a "would more help?" note.
- **Design reason for with/without instead of raw validation loss:** loss on a submitter's own held-out episodes
  measures consistency, not usefulness (500 copies of one pick score perfectly). The test trains the same model with
  and without the data, same steps, scores both on a reference set the submitter never touches, and reports the
  difference with error bars over several seeds. Rollout success is shown as "coming later" because BC loss
  correlates imperfectly with it. The research claims behind this (DataComp / DataPerf style benchmarks, robomimic's
  loss-vs-success finding, robot data-curation results) are from memory and not yet re-checked against sources.

**Pending approval:**
1. Keeping the name "Robot Data Smog Check" for all three sections, with the brick theme as a skin. The alternative
   is a brick-native rename so the metaphor matches ("Brickyard"). Not renamed.
2. The "brick" scoring rules (1 brick per 50 clean episodes; colour bonuses; gold/orange for Model Validation) are
   illustrative, not tuned.
3. The reference models and GPU-hour/cost figures on the Model Validation form are placeholders.
4. The theme colours are close to well-known toy-brick colours. Generic bricks only, no brand marks; consider
   shifting the reds/yellows slightly before the repo is public.

---

## 2026-10-01 — Rebrand to "Robot Data Smog Check", industrial theme, and a "what kind of data" check

**Name.** The web app is now *Robot Data Smog Check*; GripCheck is retired. The metaphor: a standardized
inspection with measured readings, done before the data "hits the road" to training. The UI copy
avoids "FAIL" stamps on datasets. The stamp reads PASS or NOT YET, and verdicts stay in
distance-to-ready language. The localStorage key changed, so the old GripCheck history doesn't carry
over.

**Theme.** Industrial "inspection station": graphite and steel, safety-yellow accents, a hazard
stripe, a blueprint grid, Space Grotesk headings and monospace labels. The mascot became a line-art
robot arm, which animates while an inspection runs, and each result gets a readiness gauge
(blocked → ready) like an emissions readout. The previous stylesheet is not kept in the repo.

**New: what kind of data is this?** (`conformance/embodiment.py` + `docs/app/embodiment.js`, kept in
agreement by `tests/test_js_parity.py` over all 552 cached `info.json` files). Prompted by
`yaak-ai/lerobot-driving-school`: well-formed LeRobot v2.1, `robot_type: "KIA Niro EV 2023"`, steering /
brake / gear actions. The format checks rate it "one step away", which is accurate about format and
misleading about usefulness.
- **Categories:** arm, bimanual, humanoid, mobile manipulator (these fit GR00T); vehicle, human motion
  (outside GR00T's scope); unclear.
- **Evidence order:** `robot_type`, then vehicle (≥2 of steer/brake/throttle/gear/lat/long) or
  human-motion (SMPL / mocap) feature names, then arm/body dimension names, then the dataset name.
  The name is used only for robot categories: "human" in `robocasa_..._human` means
  human-teleoperated.
- **Bugs caught while building it:** `koch_screwdriver_follower` matched "drive". `lerobot` in a
  dataset name was counted as arm evidence. A `\b` escaping slip stopped `yam` matching.
  `tests/test_embodiment.py` covers each case.
- **Audit result** (from `info.json` at the audited sha; no re-audit):
  - fits: 130/162, 89/92, 98/99, 193/199;
  - outside: 1 / 2 / 0 / 2;
  - unclear: 31 / 1 / 1 / 4.
  - 3 outside-scope datasets pass every FAIL-level check except modality.json, including 2 of the
    61 "one file away" in S-tail. So the robot-data share of the headline is 59/200.
- It doesn't change any verdict. It is reported as report.md §2c, `summary.csv` columns
  `embodiment*`, README "Format is not the same as fit", CHECKLIST 2.5a/2.5b/3.8, and a "What kind of
  data is this?" panel plus a violet callout in the web app.
- **Side finding:** `robot_type` is missing or "unknown" in 75/162 curated datasets (the old Open-X
  ports).

Report section 2c was renumbered (the old 2c "top 5 overall" is now 2d); the README's §2 anchor is
unchanged.

**Pending approval:**
1. The name "Robot Data Smog Check".
2. The theme.
3. Keeping embodiment separate from the verdict (option b would fold "outside scope" into a verdict).

---

## 2026-10-01 — GripCheck web app (`docs/`)

**What it is.** Paste a Hugging Face dataset link and get a verdict, every check explained in plain
English with its fix and the GR00T source lines, plus a drafted `modality.json` where the names allow.
The UI flow was modelled on OverEasy (a hackathon-winning security scanner): a dashboard of past runs,
a three-step "New Check" dialog, and a results view with a list on the left and details on the right.
The identity is its own: a robot-gripper mascot and the name "GripCheck". None of OverEasy's assets
are used.

**How it works.**
- Runs entirely in the browser; no server. Hugging Face's API and file downloads send CORS headers
  (verified 2026-10-01), so the page reads metadata directly, and each visitor uses their own
  rate-limit quota. History is kept in `localStorage`; `?d=<user>/<name>` links re-run a check.
- `docs/app/checks.js` is a line-for-line port of `conformance/checks.py`. `docs/app/draft.js` is a
  port of the goal-6 name classifier plus a draft generator.
- `tests/test_js_parity.py` runs both versions on:
  - the 3 fixtures;
  - 13 corrupted variants of NVIDIA's cube fixture;
  - corrupted copies of the public v2.1 fixture;
  - the classifier over all 545 cached `info.json` files: 0 differences.

  A planted bug in the JS verdict makes it fail, so the test is not vacuous.
- Live spot checks agreed with the CLI exactly: tictac-bot, so101 v3.0, and svla_so100_sorting.

**Draft rules.**
- A draft is offered only when state and action names are `looks_inferable`.
- If action has no usable names but the same dimension as state, it copies state's split and says so.
- A single shared non-left/right prefix (e.g. `main_` on every dimension) is treated as the robot's
  name, so a single arm gets NVIDIA's demo names (`single_arm`, `gripper`).
- `annotation` points at `task_index`, as in `cube_to_bowl_5`.
- Every draft is re-checked with the same 28 checks, and the page shows the resulting verdict
  alongside a "please verify" warning.

**Differences from the CLI** (shown in the UI where relevant):
- The `data/` + `videos/` listing is capped at 20k entries per folder (CLI: 200k); above that, G14 is
  skipped and reported as unverified.
- The nested-container scan is shallower: 12 listings, depth 4.
- A JSON `5.0` cannot be told from `5` in JS, so G12's integer test is slightly looser.

**Fixed during the build.** A new parity mutation wrote in place into a hard-linked fixture copy,
which changed `fixtures/cube_to_bowl_5/meta/episodes.jsonl`. The file was restored from git, and the
mutation now writes a new file and renames it. The suite leaves `fixtures/` clean.

**Pending approval:**
1. ~~The name "GripCheck".~~ Superseded: renamed to Robot Data Smog Check (entry above).
2. Hosting on GitHub Pages: Settings → Pages → Deploy from branch `main`, folder `/docs`.
3. Linking it from the top of the README.

---

## 2026-10-01 — README visuals

README restructured for a non-specialist first read. Plain-language sections and figures come first;
the full tables, method and limitations sit in collapsible `<details>` blocks (content unchanged).

Figures are made by `scripts/make_figures.py`: `docs/img/kpi.png`, `funnel.png`/`funnel.gif`,
`modality.gif` and `linter_demo.gif`. Every number is computed from `results/summary.csv` and
asserted. The terminal GIF replays real linter output saved in `docs/img/demo_output.txt`; long
lines are clipped to the terminal width.

Also:
- Added `--brief` to both linter CLIs (prints only checks that don't pass, plus a tally).
- Enlarged the text in the stratum chart; its data is unchanged.
- All figures are drawn 1000 px wide, because GitHub shows README images at about 830 px.

The funnel uses S-tail only, the random sample. Its steps are nested filters:
- LeRobot format;
- has parquet under `data/`;
- not `NEEDS_DOWNCONVERT` or `BLOCKED`;
- ships `modality.json`.

Its 61 equals the `clean_except_modality` count.

---

## 2026-10-01 — Publication pass: upstream re-check, brief alignment, corrections

**Upstream re-checked.** `git ls-remote https://github.com/NVIDIA/Isaac-GR00T` on 2026-10-01:
`main` = `51d4c89f72fda44cbf77285c6a8114b52676b8a1`, the same commit as the pin. Nothing to
re-vendor. Read for the first time this pass and vendored at the same sha: the top-level
`README.md` (as `upstream_README.md`), `getting_started/data_preparation.md` and
`getting_started/finetune_new_embodiment.md`.

**What those docs changed:**
1. **The format *is* documented.** `data_preparation.md` gives the layout, the parquet columns,
   the `modality.json` schema, and "We will compute `meta/stats.json`". The earlier README/CONTRACT
   sentence "the rules are not written down anywhere" was wrong and has been removed. CONTRACT.md
   now describes itself as going one level below the guide: per-clause failure behaviour with line
   citations.
2. **NVIDIA plans native v3 support** (`data_preparation.md` L15: "We plan to support both v2 and v3
   formats natively in a future release"). `NEEDS_DOWNCONVERT` is framed as a current gap, not a
   defect.
3. **A second loading path exists.** GR00T N1.7 also trains through LeRobot's own `groot` policy
   (upstream README L262-264), which uses LeRobot's loader. That path is out of scope, and this is
   now stated in README Limitations and CONTRACT §1.3. Not checked: whether the LeRobot path needs
   `modality.json` or reads v3.0 natively. An expert reader will likely ask.
4. **N1.7 uses a relative EEF action space** (upstream README L90). The fine-tuning example uses
   RELATIVE joint actions for the arm and ABSOLUTE for the gripper
   (`finetune_new_embodiment.md` L48-60). Cited in CHECKLIST tier 3, not answered.

**Discrepancies between the hand-off brief and the repo** (where they disagree, the repo wins):
- Brief M5 (stats present) would be FAIL. In GR00T, training regenerates stats (factory L57-60,
  dataprep L166), so `G4`/`G5` stay WARN.
- Brief S3 (`videos/` exists) would be FAIL. A state-only dataset is not a format defect, so `L4`
  stays INFO.
- Brief C1 (`episodes.jsonl` lines == `total_episodes`) is now `L11`. It is a WARN because GR00T
  never reads `total_episodes`.
- Brief verdict `BLOCKED` = "any FAIL outside G-series". Here a v3.0 layout is `NEEDS_DOWNCONVERT`,
  not `BLOCKED`, because NVIDIA ships the converter (judgement call 1 below).
- Brief says the work started on Sept 30. The files show Sept 28-29.

**Crosswalk: brief check → linter check.** IDs were kept so that `results/raw` and CONTRACT stay
stable.

| brief | here | note |
|---|---|---|
| S1 `meta/` | `L1` | fail → `NOT_LEROBOT` |
| S2 `data/`, S4 parquet | `L3` | fail → `BLOCKED` (new today, see below) |
| S3 `videos/` | `L4` (INFO), `L10` | |
| M1 info.json | `G1` / `L1` | |
| M2 codebase_version | `L2` (INFO) | GR00T never reads it |
| M3 episodes.jsonl | `G2`, `L5` | |
| M4 tasks.jsonl | `G3`, `L6` | |
| M5 stats | `L7`, `G4`, `G5` (WARN) | |
| F1 features | `L8` | |
| F2/F3 state/action dim | `L8` data, `G16` | |
| F4 cameras | `L8` data (`n_cameras`) | |
| F5 fps | `L12` (new) | |
| C1 episode count | `L11` (new) | |
| C2 parquet count vs episodes | `G14` | stricter: every episode's parquet + each camera's mp4 |
| C3 camera dirs | `L10` | |
| G1 modality.json | `G6` | |
| G2 state/action/video sections | `G11`, `G10` | |
| G3 max end == dims | `G12` | stricter: every slice in range *and* every dim covered |
| G4 video original_key in features | `G10` | |
| verdict NEEDS_MODALITY | `NEEDS_MODALITY` | renamed today from NEEDS_SEMANTICS |
| verdict BLOCKED | `BLOCKED` (+ `NEEDS_DOWNCONVERT`) | BLOCKED renamed from UNCLASSIFIED_STRUCTURE |

**Linter changes** (tests: 15 → 20, all pass):
- Renames: `NEEDS_SEMANTICS` → `NEEDS_MODALITY` (step `SEMANTICS` → `MODALITY`), and
  `UNCLASSIFIED_STRUCTURE` → `BLOCKED`.
- New checks:
  - `L11`: episode count, WARN.
  - `L12`: fps declared, WARN. The loader silently defaults to 30 (L202).
  - `G15`: every feature has a `dtype`. This was `U1`.
  - `G16`: state/action columns are float. This was `U2`.
- **Backfilled, not re-audited.** All four new checks take only `info.json` as input (L11 also
  uses the count stored in G2's detail), so `scripts/backfill_2026_10_01.py` computed them from
  `info.json` at each dataset's audited `repo_sha`. It fetched 7 more `info.json` files and 7
  `modality.json` files at those shas. Each raw row is stamped with `backfill`.
  - Results: G15 0/552 fail, G16 0/534 fail (18 skipped: neither column declared), L12 0/552 fail,
    L11 1/141 fail (S-popular).
- **New gate tests** (the brief's linter gate):
  - The real public `tictac-bot` comes out `NEEDS_MODALITY`.
  - A corrupted copy of it (no `episodes.jsonl`, no `chunks_size`) comes out `BLOCKED`.
  - A v3.0 copy with `data/` removed comes out `BLOCKED`.
  - Non-float action and a missing `dtype` each come out `BLOCKED`.
  - A control that pointed at a local path outside the repo was replaced with a self-contained
    "no `meta/`" control.

**Correction: metadata-only uploads were counted as `NEEDS_DOWNCONVERT`.** The new
"failures beyond modality.json" table showed 22/199 tail datasets with **no parquet under
`data/`** (`L3`).
- 20 are v3.0 repos with 0 bytes stored, most named `eval_*`.
- 2 are the v2.1 pair already `BLOCKED`.
- 1 popular repo stores episodes in a different columnar format.

No converter can produce data that was never uploaded, so `verdict()` now puts `L3` failure into
`BLOCKED`, ahead of the v3 check. **21 verdicts moved**, and the backfill script refuses any other
kind of move.

| | before | after |
|---|---|---|
| S-tail `NEEDS_DOWNCONVERT` | 136/200 = 68.0% [61.2, 74.1] | **116/200 = 58.0% [51.1, 64.6]** |
| S-tail `BLOCKED` | 2 | 22 |
| S-popular `NEEDS_DOWNCONVERT` | 31 | 30 |
| S-popular `BLOCKED` | 1 | 2 |

The earlier "S-tail 68% need a downconvert" figure overstated what the converter fixes.

**Report changes:**
- New §2, "What fails besides the missing `modality.json`", with tables by root cause and by check.
- New S-tail headline: passes every FAIL-level check except `modality.json` = 61/200 = 30.5%,
  CI [24.5, 37.2].
- Individual datasets are no longer named in `report.md`. Ids remain in `summary.csv` and
  `results/raw/`. The fix-cost medians changed with the reclassification.
- `pct()` prints `<1%` instead of `0%` for nonzero counts.

**Docs:**
- `CHECKLIST.md` is new. It has three tiers; every tier-1 item is cited to a file and line at
  `51d4c89`, and every tier-2 item carries its count.
- `SPEC.md` was removed, superseded by CHECKLIST.
- `README.md` was rewritten in the brief's order.
- `CONTRACT.md` framing was neutralised: no "undocumented contract" language, scope note §1.3,
  G15/G16 rows. A personal-notes section and personal references were removed from NOTES.
- Datasets named for a failure are anonymised in NOTES and CONTRACT.
- Added: `LICENSE` (MIT), the Apache-2.0 notice in `vendor/`, `fixtures/README.md` provenance,
  `scripts/reproduce.py` (one command), and `results/dataset_list.json.gz` (2.4 MB; the 38 MB
  JSON is gitignored and rebuilt).
- Verified: `reproduce.py` regenerates byte-identical `summary.csv`/`report.md`, and the rebuilt
  sample matches `strata.json`.

**Judgement calls — pending approval:**
1. **v3.0 stays `NEEDS_DOWNCONVERT` rather than `BLOCKED`.** NVIDIA ships the converter and plans
   native v3 support, so 386 "blocked" datasets would overstate the gap and read as a criticism of
   LeRobot's current default. Options: (a) keep [done]; (b) fold into BLOCKED per the brief.
2. **No parquet under `data/` → `BLOCKED`** (21 moved, above). Options: (a) keep [done];
   (b) give it its own verdict, e.g. `NO_DATA`; (c) revert.
3. **Check IDs kept (L/G) with the crosswalk above**, rather than renamed to the brief's S/M/F/C/G.
4. **Anonymisation scope.** Individual datasets are unnamed in README, report.md, NOTES and
   CONTRACT. Publisher orgs (lerobot, IPEC-COMMUNITY, nvidia, RoboCOIN) are still named. Per-dataset
   ids stay in `summary.csv`/`raw/` for reproducibility.
5. **Headline number = S-tail only** (the random sample). The other strata are reported but not
   pooled.
6. **LICENSE holder is "VincentD"** (git `user.name`). Change it if a full name is wanted.
7. **The optional GR00T-loader validation was not done** (it needs GR00T's full install plus
   payload downloads > 2 MB, against the brief's constraints). It is listed as a limitation.

---

## 2026-09-29 — README.md written

Plan §3 deliverable: headline distance-to-ready table (per stratum, no pooled rate) + chart + findings +
how to run + limits. Numbers copied from `results/report.md`; nothing re-run. All plan §3 deliverables now exist.

---

## 2026-09-29 — Phase 5: CONTRACT.md + SPEC.md — DONE (docs only; report.py and results/ untouched)

`CONTRACT.md`: the contract clause by clause, loud/silent/healed, construction vs mid-run,
citations @51d4c89 (G-citations copied from `contract.SOURCES`, others read off the vendored files).
`SPEC.md`: producer side (A1-A6) / converter side (B1-B4) / auto-healed (C1) / recipe-dependent (D),
with per-stratum rates from `summary.csv` (never pooled).

**Read beyond Phase 0: the entrypoints.** Vendored 4 more files at the same SHA (see vendor README):
`sharded_single_step_dataset.py`, `sharded_mixture_dataset.py`, `eval/open_loop_eval.py`,
`policy/replay_policy.py`. This changed one conclusion.

**Correction — `G11` is loud on the training path, silent only on eval/replay.**
`ShardedMixtureDataset.__init__` → `merge_statistics()` (mixture L242) → `get_dataset_statistics()`
(L280) → loader L517 indexes `self.modality_meta[modality][joint_key]` directly → `KeyError` at
construction if a recipe-requested group is missing. The `print()`-and-drop at L339-342 is reached only
by direct-loader users (open_loop_eval L147, replay L100; replay then raises for a missing *action* group).
**No number changes**: G11 fired 0/562; the one real silent case (one S-popular dataset) is G12.
The README sentence narrows from "both silent failures live in modality.json" to "the contract's
silent failure (G12) lives in modality.json". Plan §5.2/§9 and `checks.py` G11 detail string still say
"SILENT" — not edited.

**Other things found (all in CONTRACT.md):**
- Loader vs repair disagree on a video entry's default `original_key` (`observation.images.{key}`, L426-428,
  vs bare `{key}`, repair L109-117). G10 follows the loader, G14 follows repair.
- Video key positional auto-mapping (loader L278-297): if recipe camera names ≠ modality.json keys and counts
  match, cameras are mapped by order with a `logging.warning` — a silent camera swap. Recipe-dependent.
- `video_path` absent while the recipe requests video → loader returns no frames, no warning (L416-417).
  G9 already FAILs this case; 0 real instances.
- `length` ≠ parquet rows → silent truncation to the shorter (L599-601).
- 7 unchecked clauses `U1`-`U7` (CONTRACT §8): features/dtype (stats L254-256), float state/action (L527),
  camera order, annotation values ⊆ task_index, `episode_index` per line (L587; linter's G14 falls back to line
  position), `tasks` per line (L541), video frames ≥ length (L608).
- `convert_v3_to_v2.py` `snapshot_download` is L502 (Phase 0 table cited L40, the import).
- G14 fired in S-popular only (3), not S-curated as Phase 0 hypothesised.

**Judgement calls — all four approved 2026-09-29; G11 = option (b):**
1. Keep G11 at FAIL (it does break training, loudly) but relabel it "loud at construction on the training path;
   silent on eval/replay". Needs a `checks.py` detail-string edit + re-run; no verdict can move.
   Options: (a) edit now + re-run, (b) leave code, CONTRACT.md is the record, (c) defer to a re-pin.
   → **(b) approved**: `checks.py` and `results/` unchanged; CONTRACT.md §4.3 is the record of G11's real behaviour.
2. Vendored 4 extra upstream files (additive, same SHA) so every CONTRACT.md citation is reproducible offline.
3. `U1`/`U2`/`U5`/`U6` are cheap (inputs already fetched) — add as G15+ in a later pass? Not done: changes the
   check set, so it needs a full re-audit. `U3`/`U4`/`U7` need a recipe or payload and stay out of scope.
   → **approved**: add U1/U2/U5/U6 as G15+ in a later pass, together with a full re-audit; not done now.
4. SPEC.md classifies G14 as converter-side (repair tool exists) with prevention listed as producer-side A6,
   because the fix is lossy. Plan §5.3 lists it as converter only.

---

## 2026-09-29 — Phase 4: report — DONE (`conformance/report.py`)

`.venv/bin/python -m conformance.report [--offline]` → `results/{summary.csv, report.md,
goal6_inferability.csv, conformance_chart.png}`. Adds pandas 3.0.6 + matplotlib 3.11.2 to the venv. Read
`results/report.md` for every table; below are the decisions and what the numbers say.

**Decisions (approved in the Phase 4 request):**
- 8 `nested_datasets` containers are their own row `NOT_LEROBOT: container`; sub-datasets not audited.
  They stay in n (562 audited). 50 sub-datasets were *seen* (lower bound, 4 scans incomplete).
- 24 `unverified_size`: a READY with any unverified check is `READY†` (1, S-popular), never clean READY.
  On every other row the † count is footnoted and the distance is a lower bound.
- CI only for S-tail (the only random sample): NEEDS_DOWNCONVERT 136/200 = 68.0% [61.2%, 74.1%].
  S-curated is a census; S-popular/S-recent are top-100 sets.

**Judgement calls I made (pending your OK):**
1. Top-5 failures are per stratum, over LeRobot-format datasets only (NOT_LEROBOT would put G1 in every list).
   G2/G3/G7/G8/G9 are one root cause (v3.0 layout) and rank together; the table shows the v3 share.
2. Goal 6 needed `info.json` (raw JSON keeps only "names present?"). report.py re-fetches it at the audited
   repo sha (2 MB cap, cached in `results/info_cache/`, 545 fetches, 0 failures). Rate is a **keyword
   heuristic**, not ground truth; `looks_inferable` = every dim recognised AND each group one contiguous range.
3. Added two Phase 2 flags I had noted: S-popular with/without RoboCOIN, and author concentration.

**What the numbers say (goal 6 spot-checked below):**
- S-curated: 0 READY; `lerobot/*` is 124/124 NEEDS_DOWNCONVERT (all v3.0); the other 38 curated (IPEC, HF-VLA,
  PI, nvidia) are 35 NEEDS_SEMANTICS + 3 DOWNCONVERT. So "curated also fails" is really "the HF namespace moved
  to v3.0, GR00T reads v2.x" — two projects with unaligned contracts, confirmed.
- S-recent 92/100 v3.0 → NEEDS_DOWNCONVERT; the 4 READY are all from one producer (v2.1, 17-dim).
- `modality.json` absent in 98-100% of LeRobot-format datasets in every stratum; G6 is the only failure that
  is not v3-explained.
- Only real silent-failure instance: one S-popular dataset (G12, plus G13 loud).
- Drift: `v3.0` has 8 distinct signatures (episodes parquet vs none vs jsonl; quantile stats 236 pass / 130 fail);
  one S-recent dataset says v3.0 with a v2-style data_path.
- Goal 6 (heuristic, share of datasets lacking modality.json), after the manual check below: `looks_inferable`
  S-curated 33%, S-popular 66%, S-recent 85%, S-tail 84%. S-curated is low because 92/162 use `motor_0..N` names
  with no named gripper (opaque). Even `looks_inferable` gives only a partition; group names must still match the
  embodiment config.
- UNCLASSIFIED_STRUCTURE: an S-tail pair from one org have ~1 MB parquet and no videos (tiny/partial); an S-popular dataset
  has 76 GB parquet + 51 GB video with only info.json in meta/ (exporter-style). Different causes; still not proven.

**Goal-6 manual validation (2026-09-29, two rounds, ~50 datasets read against their real `names` lists).**
Round 1 (9 inferable / 6 opaque / 6 fragmented) found the first classifier wrong in both directions; round 2
(8 non-standard inferable / 8 fragmented / 6 opaque + all 12 reclassified) confirmed the fixes. Bugs found and fixed:
1. `chassis_pos_*`/`base_pos_*` were tagged eef position (keyword order) → base now precedes eef.
2. `head_yaw`, `torso_pitch` were tagged eef rotation → head/neck/torso/leg are their own groups.
3. Side detection took `left_left_carriage` / `right_left_carriage` both as L; now first side token, and
   `armN`, `umiN`, `main`/`aux` count as sides (else two-arm datasets looked fragmented).
4. `Joint1`, `joint_0` fell through to `_GENERIC` (opaque) or to `pos` (eef); digits are now stripped from tokens.
5. `carriage` added to gripper vocab (han10e prismatic gripper).
Effect (round-2 fixes, 545 datasets): fragmented 8→6, opaque 131→118, inferable 345→360 (+12 from opaque, +3 from
fragmented; 1 opaque→fragmented). Round-1 fixes had already taken fragmented 27→8. All 12 opaque→inferable moves are the
"`joint_0..6`/`motor_0..6` + a *named* `gripper`" pattern, where the arm is identified **by elimination**. That is a
softer claim than a fully named dim (e.g. is `motor_0..6` really joints?) - at most 12/545 (2%) of the rate.
Remaining known limits: `pad`, `r00..r21` (rotation matrix), `W/P/R` stay opaque (conservative); dual-arm datasets whose
two arms share identical names (`joint1..5` twice) come out fragmented (correct: index order is the only cue);
duplicate blocks (`bimanual-so101-pickvials-sim-2Dcam`, state 24 = 2×12) likewise. Precision on the sample read:
every `looks_inferable` partition I checked matched a plausible robot layout; no false-positive found in round 2.
Not estimated: recall of `opaque_names` beyond the ~6 read per round. Treat the rates as a heuristic ± a few points.


---

## 2026-09-29 — Phase 3: batch audit — DONE (562/562 audited, 0 excluded)

**Run.** 7 invocations (first full run by the author, then retries and re-audits), 32 min
wall clock, about 5.2k metadata requests, 31 MB downloaded (meta files only), $0,
unauthenticated. Every result is stamped GR00T `51d4c89`, `huggingface_hub` 2.0.0,
audit date 2026-09-29, plus the repo commit sha. One JSON per dataset is in
`results/raw/`. Console logs are in `results/run_*.log`, and a per-run summary line is in
`results/run_log.jsonl`.

**Exclusions: 0 final.** The first full run left **50 `rate_limited`** (12 curated,
2 popular, 12 recent, 24 tail). This was a client-side problem, not a dataset problem:
the backoff was too short (2→16 s) for HF's anonymous window (Retry-After ≈ 188 s).
The fix was a minimum 60 s × attempt for 429s. Rerunning at `--workers 1` cleared all 50
with 0 errors. The plan's rule holds: a high error rate meant my client was wrong.
**Recommendation for a rerun:** set `HF_TOKEN`.

**Verdicts, per stratum (n = sample size; raw counts only, analysis is Phase 4):**

| verdict | S-curated (162) | S-popular (100) | S-recent (100) | S-tail (200) |
|---|---|---|---|---|
| READY | 0 | 1 | 4 | 0 |
| NEEDS_SEMANTICS | 35 | 58 | 3 | 61 |
| NEEDS_DOWNCONVERT | 127 | 31 | 92 | 136 |
| INCONSISTENT_MODALITY | 0 | 1 | 0 | 0 |
| UNCLASSIFIED_STRUCTURE | 0 | 1 | 0 | 2 |
| NOT_LEROBOT | 0 | 8 | 1 | 1 |
| *…of which `unverified_size` ≠ ∅* | *6* | *18* | *0* | *0* |

**Linter changes during Phase 3** (tests still pass):
- **`NOT_LEROBOT` split: new fields `not_lerobot_reason` + `nested_datasets`.** 8 of the 10
  are **multi-dataset containers**: LeRobot datasets sit in subfolders
  (`OpenDriveLab-org/Kai0/Task_A/base/`, `TacVerse/opendata/taccap-*`, `LeCAR-Lab/Wanda/fridge/`, …).
  They are a mismatch in the audit unit, not a format defect. GR00T is pointed at one
  dataset directory, so the root verdict stays `NOT_LEROBOT`. The other 2 (`other`) are
  genuine: `Voxel51/aloha_pen_uncap` is FiftyOne format, and
  `jborbon/tape_pick_and_place` names its folder `meta_data/`, not `meta/`. Detection
  runs a breadth-first scan of directory listings (budget 25, depth ≤ 6), falling back
  to recursive listings of the top 5 folders. Needing both was found empirically: BFS
  missed deep or wide trees, and the recursive scan missed `Task_A/data/` sorting before
  `Task_A/meta/`. When `scan_complete` is False, `n_found` is a lower bound.
  - **Phase 4 decision needed:** report the 8 containers as their own row
    ("NOT_LEROBOT: container") rather than lumping them with the 2 genuine ones. Whether
    to audit the subdatasets is a separate question: it changes the sampling unit, so I
    have not done it.
- 429 backoff lengthened (above).

**Things Phase 4 must handle (observed, not yet analysed):**
- **S-curated has 0 READY, and 127/162 (78%) need a downconvert.** `lerobot/*` itself has
  migrated to v3.0. Pre-registered framing (plan §6 Phase 2): if curated also fails, the
  story is two projects with unaligned contracts, not hygiene. Confirm with the
  codebase_version cross-tab.
- **S-recent is 92% `NEEDS_DOWNCONVERT`**: current `lerobot record` defaults write v3.0,
  which GR00T can't read. This is the forward-looking number.
- **5 READY** (1 popular, 4 recent). One S-popular READY has
  G2/G14 unverified (size). The S-recent four (v2.1) share one producer: look at who
  these producers are. Hypothesis, not
  a finding: they are GR00T fine-tuners who wrote `modality.json` themselves.
- **1 INCONSISTENT_MODALITY**: one S-popular dataset ships a `modality.json`
  in which `observation.state` dim 6 of 8 is covered by no group (`G12`, **silent**), and
  whose `annotation` keys aren't in `features` (`G13`, loud). This is the first real-world
  instance of the silent-failure class.
- **3 UNCLASSIFIED_STRUCTURE**: v2.1, where `meta/` contains **only `info.json`**
  (1 S-popular, 2 S-tail from one org). Hypothesis: partial uploads, or an
  exporter (LeIsaac?) that writes only info.json. Check before claiming.
- **24 results with `unverified_size`** (6 curated, 18 popular): G2/G3/G14 were not
  checkable under the 2 MB cap. Footnote them; don't count them as clean.

### Phase 3 build notes


**Built:** `conformance/inspect_hub.py` (`HubView`, the same `DatasetView` interface as
`inspect_local`) and `scripts/run_audit.py`. Command: `.venv/bin/python scripts/run_audit.py`.
- **Requests per dataset: about 9.** dataset_info, root tree, meta tree, data/+videos/
  recursive trees, and up to 5 meta files. Every request is pinned to the repo commit sha
  resolved in the first call, and that sha is stamped into the result JSON. This is more
  than the plan's "2-4", because G14 needs `episodes.jsonl` plus the full listing. Smoke
  test: 8 datasets, 70 requests, 0.3 MB, 12 s.
- **2 MB rule enforced twice:** once on the listing size before any GET, and again as a
  byte cap on the body. **Correction to Phase 1 code:** an over-cap `episodes.jsonl` used to
  make `G2` **FAIL**; it now returns `SKIPPED(size)`, as do `G3` and `G5`. `G14` skips if
  `episodes.jsonl` is over the cap or the data/videos listing hit its cap (200k entries per
  directory, or 5k when G14 can't run anyway). This first bit on DROID
  (`IPEC-COMMUNITY/droid_lerobot`: `episodes.jsonl` is 7.3 MB, `tasks.jsonl` 2.7 MB).
- **New report field `unverified_size`:** a skipped check doesn't move the verdict, so a
  DROID-scale repo can come out `NEEDS_SEMANTICS` with G2/G3/G14 unverified. The field says
  so explicitly. Phase 4 must footnote these and must not count them as clean passes.
  Tests: `tests/test_size_cap.py`.
- **L10 on a capped listing** → `INFO` skip rather than "missing camera dirs".
- **Exclusion bucket** (`results/errors/`): gated, not_found_or_private, disabled,
  empty_repo, rate_limited (after 5 backoff retries honouring `Retry-After`),
  server_error, network, http_error, oversize_body, and `linter_exception` (a bug in my
  code, with the traceback kept). None of these enter the denominator. Errors are retried
  on the next run.
- **Fix-cost input:** `size.used_storage_bytes` from `dataset_info(expand=usedStorage)`,
  which is one free field. It covers the whole repo including LFS history, so it
  overstates what `snapshot_download` pulls. Also recorded: `parquet_/video_bytes_listed`
  from the listing, which is a lower bound when the listing was capped.
- The 8 smoke-test results are already in `results/raw/`. The full run resumes past them.

---

## 2026-09-29 — Phase 2: sampling frame (enumeration + strata only; no audit run)

**Env.** `.venv/` = Python 3.11.16 (conda-forge, `conda create -p ./.venv python=3.11`),
`huggingface_hub` 2.0.0. **Unauthenticated**: no `HF_TOKEN` set.

**Enumeration** (`scripts/collect_dataset_list.py` → `results/dataset_list.json`).
`HfApi().list_datasets(filter="LeRobot", expand=[author, downloads, downloadsAllTime, likes,
lastModified, createdAt, gated, disabled, tags])`, cursor-paged by the client. Snapshot
started 2026-09-29T05:29:27Z. **n = 78,296**, 0 duplicates, 14 s wall clock, ~79 requests,
$0. The pilot's ">60,000" was only a floor because it stopped after 60 pages. Rows are
sorted by id. `downloads` is the Hub's 30-day count. File is 40 MB, mostly `tags`.

**Strata** (`scripts/build_strata.py` → `results/strata.json`, plus `stratum`/`in_sample`
written back onto every row of `dataset_list.json`). **Seed `20260928`.** The strata are
disjoint and assigned in priority order, so every enumerated id sits in exactly one frame:

| stratum | rule | frame | sample |
|---|---|---|---|
| S-curated | `author.lower()` ∈ {lerobot, nvidia, ipec-community, huggingfacevla, physical-intelligence}; census | 162 | 162 |
| S-popular | top 100 **non-gated** by 30-day `downloads`, excluding S-curated; ties by `downloads_all_time` desc, then id asc | 136 (36 gated skipped) | 100 |
| S-recent | top 100 non-gated by `last_modified`, excluding the above; ties by id asc | 100 (0 gated) | 100 |
| S-tail | first 200 non-gated of `random.Random(20260928).sample(remaining ids sorted by id, len(frame))` | 77,898 (6 gated skipped) | 200 |
| **total** | | 78,296 | **562**, 0 gated |

**Gated policy (option b, approved 2026-09-29):** a gated repo is never sampled. Each
stratum takes the next non-gated id in its own order instead: the next rank for
S-popular/S-recent, the next position in the seeded permutation for S-tail. Skipped ids
stay in their stratum's frame and are listed in `strata.json:meta.gated_skipped`, so the
exclusion is on the record rather than hidden. Consequence for the writeup: **S-popular
means "most-downloaded *openly accessible*"**. 36 of the ranks down to #136 were skipped
(all `RoboCOIN`, `gated="auto"`); the popularity floor is now 1,633 downloads/30d.

Sample hashes (sha256 of the sorted ids, newline-joined): curated `573c4c76…`,
popular `81a2383e…`, recent `9236a440…`, tail `4091f57c…`. Full values are in `strata.json:meta`.

To redraw: rerun both scripts. Rerunning `build_strata.py` on the same `dataset_list.json`
reproduces the sample byte-for-byte; I ran it twice and the `sample_sha256` values matched.
A fresh enumeration will shift S-popular and S-recent, which are time-dependent by
definition. S-tail only shifts as far as the population itself changed.

**Decisions the plan didn't specify: all four approved 2026-09-29.**
1. **S-curated is defined by publisher allowlist, not by name match.** Plan: "`lerobot/*`,
   `nvidia/*`, and known benchmark republications (OXE, DROID, LIBERO, RoboCasa ports)".
   A regex on droid|libero|robocasa|oxe|fractal|bridge|metaworld|calvin matches **2,501**
   ids, 1,342 of them "libero". Most are personal re-uploads and eval runs, which is tail,
   not curation. Instead I added the three orgs that institutionally publish benchmark
   ports: **IPEC-COMMUNITY** (32; OXE + DROID + LIBERO-90), **HuggingFaceVLA** (3),
   **physical-intelligence** (2). `nvidia` has exactly 1 LeRobot-tagged dataset
   (`Arena-GR1-Manipulation-Task-v3`). `cadene` (the LeRobot maintainer's personal
   namespace) is excluded as a personal account; 3 of its datasets land in S-popular anyway.
   No RoboCasa-port org was found; `ember-lab-berkeley/robocasa365-*` falls in S-popular.
2. **S-curated is a census of 162, not capped at 100.** `lerobot/*` alone is 124. A census
   removes sampling error from the most important comparison (curated vs tail) and costs
   roughly 250 metadata requests. It puts the total at 562 against the 500 target.
   `--curated-cap 100` reverts to the plan's cap: a seeded subset, with S-tail unchanged.
   Note that `lerobot/*` includes some non-manipulation repos (`SMPL_samples`,
   `outdoor-depth`, `paris_street`, `abc_130k_v3_*`), so expect some `NOT_LEROBOT` there.
3. **Strata are disjoint, in priority order curated > popular > recent > tail.** The plan
   lists S-tail before S-recent. I drew S-recent first so that no id sits in two strata and
   S-tail is "everything else". This moves 100 ids out of a 78k frame, which is negligible.
4. **"downloads" means the 30-day count**, which is the Hub's `downloads` field. All-time
   is recorded and used only to break ties.

**Flags for Phase 3.** Facts about the sample; nothing has been changed because of them:
- ~~26/100 S-popular gated~~ → **resolved with option b** (see gated policy above). Gated
  repos in the population: 765/78,296.
- **One producer dominates S-popular: RoboCOIN has 32/100** after the gated replacement
  (42/100 before it) (808 datasets in the
  population, arXiv 2511.17441). S-popular results will partly measure RoboCOIN's
  converter. Report S-popular with and without RoboCOIN, or cap per author. Not done here.
- **S-recent covers only ~18 h** (2026-09-28T11:49Z → 2026-09-29T05:24Z), 15/100 of it
  from one author. 97/100 were created in the preceding week, so using
  `last_modified` rather than `created_at` makes no practical difference. Some of these
  repos may still be mid-upload; expect more "empty repo" exclusions here than elsewhere.
- S-tail: 200 ids from 177 distinct authors, median 34 downloads in 30 days.
- **The most-downloaded LeRobot datasets are IPEC-COMMUNITY's OXE ports**: 5 of the top
  6, 125k–215k downloads/30d, above `lerobot/*`. Observation: the de facto
  "curated" layer is a third-party porter, not HF or NVIDIA.

---

## 2026-09-28 — Phase 1: linter core — GATE CLOSED (8/8 on real fixtures)

**Built:** `conformance/contract.py` (citations generated from anchors in the vendored files),
`checks.py` (L1-L10, G1-G14, verdict), `inspect_local.py` (CLI: `python3 -m conformance.inspect_local <dir>`),
`tests/fixtures.py`, `tests/test_controls.py` (stdlib `unittest`, no deps; run
`python3 -m unittest discover -s tests -t . -v`). Python is the system 3.9 — code is 3.9-safe, no
3.11-only syntax; the venv/3.11 requirement from plan §4 isn't needed until `huggingface_hub`/pandas in Phase 2.

**Gate status: closed.** All eight controls pass on real fixtures (`fixtures/`, 1.4 MB total):
`cube_to_bowl_5` from `NVIDIA/Isaac-GR00T@51d4c89` (21 files, 29 KB; its parquet/mp4 are **git-LFS
pointer files**, ~130 B — the linter only reads names, so this is enough for `G14`), plus
`youliangtan/tictac-bot` (v2.1) and `whosricky/so101_pick_red_cube_3cams` (v3.0). For the two HF
datasets only `meta/` was fetched (all files < 2 MB); `data/`+`videos/` are **zero-byte placeholders
carrying the real names**, so `G14`/`L10` see the true listing. Verdicts: cube `READY`; tictac-bot
`NEEDS_SEMANTICS` with `G4` WARN (ships `episodes_stats.jsonl`); so101 `NEEDS_DOWNCONVERT`
(steps DOWNCONVERT+SEMANTICS; G2/G3/G7/G9 fail from `info.json` alone). The synthetic cube builder in
`tests/fixtures.py` remains as a fallback when `fixtures/` is absent. The positive control is
hand-built by NVIDIA, as predicted — no public dataset qualified (part of the finding).

**Generated citations vs plan v2.1** (all consistent with Phase 0 except where noted):
G2 L163-165, L204-213 · G4 L179-182 + factory.py L57-60 · G7 L198, **L363-365** (plan: 362-366) ·
G9 L199, L434-438 · G10 L426-431 · G11 L325-342 · G12 L60-63, L333-338, **L517-531** (plan: 523-530;
mine spans the whole stats-slice loop) · G13 L376-381 · G14 repair.py L120-163. Ranges I chose are
anchor-to-anchor, so they're slightly wider/narrower than the hand-typed ones in places.

**Decisions / interpretations the plan didn't specify** (first three bullets approved 2026-09-28):
- **Skipped ≠ failed.** When `modality.json` is absent, `G10-G13` return `passed=None, blocked_by="G6"`
  instead of failing. Plan §5.3 says they "therefore fail"; counting them would triple-count one root
  cause in the top-5 failure table. Verdict is identical either way. Same for `G5`←`G4`, `G14`←`G2/G7/G8`.
- **`G10`/`G13` failing with `G6` passing → `INCONSISTENT_MODALITY`.** The §5.3 table only lists
  `G11`/`G12` there. But G10/G13 are *loud* (assert/KeyError), while the verdict's description says
  "fails silently". Left mapped to INCONSISTENT_MODALITY for now; may deserve its own verdict.
- **`UNCLASSIFIED_STRUCTURE`**: `G2/G3/G7/G8/G9` fail on a *non-v3* layout. Not in the plan's taxonomy.
- **v3 detection** for the DOWNCONVERT step: `codebase_version` starts `v3`, OR `file_index`/`chunk_index`
  in path patterns, OR `meta/tasks.parquet` / `meta/episodes/`. (Plan §7: don't trust the version string alone.)
- **`G13`** implemented as: each `annotation` entry's `original_key` (default `annotation.<sub>`) must be a
  column in `features`. The loader's real assert (`subkey in modality_meta["annotation"]`) depends on the
  recipe, so this is the dataset-side necessary condition only.
- **`G5`** iterates every `float*` feature in `features` (incl. `timestamp`); I have not confirmed GR00T's
  `lowdim_features` list is identical. WARN-level, so no verdict impact.
- **`G12`** also flags uncovered dims (`groups must cover [0,dim)` per plan); overlap is not checked. A
  non-1-D column skips slicing, matching L335-338. `G14` video keys: `modality.json:video` `original_key or key`
  (repair.py `_original_keys`), else `features` with `dtype=="video"`; masks not checked.
- Output carries `steps` (e.g. `["SEMANTICS","REPAIR"]`) so stacked verdicts (`NEEDS_REPAIR` on top of
  another) aren't lost; `verdict` is the primary one, `NEEDS_REPAIR` only when it is the sole step.

---

## 2026-09-28 — Phase 0: contract pinned and verified

### Pin

| | |
|---|---|
| Isaac-GR00T commit | `51d4c89f72fda44cbf77285c6a8114b52676b8a1` (main on 2026-09-28; committed 2026-08-20, "Add support for Jetpack 7.2 on Orin and Thor") |
| Vendored copies | `vendor/groot_51d4c89/` — every citation below is to these files |
| Audit date | 2026-09-28 |

Files read in full or in the cited ranges: `gr00t/data/dataset/lerobot_episode_loader.py`,
`gr00t/data/stats.py`, `gr00t/data/dataset/factory.py`,
`scripts/repair_lerobot_metadata.py`, `scripts/lerobot_conversion/convert_v3_to_v2.py`.

### Line-number verification against the pin

Loader = `lerobot_episode_loader.py`. The plan (v2) was drafted from the same file
content — confirmed byte-identical — so every discrepancy below is a transcription error,
not upstream drift.

| check | plan v2 cited | actual @51d4c89 | status |
|---|---|---|---|
| G1 info.json | L158-160 | L158-160 | ✅ |
| G2 episodes.jsonl + `length` | L163-165, L203-213 | L163-165, L204-213 | ✅ (L203 is blank) |
| G3 tasks.jsonl | L168-171 | L168-171 | ✅ |
| G4 stats.json assert | L179-181 | L179-182 | ✅ — **but see correction 1** |
| G5 six stat types | stats.py:224 | stats.py:224 | ✅ line — **wrong characterisation, see correction 1** |
| G6 modality.json | L174-176 | L174-176 | ✅ |
| G7 `data_path` | L197, L362-366 | **L198**, L362-366 | ❌ off by one (L197 is `features`) |
| G8 `chunks_size` | L200 | **L201** | ❌ off by one (L200 is `mask_path`) |
| G9 `video_path` | L198, L434-438 | **L199**, L434-438 | ❌ off by one |
| G10 video `original_key` | L426-431 | L426-431 | ✅ |
| G11 allowed modalities | L59, L243-251 | lines exist | ❌ **wrong mechanism, see correction 2** |
| G12 start/end slicing | L331-336, L523-530 | L331-336, L523-530 | ✅ — **refined, see correction 3** |
| G13 annotation subkeys | L373-378 | L373-378 | ✅ |
| optional: fps / video_path / mask_path | "L198-201" | L199, L200, L202 | ❌ fixed |
| optional: relative_stats.json | L186-189 | L186-189 | ✅ |

Three off-by-one errors, all in the L196-202 block: I miscounted once while reading an
excerpt and it propagated. Lesson for `contract.py`: generate the citations from the
vendored file (grep for the anchor string, record the line) instead of typing them.

### Substantive corrections — these change conclusions, not just line numbers

**Correction 1 — stats are auto-regenerated in the training path. `G4`/`G5` are not
blockers for fine-tuning.** `factory.py:57-60` calls `generate_stats(dataset_path)` and
`generate_rel_stats(...)` **unconditionally**, on rank 0, before constructing each
dataset. `generate_stats` (stats.py:251-291) reads `data/*/*.parquet` (stats.py:51),
recomputes any feature whose stats are missing, lack any of the six stat types, or lack a
matching `__fingerprints__` entry (`_stale_features`, stats.py:201-229), and writes
`meta/stats.json`.

Consequences:
- stats.py:224 is not a loader rejection. It is a cache-freshness test inside
  `_stale_features`. Its effect is "recompute", not "fail".
- **No public LeRobot dataset will ever pass that freshness test**, because
  `__fingerprints__` (stats.py:62) is a GR00T-private sidecar key. So every dataset gets
  its stats recomputed on first training run, regardless of what it ships. The shipped
  `stats.json` is effectively ignored for training.
- `G4` (the `assert` at L179-182) still fires for **direct** users of
  `LeRobotEpisodeLoader` that bypass the factory: `gr00t/eval/open_loop_eval.py`,
  `gr00t/policy/replay_policy.py`, and four scripts under `scripts/deployment/`. In
  practice these run after training, when stats.json has already been written.
- **Decision:** `G4`, `G5` downgraded `FAIL` → `WARN`, with a remediation field
  `auto: factory.py:57-60`. The `NEEDS_RECOMPUTE` verdict step is removed from the
  distance-to-ready taxonomy. Stats conformance is still reported as its own column —
  it's a real format divergence, just not a blocker.
- **This invalidates the headline of pilot finding 1** ("the two hard requirements are
  anti-correlated"). The static fact is still true — v2.x has structure without
  quantile stats, v3.0 has quantile stats without structure — but only one of the two is
  actually a requirement. See the correction appended to `pilot/PILOT.md`.

**Correction 2 — `G11` was sourced from the wrong side of the interface.**
`ALLOWED_MODALITIES` (L59) and the filter at L243-251 apply to `modality_configs` — the
**model/embodiment-side** config passed in by the training recipe — not to the dataset's
`modality.json`. Extra sections in `modality.json` are harmless.

What the dataset side actually does is worse: `_extract_joint_groups` (L325-342) looks up
each joint group the embodiment config requests in `modality_meta[state|action]` with
`.get(..., {})`. A missing section or group hits L339-342: a `print()` warning (not even
`logging`) and the group is **silently dropped**. Training continues with fewer
dimensions than the recipe declared.

- **Decision:** `G11` rewritten as "`modality.json` has non-empty `state` and `action`
  sections". This is a *necessary* condition only; the *sufficient* condition ("contains
  every group the embodiment config requests") depends on the recipe, which a
  dataset-only linter doesn't have. Record the gap in `CONTRACT.md`.
- `video` behaves differently: L426 indexes `modality_meta["video"][meta_key]` directly,
  so a missing video section is a loud `KeyError`, not a silent drop.
- **This is the second silent-failure path in the contract** (the first is `G12`). Both
  live in `modality.json`, the one file only a human can write.

**Correction 3 — `G12` must compare against the group's own column, not always
`observation.state`.** L333: each state/action group may set `original_key`, defaulting
to `DEFAULT_COLUMN_NAMES` (L60-63: `state→observation.state`, `action→action`). So the
check is: for each group, `end ≤ shape[0]` of `features[original_key]`, and the union of
groups per column covers `[0, dim)`. Separately, L335-338: if the column isn't an
ndarray (scalar/string), slicing is skipped entirely.

**Addition — `G14`, episode files referenced but absent.** Discovered via a script the
plan didn't know about: `scripts/repair_lerobot_metadata.py`. Its docstring: some HF
snapshots "contain episode metadata for files that are not present in the remote repo".
NVIDIA's definition of required files per episode (L120-163): the `data_path` parquet,
plus one `video_path` mp4 per video `original_key` in `modality.json` (and masks). The
repair drops those episodes and regenerates stats — automatable but **lossy**.
- Checkable from the HF file listing, no payload download. When `modality.json` is
  absent, use `features` with `dtype == "video"` as the video keys (this matches the
  L427 default `observation.images.{key}` for v2.x naming).
- **Pilot: 0/18 v2.x datasets fire it** (`pilot/probe_g14.py`,
  `pilot/pilot_g14_2026-09-28.json`). The script exists, so NVIDIA hit this somewhere.
  Hypothesis: large curated republications (DROID-scale), not the hobbyist tail. S-curated
  will test it.
- Same probe: `episodes.jsonl` line count == `info.total_episodes` in 18/18. Confirms
  dropping v1's `C1` cost nothing on the tail.

### Facts about the remediation tools (for the fix-cost column)

| tool | what it does | cost | source |
|---|---|---|---|
| `generate_stats` | recompute stats + fingerprints | automatic at train time | factory.py:57-60 |
| `convert_v3_to_v2.py` | rewrite v3.0 → v2.x layout | **full `snapshot_download`** (L40) + per-episode ffmpeg cut; copies v3 stats.json across (L471-476); **does not create `modality.json`** | vendor/…convert_v3_to_v2.py |
| `repair_lerobot_metadata.py` | drop episodes whose files are missing | needs local copy; **drops data** | vendor/…repair_lerobot_metadata.py |
| — | write `modality.json` | **no tool exists. Human.** | — |

That last row is the project's thesis, now confirmed from the source rather than argued.

### Decisions log

| date | decision | why |
|---|---|---|
| 2026-09-28 | `G4`, `G5` FAIL → WARN; drop `NEEDS_RECOMPUTE` | auto-remediated at factory.py:57-60 |
| 2026-09-28 | `G11` rewritten to necessary-condition check | real mechanism is L325-342; sufficiency needs the recipe |
| 2026-09-28 | `G12` compares per-group `original_key` column | L333, L60-63 |
| 2026-09-28 | add `G14` (+ verdict `NEEDS_REPAIR`) | repair_lerobot_metadata.py exists; fires 0/18 in pilot tail |
| 2026-09-28 | citations generated from vendored file, not hand-typed | 3 off-by-one errors in plan v2 |

### Open questions / hypotheses (unverified — do not cite as findings)

- **Episode-boundary accuracy after downconversion.** `convert_v3_to_v2.py` cuts with
  `ffmpeg -ss … -c copy` (L336-353): stream copy, no re-encode, so cuts snap to
  keyframes. The loader asserts `len(video_data[key]) == len(df)` (L608). If source GOP
  > 1, a downconverted episode could fail that assert or be off by frames. Needs a real
  download to test — out of scope; note for the writeup as a question, not a claim.
- Does S-curated fire `G14`? (see above)
- Pilot `G14` probe relied on 2 MB cap: `episodes.jsonl` for very large datasets may
  exceed it. `inspect_hub.py` must mark `G14` as `SKIPPED(size)` in that case, never
  pass.

---

## 2026-09-28 — Pilot recon (folded in from `pilot/PILOT.md`)

**Method.** Population: HF datasets tagged `LeRobot`, enumerated via
`/api/datasets?filter=LeRobot&limit=1000` + cursor paging — >60,000 (paging didn't
terminate at 60 pages). Sample: `random.sample(ids, 40)`, `random.seed(7)`, over the first
60,000 ids collected. **Unstratified — a smoke test, not a result.** 2-3 metadata requests
per dataset, zero payload download, ~2 min, $0. Scripts and raw output in `pilot/`.

**Numbers.**

| codebase_version | n | episodes.jsonl + tasks.jsonl | stats.json | stats.json with q01/q99 | modality.json |
|---|---|---|---|---|---|
| v3.0 | 22 | 0 | 20 | 17 | 0 |
| v2.1 | 15 | 15 | 1 | 0 | 0 |
| v2.0 | 3 | 3 | 3 | 0 | 0 |

**Re-read in light of Phase 0** — distance-to-ready, training path:
- v2.0 + v2.1 = **18/40 (45%) → `NEEDS_SEMANTICS`**: one step, `modality.json`, human.
  (Stats: auto. `G14`: 0/18.)
- v3.0 = **22/40 (55%) → `NEEDS_DOWNCONVERT` + `NEEDS_SEMANTICS`**: full download +
  converter, then the same human step.
- `READY`: 0/40. `NOT_LEROBOT`: 0/40.

**Findings that survive Phase 0.**
1. `modality.json` 0/40, and it's the only requirement with no tool. *(Strengthened.)*
2. Same `codebase_version`, different stats schema: 17/20 v3.0 `stats.json` carry
   quantiles, 3 don't. A version string that doesn't pin the schema. *(Still true; now a
   format-governance observation rather than a blocker, since GR00T recomputes anyway.)*
3. v3.0 is the majority of the tail (55%) and GR00T reads only v2.x, with an official
   downgrade script. *(Unchanged.)*

**Finding that did not survive:** "the two hard requirements are anti-correlated" — only
one of them is a hard requirement. See Correction 1.
