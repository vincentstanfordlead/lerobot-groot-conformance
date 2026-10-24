// Browser/Node port of conformance/models.py: the LeRobot-native and openpi columns
// (CONTRACT_lerobot_openpi.md). Kept function-for-function close to the Python so
// tests/test_js_parity.py can hold them equal over every audited dataset.

export const LEROBOT_SHA = "ff71cae1ae2d09fd035553c35da65888ed6c8304";
export const OPENPI_SHA = "215abfb217dbac7d5f1273282331b9b1866c0479";
export const OPENPI_LEROBOT_SHA = "0cf864870cf29f4738d3ade893e6fd13fbd7cdb5";

// ---------------------------------------------------------------- packaging.version, the part that matters here

// PEP 440 as `packaging.version.parse` reads it: optional "v", release, pre/post/dev, optional local.
const VERSION_RE = new RegExp(
  "^\\s*v?(?:(\\d+)!)?(\\d+(?:\\.\\d+)*)" +
  "(?:[-_.]?(alpha|a|beta|b|preview|pre|c|rc)[-_.]?(\\d+)?)?" +
  "(?:(?:-(\\d+))|(?:[-_.]?(post|rev|r)[-_.]?(\\d+)?))?" +
  "(?:[-_.]?(dev)[-_.]?(\\d+)?)?" +
  "(?:\\+[a-z0-9]+(?:[-_.][a-z0-9]+)*)?\\s*$", "i");
const PRE = { alpha: "a", a: "a", beta: "b", b: "b", c: "rc", rc: "rc", pre: "rc", preview: "rc" };

export class Version {
  constructor(m) {
    this.epoch = m[1] ? Number(m[1]) : 0;
    this.release = m[2].split(".").map(Number);
    this.pre = m[3] ? [PRE[m[3].toLowerCase()], Number(m[4] ?? 0)] : null;
    this.post = m[5] !== undefined ? Number(m[5]) : m[6] ? Number(m[7] ?? 0) : null;
    this.dev = m[8] ? Number(m[9] ?? 0) : null;
  }
  get major() { return this.release[0]; }
  get minor() { return this.release.length > 1 ? this.release[1] : 0; }
  toString() {
    let s = (this.epoch ? `${this.epoch}!` : "") + this.release.join(".");
    if (this.pre) s += this.pre[0] + this.pre[1];
    if (this.post !== null) s += `.post${this.post}`;
    if (this.dev !== null) s += `.dev${this.dev}`;
    return s;
  }
  // packaging's ordering key: trailing zeros of the release do not count; a bare dev release sorts first,
  // a pre-release before its release, a post-release after it.
  key() {
    const rel = [...this.release];
    while (rel.length > 1 && rel[rel.length - 1] === 0) rel.pop();
    const preKey = this.pre ? [0, this.pre[0] === "a" ? 0 : this.pre[0] === "b" ? 1 : 2, this.pre[1]]
      : this.post === null && this.dev !== null ? [-1, 0, 0] : [1, 0, 0];
    return [this.epoch, rel, preKey, this.post === null ? [-1, 0] : [0, this.post], this.dev === null ? [1, 0] : [0, this.dev]];
  }
}

function cmpArr(a, b) {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i], y = b[i];
    if (x === undefined) return -1;
    if (y === undefined) return 1;
    const c = Array.isArray(x) ? cmpArr(x, y) : x < y ? -1 : x > y ? 1 : 0;
    if (c) return c;
  }
  return 0;
}
export const cmp = (a, b) => cmpArr(a.key(), b.key());
export const eq = (a, b) => cmp(a, b) === 0;

export function parseVersion(s) {
  const m = VERSION_RE.exec(String(s));
  return m ? new Version(m) : null;
}

export const LEROBOT_TARGET = parseVersion("3.0"); // vendor/lerobot_ff71cae  dataset_metadata.py:63
export const OPENPI_TARGET = parseVersion("2.1"); // vendor/lerobot_0cf8648  lerobot_dataset.py:77

// ---------------------------------------------------------------- revision selection (port of get_safe_version)

