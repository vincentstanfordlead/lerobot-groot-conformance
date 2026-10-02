# Vendored Isaac-GR00T source — pinned

- Repo: https://github.com/NVIDIA/Isaac-GR00T
- Commit: `51d4c89f72fda44cbf77285c6a8114b52676b8a1` (main as of 2026-09-28; committed 2026-08-20)
- Fetched: 2026-09-28

Every `source` citation in `conformance/contract.py` and `CONTRACT.md` refers to line
numbers in these files. Filenames are the repo path with `/` replaced by `_`.

Do not edit. To re-pin: fetch the new commit into a new `groot_<sha7>/` directory, diff
the contract-relevant lines, and record what moved in `NOTES.md`.

Added 2026-09-29 (Phase 5, same commit, fetched from raw.githubusercontent.com at the pinned
SHA): `gr00t_data_dataset_sharded_single_step_dataset.py`,
`gr00t_data_dataset_sharded_mixture_dataset.py`, `gr00t_eval_open_loop_eval.py`,
`gr00t_policy_replay_policy.py` — the entrypoints CONTRACT.md §1 cites.

Added 2026-10-01 (same commit; `main` was still `51d4c89` on that date):
`getting_started_data_preparation.md`, `getting_started_finetune_new_embodiment.md`, and
`upstream_README.md` (the repo's top-level `README.md`, renamed to avoid clashing with this
file). CHECKLIST.md tier 1 cites them.

License: Isaac-GR00T is Apache License 2.0; a copy is in [`LICENSE`](LICENSE). The files here
are unmodified copies, kept so that every citation in this project can be checked offline.
