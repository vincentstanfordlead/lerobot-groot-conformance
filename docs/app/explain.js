// Plain-language copy for every check and verdict. Tone: neutral, constructive; never "broken".

export const GROUPS = [
  { id: "basics", title: "Dataset basics", ids: ["L1", "L2", "L3", "L4", "L8", "L9", "L12"] },
  { id: "layout", title: "File layout GR00T reads", ids: ["G1", "G2", "G3", "G7", "G8", "G9", "G14"] },
  { id: "modality", title: "GR00T's extra file: modality.json", ids: ["G6", "G11", "G12", "G10", "G13"] },
  { id: "types", title: "Data types & statistics", ids: ["G15", "G16", "G4", "G5", "L7"] },
  { id: "consistency", title: "Consistency", ids: ["L5", "L6", "L10", "L11"] },
];

const CONVERT = "Convert with NVIDIA's script (it downloads the full dataset, then rewrites it as v2):\n" +
  "  cd scripts/lerobot_conversion && python convert_v3_to_v2.py --repo-id <user>/<dataset>";

// title, what it means (why), how to fix (fix). `fix` is shown only when the check doesn't pass.
export const CHECKS = {
  L1: { title: "Has meta/info.json", why: "Every LeRobot dataset describes itself in meta/info.json. Without it, the repo isn't a LeRobot dataset at its root.", fix: "If the datasets sit in subfolders, check each subfolder; GR00T is pointed at one dataset directory at a time." },
  L2: { title: "Declares a LeRobot version", why: "codebase_version says which LeRobot layout the files follow. GR00T itself never reads it; this checker detects the layout from the files.", fix: "Informational only." },
  L3: { title: "Contains recorded episodes", why: "Episode data (robot state, actions, timestamps) lives in parquet files under data/. A repo without them has metadata but no recordings.", fix: "Upload the data/ folder. If this was an evaluation run or an aborted recording, it may not be meant as a dataset." },
  L4: { title: "Has camera videos", why: "Camera streams live under videos/. A state-only dataset is valid; GR00T's vision-language-action recipes usually expect at least one camera.", fix: "Informational only." },
  L5: { title: "Has episode metadata", why: "A list of episodes and their lengths (episodes.jsonl in v2, episodes/*.parquet in v3).", fix: "Re-export the dataset with the LeRobot tools so the metadata is regenerated." },
  L6: { title: "Has task metadata", why: "The language instruction for each task (tasks.jsonl in v2, tasks.parquet in v3).", fix: "Re-export the dataset with the LeRobot tools so the metadata is regenerated." },
  L7: { title: "Ships some statistics file", why: "Normalisation statistics. GR00T recomputes its own at training time, so this is informational.", fix: "Nothing required." },
  L8: { title: "Describes its features", why: "info.json:features lists every column: the state and action vectors, cameras, and their shapes.", fix: "Re-export the dataset with the LeRobot tools." },
  L9: { title: "Names every state/action dimension", why: "GR00T doesn't read names, but clear names (shoulder_pan.pos, gripper.pos) are what let anyone write modality.json later, and what lets this page draft one.", fix: "Record with descriptive per-dimension names: body part, side, and quantity." },
  L10: { title: "Every camera has a videos/ folder", why: "Each camera declared in features should have its own folder of videos.", fix: "Re-upload the missing camera folders." },
  L11: { title: "Episode count adds up", why: "The number of lines in episodes.jsonl should equal info.json:total_episodes. GR00T reads the list, so this is a consistency warning.", fix: "Regenerate info.json, or upload the missing episodes." },
  L12: { title: "Declares the true frame rate", why: "GR00T reads info.json:fps and silently assumes 30 Hz if it's missing. In the audit, nearly half of public datasets are not 30 Hz.", fix: "Add \"fps\": <your recording rate> to meta/info.json." },
  G1: { title: "info.json parses", why: "GR00T's loader opens meta/info.json first.", fix: "Fix the JSON syntax in meta/info.json." },
  G2: { title: "Has meta/episodes.jsonl with lengths", why: "GR00T reads the v2 file meta/episodes.jsonl (one episode per line, each with a length). LeRobot v3 stores this as parquet instead, so a v3 dataset fails here.", fix: CONVERT },
  G3: { title: "Has meta/tasks.jsonl", why: "GR00T reads task descriptions from the v2 file meta/tasks.jsonl.", fix: CONVERT },
  G4: { title: "Ships meta/stats.json", why: "GR00T regenerates stats.json before every training run, so this is only a warning. Evaluation/replay scripts read it directly.", fix: "Nothing required for training. GR00T computes it." },
  G5: { title: "Stats include all six types", why: "GR00T uses mean, std, min, max, q01 and q99, and recomputes any that are missing.", fix: "Nothing required. GR00T recomputes them." },
  G6: { title: "Has meta/modality.json", why: "The one file GR00T needs that standard LeRobot doesn't define. It says which slice of the state/action numbers is the arm, the gripper, and so on. Its absence is a gap between the two formats, not a defect in the data.", fix: "Add meta/modality.json. If the dimension names are clear, use the drafted file below as a starting point and check it against your robot." },
  G7: { title: "data_path uses the v2 template", why: "GR00T builds each episode's file path from info.json:data_path using {episode_chunk} and {episode_index}. v3 uses {chunk_index}/{file_index}, which GR00T doesn't supply.", fix: CONVERT },
  G8: { title: "Declares chunks_size", why: "GR00T needs chunks_size to work out which chunk folder holds each episode.", fix: "Add \"chunks_size\" to meta/info.json (LeRobot's default is 1000)." },
  G9: { title: "video_path uses the v2 template", why: "When a dataset has cameras, GR00T builds video paths from info.json:video_path using {episode_chunk}, {video_key} and {episode_index}.", fix: CONVERT },
  G10: { title: "Camera entries point at real features", why: "Each video entry in modality.json must name a camera feature that exists. Set original_key explicitly: GR00T's loader and repair script default it differently.", fix: "Set \"original_key\": \"observation.images.<camera>\" on every video entry." },
  G11: { title: "modality.json has state and action groups", why: "GR00T looks up the body-part groups its training recipe asks for. Missing groups fail at training startup and are silently dropped in eval/replay.", fix: "Add non-empty \"state\" and \"action\" sections." },
  G12: { title: "Every slice fits and every dimension is covered", why: "Groups are Python slices [start:end]. A slice past the end is silently cut short by numpy, and an uncovered dimension is silently ignored. Neither raises an error.", fix: "Make sure 0 ≤ start < end ≤ dimension for every group, and that the groups cover every dimension." },
  G13: { title: "Language annotations point at real columns", why: "Each annotation entry must name a column in the data.", fix: "Point each annotation's original_key at an existing column (e.g. task_index)." },
  G14: { title: "Every listed episode's files exist", why: "For each episode in the metadata, GR00T needs its parquet file and one video per camera. NVIDIA's repair script fixes this by dropping the episode.", fix: "Upload the missing files, or run scripts/repair_lerobot_metadata.py (it removes those episodes)." },
  G15: { title: "Every feature declares a dtype", why: "GR00T's statistics step reads each feature's dtype and stops if one is missing.", fix: "Add \"dtype\" to every entry in info.json:features." },
  G16: { title: "State and action are floats", why: "GR00T computes statistics only for float features; integer state/action has no stats and fails at startup.", fix: "Store observation.state and action as float32." },
};