// -> Map<canonical version string, {version, names:Set}>; Python keys a dict by Version, so two names that
// parse to one version ("v3", "v3.0") share an entry.
export function parseVersions(refNames) {
  const out = new Map();
  for (const name of refNames) {
    const v = parseVersion(name);
    if (!v) continue;
    const k = JSON.stringify(v.key());
    if (!out.has(k)) out.set(k, { version: v, names: new Set() });
    out.get(k).names.add(name);
  }
  return out;
}

const hubVersions = (hub) => [...hub.values()].map((e) => e.version);
const entryFor = (hub, v) => hub.get(JSON.stringify(v.key()));
const maxOf = (vs) => vs.reduce((a, b) => (cmp(b, a) > 0 ? b : a));
const minOfV = (vs) => vs.reduce((a, b) => (cmp(b, a) < 0 ? b : a));
const firstName = (e) => [...e.names].sort()[0];

// -> [outcome, ref]: "none" | "ok" | "ref_missing" | "backward" | "forward"
export function selectRevision(hub, target) {
  if (!hub.size) return ["none", null];
  const ask = (v) => {
    const want = `v${v}`;
    return entryFor(hub, v).names.has(want) ? ["ok", want] : ["ref_missing", want];
  };
  if (entryFor(hub, target)) return ask(target);
  const vs = hubVersions(hub);
  const compatibles = vs.filter((v) => v.major === target.major && v.minor <= target.minor);
  if (compatibles.length) return ask(maxOf(compatibles));
  const lower = vs.filter((v) => v.major < target.major);
  if (lower.length) return ["backward", firstName(entryFor(hub, maxOf(lower)))];
  return ["forward", firstName(entryFor(hub, minOfV(vs.filter((v) => cmp(v, target) > 0))))];
}

// ---------------------------------------------------------------- facts about the dataset

// checks: results of runAll().checks (or a stored record's checks); info: parsed info.json or null;
// refNames: every branch and tag name, or null when the refs could not be read.
export function facts(checks, info, refNames) {
  const by = Object.fromEntries(checks.map((c) => [c.id, c]));
  const passed = (i) => by[i]?.passed ?? null;
  const data = (i, k) => by[i]?.data?.[k] ?? null;
  const verS = data("L2", "codebase_version");
  const ver = verS !== null ? parseVersion(String(verS)) : null;
  const ep = data("L5", "layout"), tk = data("L6", "layout"), st = data("L7", "layout");
  const v3 = (ver !== null && ver.major === 3) || ep === "parquet" || tk === "parquet";
  return {
    is_lerobot: passed("L1") === true,
    has_data: passed("L3") === true,
    version: ver,
    version_str: verS,
    layout: v3 ? "v3" : ep === "jsonl" || tk === "jsonl" ? "v2" : null,
    episodes_layout: ep, tasks_layout: tk, stats_layout: st,
    total_episodes: info?.total_episodes ?? data("L11", "total_episodes"),
    total_tasks: info?.total_tasks ?? null,
    refs: refNames === null ? null : parseVersions(refNames),
  };
}

const truthy = (x) => x !== null && x !== undefined && x !== 0 && x !== "" && x !== false;

function missingV3(f) {
  const miss = [];
  if (truthy(f.total_tasks) && f.tasks_layout !== "parquet") miss.push("meta/tasks.parquet");
  if (truthy(f.total_episodes) && f.episodes_layout !== "parquet") miss.push("meta/episodes/*.parquet");
  return miss;
}

function missingV2(f) {
  const miss = [];
  if (f.tasks_layout !== "jsonl") miss.push("meta/tasks.jsonl");
  if (f.episodes_layout !== "jsonl") miss.push("meta/episodes.jsonl");
  const old = f.version !== null && cmp(f.version, parseVersion("2.1")) < 0;
  const want = old ? "stats.json" : "episodes_stats.jsonl";
  if (f.stats_layout !== want) miss.push(`meta/${want}`);
  return miss;
}

const result = (verdict, steps, reason, extra = {}) => ({ verdict, steps, reason, ...extra });

