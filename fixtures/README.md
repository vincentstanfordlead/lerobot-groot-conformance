# Test fixtures

Control datasets for `tests/test_controls.py`. Only `meta/` files are real copies. Files under
`data/` and `videos/` are zero-byte placeholders (or, for `cube_to_bowl_5`, git-LFS pointer
files) that keep the real filenames. The linter reads only names and metadata.

| folder | source | license |
|---|---|---|
| `cube_to_bowl_5/` | [NVIDIA/Isaac-GR00T `demo_data/cube_to_bowl_5`](https://github.com/NVIDIA/Isaac-GR00T/tree/51d4c89f72fda44cbf77285c6a8114b52676b8a1/demo_data/cube_to_bowl_5) @ `51d4c89` | Apache-2.0 ([LICENSE](../vendor/groot_51d4c89/LICENSE)) |
| `tictac-bot/` | Hugging Face [`youliangtan/tictac-bot`](https://huggingface.co/datasets/youliangtan/tictac-bot) (LeRobot v2.1) | Apache-2.0 (dataset card) |
| `so101_pick_red_cube_3cams/` | Hugging Face [`whosricky/so101_pick_red_cube_3cams`](https://huggingface.co/datasets/whosricky/so101_pick_red_cube_3cams) (LeRobot v3.0) | Apache-2.0 (dataset card) |

These are used as known-good controls (one positive, one v2.1, one v3.0) and as the base for
deliberately corrupted copies. They are not examples of defects.
