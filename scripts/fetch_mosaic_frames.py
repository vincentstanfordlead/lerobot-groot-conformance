"""Fetch one video frame per dataset for the README mosaic (network; needs `pip install av`).

    .venv/bin/python scripts/fetch_mosaic_frames.py

Each frame is decoded from episode 0 of the first listed camera at the dataset's *audited* commit
(repo_sha in results/summary.csv), so the picture matches the verdict it is shown with. Only the
start of each video is streamed. Output: docs/img/mosaic_frames/NN.jpg (cropped to the tile size)
and sources.json (dataset, commit, camera, license). The badges are not stored here:
scripts/make_figures.py reads them from results/summary.csv.

The selection is hand-picked for visual variety from datasets with video. Its colour mix is
illustrative, not a sample (the README says so under the image).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import av
import pandas as pd
from huggingface_hub import HfApi
from PIL import ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img" / "mosaic_frames"
TILE = (480, 360)  # 2x the displayed tile
FRAME = 45  # skip the first 1.5 s: early frames are often blank or mid-exposure

DATASETS = [
    # one file away (NEEDS_MODALITY / READY)
    "7smile/omx_f_task_0916", "Kazu1232/record-so101-test", "RoboCOIN/AI2_Alphabot_2_package_fruit",
    "ilBiondo06/eval_act_so100_movelladot_c5", "jiroh2000/so100_test_007", "ygtxr1997/bc_z_lerobot",
    "IPEC-COMMUNITY/viola_lerobot",
    # needs conversion (NEEDS_DOWNCONVERT)
    "addisonhammer/so101_pink_die_in_cup_20260817_220140_20260819_090202", "brandonyang/artem-pour-water",
    "hukewei/lerobot_peg_in_optical", "humjie/bimanual-so101-fold-towel-v6", "krish5831/tissues_into_box_20260928_194959",
    "lerobotForScienceEdu/eval_Rock_Acid-v4-gt-hand", "lerobot/robomme", "max-chr/libero_plus_10_texture_all_iiwa",
    "qownscks/pot100", "rbtrprjkt/rollout_pi05_han10e_20260928_075758", "shp314/gr00t_so101",
    "ssabats/object-orange-lego-placing-coffe-box_20260928_162843", "wuc1/bi_so101_ffp_show_20260702_022156",
    "jio2/clean_desk_v1_pi", "LTH4663/fod_c3_strategy_desc_v2_216_2cam_20260928",
    "leapshared/Electroscope_new_20260928_202529",
    # not robot manipulation (embodiment_fit == outside)
    "Lyrasilas/eval_ep500_seed1_default_center_guessed_20000_default",
]


def camera(info: dict) -> str:
    keys = [k for k, v in info["features"].items() if v.get("dtype") == "video"]
    return sorted(keys, key=lambda k: ("wrist" in k or "hand" in k))[0]  # prefer a scene camera


def main() -> int:
    df = pd.read_csv(ROOT / "results" / "summary.csv").set_index("dataset")
    api = HfApi()
    OUT.mkdir(parents=True, exist_ok=True)
    sources = []
    for i, ds in enumerate(DATASETS):
        sha = df.loc[ds, "repo_sha"]
        info = json.loads((ROOT / "results" / "info_cache" / f"{ds}.json").read_text())
        key = camera(info)
        rel = info["video_path"].format(video_key=key, episode_chunk=0, episode_index=0, chunk_index=0, file_index=0)
        with av.open(f"https://huggingface.co/datasets/{ds}/resolve/{sha}/{rel}", options={"timeout": "15000000"}) as c:
            for n, frame in enumerate(c.decode(video=0)):
                if n == FRAME:
                    break
            img = frame.to_image().convert("RGB")
        ImageOps.fit(img, TILE, method=3).save(OUT / f"{i:02d}.jpg", quality=82, optimize=True)
        card = api.dataset_info(ds, revision=sha).card_data
        lic = (card or {}).get("license") if card else None
        sources.append({"tile": f"{i:02d}.jpg", "dataset": ds, "repo_sha": sha, "camera": key,
                        "episode": 0, "frame": FRAME, "license": lic or "not stated"})
        print(f"{i:02d} {ds}  [{lic or 'not stated'}]")
    (OUT / "sources.json").write_text(json.dumps(sources, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