function commonBlock(f) {
  if (!f.is_lerobot) return result("BLOCKED", [], "not a LeRobot dataset (no readable info.json)");
  if (!f.has_data) return result("BLOCKED", [], "no parquet under data/ (metadata-only upload)");
  if (f.refs === null) return result("UNASSESSED", [], "Hub refs unavailable (repo gone or private since the audit)");
  return null;
}

function tagNote(f, hub) {
  const majors = new Set(hubVersions(hub).map((v) => v.major));
  return { tag_info_mismatch: hub.size > 0 && f.version !== null && !majors.has(f.version.major) };
}

// ---------------------------------------------------------------- the two verdicts

export function lerobotVerdict(f) {
  const b = commonBlock(f);
  if (b) return b;
  const hub = f.refs;
  const [outcome, ref] = selectRevision(hub, LEROBOT_TARGET);
  const note = tagNote(f, hub);
  if (f.layout === null) return result("BLOCKED", [], "episode/task metadata layout not recognised", note);
  if (f.layout === "v3") {
    const miss = missingV3(f);
    if (miss.length) return result("BLOCKED", [], `missing ${miss.join(", ")}`, note);
    if (outcome === "ok") return result("PASS", [], `loader picks ${ref}`, { ref, ...note });
    if (outcome === "none") return result("NEEDS_TAG", ["TAG"], "no version-named ref (RuntimeError)", note);
    if (outcome === "ref_missing") return result("NEEDS_TAG", ["TAG"], `loader asks for ${ref}, which does not exist`, note);
    return result("NEEDS_TAG", ["TAG"], `latest ref is ${ref}; v3 files need a v3.0 ref`, note);
  }
  const ver = f.version;
  if (ver !== null && ver.major === 2 && ver.minor > 1)
    return result("BLOCKED", [], `codebase_version ${ver}: loader raises NotImplementedError, no converter named`, note);
  if (ver !== null && ver.major < 2) return result("BLOCKED", [], `codebase_version ${ver}: no converter`, note);
  const steps = (ver !== null && eq(ver, parseVersion("2.0")) ? ["CONVERT_V20_V21"] : []).concat(["CONVERT"]);
  if (outcome === "none") steps.push("TAG");
  return result("NEEDS_CONVERT", steps, `v2 data; loader target is v3.0 (outcome: ${outcome})`, note);
}

export function openpiVerdict(f) {
  const b = commonBlock(f);
  if (b) return b;
  const hub = f.refs;
  const [outcome, ref] = selectRevision(hub, OPENPI_TARGET);
  const note = { ...tagNote(f, hub), unverified: ["timestamp_sync"] };
  if (f.layout === null) return result("BLOCKED", [], "episode/task metadata layout not recognised", note);
  if (f.layout === "v3") {
    if (outcome === "ok")
      return result("NEEDS_CONFIG", ["CONFIG", "NORM_STATS"], `loader picks older ref ${ref}; files at that ref not inspected`,
        { ref, files_at_ref_unverified: true, ...note });
    return result("NEEDS_CONVERT", outcome === "none" ? ["CONVERT", "TAG"] : ["CONVERT"],
      `v3 data; loader target is v2.1 (outcome: ${outcome})`, note);
  }
  const ver = f.version;
  if (ver !== null && ver.major !== 2) return result("BLOCKED", [], `codebase_version ${ver}: no converter`, note);
  if (ver !== null && ver.minor > 1)
    return result("BLOCKED", [], `codebase_version ${ver}: ForwardCompatibilityError unless re-tagged v2.1`, note);
  const miss = missingV2(f);
  if (miss.length) return result("BLOCKED", [], `missing ${miss.join(", ")}`, note);
  if (outcome === "ok") return result("NEEDS_CONFIG", ["CONFIG", "NORM_STATS"], `loader picks ${ref}`, { ref, ...note });
  if (outcome === "none") return result("NEEDS_TAG", ["TAG", "CONFIG", "NORM_STATS"], "no version-named ref", note);
  if (outcome === "ref_missing") return result("NEEDS_TAG", ["TAG", "CONFIG", "NORM_STATS"], `loader asks for ${ref}, which does not exist`, note);
  return result("BLOCKED", [], `only ${outcome} refs (${ref}) for v2 files: re-tag as v2.1`, note);
}

