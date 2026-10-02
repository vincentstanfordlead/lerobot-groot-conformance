// Draft a meta/modality.json from info.json:features.*.names.
// The classifier is a port of conformance/report.py (classify_name / feature_tier), the heuristic
// behind the audit's "names clean enough to draft one" figure. A draft is a PROPOSAL: a wrong
// gripper index trains silently on the wrong joints, so the UI always asks a human to confirm.

const GRIPPER = new Set(["gripper", "grip", "claw", "finger", "fingers", "grasp", "carriage"]);
const HAND = new Set(["hand", "thumb", "index", "middle", "ring", "pinky", "palm"]);
const BODY = new Set(["head", "neck", "torso", "leg", "hip", "knee", "ankle"]);
const JOINT = new Set(["joint", "joints", "shoulder", "elbow", "wrist", "waist", "forearm", "arm", "upperarm", "flex"]);
const BASE = new Set(["base", "wheel", "wheels", "vel", "velocity", "odom", "chassis"]);
const ROT = new Set(["roll", "pitch", "yaw", "rx", "ry", "rz", "rw", "quat", "qx", "qy", "qz", "qw", "rot", "rotation", "axis", "euler"]);
const POS = new Set(["x", "y", "z", "pos", "position", "xyz"]);
const NUMBERED_JOINT = /^(?:joint|j|motor|q|dof|servo)[_.\- ]?\d+$/;
const GENERIC = /^(?:[a-z]{0,6}[_.\- ]?)?\d+$|^(?:dim|state|action|obs|axis)[_.\- ]?\d+$/;
const SIDE = /^(?:left|right|l|r|main|aux|(?:arm|robot|agent|umi)\d+)$/;

export function classifyName(name, numberedJointOk = false) {
  const n = String(name).toLowerCase().trim();
  if (!n) return null;
  if (NUMBERED_JOINT.test(n)) return numberedJointOk ? ["", "joint"] : null;
  if (GENERIC.test(n)) return null;
  const raw = n.split(/[^a-z0-9]+/).filter(Boolean);
  const sideTok = raw.find((t) => SIDE.test(t));
  const side = sideTok === undefined ? "" : ["left", "right", "l", "r"].includes(sideTok) ? sideTok[0].toUpperCase() : sideTok;
  const toks = raw.map((t) => t.replace(/(?<=[a-z])\d+$/, ""));
  const has = (vocab) => toks.some((t) => vocab.has(t));
  if (has(GRIPPER)) return [side, "gripper"];
  if (has(HAND)) return [side, "hand"];
  const body = toks.find((t) => BODY.has(t));
  if (body) return ["", "body:" + body];
  for (const [cls, vocab] of [["joint", JOINT], ["base", BASE], ["eef_rot", ROT], ["eef_pos", POS]]) if (has(vocab)) return [side, cls];
  return null;
}

function flatNames(feat) {
  let nm = feat.names;
  if (nm && typeof nm === "object" && !Array.isArray(nm)) {
    const vals = Object.values(nm).filter(Array.isArray);
    nm = vals.length === 1 ? vals[0] : vals.length ? vals.flat() : null;
  }
  return Array.isArray(nm) && nm.every((x) => typeof x === "string") ? nm : null;
}

// -> { tier, runs: [[ [side, cls], start, end ]], names, bad }
export function featureTier(feats, key) {
  const f = feats[key];
  if (!f || typeof f !== "object") return { tier: "no_state_or_action_feature" };
  if (!f.names || (Array.isArray(f.names) && !f.names.length)) return { tier: "no_names" };
  const names = flatNames(f);
  const shape = f.shape;
  if (!names || !Array.isArray(shape) || shape.length !== 1 || names.length !== shape[0]) return { tier: "names_unusable" };
  const namedGripper = names.some((n) => (classifyName(n) || [])[1] === "gripper");
  const cls = names.map((n) => classifyName(n, namedGripper));
  const bad = names.filter((n, i) => cls[i] === null);
  if (bad.length) return { tier: "opaque_names", bad: bad.slice(0, 6), names };
  const runs = [];
  let start = 0;
  const same = (a, b) => a[0] === b[0] && a[1] === b[1];
  for (let i = 1; i <= cls.length; i++) {
    if (i === cls.length || !same(cls[i], cls[start])) {
      runs.push([cls[start], start, i]);
      start = i;
    }
  }
  const labels = runs.map(([c]) => c.join("|"));
  if (new Set(labels).size < labels.length) return { tier: "fragmented_groups", runs, names };
  return { tier: "looks_inferable", runs, names };
}

const SIDE_PREFIX = (side) => (side === "L" ? "left_" : side === "R" ? "right_" : side ? `${side}_` : "");

