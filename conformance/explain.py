"""Plain-language copy for every check and verdict. Python mirror of docs/app/explain.js.

Tone: neutral and constructive; never "broken". `fix` is shown only when a check does not pass.
"""
from __future__ import annotations

CONVERT = ("Convert with NVIDIA's script (it reads the full dataset, then rewrites it as v2):\n"
           "  cd Isaac-GR00T/scripts/lerobot_conversion && python convert_v3_to_v2.py --repo-id <user>/<dataset>")

CHECKS = {
    "L1": ("Has meta/info.json", "If the datasets sit in subfolders, check each subfolder; GR00T is pointed at one dataset directory at a time."),
    "L2": ("Declares a LeRobot version", "Informational only."),
    "L3": ("Contains recorded episodes", "Upload or copy the data/ folder. If this was an evaluation run or an aborted recording, it may not be meant as a dataset."),
    "L4": ("Has camera videos", "Informational only."),
    "L5": ("Has episode metadata", "Re-export the dataset with the LeRobot tools so the metadata is regenerated."),
    "L6": ("Has task metadata", "Re-export the dataset with the LeRobot tools so the metadata is regenerated."),
    "L7": ("Ships some statistics file", "Nothing required."),
    "L8": ("Describes its features", "Re-export the dataset with the LeRobot tools."),
    "L9": ("Names every state/action dimension", "Record with descriptive per-dimension names (body part, side, quantity, e.g. shoulder_pan.pos, gripper.pos). Clear names are what let anyone, or this tool, write modality.json."),
    "L10": ("Every camera has a videos/ folder", "Copy or upload the missing camera folders."),
    "L11": ("Episode count adds up", "Regenerate info.json, or add the missing episodes."),
    "L12": ("Declares the true frame rate", 'Add "fps": <your recording rate> to meta/info.json. GR00T silently assumes 30 Hz if it is missing.'),
    "G1": ("info.json parses", "Fix the JSON syntax in meta/info.json."),
    "G2": ("Has meta/episodes.jsonl with lengths", CONVERT),
    "G3": ("Has meta/tasks.jsonl", CONVERT),
    "G4": ("Ships meta/stats.json", "Nothing required for training: GR00T computes it. Evaluation and replay scripts read it directly."),
    "G5": ("Stats include all six types", "Nothing required: GR00T recomputes them."),
    "G6": ("Has meta/modality.json", "Add meta/modality.json, the one file GR00T needs that standard LeRobot doesn't define: which slice of the state/action numbers is the arm, the gripper, and so on."),
    "G7": ("data_path uses the v2 template", CONVERT),
    "G8": ("Declares chunks_size", 'Add "chunks_size" to meta/info.json (LeRobot\'s default is 1000).'),
    "G9": ("video_path uses the v2 template", CONVERT),
    "G10": ("Camera entries point at real features", 'Set "original_key": "observation.images.<camera>" on every video entry in modality.json.'),
    "G11": ("modality.json has state and action groups", 'Add non-empty "state" and "action" sections to modality.json. Missing groups are silently dropped in eval and replay.'),
    "G12": ("Every slice fits and every dimension is covered", "Make sure 0 <= start < end <= dimension for every group and that the groups cover every dimension. Out-of-range slices are silently cut short."),
    "G13": ("Language annotations point at real columns", "Point each annotation's original_key at an existing column (e.g. task_index)."),
    "G14": ("Every listed episode's files exist", "Add the missing files, or run Isaac-GR00T's scripts/repair_lerobot_metadata.py (it drops those episodes)."),
    "G15": ("Every feature declares a dtype", 'Add "dtype" to every entry in info.json:features.'),
    "G16": ("State and action are floats", "Store observation.state and action as float32."),
}

# Mirrors docs/app/explain.js GROUPS: how the report and the web app group GR00T's 28 checks.
GROUPS = [
    ("Dataset basics", ["L1", "L2", "L3", "L4", "L8", "L9", "L12"]),
    ("File layout GR00T reads", ["G1", "G2", "G3", "G7", "G8", "G9", "G14"]),
    ("GR00T's extra file: modality.json", ["G6", "G11", "G12", "G10", "G13"]),
    ("Data types & statistics", ["G15", "G16", "G4", "G5", "L7"]),
    ("Consistency", ["L5", "L6", "L10", "L11"]),
]

# Traffic-light tone per GR00T verdict, as the web app shows it (good / close / bad).
TONES = {"READY": "good", "NEEDS_MODALITY": "close", "INCONSISTENT_MODALITY": "close", "NEEDS_REPAIR": "close",
         "NEEDS_DOWNCONVERT": "bad", "BLOCKED": "bad", "NOT_LEROBOT": "bad"}

# Mirrors docs/app/explain.js PI05_CHECKS.
PI05_CHECKS = {
    "P1": "Actions are one float vector",
    "P2": "Action dimension ≤ 32",
    "P3": "State is one float vector, ≤ 32",
    "P4": "1–3 RGB cameras for 3 image slots",
    "P5": "Camera size vs 224×224",
    "P6": "Frame rate vs the 50-step action chunk",
    "P7": "Episodes at least one chunk long",
    "P8": "Task text for the prompt",
}

VERDICTS = {
    "READY": ("READY", "Passes every static check",
              "All 28 metadata checks pass. That is not a guarantee it trains well, but nothing in the files stands in the way."),
    "NEEDS_MODALITY": ("ONE STEP AWAY", "One file away",
                       "Everything GR00T reads is in place except meta/modality.json, the file that says which numbers are the arm and which the gripper."),
    "NEEDS_DOWNCONVERT": ("TWO STEPS AWAY", "Needs a format conversion, then modality.json",
                          "This dataset uses the newer LeRobot v3.0 layout. GR00T reads v2 today and ships a converter; NVIDIA's docs say native v3 support is planned."),
    "INCONSISTENT_MODALITY": ("FIX MODALITY.JSON", "modality.json disagrees with the data",
                              "Some of these mistakes don't raise an error at training time, so fix them first."),
    "NEEDS_REPAIR": ("REPAIR", "Some episode files are missing", "The metadata lists episodes whose files aren't present."),
    "BLOCKED": ("BLOCKED", "Something no converter can fix",
                "Most often: metadata but no recorded episodes, or a structural problem in a v2 layout."),
    "NOT_LEROBOT": ("NOT LEROBOT", "Not a LeRobot dataset at this level",
                    "There is no meta/info.json here. Point the check at one dataset directory; other formats (RLDS, HDF5, rosbag) need converting to LeRobot first."),
}