// The ref a loader would pull, with its commit, when that is not the commit that was inspected.
export function snapshotToInspect(refs, inspectedSha, target) {
  const names = [...refs.map((r) => r.name)];
  const [outcome, ref] = selectRevision(parseVersions(names), target);
  if (outcome !== "ok") return null;
  const commit = refs.find((r) => r.name === ref)?.commit;
  return commit && commit !== inspectedSha ? { ref, commit } : null;
}

// ---------------------------------------------------------------- π0.5 model fit (contract §7; port of models.pi05_fit)

export const PI05_ACTION_DIM = 32; // src_openpi_models_pi0_config.py:25 (state shares it, :80)
export const PI05_ACTION_HORIZON = 50; // src_openpi_models_pi0_config.py:26
export const PI05_IMAGE_SLOTS = ["base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb"]; // src_openpi_models_model.py:39-43
export const PI05_IMAGE_RESOLUTION = [224, 224]; // src_openpi_models_model.py:47
const PI05_LOW_FPS = 15;
export const PI05_STATUS = ["OK", "NOTE", "ADAPT", "FAIL"];

const isObj = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
const isInt = (x) => Number.isInteger(x) && typeof x === "number";
const isFloat = (ft) => String(ft.dtype ?? "").startsWith("float");
// Python's f"{x:g}" for the fps values that occur (integers and short decimals)
const g = (x) => String(Number(x.toPrecision(6)));
// models._half_up: round half away from zero (x >= 0) on both sides, then format
const round = (x, n) => Math.floor(x * 10 ** n + 0.5) / 10 ** n;
const fix = (x, n) => round(x, n).toFixed(n);

function vecDim(ft) {
  const s = ft.shape;
  if (!Array.isArray(s) || !s.length || !s.every(isInt)) return null;
  if (s.length === 1 || (s.length === 2 && s[0] === 1)) return s[s.length - 1];
  return null;
}

function vectorGroup(F, whole, prefixes) {
  for (const k of whole) {
    if (isObj(F[k])) return { keys: [k], dim: vecDim(F[k]), float: isFloat(F[k]), split: false };
  }
  const parts = Object.keys(F).filter((k) => isObj(F[k]) && prefixes.some((p) => k.startsWith(p)) && isFloat(F[k]) && vecDim(F[k]))
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  if (!parts.length) return { keys: [], dim: null, float: false, split: false };
  return { keys: parts, dim: parts.reduce((t, k) => t + vecDim(F[k]), 0), float: true, split: true };
}

function camera(key, ft) {
  const s = Array.isArray(ft.shape) ? ft.shape : [];
  const names = Array.isArray(ft.names) ? ft.names.map((n) => String(n).toLowerCase()) : [];
  let h = null, w = null, c = null;
  if (s.length === 3 && names.length === 3 && names.includes("height") && names.includes("width")) {
    h = s[names.indexOf("height")]; w = s[names.indexOf("width")];
    c = s[[0, 1, 2].filter((i) => names[i] !== "height" && names[i] !== "width")[0]];
  } else if (s.length === 3) {
    if ([1, 3, 4].includes(s[2])) [h, w, c] = s;
    else if ([1, 3, 4].includes(s[0])) [c, h, w] = s;
  }
  const rgb = c === 3 && !key.toLowerCase().includes("depth") && !names.includes("depth");
  return { key, height: h, width: w, channels: c, rgb };
}

const check = (id, status, detail, data) => ({ id, status, detail, ...(data && Object.keys(data).length ? { data } : {}) });