export const VERDICTS = {
  READY: { headline: "Passes every static check", sub: "All 28 metadata checks pass. That's not a guarantee it trains well, but nothing in the files stands in the way.", tone: "good", mood: "happy" },
  NEEDS_MODALITY: { headline: "One step away", sub: "Everything GR00T reads is in place except meta/modality.json, the file that names which numbers are the arm and which the gripper.", tone: "close", mood: "happy" },
  NEEDS_DOWNCONVERT: { headline: "Two steps away", sub: "This dataset uses the newer LeRobot v3.0 layout. GR00T reads v2 today (NVIDIA plans native v3 support); its converter handles step one, then add modality.json.", tone: "mid", mood: "think" },
  INCONSISTENT_MODALITY: { headline: "modality.json needs a fix", sub: "The dataset ships modality.json, but it disagrees with the data. Some of these mistakes don't raise an error, so they're worth fixing first.", tone: "warn", mood: "think" },
  NEEDS_REPAIR: { headline: "Some episode files are missing", sub: "Metadata lists episodes whose files aren't in the repo.", tone: "warn", mood: "think" },
  BLOCKED: { headline: "Blocked", sub: "Something no converter can fix: most often the repo has metadata but no recorded episodes.", tone: "bad", mood: "oops" },
  NOT_LEROBOT: { headline: "Not a LeRobot dataset at this level", sub: "There's no meta/info.json at the repo root.", tone: "bad", mood: "oops" },
};