function groupName([side, cls]) {
  if (cls === "joint") return side ? `${SIDE_PREFIX(side)}arm` : "single_arm";
  if (cls === "eef_pos") return `${SIDE_PREFIX(side)}eef_position`;
  if (cls === "eef_rot") return `${SIDE_PREFIX(side)}eef_rotation`;
  if (cls.startsWith("body:")) return cls.slice(5);
  return `${SIDE_PREFIX(side)}${cls}`;
}

const TIER_HELP = {
  no_state_or_action_feature: "info.json declares no observation.state / action feature, so there is nothing to split.",
  no_names: "The state/action dimensions have no names. Only someone who knows the robot can say which is which.",
  names_unusable: "The names don't line up one-to-one with the dimensions, so they can't be used to split them.",
  opaque_names: "Some dimension names are generic (e.g. motor_0, joint_3, 0), so which one is the gripper can't be inferred.",
  fragmented_groups: "A body part's dimensions are not contiguous, but GR00T groups must be one start:end range.",
};

// -> { ok, draft?, groups?, notes[], reason? }
export function draftModality(info) {
  const feats = info && typeof info.features === "object" && info.features ? info.features : {};
  const notes = [];
  const parts = {};
  for (const key of ["observation.state", "action"]) parts[key] = featureTier(feats, key);
  const st = parts["observation.state"], ac = parts["action"];
  // Common case: action has no usable names but mirrors state (same dim). Reuse state's split, flagged.
  if (st.tier === "looks_inferable" && ac.tier !== "looks_inferable" && ["no_names", "names_unusable"].includes(ac.tier) &&
      feats.action?.shape?.[0] === feats["observation.state"]?.shape?.[0]) {
    parts.action = { ...st, mirrored: true };
    notes.push("action has no usable names; its split copies observation.state (same dimension). Check that the action really is ordered the same way.");
  }
  for (const [key, p] of Object.entries(parts)) {
    if (p.tier !== "looks_inferable") {
      return { ok: false, reason: `${key}: ${TIER_HELP[p.tier] || p.tier}`, bad: p.bad, notes };
    }
  }
  const draft = { state: {}, action: {} };
  const groups = { state: [], action: [] };
  // One robot whose dims all carry the same non-left/right prefix (LeRobot's "main_shoulder_pan"):
  // drop it, so a single arm gets NVIDIA's demo names (single_arm, gripper) rather than main_arm.
  const sides = new Set(["observation.state", "action"].flatMap((k) => parts[k].runs.map(([c]) => c[0])));
  const [only] = sides;
  const dropSide = sides.size === 1 && only && only !== "L" && only !== "R";
  if (dropSide) notes.push(`Every dimension name starts with "${only}"; it was treated as the robot's name, not a side.`);
  for (const [section, key] of [["state", "observation.state"], ["action", "action"]]) {
    for (const [rawCls, s, e] of parts[key].runs) {
      const cls = dropSide ? ["", rawCls[1]] : rawCls;
      const name = groupName(cls);
      draft[section][name] = { start: s, end: e };
      groups[section].push({ name, start: s, end: e, dims: parts[key].names.slice(s, e) });
    }
  }
  const video = Object.entries(feats).filter(([, v]) => v && v.dtype === "video").map(([k]) => k);
  if (video.length) {
    draft.video = {};
    for (const k of video) draft.video[k.replace(/^observation\.images\./, "").replace(/\./g, "_")] = { original_key: k };
  }
  if ("task_index" in feats) {
    draft.annotation = { "human.task_description": { original_key: "task_index" } };
    notes.push("annotation points at task_index, as in NVIDIA's cube_to_bowl_5 demo. The key must match the language key in your training recipe.");
  }
  notes.push("Group names (single_arm, gripper, …) must match the embodiment config you train with. NVIDIA's demo uses single_arm and gripper.");
  return { ok: true, draft, groups, notes };
}

// Readable JSON: one line per group / video / annotation entry.
const inline = (v) => (v && typeof v === "object" && !Array.isArray(v)
  ? "{" + Object.entries(v).map(([a, b]) => `${JSON.stringify(a)}: ${JSON.stringify(b)}`).join(", ") + "}" : JSON.stringify(v));

export function formatModality(m) {
  const sec = (obj) => "{\n" + Object.entries(obj).map(([k, v]) => `    ${JSON.stringify(k)}: ${inline(v)}`).join(",\n") + "\n  }";
  return "{\n" + Object.entries(m).map(([k, v]) => `  ${JSON.stringify(k)}: ${sec(v)}`).join(",\n") + "\n}\n";
}