export function pi05Fit(info) {
  if (!isObj(info) || !isObj(info.features)) return { verdict: "UNASSESSED", checks: [], reason: "no readable info.json" };
  const F = info.features;
  const out = [];

  const act = vectorGroup(F, ["action", "actions"], ["action.", "actions."]);
  if (!act.keys.length) out.push(check("P1", "FAIL", "no action feature: π0.5 trains on action chunks"));
  else if (!act.float || act.dim === null) {
    const ft = F[act.keys[0]];
    out.push(check("P1", "FAIL", `\`${act.keys[0]}\` is not a float vector (dtype ${pyRepr(ft.dtype)}, shape ${pyRepr(ft.shape)})`));
  } else {
    out.push(act.split
      ? check("P1", "ADAPT", `actions split over ${act.keys.length} keys; the config must concatenate them into one vector`, { keys: act.keys })
      : check("P1", "OK", `\`${act.keys[0]}\` (float vector)`));
    const d = act.dim;
    out.push(check("P2", d > PI05_ACTION_DIM ? "FAIL" : "OK", d > PI05_ACTION_DIM
      ? `action dim ${d} > ${PI05_ACTION_DIM}: openpi pads but never truncates, and pi05_base is ${PI05_ACTION_DIM}-wide`
      : `action dim ${d}, zero-padded to ${PI05_ACTION_DIM}`, { dim: d }));
  }

  const st = vectorGroup(F, ["observation.state", "state"], ["observation.state.", "observation.states."]);
  if (!st.keys.length || !st.float || st.dim === null)
    out.push(check("P3", "ADAPT", "no float state vector: π0.5 puts the state in its prompt and raises 'State is required' (transforms.py:256-258); set discrete_state_input=False or feed zeros"));
  else if (st.dim > PI05_ACTION_DIM)
    out.push(check("P3", "FAIL", `state dim ${st.dim} > ${PI05_ACTION_DIM}: the model's state input is ${PI05_ACTION_DIM}-wide (pi0_config.py:80)`, { dim: st.dim }));
  else if (st.split)
    out.push(check("P3", "ADAPT", `state split over ${st.keys.length} keys (dim ${st.dim}); the config must concatenate them`, { keys: st.keys, dim: st.dim }));
  else out.push(check("P3", "OK", `state dim ${st.dim}, quantile-normalised then tokenised into the prompt`, { dim: st.dim }));

  const cams = Object.entries(F).filter(([, ft]) => isObj(ft) && (ft.dtype === "video" || ft.dtype === "image")).map(([k, ft]) => camera(k, ft));
  const rgb = cams.filter((c) => c.rgb);
  const other = cams.filter((c) => !c.rgb).map((c) => c.key);
  const skip = other.length ? `; not RGB, unusable as is: ${other.join(", ")}` : "";
  const n = rgb.length, slots = PI05_IMAGE_SLOTS.length;
  if (n === 0) out.push(check("P4", "FAIL", "no RGB camera: π0.5 is a vision-language-action model and every image slot would be blank" + skip, { n_rgb: 0 }));
  else if (n > slots) out.push(check("P4", "ADAPT", `${n} RGB cameras for ${slots} slots (one base, two wrist); the config must choose which to keep` + skip, { n_rgb: n }));
  else out.push(check("P4", "OK", `${n} RGB camera(s) for ${slots} slots; empty slots are zero images, masked` + skip, { n_rgb: n }));
  if (rgb.length) {
    const [H, W] = PI05_IMAGE_RESOLUTION;
    const sized = rgb.filter((c) => truthy(c.height) && truthy(c.width));
    const small = sized.filter((c) => c.height < H || c.width < W).map((c) => c.key);
    const wide = sized.filter((c) => Math.max(c.height, c.width) >= 1.5 * Math.min(c.height, c.width)).map((c) => c.key);
    const bits = [];
    if (small.length) bits.push(`below ${H}x${W}, upscaled: ${small.join(", ")}`);
    if (wide.length) bits.push(`aspect >= 1.5, so a third or more of the ${H}x${W} input is black padding: ${wide.join(", ")}`);
    out.push(check("P5", bits.length ? "NOTE" : "OK", bits.length ? bits.join("; ") : `all RGB cameras resize to ${H}x${W} with little padding`));
  }

  const fps = info.fps;
  if (typeof fps !== "number" || !(fps > 0)) out.push(check("P6", "FAIL", "no fps in info.json: openpi builds the action chunk's timestamps from it"));
  else {
    const secs = PI05_ACTION_HORIZON / fps;
    out.push(fps <= PI05_LOW_FPS
      ? check("P6", "ADAPT", `${g(fps)} Hz: the default ${PI05_ACTION_HORIZON}-step chunk spans ${fix(secs, 1)} s; openpi's own low-rate π0.5 configs shorten action_horizon (pi05_libero 10, pi05_droid 15)`, { fps, chunk_s: round(secs, 2) })
      : check("P6", "OK", `${g(fps)} Hz: a ${PI05_ACTION_HORIZON}-step chunk spans ${fix(secs, 1)} s`, { fps, chunk_s: round(secs, 2) }));
    const eps = info.total_episodes, frames = info.total_frames;
    if (isInt(eps) && isInt(frames) && eps > 0) {
      const mean = frames / eps;
      out.push(check("P7", mean < PI05_ACTION_HORIZON ? "NOTE" : "OK", mean < PI05_ACTION_HORIZON
        ? `episodes average ${fix(mean, 0)} frames, shorter than one ${PI05_ACTION_HORIZON}-step chunk: most targets are padding`
        : `episodes average ${fix(mean, 0)} frames`, { mean_frames: round(mean, 1) }));
    }
  }

  const tasks = info.total_tasks ?? null;
  if (isInt(tasks) && tasks > 0 && isObj(F.task_index))
    out.push(check("P8", "OK", `${tasks} task string(s); prompt_from_task=True gives each frame its prompt`, { tasks }));
  else out.push(check("P8", "ADAPT", "no task strings to use as prompts: set default_prompt in the config, or π0.5 raises 'Prompt is required'", { tasks }));

  const worst = Math.max(0, ...out.map((c) => PI05_STATUS.indexOf(c.status)));
  const verdict = worst === 3 ? "NO_FIT" : worst === 2 ? "ADAPT" : "FIT";
  const bad = out.filter((c) => c.status === "ADAPT" || c.status === "FAIL");
  return { verdict, checks: out, issues: bad.map((c) => c.id), reason: bad.map((c) => c.detail).join("; ") || "fits π0.5 defaults" };
}

