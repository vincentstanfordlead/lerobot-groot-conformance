// Port of conformance/embodiment.py: what kind of data is this? Separate from loadability.
// tests/test_js_parity.py checks this against the Python on every audited info.json.

export const CATEGORIES = {
  arm: ["Single robot arm", "fits"],
  bimanual: ["Two-arm (bimanual) robot", "fits"],
  humanoid: ["Humanoid / whole-body robot", "fits"],
  mobile_manipulator: ["Mobile manipulator", "fits"],
  vehicle: ["Vehicle / driving", "outside"],
  human_motion: ["Human motion (no robot)", "outside"],
  unclear: ["Couldn't tell from metadata", "unclear"],
};

const ROBOT_TYPES = [
  ["vehicle", /racecar|\bcar\b|vehicle|\bkia\b|tesla|toyota|\bniro\b|driving|truck|carla/],
  ["human_motion", /smpl|mocap|human/],
  ["humanoid", /humanoid|unitree_?g1|\bg1\b|unitree_?h1|\bh1\b|gr1|fourier|kuavo|optimus|figure|digit|apollo|r1pro|a2d|tiangong|booster|t1\b/],
  ["mobile_manipulator", /robocasa|stretch|lekiwi|mobile|omron|tiago|fetch|alphabot|ranger|xlerobot|aibot/],
  ["bimanual", /^bi_|bimanual|aloha|_bi_|dual|yam_bimanual/],
  ["arm", /so[-_]?10[01]|so_follower|so_simplified|koch|franka|panda|kuka|ur[35e]|xarm|widowx|piper|moss|omx|openarm|google_robot|metaworld|trossen|jaco|kinova|sawyer|fanuc|realman|arx|elephant|mycobot|stringman|yor|ffw|\byam\b|yam_/],
];
const VEHICLE_WORDS = ["steer", "steering", "throttle", "gas_pedal", "brake", "brake_pedal", "gear", "turn_signal", "latitude", "longitude"];
const HUMAN_WORDS = ["smpl", "mocap"];
const pyRepr = (s) => `'${s}'`;

function names(info) {
  const words = new Set();
  const feats = info.features && typeof info.features === "object" && !Array.isArray(info.features) ? info.features : {};
  for (const [k, v] of Object.entries(feats)) {
    const kl = k.toLowerCase();
    words.add(kl);
    for (const t of kl.match(/[a-z0-9]+/g) || []) words.add(t);
    const nm = v && typeof v === "object" ? v.names : undefined;
    const text = nm === undefined || nm === null ? "" : JSON.stringify(nm).toLowerCase();
    for (const t of text.match(/[a-z0-9]+/g) || []) words.add(t);
    for (const t of text.match(/[a-z]+_[a-z_]+/g) || []) words.add(t);
  }
  return words;
}

const out = (cat, evidence) => ({ category: cat, label: CATEGORIES[cat][0], fit: CATEGORIES[cat][1], evidence });

export function classifyEmbodiment(info, repoId = null) {
  if (!info || typeof info !== "object") return out("unclear", "info.json unavailable");
  const rt = String(info.robot_type ?? "").trim();
  const rtl = rt.toLowerCase();
  const words = names(info);
  const veh = VEHICLE_WORDS.filter((w) => words.has(w)).sort();
  const hum = HUMAN_WORDS.filter((w) => words.has(w)).sort();
  if (veh.length >= 2) return out("vehicle", `vehicle controls in features: ${veh.join(", ")}` + (rt ? `; robot_type=${pyRepr(rt)}` : ""));
  if (hum.length) return out("human_motion", `human-motion features: ${hum.join(", ")}`);
  if (rtl && !["unknown", "none", "null", "robot"].includes(rtl)) {
    for (const [cat, pat] of ROBOT_TYPES) if (pat.test(rtl)) return out(cat, `robot_type=${pyRepr(rt)}`);
  }
  const has = (...ws) => ws.some((w) => words.has(w));
  const sides = has("left", "right") || [...words].some((w) => w.startsWith("left_") || w.startsWith("right_"));
  if (has("leg", "knee", "ankle", "hip", "waist", "torso") && (has("hand", "finger", "thumb") || sides)) {
    return out("humanoid", "body-part names (legs/waist with hands or two sides)");
  }
  if (has("gripper", "joint", "shoulder", "elbow", "wrist", "eef", "ee")) {
    if (has("base", "wheel", "odom", "chassis")) return out("mobile_manipulator", "arm and mobile-base dimension names");
    if (sides) return out("bimanual", "left/right arm dimension names");
    return out("arm", "arm dimension names (gripper / joints)");
  }
  const name = (repoId || "").split("/").pop().toLowerCase();
  if (name) {
    for (const [cat, pat] of ROBOT_TYPES) {
      if (CATEGORIES[cat][1] !== "fits") continue;
      const m = name.match(pat);
      if (m) return out(cat, `only the dataset name (${pyRepr(m[0])} in ${pyRepr(name)}); robot_type=${pyRepr(rt)}`);
    }
  }
  return out("unclear", rt ? `robot_type=${pyRepr(rt)} and no recognisable dimension names` : "no robot_type and no recognisable dimension names");
}