export function sourceUrl(src) {
  // "path:L1-2, L3, other/path:L4" -> [{label, url}]
  const base = "https://github.com/NVIDIA/Isaac-GR00T/blob/51d4c89f72fda44cbf77285c6a8114b52676b8a1/";
  const out = [];
  let file = null;
  for (const part of String(src || "").split(/,\s*/)) {
    const m = part.match(/^(?:(.+?):)?L(\d+)(?:-(\d+))?$/);
    if (!m) continue;
    file = m[1] || file;
    const [a, b] = [m[2], m[3]];
    out.push({ label: `${file.split("/").pop()} L${a}${b ? "-" + b : ""}`, url: `${base}${file}#L${a}${b ? "-L" + b : ""}` });
  }
  return out;
}

// LeRobot-native and openpi columns (conformance/models.py, CONTRACT_lerobot_openpi.md).
export const MODEL_VERDICTS = {
  PASS: { label: "Loads", tone: "good", sub: "LeRobot's loader can pull this from the Hub and read its metadata." },
  NEEDS_CONFIG: { label: "Needs a config", tone: "close", sub: "The files load. openpi still needs a data config for this dataset and a normalization-stats run; no dataset loads there as is." },
  NEEDS_TAG: { label: "Needs a version tag", tone: "close", sub: "The files are in the right layout, but the repo has no version tag the loader accepts, so loading by repo id fails." },
  NEEDS_CONVERT: { label: "Needs converting", tone: "mid", sub: "The data is in the other layout from the one this loader reads." },
  BLOCKED: { label: "Blocked", tone: "bad", sub: "No episodes, not a LeRobot dataset, a required metadata file is missing, or no tool exists for this version." },
  UNASSESSED: { label: "Not assessed", tone: "bad", sub: "The Hub's tag list could not be read." },
};

// Steps by column. Commands are the ones each loader prints in its own error message (vendor/ copies).
export const MODEL_STEPS = {
  lerobot: {
    TAG: `<b>Tag the repo with its codebase version</b> (for example <code>v3.0</code>). LeRobot prints the call: <code>HfApi().create_tag(repo_id, tag="v3.0", repo_type="dataset")</code>.`,
    CONVERT: `<b>Convert v2.1 → v3.0</b> with LeRobot's converter: <code>python -m lerobot.scripts.convert_dataset_v21_to_v30 --repo-id=…</code>.`,
    CONVERT_V20_V21: `<b>Upgrade v2.0 → v2.1 first.</b> The current loader names no converter for v2.0; the older LeRobot ships <code>convert_dataset_v20_to_v21.py</code>.`,
  },
  openpi: {
    TAG: `<b>Tag the repo with its codebase version</b> (for example <code>v2.1</code>); openpi's pinned LeRobot looks tags up by version.`,
    CONVERT: `<b>Convert v3.0 → v2.1.</b> openpi's pinned LeRobot reads v2.x only. GR00T's <code>convert_v3_to_v2.py</code> is the one converter we know of; it has not been tried with openpi.`,
    CONFIG: `<b>Write an openpi data config</b> for this dataset: which keys are images, state and actions, and the action-sequence key.`,
    NORM_STATS: `<b>Run <code>scripts/compute_norm_stats.py</code></b> for that config; training stops without the stats.`,
  },
};

// π0.5 model fit (conformance/models.py pi05_fit, CONTRACT_lerobot_openpi.md §7).
export const PI05_VERDICTS = {
  FIT: { label: "Fits π0.5", tone: "good", sub: "The contents match π0.5's defaults: the data config only has to rename keys." },
  ADAPT: { label: "Fits with changes", tone: "close", sub: "π0.5 can train on it, but the config (or one model setting) has to do more than rename keys." },
  NO_FIT: { label: "Doesn't fit π0.5", tone: "bad", sub: "π0.5 as shipped can't train on it without changing the data itself." },
  UNASSESSED: { label: "Not assessed", tone: "bad", sub: "info.json could not be read." },
};
export const PI05_CHECKS = {
  P1: "Actions are one float vector",
  P2: "Action dimension ≤ 32",
  P3: "State is one float vector, ≤ 32",
  P4: "1–3 RGB cameras for 3 image slots",
  P5: "Camera size vs 224×224",
  P6: "Frame rate vs the 50-step action chunk",
  P7: "Episodes at least one chunk long",
  P8: "Task text for the prompt",
};