// Python repr for the dtype/shape values in the P1 message (strings quoted, lists of ints, None)
function pyRepr(x) {
  if (x === null || x === undefined) return "None";
  if (typeof x === "string") return `'${x}'`;
  if (Array.isArray(x)) return `[${x.map(pyRepr).join(", ")}]`;
  if (typeof x === "boolean") return x ? "True" : "False";
  return String(x);
}

// A starting point for the openpi config, from the same info.json (web app only; not part of the verdict).
// Base slot: the first RGB camera without "wrist" in its key; wrist slots: the "wrist" cameras, then the rest.
export function pi05Draft(info, fit) {
  if (!isObj(info) || !isObj(info.features) || fit.verdict === "UNASSESSED") return null;
  const F = info.features;
  const rgb = Object.entries(F).filter(([, ft]) => isObj(ft) && (ft.dtype === "video" || ft.dtype === "image"))
    .map(([k, ft]) => camera(k, ft)).filter((c) => c.rgb).map((c) => c.key);
  const isWrist = (k) => /wrist|hand|gripper|eef/i.test(k);
  const base = rgb.find((k) => !isWrist(k)) ?? rgb[0] ?? null;
  const rest = rgb.filter((k) => k !== base);
  const wrists = [...rest.filter(isWrist), ...rest.filter((k) => !isWrist(k))];
  const slots = { base_0_rgb: base, left_wrist_0_rgb: wrists[0] ?? null, right_wrist_0_rgb: wrists[1] ?? null };
  const act = vectorGroup(F, ["action", "actions"], ["action.", "actions."]);
  const st = vectorGroup(F, ["observation.state", "state"], ["observation.state.", "observation.states."]);
  const fps = typeof info.fps === "number" && info.fps > 0 ? info.fps : null;
  // openpi's own π0.5 configs: pi05_libero (10 Hz) uses 10, pi05_droid (15 Hz) 15; otherwise keep the default
  const horizon = fps !== null && fps <= PI05_LOW_FPS ? Math.max(1, Math.round(fps)) : PI05_ACTION_HORIZON;
  return { slots, dropped: wrists.slice(2), action: act.keys, state: st.keys, horizon, fps,
    prompt: isInt(info.total_tasks) && info.total_tasks > 0 && isObj(F.task_index) };
}
